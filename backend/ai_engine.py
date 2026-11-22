"""
AI Engine
=========
Wraps every language-model call used by InterviewRAG:

  1. summarize_resume()      -> structured JSON summary of the candidate
  2. generate_questions()    -> role/difficulty-specific interview questions
  3. evaluate_answer()       -> per-answer scoring + feedback
  4. generate_final_report() -> overall performance summary

Providers (set LLM_PROVIDER in .env):
  auto   (default) Gemini first; if Gemini stays busy, fall back to local Ollama
  gemini only Gemini (with retries)
  ollama only the local Ollama model (no API key traffic, works offline)

Questions and scoring can be grounded in notes retrieved by RAG.
"""

import json
import os
import time

import requests
from google import genai
from google.genai import errors, types
from config import Config

RETRYABLE_CODES = (429, 500, 503)
RETRY_WAITS = (0, 4, 10)  # seconds to wait before Gemini attempt 1, 2, 3
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
LOCAL_MODEL = os.getenv("LOCAL_MODEL", "qwen3:4b-instruct")
OLLAMA_TIMEOUT = (5, 240)


class AIInterviewEngine:
    def __init__(self):
        Config.validate()
        self.client = genai.Client(api_key=Config.GEMINI_API_KEY)
        self.model = Config.GEMINI_MODEL

    # ------------------------------------------------------------ providers
    def _chat_gemini(self, system_prompt: str, user_prompt: str, json_mode: bool) -> str:
        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=0.4,
            response_mime_type="application/json" if json_mode else "text/plain",
        )
        last_error = None
        for wait in RETRY_WAITS:
            if wait:
                time.sleep(wait)
            try:
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=user_prompt,
                    config=config,
                )
                return response.text.strip()
            except errors.APIError as e:
                last_error = e
                if getattr(e, "code", None) not in RETRYABLE_CODES:
                    raise
                print(f"Gemini busy (code {e.code}); retrying...")
        raise last_error

    def _chat_ollama(self, system_prompt: str, user_prompt: str, json_mode: bool) -> str:
        payload = {
            "model": LOCAL_MODEL,
            "stream": False,
            "options": {"temperature": 0.4},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        if json_mode:
            payload["format"] = "json"
        response = requests.post(
            f"{OLLAMA_URL}/api/chat", json=payload, timeout=OLLAMA_TIMEOUT
        )
        response.raise_for_status()
        return response.json()["message"]["content"].strip()

    def _chat(self, system_prompt: str, user_prompt: str, json_mode: bool = True) -> str:
        """One helper so every call shares the same provider and error handling."""
        provider = os.getenv("LLM_PROVIDER", "auto").strip().lower()
        print(f"LLM provider: {provider}")

        if provider == "ollama":
            print(f"Using local model {LOCAL_MODEL}...")
            return self._chat_ollama(system_prompt, user_prompt, json_mode)

        try:
            return self._chat_gemini(system_prompt, user_prompt, json_mode)
        except errors.APIError as e:
            if provider == "auto" and getattr(e, "code", None) in RETRYABLE_CODES:
                print(f"Gemini unavailable; falling back to local model {LOCAL_MODEL}...")
                try:
                    return self._chat_ollama(system_prompt, user_prompt, json_mode)
                except requests.RequestException as oe:
                    print(f"Local fallback failed: {oe}")
            raise

    # ------------------------------------------------------------ features
    def summarize_resume(self, resume_text: str) -> dict:
        """Turn raw resume text into a structured skills/experience summary."""
        system_prompt = (
            "You are a technical recruiter. Extract a structured summary "
            "from the resume text below. Respond ONLY with valid JSON in "
            "exactly this schema, no extra commentary: "
            '{"role_fit": str, "skills": [str], "projects": [str], '
            '"experience_level": str}'
        )
        raw = self._chat(system_prompt, resume_text[:6000])
        return self._safe_json(raw)

    def generate_questions(self, role: str, difficulty: str,
                           num_questions: int, resume_summary: dict = None,
                           notes_context: str = "") -> list:
        """Generate a list of {question, topic} objects tailored to the role."""
        context = (
            f"Candidate resume summary: {json.dumps(resume_summary)}"
            if resume_summary else "No resume was provided."
        )
        system_prompt = (
            "You are a senior technical interviewer. Generate interview "
            "questions tailored to the given role and difficulty level. "
            "Mix conceptual and practical questions. "
            "If study notes are provided, base the questions on them. "
            "Write exactly the requested number of questions. "
            "Respond ONLY with a valid JSON object shaped exactly like: "
            '{"questions": [{"question": "...", "topic": "..."}]}'
        )
        user_prompt = (
            f"Role: {role}\n"
            f"Difficulty: {difficulty}\n"
            f"Number of questions: {num_questions}\n"
            f"{context}\n"
            + (f"Study notes:\n{notes_context}" if notes_context else "")
        )
        raw = self._chat(system_prompt, user_prompt)
        questions = self._extract_questions(self._safe_json(raw))
        if not questions:
            print("RAW MODEL OUTPUT:", raw[:1500])
        return questions

    def evaluate_answer(self, question: str, answer: str, reference: str = "") -> dict:
        """Score a single answer and produce actionable feedback."""
        system_prompt = (
            "You are a strict but fair technical interviewer grading a "
            "candidate's answer. If reference notes are provided, "
            "judge correctness against them. Respond ONLY with valid JSON: "
            '{"score": int (0-10), "strengths": [str], '
            '"improvements": [str], "ideal_answer_tip": str}'
        )
        user_prompt = (
            f"Question: {question}\n"
            f"Candidate answer: {answer}\n"
            + (f"Reference notes:\n{reference}" if reference else "")
        )
        raw = self._chat(system_prompt, user_prompt)
        result = self._safe_json(raw)
        if not result:
            print("RAW MODEL OUTPUT (evaluation):", raw[:1500])
        return result

    def generate_final_report(self, qa_records: list) -> str:
        """Produce a short overall performance summary across all answers."""
        system_prompt = (
            "You are an interview coach. Given a full mock interview "
            "transcript with per-question scores, write a concise, honest, "
            "encouraging overall performance summary (150-200 words) "
            "covering strengths, weak areas, and 2-3 concrete next steps. "
            "Respond with plain text, not JSON."
        )
        return self._chat(system_prompt, json.dumps(qa_records), json_mode=False)

    # ------------------------------------------------------------ helpers
    @staticmethod
    def _safe_json(raw: str):
        """Strip markdown fences and any text around the JSON, then parse."""
        cleaned = raw.replace("```json", "").replace("```", "").strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass
        for open_char, close_char in (("{", "}"), ("[", "]")):
            start, end = cleaned.find(open_char), cleaned.rfind(close_char)
            if start != -1 and end > start:
                try:
                    return json.loads(cleaned[start:end + 1])
                except json.JSONDecodeError:
                    continue
        return {}

    @staticmethod
    def _extract_questions(data) -> list:
        """Accept the shapes models commonly return; normalise to [{question, topic}]."""
        if isinstance(data, dict):
            if isinstance(data.get("question"), str):
                data = [data]  # a single question object
            else:
                lists = [v for v in data.values() if isinstance(v, list)]
                data = lists[0] if lists else list(data.values())
        if not isinstance(data, list):
            return []

        questions = []
        for item in data:
            if isinstance(item, str) and item.strip():
                questions.append({"question": item.strip(), "topic": ""})
            elif isinstance(item, dict):
                text = item.get("question") or item.get("text") or item.get("q")
                if isinstance(text, str) and text.strip():
                    questions.append(
                        {"question": text.strip(), "topic": str(item.get("topic", ""))}
                    )
        return questions

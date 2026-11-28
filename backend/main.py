import os
import random
import tempfile
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from google.genai import errors as genai_errors
from pydantic import BaseModel

import rag_core
from ai_engine import AIInterviewEngine
from db import init_db, list_sessions, save_answer, save_session
from resume_parser import extract_text_from_pdf

state: dict = {}      # RAG index + engine, built once at startup
sessions: dict = {}   # session_id -> questions and answer records (in memory)


@asynccontextmanager
async def lifespan(app: FastAPI):
    items = rag_core.load_chunks_with_sources()
    if not items:
        raise RuntimeError(
            "No readable notes found in backend/docs. Add PDF, .md or .txt files."
        )
    state["items"] = items
    state["vectors"] = rag_core.embed_in_batches([i["text"] for i in items])
    state["engine"] = AIInterviewEngine()
    print(f"Index ready: {len(items)} chunks loaded.")

    # History is optional: if Postgres is down, interviews still work.
    try:
        init_db()
        print("Database ready.")
    except Exception as e:
        print(f"Database unavailable, history will not be saved: {e}")
    yield


app = FastAPI(title="InterviewRAG", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class StartRequest(BaseModel):
    role: str
    difficulty: str = "medium"
    num_questions: int = 5
    topic: str = ""          # e.g. "Prompt Engineering"; empty means any topic
    resume_summary: dict | None = None


class AnswerRequest(BaseModel):
    index: int
    answer: str


def ai_error(e: Exception) -> HTTPException:
    """Turn a Gemini API failure into a clear message instead of a bare 500."""
    print(f"Gemini error: {e}")
    code = getattr(e, "code", "unknown")
    return HTTPException(
        503,
        f"The AI service had a problem (code {code}). Please try again in a minute.",
    )


@app.get("/topics")
def topics():
    """Topics offered in the UI (kept here so frontend and backend agree)."""
    return {
        "topics": [
            "Large Language Models (LLMs)",
            "Prompt Engineering",
            "Generative AI",
            "Retrieval-Augmented Generation (RAG)",
            "Vector Databases",
        ]
    }


@app.post("/resume")
async def upload_resume(file: UploadFile = File(...)):
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(await file.read())
        path = tmp.name
    try:
        text = extract_text_from_pdf(path)
    finally:
        os.remove(path)
    try:
        return state["engine"].summarize_resume(text)
    except genai_errors.APIError as e:
        raise ai_error(e) from e


@app.post("/session/start")
def start_session(req: StartRequest):
    topic = req.topic.strip()

    # Search the notes by topic (or by role if no topic). Take a pool of the
    # best chunks and sample from it, so repeated interviews are not identical.
    query = topic or f"{req.role} interview"
    pool = rag_core.retrieve_with_sources(
        query, state["items"], state["vectors"], k=8
    )
    hits = random.sample(pool, k=min(5, len(pool)))
    notes = "\n".join(h["text"] for h in hits)

    role_for_prompt = f"{req.role} (focus on: {topic})" if topic else req.role
    try:
        questions = state["engine"].generate_questions(
            role_for_prompt, req.difficulty, req.num_questions,
            req.resume_summary, notes_context=notes,
        )
    except genai_errors.APIError as e:
        raise ai_error(e) from e
    if not questions:
        raise HTTPException(502, "Could not generate questions")
    sid = uuid.uuid4().hex
    sessions[sid] = {"questions": questions, "records": []}
    save_session(sid, req.role, topic, req.difficulty, len(questions))
    return {"session_id": sid, "questions": questions}


@app.post("/session/{sid}/answer")
def answer(sid: str, body: AnswerRequest):
    session = sessions.get(sid)
    if not session:
        raise HTTPException(404, "Session not found")
    if not 0 <= body.index < len(session["questions"]):
        raise HTTPException(400, "Invalid question index")
    q = session["questions"][body.index]
    hits = rag_core.retrieve_with_sources(
        q["question"], state["items"], state["vectors"]
    )
    reference = "\n".join(h["text"] for h in hits)
    try:
        evaluation = state["engine"].evaluate_answer(
            q["question"], body.answer, reference=reference
        )
    except genai_errors.APIError as e:
        raise ai_error(e) from e
    session["records"].append({
        "question": q["question"],
        "topic": q.get("topic", ""),
        "answer": body.answer,
        "evaluation": evaluation,
    })
    save_answer(sid, q["question"], body.answer, evaluation, hits)
    return {"evaluation": evaluation, "sources": hits}


@app.get("/session/{sid}/report")
def report(sid: str):
    session = sessions.get(sid)
    if not session or not session["records"]:
        raise HTTPException(404, "No answers yet")
    records = session["records"]
    scores = [
        r["evaluation"]["score"]
        for r in records
        if isinstance(r.get("evaluation"), dict)
        and isinstance(r["evaluation"].get("score"), (int, float))
    ]
    try:
        summary = state["engine"].generate_final_report(records)
    except genai_errors.APIError as e:
        raise ai_error(e) from e
    return {
        "average_score": round(sum(scores) / len(scores), 1) if scores else 0,
        "records": records,
        "summary": summary,
    }


@app.get("/history")
def history():
    """Latest saved interviews with answer count and average score."""
    return {"sessions": list_sessions()}
"use client";

import { useState } from "react";

const API = "http://127.0.0.1:8000";

type Question = { question: string; topic?: string };
type Evaluation = {
  score?: number;
  strengths?: string[];
  improvements?: string[];
  ideal_answer_tip?: string;
};
type Source = { text: string; source: string; score: number };

export default function Home() {
  const [role, setRole] = useState("Java Developer");
  const [difficulty, setDifficulty] = useState("medium");
  const [count, setCount] = useState(3);

  const [sessionId, setSessionId] = useState("");
  const [questions, setQuestions] = useState<Question[]>([]);
  const [current, setCurrent] = useState(0);
  const [answer, setAnswer] = useState("");
  const [evaluation, setEvaluation] = useState<Evaluation | null>(null);
  const [sources, setSources] = useState<Source[]>([]);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function startInterview() {
    setLoading(true);
    setError("");
    try {
      const res = await fetch(`${API}/session/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ role, difficulty, num_questions: count }),
      });
      if (!res.ok) {
        throw new Error(`Server error ${res.status}. If it is 500, Gemini may be busy - try again in a minute.`);
      }
      const data = await res.json();
      setSessionId(data.session_id);
      setQuestions(data.questions);
      setCurrent(0);
      setAnswer("");
      setEvaluation(null);
      setSources([]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setLoading(false);
    }
  }

  async function submitAnswer() {
    if (!answer.trim()) return;
    setLoading(true);
    setError("");
    try {
      const res = await fetch(`${API}/session/${sessionId}/answer`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ index: current, answer }),
      });
      if (!res.ok) {
        throw new Error(`Server error ${res.status}. Try again in a minute.`);
      }
      const data = await res.json();
      setEvaluation(data.evaluation);
      setSources(data.sources);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setLoading(false);
    }
  }

  function nextQuestion() {
    setCurrent((c) => c + 1);
    setAnswer("");
    setEvaluation(null);
    setSources([]);
  }

  function reset() {
    setQuestions([]);
    setSessionId("");
    setCurrent(0);
    setAnswer("");
    setEvaluation(null);
    setSources([]);
    setError("");
  }

  const finished = questions.length > 0 && current >= questions.length;

  return (
    <main className="min-h-screen bg-zinc-950 text-zinc-100 flex justify-center px-4 py-12">
      <div className="w-full max-w-2xl">
        <h1 className="text-3xl font-bold">InterviewRAG</h1>
        <p className="text-zinc-400 mt-1 mb-8">
          Practice interviews grounded in your own notes.
        </p>

        {error && (
          <div className="mb-6 rounded-lg border border-red-800 bg-red-950 p-3 text-sm text-red-200">
            {error}
          </div>
        )}

        {/* 1) Setup form */}
        {questions.length === 0 && (
          <div className="space-y-5 rounded-xl border border-zinc-800 bg-zinc-900 p-6">
            <div>
              <label className="block text-sm text-zinc-400 mb-1">Role</label>
              <input
                value={role}
                onChange={(e) => setRole(e.target.value)}
                className="w-full rounded-lg bg-zinc-800 px-3 py-2 outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm text-zinc-400 mb-1">Difficulty</label>
                <select
                  value={difficulty}
                  onChange={(e) => setDifficulty(e.target.value)}
                  className="w-full rounded-lg bg-zinc-800 px-3 py-2"
                >
                  <option value="easy">Easy</option>
                  <option value="medium">Medium</option>
                  <option value="hard">Hard</option>
                </select>
              </div>
              <div>
                <label className="block text-sm text-zinc-400 mb-1">Questions</label>
                <select
                  value={count}
                  onChange={(e) => setCount(Number(e.target.value))}
                  className="w-full rounded-lg bg-zinc-800 px-3 py-2"
                >
                  {[3, 5, 7].map((n) => (
                    <option key={n} value={n}>
                      {n}
                    </option>
                  ))}
                </select>
              </div>
            </div>
            <button
              onClick={startInterview}
              disabled={loading || !role.trim()}
              className="w-full rounded-lg bg-indigo-600 py-2.5 font-medium hover:bg-indigo-500 disabled:opacity-50"
            >
              {loading ? "Preparing questions..." : "Start interview"}
            </button>
          </div>
        )}

        {/* 2) Question + answer + feedback */}
        {questions.length > 0 && !finished && (
          <div className="space-y-5">
            <div className="text-sm text-zinc-400">
              Question {current + 1} of {questions.length}
              {questions[current].topic ? ` · ${questions[current].topic}` : ""}
            </div>
            <div className="rounded-xl border border-zinc-800 bg-zinc-900 p-6 text-lg">
              {questions[current].question}
            </div>

            <textarea
              value={answer}
              onChange={(e) => setAnswer(e.target.value)}
              disabled={loading || evaluation !== null}
              rows={5}
              placeholder="Type your answer..."
              className="w-full rounded-lg bg-zinc-800 px-3 py-2 outline-none focus:ring-2 focus:ring-indigo-500 disabled:opacity-60"
            />

            {evaluation === null ? (
              <button
                onClick={submitAnswer}
                disabled={loading || !answer.trim()}
                className="rounded-lg bg-indigo-600 px-5 py-2.5 font-medium hover:bg-indigo-500 disabled:opacity-50"
              >
                {loading ? "Checking..." : "Submit answer"}
              </button>
            ) : (
              <div className="space-y-4 rounded-xl border border-zinc-800 bg-zinc-900 p-6">
                <div className="text-2xl font-bold">
                  Score: {evaluation.score ?? "?"}/10
                </div>
                {(evaluation.strengths ?? []).length > 0 && (
                  <div>
                    <div className="font-semibold text-green-400">Strengths</div>
                    <ul className="list-disc pl-5 text-zinc-300">
                      {(evaluation.strengths ?? []).map((s, i) => (
                        <li key={i}>{s}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {(evaluation.improvements ?? []).length > 0 && (
                  <div>
                    <div className="font-semibold text-amber-400">To improve</div>
                    <ul className="list-disc pl-5 text-zinc-300">
                      {(evaluation.improvements ?? []).map((s, i) => (
                        <li key={i}>{s}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {evaluation.ideal_answer_tip && (
                  <div className="text-zinc-300">
                    <span className="font-semibold">Tip: </span>
                    {evaluation.ideal_answer_tip}
                  </div>
                )}

                {sources.length > 0 && (
                  <div className="border-t border-zinc-800 pt-4">
                    <div className="font-semibold text-indigo-400 mb-2">
                      Checked against your notes
                    </div>
                    {sources.map((s, i) => (
                      <div key={i} className="mb-3 rounded-lg bg-zinc-800 p-3 text-sm">
                        <div className="text-xs text-zinc-400 mb-1">{s.source}</div>
                        <div className="text-zinc-300">{s.text}</div>
                      </div>
                    ))}
                  </div>
                )}

                <button
                  onClick={nextQuestion}
                  className="rounded-lg bg-indigo-600 px-5 py-2.5 font-medium hover:bg-indigo-500"
                >
                  {current + 1 < questions.length ? "Next question" : "Finish"}
                </button>
              </div>
            )}
          </div>
        )}

        {/* 3) Finished */}
        {finished && (
          <div className="rounded-xl border border-zinc-800 bg-zinc-900 p-6 space-y-4">
            <div className="text-xl font-semibold">Interview complete</div>
            <p className="text-zinc-400">The full report page comes in the next step.</p>
            <button
              onClick={reset}
              className="rounded-lg bg-indigo-600 px-5 py-2.5 font-medium hover:bg-indigo-500"
            >
              Start another
            </button>
          </div>
        )}
      </div>
    </main>
  );
}
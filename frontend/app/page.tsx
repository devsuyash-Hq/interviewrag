"use client";

import { useEffect, useRef, useState } from "react";

const API = "http://127.0.0.1:8000";

const TOPICS = [
  { value: "", label: "Any topic" },
  { value: "Large Language Models (LLMs)", label: "Large Language Models (LLMs)" },
  { value: "Prompt Engineering", label: "Prompt Engineering" },
  { value: "Generative AI", label: "Generative AI" },
  { value: "Retrieval-Augmented Generation (RAG)", label: "Retrieval-Augmented Generation (RAG)" },
  { value: "Vector Databases", label: "Vector Databases" },
];

type Question = { question: string; topic?: string };
type Evaluation = {
  score?: number;
  strengths?: string[];
  improvements?: string[];
  ideal_answer_tip?: string;
};
type Source = { text: string; source: string; score: number };
type ReportRecord = {
  question: string;
  topic?: string;
  answer: string;
  evaluation: Evaluation;
};
type ReportData = {
  average_score: number;
  summary: string;
  records: ReportRecord[];
};

async function readError(res: Response): Promise<string> {
  try {
    const data = await res.json();
    if (typeof data.detail === "string") return data.detail;
  } catch {
    // response was not JSON; fall through to the generic message
  }
  return `Server error ${res.status}. Please try again.`;
}

export default function Home() {
  const [role, setRole] = useState("Generative AI Engineer");
  const [topic, setTopic] = useState("");
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

  const [report, setReport] = useState<ReportData | null>(null);
  const [reportLoading, setReportLoading] = useState(false);
  const reportRequested = useRef(false);

  async function startInterview() {
    setLoading(true);
    setError("");
    try {
      const res = await fetch(`${API}/session/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ role, topic, difficulty, num_questions: count }),
      });
      if (!res.ok) throw new Error(await readError(res));
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
      if (!res.ok) throw new Error(await readError(res));
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
    setReport(null);
    reportRequested.current = false;
    setQuestions([]);
    setSessionId("");
    setCurrent(0);
    setAnswer("");
    setEvaluation(null);
    setSources([]);
    setError("");
  }

  const finished = questions.length > 0 && current >= questions.length;

  // When the interview ends, ask the backend for the report (once).
  useEffect(() => {
    if (!finished || !sessionId || reportRequested.current) return;
    reportRequested.current = true;
    (async () => {
      setReportLoading(true);
      try {
        const res = await fetch(`${API}/session/${sessionId}/report`);
        if (!res.ok) throw new Error(await readError(res));
        setReport(await res.json());
      } catch (e) {
        setError(e instanceof Error ? e.message : "Could not load the report.");
      } finally {
        setReportLoading(false);
      }
    })();
  }, [finished, sessionId]);

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
            <div>
              <label className="block text-sm text-zinc-400 mb-1">Topic</label>
              <select
                value={topic}
                onChange={(e) => setTopic(e.target.value)}
                className="w-full rounded-lg bg-zinc-800 px-3 py-2"
              >
                {TOPICS.map((t) => (
                  <option key={t.label} value={t.value}>
                    {t.label}
                  </option>
                ))}
              </select>
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
            {loading && (
              <p className="text-xs text-zinc-500">
                With a local model this can take up to a minute. Please wait.
              </p>
            )}
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

        {/* 3) Finished: report */}
        {finished && (
          <div className="space-y-5">
            <div className="rounded-xl border border-zinc-800 bg-zinc-900 p-6 space-y-4">
              <div className="text-xl font-semibold">Interview complete</div>

              {reportLoading && (
                <p className="text-zinc-400">
                  Preparing your report... with a local model this can take up to a minute.
                </p>
              )}

              {report && (
                <>
                  <div className="text-4xl font-bold">
                    {report.average_score}
                    <span className="text-xl text-zinc-400"> / 10 average</span>
                  </div>
                  {report.summary && (
                    <p className="whitespace-pre-line text-zinc-300">{report.summary}</p>
                  )}
                </>
              )}
            </div>

            {report &&
              report.records.map((r, i) => (
                <div
                  key={i}
                  className="rounded-xl border border-zinc-800 bg-zinc-900 p-5 space-y-2"
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="font-medium">
                      {i + 1}. {r.question}
                    </div>
                    <div className="shrink-0 rounded-md bg-zinc-800 px-2 py-1 text-sm">
                      {r.evaluation?.score ?? "?"}/10
                    </div>
                  </div>
                  <div className="text-sm text-zinc-400">
                    <span className="font-semibold text-zinc-300">Your answer: </span>
                    {r.answer}
                  </div>
                  {r.evaluation?.ideal_answer_tip && (
                    <div className="text-sm text-zinc-400">
                      <span className="font-semibold text-zinc-300">Tip: </span>
                      {r.evaluation.ideal_answer_tip}
                    </div>
                  )}
                </div>
              ))}

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

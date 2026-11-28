"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

const API = "http://127.0.0.1:8000";

type SessionRow = {
  session_id: string;
  role: string;
  topic: string;
  difficulty: string;
  questions: number;
  answered: number;
  average_score: number | null;
  created_at: string;
};

export default function HistoryPage() {
  const [rows, setRows] = useState<SessionRow[] | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    fetch(`${API}/history`)
      .then((res) => {
        if (!res.ok) throw new Error(`Server returned ${res.status}`);
        return res.json();
      })
      .then((data) => setRows(data.sessions))
      .catch(() => setError("Could not load history. Is the backend running?"));
  }, []);

  return (
    <main className="min-h-screen bg-zinc-950 text-zinc-100"><div className="mx-auto max-w-3xl px-6 py-10">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-bold">Interview history</h1>
        <Link href="/" className="text-sm text-indigo-400 hover:underline">
          Back to home
        </Link>
      </div>

      {error && <p className="text-red-400">{error}</p>}
      {!error && rows === null && <p className="text-gray-400">Loading...</p>}
      {rows && rows.length === 0 && (
        <p className="text-gray-400">No interviews saved yet. Finish one and it will show up here.</p>
      )}

      {rows && rows.length > 0 && (
        <div className="overflow-x-auto rounded-xl border border-white/10">
          <table className="w-full text-left text-sm">
            <thead className="bg-white/5 text-gray-400">
              <tr>
                <th className="px-4 py-3">Date</th>
                <th className="px-4 py-3">Role</th>
                <th className="px-4 py-3">Topic</th>
                <th className="px-4 py-3">Level</th>
                <th className="px-4 py-3">Answered</th>
                <th className="px-4 py-3">Avg score</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.session_id} className="border-t border-white/10">
                  <td className="px-4 py-3 whitespace-nowrap">
                    {new Date(r.created_at + "Z").toLocaleString()}
                  </td>
                  <td className="px-4 py-3">{r.role}</td>
                  <td className="px-4 py-3">{r.topic || "Any"}</td>
                  <td className="px-4 py-3 capitalize">{r.difficulty}</td>
                  <td className="px-4 py-3">
                    {r.answered}/{r.questions}
                  </td>
                  <td className="px-4 py-3 font-semibold">
                    {r.average_score ?? "-"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div></main>
  );
}

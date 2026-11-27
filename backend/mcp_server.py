"""
InterviewRAG MCP server
=======================
Exposes the InterviewRAG notes and interview engine as MCP tools, so any
MCP-compatible app (for example Claude Desktop) can use them.

Tools
  list_notes                   which note files are indexed
  search_notes                 find the passages of the notes that match a query
  generate_interview_questions interview questions based on the notes
  score_answer                 score an answer against the notes

Run
  uv run python mcp_server.py           # stdio (Claude Desktop, local clients)
  uv run python mcp_server.py --http    # streamable HTTP (MCP Inspector, tests)

Important for stdio: the protocol uses stdout, so nothing else may print
there. Any print() from the code we call is redirected to stderr.
"""

import contextlib
import random
import sys
from collections import Counter

from mcp.server.fastmcp import FastMCP

import rag_core

mcp = FastMCP("interviewrag")

_state: dict = {}


def _index():
    """Build the notes index on first use, so the server starts instantly."""
    if "items" not in _state:
        with contextlib.redirect_stdout(sys.stderr):
            items = rag_core.load_chunks_with_sources()
            if not items:
                raise RuntimeError("No readable notes found in backend/docs.")
            _state["items"] = items
            _state["vectors"] = rag_core.embed_in_batches([i["text"] for i in items])
    return _state["items"], _state["vectors"]


def _engine():
    """Create the interview engine on first use (needs the LLM settings)."""
    if "engine" not in _state:
        from ai_engine import AIInterviewEngine

        _state["engine"] = AIInterviewEngine()
    return _state["engine"]


@mcp.tool()
def list_notes() -> str:
    """List the note files that InterviewRAG has indexed, with chunk counts."""
    with contextlib.redirect_stdout(sys.stderr):
        items = rag_core.load_chunks_with_sources()
    if not items:
        return "No notes found."
    counts = Counter(i["source"].split(" (p.")[0] for i in items)
    lines = [f"- {name}: {n} chunks" for name, n in sorted(counts.items())]
    return f"{len(items)} chunks from {len(counts)} files:\n" + "\n".join(lines)


@mcp.tool()
def search_notes(query: str, top_k: int = 3) -> str:
    """Search the notes (AI/LLM/RAG/prompt engineering/vector DB study material).

    Returns the best matching passages with their source file and page.
    """
    if not query.strip():
        return "Please provide a search query."
    top_k = max(1, min(int(top_k), 8))
    try:
        items, vectors = _index()
        with contextlib.redirect_stdout(sys.stderr):
            hits = rag_core.retrieve_with_sources(query, items, vectors, k=top_k)
    except Exception as e:  # e.g. Ollama not running
        return f"Search failed: {e}. Is Ollama running?"
    lines = []
    for n, hit in enumerate(hits, start=1):
        lines.append(f"[{n}] {hit['source']} (similarity {hit['score']:.2f})\n{hit['text']}")
    return "\n\n".join(lines)


@mcp.tool()
def generate_interview_questions(
    topic: str, difficulty: str = "medium", count: int = 3
) -> str:
    """Generate interview questions about a topic, based on the notes.

    difficulty is easy, medium or hard; count is 1 to 7.
    """
    difficulty = difficulty.lower() if difficulty.lower() in {"easy", "medium", "hard"} else "medium"
    count = max(1, min(int(count), 7))
    try:
        items, vectors = _index()
        with contextlib.redirect_stdout(sys.stderr):
            pool = rag_core.retrieve_with_sources(topic or "AI", items, vectors, k=8)
            hits = random.sample(pool, k=min(5, len(pool)))
            notes = "\n".join(h["text"] for h in hits)
            questions = _engine().generate_questions(
                f"AI Engineer (focus on: {topic})", difficulty, count, None,
                notes_context=notes,
            )
    except Exception as e:
        return f"Could not generate questions: {e}"
    if not questions:
        return "The model did not return any questions. Please try again."
    return "\n".join(f"{n}. {q['question']}" for n, q in enumerate(questions, start=1))


@mcp.tool()
def score_answer(question: str, answer: str) -> str:
    """Score an interview answer from 0 to 10, checked against the notes."""
    if not question.strip() or not answer.strip():
        return "Please provide both a question and an answer."
    try:
        items, vectors = _index()
        with contextlib.redirect_stdout(sys.stderr):
            hits = rag_core.retrieve_with_sources(question, items, vectors, k=3)
            reference = "\n".join(h["text"] for h in hits)
            result = _engine().evaluate_answer(question, answer, reference=reference)
    except Exception as e:
        return f"Could not score the answer: {e}"
    if not result:
        return "The model did not return a score. Please try again."

    lines = [f"Score: {result.get('score', '?')}/10"]
    if result.get("strengths"):
        lines.append("Strengths: " + "; ".join(result["strengths"]))
    if result.get("improvements"):
        lines.append("To improve: " + "; ".join(result["improvements"]))
    if result.get("ideal_answer_tip"):
        lines.append("Tip: " + result["ideal_answer_tip"])
    lines.append("Checked against: " + ", ".join(h["source"] for h in hits))
    return "\n".join(lines)


def main() -> None:
    if "--http" in sys.argv:
        mcp.run(transport="streamable-http")
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()

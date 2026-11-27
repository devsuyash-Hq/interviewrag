# InterviewRAG

An AI mock-interview app that asks questions **from your own study notes** (PDFs), scores your answers, and shows the source chunks it used. Built with FastAPI, Next.js, a custom RAG pipeline, and an MCP server.

<!-- Add demo GIF here: ![demo](docs/demo.gif) -->

## Features
- Choose a topic (RAG, LLM, Prompt Engineering, Vector DB, Generative AI)
- Questions generated from your PDF notes, not from the model's memory
- Answer scoring with feedback and source chunks shown
- Final report page after the session
- MCP server so Claude Desktop can use the same notes
- Gemini with automatic fallback to local Ollama when Gemini returns 503

## Architecture
```
Next.js UI  ->  FastAPI  ->  RAG core (PDF chunks + embeddings + retrieval)
                    |
                    +->  LLM (Gemini, fallback: Ollama)
Claude Desktop  ->  MCP server  ->  same RAG core
```

## Project structure
```
interviewrag/
  backend/    FastAPI app, RAG core, MCP server, evaluation
    docs/     PDF study notes (knowledge base)
  frontend/   Next.js interview UI
```

## Setup

### 1. Backend
```bash
cd backend
cp .env.example .env      # add your GEMINI_API_KEY
uv sync
uv run uvicorn main:app --reload
```

### 2. Frontend
```bash
cd frontend
npm install
npm run dev
```
Open http://localhost:3000

### LLM provider
Set `LLM_PROVIDER` in `backend/.env`:
- `gemini`: use Gemini only
- `ollama`: use local Ollama (e.g. `qwen3:4b-instruct`)
- `auto`: Gemini first, Ollama if Gemini fails

## Retrieval evaluation
14 hand-written questions (`backend/eval_questions.json`), run with `python evaluate.py`.

| Chunk size / overlap | Hit@1 | Hit@3 | MRR |
|---|---|---|---|
| 500 / 100 | - | - | 0.96 |
| **900 / 150** | **1.00** | **1.00** | **1.00** |
| 1500 / 250 | 0.86 | - | - |

I chose 900/150 because it gave the best retrieval.

## MCP server
`backend/mcp_server.py` exposes 4 tools: `list_notes`, `search_notes`, `generate_interview_questions`, `score_answer`.
Add it to Claude Desktop's `claude_desktop_config.json`, then ask Claude to quiz you from your notes.

## Limitations
- Small knowledge base (5 PDFs, 44 chunks), eval set is only 14 questions
- Scores come from an LLM, so they can vary
- Local Ollama model is slower and less accurate than Gemini
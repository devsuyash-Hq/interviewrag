import os
import tempfile
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import rag_core
from ai_engine import AIInterviewEngine
from resume_parser import extract_text_from_pdf

state: dict = {}      # RAG index + engine, built once at startup
sessions: dict = {}   # session_id -> questions and answer records (in memory)


@asynccontextmanager
async def lifespan(app: FastAPI):
    state["items"] = rag_core.load_chunks_with_sources()
    state["vectors"] = rag_core.embed([i["text"] for i in state["items"]])
    state["engine"] = AIInterviewEngine()
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
    resume_summary: dict | None = None


class AnswerRequest(BaseModel):
    index: int
    answer: str


@app.post("/resume")
async def upload_resume(file: UploadFile = File(...)):
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(await file.read())
        path = tmp.name
    try:
        text = extract_text_from_pdf(path)
    finally:
        os.remove(path)
    return state["engine"].summarize_resume(text)


@app.post("/session/start")
def start_session(req: StartRequest):
    hits = rag_core.retrieve_with_sources(
        f"{req.role} interview", state["items"], state["vectors"], k=5
    )
    notes = "\n".join(h["text"] for h in hits)
    questions = state["engine"].generate_questions(
        req.role, req.difficulty, req.num_questions,
        req.resume_summary, notes_context=notes,
    )
    if not questions:
        raise HTTPException(502, "Could not generate questions")
    sid = uuid.uuid4().hex
    sessions[sid] = {"questions": questions, "records": []}
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
    evaluation = state["engine"].evaluate_answer(
        q["question"], body.answer, reference=reference
    )
    session["records"].append({
        "question": q["question"],
        "topic": q.get("topic", ""),
        "answer": body.answer,
        "evaluation": evaluation,
    })
    return {"evaluation": evaluation, "sources": hits}


@app.get("/session/{sid}/report")
def report(sid: str):
    session = sessions.get(sid)
    if not session or not session["records"]:
        raise HTTPException(404, "No answers yet")
    records = session["records"]
    scores = [r["evaluation"].get("score", 0) for r in records if r["evaluation"]]
    return {
        "average_score": round(sum(scores) / len(scores), 1) if scores else 0,
        "records": records,
        "summary": state["engine"].generate_final_report(records),
    }
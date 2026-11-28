import json
import logging
import os
from datetime import datetime, timezone

from sqlalchemy import (
    JSON, DateTime, ForeignKey, Integer, String, Text, create_engine, func, select,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

log = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not set. Add it to backend/.env")

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def _now() -> datetime:
    # naive UTC time (utcnow() is deprecated in newer Python)
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


class InterviewSession(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)  # same uuid hex as the API
    role: Mapped[str] = mapped_column(String(200))
    topic: Mapped[str] = mapped_column(String(100), default="")
    difficulty: Mapped[str] = mapped_column(String(20))
    num_questions: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    answers: Mapped[list["Answer"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )


class Answer(Base):
    __tablename__ = "answers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id"))
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str] = mapped_column(Text)
    score: Mapped[float | None] = mapped_column(nullable=True)
    evaluation: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    sources: Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    session: Mapped["InterviewSession"] = relationship(back_populates="answers")


def init_db() -> None:
    """Create tables if they don't exist."""
    Base.metadata.create_all(engine)


def _json_safe(value):
    # sources may contain numpy floats; convert so the JSON column accepts them
    return json.loads(json.dumps(value, default=float))


def save_session(sid, role, topic, difficulty, num_questions) -> None:
    try:
        with SessionLocal() as db:
            db.add(InterviewSession(
                id=sid, role=role, topic=topic,
                difficulty=difficulty, num_questions=num_questions,
            ))
            db.commit()
    except Exception:
        log.exception("DB: could not save session")


def save_answer(sid, question, answer, evaluation, sources) -> None:
    try:
        score = evaluation.get("score") if isinstance(evaluation, dict) else None
        with SessionLocal() as db:
            db.add(Answer(
                session_id=sid, question=question, answer=answer,
                score=score if isinstance(score, (int, float)) else None,
                evaluation=_json_safe(evaluation), sources=_json_safe(sources),
            ))
            db.commit()
    except Exception:
        log.exception("DB: could not save answer")


def list_sessions(limit: int = 20) -> list[dict]:
    """Latest interviews with answer count and average score."""
    try:
        with SessionLocal() as db:
            stmt = (
                select(
                    InterviewSession,
                    func.count(Answer.id),
                    func.avg(Answer.score),
                )
                .outerjoin(Answer, Answer.session_id == InterviewSession.id)
                .group_by(InterviewSession.id)
                .order_by(InterviewSession.created_at.desc())
                .limit(limit)
            )
            rows = db.execute(stmt).all()
        return [
            {
                "session_id": s.id,
                "role": s.role,
                "topic": s.topic,
                "difficulty": s.difficulty,
                "questions": s.num_questions,
                "answered": n,
                "average_score": round(float(avg), 1) if avg is not None else None,
                "created_at": s.created_at.isoformat(),
            }
            for s, n, avg in rows
        ]
    except Exception:
        log.exception("DB: could not list sessions")
        return []
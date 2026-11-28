import os
import tempfile

import pytest

# CI sets TEST_DATABASE_URL to a real Postgres; locally we fall back to a throwaway SQLite file.
# (A file, not :memory:, because FastAPI's TestClient runs endpoints in another thread.)
# This must be set BEFORE importing db or main, because db.py reads it at import time.
_tmp_dir = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = os.getenv(
    "TEST_DATABASE_URL", f"sqlite:///{_tmp_dir}/test.db"
)

from fastapi.testclient import TestClient  # noqa: E402

import db  # noqa: E402
from main import app  # noqa: E402

# No `with` block on purpose: that skips the startup (PDF indexing, Gemini calls).
client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_db():
    """Start every test with empty tables, so tests do not depend on each other."""
    db.Base.metadata.drop_all(db.engine)
    db.Base.metadata.create_all(db.engine)
    yield


def test_topics_returns_five_topics():
    res = client.get("/topics")
    assert res.status_code == 200
    assert len(res.json()["topics"]) == 5


def test_history_is_empty_without_data():
    res = client.get("/history")
    assert res.status_code == 200
    assert res.json() == {"sessions": []}


def test_saved_session_shows_in_history():
    db.save_session("abc123", "Tester", "RAG", "easy", 3)
    db.save_answer(
        "abc123",
        "What is RAG?",
        "Retrieval plus generation",
        {"score": 8},
        [{"text": "x", "source": "a.pdf", "score": 0.9}],
    )

    sessions = client.get("/history").json()["sessions"]
    row = next(s for s in sessions if s["session_id"] == "abc123")
    assert row["answered"] == 1
    assert row["average_score"] == 8.0


def test_answer_for_unknown_session_returns_404():
    res = client.post(
        "/session/does-not-exist/answer",
        json={"index": 0, "answer": "hello"},
    )
    assert res.status_code == 404
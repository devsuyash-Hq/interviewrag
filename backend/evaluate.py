"""
Mini retrieval evaluation for InterviewRAG
==========================================
Question: when a user asks something, does the retriever bring back the right
part of the notes?

How it works
  1. eval_questions.json holds test questions and the file(s) that should be
     found for each one (the "ground truth").
  2. For several chunk-size settings, the notes are re-chunked, embedded with
     Ollama, and each question is searched.
  3. A search counts as a hit if one of the top-k chunks comes from an
     expected file AND contains one of the question's keywords (so the chunk
     really holds the answer, not just a page from the same file).

Metrics
  Hit@k : share of questions with a correct chunk in the top k results.
  MRR   : mean reciprocal rank = average of 1/rank of the first correct chunk
          (1.0 = always first, 0 = never found).

Run (Ollama must be running; Gemini is NOT used here):
  uv run python evaluate.py
"""

import json
from pathlib import Path

import numpy as np
import pdfplumber

import rag_core

QUESTIONS_FILE = Path(__file__).parent / "eval_questions.json"
CONFIGS = [(500, 100), (900, 150), (1500, 250)]   # (chunk size, overlap)
K_VALUES = (1, 3, 5)


def read_pages() -> list[tuple[str, str, str]]:
    """Return (file name, source label, text) for every page of every note."""
    pages = []
    for path in sorted(rag_core.DOCS_DIR.iterdir()):
        suffix = path.suffix.lower()
        if suffix == ".pdf":
            with pdfplumber.open(path) as pdf:
                for number, page in enumerate(pdf.pages, start=1):
                    pages.append((path.name, f"{path.name} (p.{number})",
                                  page.extract_text() or ""))
        elif suffix in {".md", ".txt"}:
            pages.append((path.name, path.name, path.read_text(encoding="utf-8")))
    return pages


def build_items(pages, size: int, overlap: int) -> list[dict]:
    items = []
    for file_name, label, text in pages:
        for chunk in rag_core._split_text(text, size, overlap):
            items.append({"text": chunk, "source": label, "file": file_name})
    return items


def is_correct(item: dict, expected: list[str], keywords: list[str]) -> bool:
    """Right file, and (if keywords are given) the chunk contains one of them."""
    if not any(item["file"].startswith(prefix) for prefix in expected):
        return False
    if not keywords:
        return True
    text = item["text"].lower()
    return any(word.lower() in text for word in keywords)


def first_correct_rank(retrieved: list[dict], expected: list[str], keywords: list[str]):
    """1-based rank of the first correct chunk, or None."""
    for position, item in enumerate(retrieved, start=1):
        if is_correct(item, expected, keywords):
            return position
    return None


def evaluate(items, vectors, questions):
    k_max = max(K_VALUES)
    ranks = []
    misses = []
    for q in questions:
        retrieved = rag_core.retrieve_with_sources(q["question"], items, vectors, k=k_max)
        rank = first_correct_rank(
            retrieved, q["expected_files"], q.get("keywords", [])
        )
        ranks.append(rank)
        if rank is None or rank > 3:
            top = retrieved[0]["source"] if retrieved else "-"
            misses.append((q["question"], rank, top))

    total = len(questions)
    hit = {k: sum(1 for r in ranks if r is not None and r <= k) / total for k in K_VALUES}
    mrr = sum(1 / r for r in ranks if r) / total
    return hit, mrr, misses


def main() -> None:
    questions = json.loads(QUESTIONS_FILE.read_text(encoding="utf-8"))
    pages = read_pages()
    print(f"Notes: {len(pages)} pages/files | Questions: {len(questions)}\n")

    rows = []
    all_misses = {}
    for size, overlap in CONFIGS:
        items = build_items(pages, size, overlap)
        vectors = rag_core.embed_in_batches([i["text"] for i in items])
        hit, mrr, misses = evaluate(items, vectors, questions)
        rows.append((size, overlap, len(items), hit, mrr))
        all_misses[(size, overlap)] = misses

    header = f"{'chunk/overlap':<14}{'chunks':>7}" + "".join(
        f"{'Hit@' + str(k):>8}" for k in K_VALUES) + f"{'MRR':>8}"
    print(header)
    print("-" * len(header))
    for size, overlap, n_chunks, hit, mrr in rows:
        line = f"{str(size) + '/' + str(overlap):<14}{n_chunks:>7}"
        line += "".join(f"{hit[k]:>8.2f}" for k in K_VALUES) + f"{mrr:>8.2f}"
        print(line)

    best = max(rows, key=lambda r: (r[3][3], r[4]))
    print(f"\nBest setting by Hit@3 then MRR: chunk size {best[0]}, overlap {best[1]}")

    print("\nQuestions where a correct chunk was not in the top 3:")
    for (size, overlap), misses in all_misses.items():
        print(f"\n  [{size}/{overlap}]")
        if not misses:
            print("    none")
        for question, rank, top in misses:
            found = f"rank {rank}" if rank else "not in top 5"
            print(f"    - {question}\n        {found}; top result was {top}")


if __name__ == "__main__":
    main()

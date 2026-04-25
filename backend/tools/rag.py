"""RAG over the legal corpus.

CLASS CONCEPT — Retrieval-Augmented Generation.
A small Chroma collection seeded from `backend/corpus/*.md` (NYC CCA,
CPLR, venue rules, filing procedure, sample complaint). The agent uses
this to cite statutes when paraphrasing rules.

We use Chroma's default sentence-transformers embedding so we have NO
external embedding API dependency at demo time.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import List

import chromadb
from agents import function_tool
from pydantic import BaseModel

CORPUS_DIR = Path(__file__).resolve().parent.parent / "corpus"
DB_DIR = Path(__file__).resolve().parent.parent / "data" / "chroma"
COLLECTION = "legal_kb"


class RagHit(BaseModel):
    source: str
    text: str
    score: float


class RagResults(BaseModel):
    query: str
    hits: List[RagHit]


def _client() -> chromadb.api.ClientAPI:
    DB_DIR.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=str(DB_DIR))


def ingest() -> int:
    """Ingest the corpus directory into Chroma. Idempotent — drops & rebuilds."""
    client = _client()
    try:
        client.delete_collection(COLLECTION)
    except Exception:
        pass
    coll = client.create_collection(COLLECTION)

    docs, ids, metas = [], [], []
    for path in sorted(CORPUS_DIR.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        # Each doc is small; one chunk per file is fine for this demo.
        docs.append(text)
        ids.append(path.stem)
        metas.append({"source": path.name})
    coll.add(documents=docs, ids=ids, metadatas=metas)
    return len(docs)


def _get_collection():
    client = _client()
    try:
        return client.get_collection(COLLECTION)
    except Exception:
        ingest()
        return client.get_collection(COLLECTION)


@function_tool
def search_legal_kb(query: str, k: int = 3) -> RagResults:
    """Search the small-claims legal knowledge base.

    Returns the top-k most relevant passages with their source filename.
    Cite the `source` field in any answer that paraphrases a rule.

    Args:
        query: Natural-language legal question.
        k: How many passages to return (default 3, max 5).
    """
    coll = _get_collection()
    res = coll.query(query_texts=[query], n_results=min(max(k, 1), 5))
    hits: List[RagHit] = []
    for doc, meta, dist in zip(
        res["documents"][0], res["metadatas"][0], res["distances"][0]
    ):
        hits.append(RagHit(source=meta.get("source", "?"), text=doc, score=float(dist)))
    return RagResults(query=query, hits=hits)


if __name__ == "__main__":
    n = ingest()
    print(f"Ingested {n} documents into collection {COLLECTION!r} at {DB_DIR}")

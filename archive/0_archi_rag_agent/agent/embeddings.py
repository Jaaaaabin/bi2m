"""OpenAI embeddings index over the Neufert sqlite."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Iterator

import numpy as np
from openai import OpenAI

from . import db

EMBED_MODEL = "text-embedding-3-small"
EMBED_DIM = 1536
DEFAULT_INDEX = Path(__file__).resolve().parent.parent / "embeddings.sqlite"

INDEX_SCHEMA = """
CREATE TABLE IF NOT EXISTS embeddings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_table TEXT NOT NULL,
    source_row_id INTEGER NOT NULL,
    page TEXT NOT NULL,
    content TEXT NOT NULL,
    embedding BLOB NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_emb_page ON embeddings(page);
"""

# In-process cache so semantic_search doesn't reload the index every call.
_cache: dict[str, Any] = {"vectors": None, "rows": None, "path": None}


def _iter_chunks(src_db: str | Path) -> Iterator[tuple[str, int, str, str]]:
    """Yield (source_table, source_row_id, page, content) for every embeddable row."""
    with db.connect(src_db) as conn:
        for r in conn.execute(
            "SELECT id, page, response_text FROM text WHERE response_text IS NOT NULL"
        ):
            content = db._unwrap(r["response_text"], "text")
            if content.strip():
                yield "text", r["id"], r["page"], content

        for r in conn.execute(
            "SELECT id, page, response_text FROM caption WHERE response_text IS NOT NULL"
        ):
            content = db._unwrap(r["response_text"], "caption")
            if content.strip():
                yield "caption", r["id"], r["page"], content

        for r in conn.execute(
            "SELECT id, page, response_text FROM 'table' WHERE response_text IS NOT NULL"
        ):
            rows = db._parse_table(r["response_text"])
            if rows:
                content = "\n".join(" | ".join(str(c) for c in row) for row in rows)
                yield "table", r["id"], r["page"], content


def build_index(
    src_db: str | Path = db.DEFAULT_DB,
    index_db: str | Path = DEFAULT_INDEX,
    batch_size: int = 100,
    client: OpenAI | None = None,
    verbose: bool = True,
) -> int:
    """(Re)build the embedding index. Drops existing rows. Returns chunk count."""
    if client is None:
        from .agent import load_client
        client = load_client()

    chunks = list(_iter_chunks(src_db))
    if verbose:
        print(f"[index] {len(chunks)} chunks → {EMBED_MODEL}")

    conn = sqlite3.connect(str(index_db))
    conn.executescript(INDEX_SCHEMA)
    conn.execute("DELETE FROM embeddings")
    conn.commit()

    for i in range(0, len(chunks), batch_size):
        batch = chunks[i : i + batch_size]
        texts = [c[3] for c in batch]
        resp = client.embeddings.create(model=EMBED_MODEL, input=texts)
        for chunk, emb in zip(batch, resp.data):
            vec = np.asarray(emb.embedding, dtype=np.float32).tobytes()
            conn.execute(
                "INSERT INTO embeddings "
                "(source_table, source_row_id, page, content, embedding) "
                "VALUES (?, ?, ?, ?, ?)",
                (chunk[0], chunk[1], chunk[2], chunk[3], vec),
            )
        conn.commit()
        if verbose:
            print(f"[index] {min(i + batch_size, len(chunks))}/{len(chunks)}")

    conn.close()
    # Invalidate cache so a subsequent semantic_search reloads.
    _cache.update({"vectors": None, "rows": None, "path": None})
    return len(chunks)


def _load_index(index_db: str | Path) -> tuple[np.ndarray, list[dict[str, Any]]]:
    index_db = str(index_db)
    if _cache["vectors"] is not None and _cache["path"] == index_db:
        return _cache["vectors"], _cache["rows"]

    if not Path(index_db).exists():
        raise RuntimeError(
            f"embedding index not found at {index_db} — run "
            f"`python -m agent.build_index` first"
        )
    conn = sqlite3.connect(index_db)
    conn.row_factory = sqlite3.Row
    has_table = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='embeddings'"
    ).fetchone()
    if not has_table:
        conn.close()
        raise RuntimeError(
            f"embedding index at {index_db} has no `embeddings` table — run "
            f"`python -m agent.build_index` first"
        )
    rows = conn.execute(
        "SELECT id, source_table, source_row_id, page, content, embedding FROM embeddings"
    ).fetchall()
    conn.close()

    if not rows:
        raise RuntimeError(
            f"embedding index at {index_db} is empty — run `python -m agent.build_index` first"
        )

    vecs = np.stack(
        [np.frombuffer(r["embedding"], dtype=np.float32) for r in rows]
    )
    norms = np.linalg.norm(vecs, axis=1, keepdims=True)
    vecs = vecs / np.clip(norms, 1e-9, None)

    rows_dicts = [
        {
            "id": r["id"],
            "source_table": r["source_table"],
            "source_row_id": r["source_row_id"],
            "page": r["page"],
            "content": r["content"],
        }
        for r in rows
    ]

    _cache.update({"vectors": vecs, "rows": rows_dicts, "path": index_db})
    return vecs, rows_dicts


def semantic_search(
    query: str,
    k: int = 10,
    index_db: str | Path = DEFAULT_INDEX,
    client: OpenAI | None = None,
) -> list[dict[str, Any]]:
    """Return top-k most semantically similar chunks for `query`."""
    if client is None:
        from .agent import load_client
        client = load_client()

    vecs, rows = _load_index(index_db)
    qe = client.embeddings.create(model=EMBED_MODEL, input=[query]).data[0].embedding
    q = np.asarray(qe, dtype=np.float32)
    q = q / max(float(np.linalg.norm(q)), 1e-9)

    scores = vecs @ q
    top_idx = np.argsort(-scores)[:k]
    out: list[dict[str, Any]] = []
    for i in top_idx:
        r = rows[int(i)]
        out.append(
            {
                "page": r["page"],
                "source": r["source_table"],
                "score": round(float(scores[int(i)]), 4),
                "content": r["content"][:400],
            }
        )
    return out

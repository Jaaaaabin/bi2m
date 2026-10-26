"""SQLite query helpers for Neufert vlm_pages.sqlite."""

from __future__ import annotations

import json
import re
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

DEFAULT_DB = Path(__file__).resolve().parent.parent / "vlm_pages.sqlite"


@contextmanager
def connect(db_path: str | Path = DEFAULT_DB) -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def _unwrap(response_text: str | None, key: str | None = None) -> str:
    """response_text is usually JSON like {"text": "..."} or {"caption": "..."}.
    Strip ```json fences and unwrap the single value."""
    if not response_text:
        return ""
    raw = response_text.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    obj = None
    try:
        obj = json.loads(raw, strict=False)
    except Exception:
        # Many VLM outputs contain raw newlines inside JSON string values; fall back
        # to a tolerant single-key regex.
        m = re.match(r'^\{\s*"(\w+)"\s*:\s*"(.*)"\s*\}\s*$', raw, re.DOTALL)
        if m:
            val = m.group(2)
            val = val.replace('\\"', '"').replace("\\n", "\n").replace("\\t", "\t")
            return val
        return response_text
    if isinstance(obj, dict):
        if key and key in obj:
            return str(obj[key])
        if len(obj) == 1:
            return str(next(iter(obj.values())))
        return json.dumps(obj, ensure_ascii=False)
    return str(obj)


def _parse_table(response_text: str | None) -> list[list[str]]:
    if not response_text:
        return []
    raw = response_text.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    try:
        obj = json.loads(raw)
    except Exception:
        return []
    if isinstance(obj, dict) and "rows" in obj:
        return obj["rows"]
    return []


# ---------- public query functions ----------

def list_subheadings(db_path: str | Path = DEFAULT_DB) -> list[str]:
    """Distinct top-level topic labels (OFFICE BUILDINGS, ROOMS, HOTELS, ...)."""
    with connect(db_path) as conn:
        rows = conn.execute(
            "SELECT DISTINCT response_text FROM subheading WHERE response_text IS NOT NULL"
        ).fetchall()
    seen: set[str] = set()
    out: list[str] = []
    for r in rows:
        v = _unwrap(r[0], "subheading").strip()
        if v and v not in seen:
            seen.add(v)
            out.append(v)
    return sorted(out)


def find_pages_by_subheading(
    subheading: str, db_path: str | Path = DEFAULT_DB
) -> list[str]:
    """Pages whose subheading matches (case-insensitive substring)."""
    pattern = f"%{subheading}%"
    with connect(db_path) as conn:
        rows = conn.execute(
            "SELECT DISTINCT page FROM subheading "
            "WHERE LOWER(response_text) LIKE LOWER(?) ORDER BY page",
            (pattern,),
        ).fetchall()
    return [r[0] for r in rows]


def keyword_search(
    keyword: str,
    fields: list[str] | None = None,
    limit: int = 40,
    db_path: str | Path = DEFAULT_DB,
) -> list[dict[str, Any]]:
    """Substring search across selected tables. Returns hits with page + snippet."""
    fields = fields or ["text", "caption", "caption_group", "subheading"]
    valid = {"text", "caption", "caption_group", "subheading", "chapter_banner"}
    fields = [f for f in fields if f in valid]
    pattern = f"%{keyword}%"
    out: list[dict[str, Any]] = []
    with connect(db_path) as conn:
        for tbl in fields:
            rows = conn.execute(
                f"SELECT page, response_text FROM {tbl} "
                f"WHERE LOWER(response_text) LIKE LOWER(?) ORDER BY page LIMIT ?",
                (pattern, limit),
            ).fetchall()
            for r in rows:
                snippet = _unwrap(r[1])
                out.append(
                    {
                        "page": r["page"],
                        "table": tbl,
                        "snippet": snippet[:400],
                    }
                )
    return out[:limit]


def get_page(page: str, db_path: str | Path = DEFAULT_DB) -> dict[str, Any]:
    """Return everything we have on one page: subheading(s), text blocks, captions, tables."""
    with connect(db_path) as conn:
        sub = conn.execute(
            "SELECT response_text FROM subheading WHERE page = ? ORDER BY item_index",
            (page,),
        ).fetchall()
        chap = conn.execute(
            "SELECT response_text FROM chapter_banner WHERE page = ? ORDER BY item_index",
            (page,),
        ).fetchall()
        text = conn.execute(
            "SELECT item_index, response_text FROM text WHERE page = ? ORDER BY item_index",
            (page,),
        ).fetchall()
        caps = conn.execute(
            "SELECT item_index, response_text FROM caption WHERE page = ? ORDER BY item_index",
            (page,),
        ).fetchall()
        tabs = conn.execute(
            "SELECT item_index, response_text FROM 'table' WHERE page = ? ORDER BY item_index",
            (page,),
        ).fetchall()

    return {
        "page": page,
        "chapter": [_unwrap(r[0], "chapter") for r in chap],
        "subheading": [_unwrap(r[0], "subheading") for r in sub],
        "text_blocks": [
            {"item_index": r[0], "text": _unwrap(r[1], "text")} for r in text
        ],
        "captions": [
            {"item_index": r[0], "text": _unwrap(r[1], "caption")} for r in caps
        ],
        "tables": [
            {"item_index": r[0], "rows": _parse_table(r[1])} for r in tabs
        ],
    }


def get_pages_bulk(
    pages: list[str], db_path: str | Path = DEFAULT_DB
) -> list[dict[str, Any]]:
    return [get_page(p, db_path) for p in pages]

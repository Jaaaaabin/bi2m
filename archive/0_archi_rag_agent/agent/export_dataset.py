"""Export a figure-centric dataset from vlm_pages.sqlite.

One record per illustration: the PNG on disk, its caption, the figure numbers
printed on it, and the body-text paragraphs that reference those numbers.

    python -m agent.export_dataset
    python -m agent.export_dataset --out ../1_dataset --no-images

Layout produced:

    1_dataset/
      images/*.png     one crop per illustration
      dataset.jsonl    one line per illustration
      pages.jsonl      one line per page (full body text + chapter context)
      stats.json
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
from collections import defaultdict
from pathlib import Path
from typing import Any

from .db import DEFAULT_DB, _unwrap

ROOT = Path(__file__).resolve().parents[2]
SRC_DB = DEFAULT_DB if DEFAULT_DB.exists() else ROOT / "vlm_pages.sqlite"

ELEMENT_TABLES = ["text", "image", "table", "caption", "circle_large", "circle_small"]


def _rows_by_crop(conn: sqlite3.Connection, table: str) -> dict[str, sqlite3.Row]:
    """crop_path is globally unique per table; the `index` in linked_*_json is not
    item_index, so crop_path is the only reliable join key."""
    return {
        r["crop_path"]: r
        for r in conn.execute(f'SELECT * FROM "{table}"')
        if r["crop_path"]
    }


def _links(raw: str | None) -> list[dict[str, Any]]:
    try:
        v = json.loads(raw or "[]")
        return v if isinstance(v, list) else []
    except Exception:
        return []


def _number(row: sqlite3.Row | None) -> str | None:
    """Figure number off a circle_large / circle_small row."""
    if row is None:
        return None
    try:
        n = json.loads(row["parsed_json"] or "{}").get("number")
    except Exception:
        n = None
    return str(n).strip() if n not in (None, "") else None


def _table_rows(row: sqlite3.Row | None) -> list[list[str]]:
    """parsed_json is null for ~2/3 of tables, but response_text still holds the
    same JSON behind a ```json fence -- fall back to that."""
    if row is None:
        return []
    for raw in (row["parsed_json"], row["response_text"]):
        if not raw:
            continue
        txt = re.sub(r"^```(?:json)?\s*", "", raw.strip())
        txt = re.sub(r"\s*```$", "", txt)
        try:
            rows = json.loads(txt, strict=False).get("rows")
        except Exception:
            continue
        if rows:
            return rows
    return []


def _bbox(r: sqlite3.Row) -> list[float] | None:
    vals = [r["bbox_x0"], r["bbox_y0"], r["bbox_x1"], r["bbox_y1"]]
    return [round(float(v), 2) for v in vals] if all(v is not None for v in vals) else None


def build(
    src: Path,
    out: Path,
    write_images: bool = True,
    drop_front_matter: bool = True,
) -> dict[str, Any]:
    if not src.exists():
        raise SystemExit(f"source db not found: {src}")
    conn = sqlite3.connect(f"file:{src}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row

    fig_dir = out / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)

    by_crop = {t: _rows_by_crop(conn, t) for t in ELEMENT_TABLES}
    images = by_crop["image"]

    # Cover, copyright, contents, preface and back cover carry no chapter banner.
    # The banner range is the book proper; everything outside it is front/back matter.
    skip_pages: set[str] = set()
    if drop_front_matter:
        lo, hi = conn.execute(
            "SELECT MIN(p.page_index), MAX(p.page_index) FROM chapter_banner b "
            "JOIN pages p ON p.page = b.page"
        ).fetchone()
        skip_pages = {
            r["page"]
            for r in conn.execute(
                "SELECT page FROM pages WHERE page_index < ? OR page_index > ?", (lo, hi)
            )
        }
        images = {cp: r for cp, r in images.items() if r["page"] not in skip_pages}

    # ---- page-level context -------------------------------------------------
    page_meta: dict[str, dict[str, Any]] = {}
    for r in conn.execute("SELECT page, page_index FROM pages"):
        page_meta[r["page"]] = {
            "page": r["page"],
            "page_index": r["page_index"],
            "book_page": None,
            "chapter": None,
            "subheadings": [],
            "topics": [],
            "norms": [],
            "body_text": [],
        }

    def _first(table: str, key: str) -> None:
        for r in conn.execute(f'SELECT page, response_text FROM "{table}"'):
            m = page_meta.get(r["page"])
            if m is None or m[key] is not None:
                continue
            v = _unwrap(r["response_text"], key if table != "page_number" else "page_number")
            if v.strip():
                m[key] = v.strip()

    _first("chapter_banner", "chapter")
    _first("page_number", "book_page")

    for r in conn.execute("SELECT page, response_text FROM subheading"):
        m = page_meta.get(r["page"])
        v = _unwrap(r["response_text"], "subheading").strip()
        if m and v and v not in m["subheadings"]:
            m["subheadings"].append(v)

    for r in conn.execute("SELECT page, response_text FROM subheading_group"):
        m = page_meta.get(r["page"])
        if not m:
            continue
        try:
            obj = json.loads((r["response_text"] or "").strip().strip("`").removeprefix("json"))
        except Exception:
            continue
        for k in ("topics", "norms"):
            for v in obj.get(k) or []:
                if v and v not in m[k]:
                    m[k].append(v)

    # ---- body text, with the figure numbers each paragraph cites ------------
    # page -> figure number -> [text ids]; and the text records themselves
    cites: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    for r in conn.execute("SELECT * FROM text"):
        m = page_meta.get(r["page"])
        if m is None:
            continue
        content = _unwrap(r["response_text"], "text").strip()
        if not content:
            continue
        tid = Path(r["crop_path"] or f'{r["page"]}_text_{r["id"]}').stem
        nums: list[str] = []
        for lk in _links(r["linked_circle_small_json"]):
            n = (lk.get("parsed") or {}).get("number") if isinstance(lk.get("parsed"), dict) else None
            if n not in (None, "") and str(n).strip() not in nums:
                nums.append(str(n).strip())
        m["body_text"].append({"id": tid, "text": content, "cites_figures": nums, "bbox": _bbox(r)})
        for n in nums:
            cites[r["page"]][n].append(tid)

    text_by_id = {
        t["id"]: t for m in page_meta.values() for t in m["body_text"]
    }

    # ---- caption_group: image -> captions / figure numbers / tables ---------
    group_of: dict[str, dict[str, Any]] = {}
    for g in conn.execute("SELECT * FROM caption_group"):
        page = g["page"]
        caps = []
        for lk in _links(g["linked_captions_json"]):
            row = by_crop["caption"].get(lk.get("crop_path"))
            txt = _unwrap(row["response_text"], "caption").strip() if row is not None else ""
            if not txt and isinstance(lk.get("parsed"), dict):
                txt = str(lk["parsed"].get("caption") or "").strip()
            if txt:
                caps.append({"text": txt, "bbox": _bbox(row) if row is not None else lk.get("bbox_px")})

        nums = []
        for lk in _links(g["linked_circle_large_json"]):
            n = _number(by_crop["circle_large"].get(lk.get("crop_path")))
            if n is None and isinstance(lk.get("parsed"), dict):
                n = str(lk["parsed"].get("number") or "").strip() or None
            if n and n not in nums:
                nums.append(n)

        tbls = []
        for lk in _links(g["linked_tables_json"]):
            row = by_crop["table"].get(lk.get("crop_path"))
            rows = _table_rows(row)
            if rows:
                tbls.append({"rows": rows, "bbox": _bbox(row) if row is not None else None})

        payload = {
            "group_id": g["id"],
            "page": page,
            "captions": caps,
            "figure_numbers": nums,
            "tables": tbls,
        }
        for lk in _links(g["linked_images_json"]):
            cp = lk.get("crop_path")
            if cp in images:
                group_of[cp] = payload

    # ---- emit ---------------------------------------------------------------
    out.mkdir(parents=True, exist_ok=True)
    stats = defaultdict(int)

    with (out / "index.jsonl").open("w", encoding="utf-8") as fh:
        for cp, r in sorted(images.items(), key=lambda kv: kv[1]["crop_path"]):
            iid = Path(cp).stem
            page = r["page"]
            m = page_meta.get(page, {})
            g = group_of.get(cp)

            folder = fig_dir / iid
            folder.mkdir(exist_ok=True)
            if write_images and r["crop_bytes"]:
                (folder / "image.png").write_bytes(r["crop_bytes"])

            caps = g["captions"] if g else []
            nums = g["figure_numbers"] if g else []

            related = []
            for n in nums:
                for tid in cites.get(page, {}).get(n, []):
                    t = text_by_id.get(tid)
                    if t and not any(x["id"] == tid for x in related):
                        related.append({"id": tid, "text": t["text"], "via_figure_number": n})

            rec = {
                "id": iid,
                "image": "image.png",
                "page": page,
                "page_index": m.get("page_index"),
                "book_page": m.get("book_page"),
                "bbox": _bbox(r),
                "caption": " ".join(c["text"] for c in caps) or None,
                "captions": caps,
                "figure_numbers": nums,
                "related_text": related,
                "tables": g["tables"] if g else [],
                "chapter": m.get("chapter"),
                "subheadings": m.get("subheadings", []),
                "topics": m.get("topics", []),
                "norms": m.get("norms", []),
                "group_id": g["group_id"] if g else None,
                "flags": {
                    "orphan": g is None,
                    "has_caption": bool(caps),
                    "has_figure_number": bool(nums),
                    "has_related_text": bool(related),
                },
            }
            (folder / "data.json").write_text(
                json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            fh.write(json.dumps({**rec, "image": f"figures/{iid}/image.png"},
                                ensure_ascii=False) + "\n")

            stats["images"] += 1
            for k, v in rec["flags"].items():
                stats[k] += int(v)
            stats["related_text_paragraphs"] += len(related)
            stats["linked_tables"] += len(rec["tables"])

    with (out / "pages.jsonl").open("w", encoding="utf-8") as fh:
        for page in sorted(p for p in page_meta if p not in skip_pages):
            fh.write(json.dumps(page_meta[page], ensure_ascii=False) + "\n")

    summary = {
        "source": str(src),
        "images": stats["images"],
        "with_caption": stats["has_caption"],
        "with_figure_number": stats["has_figure_number"],
        "with_related_text": stats["has_related_text"],
        "orphan_no_group": stats["orphan"],
        "related_text_paragraphs_total": stats["related_text_paragraphs"],
        "linked_tables_total": stats["linked_tables"],
        "pages": len(page_meta) - len(skip_pages),
        "dropped_front_back_matter_pages": sorted(skip_pages),
        "body_text_paragraphs": sum(
            len(m["body_text"]) for k, m in page_meta.items() if k not in skip_pages
        ),
    }
    (out / "stats.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    conn.close()
    return summary


def main() -> None:
    p = argparse.ArgumentParser(description="Export figure dataset from vlm_pages.sqlite.")
    p.add_argument("--src", type=Path, default=SRC_DB)
    p.add_argument("--out", type=Path, default=ROOT / "1_dataset")
    p.add_argument("--no-images", action="store_true", help="only rewrite the jsonl files")
    p.add_argument(
        "--keep-front-matter",
        action="store_true",
        help="keep cover / contents / preface / back cover pages (dropped by default)",
    )
    args = p.parse_args()

    s = build(
        args.src,
        args.out,
        write_images=not args.no_images,
        drop_front_matter=not args.keep_front_matter,
    )
    print(json.dumps(s, ensure_ascii=False, indent=2))
    print(f"\n[done] -> {args.out}")


if __name__ == "__main__":
    main()

"""Extract page renders, figure crops, caption crops to disk."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from . import db

VALID_KINDS = {"page", "caption", "image", "caption_group"}


def list_figures_on_page(page: str) -> dict[str, Any]:
    """Return a lightweight view of every extractable figure on a page.

    Useful for the agent to know which item_index values exist before calling
    save_figures.
    """
    with db.connect() as conn:
        page_row = conn.execute(
            "SELECT 1 FROM pages WHERE page = ?", (page,)
        ).fetchone()
        if not page_row:
            return {"page": page, "exists": False}

        captions = conn.execute(
            "SELECT item_index, response_text FROM caption WHERE page = ? "
            "ORDER BY item_index",
            (page,),
        ).fetchall()
        images = conn.execute(
            "SELECT item_index FROM image WHERE page = ? ORDER BY item_index",
            (page,),
        ).fetchall()
        cgs = conn.execute(
            "SELECT item_index FROM caption_group WHERE page = ? ORDER BY item_index",
            (page,),
        ).fetchall()

    return {
        "page": page,
        "exists": True,
        "captions": [
            {"item_index": r["item_index"], "text": db._unwrap(r["response_text"], "caption")}
            for r in captions
        ],
        "images": [{"item_index": r["item_index"]} for r in images],
        "caption_groups": [{"item_index": r["item_index"]} for r in cgs],
    }


def save_figures(
    figures: list[dict[str, Any]],
    output_dir: str | Path,
) -> list[dict[str, Any]]:
    """Write requested figures to `output_dir`. Returns per-item result records.

    Each figure: {"page": "page_0250", "kind": "page" | "caption" | "image" | "caption_group", "item_index": int?}
    'page' kind needs no item_index; the others require it.
    """
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []

    with db.connect() as conn:
        for fig in figures:
            page = fig.get("page")
            kind = fig.get("kind")
            item_index = fig.get("item_index")
            try:
                if kind not in VALID_KINDS:
                    raise ValueError(f"unknown kind: {kind}")
                if not page:
                    raise ValueError("missing page")

                if kind == "page":
                    row = conn.execute(
                        "SELECT page_image_bytes FROM pages WHERE page = ?",
                        (page,),
                    ).fetchone()
                    if not row or not row[0]:
                        raise ValueError(f"no page image bytes for {page}")
                    fname = f"{page}.png"
                    blob = row[0]
                else:
                    if item_index is None:
                        raise ValueError(f"{kind} requires item_index")
                    row = conn.execute(
                        f"SELECT crop_bytes FROM {kind} WHERE page = ? AND item_index = ?",
                        (page, item_index),
                    ).fetchone()
                    if not row or not row[0]:
                        raise ValueError(
                            f"no crop bytes for {kind} {page}#{item_index}"
                        )
                    fname = f"{page}_{kind}_{item_index}.png"
                    blob = row[0]

                path = out_dir / fname
                path.write_bytes(blob)
                results.append({**fig, "saved_path": str(path), "error": None})
            except Exception as e:
                results.append({**fig, "saved_path": None, "error": str(e)})
    return results

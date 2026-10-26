"""Build a self-contained review page (HTML) for the pilot intents."""

from __future__ import annotations

import base64
import json
from pathlib import Path

from .corpus import ROOT, load_pages

OUT = ROOT / "runs" / "intent_pilot_residential"
TEMPLATE = Path(__file__).with_name("review_template.html")


def compact(r: dict, layer: str, pages: dict) -> dict:
    pg = pages.get(r["page"])
    p = r["prescription"]
    if p["op"] == "qualitative":
        val = p["qualitative"] or ""
    else:
        v = f"{p['value_min']:g}" if p["value_min"] is not None else "?"
        if p["value_max"] is not None:
            v += f"–{p['value_max']:g}"
        val = f"{p['property'] or ''} {p['op']} {v} {p['unit'] or ''}".strip()
    figs = list(r["source"].get("figure_ids") or [])
    if layer == "figure" and r.get("figure_id") and r["figure_id"] not in figs:
        figs.insert(0, r["figure_id"])
    c = r["condition"]
    cond = ", ".join(f"{k}: {v}" for k, v in c.items() if v)
    return {
        "id": r["id"], "layer": layer, "page": r["page"],
        "book_page": pg.book_page if pg else None, "pdf": pg.page_index if pg else None,
        "sub": (pg.subheadings[0] if pg and pg.subheadings else ""),
        "statement": r["statement"], "kind": r["kind"], "modality": r["modality"],
        "space": r["scope"].get("space_type") or "", "elem": r["scope"]["element_class"],
        "ifc": r["scope"].get("ifc_entity") or "", "cond": cond, "value": val,
        "concept": r["rationale"]["concept"], "stated": bool(r["rationale"]["stated"]),
        "why": r["rationale"].get("text") or "",
        "quote": r["source"]["quote"], "qv": r.get("quote_verified", ""),
        "paras": r["source"].get("paragraph_ids") or [], "figs": figs,
        "check": r["ifc_checkable"], "sketch": r.get("check_sketch") or "",
        "prov": r.get("provenance", "figure"), "caption": r.get("caption") or "",
        "dims": r.get("dimensions_read") or [],
    }


def main() -> None:
    pages = load_pages()
    text = [compact(json.loads(l), "text", pages) for l in open(OUT / "intents.jsonl", encoding="utf-8")]
    figs = [compact(json.loads(l), "figure", pages) for l in open(OUT / "figure_intents.jsonl", encoding="utf-8")]
    rows = text + figs
    rows.sort(key=lambda r: (r["pdf"] or 0, r["layer"] != "text", r["id"]))
    img_ids = sorted({f for r in rows for f in r["figs"]})
    images = {}
    for fid in img_ids:
        p = ROOT / "data" / "neufert" / "dataset" / "figures" / fid / "image.png"
        if p.exists():
            images[fid] = "data:image/png;base64," + base64.standard_b64encode(p.read_bytes()).decode()
    html = TEMPLATE.read_text(encoding="utf-8")
    html = html.replace("/*__DATA__*/", json.dumps(rows, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/"))
    html = html.replace("/*__IMAGES__*/", json.dumps(images, separators=(",", ":")))
    out = OUT / "review.html"
    out.write_text(html, encoding="utf-8")
    print(f"{len(rows)} intents ({len(text)} text + {len(figs)} figure), {len(images)} images, "
          f"{out.stat().st_size/1e6:.1f} MB -> {out}")


if __name__ == "__main__":
    main()

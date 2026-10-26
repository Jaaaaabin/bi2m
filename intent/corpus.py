"""Load the exported Neufert dataset and render one page as extractor input."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DATASET = ROOT / "data" / "neufert" / "dataset"


@dataclass
class Page:
    page: str
    page_index: int
    book_page: str | None
    chapter: str | None
    subheadings: list[str]
    topics: list[str]
    norms: list[str]
    body_text: list[dict[str, Any]]
    figures: list[dict[str, Any]] = field(default_factory=list)

    # ---- text used for quote verification ----
    def all_text_units(self) -> list[tuple[str, str]]:
        """(id, text) for every paragraph, caption and table cell on the page."""
        units: list[tuple[str, str]] = []
        for t in self.body_text:
            units.append((t["id"], t["text"]))
        for f in self.figures:
            for c in f.get("captions") or []:
                units.append((f["id"], c["text"]))
            for tb in f.get("tables") or []:
                for row in tb.get("rows") or []:
                    units.append((f["id"], " | ".join(str(c) for c in row)))
        return units

    def render(self) -> str:
        """Plain-text bundle handed to the extractor."""
        hdr = [
            f"PAGE: {self.page}  (book page {self.book_page}, pdf index {self.page_index})",
            f"CHAPTER: {self.chapter}",
            f"SUBHEADINGS: {', '.join(self.subheadings) or '-'}",
            f"TOPICS: {', '.join(self.topics) or '-'}",
            f"NORMS CITED: {', '.join(self.norms) or '-'}",
        ]
        out = ["\n".join(hdr), "\n=== BODY TEXT ==="]
        for t in self.body_text:
            cites = f"  [cites figures: {', '.join(t['cites_figures'])}]" if t.get("cites_figures") else ""
            out.append(f"\n[{t['id']}]{cites}\n{t['text'].strip()}")
        out.append("\n=== FIGURE CAPTIONS ===")
        if not self.figures:
            out.append("(none)")
        for f in sorted(self.figures, key=lambda x: x["id"]):
            nums = ",".join(f.get("figure_numbers") or []) or "?"
            cap = (f.get("caption") or "(no caption)").strip()
            out.append(f"[{f['id']}] fig.{nums}: {cap}")
            for tb in f.get("tables") or []:
                out.append("  TABLE:")
                for row in tb.get("rows") or []:
                    out.append("   | " + " | ".join(str(c) for c in row))
        return "\n".join(out)


def load_pages(dataset: Path = DATASET) -> dict[str, Page]:
    pages: dict[str, Page] = {}
    with open(dataset / "pages.jsonl", encoding="utf-8") as fh:
        for line in fh:
            d = json.loads(line)
            pages[d["page"]] = Page(
                page=d["page"], page_index=d["page_index"], book_page=d.get("book_page"),
                chapter=d.get("chapter"), subheadings=d.get("subheadings") or [],
                topics=d.get("topics") or [], norms=d.get("norms") or [],
                body_text=d.get("body_text") or [],
            )
    with open(dataset / "index.jsonl", encoding="utf-8") as fh:
        for line in fh:
            f = json.loads(line)
            if f["page"] in pages:
                pages[f["page"]].figures.append(f)
    return pages


def select_pages(pages: dict[str, Page], chapter: str | None = None,
                 subheading: str | None = None, limit: int | None = None,
                 only: list[str] | None = None) -> list[Page]:
    sel = [p for p in pages.values()]
    if chapter:
        sel = [p for p in sel if p.chapter == chapter]
    if subheading:
        sel = [p for p in sel if subheading in p.subheadings]
    if only:
        keep = set(only)
        sel = [p for p in sel if p.page in keep]
    sel.sort(key=lambda p: p.page_index)
    return sel[:limit] if limit else sel


_WS = re.compile(r"\s+")


def norm(s: str) -> str:
    s = s.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    s = s.replace("–", "-").replace("—", "-").replace(" ", " ")
    return _WS.sub(" ", s).strip().lower()

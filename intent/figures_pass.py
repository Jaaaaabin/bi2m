"""Figure pass: ask a VLM what rule a figure demonstrates that the text intents miss.

Usage (project root):
    .venv/bin/python -m intent.figures_pass --subheading ROOMS --limit 50
    .venv/bin/python -m intent.figures_pass --only page_0169_image_003 --force
"""

from __future__ import annotations

import argparse
import base64
import json
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from pydantic import BaseModel, Field

from . import llm
from .corpus import DATASET, ROOT, Page, load_pages, select_pages
from .prompts import EXTRACTOR_SYSTEM
from .schema import Intent

OUT_DEFAULT = ROOT / "runs" / "intent_pilot_residential"


class FigureExtraction(BaseModel):
    figure_id: str
    what_is_shown: str = Field(description="One or two sentences: what the drawing actually depicts (plan/section/diagram, elements, dimensions visible)")
    dimensions_read: list[str] = Field(description="Every dimension or number legible in the figure, verbatim, e.g. '13 m²', '2.10', '0.90 x 2.00'")
    intents: list[Intent] = Field(description="Rules this figure demonstrates that are NOT already covered by the text intents given; kind should be 'tacit' unless the figure states a number (then typical_value/hard_constraint)")
    already_covered: list[str] = Field(description="Statements from the given text intents that this figure illustrates (copy their text), or empty")


FIGURE_SYSTEM = EXTRACTOR_SYSTEM + """

## FIGURE MODE
You now receive ONE figure image (a crop from the page), its caption, the page header, and
the list of intents ALREADY extracted from this page's text. Your task is different:

1. Read the figure carefully: what is drawn, which dimensions are legible.
2. Output ONLY intents that the figure demonstrates and that are NOT already in the given
   text intents. Typical cases: a furniture layout implying a room proportion or a
   clearance; a plan implying an adjacency or zoning; a dimension printed in the drawing
   but not in the text; window/door placement implying a rule.
3. For these figure-derived intents, `source.quote` must be the caption text or a
   dimension string legible in the figure (verbatim). `source.figure_ids` = this figure.
4. Set kind='tacit' when the rule is implied by the drawing, not stated. If the figure
   prints a number, kind may be typical_value or hard_constraint.
5. If the figure adds nothing beyond the text intents, return an empty `intents` list —
   that is a valid and common answer. Do not restate text intents.
"""


def _img_block(path: Path) -> dict:
    data = base64.standard_b64encode(path.read_bytes()).decode()
    return {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": data}}


def run_figure(fig: dict, page: Page, text_intents: list[dict], out_dir: Path, force: bool,
               model: str) -> Path | None:
    tgt = out_dir / "figures" / f"{fig['id']}.json"
    if tgt.exists() and not force:
        return tgt
    img = DATASET / "figures" / fig["id"] / "image.png"
    if not img.exists():
        print(f"[fig] missing image {img}")
        return None
    tgt.parent.mkdir(parents=True, exist_ok=True)
    hdr = (f"PAGE: {page.page} (book page {page.book_page})\nCHAPTER: {page.chapter}\n"
           f"SUBHEADINGS: {', '.join(page.subheadings)}\nTOPICS: {', '.join(page.topics)}\n")
    cap = fig.get("caption") or "(no caption)"
    nums = ",".join(fig.get("figure_numbers") or []) or "?"
    related = "\n".join(f"  [{t['id']}] {t['text'][:400]}" for t in fig.get("related_text") or []) or "  (none)"
    ti = "\n".join(f"  - {t['statement']}" for t in text_intents) or "  (none)"
    text = (hdr + f"\nFIGURE ID: {fig['id']}\nCAPTION (fig.{nums}): {cap}\n"
            f"\nBODY TEXT PARAGRAPHS THAT CITE THIS FIGURE:\n{related}\n"
            f"\nINTENTS ALREADY EXTRACTED FROM THIS PAGE'S TEXT ({len(text_intents)}):\n{ti}\n")
    client = llm._an()
    with client.messages.stream(
        model=model, max_tokens=16000, system=FIGURE_SYSTEM,
        messages=[{"role": "user", "content": [_img_block(img), {"type": "text", "text": text}]}],
        output_format=FigureExtraction,
    ) as stream:
        resp = stream.get_final_message()
    llm.USAGE.add(model, resp.usage.input_tokens, resp.usage.output_tokens)
    if resp.stop_reason == "refusal":
        raise RuntimeError(f"refusal: {resp.stop_details}")
    res = resp.parsed_output
    res.figure_id = fig["id"]
    d = res.model_dump()
    d["page"] = page.page
    d["caption"] = cap
    d["image"] = str(img.relative_to(ROOT))
    tgt.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[fig] {fig['id']}: {len(res.intents)} new intents, {len(res.dimensions_read)} dims read")
    return tgt


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--chapter", default="Residential buildings")
    ap.add_argument("--subheading", default="ROOMS")
    ap.add_argument("--limit", type=int, default=50)
    ap.add_argument("--only", nargs="*", default=None, help="figure ids")
    ap.add_argument("--out", type=Path, default=OUT_DEFAULT)
    ap.add_argument("--model", default=llm.MODEL_JUDGE)
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    pages = select_pages(load_pages(), chapter=args.chapter, subheading=args.subheading)
    figs = [(f, p) for p in pages for f in p.figures if f.get("caption")]
    if args.only:
        keep = set(args.only)
        figs = [(f, p) for f, p in figs if f["id"] in keep]
    else:
        random.Random(args.seed).shuffle(figs)
        figs = figs[:args.limit]
    print(f"[figures] {len(figs)} figures from {len(pages)} pages -> {args.out/'figures'}")

    def text_intents_for(page: str) -> list[dict]:
        jf = args.out / "judged" / f"{page}.json"
        return json.loads(jf.read_text())["intents"] if jf.exists() else []

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(llm.with_retry, run_figure, f, p, text_intents_for(p.page), args.out,
                          args.force, args.model): f["id"] for f, p in figs}
        for fu in as_completed(futs):
            try:
                fu.result()
            except Exception as e:  # noqa: BLE001
                print(f"[fig FAILED] {futs[fu]}: {e}")
    llm.save_usage(args.out / "_usage_figures.json")
    print("[usage]", json.dumps(llm.USAGE))


if __name__ == "__main__":
    main()

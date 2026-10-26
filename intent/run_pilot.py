"""Pilot: extract intents from a chapter with two models, adjudicate, verify, summarise.

Usage (from project root):
    .venv/bin/python -m intent.run_pilot --chapter "Residential buildings" --limit 2 --stage extract
    .venv/bin/python -m intent.run_pilot --chapter "Residential buildings" --stage all
    .venv/bin/python -m intent.run_pilot --only page_0169 --stage all --force
"""

from __future__ import annotations

import argparse
import json
import random
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from . import llm
from .corpus import ROOT, Page, load_pages, select_pages
from .prompts import EXTRACTOR_SYSTEM, JUDGE_SYSTEM
from .judge_assemble import assemble, reassemble_file
from .schema import PageExtraction, PageJudgement
from .verify import verify_quote

OUT_DEFAULT = ROOT / "runs" / "intent_pilot_residential"


# --- stage 1: extraction -----------------------------------------------------

def extract_one(page: Page, which: str, out_dir: Path, force: bool) -> Path:
    tgt = out_dir / f"raw_{which.lower()}" / f"{page.page}.json"
    if tgt.exists() and not force:
        return tgt
    tgt.parent.mkdir(parents=True, exist_ok=True)
    user = page.render()
    if which == "A":
        res = llm.with_retry(llm.call_openai, EXTRACTOR_SYSTEM, user, PageExtraction, model=llm.MODEL_A)
    else:
        res = llm.with_retry(llm.call_anthropic, EXTRACTOR_SYSTEM, user, PageExtraction, model=llm.MODEL_B)
    res.page = page.page
    tgt.write_text(res.model_dump_json(indent=2), encoding="utf-8")
    print(f"[extract {which}] {page.page}: {len(res.intents)} intents")
    return tgt


def stage_extract(pages: list[Page], out_dir: Path, force: bool, workers: int) -> None:
    jobs = [(p, w) for p in pages for w in ("A", "B")]
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(extract_one, p, w, out_dir, force): (p.page, w) for p, w in jobs}
        for f in as_completed(futs):
            try:
                f.result()
            except Exception as e:  # noqa: BLE001
                print(f"[extract FAILED] {futs[f]}: {e}")


# --- stage 2: adjudication ---------------------------------------------------

def judge_one(page: Page, out_dir: Path, force: bool) -> Path | None:
    tgt = out_dir / "judged" / f"{page.page}.json"
    if tgt.exists() and not force:
        return tgt
    a = out_dir / "raw_a" / f"{page.page}.json"
    b = out_dir / "raw_b" / f"{page.page}.json"
    if not (a.exists() and b.exists()):
        print(f"[judge] {page.page}: missing raw A or B, skipping")
        return None
    tgt.parent.mkdir(parents=True, exist_ok=True)
    ea = PageExtraction.model_validate_json(a.read_text(encoding="utf-8"))
    eb = PageExtraction.model_validate_json(b.read_text(encoding="utf-8"))
    def numbered(tag: str, items) -> str:
        return "\n".join(f"--- {tag}{i} ---\n" + json.dumps(it.model_dump(), ensure_ascii=False)
                         for i, it in enumerate(items)) or "(none)"
    user = (
        "=== PAGE ===\n" + page.render() +
        "\n\n=== CANDIDATES A (" + str(len(ea.intents)) + ") ===\n" + numbered("A", ea.intents) +
        "\n\n=== CANDIDATES B (" + str(len(eb.intents)) + ") ===\n" + numbered("B", eb.intents)
    )
    res = llm.with_retry(llm.call_anthropic, JUDGE_SYSTEM, user, PageJudgement,
                         model=llm.MODEL_JUDGE, max_tokens=32000)
    res.page = page.page
    kept, problems = assemble(res, ea, eb)
    out = {"page": page.page, "intents": kept, "rejected": [r.model_dump() for r in res.rejected],
           "notes": res.notes, "problems": problems, "raw_decisions": res.model_dump()["decisions"]}
    tgt.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[judge] {page.page}: A={len(ea.intents)} B={len(eb.intents)} -> "
          f"kept {len(kept)}, rejected {len(res.rejected)}, problems {len(problems)}")
    return tgt


def stage_judge(pages: list[Page], out_dir: Path, force: bool, workers: int) -> None:
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(judge_one, p, out_dir, force): p.page for p in pages}
        for f in as_completed(futs):
            try:
                f.result()
            except Exception as e:  # noqa: BLE001
                print(f"[judge FAILED] {futs[f]}: {e}")


# --- stage 3: verify + merge + stats + review sheet --------------------------

def stage_report(pages: list[Page], out_dir: Path, sample_n: int = 50, seed: int = 7) -> None:
    by_page = {p.page: p for p in pages}
    merged = []
    per_page = {}
    for p in pages:
        jf = out_dir / "judged" / f"{p.page}.json"
        if not jf.exists():
            continue
        j = json.loads(jf.read_text(encoding="utf-8"))
        na = nb = None
        fa, fb = out_dir / "raw_a" / f"{p.page}.json", out_dir / "raw_b" / f"{p.page}.json"
        if fa.exists():
            na = len(PageExtraction.model_validate_json(fa.read_text()).intents)
        if fb.exists():
            nb = len(PageExtraction.model_validate_json(fb.read_text()).intents)
        per_page[p.page] = {"A": na, "B": nb, "kept": len(j["intents"]), "rejected": len(j["rejected"]),
                            "problems": len(j.get("problems", []))}
        for k, d in enumerate(j["intents"], 1):
            d = dict(d)
            status, uid = verify_quote(d["source"]["quote"], p)
            d["id"] = f"{p.page}_intent_{k:03d}"
            d["page"] = p.page
            d["chapter"] = p.chapter
            d["subheadings"] = p.subheadings
            d["quote_verified"] = status
            d["quote_unit"] = uid
            d["figure_images"] = [f"data/neufert/dataset/figures/{fid}/image.png" for fid in d["source"]["figure_ids"]]
            merged.append(d)

    (out_dir / "intents.jsonl").write_text(
        "\n".join(json.dumps(m, ensure_ascii=False) for m in merged) + "\n", encoding="utf-8")

    n = len(merged) or 1
    def share(counter: Counter) -> dict:
        return {k: {"n": v, "pct": round(100 * v / n, 1)} for k, v in counter.most_common()}
    stats = {
        "pages_judged": len(per_page),
        "intents_total": len(merged),
        "raw_A_total": sum(v["A"] or 0 for v in per_page.values()),
        "raw_B_total": sum(v["B"] or 0 for v in per_page.values()),
        "rejected_total": sum(v["rejected"] for v in per_page.values()),
        "by_kind": share(Counter(m["kind"] for m in merged)),
        "by_modality": share(Counter(m["modality"] for m in merged)),
        "by_provenance": share(Counter(m["provenance"] for m in merged)),
        "by_checkable": share(Counter(m["ifc_checkable"] for m in merged)),
        "by_concept": share(Counter(m["rationale"]["concept"] for m in merged)),
        "rationale_stated": share(Counter("stated" if m["rationale"]["stated"] else "inferred" for m in merged)),
        "quote_verified": share(Counter(m["quote_verified"] for m in merged)),
        "by_element_class": share(Counter(m["scope"]["element_class"] for m in merged)),
        "top_space_types": Counter(m["scope"]["space_type"] for m in merged if m["scope"]["space_type"]).most_common(15),
        "per_page": per_page,
    }
    (out_dir / "stats.json").write_text(json.dumps(stats, indent=2, ensure_ascii=False), encoding="utf-8")

    # --- stratified review sample ---
    rnd = random.Random(seed)
    by_kind: dict[str, list] = {}
    for m in merged:
        by_kind.setdefault(m["kind"], []).append(m)
    sample: list = []
    kinds = sorted(by_kind)
    quota = {k: max(1, round(sample_n * len(by_kind[k]) / n)) for k in kinds}
    for k in kinds:
        pool = by_kind[k][:]
        rnd.shuffle(pool)
        sample.extend(pool[:quota[k]])
    sample = sample[:sample_n]
    sample.sort(key=lambda m: m["id"])

    lines = ["# Pilot review sample", "",
             f"{len(sample)} intents, stratified by kind. Fill the **Verdict** column: "
             "`ok` / `partial` / `wrong` / `not_an_intent`, and a note if useful.", "",
             "| # | id | kind | statement | quote (verified?) | concept (stated?) | checkable | Verdict | Note |",
             "|---|---|---|---|---|---|---|---|---|"]
    for i, m in enumerate(sample, 1):
        st = m["statement"].replace("|", "\\|")
        q = m["source"]["quote"].replace("|", "\\|").replace("\n", " ")
        figs = " ".join(f"[{Path(x).parent.name}]({x})" for x in m["figure_images"])
        lines.append(
            f"| {i} | `{m['id']}` | {m['kind']} / {m['modality']} | {st} | “{q}” ({m['quote_verified']}) {figs} | "
            f"{m['rationale']['concept']} ({'stated' if m['rationale']['stated'] else 'inferred'}) | "
            f"{m['ifc_checkable']} |  |  |")
    (out_dir / "review_sample.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps({k: v for k, v in stats.items() if k != "per_page"}, indent=2, ensure_ascii=False))
    print(f"\n[written] {out_dir/'intents.jsonl'}  {out_dir/'stats.json'}  {out_dir/'review_sample.md'}")


# --- cli ---------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--chapter", default="Residential buildings")
    ap.add_argument("--subheading", default=None)
    ap.add_argument("--only", nargs="*", default=None, help="page ids")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--stage", choices=["extract", "judge", "reassemble", "report", "all"], default="all")
    ap.add_argument("--out", type=Path, default=OUT_DEFAULT)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()

    pages = select_pages(load_pages(), chapter=args.chapter, subheading=args.subheading,
                         limit=args.limit, only=args.only)
    print(f"[pilot] {len(pages)} pages -> {args.out}")
    args.out.mkdir(parents=True, exist_ok=True)

    if args.stage in ("extract", "all"):
        stage_extract(pages, args.out, args.force, args.workers)
    if args.stage in ("judge", "all"):
        stage_judge(pages, args.out, args.force, max(1, args.workers // 2))
    if args.stage == "reassemble":
        for p in pages:
            jf = args.out / "judged" / f"{p.page}.json"
            if jf.exists():
                ea = PageExtraction.model_validate_json((args.out / "raw_a" / f"{p.page}.json").read_text())
                eb = PageExtraction.model_validate_json((args.out / "raw_b" / f"{p.page}.json").read_text())
                o = reassemble_file(jf, ea, eb)
                if o["problems"]:
                    print(f"[reassemble] {p.page}: still {len(o['problems'])} problems")
        stage_report(pages, args.out)
    if args.stage in ("report", "all"):
        stage_report(pages, args.out)
    llm.save_usage(args.out / "_usage.json")
    if llm.USAGE:
        print("[usage]", json.dumps(llm.USAGE))


if __name__ == "__main__":
    main()

"""Run the knowledge probes through subject models and grade them.

    .venv/bin/python -m qa_agent.run_probes --models sonnet,luna,gemini,jev --formats mcq,open --limit 5

Outputs runs/<timestamp>/: answers.jsonl, graded.jsonl, summary.json, summary.md
JEV takes part in mcq only; open answers are judged by JEV.
"""

from __future__ import annotations

import argparse
import collections
import json
import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from .agent import QAAgent
from .config import MODELS, PACKS, PROBES, RUNS
from .judge import grade_mcq, grade_open
from .types import Question


def window(context: str, quote: str, chars: int = 1200) -> str:
    """The paragraph around a quote, capped at about `chars` characters centred on the quote."""
    i = context.find(quote)
    if len(context) <= chars:
        return context
    if i < 0:
        return quote
    pad = max(0, (chars - len(quote)) // 2)
    a, b = max(0, i - pad), min(len(context), i + len(quote) + pad)
    return ("…" if a else "") + context[a:b] + ("…" if b < len(context) else "")


def load_contexts() -> dict[str, list[str]]:
    """title -> source paragraph around each quote (from the probe source packs)."""
    out = {}
    for f in PACKS:
        for p in json.load(open(f, encoding="utf-8")):
            out[p["title"]] = [window(e.get("context") or e["quote"], e["quote"]) for e in p["evidence"]]
    return out


def load_questions(path: Path, formats: list[str], limit: int | None, kids: set[str] | None,
                   shuffle_seed: int | None) -> list[Question]:
    rows = [json.loads(l) for l in open(path, encoding="utf-8")]
    if kids:
        rows = [r for r in rows if r["kid"] in kids or r["title"] in kids]
    if limit:
        rows = rows[:limit]
    ctx = load_contexts()
    qs = []
    for r in rows:
        meta = {k: r[k] for k in ("title", "topic", "priority", "lod", "modality") if k in r}
        source = [b["quote"] for b in r.get("basis", [])]
        context = ctx.get(r["title"], source)
        if "mcq" in formats:
            opts, correct = list(r["mcq"]["options"]), r["mcq"]["correct"]
            if shuffle_seed is not None:
                rng = random.Random(f"{shuffle_seed}:{r['kid']}")
                order = list(range(len(opts)))
                rng.shuffle(order)
                opts, correct = [opts[i] for i in order], order.index(correct)
            qs.append(Question(qid=r["kid"], format="mcq", text=r["question"], options=opts, correct=correct,
                               source=source, context=context, meta=meta))
        if "open" in formats:
            qs.append(Question(qid=r["kid"], format="open", text=r["question"], gold=r["answer"],
                               accept=r.get("accept", []), rubric=r.get("rubric", []), source=source, context=context, meta=meta))
    return qs


def run_one(agent: QAAgent, q: Question, judge: bool) -> dict:
    a = agent.answer(q)
    if q.format == "mcq":
        g = grade_mcq(q, a)
    elif judge:
        try:
            g = grade_open(q, a)
        except Exception as e:  # noqa: BLE001
            g = {"label": "judge_error", "correct": False, "error": f"{type(e).__name__}: {e}"}
    else:
        g = {"label": "ungraded", "correct": None}
    return {"question": q.__dict__, "answer": a.to_dict(), "grade": g}


def summarise(results: list[dict]) -> dict:
    by = collections.defaultdict(lambda: collections.Counter())
    lat = collections.defaultdict(list)
    for r in results:
        key = (r["answer"]["model"], r["question"]["format"])
        by[key][r["grade"]["label"]] += 1
        by[key]["n"] += 1
        by[key]["correct_n"] += bool(r["grade"].get("correct"))
        by[key]["needs_review"] += bool(r["grade"].get("needs_review"))
        lat[key].append(r["answer"]["latency_s"])
    out = {}
    for (m, f), c in sorted(by.items()):
        n = c["n"]
        out[f"{m}/{f}"] = {"n": n, "accuracy": round(c["correct_n"] / n, 3) if n else None,
                          "labels": {k: v for k, v in c.items() if k not in ("n", "correct_n", "needs_review")},
                          "needs_review": c["needs_review"],
                          "median_latency_s": sorted(lat[(m, f)])[len(lat[(m, f)]) // 2]}
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", default="sonnet,luna,gemini,jev")
    ap.add_argument("--formats", default="mcq,open")
    ap.add_argument("--limit", type=int, default=None, help="first N knowledge points")
    ap.add_argument("--kids", default="", help="comma-separated knowledge ids or titles")
    ap.add_argument("--shuffle-seed", type=int, default=None, help="shuffle mcq options per item with this seed")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--no-judge", action="store_true", help="skip judging open answers")
    ap.add_argument("--probes", default=str(PROBES))
    args = ap.parse_args()

    models = [m.strip() for m in args.models.split(",") if m.strip()]
    formats = [f.strip() for f in args.formats.split(",") if f.strip()]
    for m in models:
        if m not in MODELS:
            raise SystemExit(f"unknown model {m}; known: {sorted(MODELS)}")
    qs = load_questions(Path(args.probes), formats, args.limit,
                        {k.strip() for k in args.kids.split(",") if k.strip()} or None, args.shuffle_seed)
    jobs = [(QAAgent(m), q) for m in models for q in qs if QAAgent(m).supports(q.format)]
    out_dir = RUNS / time.strftime("%Y%m%d-%H%M%S")
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "config.json").write_text(json.dumps(vars(args) | {"model_ids": {m: MODELS[m].model_id for m in models}},
                                                    indent=2), encoding="utf-8")
    print(f"{len(qs)} questions x {len(models)} models -> {len(jobs)} jobs -> {out_dir}")

    results = []
    with ThreadPoolExecutor(max_workers=args.workers) as ex, \
            open(out_dir / "graded.jsonl", "w", encoding="utf-8") as fg:
        futs = {ex.submit(run_one, ag, q, not args.no_judge): (ag.spec.alias, q.qid, q.format) for ag, q in jobs}
        for i, fut in enumerate(as_completed(futs), 1):
            r = fut.result()
            results.append(r)
            fg.write(json.dumps(r, ensure_ascii=False) + "\n"); fg.flush()
            m, qid, fmt = futs[fut]
            print(f"[{i}/{len(jobs)}] {m:7s} {fmt:4s} {qid:5s} -> {r['grade']['label']}"
                  + (f"  ERR {r['answer']['error'][:80]}" if r['answer'].get('error') else ""))

    with open(out_dir / "answers.jsonl", "w", encoding="utf-8") as fa:
        for r in sorted(results, key=lambda r: (r["answer"]["model"], r["question"]["qid"], r["question"]["format"])):
            fa.write(json.dumps(r["answer"], ensure_ascii=False) + "\n")
    summ = summarise(results)
    (out_dir / "summary.json").write_text(json.dumps(summ, indent=2, ensure_ascii=False), encoding="utf-8")
    lines = ["| model / format | n | accuracy | labels | needs review | median latency (s) |", "|---|---|---|---|---|---|"]
    for k, v in summ.items():
        lines.append(f"| {k} | {v['n']} | {v['accuracy']} | {v['labels']} | {v['needs_review']} | {v['median_latency_s']} |")
    (out_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()

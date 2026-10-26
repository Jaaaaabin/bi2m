"""Tune the gold-less open-question judge against a labelled test suite.

    .venv/bin/python -m qa_agent.judge_tune build                     # generate the suite (cached)
    .venv/bin/python -m qa_agent.judge_tune run --judges v1_quotes,v2_quotes --split dev
    .venv/bin/python -m qa_agent.judge_tune run --judges v2_quotes --split holdout

Suite (per knowledge point):
  positives  gold answer, every accepted form, and three faithful rewrites made by Claude
             (paraphrase with unit conversion, verbose model-style answer, terse reordered answer)
             -> must be graded "correct"
  negatives  every MCQ distractor, a near-miss rewrite (one requested value/rule changed) and an omission
             rewrite (a requested part left out or left vague)
             -> must NOT be graded "correct"
Split: knowledge points are split 60/40 into dev / holdout by a hash of the id (prompts are tuned on dev only).
The judge never sees the gold answer; the suite only uses it to label the test items.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import providers
from .config import ROOT, JUDGE_MODEL, PROBES
from .judge import JUDGES, judge_request, read_verdict
from .run_probes import load_questions

OUT = ROOT / "runs" / "judge_tune"
SUITE = OUT / "suite.jsonl"
GEN_CACHE = OUT / "variants_cache.jsonl"
GEN_MODEL = "claude-sonnet-5-5"

POS_TYPES = ("gold", "accept", "paraphrase", "verbose", "terse")
NEG_TYPES = ("distractor", "near_miss", "omission")

GEN_SYSTEM = "You write test items for an answer-grading model. Reply with one JSON object only, no code fence."

GEN_PROMPT = """Question:
{question}

Reference answer:
{gold}

Source text (authoritative):
{source}

Write five answers to the question:
1. "paraphrase": a correct answer in one or two full sentences, different wording from the reference; convert at least
   one unit or notation where natural (e.g. 1.25 m -> 125 cm, "min." -> "at least", ">" -> "more than"). Every
   value and rule must stay exactly equivalent to the reference.
2. "verbose": a correct answer the way a knowledgeable model would write it: the answer plus two or three sentences of
   reasoning or background. The background must not add any new number, and must not contradict the source.
3. "terse": a correct answer with only the values/keywords, parts in a different order or notation if there are several,
   each part labelled so it is unambiguous.
4. "near_miss": looks like a confident, well-written answer, but exactly one requested value or rule is changed to a
   plausible wrong one (everything else correct).
5. "omission": if the question asks for several parts, answer correctly but leave one requested part out entirely;
   if it asks for one thing, give a vague answer that does not commit to the value or rule.

JSON keys: paraphrase, verbose, terse, near_miss, omission (strings)."""


def split_of(kid: str) -> str:
    return "dev" if int(hashlib.md5(kid.encode()).hexdigest(), 16) % 5 < 3 else "holdout"


def _json(text: str) -> dict:
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    return json.loads(t[t.index("{"): t.rindex("}") + 1])


def generate(q) -> dict:
    prompt = GEN_PROMPT.format(question=q.text, gold=q.gold, source="\n".join(q.source))
    for _ in range(3):
        text, _, _ = providers.call_anthropic(GEN_MODEL, GEN_SYSTEM, prompt, effort="low")
        try:
            d = _json(text)
            if all(isinstance(d.get(k), str) and d[k].strip() for k in ("paraphrase", "verbose", "terse", "near_miss", "omission")):
                return d
        except (ValueError, json.JSONDecodeError):
            pass
    raise RuntimeError(f"no valid variants for {q.qid}")


def build(workers: int) -> None:
    OUT.mkdir(exist_ok=True)
    opens = {q.qid: q for q in load_questions(PROBES, ["open"], None, None, None)}
    mcqs = {q.qid: q for q in load_questions(PROBES, ["mcq"], None, None, None)}
    cache = {}
    if GEN_CACHE.exists():
        cache = {r["kid"]: r["variants"] for r in map(json.loads, open(GEN_CACHE, encoding="utf-8"))}
    todo = [q for k, q in opens.items() if k not in cache]
    print(f"generating variants for {len(todo)} points ({len(cache)} cached)")
    with ThreadPoolExecutor(workers) as ex, open(GEN_CACHE, "a", encoding="utf-8") as fc:
        for q, d in zip(todo, ex.map(generate, todo)):
            cache[q.qid] = d
            fc.write(json.dumps({"kid": q.qid, "variants": d}, ensure_ascii=False) + "\n")

    items = []
    for kid, q in opens.items():
        v = cache[kid]

        def add(kind, text, n=0):
            items.append({"id": f"{kid}:{kind}:{n}", "kid": kid, "kind": kind, "positive": kind in POS_TYPES,
                          "split": split_of(kid), "candidate": text})
        add("gold", q.gold)
        for i, t in enumerate(q.accept):
            add("accept", t, i)
        for k in ("paraphrase", "verbose", "terse", "near_miss", "omission"):
            add(k, v[k])
        m = mcqs[kid]
        for i, o in enumerate(m.options):
            if i != m.correct:
                add("distractor", o, i)
    with open(SUITE, "w", encoding="utf-8") as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")
    c = collections.Counter((it["split"], it["kind"]) for it in items)
    print(f"{len(items)} items -> {SUITE}")
    for s in ("dev", "holdout"):
        print(s, {k: c[(s, k)] for k in POS_TYPES + NEG_TYPES})


def _key(judge: str, model: str, item: dict, repeat: int = 0) -> str:
    cfg = json.dumps(JUDGES[judge], sort_keys=True)
    rep = f"|rep{repeat}" if repeat else ""
    return hashlib.md5(f"{model}|{cfg}|{item['id']}|{item['candidate']}{rep}".encode()).hexdigest()


def run(judges: list[str], split: str, model: str, workers: int, show: int, repeat: int = 0) -> None:
    items = [json.loads(l) for l in open(SUITE, encoding="utf-8")]
    if split != "all":
        items = [it for it in items if it["split"] == split]
    qs = {q.qid: q for q in load_questions(PROBES, ["open"], None, None, None)}
    cache_f = OUT / "judge_cache.jsonl"
    cache = {}
    if cache_f.exists():
        cache = {r["key"]: r for r in map(json.loads, open(cache_f, encoding="utf-8"))}

    def one(args):
        judge, it = args
        k = _key(judge, model, it, repeat)
        if k in cache:
            return cache[k]
        state, questions = judge_request(qs[it["kid"]], it["candidate"], judge)
        answers, usage = providers.call_jev(model, state, questions)
        return {"key": k, "judge": judge, "id": it["id"], "answers": answers, "usage": usage}

    report = {}
    for judge in judges:
        with ThreadPoolExecutor(workers) as ex:
            res = list(ex.map(one, [(judge, it) for it in items]))
        with open(cache_f, "a", encoding="utf-8") as fc:
            for r in res:
                if r["key"] not in cache:
                    cache[r["key"]] = r
                    fc.write(json.dumps(r, ensure_ascii=False) + "\n")
        by = collections.defaultdict(collections.Counter)
        fails = []
        tokens = []
        for it, r in zip(items, res):
            v = read_verdict(r["answers"], judge)
            ok = (v["label"] == "correct") == it["positive"]
            by[it["kind"]]["n"] += 1
            by[it["kind"]]["ok"] += ok
            tokens.append((r.get("usage") or {}).get("input_tokens", 0))
            if not ok:
                fails.append((it, v))
        pos = [it for it in items if it["positive"]]
        neg = [it for it in items if not it["positive"]]
        pos_ok = sum(by[k]["ok"] for k in POS_TYPES)
        neg_bad = sum(by[k]["n"] - by[k]["ok"] for k in NEG_TYPES)
        report[judge] = {
            "split": split, "n": len(items),
            "positives_full_marks": f"{pos_ok}/{len(pos)} = {pos_ok / max(1, len(pos)):.1%}",
            "negatives_false_correct": f"{neg_bad}/{len(neg)} = {neg_bad / max(1, len(neg)):.1%}",
            "by_kind": {k: f"{by[k]['ok']}/{by[k]['n']}" for k in POS_TYPES + NEG_TYPES if by[k]["n"]},
            "mean_input_tokens": round(sum(tokens) / max(1, len(tokens))),
        }
        print(f"\n== {judge} on {split}: positives {report[judge]['positives_full_marks']}, "
              f"negatives graded correct {report[judge]['negatives_false_correct']}")
        print("   ", report[judge]["by_kind"])
        for it, v in fails[:show]:
            print(f"   FAIL {it['id']:22s} {v['label']:17s} {json.dumps(v.get('verdict_probs'))[:80]}  | {it['candidate'][:150]!r}")
        with open(OUT / f"fails_{judge}_{split}.jsonl", "w", encoding="utf-8") as ff:
            for it, v in fails:
                ff.write(json.dumps({"item": it, "verdict": v, "gold": qs[it["kid"]].gold,
                                     "question": qs[it["kid"]].text}, ensure_ascii=False) + "\n")
    rf = OUT / "report.json"
    old = json.loads(rf.read_text()) if rf.exists() else {}
    old.update({f"{j}@{split}" + (f"#rep{repeat}" if repeat else ""): r for j, r in report.items()})
    rf.write_text(json.dumps(old, indent=2, ensure_ascii=False), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["build", "run"])
    ap.add_argument("--judges", default="v2_quotes")
    ap.add_argument("--split", default="dev", choices=["dev", "holdout", "all"])
    ap.add_argument("--model", default=JUDGE_MODEL)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--repeat", type=int, default=0, help="n>0: fresh judge calls (stability check), cached separately")
    ap.add_argument("--show", type=int, default=15, help="failures to print per judge")
    a = ap.parse_args()
    if a.cmd == "build":
        build(a.workers)
    else:
        run([j.strip() for j in a.judges.split(",")], a.split, a.model, a.workers, a.show, a.repeat)


if __name__ == "__main__":
    main()

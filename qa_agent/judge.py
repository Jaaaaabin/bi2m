"""Grading.

MCQ  : rule-based - parsed letter vs the correct option.
Open : JEV (TypeSafe decision model) as judge, plus a deterministic numeric check.
       The judge does NOT see the reference answer. Its state holds only the question, the verbatim source text
       (quotes, or the paragraph around them) and the candidate answer; it decides from the source whether the
       candidate states what the question asks for. Judge prompts are versioned in JUDGES; tuned with
       qa_agent/judge_tune.py.
       The numeric check (outside the judge) compares unit-normalised values with the reference answer and
       only flags items for review.
"""

from __future__ import annotations

import re

from . import providers
from .config import JUDGE_MODEL
from .types import LETTERS, Answer, Question

# --------------------------------------------------------------------------- MCQ


def grade_mcq(q: Question, a: Answer) -> dict:
    gold = LETTERS[q.correct]
    if a.error:
        return {"label": "error", "correct": False, "gold": gold}
    if not a.choice:
        return {"label": "unparsed", "correct": False, "gold": gold}
    ok = a.choice == gold
    out = {"label": "correct" if ok else "incorrect", "correct": ok, "gold": gold, "chosen": a.choice}
    if a.choice_probs:
        out["p_gold"] = a.choice_probs.get(gold)
    return out


# --------------------------------------------------------------------------- numeric check

_UNIT = {"mm": ("len", 0.001), "cm": ("len", 0.01), "m": ("len", 1.0), "km": ("len", 1000.0),
         "m²": ("area", 1.0), "m2": ("area", 1.0), "sqm": ("area", 1.0), "cm²": ("area", 1e-4),
         "m³": ("vol", 1.0), "m3": ("vol", 1.0), "%": ("pct", 1.0), "°": ("deg", 1.0), "deg": ("deg", 1.0),
         "kn/m²": ("load", 1.0), "kn/m2": ("load", 1.0)}
_NUM = re.compile(r"(\d+(?:[.,]\d+)?)(?:\s*/\s*(\d+(?:[.,]\d+)?))?\s*(kN/m²|kN/m2|mm|cm|km|m²|m2|m³|m3|sqm|m|%|°|deg)?(?![\w²³])", re.I)
_RANGE = re.compile(r"^\s*(?:–|-|to|—)\s*$")


def quantities(text: str) -> list[tuple[str, float]]:
    """(dimension, value in base unit) for every number in text; units carry back over ranges like '59–65 cm'."""
    toks = []
    for m in _NUM.finditer(text.replace(" ", " ")):
        a = float(m.group(1).replace(",", "."))
        val = a / float(m.group(2).replace(",", ".")) if m.group(2) else a
        unit = (m.group(3) or "").lower()
        toks.append([m.start(), m.end(), val, unit])
    for i in range(len(toks) - 1):
        if not toks[i][3] and toks[i + 1][3] and _RANGE.match(text[toks[i][1]:toks[i + 1][0]]):
            toks[i][3] = toks[i + 1][3]
    out = []
    for _, _, val, unit in toks:
        dim, f = _UNIT.get(unit, ("num", 1.0))
        out.append((dim, round(val * f, 6)))
    return out


def numeric_check(gold: str, candidate: str) -> dict | None:
    g = quantities(gold)
    if not g:
        return None
    c = quantities(candidate)

    def found(dim, v):
        return any(abs(v - cv) <= max(1e-9, 0.005 * abs(v)) and (dim == cd or "num" in (dim, cd)) for cd, cv in c)

    hits = [found(d, v) for d, v in g]
    return {"gold_values": len(g), "matched": sum(hits), "recall": round(sum(hits) / len(g), 3)}


# --------------------------------------------------------------------------- open-question judge

INSTR_V1 = ("Grade the candidate answer to this exam question. The source text is the authoritative reference: "
            "the correct answer is stated in it. Judge factual agreement with the source only; ignore length, style "
            "and extra explanation that does not change the facts.")

CRIT_V1 = {
    "correct": "Every value or rule the question asks for is stated in the candidate answer and agrees with the source "
               "text (equivalent units or wording count as agreeing), and nothing it states contradicts the source.",
    "partially_correct": "Part of what was asked is stated and agrees with the source, but another part is missing, "
                         "disagrees with the source, or the candidate adds a statement that contradicts the source.",
    "incorrect": "The core value or rule asked for is missing or disagrees with the source text, or the candidate does "
                 "not answer the question.",
}

INSTR_V2 = ("You grade answers to a closed-book exam on architectural design rules. The source text is the "
            "authoritative reference and contains the correct answer. First identify, from the source, exactly which "
            "values or rules the question asks for. Then check whether the candidate states each of them. "
            "Grade facts only. A candidate is NOT penalised for: being terse (a bare value such as '1.25 m' or "
            "'22 m / 1.25 m' is a complete answer), different wording or word order, equivalent units or notation "
            "(125 cm = 1.25 m, 'min. 2.5 m' = 'at least 2.50 m', '>' = 'more than'), naming the parts in a different "
            "order, hedging, or extra explanation and background that does not contradict the source. "
            "A candidate IS penalised when a value or rule it gives differs from the source, or when a part the "
            "question asks for is missing.")

CRIT_V2 = {
    "correct": "Each value or rule the question asks for appears in the candidate answer and matches the source "
               "(after unit conversion and paraphrase). Nothing the candidate states contradicts the source.",
    "partially_correct": "At least one requested value or rule matches the source, but another requested part is "
                         "missing or differs from the source.",
    "incorrect": "None of the requested values or rules matches the source, or the main one differs from the source, "
                 "or the candidate gives no answer.",
}

GLOSSARY = ("German regulatory terms and their English renderings are equivalent, e.g. 'schwer entflammbar' = "
            "'flame-resistant' = 'hardly flammable' = 'flame-retardant' (material class B1); 'feuerhemmend' = "
            "'fire-retarding' = F 30; 'feuerbeständig' = 'fire-resistant' = F 90; 'nichtbrennbar' = 'non-combustible' "
            "(A); 'lichte Breite/Höhe' = 'clear width/height'; 'Rohbaumaß' = 'structural/shell/rough opening'.")

INSTR_V3 = INSTR_V2 + (" The source has two parts: source_quotes (the key sentences) and source_context (the paragraph "
                       "around them); together they contain the full answer. ") + GLOSSARY

# name -> judge prompt. "source": which source text goes into the state ("quotes" or "context").
JUDGES = {
    "v1_quotes": {"source": "quotes", "instructions": INSTR_V1, "criteria": CRIT_V1, "checks": False},
    "v1_context": {"source": "context", "instructions": INSTR_V1, "criteria": CRIT_V1, "checks": False},
    "v2_quotes": {"source": "quotes", "instructions": INSTR_V2, "criteria": CRIT_V2, "checks": False},
    "v2_context": {"source": "context", "instructions": INSTR_V2, "criteria": CRIT_V2, "checks": False},
    "v2_quotes_checks": {"source": "quotes", "instructions": INSTR_V2, "criteria": CRIT_V2, "checks": True},
    "v3_both": {"source": "both", "instructions": INSTR_V3, "criteria": CRIT_V2, "checks": False},
    "v3_both_checks": {"source": "both", "instructions": INSTR_V3, "criteria": CRIT_V2, "checks": True},
}
DEFAULT_JUDGE = "v3_both_checks"

CHECKS = {
    "complete": "The candidate answer states every value or rule that the question asks for (whether or not it is "
                "right). A terse answer that only gives the values counts as complete.",
    "contradicts": "The candidate answer states at least one value or rule that differs from the source text "
                   "(after unit conversion; wording differences do not count).",
}


def judge_request(q: Question, candidate: str, judge: str = DEFAULT_JUDGE) -> tuple[dict, dict]:
    cfg = JUDGES[judge]
    if cfg["source"] == "both":
        ctx = list(dict.fromkeys(q.context))            # packs repeat a paragraph when several quotes share it
        state = {"question": q.text, "source_quotes": q.source, "source_context": ctx, "candidate_answer": candidate}
    else:
        source = list(dict.fromkeys(q.context)) if cfg["source"] == "context" and q.context else q.source
        state = {"question": q.text, "source_text": source, "candidate_answer": candidate}
    questions = {"verdict": {"type": "choice", "instructions": cfg["instructions"], "criteria": cfg["criteria"]}}
    if cfg["checks"]:
        for k, ins in CHECKS.items():
            questions[k] = {"type": "noul", "instructions": ins}
    return state, questions


def read_verdict(answers: dict, judge: str = DEFAULT_JUDGE) -> dict:
    v = answers.get("verdict", {})
    label = v.get("choice", "incorrect")
    out = {"label": label, "verdict_probs": v.get("probabilities")}
    if JUDGES[judge]["checks"]:
        pc, px = answers.get("complete", {}).get("noul"), answers.get("contradicts", {}).get("noul")
        out |= {"p_complete": pc, "p_contradicts": px}
        # a confident check overrides a verdict it clearly disagrees with
        if label == "correct" and ((px is not None and px > 0.8) or (pc is not None and pc < 0.2)):
            out["label"] = "partially_correct"
        elif label != "correct" and pc is not None and px is not None and pc > 0.8 and px < 0.2:
            out["label"] = "correct"
    probs = out["verdict_probs"] or {}
    out["verdict_margin"] = round(max(probs.values()), 3) if probs else None
    return out


def grade_open(q: Question, a: Answer, model: str = JUDGE_MODEL, judge: str = DEFAULT_JUDGE) -> dict:
    if a.error:
        return {"label": "error", "correct": False}
    if not a.text.strip():
        return {"label": "no_answer", "correct": False}
    state, questions = judge_request(q, a.text.strip(), judge)
    answers, usage = providers.call_jev(model, state, questions)
    out = read_verdict(answers, judge)
    label = out["label"]
    out |= {"correct": label == "correct", "numeric": numeric_check(q.gold, a.text),
            "judge_model": model, "judge": judge, "judge_usage": usage}
    num = out["numeric"]
    out["needs_review"] = bool((num and ((num["recall"] == 1.0 and label == "incorrect")
                                         or (num["recall"] == 0.0 and label == "correct")))
                               or (out["verdict_margin"] is not None and out["verdict_margin"] < 0.7))
    return out

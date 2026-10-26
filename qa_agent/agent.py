"""QA agent: answers a multiple-choice or open question with one subject model.

A single call per question (closed book, no tools) - the task needs no agent loop.
JEV answers multiple choice through its native `choice` question type and cannot answer open questions.
"""

from __future__ import annotations

import re
import time

from . import providers
from .config import CLAUDE_EFFORT, MODELS, ModelSpec
from .types import LETTERS, Answer, Question

SYSTEM_OPEN = (
    "You are answering a closed-book question about architectural design rules and building regulations. "
    "Answer from your own knowledge. Give the answer directly and concisely: the value(s) with units, or the rule "
    "in one or two sentences. If the question asks for several values, give each of them. "
    "Do not ask for clarification; if you are unsure, still give your best answer."
)

SYSTEM_MCQ = (
    "You are answering a closed-book multiple-choice question about architectural design rules and building "
    "regulations. Exactly one option is correct. You may reason briefly first, but the last line of your reply "
    "must be exactly 'Answer: <letter>'."
)


def render_mcq(q: Question) -> str:
    opts = "\n".join(f"{LETTERS[i]}. {o}" for i, o in enumerate(q.options))
    return f"{q.text}\n\n{opts}\n\nEnd with a final line 'Answer: <letter>' ({', '.join(LETTERS[:len(q.options)])})."


_LETTER = re.compile(r"(?i)(?:answer|option|choice)\s*(?:is|:)?\s*\(?\*{0,2}([A-H])\b")


def parse_letter(text: str, n_options: int) -> str | None:
    """Letter from a reply such as 'B', '**B**', '(B) ...', 'Answer: B'. None if absent or ambiguous."""
    allowed = LETTERS[:n_options]
    t = text.strip()
    # 1) last explicit "Answer: X"
    finals = [m.group(1).upper() for m in re.finditer(r"(?i)answer\s*[:\-]\s*\**\(?([A-H])\b", t)]
    if finals and finals[-1] in allowed:
        return finals[-1]
    # 2) a last line that is just a letter, e.g. "**B**"
    last = t.splitlines()[-1] if t else ""
    m = re.fullmatch(r"[\s*(\[]*([A-H])[\s*.)\]:]*", last)
    if m and m.group(1).upper() in allowed:
        return m.group(1).upper()
    m = re.fullmatch(r"[\s*(\[]*([A-H])[\s*.)\]:]*", t)
    if m and m.group(1).upper() in allowed:
        return m.group(1).upper()
    m = _LETTER.search(t)
    if m and m.group(1).upper() in allowed:
        return m.group(1).upper()
    m = re.match(r"[\s*(\[]*([A-H])[\s.):\]]", t)
    if m and m.group(1).upper() in allowed:
        return m.group(1).upper()
    found = {c for c in re.findall(r"\b([A-H])\b", t) if c in allowed}
    return found.pop() if len(found) == 1 else None


class QAAgent:
    def __init__(self, alias: str):
        if alias not in MODELS:
            raise KeyError(f"unknown model {alias!r}; choose from {sorted(MODELS)}")
        self.spec: ModelSpec = MODELS[alias]

    def supports(self, fmt: str) -> bool:
        return fmt == "mcq" or self.spec.open_ended

    def answer(self, q: Question) -> Answer:
        a = Answer(qid=q.qid, format=q.format, model=self.spec.alias, model_id=self.spec.model_id)
        if not self.supports(q.format):
            a.error = f"{self.spec.alias} cannot answer {q.format} questions"
            return a
        t0 = time.time()
        try:
            if self.spec.provider == "jev":
                self._jev_mcq(q, a)
            else:
                system, user = (SYSTEM_MCQ, render_mcq(q)) if q.format == "mcq" else (SYSTEM_OPEN, q.text)
                a.text, a.stop_reason, a.usage = self._text_call(system, user)
                if q.format == "mcq":
                    a.choice = parse_letter(a.text, len(q.options))
        except Exception as e:  # noqa: BLE001 - recorded per item, the run continues
            a.error = f"{type(e).__name__}: {e}"
        a.latency_s = round(time.time() - t0, 2)
        return a

    def _text_call(self, system: str, user: str):
        p, m = self.spec.provider, self.spec.model_id
        if p == "anthropic":
            return providers.call_anthropic(m, system, user, effort=CLAUDE_EFFORT)
        if p == "openai":
            return providers.call_openai(m, system, user)
        if p == "gemini":
            return providers.call_gemini(m, system, user)
        raise ValueError(p)

    def _jev_mcq(self, q: Question, a: Answer) -> None:
        criteria = {LETTERS[i]: o for i, o in enumerate(q.options)}
        answers, usage = providers.call_jev(
            self.spec.model_id,
            state={"question": q.text},
            questions={"answer": {"type": "choice",
                                  "instructions": "Which option correctly answers the question? Exactly one option is correct.",
                                  "criteria": criteria}},
        )
        ans = answers.get("answer", {})
        a.choice = ans.get("choice")
        a.choice_probs = ans.get("probabilities")
        a.text = a.choice or ""
        a.stop_reason = "choice"
        a.usage = usage

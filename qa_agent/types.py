"""Question / answer records passed between agent, judge and runner."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Literal

Format = Literal["mcq", "open"]
LETTERS = "ABCDEFGH"


@dataclass
class Question:
    qid: str                       # knowledge-point id, e.g. "K07"
    format: Format
    text: str
    options: list[str] = field(default_factory=list)     # mcq only
    correct: int | None = None                           # mcq only: index into options
    gold: str = ""                                       # open: reference answer
    accept: list[str] = field(default_factory=list)      # open: equivalent forms
    rubric: list[str] = field(default_factory=list)      # open: key points
    source: list[str] = field(default_factory=list)      # verbatim source quotes
    context: list[str] = field(default_factory=list)     # surrounding source paragraph per quote (judge only)
    meta: dict = field(default_factory=dict)             # title, topic, priority, ...


@dataclass
class Answer:
    qid: str
    format: Format
    model: str                     # alias
    model_id: str
    text: str = ""                 # raw model output (open answer, or mcq reply text)
    choice: str | None = None      # mcq: parsed letter
    choice_probs: dict[str, float] | None = None   # mcq via JEV: per-option probability
    stop_reason: str | None = None
    error: str | None = None
    latency_s: float = 0.0
    usage: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

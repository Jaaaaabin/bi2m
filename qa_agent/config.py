"""Model registry and shared settings for the QA agent."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]          # 4_bim_intent/
load_dotenv(ROOT / ".env")

PROBES = ROOT / "knowledge" / "knowledge_probes.jsonl"
PACKS = sorted((ROOT / "knowledge" / "probes").glob("pack_*.json"))   # source context per point
RUNS = ROOT / "runs" / "qa_probes"


def env(*names: str) -> str:
    """First non-empty env var among names (the .env uses non-standard names such as Gemini_KET)."""
    for n in names:
        v = os.getenv(n)
        if v and v.strip():
            return v.strip().strip('"')
    raise RuntimeError(f"none of {names} is set in {ROOT / '.env'}")


@dataclass(frozen=True)
class ModelSpec:
    alias: str          # short name used on the command line
    provider: str       # anthropic | openai | gemini | jev
    model_id: str
    open_ended: bool    # can generate free text (False for JEV: it only returns choices/probabilities)


# Subject models under test. JEV is a decision model: multiple choice only.
MODELS: dict[str, ModelSpec] = {
    "sonnet": ModelSpec("sonnet", "anthropic", "claude-sonnet-5-5", True),
    "luna": ModelSpec("luna", "openai", "gpt-6-luna", True),
    "gemini": ModelSpec("gemini", "gemini", "gemini-3.8-flash", True),
    "jev": ModelSpec("jev", "jev", "jev-latest", False),
    # flagship models
    "opus": ModelSpec("opus", "anthropic", "claude-opus-5-5", True),
    "sol": ModelSpec("sol", "openai", "gpt-6.1-sol", True),
}

# Judge for open-ended answers.
JUDGE_MODEL = "jev-latest"

# Claude effort (thinking is always adaptive on Sonnet 5.5; None = API default "high").
CLAUDE_EFFORT: str | None = None
MAX_TOKENS = 16000

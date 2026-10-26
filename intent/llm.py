"""Two providers behind one function: extract(page_text) -> PageExtraction."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import TypeVar

from dotenv import load_dotenv
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

T = TypeVar("T", bound=BaseModel)

MODEL_A = "gpt-5.6-sol"       # extractor A (OpenAI)
MODEL_B = "claude-sonnet-5"    # extractor B (Anthropic)
MODEL_JUDGE = "claude-opus-5"  # adjudicator (Anthropic)


class Usage(dict):
    def add(self, model: str, inp: int, out: int) -> None:
        d = self.setdefault(model, {"input": 0, "output": 0, "calls": 0})
        d["input"] += inp; d["output"] += out; d["calls"] += 1


USAGE = Usage()


# --- OpenAI ------------------------------------------------------------------

_openai = None


def _oa():
    global _openai
    if _openai is None:
        from openai import OpenAI
        key = os.getenv("OA_OPENAI_KEY") or os.getenv("OPENAI_API_KEY")
        if not key:
            raise RuntimeError("OA_OPENAI_KEY missing in .env")
        _openai = OpenAI(api_key=key)
    return _openai


def call_openai(system: str, user: str, schema: type[T], model: str = MODEL_A) -> T:
    client = _oa()
    resp = client.chat.completions.parse(
        model=model,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        response_format=schema,
    )
    if resp.usage:
        USAGE.add(model, resp.usage.prompt_tokens, resp.usage.completion_tokens)
    msg = resp.choices[0].message
    if msg.parsed is None:
        raise RuntimeError(f"OpenAI returned no parsed output (refusal={msg.refusal!r})")
    return msg.parsed


# --- Anthropic ---------------------------------------------------------------

_anthropic = None


def _an():
    global _anthropic
    if _anthropic is None:
        import anthropic
        key = os.getenv("Anthropic_KEY") or os.getenv("ANTHROPIC_API_KEY")
        if not key:
            raise RuntimeError("Anthropic_KEY missing in .env")
        _anthropic = anthropic.Anthropic(api_key=key)
    return _anthropic


def call_anthropic(system: str, user: str, schema: type[T], model: str = MODEL_B,
                   max_tokens: int = 32000) -> T:
    client = _an()
    with client.messages.stream(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
        output_format=schema,
    ) as stream:
        resp = stream.get_final_message()
    USAGE.add(model, resp.usage.input_tokens, resp.usage.output_tokens)
    if resp.stop_reason == "refusal":
        raise RuntimeError(f"Anthropic refusal: {resp.stop_details}")
    parsed = getattr(resp, "parsed_output", None)
    if parsed is None:
        # fall back: parse the text block ourselves
        text = "".join(b.text for b in resp.content if b.type == "text")
        parsed = schema.model_validate_json(text)
    return parsed


def with_retry(fn, *args, tries: int = 3, **kw):
    last = None
    for i in range(tries):
        try:
            return fn(*args, **kw)
        except Exception as e:  # noqa: BLE001
            last = e
            wait = 5 * (i + 1)
            print(f"  [retry {i+1}/{tries}] {type(e).__name__}: {str(e)[:160]} -> sleep {wait}s")
            time.sleep(wait)
    raise last  # type: ignore[misc]


def save_usage(path: Path) -> None:
    path.write_text(json.dumps(USAGE, indent=2), encoding="utf-8")

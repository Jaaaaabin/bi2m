"""Thin provider clients. Each text provider returns (text, stop_reason, usage).

anthropic -> official SDK; openai -> official SDK; gemini -> REST (no SDK installed);
jev (TypeSafe) -> REST /v1/systemone, a decision model that answers choice / yes-no questions.
"""

from __future__ import annotations

import time

import httpx

from .config import MAX_TOKENS, env

# --------------------------------------------------------------------------- Anthropic

_anthropic = None


def _anthropic_client():
    global _anthropic
    if _anthropic is None:
        import anthropic
        _anthropic = anthropic.Anthropic(api_key=env("Anthropic_KEY", "ANTHROPIC_API_KEY"), max_retries=4)
    return _anthropic


def call_anthropic(model: str, system: str, user: str, effort: str | None = None) -> tuple[str, str, dict]:
    import anthropic
    kwargs = dict(model=model, max_tokens=MAX_TOKENS, system=system, messages=[{"role": "user", "content": user}])
    if effort:
        kwargs["output_config"] = {"effort": effort}
    # No server-side refusal fallback on purpose: a fallback would let another model answer a benchmark item.
    try:
        resp = _anthropic_client().messages.create(**kwargs)
    except anthropic.BadRequestError as e:
        raise RuntimeError(f"anthropic 400: {e.message}") from e
    text = "".join(b.text for b in resp.content if b.type == "text")
    usage = {"input": resp.usage.input_tokens, "output": resp.usage.output_tokens}
    return text, resp.stop_reason, usage


# --------------------------------------------------------------------------- OpenAI

_openai = None


def _openai_client():
    global _openai
    if _openai is None:
        from openai import OpenAI
        _openai = OpenAI(api_key=env("OA_OPENAI_KEY", "OPENAI_API_KEY"), max_retries=4)
    return _openai


def call_openai(model: str, system: str, user: str) -> tuple[str, str, dict]:
    resp = _openai_client().chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
    )
    choice = resp.choices[0]
    text = choice.message.content or ""
    stop = "refusal" if (not text and getattr(choice.message, "refusal", None)) else choice.finish_reason
    usage = {"input": resp.usage.prompt_tokens, "output": resp.usage.completion_tokens} if resp.usage else {}
    return text, stop, usage


# --------------------------------------------------------------------------- Gemini (REST)

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


def call_gemini(model: str, system: str, user: str, tries: int = 4) -> tuple[str, str, dict]:
    body = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": user}]}],
    }
    key = env("Gemini_KET", "GEMINI_API_KEY", "GOOGLE_API_KEY")
    last = None
    for i in range(tries):
        r = httpx.post(GEMINI_URL.format(model=model), params={"key": key}, json=body, timeout=180)
        if r.status_code == 200:
            d = r.json()
            cand = (d.get("candidates") or [{}])[0]
            text = "".join(p.get("text", "") for p in cand.get("content", {}).get("parts", []) if not p.get("thought"))
            um = d.get("usageMetadata", {})
            usage = {"input": um.get("promptTokenCount", 0), "output": um.get("candidatesTokenCount", 0) + um.get("thoughtsTokenCount", 0)}
            return text, cand.get("finishReason", ""), usage
        last = f"gemini {r.status_code}: {r.text[:300]}"
        if r.status_code in (429, 500, 502, 503, 504):
            time.sleep(4 * (i + 1)); continue
        break
    raise RuntimeError(last)


# --------------------------------------------------------------------------- JEV (TypeSafe)

JEV_URL = "https://api.typesafe.ai/v1/systemone"


def call_jev(model: str, state, questions: dict, tries: int = 4) -> tuple[dict, dict]:
    """POST /v1/systemone. questions: {name: {"type": "choice"|"noul"|"score", "instructions": ..., "criteria": ...}}.
    Returns (answers keyed by question name, usage)."""
    headers = {"Authorization": "Bearer " + env("JEV_KEY")}
    payload = {"model": model, "state": state, "questions": questions}
    last = None
    for i in range(tries):
        r = httpx.post(JEV_URL, headers=headers, json=payload, timeout=120)
        if r.status_code == 200:
            d = r.json()
            return d.get("answers", {}), d.get("usage") or {}
        last = f"jev {r.status_code}: {r.text[:400]}"
        if r.status_code in (429, 500, 502, 503, 504):
            time.sleep(4 * (i + 1)); continue
        break
    raise RuntimeError(last)

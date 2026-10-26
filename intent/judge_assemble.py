"""Turn a PageJudgement (index-based) into full intent records."""

from __future__ import annotations

import json
from typing import Any

from .schema import Intent, PageExtraction, PageJudgement


def _parse_value(v: str) -> Any:
    try:
        return json.loads(v)
    except Exception:  # noqa: BLE001
        return v


def _set_path(d: dict, path: str, value: Any) -> None:
    keys = path.split(".")
    cur = d
    for k in keys[:-1]:
        cur = cur.setdefault(k, {})
    cur[keys[-1]] = value


def assemble(j: PageJudgement, ea: PageExtraction, eb: PageExtraction) -> tuple[list[dict], list[dict]]:
    """Return (kept_records, problems). Each kept record = Intent dict + provenance fields."""
    kept: list[dict] = []
    problems: list[dict] = []
    for n, dec in enumerate(j.decisions):
        base_list = ea.intents if dec.prefer == "A" else eb.intents
        idx = dec.a_index if dec.prefer == "A" else dec.b_index
        if idx is None or idx >= len(base_list):
            problems.append({"decision": n, "error": "preferred index missing/out of range", "dec": dec.model_dump()})
            continue
        rec = base_list[idx].model_dump()
        for fx in dec.fixes:
            val = _parse_value(fx.value)
            if fx.path.endswith(("figure_ids", "paragraph_ids")) and isinstance(val, str):
                val = [v.strip() for v in val.split(",") if v.strip()]
            _set_path(rec, fx.path, val)
        try:
            rec = Intent.model_validate(rec).model_dump()
        except Exception as e:  # noqa: BLE001
            problems.append({"decision": n, "error": f"fix broke schema: {str(e)[:200]}", "dec": dec.model_dump()})
            rec = base_list[idx].model_dump()  # fall back to unfixed
        if dec.a_index is not None and dec.b_index is not None:
            prov = "both"
        elif dec.a_index is not None:
            prov = "A_only"
        else:
            prov = "B_only"
        rec["provenance"] = prov
        rec["judge_action"] = "merged" if prov == "both" else ("corrected" if dec.fixes else "accepted")
        rec["judge_note"] = dec.note
        rec["a_index"], rec["b_index"] = dec.a_index, dec.b_index
        kept.append(rec)
    return kept, problems


def reassemble_file(judged_path, ea: PageExtraction, eb: PageExtraction) -> dict:
    """Rebuild a judged/*.json from its stored raw_decisions (no LLM call)."""
    import json as _json
    from .schema import Decision
    old = _json.loads(judged_path.read_text(encoding="utf-8"))
    j = PageJudgement(page=old["page"], decisions=[Decision(**d) for d in old["raw_decisions"]],
                      rejected=[], notes=old.get("notes"))
    kept, problems = assemble(j, ea, eb)
    old["intents"], old["problems"] = kept, problems
    judged_path.write_text(_json.dumps(old, ensure_ascii=False, indent=2), encoding="utf-8")
    return old

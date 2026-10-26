"""Aggregate figures/*.json -> figure_intents.jsonl + figure_stats.json + review rows."""

from __future__ import annotations

import argparse
import glob
import json
from collections import Counter
from pathlib import Path

from .corpus import ROOT

OUT_DEFAULT = ROOT / "runs" / "intent_pilot_residential"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=OUT_DEFAULT)
    args = ap.parse_args()
    files = sorted(glob.glob(str(args.out / "figures" / "*.json")))
    rows, per_fig = [], []
    for f in files:
        d = json.loads(Path(f).read_text(encoding="utf-8"))
        per_fig.append({"figure_id": d["figure_id"], "page": d["page"], "n_new": len(d["intents"]),
                        "n_dims": len(d["dimensions_read"]), "n_covered": len(d["already_covered"])})
        for k, it in enumerate(d["intents"], 1):
            it = dict(it)
            it["id"] = f"{d['figure_id']}_fig_{k:02d}"
            it["page"] = d["page"]; it["figure_id"] = d["figure_id"]; it["image"] = d["image"]
            it["caption"] = d["caption"]; it["dimensions_read"] = d["dimensions_read"]
            # quote check: caption or a legible dimension string
            q = it["source"]["quote"].strip().lower()
            it["quote_verified"] = ("caption" if q and q in (d["caption"] or "").lower()
                                    else "dimension" if any(q in x.lower() or x.lower() in q for x in d["dimensions_read"])
                                    else "unverified")
            rows.append(it)
    (args.out / "figure_intents.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")
    n = len(rows) or 1
    stats = {
        "figures_processed": len(files),
        "figures_with_new_intents": sum(1 for p in per_fig if p["n_new"]),
        "figure_intents_total": len(rows),
        "mean_new_per_figure": round(len(rows) / max(1, len(files)), 2),
        "by_kind": dict(Counter(r["kind"] for r in rows)),
        "by_checkable": dict(Counter(r["ifc_checkable"] for r in rows)),
        "by_concept": dict(Counter(r["rationale"]["concept"] for r in rows).most_common()),
        "quote_verified": dict(Counter(r["quote_verified"] for r in rows)),
        "with_numeric_value": sum(1 for r in rows if r["prescription"]["value_min"] is not None),
        "per_figure": per_fig,
    }
    (args.out / "figure_stats.json").write_text(json.dumps(stats, indent=2, ensure_ascii=False), encoding="utf-8")

    lines = ["# Figure-pass review sample", "", f"All {len(rows)} figure-derived intents. Verdict: ok / partial / wrong / not_an_intent", "",
             "| # | id | image | kind | statement | quote | checkable | Verdict | Note |", "|---|---|---|---|---|---|---|---|---|"]
    for i, r in enumerate(rows, 1):
        st = r["statement"].replace("|", "\\|"); q = r["source"]["quote"].replace("|", "\\|")
        lines.append(f"| {i} | `{r['id']}` | [{r['figure_id']}]({r['image']}) | {r['kind']}/{r['modality']} | {st} | “{q}” ({r['quote_verified']}) | {r['ifc_checkable']} |  |  |")
    (args.out / "review_figures.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in stats.items() if k != "per_figure"}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

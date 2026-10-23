"""Line the live Neufert rules up against the ground truth of the QA pack
(neufert_validation_pack.json: the Neufert QA Workbench's advanced cases).

Read-only. For every benchmark project that is on disk as an IFC4 model, the
13 Neufert categories run as the CLI runs them (AccessGraph + engine.run_topic);
then each advanced-QA case whose cards include a live rule is printed with
the records those rules produced on that model, and the numbers the case's
evidence quotes (lengths, areas, counts; coordinate ranges dropped) are
looked up among the values the records carry. "Numbers found" is the measurement-layer check:
a figure the ground truth relies on that none of our records measured is a
tool gap or a tool error. The verdict comparison (does the record's outcome
agree with the case's answer?) is read off the report by hand and recorded
separately; this script never judges prose.

    uv run python scripts/validate_neufert.py            # report to research/neufert/validation_<date>.md
    uv run python scripts/validate_neufert.py --stdout   # the report on stdout
    uv run python scripts/validate_neufert.py --only fzk_house,fantasy_hotel_1

The benchmark files are matched to the pack's projects by their element
counts (Space/Door/Window/Stair/Railing); a mismatch is reported, never
silently scored. Project ids, paths and the match are data in BENCHMARKS.
"""

import argparse
import datetime
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

import ifcopenshell  # noqa: E402

from recognition.access_graph import AccessGraph  # noqa: E402
from recognition.neufert.engine import run_topic  # noqa: E402
from recognition.neufert.rules import load_rules, status_kind  # noqa: E402
from recognition.neufert.topics import TOPICS  # noqa: E402
from local_env import env_path  # noqa: E402

PACK = REPO_ROOT / "neufert_validation_pack.json"
OUT_DIR = REPO_ROOT / "research" / "neufert"

# project id -> IFC4 file under BI2M_IFC_ROOT (matched on 2026-10-20 by element counts,
# re-checked here on every run). IFC2X3 projects (duplex, 4351) and the two
# not on disk (samuel_macalister_sample_house, ac20's IFC4 export) are absent.
BENCHMARKS = {
    "fantasy_residential_building_1": "tumgni_all/0263.ifc",
    "fantasy_hotel_1": "tumgni_all/0251.ifc",
    "fantasy_office_building_1": "tumgni_all/0281.ifc",
    "fantasy_office_building_2": "tumgni_all/0286.ifc",
    "fantasy_office_building_3": "tumgni_all/0290.ifc",
    "fzk_house": "openrepo/20201030AC20-FZK-Haus.ifc",
    # a later export of the same building (70 doors where the pack counts 64)
    "digital_hub": "openrepo/20201208DigitalHub_ARC.ifc",
}


def benchmark_path(relative):
    """A BENCHMARKS entry under BI2M_IFC_ROOT, the folder holding the corpora."""
    root = env_path("BI2M_IFC_ROOT")
    if root is None:
        sys.exit("Set BI2M_IFC_ROOT (in .env at the repository root, see .env.example)")
    return str(root / relative)
COUNT_CLASSES = ("Space", "Door", "Window", "Stair", "Railing")
# quoted figures: "0.20 m", "20 cm", "910 mm", "13.37 m²", "17 risers", "1.135 × 2.43 m"
NUMBER = re.compile(r"(?<![\w.…–\-])(\d+(?:[.,]\d+)?)\s*(m²|m2|mm|cm|m)(?![\w])")
# "x 6.72–8.31, y 2.24…3.95 m": coordinate ranges name positions, not measures
COORDINATE = re.compile(r"\b[xyz]\s*[≈=]?\s*[−\-]?\d+(?:[.,]\d+)?\s*(?:[…–\-]+\s*[−\-]?\d+(?:[.,]\d+)?\s*)*(?:m\b)?")
COUNT = re.compile(r"(?<![\w.])(\d+)\s+(?:x\s+|×\s+)?(?:Ifc\w+|risers?|steps?|flats?|windows?|doors?|stairs?|storeys?|floors?)")
TO_METRES = {"m": 1.0, "cm": 0.01, "mm": 0.001, "m²": 1.0, "m2": 1.0}
REL_TOL = 0.006   # 0.6 %: the pack rounds to 2-3 decimals
ABS_TOL = 0.006


def quoted_numbers(texts):
    """{(value, kind)} quoted in the texts; lengths and areas in metres, counts as ints."""
    found = set()
    for text in texts:
        text = COORDINATE.sub(" ", text)
        for raw, unit in NUMBER.findall(text):
            value = float(raw.replace(",", ".")) * TO_METRES[unit]
            found.add((round(value, 4), "area" if unit in ("m²", "m2") else "length"))
        for raw in COUNT.findall(text):
            found.add((int(raw), "count"))
    return found


def metrics_of(record):
    """The record's metrics (writers.py puts them under evidence)."""
    return (record.get("evidence") or {}).get("metrics") or {}


def record_values(record):
    """Every number a record carries: min/max/mean, the template value, the
    per-member values, the member count."""
    metrics = metrics_of(record)
    values = set()
    for key in ("min", "max", "mean"):
        if isinstance(metrics.get(key), (int, float)):
            values.add(float(metrics[key]))
    if metrics.get("templateValue"):
        values.add(float(metrics["templateValue"]["value"]))
    for value in (metrics.get("values") or {}).values():
        if isinstance(value, (int, float)):
            values.add(float(value))
    counts = {int(metrics.get("count") or 0)}
    for term in (metrics.get("aggregate") or {}).values() if isinstance(metrics.get("aggregate"), dict) else ():
        if isinstance(term, (int, float)):
            values.add(float(term))
    return values, counts


def close(a, b):
    return abs(a - b) <= max(ABS_TOL, REL_TOL * abs(b))


def matched(quoted, records):
    """(found, missing) among the quoted numbers against the records' values."""
    values, counts = set(), set()
    for record in records:
        v, c = record_values(record)
        values |= v
        counts |= c
    found, missing = [], []
    for value, kind in sorted(quoted):
        hit = (value in counts) if kind == "count" else any(close(candidate, value) for candidate in values)
        (found if hit else missing).append((value, kind))
    return found, missing


def run_model(path, file_key):
    model = ifcopenshell.open(path)
    graph = AccessGraph(model) if model.by_type("IfcSpace") and model.by_type("IfcDoor") else None
    records = []
    for suffix, _topic, _level, _classes in TOPICS:
        records.extend(run_topic(suffix, model, file_key, graph=graph))
    return model, records


def counts_match(model, project):
    got = {cls: len(model.by_type("Ifc" + cls)) for cls in COUNT_CLASSES}
    expected = {cls: project["counts"].get(cls) for cls in COUNT_CLASSES}
    diff = {cls: (got[cls], expected[cls]) for cls in COUNT_CLASSES if got[cls] != expected[cls]}
    return got, diff


def outcome_of(record):
    return record["type"].rsplit("_", 1)[-1]


def fmt_record(record):
    metrics = metrics_of(record)
    text = f"- [{outcome_of(record)}] {(record.get('evidence') or {}).get('summary', '')}"
    if metrics.get("values"):
        shown = list(metrics["values"].items())[:6]
        text += "\n  values: " + ", ".join(f"{guid}={value}" for guid, value in shown) + (" ..." if len(metrics["values"]) > 6 else "")
    return text


def scenario_lines(case, kids, by_kid, rules):
    """The scenario score of one case (2026-10-20): per card, whether a
    scenario record exists on the model (recognised), its member count, and
    whether the GlobalIds the evidence quotes are among its members."""
    lines, score = [], Counter()
    quoted = set(GUID.findall(" ".join(case.get("evidence", []))))
    for kid in kids:
        rule = rules.get(kid)
        if rule is None:
            continue
        found = [r for r in by_kid.get(kid, []) if r["type"].endswith("_scenario")]
        if rule.get("scenario") is None:
            lines.append(f"- {kid} scenario: not determinable ({rule.get('scenario_reason')})")
            score["not_determinable"] += 1
            continue
        if not found:
            lines.append(f"- {kid} scenario: absent, nothing found on this model (selector {rule['scenario']})")
            score["absent"] += 1
            continue
        members = {m["guid"] for m in found[0]["members"]}
        hits = quoted & members
        lines.append(f"- {kid} scenario: recognised, {len(members)} element(s)"
                     + (f"; evidence GUIDs among members {len(hits)} of {len(quoted)}" if quoted else "")
                     + f"; {(found[0].get('evidence') or {}).get('summary', '')[:220]}")
        score["recognised"] += 1
    return lines, score


GUID = re.compile(r"\b[0-9A-Za-z_$]{22}\b")


def report(pack, only=None):
    rules = load_rules()
    live = {kid for kid, rule in rules.items() if status_kind(rule["status"]) != "deferred"}
    projects = {project["id"]: project for project in pack["projects"]}
    lines = [f"# Neufert validation against the QA pack ({datetime.date.today()})", "",
             f"Pack: {pack['meta'].get('source', '')} read {pack['meta'].get('read_on', '')}; "
             f"{len(live)} live rules; {len(pack['advanced_qa'])} advanced cases.", ""]
    totals = Counter()
    per_rule = defaultdict(Counter)
    for project_id, relative in BENCHMARKS.items():
        path = benchmark_path(relative)
        if only and project_id not in only:
            continue
        project = projects[project_id]
        cases = [case for case in pack["advanced_qa"] if case["project"] == project_id and set(case["cards"]) & set(rules)]
        lines.append(f"## {project_id} ({project['type']}; {project['schema']}; {Path(path).name})")
        if not Path(path).exists():
            lines += ["", f"MISSING on disk: {path}", ""]
            totals["models_missing"] += 1
            continue
        model, records = run_model(path, project_id)
        got, diff = counts_match(model, project)
        lines.append("")
        lines.append(f"schema {model.schema}; counts {got}" + (f"; DIFFERS from the pack on {diff}" if diff else "; counts match the pack"))
        by_kid = defaultdict(list)
        for record in records:
            by_kid[metrics_of(record).get("kid")].append(record)
        lines.append(f"{len(records)} Neufert records; live rules with records: {sorted(k for k in by_kid if k)}")
        deferred_here = Counter()
        for case in pack["advanced_qa"]:
            if case["project"] == project_id:
                for kid in case["cards"]:
                    if kid in rules and kid not in live:
                        deferred_here[kid] += 1
        if deferred_here:
            lines.append("deferred cards the project's cases also test: " + ", ".join(f"{k} x{n}" for k, n in sorted(deferred_here.items())))
        lines.append(f"{len(cases)} advanced cases touch a card; scenario records on this model: "
                     + ", ".join(sorted((k for k in by_kid if k and any(r["type"].endswith("_scenario") for r in by_kid[k])), key=lambda k: int(k[1:]))))
        totals["models"] += 1
        for case in cases:
            kids = sorted(k for k in case["cards"] if k in live)
            all_kids = sorted(k for k in case["cards"] if k in rules)
            lines += ["", f"### {case['hid']} [{case['question_type']}, {case['pairing']}] cards {case['cards']} (live: {kids})", "",
                      f"Q: {case['question']}", "", f"A: {case['answer']}", ""]
            scen_lines, scen_score = scenario_lines(case, all_kids, by_kid, rules)
            totals["scenario_cases"] += 1
            for key, n in scen_score.items():
                totals["scenario_" + key] += n
            lines.append("Scenario recognition:")
            lines += scen_lines
            lines.append("Evidence:")
            lines += [f"- {e}" for e in case.get("evidence", [])]
            lines.append("Rubric:")
            lines += [f"- {r}" for r in case.get("rubric", [])]
            quoted = quoted_numbers(case.get("evidence", []))
            case_records = [record for kid in kids for record in by_kid.get(kid, []) if not record["type"].endswith("_scenario")]
            found, missing = matched(quoted, case_records)
            totals["cases"] += 1
            totals["numbers"] += len(quoted)
            totals["numbers_found"] += len(found)
            for kid in kids:
                verdicts = [r for r in by_kid.get(kid, []) if not r["type"].endswith("_scenario")]
                per_rule[kid]["cases"] += 1
                per_rule[kid]["records"] += len(verdicts)
                if not verdicts:
                    per_rule[kid]["no_record"] += 1
            lines.append("")
            lines.append(f"Numbers quoted: {len(quoted)}; found among our values: {len(found)}; missing: "
                         + (", ".join(f"{v} ({k})" for v, k in missing) if missing else "none"))
            lines.append("")
            lines.append("Our records:")
            for kid in kids:
                if not by_kid.get(kid):
                    lines.append(f"- {kid}: NO RECORD on this model (status: {rules[kid]['status']})")
                for record in by_kid.get(kid, []):
                    if not record["type"].endswith("_scenario"):
                        lines.append(fmt_record(record))
        lines.append("")
    lines += ["## Summary", "",
              f"models run {totals['models']}, missing {totals['models_missing']}; cases {totals['cases']}; "
              f"quoted numbers {totals['numbers']}, found {totals['numbers_found']}", "",
              f"scenario recognition over {totals['scenario_cases']} cases and their cards: recognised {totals['scenario_recognised']}, "
              f"absent {totals["scenario_absent"]}, not determinable {totals['scenario_not_determinable']}", "",
              "| rule | cases | records | cases without a record |", "|---|---:|---:|---:|"]
    for kid in sorted(per_rule, key=lambda k: int(k[1:])):
        c = per_rule[kid]
        lines.append(f"| {kid} | {c['cases']} | {c['records']} | {c['no_record']} |")
    return "\n".join(lines) + "\n", totals


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--stdout", action="store_true", help="print the report instead of writing it")
    parser.add_argument("--only", default="", help="comma list of project ids")
    args = parser.parse_args()
    pack = json.loads(PACK.read_text(encoding="utf-8"))
    only = {p for p in args.only.split(",") if p} or None
    text, totals = report(pack, only)
    if args.stdout:
        print(text)
    else:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        out = OUT_DIR / f"validation_{datetime.date.today()}.md"
        out.write_text(text, encoding="utf-8")
        print(f"wrote {out}")
    print(f"models {totals['models']} (missing {totals['models_missing']}), cases {totals['cases']}, "
          f"quoted numbers found {totals['numbers_found']} of {totals['numbers']}; scenario cards recognised "
          f"{totals['scenario_recognised']}, absent {totals["scenario_absent"]}, not determinable {totals['scenario_not_determinable']}")


if __name__ == "__main__":
    main()

"""The two config layers of the Neufert categories, from the cards.

    uv run python scripts/neufert_bindings.py cards neufert_logic.md cards.json
    uv run python scripts/neufert_bindings.py bindings cards.json [config/neufert/bindings.yaml]

`cards` parses every task card of neufert_logic.md (title, topic, rule
type, priority, level, primary entities, check types, logic, applies,
notes, the YAML block, accessors, project inputs) into JSON. `bindings`
writes config/neufert/bindings.yaml from that JSON: every rule deferred
with a reason and `needs` tags derived from it, then the hand-written
BOUND entries applied on top (the bound, partial and widened rules and
their selectors, measures and checks). The YAML threshold files under
config/neufert/rules/ are the cards' blocks verbatim and are not written
here. Re-running `bindings` reproduces the committed file; a new binding
is an entry in BOUND, never an edit to the generated file.
"""

import copy
import json
import os
import re
import sys

import yaml

CONFIG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "config", "neufert")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from recognition.neufert.families import BUILT as BUILT_FAMILIES  # noqa: E402 - a family:<name> tag only for a stub family


def parse_cards(text):
    cards = re.split(r'\n(?=### K\d+ · )', text)
    sections = [(m.start(), m.group(1)) for m in re.finditer(r'^## \d+\. (.*?) \(\d+\)', text, re.M)]
    out = []
    offset = 0
    for c in cards[1:]:
        offset = text.find(c, offset)
        section = next((name for pos, name in reversed(sections) if pos < offset), None)
        m = re.match(r'### (K\d+) · (.*)', c); kid, title = m.group(1), m.group(2).strip()
        def row(name):
            r = re.search(r'\| ' + re.escape(name) + r' \| (.*?) \|\n', c); return r.group(1).strip() if r else None
        rtl = row('Rule type · priority · LOD') or ''
        parts = [p.strip() for p in rtl.split('·')]
        y = re.search(r'```yaml\n(.*?)```', c, re.S)
        logic = re.search(r'#### ② Scenario logic\n\n\*\*Check types\*\* (.*?)\n\n```text\n(.*?)```', c, re.S)
        applies = re.search(r'\*\*Applies when\.\*\* (.*?)\n', c)
        notes = re.search(r'\*\*Notes\.\*\* (.*?)\n', c)
        exempt = re.search(r'\*\*Exemptions and variants\.\*\* (.*?)\n', c)
        bench = re.search(r'\*\*Benchmark models with the special data:\*\* (.*?)\n', c)
        prim = re.search(r'\*\*Primary entities\*\* (.*?)\n', c)
        req = re.search(r'\*\*Requirement\.\*\* (.*?)\n', c)
        acc = re.findall(r'\| ([^|\n]*?) \| `([a-z_.]+\([^)]*\))` \|', c)
        out.append(dict(kid=kid, title=title, section=section, phase=(row('Phase') or '')[:1], topic=row('Topic'),
            rule_type=parts[0] if parts else None, priority=parts[1] if len(parts)>1 else None,
            lod=parts[2] if len(parts)>2 else None, depends=row('Depends on (facts)'), defines=row('Defines fact'),
            primary=[p.strip('` ') for p in prim.group(1).rstrip('.').split(',')] if prim else [],
            check_types=re.findall(r'`([A-Z]+)`', logic.group(1)) if logic else [],
            logic=logic.group(2).strip() if logic else None, applies=applies.group(1) if applies else None,
            notes=notes.group(1) if notes else None, exemptions=exempt.group(1) if exempt else None,
            benchmark=bench.group(1) if bench else None, requirement=req.group(1) if req else None,
            yaml=y.group(1) if y else None, accessors=[a[1] for a in acc],
            project_inputs=re.findall(r'project_input\("([a-z_]+)"\)', c)))
    return out


SECTION_LEVEL = {"Site & Building": "site_building", "Storey": "storey", "Zone": "zone", "Space": "space", "Element": "element"}


def bindings_text(cards, bound_path, reasons_path, families_path):
    cards_by_kid = {c["kid"]: c for c in cards}
    TOPIC_ID = {
     "Site and massing": "site", "Habitable-room standards and area calculation": "rooms",
     "Housing: layout and entrance": "housing", "Offices": "offices", "High-rise buildings": "highrise",
     "Stairs, ramps, lifts and railings": "stairs", "Accessibility": "accessibility",
     "Escape and fire protection": "escape", "Housing: bedrooms, bathrooms and storage": "bedrooms",
     "Daylight, sunlight, ventilation and windows": "daylight", "Doors": "doors",
     "Building envelope and thermal insulation": "envelope", "Walls and construction": "walls"}
    FAMILY = {kid: fam for fam, kids in (yaml.safe_load(open(families_path, encoding="utf-8")) or {}).items() for kid in kids}
    REASON = yaml.safe_load(open(reasons_path, encoding="utf-8")) or {}
    NEEDS = {
     "dwelling": "fact:dwelling_units", "dwellings": "fact:dwelling_units", "units": "fact:dwelling_units",
     "essential": "fact:essential_stairs", "is_highrise": "fact:is_highrise", "workstation": "fact:workstations",
     "seats": "fact:workstations", "persons": "fact:persons", "lifts": "fact:lifts", "lift": "fact:lifts",
     "public": "fact:public_building", "barrier-free": "fact:public_building", "building use": "fact:building_use",
     "office-building": "fact:building_use", "door -> reached": "select:door_rooms", "door swing": "geom:door_swing",
     "furniture": "geom:furniture_footprints", "free-square": "geom:free_square", "square": "geom:free_square",
     "geometry": "geom:element_geometry", "landing": "geom:flight_landing", "handrail": "geom:railing_sides",
     "railing": "geom:railing_sides", "escape corridors": "fact:escape_corridors", "green-roof": "fact:green_roof",
     "wall ratings": "fact:wall_fire_rating", "concept": "vocab:assembly_hall", "grid": "fact:declared_grid",
     "sightline": "geom:sightline", "project input": "input:project", "university": "fact:building_use",
     "informational": "family:classify", "raised floor": "geom:element_geometry",
    }
    def needs_for(reason, fam, project_inputs, explicit=None):
        if explicit:
            return list(explicit)
        tags = []
        if fam not in BUILT_FAMILIES:
            tags.append(f"family:{fam}")
        for key, tag in NEEDS.items():
            if key in reason and tag not in tags:
                tags.append(tag)
        for inp in project_inputs:
            tags.append(f"input:{inp}")
        return tags
    out = {}
    for c in cards:
        kid = c['kid']; fam = FAMILY.get(kid, "measure")
        entry = REASON.get(kid)
        explicit = None
        if isinstance(entry, dict):
            reason, explicit = entry.get("reason", "not bound yet"), entry.get("needs")
        elif fam not in BUILT_FAMILIES:
            reason = entry or f"family '{fam}' not built"
        else:
            reason = entry or "not bound yet"
        if c['project_inputs'] and kid not in REASON:
            reason = "project input (" + ", ".join(c['project_inputs']) + ")"
        out[kid] = {
            "title": c['title'], "topic": TOPIC_ID[c['topic']], "family": fam,
            "rule_type": c['rule_type'], "priority": c['priority'], "level": None,
            "status": f"deferred: {reason}", "scope": "storey",
            "needs": needs_for(reason, fam, c['project_inputs'], explicit),
        }
    # levels from the plan's sections
    for kid in out: out[kid]["level"] = SECTION_LEVEL.get(cards_by_kid[kid]["section"], "space")

    # ---- bound and partial bindings ----
    bound = yaml.safe_load(open(bound_path, encoding="utf-8")) or {}
    for kid, b in bound.items():
        if kid not in out:
            raise SystemExit(f"{bound_path}: {kid} is not a card")
        out[kid].update(b)
        out[kid].pop("needs", None)
    # ---- the scenario layer (2026-10-20): the card's "applies when" as text, and the selector that finds the
    # situation: scenarios.yaml, else an active rule's `applies`, else its `select`; null + reason when the gate
    # itself is the missing fact. A deferred rule keeps its `needs`, which the scenario record quotes.
    scenarios = yaml.safe_load(open(os.path.join(os.path.dirname(bound_path), "scenarios.yaml"), encoding="utf-8")) or {}
    unknown = sorted(set(scenarios) - set(out))
    if unknown:
        raise SystemExit(f"scenarios.yaml: not cards: {unknown}")
    for kid in out:
        out[kid]["applies_text"] = cards_by_kid[kid].get("applies")
        entry = scenarios.get(kid)
        if kid in scenarios:
            entry = entry or {}
            if "scenario" in entry:
                out[kid]["scenario"] = entry["scenario"]
            elif not out[kid]["status"].startswith("deferred"):
                out[kid]["scenario"] = copy.deepcopy(out[kid].get("applies") or out[kid].get("select") or None)
            else:
                out[kid]["scenario"] = None
            if out[kid]["scenario"] is None:
                out[kid]["scenario_reason"] = entry.get("reason") or "not determinable"
            elif entry.get("related"):
                # the `related` facet on the scenario (a list scenario takes it on its first part)
                target = out[kid]["scenario"][0] if isinstance(out[kid]["scenario"], list) else out[kid]["scenario"]
                target["related"] = entry["related"]
            if entry.get("note"):
                out[kid]["scenario_note"] = entry["note"]
        elif out[kid]["status"].startswith("deferred"):
            out[kid]["scenario"] = None
            out[kid]["scenario_reason"] = "no scenario selector written yet"
        else:
            out[kid]["scenario"] = copy.deepcopy(out[kid].get("applies") or out[kid].get("select") or None)  # a copy: no YAML anchors
            if out[kid]["scenario"] is None:
                out[kid]["scenario_reason"] = "the rule selects per check"
    order = sorted(out, key=lambda k: int(k[1:]))
    text = "# bi2m bindings for the Neufert K-rules (see docs/detectors.md \"The 13 Neufert categories\").\n" \
           "# One entry per KID. Thresholds live in rules/<KID>.yaml (verbatim from neufert_logic.md); this file says\n" \
           "# which Topic and family run the rule, what it selects, which measures it reads and against which params.\n" \
           "# status: bound | partial: <what is skipped> (info only) | deferred: <reason>. Generated 2026-10-18 from the\n" \
           "# cards, then hand-maintained. `scenario` (2026-10-20): the selector that finds the situation the card addresses\n" \
           "# (scenarios.yaml, else applies, else select); `scenario_reason` when there is none.\n\n"
    for kid in order:
        text += yaml.safe_dump({kid: out[kid]}, sort_keys=False, allow_unicode=True, width=120) + "\n"
    return text


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 1
    command = sys.argv[1]
    if command == "cards":
        cards = parse_cards(open(sys.argv[2], encoding="utf-8").read())
        json.dump(cards, open(sys.argv[3], "w"), indent=1, ensure_ascii=False)
        print(len(cards), "cards")
        return 0
    if command == "bindings":
        cards = json.load(open(sys.argv[2]))
        target = sys.argv[3] if len(sys.argv) > 3 else os.path.join(CONFIG_DIR, "bindings.yaml")
        config = CONFIG_DIR
        open(target, "w", encoding="utf-8").write(bindings_text(
            cards, os.path.join(config, "bound.yaml"), os.path.join(config, "deferred_reasons.yaml"), os.path.join(config, "families.yaml")))
        print("wrote", target)
        return 0
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main())

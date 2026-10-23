"""Self-checks for the intent-category registry after the 2026-10-08
reorganization:
the `level` axis, the four merged categories and their tombstones, the
manifest, the shard writer's tombstone rule, and - on data/example_autcon.ifc
with its cached extraction - that each merged category's records are its
parts' records, id for id. The window comparison is vacuous on that model
(no IfcWindow, so both sides are empty); the window merge was checked by a
separate regeneration count on models that have windows.

    uv run python scripts/verify_registry.py

Writes only into temporary folders. A missing fixture is a FAIL, not a
skip. Exit code 0 when every check passes, 1 otherwise.
"""

import importlib
import inspect
import json
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

import ifcopenshell  # noqa: E402

from file_identity import resolve_file_identity  # noqa: E402
from recognition.intent import make_intent  # noqa: E402
from recognition.registry import CATEGORIES  # noqa: E402
from recognition.writers import (  # noqa: E402
    recomputed_with_tombstones,
    shard_path,
    write_category_manifest,
    write_intent_shard,
)

LEVELS = ("room", "storey", "building")
# What each retired category wrote and read, as of its last run (registry.py
# before 2026-10-08). The merged categories must declare exactly these types
# and at least these extraction keys.
FORMER_TYPES = {
    "space_access": ["access_reachable_group", "access_isolated_space",
                     "access_door_anomaly", "access_storey_without_rooms"],
    "space_syntax": ["syntax_integration_core", "syntax_ring"],
    "circulation_horizontal": ["circulation_horizontal_space"],
    "egress_reachability": ["egress_reachable", "egress_unreachable"],
    "egress_access": ["egress_external_access"],
    "fire_compartments": ["fire_compartment"],
    "window_alignment": ["window_vertical_alignment", "window_bay_interrupted"],
    "lighting_clusters": ["window_lighting_cluster"],
    "unit_typology": ["unit_type_recurrence"],
    "unit_layout": ["unit_layout_recurrence"],
    "grid_claims": ["grid_line_consistency", "grid_line_gap"],
}
FORMER_EXTRACTION = {"lighting_clusters": ("info_envelope_shapes",)}  # every other part: ()
# Types a merged category added after the merge (its own rules, not a part's).
OWN_TYPES = {"egress_fire": ["fire_compartment_singletons"]}  # 2026-10-08, every door rated
MERGED = {
    "room_access": ("space_access", "space_syntax", "circulation_horizontal"),
    "egress_fire": ("egress_reachability", "egress_access", "fire_compartments"),
    "window_patterns": ("window_alignment", "lighting_clusters"),
    "repeated_units": ("unit_typology", "unit_layout"),
}
EXAMPLE = REPO_ROOT / "data" / "example_autcon.ifc"

RESULTS = []


def check(name, condition, detail=""):
    RESULTS.append((name, bool(condition), detail))


def comparable(record):
    """A record without the two fields a merge legitimately changes."""
    out = json.loads(json.dumps(record, default=str))
    out["provenance"].pop("detector", None)
    out["provenance"].pop("generatedAt", None)
    return out


def main():
    live = {cid: info for cid, info in CATEGORIES.items() if not info.get("retired")}
    tombstones = {cid: info for cid, info in CATEGORIES.items() if info.get("retired")}
    # The Neufert Topic categories (2026-10-18) carry `section`; the level
    # counts and the "merged come last" order below are about the level axis
    # and skip them. Their own block is further down.
    sectioned = {cid: info for cid, info in live.items() if info.get("section")}
    levelled = {cid: info for cid, info in live.items() if not info.get("section")}
    unsectioned_order = [cid for cid in CATEGORIES if not CATEGORIES[cid].get("section")]

    # ---- the level axis ----
    bad_level = [cid for cid, info in CATEGORIES.items() if info.get("level") not in LEVELS]
    check("every entry has a level: room, storey or building", not bad_level, bad_level)
    check("no entry carries the retired scope field", not any("scope" in info for info in CATEGORIES.values()))
    per_level = {lvl: sorted(cid for cid, info in levelled.items() if info["level"] == lvl) for lvl in LEVELS}
    check("17 live categories: 1 room, 8 storey, 8 building",
          [len(per_level[lvl]) for lvl in LEVELS] == [1, 8, 8], {k: len(v) for k, v in per_level.items()})
    check("11 tombstones", len(tombstones) == 11, sorted(tombstones))
    check("the four merged categories come last among the level categories, in order",
          unsectioned_order[-4:] == ["room_access", "egress_fire", "window_patterns", "repeated_units"], unsectioned_order[-4:])
    # ---- the Neufert section (2026-10-18) ----
    from recognition.neufert.topics import TOPICS, category_id as neufert_id, intent_types as neufert_types
    neufert_ids = [neufert_id(t[0]) for t in TOPICS]
    check("the 13 Neufert categories come last, in topic order", list(CATEGORIES)[-13:] == neufert_ids, list(CATEGORIES)[-13:])
    check("every Neufert entry: section neufert, a level, five outcome types, graph-taking detector, no hard signals",
          all(info.get("section") == "neufert" and info["level"] in LEVELS and info["intent_types"] == neufert_types(cid[len("neufert_"):])
              and "graph" in inspect.signature(info["detector"]).parameters and info["signals"] == ()
              for cid, info in sectioned.items()) and set(sectioned) == set(neufert_ids))
    from recognition.neufert.families import BUILT
    from recognition.neufert.rules import load_rules, status_kind
    try:
        rules = load_rules()
        check("config/neufert loads: 122 rules, every binding validated", len(rules) == 122, len(rules))
        check("every rule's topic is a registered Topic", all(neufert_id(r["topic"]) in sectioned for r in rules.values()))
        check("every bound or partial rule has checks and a built family",
              all(r["checks"] and r["family"] in BUILT for r in rules.values() if status_kind(r["status"]) != "deferred"))
    except Exception as e:  # noqa: BLE001
        check("config/neufert loads", False, f"{type(e).__name__}: {e}")

    # ---- merged categories and their parts ----
    for cid, parts in MERGED.items():
        info = CATEGORIES[cid]
        union = [t for part in parts for t in FORMER_TYPES[part]] + OWN_TYPES.get(cid, [])
        check(f"{cid}: types are exactly its parts' former types plus its own additions", sorted(info["intent_types"]) == sorted(union),
              (info["intent_types"], union))
        need = {k for part in parts for k in FORMER_EXTRACTION.get(part, ())}
        check(f"{cid}: extraction keys cover its parts' former keys", need <= set(info["extraction_keys"]),
              (need, info["extraction_keys"]))
        check(f"{cid}: every part is a tombstone naming it as successor",
              all(CATEGORIES[p].get("retired") == cid for p in parts), [CATEGORIES[p].get("retired") for p in parts])
        check(f"{cid}: level is its parts' level", all(CATEGORIES[p]["level"] == info["level"] for p in parts))
        check(f"{cid}: detect() takes graph=, so the shared door graph reaches its parts",
              "graph" in inspect.signature(info["detector"]).parameters)
    check("alignment carries grid_claims' former types", set(FORMER_TYPES["grid_claims"]) <= set(CATEGORIES["alignment"]["intent_types"]))
    check("grid_claims is a tombstone of alignment", CATEGORIES["grid_claims"].get("retired") == "alignment")

    # ---- tombstones ----
    for cid, info in tombstones.items():
        successor = info["retired"]
        check(f"{cid}: no types, no inputs, no signals, a live successor, a detector that returns nothing",
              info["intent_types"] == [] and tuple(info["extraction_keys"]) == () and tuple(info["signals"]) == ()
              and successor in live and info["detector"](None, None, "k") == [],
              (info["intent_types"], info["extraction_keys"], info["signals"], successor))
    types_of = {}
    for cid, info in live.items():
        for t in info["intent_types"]:
            types_of.setdefault(t, []).append(cid)
    check("no record type belongs to two live categories", all(len(v) == 1 for v in types_of.values()),
          {t: v for t, v in types_of.items() if len(v) > 1})
    from recognition.preflight import parse_signal
    unparsable = []
    for cid, info in CATEGORIES.items():
        for sig in tuple(info.get("signals", ())) + tuple(info.get("soft_signals", ())):
            try:
                parse_signal(sig)
            except ValueError as e:
                unparsable.append((cid, sig, str(e)))
    check("every signals and soft_signals string parses", not unparsable, unparsable)

    # ---- the manifest ----
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "intent_categories.json"
        write_category_manifest(str(path), CATEGORIES)
        manifest = json.loads(path.read_text())
    check("manifest keeps registry order (the colour contract)", [m["id"] for m in manifest] == list(CATEGORIES))
    check("manifest: level on every entry, retired on tombstones only, section on the Neufert entries only, no scope",
          all(m.get("level") in LEVELS for m in manifest)
          and all(("retired" in m) == (m["id"] in tombstones) for m in manifest)
          and all(("section" in m) == (m["id"] in sectioned) for m in manifest)
          and not any("scope" in m for m in manifest))

    # ---- the writer's tombstone rule (spec §4, found in review) ----
    completed = recomputed_with_tombstones(CATEGORIES, {"room_access"})
    check("a live-only recompute also retires the successor's tombstones",
          {"room_access", "space_access", "space_syntax", "circulation_horizontal"} <= completed
          and "egress_reachability" not in completed, sorted(completed))
    failed = recomputed_with_tombstones(CATEGORIES, {"space_access"}, failed={"room_access"})
    check("a tombstone whose successor failed keeps its records, even when the run named it",
          "space_access" not in failed and "room_access" not in failed, sorted(failed))
    with tempfile.TemporaryDirectory() as tmp:
        res = Path(tmp)
        (res / "intents").mkdir()
        old = make_intent("k-access-group-A", "access_reachable_group", "old", [], "space_access", "s")
        write_intent_shard(str(res), "k", [old], recomputed_categories={"space_access"}, known_categories=set(CATEGORIES))
        new = make_intent("k-access-group-A", "access_reachable_group", "new", [], "room_access", "s")
        write_intent_shard(str(res), "k", [new], recomputed_categories=recomputed_with_tombstones(CATEGORIES, {"room_access"}),
                           known_categories=set(CATEGORIES))
        shard = json.loads(Path(shard_path(str(res), "k")).read_text())["intents"]
        check("shard round-trip: an old-id record, then a live-only recompute, leaves one record under the successor",
              len(shard) == 1 and shard[0]["provenance"]["detector"] == "room_access" and shard[0]["label"] == "new",
              [(r["id"], r["provenance"]["detector"]) for r in shard])

    # ---- merged records equal the parts' records, on the example model ----
    key = resolve_file_identity(EXAMPLE, EXAMPLE.name)["key"] if EXAMPLE.exists() else None
    cache = REPO_ROOT / "data" / "extracted" / key / "recognition_cache.json" if key else None
    check("the example model and its extraction cache are present (the in-process comparison needs both)",
          key is not None and cache.exists(), (str(EXAMPLE), str(cache)))
    if key is not None and cache.exists():
        extracted = json.loads(cache.read_text())["extracted"]
        model = ifcopenshell.open(str(EXAMPLE))
        from recognition.access_graph import AccessGraph
        graph = AccessGraph(model)
        for cid, parts in MERGED.items():
            merged = CATEGORIES[cid]["detector"](model, extracted, key, graph=graph)
            expected = []
            for part in parts:
                module = importlib.import_module(f"recognition.detectors.{part}")
                kwargs = {"graph": graph} if "graph" in inspect.signature(module.detect).parameters else {}
                expected.extend(module.detect(model, extracted, key, **kwargs))
            same = sorted((comparable(r) for r in merged), key=lambda r: r["id"]) == \
                sorted((comparable(r) for r in expected), key=lambda r: r["id"])
            note = " (vacuous: the fixture has no IfcWindow)" if cid == "window_patterns" and not merged else ""
            check(f"{cid} on the example model: {len(merged)} records, the parts' records id for id{note}",
                  same and all(r["provenance"]["detector"] == cid for r in merged) and len(merged) == len(expected),
                  (len(merged), len(expected)))
            check(f"{cid}: every emitted type is declared",
                  {r["type"] for r in merged} <= set(CATEGORIES[cid]["intent_types"]), sorted({r["type"] for r in merged}))

    failed_checks = [r for r in RESULTS if not r[1]]
    for name, ok, detail in RESULTS:
        print(f"{'ok  ' if ok else 'FAIL'} {name}" + ("" if ok else f"  ->  {detail}"))
    print(f"\n{len(RESULTS) - len(failed_checks)} of {len(RESULTS)} checks passed")
    return 1 if failed_checks else 0


if __name__ == "__main__":
    sys.exit(main())

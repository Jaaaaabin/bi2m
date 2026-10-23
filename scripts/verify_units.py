"""Checks for src/ifc_units.py and everything that reads placements through it.

Read-only with respect to the intent store and verdicts: nothing here writes
a shard. It does rebuild the gitignored extraction cache for the corpus when
the cache version has moved, which is what a normal run would do too.

    uv run python scripts/verify_units.py
    uv run python scripts/verify_units.py --library $BI2M_IFC_CORPUS

Checks, in order:
  1. the helper itself: scale per unit, exact division for SI prefixes,
     `None` for an element without a placement. The metre case is
     data/example_autcon.ifc; the millimetre case is a small in-memory
     model, because data/ holds no millimetre file
  2. invariance: data/example_autcon.ifc, re-read as if it were millimetres
     (unit scale 0.001, every placement translation x1000), must give the
     placement-reading detectors byte-identical intent ids
  3. no-op on the fixtures: every category's in-process ids equal the ids in
     the stored shard, for every .ifc directly under data/
  4. with --library: on the millimetre and centimetre picks the door-to-room
     reach must be dominated by "exactly two rooms" and the isolated-room
     record must cover well under half the storey - the failure this helper
     removes had every door reaching zero rooms
"""

import argparse
import collections
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))
sys.path.insert(0, str(REPO_ROOT / "src"))

import numpy as np  # noqa: E402
import ifcopenshell  # noqa: E402
import ifcopenshell.api.geometry  # noqa: E402
import ifcopenshell.api.root  # noqa: E402
import ifcopenshell.api.unit  # noqa: E402
import ifcopenshell.util.placement  # noqa: E402
import ifcopenshell.util.unit  # noqa: E402

import ifc_units  # noqa: E402
import recognize_intents as rp  # noqa: E402
from recognition.access_graph import AccessGraph  # noqa: E402
from recognition.registry import CATEGORIES  # noqa: E402

DATA_DIR = REPO_ROOT / "data"
# The one model data/ keeps: metres, with a tracked shard. Models are not in
# git (.gitignore "No models in git"), so a fresh copy of the repo needs it
# copied into data/ by hand.
EXAMPLE = DATA_DIR / "example_autcon.ifc"
MM_DOOR_TRANSLATION = (17161.49557909889, -2500.25, 0.0)
SHARDS_DIR = REPO_ROOT / "Interfaces" / "Frontend" / "core" / "public" / "res" / "intents"
# Categories whose only unit-dependent input is a placement (daylight_rooms,
# beam_framing and convention_outlier also scale raw attributes, which the
# invariance check below deliberately does not fake).
PLACEMENT_CATEGORIES = (
    # 2026-10-08: the merged ids (room_access = space_access + space_syntax +
    # circulation_horizontal, egress_fire = egress_reachability + egress_access +
    # fire_compartments, window_patterns = window_alignment + lighting_clusters,
    # repeated_units = unit_typology + unit_layout); the rules are unchanged.
    "window_patterns", "circulation", "room_access", "repeated_units",
    "egress_fire", "sanitary_provision", "furniture_occupancy",
)

results = []


def check(name, ok, detail=""):
    results.append(bool(ok))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" - {detail}" if detail else ""))


def run_all(path, categories=None):
    identity = rp.resolve_file_identity(path, path.name)
    key = identity["key"]
    ids = set(categories or CATEGORIES)
    needed = {k for cid in ids for k in CATEGORIES[cid]["extraction_keys"]}
    extracted = rp.build_extracted(path, key, needed, use_cache=True) if needed else None
    model = ifcopenshell.open(str(path))
    # The pipeline's own call (recognize_intents.process_file): one shared door
    # graph for every detector that takes `graph=`. The Neufert categories give
    # fewer records without it, so a bare call would not match the stored shard.
    shared_graph = rp._shared_access_graph(model, ids)
    out = {}
    for cid in ids:
        detector = CATEGORIES[cid]["detector"]
        kwargs = {"graph": shared_graph} if shared_graph is not None and rp._accepts_graph(detector) else {}
        try:
            out[cid] = sorted(p["id"] for p in detector(model, extracted, key, **kwargs))
        except Exception as e:  # noqa: BLE001
            out[cid] = [f"ERROR {type(e).__name__}: {e}"]
    return key, model, out


def millimetre_model():
    """An IFC4 file declared in millimetres, holding one placed IfcDoor."""
    model = ifcopenshell.file(schema="IFC4")
    ifcopenshell.api.root.create_entity(model, ifc_class="IfcProject", name="millimetres")
    ifcopenshell.api.unit.assign_unit(model, length={"is_metric": True, "raw": "MILLIMETERS"})
    door = ifcopenshell.api.root.create_entity(model, ifc_class="IfcDoor", name="door")
    matrix = np.eye(4)
    matrix[:3, 3] = MM_DOOR_TRANSLATION
    ifcopenshell.api.geometry.edit_object_placement(model, product=door, matrix=matrix, is_si=False)
    return model


def section_helper():
    print("helper")
    m_metre = ifcopenshell.open(str(EXAMPLE))
    m_mm = millimetre_model()
    check(f"length_scale({EXAMPLE.stem}) == 1.0 (metres)", ifc_units.length_scale(m_metre) == 1.0)
    check("length_scale(in-memory millimetre model) == 0.001", ifc_units.length_scale(m_mm) == 0.001)
    x = 17161.49557909889
    check("to_metres is bit-identical to the old `/ 1000` on a millimetre value", ifc_units.to_metres(x, 0.001) == x / 1000)
    check("to_metres is the identity on a metre value", ifc_units.to_metres(x, 1.0) == x)
    check("to_metres handles centimetres and feet", ifc_units.to_metres(250.0, 0.01) == 2.5 and abs(ifc_units.to_metres(10.0, 0.3048) - 3.048) < 1e-12)
    synthetic = ifcopenshell.file(schema="IFC4")
    window = synthetic.createIfcWindow(ifcopenshell.guid.new(), None, "no placement")
    check("placement_xy is None for an element without ObjectPlacement", ifc_units.placement_xy(window, 1.0) is None)
    check("length_scale of a file without IfcProject is 1.0", ifc_units.length_scale(synthetic) == 1.0)
    door = next(d for d in m_mm.by_type("IfcDoor") if d.ObjectPlacement is not None)
    raw = ifcopenshell.util.placement.get_local_placement(door.ObjectPlacement)
    xy = ifc_units.placement_xy(door, ifc_units.length_scale(m_mm))
    check("placement_xy on a millimetre model divides the raw translation by 1000", xy == (raw[0][3] / 1000, raw[1][3] / 1000),
          f"raw {tuple(round(float(v), 1) for v in raw[:2, 3])} -> {tuple(round(v, 4) for v in xy)}")


def section_invariance():
    print(f"invariance ({EXAMPLE.stem} re-read as millimetres)")
    path = EXAMPLE
    _, _, plain = run_all(path, PLACEMENT_CATEGORIES)
    original_scale = ifcopenshell.util.unit.calculate_unit_scale
    original_place = ifcopenshell.util.placement.get_local_placement

    def fake_scale(model, unit_type="LENGTHUNIT"):
        return 0.001 if unit_type == "LENGTHUNIT" else original_scale(model, unit_type)

    # get_local_placement is recursive through the module attribute, so a
    # fake that scales every call would multiply a 3-level placement chain by
    # 1000^3. Scale only the outermost call: that is what a millimetre file
    # looks like from the caller's side.
    depth = [0]

    def fake_place(placement):
        depth[0] += 1
        try:
            matrix = original_place(placement)
        finally:
            depth[0] -= 1
        if depth[0]:
            return matrix
        matrix = matrix.copy()
        for row in range(3):
            matrix[row][3] *= 1000
        return matrix

    ifcopenshell.util.unit.calculate_unit_scale = fake_scale
    ifcopenshell.util.placement.get_local_placement = fake_place
    try:
        _, _, faked = run_all(path, PLACEMENT_CATEGORIES)
    finally:
        ifcopenshell.util.unit.calculate_unit_scale = original_scale
        ifcopenshell.util.placement.get_local_placement = original_place
    for cid in PLACEMENT_CATEGORIES:
        check(f"{cid}: ids identical when placements are x1000 and the scale is 0.001",
              plain[cid] == faked[cid], f"{len(plain[cid])} records")


def section_corpus():
    print("no-op on the fixtures (in-process ids vs stored shards)")
    fixtures = sorted(DATA_DIR.glob("*.ifc"))
    check("data/ holds at least one model", fixtures, "copy example_autcon.ifc into data/")
    for path in fixtures:
        name = path.stem
        key, _, out = run_all(path)
        shard_path = SHARDS_DIR / f"{key}.json"
        if not shard_path.exists():
            check(f"{name}: stored shard present", False, str(shard_path))
            continue
        stored = collections.defaultdict(list)
        for p in json.load(open(shard_path))["intents"]:
            stored[p["provenance"]["detector"]].append(p["id"])
        mismatched = [cid for cid in CATEGORIES if sorted(stored.get(cid, [])) != out[cid]]
        check(f"{name}: all {len(CATEGORIES)} categories reproduce the stored ids", not mismatched,
              ", ".join(mismatched) if mismatched else f"{sum(len(v) for v in out.values())} records")


def section_library(library):
    print(f"library picks ({library})")
    picks = (("0061", "mm"), ("0456", "mm"), ("0386", "mm"), ("0060", "cm"), ("0390", "m"))
    for stem, unit in picks:
        path = Path(library) / f"{stem}.ifc"
        if not path.exists():
            check(f"{stem}: present", False, "missing - library moved?")
            continue
        model = ifcopenshell.open(str(path))
        scale = ifc_units.length_scale(model)
        check(f"{stem}: declared unit is {unit}", ifc_units.unit_name(scale) == unit, f"scale {scale}")
        graph = AccessGraph(model)
        reach = collections.Counter(len(r) for _, r in graph.door_links.values())
        doors = sum(reach.values())
        two = reach.get(2, 0)
        check(f"{stem}: most common door reach is 2 rooms", doors and reach.most_common(1)[0][0] == 2,
              f"{dict(sorted(reach.items()))}")
        check(f"{stem}: no door reaches zero rooms on more than 20 % of doors", reach.get(0, 0) <= 0.2 * doors,
              f"{reach.get(0, 0)} of {doors} reach none")
        key = rp.resolve_file_identity(path, path.name)["key"]
        # The part module, not the merged room_access category (2026-10-08):
        # these checks target this rule's own record types.
        from recognition.detectors import space_access
        records = space_access.detect(model, None, key, graph=graph)
        isolated = sum(len(p["members"]) for p in records if p["type"] == "access_isolated_space")
        spaces = sum(len(v) for v in graph.spaces_by_storey.values())
        check(f"{stem}: isolated rooms are under half of the rooms with a footprint", isolated < spaces / 2,
              f"{isolated} of {spaces}; door median reach 2 -> {two} doors")

    # Door-graph semantics added 2026-09-23. Numbers
    # are the corpus's current names and move after a screening pass; the
    # content key is the identity, check with scripts/build_vis_index.py --list.
    # The part module, not the merged room_access category (2026-10-08):
    # these checks target this rule's own record types.
    from recognition.detectors import space_access
    for stem, expect in (("0062", "roomless"), ("0211", "shape")):
        path = Path(library) / f"{stem}.ifc"
        if not path.exists():
            check(f"{stem}: present", False, "missing - library renumbered?")
            continue
        model = ifcopenshell.open(str(path)); graph = AccessGraph(model)
        key = rp.resolve_file_identity(path, path.name)["key"]
        records = space_access.detect(model, None, key, graph=graph)
        types = collections.Counter(r["type"] for r in records)
        if expect == "roomless":
            roomless = [st for st in graph.doors_by_storey if not graph.spaces_by_storey.get(st)]
            check(f"{stem}: storeys with doors but no rooms are reported once each, not as door anomalies",
                  len(roomless) >= 1 and types.get("access_storey_without_rooms") == len(roomless),
                  f"{len(roomless)} roomless storeys, records {dict(types)}")
        else:
            shape = sum(1 for v in graph.door_anchor_source.values() if v == "shape")
            reach = collections.Counter(len(r) for _, r in graph.door_links.values())
            check(f"{stem}: doors whose placement misses every room are re-anchored on their shape",
                  shape > 0 and reach.most_common(1)[0][0] in (1, 2), f"{shape} shape-anchored, reach {dict(sorted(reach.items()))}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--library", help="folder with the tumgni_all picks (0061, 0456, 0386, 0060, 0390)")
    parser.add_argument("--skip-corpus", action="store_true")
    args = parser.parse_args()
    section_helper()
    section_invariance()
    if not args.skip_corpus:
        section_corpus()
    if args.library:
        section_library(args.library)
    print(f"\n{sum(results)}/{len(results)} checks passed")
    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    main()

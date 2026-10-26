"""Self-checks for the 2026-10-08 draft-detector batch:
the shared vocabulary, pre-flight's soft signals and `unlikely` tier, egress
seeds from doors in external walls, the degenerate-storey skip, and the
all-rated fire record. Synthetic: in-memory IFC4 files built with
ifcopenshell.api, fake door graphs, no file read or written - except the
regression section, which runs four detectors on data/example_autcon.ifc
when it and its extraction cache are present.

    uv run python scripts/verify_soft_signals.py

Exit code 0 when every check passes, 1 otherwise.
"""

import sys
import types
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

import ifcopenshell  # noqa: E402
import ifcopenshell.api  # noqa: E402

RESULTS = []


def check(name, condition, detail=""):
    RESULTS.append((name, bool(condition), detail))


def raises(exc, fn, *args):
    try:
        fn(*args)
    except exc:
        return True
    except Exception:  # noqa: BLE001 - the wrong exception is a failed check, not a crash
        return False
    return False


def fake(name):
    """An element with a Name and no type (vocabulary.element_text must cope)."""
    return types.SimpleNamespace(Name=name, GlobalId="fake")


def space_with_type(name, long_name, type_name, model=None):
    model = model or ifcopenshell.file(schema="IFC4")
    space = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcSpace", name=name)
    space.LongName = long_name
    if type_name is not None:
        space_type = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcSpaceType", name=type_name)
        ifcopenshell.api.run("type.assign_type", model, related_objects=[space], relating_type=space_type)
    return space


def section_vocabulary():
    from recognition import vocabulary as V
    check("German circulation word matches", V.matches("flur eg", "horizontal_circulation"))
    check("misspelling matches", V.matches("corridoor 1", "horizontal_circulation"))
    check("any-of concept", V.matches("bett", "seating|sleeping") and not V.matches("tisch", "seating|sleeping"))
    check("fixture kind: German wash basin", V.fixture_kind("waschbecken rund") == "wash")
    check("fixture kind: accessory rejected first", V.fixture_kind("toilet paper holder") is None)
    check("' wc' needs its boundary", V.fixture_kind("newcastle") is None and V.fixture_kind("herren wc") == "wc")
    revit = 'Toilet-Commercial-Wall-3D:15" Seat Height:129088'
    check("family segment: a dimension never counts",
          V.element_text(fake(revit)) == "toilet-commercial-wall-3d" and not V.matches(V.element_text(fake(revit)), "seating"))
    check("space_text includes the type name", V.space_text(space_with_type("A1", None, "Flur")) == "a1 flur")
    check("space_text is empty without names", V.space_text(space_with_type(None, None, None)) == "")
    check("words() keeps today's English first",
          V.words("horizontal_circulation")[:7] == ("corridor", "hall", "lobby", "foyer", "vestibule", "passage", "aisle"))


def preflight_fixture():
    """Two doors, one of them fire-rated; a wall tagged external; a space
    named Flur; a chair - the smallest file on which every grammar form has a
    True and a False case."""
    f = ifcopenshell.file(schema="IFC4")
    doors = [ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcDoor", name=n) for n in ("D1", "D2")]
    wall = ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcWall", name="W1")
    pset = ifcopenshell.api.run("pset.add_pset", f, product=wall, name="Pset_WallCommon")
    ifcopenshell.api.run("pset.edit_pset", f, pset=pset, properties={"IsExternal": True})
    pset = ifcopenshell.api.run("pset.add_pset", f, product=doors[0], name="Pset_DoorCommon")
    ifcopenshell.api.run("pset.edit_pset", f, pset=pset, properties={"FireRating": "1 hr"})
    ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcSpace", name="Flur")
    ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcFurniture", name="Stuhl:A:1")
    return f


def G(n, m):
    """A stand-in door graph: n degenerate storeys of m storeys with rooms."""
    return types.SimpleNamespace(degenerate_storeys=set(range(n)), spaces_by_storey={i: ["r"] for i in range(m)})


def section_preflight():
    from recognition import preflight as PF
    from recognition.registry import CATEGORIES
    f = preflight_fixture()
    check("class", PF.signal_available(f, "IfcDoor") and not PF.signal_available(f, "IfcWindow"))
    check("prop scoped", PF.signal_available(f, "prop:FireRating@IfcDoor") and not PF.signal_available(f, "prop:FireRating@IfcWall"))
    check("true scoped", PF.signal_available(f, "true:IsExternal@IfcDoor|IfcWall") and not PF.signal_available(f, "true:IsExternal@IfcDoor"))
    check("unknown class in a scope is False, not an error", PF.signal_available(f, "prop:FireRating@IfcNotAClass") is False)
    check("vocab on spaces", PF.signal_available(f, "vocab:horizontal_circulation") and not PF.signal_available(f, "vocab:vertical_core"))
    check("vocab on fixtures", PF.signal_available(f, "vocab:seating|sleeping") and not PF.signal_available(f, "vocab:sanitary_fixture"))
    furnishing = ifcopenshell.file(schema="IFC4")
    ifcopenshell.api.run("root.create_entity", furnishing, ifc_class="IfcFurnishingElement", name="Sessel:B:2")
    check("vocab on fixtures scans the owning detector's classes (IfcFurnishingElement is furniture, not a sanitary class)",
          PF.signal_available(furnishing, "vocab:seating") is True and PF.signal_available(furnishing, "vocab:sanitary_fixture") is False)
    check("footprints without a graph is unevaluated", PF.signal_available(f, "footprints:usable") is None)
    check("footprints threshold", PF.signal_available(f, "footprints:usable", graph=G(2, 3)) is False
          and PF.signal_available(f, "footprints:usable", graph=G(1, 3)) is True
          and PF.signal_available(f, "footprints:usable", graph=G(0, 0)) is True)
    check("why texts", PF.describe_signal("true:IsExternal@IfcDoor|IfcWall") == "no IfcDoor / IfcWall tagged IsExternal"
          and PF.describe_signal("prop:FireRating@IfcDoor") == "no FireRating values on IfcDoor"
          and PF.describe_signal("vocab:horizontal_circulation") == "no space named as horizontal circulation (any language in the table)"
          and PF.describe_signal("vocab:seating|sleeping") == "no fixture named as seating or sleeping furniture"
          and PF.describe_signal("footprints:usable", graph=G(2, 3)) == "room footprints degenerate on 2 of 3 storeys",
          [PF.describe_signal(s) for s in ("true:IsExternal@IfcDoor|IfcWall", "prop:FireRating@IfcDoor", "vocab:horizontal_circulation", "vocab:seating|sleeping")])
    report = PF.preflight(f, CATEGORIES, graph=G(2, 3))
    missing = {e["category"]: e["missing"] for e in report["unlikely"]}
    # The Neufert categories (`section`, 2026-10-18) declare their classes as soft signals and are not this batch's subject.
    from recognition.registry import CATEGORIES as _CATS
    missing = {cid: sig for cid, sig in missing.items() if not _CATS.get(cid, {}).get("section")}
    check("unlikely: the three footprint categories, sanitary without fixtures, furniture present",
          missing == {"room_access": ["footprints:usable"], "egress_fire": ["footprints:usable"],
                      "repeated_units": ["footprints:usable"], "sanitary_provision": ["vocab:sanitary_fixture"]}, missing)
    check("every unlikely entry carries a label and one why per missing signal",
          all(e["label"] and len(e["why"]) == len(e["missing"]) for e in report["unlikely"]))
    check("zero_output", PF.zero_output({"inapplicable": [{"category": "a"}]}, ["a", "b", "c"], {"b": 0, "c": 2}) == ["b"])
    check("format_report has the unlikely block", "unlikely to produce output here" in PF.format_report(report))
    check("format_zero_output", PF.format_zero_output(["b"]) == "  zero output (applicable, ran, nothing): b" and PF.format_zero_output([]) == "")
    check("parse rejects an unknown prefix", raises(ValueError, PF.parse_signal, "foo:bar"))
    # Review findings, 2026-10-08 (ledger: Final).
    retired = {cid for cid, info in CATEGORIES.items() if info.get("retired")}
    zero = PF.zero_output({"inapplicable": []}, list(CATEGORIES), {}, categories=CATEGORIES)
    check("zero_output never names a tombstone on a bare run", zero and not (set(zero) & retired), sorted(set(zero) & retired)[:3])
    empty = ifcopenshell.file(schema="IFC4")
    empty_report = PF.preflight(empty, CATEGORIES, graph=G(2, 3))
    check("a category that is inapplicable is not also unlikely",
          not [e for e in empty_report["unlikely"] if not _CATS.get(e["category"], {}).get("section")]
          and any(e["category"] == "room_access" for e in empty_report["inapplicable"]),
          [e["category"] for e in empty_report["unlikely"]][:4])
    previous = {"signals": {"footprints:usable": False, "IfcDoor": True}, "inapplicable": [],
                "unlikely": [{"category": "room_access", "label": "Room Access", "missing": ["footprints:usable"],
                              "why": ["room footprints degenerate on 5 of 5 storeys"]}],
                "zeroOutput": ["repeated_units", "room_access"]}
    current = {"signals": {"footprints:usable": None, "IfcDoor": True}, "inapplicable": [], "unlikely": [],
               "zeroOutput": ["sanitary_provision"]}
    merged = PF.merge_report(previous, current, CATEGORIES, {"sanitary_provision", "room_access"})
    check("merge: a signal this run could not judge keeps its previous value",
          merged["signals"]["footprints:usable"] is False, merged["signals"])
    check("merge: the previous unlikely entry survives when this run could not judge the category",
          [e["category"] for e in merged["unlikely"]] == ["room_access"], merged["unlikely"])
    check("merge: zeroOutput keeps categories this run did not recompute and drops the ones it did",
          merged["zeroOutput"] == ["repeated_units", "sanitary_provision"], merged["zeroOutput"])
    full = PF.merge_report(previous, {"signals": {"footprints:usable": True, "IfcDoor": True}, "inapplicable": [], "unlikely": [], "zeroOutput": []},
                           CATEGORIES, {"room_access"})
    check("merge: a fully judged run replaces the previous verdict", full["unlikely"] == [] and full["signals"]["footprints:usable"] is True)
    check("merge: no previous report passes the current one through",
          PF.merge_report(None, current, CATEGORIES, set()) == current)
    now_inapplicable = {"signals": {"footprints:usable": None, "IfcDoor": True},
                        "inapplicable": [{"category": "room_access", "label": "Room Access", "missing": ["IfcSpace"]}],
                        "unlikely": [], "zeroOutput": []}
    check("merge: a previous unlikely entry does not survive for a category this run marks inapplicable",
          PF.merge_report(previous, now_inapplicable, CATEGORIES, set())["unlikely"] == [],
          PF.merge_report(previous, now_inapplicable, CATEGORIES, set())["unlikely"])


def section_egress():
    from recognition.detectors.egress_reachability import exit_door_guids
    guids, kinds = exit_door_guids(["a", "b", "c", "d"],
                                   {"a": True, "b": False, "c": False, "d": False},
                                   {"a": False, "b": True, "c": True, "d": False},
                                   {"a": 1, "b": 1, "c": 2, "d": 1})
    check("tagged door seeds; wall-tagged door reaching one room seeds; reaching two does not; untagged does not",
          guids == {"a", "b"} and kinds == {"external door", "external wall door"}, (guids, kinds))
    check("no exits, no kinds", exit_door_guids(["x"], {"x": False}, {"x": False}, {"x": 1}) == (set(), set()))


def graph_fixture(degenerate=("S1",), rated=("S1:d1", "S2:d1")):
    """Two storeys, S1 and S2, six rooms each in two units of three (Bed,
    Bath, Kitchen, twice), each unit chained by two doors (d1: rooms 1-2,
    d2: rooms 2-3; d3: rooms 4-5, d4: rooms 5-6), as an in-memory IFC4 file
    plus a hand-built AccessGraph. Every rule of the batch fires on such a
    storey: groups of three, a recurring unit, no exit, and with d1 rated a
    two-room compartment. `degenerate` names storeys for
    graph.degenerate_storeys; `rated` names doors given FireRating "1 hr".
    Returns (model, graph, storey guids by name, door guids by name)."""
    from shapely.geometry import Polygon
    from recognition.access_graph import AccessGraph
    f = ifcopenshell.file(schema="IFC4")
    storeys, doors, graph = {}, {}, AccessGraph.__new__(AccessGraph)
    graph.model = f
    graph.spaces_by_storey, graph.door_links, graph.doors_by_storey = {}, {}, {}
    graph.doors_by_pair, graph.door_points, graph.polygons, graph.space_by_guid = {}, {}, {}, {}
    graph.median_door_to_room_m = None
    for index, name in enumerate(("S1", "S2")):
        storey = ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcBuildingStorey", name=name)
        storeys[name] = storey.GlobalId
        rooms = []
        for i, room_name in enumerate(("Bed", "Bath", "Kitchen", "Bed", "Bath", "Kitchen")):
            space = ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcSpace", name=room_name)
            rooms.append(space.GlobalId)
            graph.space_by_guid[space.GlobalId] = space
            x = index * 10 + i * 2
            graph.polygons[space.GlobalId] = Polygon([(x, 0), (x + 1, 0), (x + 1, 1), (x, 1)])
        graph.spaces_by_storey[storey.GlobalId] = rooms
        graph.doors_by_storey[storey.GlobalId] = []
        for door_name, (a, b) in (("d1", (0, 1)), ("d2", (1, 2)), ("d3", (3, 4)), ("d4", (4, 5))):
            door = ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcDoor", name=f"{name}:{door_name}")
            doors[f"{name}:{door_name}"] = door.GlobalId
            graph.door_links[door.GlobalId] = (storey.GlobalId, [rooms[a], rooms[b]])
            graph.doors_by_storey[storey.GlobalId].append(door.GlobalId)
            graph.door_points[door.GlobalId] = (index * 10 + a * 2 + 1, 0.5)
            if f"{name}:{door_name}" in rated:
                pset = ifcopenshell.api.run("pset.add_pset", f, product=door, name="Pset_DoorCommon")
                ifcopenshell.api.run("pset.edit_pset", f, pset=pset, properties={"FireRating": "1 hr"})
    graph.degenerate_storeys = {storeys[name] for name in degenerate}
    return f, graph, storeys, doors


def section_degenerate():
    import json
    import importlib
    f, graph, storeys, _doors = graph_fixture(degenerate=("S1",))
    # One door per storey that reaches a single room: a cardinality anomaly,
    # which on a degenerate storey is exactly what the footprints fabricate.
    for name in ("S1", "S2"):
        extra = ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcDoor", name=f"{name}:single")
        graph.door_links[extra.GlobalId] = (storeys[name], [graph.spaces_by_storey[storeys[name]][0]])
        graph.doors_by_storey[storeys[name]].append(extra.GlobalId)
        graph.door_points[extra.GlobalId] = (0.5, 0.5)
    any_s2 = False
    for module_name in ("space_access", "egress_reachability", "fire_compartments", "unit_typology"):
        module = importlib.import_module(f"recognition.detectors.{module_name}")
        records = module.detect(f, None, "k", graph=graph)
        dumps = [json.dumps(r, default=str) for r in records]
        check(f"{module_name}: no record touches the degenerate storey S1", not any(storeys["S1"] in d for d in dumps),
              [r["id"] for r in records if storeys["S1"] in json.dumps(r, default=str)][:3])
        any_s2 = any_s2 or any(storeys["S2"] in d for d in dumps)
    check("the other storey still produces records", any_s2)


def section_fire_singletons():
    from recognition.detectors import fire_compartments
    all_doors = tuple(f"{s}:d{i}" for s in ("S1", "S2") for i in (1, 2, 3, 4))

    def singletons(records, storey_guid):
        return [r for r in records if r["type"] == "fire_compartment_singletons" and storey_guid in r["evidence"]["relatedGuids"]]

    f, graph, storeys, doors = graph_fixture(degenerate=(), rated=all_doors)
    records = fire_compartments.detect(f, None, "k", graph=graph)
    s2 = singletons(records, storeys["S2"])
    check("every door rated: one singleton record per storey", len(s2) == 1 and len(singletons(records, storeys["S1"])) == 1, len(records))
    if s2:
        r = s2[0]
        check("the singleton record: id, rule, polarity, 6 rooms as members, 4 rated doors",
              r["id"] == f"k-firesingletons-{storeys['S2']}" and r["provenance"]["rule"] == "every_door_rated"
              and r["polarity"] == "positive" and len(r["members"]) == 6 and r["evidence"]["metrics"]["rooms"] == 6
              and r["evidence"]["metrics"]["ratedDoors"] == 4 and r["evidence"]["metrics"]["ratings"] == {"1 hr": 4},
              (r["id"], r["evidence"]["metrics"]))
        check("the label says so", r["label"] == "Every room on S2 is its own fire compartment: 6 rooms behind 4 rated doors", r["label"])

    f, graph, storeys, doors = graph_fixture(degenerate=(), rated=tuple(d for d in all_doors if d != "S1:d4"))
    records = fire_compartments.detect(f, None, "k", graph=graph)
    s1_compartments = [r for r in records if r["type"] == "fire_compartment" and storeys["S1"] in r["evidence"]["relatedGuids"]]
    check("one unrated two-room door: no singleton record, one ordinary compartment on that storey",
          not singletons(records, storeys["S1"]) and len(s1_compartments) == 1 and len(singletons(records, storeys["S2"])) == 1,
          [(r["type"], r["label"][:50]) for r in records])

    f, graph, storeys, doors = graph_fixture(degenerate=(), rated=all_doors)
    extra = ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcDoor", name="S2:single")
    graph.door_links[extra.GlobalId] = (storeys["S2"], [graph.spaces_by_storey[storeys["S2"]][0]])
    graph.doors_by_storey[storeys["S2"]].append(extra.GlobalId)
    records = fire_compartments.detect(f, None, "k", graph=graph)
    s2 = singletons(records, storeys["S2"])
    check("an unrated door that reaches one room does not block the rule, and is counted",
          len(s2) == 1 and s2[0]["evidence"]["metrics"]["unratedDoors"] == 1, [r["evidence"]["metrics"] for r in s2])


def section_example():
    """The four vocabulary consumers reproduce the stored records of the
    example model, whose names are English: nothing moves there."""
    import json
    from file_identity import resolve_file_identity
    example = REPO_ROOT / "data" / "example_autcon.ifc"
    if not example.exists():
        check("example model present for the regression section", False, str(example))
        return
    key = resolve_file_identity(example, example.name)["key"]
    cache = REPO_ROOT / "data" / "extracted" / key / "recognition_cache.json"
    shard = REPO_ROOT / "viewer" / "public" / "res" / "intents" / f"{key}.json"
    if not (cache.exists() and shard.exists()):
        check("example extraction cache and shard present", False, (str(cache), str(shard)))
        return
    extracted = json.loads(cache.read_text())["extracted"]
    stored = json.loads(shard.read_text())["intents"]
    model = ifcopenshell.open(str(example))
    import importlib
    for module_name, types_ in (("circulation_horizontal", ("circulation_horizontal_space",)),
                                ("vertical", ("vertical_space_connection",)),
                                ("sanitary_provision", ("sanitary_provision",)),
                                ("furniture_occupancy", ("furniture_occupancy",))):
        module = importlib.import_module(f"recognition.detectors.{module_name}")
        found = sorted(r["id"] for r in module.detect(model, extracted, key))
        expected = sorted(r["id"] for r in stored if r["type"] in types_)
        check(f"{module_name} on the example model: same record ids as the stored shard", found == expected,
              (len(found), len(expected)))


def main():
    section_vocabulary()
    section_preflight()
    section_egress()
    section_degenerate()
    section_fire_singletons()
    section_example()
    failed = [r for r in RESULTS if not r[1]]
    for name, ok, detail in RESULTS:
        print(f"{'ok  ' if ok else 'FAIL'} {name}" + ("" if ok else f"  ->  {detail}"))
    print(f"\n{len(RESULTS) - len(failed)} of {len(RESULTS)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

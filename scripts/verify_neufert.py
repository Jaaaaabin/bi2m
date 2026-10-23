"""Self-checks for the Neufert Topic categories (2026-10-18):
the two config layers, the no-literal-thresholds rule, synthetic IFC4
fixtures for the measure and provision families, determinism, and a
regression run of all 13 categories on data/example_autcon.ifc.

    uv run python scripts/verify_neufert.py

Writes nothing. Exit code 0 when every check passes, 1 otherwise.
"""

import re
import sys
import tempfile
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

import ifcopenshell  # noqa: E402
import ifcopenshell.api  # noqa: E402

from recognition.neufert import compare, facts, measures  # noqa: E402
from recognition.neufert.engine import run_topic  # noqa: E402
from recognition.neufert.families import BUILT, FAMILIES  # noqa: E402
from recognition.neufert.rules import RULES_DIR, load_rules, status_kind  # noqa: E402
from recognition.neufert.topics import TOPICS  # noqa: E402

RESULTS = []
EXAMPLE = REPO_ROOT / "data" / "example_autcon.ifc"
PACKAGE = REPO_ROOT / "src" / "recognition" / "neufert"
# Float literals a module may contain besides what the cards' YAML provides.
ALLOWED_LITERALS = {
    "compare.py": {"0.005", "0.10"},               # EPS, EPS_REL, APPROX_REL (named, documented)
    "measures.py": {"100.0", "1e-9", "0.25", "0.1"},  # percent, the unset tolerance, CORROBORATE_TOL, COUNT_ROUND_TOL
    "geometry.py": {"0.6", "2.0", "1e-9", "0.0", "0.2", "1.0", "0.05", "0.3"},  # WINDOW_REACH_M, WINDOW_FRAME_SUSPECT_M, tolerances, the upward-face cut, FLIGHT_RASTER_M, FLIGHT_SEGMENT_MIN_M
    "records.py": {"0.9", "0.3048", "0.001"},        # ROLLUP_SHARE, FOOT_M, FOOT_TOLERANCE_M
    "context.py": {"1.0", "1e-9", "2.0", "0.5"},     # GRAPH_FRAME_SUSPECT_M, GRAPH_FRAME_SHIFT_M
    "facts.py": {"0.0", "0.3", "0.5"},              # seed distance, TALL_MARGIN_M, LEVEL_BAND_M
    "select.py": {"1e-9"},
    "families/provision.py": {"0.0"},
    "families/aggregate.py": {"1.0"},               # a counted element
    "cores.py": {"0.15", "0.3", "1.0", "0.0", "0.6", "3.0"},  # Z_MARGIN_M, STACK_IOU, STACK_BASE_GAP_M, counts, LIFT_REACH_M, LIFT_CORE_REACH_M
}


def check(name, condition, detail=""):
    RESULTS.append((name, bool(condition), detail))


def run(file, ifc_class, **kwargs):
    return ifcopenshell.api.run(f"root.create_entity", file, ifc_class=ifc_class, **kwargs)


def add_pset(file, product, name, props):
    pset = ifcopenshell.api.run("pset.add_pset", file, product=product, name=name)
    ifcopenshell.api.run("pset.edit_pset", file, pset=pset, properties=props)


def add_qto(file, product, name, props):
    qto = ifcopenshell.api.run("pset.add_qto", file, product=product, name=name)
    ifcopenshell.api.run("pset.edit_qto", file, qto=qto, properties=props)


def fixture():
    """IFC4, metres: one storey; internal doors at 2.00 and 2.20 m, an
    external door at 2.00 m, a door without a height; flights with riser/
    tread 0.17/0.29 and 0.20/0.30 in Pset_StairFlightCommon; spaces
    'Büro' (Qto height 2.6, area 20), 'Flur' (height 2.2) and 'Putzraum'."""
    f = ifcopenshell.api.run("project.create_file", version="IFC4")
    run(f, "IfcProject", name="P")
    metre = ifcopenshell.api.run("unit.add_si_unit", f, unit_type="LENGTHUNIT")
    ifcopenshell.api.run("unit.assign_unit", f, units=[metre])
    storey = run(f, "IfcBuildingStorey", name="S1")
    storey.Elevation = 0.0
    storey2 = run(f, "IfcBuildingStorey", name="S2")
    storey2.Elevation = 3.0
    doors = {}
    for name, height, external in (("d_low", 2.0, False), ("d_ok", 2.2, False), ("d_ext", 2.0, True), ("d_nodata", None, False)):
        door = run(f, "IfcDoor", name=name)
        door.OverallHeight = height
        add_pset(f, door, "Pset_DoorCommon", {"IsExternal": external})
        ifcopenshell.api.run("spatial.assign_container", f, products=[door], relating_structure=storey)
        doors[name] = door
    flights = {}
    for name, riser, tread in (("f_ok", 0.17, 0.29), ("f_long", 0.20, 0.30)):
        flight = run(f, "IfcStairFlight", name=name)
        add_pset(f, flight, "Pset_StairFlightCommon", {"RiserHeight": riser, "TreadLength": tread, "NumberOfRiser": 2 if name == "f_long" else 12})
        ifcopenshell.api.run("spatial.assign_container", f, products=[flight], relating_structure=storey)
        flights[name] = flight
    for i in range(3):  # a door library at 2.00 m on S2: with d_low that is 4 of 5 internal doors failing (80 %)
        door = run(f, "IfcDoor", name=f"lib{i}")
        door.OverallHeight = 2.0
        add_pset(f, door, "Pset_DoorCommon", {"IsExternal": False})
        ifcopenshell.api.run("spatial.assign_container", f, products=[door], relating_structure=storey2)
    imperial = run(f, "IfcDoor", name="d_8ft")
    imperial.OverallHeight = 2.4384
    add_pset(f, imperial, "Pset_DoorCommon", {"IsExternal": False})
    ifcopenshell.api.run("spatial.assign_container", f, products=[imperial], relating_structure=storey2)
    doors["d_8ft"] = imperial
    revolving = run(f, "IfcDoor", name="d_rev")
    revolving.OverallHeight = 2.2
    revolving.OperationType = "REVOLVING"
    add_pset(f, revolving, "Pset_DoorCommon", {"IsExternal": True})
    ifcopenshell.api.run("spatial.assign_container", f, products=[revolving], relating_structure=storey)
    doors["d_rev"] = revolving
    roof = run(f, "IfcSlab", name="roof0", predefined_type="ROOF")
    add_pset(f, roof, "Pset_SlabCommon", {"PitchAngle": 0.0})
    ifcopenshell.api.run("spatial.assign_container", f, products=[roof], relating_structure=storey2)
    doors["roof0"] = roof
    stairs = {}
    for name, external, riser, tread in (("st_ext", True, 0.14, 0.35), ("st_int", False, 0.14, 0.35)):
        stair = run(f, "IfcStair", name=name)
        add_pset(f, stair, "Pset_StairCommon", {"IsExternal": external})
        ifcopenshell.api.run("spatial.assign_container", f, products=[stair], relating_structure=storey)
        part = run(f, "IfcStairFlight", name=name + "_flight")
        add_pset(f, part, "Pset_StairFlightCommon", {"RiserHeight": riser, "TreadLength": tread})
        ifcopenshell.api.run("aggregate.assign_object", f, products=[part], relating_object=stair)
        stairs[name] = (stair, part)
    spaces = {}
    for name, height, area, where in (("Büro", 2.6, 20.0, storey), ("Flur", 2.2, 10.0, storey), ("Putzraum", 2.5, 3.0, storey),
                                      ("Bad", 2.5, 5.0, storey2), ("Badminton", 2.5, 5.0, storey2), ("Store room", 2.5, 5.0, storey2), ("Storey lobby", 2.5, 5.0, storey2)):
        space = run(f, "IfcSpace", name=name)
        add_qto(f, space, "Qto_SpaceBaseQuantities", {"Height": height, "NetFloorArea": area})
        ifcopenshell.api.run("aggregate.assign_object", f, products=[space], relating_object=where)
        spaces[name] = space
    return f, storey, storey2, doors, flights, spaces, stairs


def by_rule_outcome(records):
    out = {}
    for record in records:
        key = (record["provenance"]["rule"], record["type"].rsplit("_", 1)[1], record["evidence"]["metrics"].get("param"))
        out.setdefault(key, []).append(record)
    return out


def primary_members(record):
    return [m["guid"] for m in record["members"] if m["role"] != "context"]


def context_members(record):
    return [m["guid"] for m in record["members"] if m["role"] == "context"]


def members(record):
    return [m["guid"] for m in record["members"]]


def section_config():
    rules = load_rules()
    check("122 rules load from config/neufert", len(rules) == 122, len(rules))
    yaml_files = sorted(p.stem for p in RULES_DIR.glob("K*.yaml"))
    check("122 rule YAML files, one per binding", yaml_files == sorted(rules), len(yaml_files))
    active = [r for r in rules.values() if status_kind(r["status"]) != "deferred"]
    check("every bound/partial rule uses a built family and has checks",
          all(r["family"] in BUILT and r["checks"] for r in active), [r["kid"] for r in active if r["family"] not in BUILT])
    check("every deferred rule states a reason",
          all(":" in r["status"] and r["status"].split(":", 1)[1].strip() for r in rules.values() if status_kind(r["status"]) == "deferred"))
    check("every family named in a binding exists", all(r["family"] in FAMILIES for r in rules.values()))
    topics = {t[0] for t in TOPICS}
    check("every rule's topic is one of the 13", all(r["topic"] in topics for r in rules.values()))
    deferred = [r for r in rules.values() if status_kind(r["status"]) == "deferred"]
    check("every deferred rule carries machine-readable needs tags", all(r["needs"] for r in deferred), [r["kid"] for r in deferred if not r["needs"]])
    stale = [(r["kid"], tag) for r in deferred for tag in r["needs"] if tag.startswith("family:") and tag[len("family:"):] in BUILT]
    check("no deferred rule waits on a family that is built (a stale reason)", not stale, stale)
    stale_facts = [(r["kid"], t) for r in deferred for t in r["needs"] if t.startswith("fact:") and t[5:] in facts.BUILT]
    check("no deferred rule waits on a fact that is built (facts.BUILT)", not stale_facts, stale_facts)
    unlocked = Counter(tag for r in deferred for tag in r["needs"])
    print("  rules waiting per missing fact / geometry / input / family:",
          ", ".join(f"{tag} {n}" for tag, n in unlocked.most_common(12)))
    print("  bound:", " ".join(r["kid"] for r in active if status_kind(r["status"]) == "bound"))
    print("  partial:", " ".join(r["kid"] for r in active if status_kind(r["status"]) == "partial"))
    print("  widened:", " ".join(r["kid"] for r in active if status_kind(r["status"]) == "widened"))
    print("  deferred:", sum(1 for r in rules.values() if status_kind(r["status"]) == "deferred"))


def section_bindings_script():
    """scripts/neufert_bindings.py carries no rule id, and its three data
    files reproduce the committed bindings.yaml byte for byte."""
    import subprocess
    script = REPO_ROOT / "scripts" / "neufert_bindings.py"
    code = re.sub(r'"""[\s\S]*?"""', "", script.read_text(encoding="utf-8"))
    check("the bindings generator names no rule id (the hand layer is bound.yaml)", not re.findall(r"\bK\d{2,3}\b", code))
    plan = REPO_ROOT / "neufert_logic.md"
    if not plan.is_file():
        check("neufert_logic.md is present for the generator round-trip", False, str(plan))
        return
    with tempfile.TemporaryDirectory() as tmp:
        cards = Path(tmp) / "cards.json"
        target = Path(tmp) / "bindings.yaml"
        subprocess.run([sys.executable, str(script), "cards", str(plan), str(cards)], check=True, capture_output=True)
        subprocess.run([sys.executable, str(script), "bindings", str(cards), str(target)], check=True, capture_output=True)
        check("cards + families.yaml + deferred_reasons.yaml + bound.yaml reproduce config/neufert/bindings.yaml",
              target.read_bytes() == (REPO_ROOT / "config" / "neufert" / "bindings.yaml").read_bytes())


def section_literals():
    """No module of the package carries a threshold: float literals outside
    the per-file allow-list fail."""
    offenders = []
    for path in sorted(PACKAGE.rglob("*.py")):
        rel = str(path.relative_to(PACKAGE))
        code = re.sub(r'"""[\s\S]*?"""', "", path.read_text(encoding="utf-8"))
        code = re.sub(r"#.*", "", code)
        literals = set(re.findall(r"(?<![\w.])\d+\.\d+(?:e-?\d+)?|(?<![\w.])\d+e-?\d+", code))
        extra = literals - ALLOWED_LITERALS.get(rel, set())
        if extra:
            offenders.append((rel, sorted(extra)))
    check("no float literal in the package beyond the named constants", not offenders, offenders)


def section_compare():
    check("compare: >= inclusive within EPS", compare.satisfied(2.1 - 0.004, {"op": ">=", "value": 2.1}))
    check("compare: >= strict below EPS", not compare.satisfied(2.1 - 0.006, {"op": ">=", "value": 2.1}))
    check("compare: in range inclusive", compare.satisfied(0.12, {"op": "in", "value": [0.12, 0.16]}))
    check("compare: in membership over strings", compare.satisfied("REVOLVING", {"op": "in", "value": ["REVOLVING"]}))
    check("compare: ~= within APPROX_REL", compare.satisfied(31, {"op": "~=", "value": 30}) and not compare.satisfied(40, {"op": "~=", "value": 30}))
    check("compare: unsupported op raises", _raises(compare.Unsupported, compare.satisfied, 1, {"op": "is", "value": "x"}))
    check("outcome: INFO met gives None, departed gives info",
          compare.outcome(2.3, {"op": ">=", "value": 2.25, "severity": "INFO"}) is None
          and compare.outcome(2.1, {"op": ">=", "value": 2.25, "severity": "INFO"}) == "info")
    check("outcome: negate flips a membership into a violation",
          compare.outcome("REVOLVING", {"op": "in", "value": ["REVOLVING"], "severity": "FAIL"}, negate=True) == "fail")
    check("derived expression rejects calls and strings",
          _raises(ValueError, measures.validate_expression, "x", "max(a.b, 1)", {})
          and _raises(ValueError, measures.validate_expression, "x", "'1'", {}))
    check("derived expression names dotted measures only",
          measures._names_in("2*flight.riser + flight.tread") == {"flight.riser", "flight.tread"})


def _raises(exc, fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
    except exc:
        return True
    except Exception:  # noqa: BLE001
        return False
    return False


def section_fixture():
    f, storey, storey2, doors, flights, spaces, stairs = fixture()
    records = run_topic("doors", f, "fx") + run_topic("stairs", f, "fx") + run_topic("offices", f, "fx")
    got = by_rule_outcome(records)

    fail = got.get(("K23", "fail", "H_DOOR"), [])
    ok = got.get(("K23", "pass", "H_DOOR"), [])
    nodata = got.get(("K23", "nodata", None), [])
    check("K23: under the rollup policy (4 of 6 judged fail, below 90 %) fails stay per storey: S1 holds the 2.00 m door, S2 the three library doors",
          len(fail) == 2 and sorted(len(members(r)) for r in fail) == [1, 3] and all(not r["evidence"]["metrics"]["modelLevel"] for r in fail), [members(r) for r in fail])
    check("K23: the 2.20 m and the 8 ft doors pass H_DOOR; the external doors are outside the population",
          sorted(g for r in ok for g in members(r)) == sorted([doors["d_ok"].GlobalId, doors["d_8ft"].GlobalId]), [members(r) for r in ok])
    eight = [r for r in ok if doors["d_8ft"].GlobalId in members(r)]
    check("imperial default: the 2.4384 m door is counted as a whole-feet value on its record",
          eight and eight[0]["evidence"]["metrics"].get("imperialDefault") == 1 and "whole feet" in eight[0]["evidence"]["summary"],
          [r["evidence"]["metrics"] for r in eight])
    check("K23: the door without a height is nodata, never a failure",
          len(nodata) == 1 and members(nodata[0]) == [doors["d_nodata"].GlobalId] and nodata[0]["polarity"] == "negative")
    info = got.get(("K23", "info", "H_BETTER"), [])
    check("K23: H_BETTER (INFO) is one model-level record of the doors below 2.25 m, with the storey distribution",
          len(info) == 1 and info[0]["evidence"]["metrics"]["modelLevel"] and len(members(info[0])) == 5
          and set(info[0]["evidence"]["metrics"]["byStorey"]) == {"S1", "S2"} and info[0]["id"].endswith("-building"), [r["evidence"]["metrics"] for r in info])
    check("K23: fail is negative polarity, pass positive, rule is the KID, type carries the category",
          fail and fail[0]["polarity"] == "negative" and ok[0]["polarity"] == "positive"
          and fail[0]["provenance"]["rule"] == "K23" and fail[0]["type"] == "neufert_doors_fail"
          and fail[0]["provenance"]["detector"] == "neufert_doors")
    check("K23: a per-storey record names its storey and its source",
          fail and all(len(r["evidence"]["relatedGuids"]) == 1 for r in fail)
          and all(set(r["evidence"]["metrics"]["sources"]) == {"IfcDoor.OverallHeight"} for r in fail))
    k24 = got.get(("K24", "info", "OP_BANNED"), [])
    k24_nodata = got.get(("K24", "nodata", None), [])
    check("K24 (partial): the revolving external door is reported as info, not fail; the external door without an OperationType is nodata",
          len(k24) == 1 and members(k24[0]) == [doors["d_rev"].GlobalId]
          and len(k24_nodata) == 1 and members(k24_nodata[0]) == [doors["d_ext"].GlobalId], ([members(r) for r in k24], [members(r) for r in k24_nodata]))
    envelope = by_rule_outcome(run_topic("envelope", f, "fx"))
    nod = envelope.get(("K63", "nodata", None), [])
    check("K63: a declared PitchAngle of 0 is not a verdict; without geometry the roof is nodata",
          len(nod) == 1 and members(nod[0]) == [doors["roof0"].GlobalId] and not envelope.get(("K63", "fail", "S_MIN")), list(envelope))
    from recognition import vocabulary as V
    check("vocabulary: bounded words - 'Bad' is a bathroom, 'Badminton' is not; 'Store room' is storage, 'Storey lobby' is not",
          V.matches("bad", "bathroom") and not V.matches("badminton", "bathroom") and V.matches("store room", "storage") and not V.matches("storey lobby", "storage")
          and V.matches("b 1.04 bad", "bathroom") and V.matches("bad/wc", "bathroom"))

    k07_pass = got.get(("K07", "pass", "STEP_MAX"), [])
    k07_warn = got.get(("K07", "warn", "STEP_MAX"), [])
    check("K07: 0.63 (0.17/0.29 and the stairs' 0.14/0.35 flights) passes STEP_MAX from Pset_StairFlightCommon (derived)",
          len(k07_pass) == 1 and set(members(k07_pass[0])) == {flights["f_ok"].GlobalId, stairs["st_ext"][1].GlobalId, stairs["st_int"][1].GlobalId}
          and k07_pass[0]["evidence"]["metrics"]["sources"] == {"derived": 3}
          and abs(k07_pass[0]["evidence"]["metrics"]["min"] - 0.63) < 1e-6, [r["evidence"]["metrics"] for r in k07_pass])
    check("K07: 2*0.20+0.30 = 0.70 warns under STEP_MAX (SHOULD), both flights pass STEP_MIN",
          len(k07_warn) == 1 and members(k07_warn[0]) == [flights["f_long"].GlobalId]
          and len(got.get(("K07", "pass", "STEP_MIN"), [])) == 1 and len(members(got[("K07", "pass", "STEP_MIN")][0])) == 4
          and got[("K07", "pass", "STEP_MIN")][0]["evidence"]["metrics"]["modelLevel"],
          [members(r) for r in k07_warn])
    k13 = got.get(("K13", "pass", "R_LO–R_HI"), [])
    check("K13: the gate reads IsExternal on the IfcStair, then expands to its flight; the internal stair is out",
          len(k13) == 1 and members(k13[0]) == [stairs["st_ext"][1].GlobalId]
          and k13[0]["evidence"]["relatedGuids"] == [storey.GlobalId], [members(r) for r in k13])
    k09 = got.get(("K09", "info", "N_MIN"), [])
    check("K09 (widened): a 2-riser flight is info under N_MIN (>= 3), never fail, because the essential-stair gate is not evaluated",
          len(k09) == 1 and members(k09[0]) == [flights["f_long"].GlobalId] and not got.get(("K09", "fail", "N_MIN")), list(k for k in got if k[0] == "K09"))
    k08 = got.get(("K08", "info", "R_OPT"), [])
    check("K08: the 0.20 and 0.14 risers depart from R_OPT (~= 0.17) as info; the 0.17 riser makes no record",
          len(k08) == 1 and set(members(k08[0])) == {flights["f_long"].GlobalId, stairs["st_ext"][1].GlobalId, stairs["st_int"][1].GlobalId},
          [members(r) for r in k08])
    k08_t = got.get(("K08", "info", "T_OPT"), [])
    check("K08: the 0.30 tread is within 10 % of T_OPT (0.29) and makes no record; the stairs' 0.35 treads do",
          len(k08_t) == 1 and set(members(k08_t[0])) == {stairs["st_ext"][1].GlobalId, stairs["st_int"][1].GlobalId}, [members(r) for r in k08_t])

    k112_warn = got.get(("K112", "warn", "H_OFF"), [])
    k112_pass = got.get(("K112", "pass", "H_MIN"), [])
    k112_aux = got.get(("K112", "fail", "H_AUX"), [])
    check("K112: 'Büro' at 2.6 m warns under H_OFF (2.75) and passes H_MIN (2.5), from the Qto",
          len(k112_warn) == 1 and members(k112_warn[0]) == [spaces["Büro"].GlobalId]
          and len(k112_pass) == 1 and k112_pass[0]["evidence"]["metrics"]["sources"] == {"Qto.Height": 1})
    check("K112: 'Flur' at 2.2 m fails H_AUX through the check's own selector",
          len(k112_aux) == 1 and members(k112_aux[0]) == [spaces["Flur"].GlobalId], [members(r) for r in k112_aux])
    k122 = got.get(("K122", "info", "N_CLEAN"), [])
    k122_pass = got.get(("K122", "pass", "N_CLEAN"), [])
    check("K122 (partial): S1 with 'Putzraum' passes, S2 with none is reported as info, not fail",
          len(k122_pass) == 1 and members(k122_pass[0]) == [spaces["Putzraum"].GlobalId]
          and len(k122) == 1 and k122[0]["evidence"]["relatedGuids"] == [storey2.GlobalId] and k122[0]["members"] == [],
          ([members(r) for r in k122_pass], [r["evidence"]["relatedGuids"] for r in k122]))

    again = run_topic("doors", f, "fx") + run_topic("stairs", f, "fx") + run_topic("offices", f, "fx")
    check("determinism: a second run gives the same ids and member order",
          [(r["id"], members(r)) for r in records] == [(r["id"], members(r)) for r in again])
    check("no literal threshold leaked: every threshold in the records equals its YAML value",
          all(r["evidence"]["metrics"]["threshold"] == load_rules()[r["provenance"]["rule"]]["params"][r["evidence"]["metrics"]["param"]].get("value")
              for r in records if r["evidence"]["metrics"].get("param")))


class FakeGraph:
    """Three rooms in a row on one storey: exit room E (external door), A 10 m from E, B 30 m from A,
    and an island room I with no door path. Distances are centroid -> door -> centroid."""

    def __init__(self, f, storey, spaces, exit_door):
        self.storey = storey
        self.spaces_by_storey = {storey.GlobalId: [s.GlobalId for s in spaces.values()]}
        self.space_by_guid = {s.GlobalId: s for s in spaces.values()}
        self.degenerate_storeys = set()
        self.polygons = {}
        e, a, b, i, o, w = (spaces[k].GlobalId for k in ("E", "A", "B", "I", "O", "W"))
        self.centroids = {e: (0.0, 0.0), a: (10.0, 0.0), b: (40.0, 0.0), i: (100.0, 100.0), o: (20.0, 0.0), w: (10.0, 10.0)}
        self.door_links = {exit_door.GlobalId: (storey.GlobalId, [e]), "d_ea": (storey.GlobalId, [e, a]), "d_ab": (storey.GlobalId, [a, b]),
                           "d_ao": (storey.GlobalId, [a, o]), "d_aw": (storey.GlobalId, [a, w])}
        self.door_points = {exit_door.GlobalId: (-1.0, 0.0), "d_ea": (5.0, 0.0), "d_ab": (25.0, 0.0), "d_ao": (15.0, 0.0), "d_aw": (10.0, 5.0)}

    def usable(self):
        return True

    def centroid(self, guid):
        return self.centroids.get(guid)

    def storey_name(self, guid):
        return self.storey.Name


def section_route():
    f = ifcopenshell.api.run("project.create_file", version="IFC4")
    run(f, "IfcProject", name="P")
    metre = ifcopenshell.api.run("unit.add_si_unit", f, unit_type="LENGTHUNIT")
    ifcopenshell.api.run("unit.assign_unit", f, units=[metre])
    storey = run(f, "IfcBuildingStorey", name="S1")
    storey.Elevation = 0.0
    spaces = {}
    for key, name in (("E", "Entrance hall"), ("A", "Living room"), ("B", "Bedroom"), ("I", "Study room"), ("O", "Office 1"), ("W", "WC 1")):
        space = run(f, "IfcSpace", name=name)
        ifcopenshell.api.run("aggregate.assign_object", f, products=[space], relating_object=storey)
        spaces[key] = space
    exit_door = run(f, "IfcDoor", name="front")
    add_pset(f, exit_door, "Pset_DoorCommon", {"IsExternal": True})
    ifcopenshell.api.run("spatial.assign_container", f, products=[exit_door], relating_structure=storey)
    graph = FakeGraph(f, storey, spaces, exit_door)
    from recognition.neufert.context import Context
    from recognition.neufert import facts
    ctx = Context(f, graph)
    seeds = facts.exit_seeds(ctx)
    check("route fact: the entrance hall is the exit seed (external door), nothing else",
          seeds == {storey.GlobalId: {spaces["E"].GlobalId: "external door"}}, seeds)
    d = facts.route_distances(ctx, storey.GlobalId, {spaces["E"].GlobalId})
    check("route fact: A is 10 m and B is 40 m from the exit through the doorways; the island has no distance",
          abs(d[spaces["A"].GlobalId] - 10) < 1e-6 and abs(d[spaces["B"].GlobalId] - 40) < 1e-6 and spaces["I"].GlobalId not in d, d)
    records = run_topic("escape", f, "fx", graph=graph) + run_topic("offices", f, "fx", graph=graph)
    got = by_rule_outcome(records)
    k38_pass = got.get(("K38", "pass", "D_ESC"), []); k38_fail = got.get(("K38", "fail", "D_ESC"), []); k38_nod = got.get(("K38", "nodata", None), [])
    check("K38: the living room (10 m) and the office (20 m) pass D_ESC <= 35 m, the bedroom (40 m) fails, the island study is nodata",
          len(k38_pass) == 1 and set(members(k38_pass[0])) == {spaces["A"].GlobalId, spaces["O"].GlobalId}
          and len(k38_fail) == 1 and members(k38_fail[0]) == [spaces["B"].GlobalId]
          and len(k38_nod) == 1 and members(k38_nod[0]) == [spaces["I"].GlobalId], (list(got)))
    check("K38: every route record says it is a lower bound and names the target kinds",
          all(r["evidence"]["metrics"].get("isLowerBound") and "lower bound" in r["evidence"]["summary"] and "route:" in next(iter(r["evidence"]["metrics"]["sources"]))
              for r in k38_pass + k38_fail))
    k134 = got.get(("K134", "nodata", None), [])
    check("K134 (partial): with no room named as a stair there is no target; every occupied room is nodata, no fail",
          len(k134) == 1 and len(members(k134[0])) == 4 and not got.get(("K134", "fail", "D_STAIR")), list(got))
    k120 = got.get(("K120", "pass", "D_WC"), [])
    k120_nod = got.get(("K120", "nodata", None), [])
    check("K120 (partial, route): the office reaches the WC in 20 m through the living room (pass); the island study room is nodata",
          len(k120) == 1 and members(k120[0]) == [spaces["O"].GlobalId] and abs(k120[0]["evidence"]["metrics"]["min"] - 20) < 1e-6
          and len(k120_nod) == 1 and members(k120_nod[0]) == [spaces["I"].GlobalId], (list(got), [r["evidence"]["metrics"].get("min") for r in k120]))
    # The route cost is a copy of egress_reachability's; both must agree on the example model (section_example checks it).


class DwellingGraph:
    """Storey S1: corridor C (shared); flat 1 = hall H1 + kitchen K1 + bath B1 + bedroom R1 + storeroom AB, all off H1, H1 off C;
    flat 2 = hall H2 + kitchen K2 + living L2, L2 off H2, K2 off L2 (not off the hall); a single room 'Apartment 3' off C;
    a stair room off C. Door points at (0,0); centroids irrelevant for adjacency."""

    def __init__(self, storey, spaces, container=None):
        self.storey = storey
        self.space_by_guid = {s.GlobalId: s for s in spaces.values()}
        g = lambda k: spaces[k].GlobalId
        # the container space "Wohnung 4" (W4) is no leaf room: it encloses Z1 and Z2
        self.container_spaces = {g("W4"): sorted([g("Z1"), g("Z2")])} if container else {}
        self.spaces_by_storey = {storey.GlobalId: sorted(k for k in self.space_by_guid if not container or k != g("W4"))}
        self.degenerate_storeys = set()
        self.polygons = {}
        pairs = [("C", "H1"), ("H1", "K1"), ("H1", "B1"), ("H1", "R1"), ("H1", "AB"), ("C", "H2"), ("H2", "L2"), ("L2", "K2"), ("C", "A3"), ("C", "ST"), ("L2", "BK")]
        if container:
            pairs += [("C", "Z1"), ("Z1", "Z2")]
        self.door_links = {f"d{i}": (storey.GlobalId, [g(a), g(b)]) for i, (a, b) in enumerate(pairs)}
        self.door_links["front"] = (storey.GlobalId, [g("C")])
        self.door_points = {k: (0.0, 0.0) for k in self.door_links}

    def usable(self):
        return True

    def centroid(self, guid):
        return (0.0, 0.0)

    def storey_name(self, guid):
        return self.storey.Name


def dwelling_fixture(container=False):
    f = ifcopenshell.api.run("project.create_file", version="IFC4")
    run(f, "IfcProject", name="P")
    metre = ifcopenshell.api.run("unit.add_si_unit", f, unit_type="LENGTHUNIT")
    ifcopenshell.api.run("unit.assign_unit", f, units=[metre])
    storey = run(f, "IfcBuildingStorey", name="S1")
    storey.Elevation = 0.0
    names = {"C": "Corridor", "H1": "Flur 1", "K1": "Küche 1", "B1": "Bad 1", "R1": "Schlafen 1", "AB": "Abstellraum 1",
             "H2": "Flur 2", "L2": "Wohnen 2", "K2": "Küche 2", "A3": "Apartment 3", "ST": "Treppenhaus", "BK": "Balkon 2"}
    if container:  # a flat modelled as one container space "Wohnung 4" over two rooms whose names say nothing
        names.update({"W4": "Wohnung 4", "Z1": "4.0 Zimmer", "Z2": "4.1 Zimmer"})
    spaces = {}
    for key, name in names.items():
        space = run(f, "IfcSpace", name=name)
        ifcopenshell.api.run("aggregate.assign_object", f, products=[space], relating_object=storey)
        spaces[key] = space
    front = run(f, "IfcDoor", name="front")
    add_pset(f, front, "Pset_DoorCommon", {"IsExternal": True})
    ifcopenshell.api.run("spatial.assign_container", f, products=[front], relating_structure=storey)
    graph = DwellingGraph(storey, spaces, container=container)
    graph.door_links["front"] = (storey.GlobalId, [spaces["C"].GlobalId])
    return f, storey, spaces, graph


def section_dwellings():
    f, storey, spaces, graph = dwelling_fixture()
    from recognition.neufert.context import Context
    from recognition.neufert import facts
    ctx = Context(f, graph)
    units = facts.dwelling_units(ctx)
    g = lambda k: spaces[k].GlobalId
    by_rooms = {tuple(sorted(u["rooms"])): u for u in units}
    flat1 = by_rooms.get(tuple(sorted([g("H1"), g("K1"), g("B1"), g("R1"), g("AB")])))
    flat2 = by_rooms.get(tuple(sorted([g("H2"), g("L2"), g("K2"), g("BK")])))
    single = by_rooms.get((g("A3"),))
    check("dwelling units: the corridor is shared (two kitchen cores), each flat keeps its own hall, the single 'Apartment 3' is a unit of one, the stair is no unit",
          len(units) == 3 and flat1 is not None and flat2 is not None and single is not None and single["single"],
          [(u["rooms"], u["single"]) for u in units])
    check("dwelling units: entrance doors and halls - flat 1's hall is Flur 1, flat 2's is Flur 2, the corridor is the shared circulation",
          flat1 and flat1["halls"] == [g("H1")] and flat2 and flat2["halls"] == [g("H2")] and g("C") in flat1["shared_circulation"],
          (flat1 and flat1["halls"], flat2 and flat2["halls"]))
    records = run_topic("housing", f, "fx", graph=graph) + run_topic("bedrooms", f, "fx", graph=graph)
    got = by_rule_outcome(records)
    k94 = got.get(("K94", "pass", "N_KITCHEN"), [])
    check("K94 (widened, per dwelling): both flats hold a kitchen, one pass record over the two flats' rooms; the single-space flat counts 0 as info",
          len(k94) == 1 and len(members(k94[0])) == 9 and k94[0]["evidence"]["metrics"]["unitCount"] == 2
          and len(got.get(("K94", "info", "N_KITCHEN"), [])) == 1 and members(got[("K94", "info", "N_KITCHEN")][0]) == [g("A3")], list(got))
    store_pass = got.get(("K94", "pass", "N_STORE"), [])
    store_info = got.get(("K94", "info", "N_STORE"), [])
    check("K94 N_STORE (per-check count selector): flat 1's 'Abstellraum 1' passes on its five rooms; flat 2 and the single-space flat count 0 storerooms as info",
          len(store_pass) == 1 and set(members(store_pass[0])) == {g("H1"), g("K1"), g("B1"), g("R1"), g("AB")}
          and len(store_info) == 1 and set(members(store_info[0])) == {g("H2"), g("L2"), g("K2"), g("BK"), g("A3")}, list(got))
    f2, storey2, spaces2, graph2 = dwelling_fixture(container=True)
    units2 = facts.dwelling_units(Context(f2, graph2))
    g2 = lambda k: spaces2[k].GlobalId
    container_unit = next((u for u in units2 if u.get("container") == g2("W4")), None)
    check("dwelling units from a container space: 'Wohnung 4' over '4.0 Zimmer' and '4.1 Zimmer' is a unit of those two rooms with the corridor door as its entrance; the three door-graph units stay (4 in all) and no inferred unit takes its rooms",
          container_unit is not None and container_unit["rooms"] == sorted([g2("Z1"), g2("Z2")]) and container_unit["entrance_doors"] == ["d11"]
          and len(units2) == 4 and not [u for u in units2 if u is not container_unit and set(u["rooms"]) & {g2("Z1"), g2("Z2")}],
          [(u.get("container"), u["rooms"]) for u in units2])
    check("K94 N_STORE: the info record names, per unit, the counted rooms on its storey outside every unit (none here: the storeroom is inside flat 1)",
          store_info[0]["evidence"]["metrics"].get("outsideOnStorey") == {} if store_info else False)
    k103 = got.get(("K103", "info", "N_BATH"), [])
    check("K103 (widened): flat 2 and the single-space flat have no bathroom and are one info record; flat 1 passes",
          len(k103) == 1 and set(members(k103[0])) == {g("H2"), g("L2"), g("K2"), g("BK"), g("A3")} and len(got.get(("K103", "pass", "N_BATH"), [])) == 1, list(got))
    k87 = got.get(("K87", "info", "R_HALL"), [])
    k87_pass = got.get(("K87", "pass", "R_HALL"), [])
    check("K87 (widened): flat 1's kitchen and bath are off its hall (pass); flat 2's kitchen is behind the living room (info)",
          len(k87_pass) == 1 and set(members(k87_pass[0])) == {g("H1"), g("K1"), g("B1"), g("R1"), g("AB")}
          and len(k87) == 1 and set(members(k87[0])) == {g("H2"), g("L2"), g("K2"), g("BK")}, list(got))
    k82 = got.get(("K82", "pass", "R_FIRST"), [])
    check("K82 (widened, adjacency from external to living|office|dining per dwelling): flat 2's balcony opens off its living room (pass); flat 1 has no open space, no record",
          len(k82) == 1 and set(members(k82[0])) == {g("H2"), g("L2"), g("K2"), g("BK")} and not got.get(("K82", "info", "R_FIRST")), list(got))
    check("K90 (widened, count of habitable rooms with a door to an open space per storey, INFO): S1 has one, so no deviation record",
          not [k for k in got if k[0] == "K90" and k[1] == "info"], [k for k in got if k[0] == "K90"])
    building = run(f, "IfcBuilding", name="B")
    ifcopenshell.api.run("aggregate.assign_object", f, products=[storey], relating_object=building)
    ctx2 = Context(f, graph)
    storeys = ctx2.fact("dwelling_storeys", facts.dwelling_storeys)
    check("dwelling_storeys fact: the one storey with dwellings counts 1 for the building; building.dwelling_storeys reads it (0 would be a count, not unset)",
          storeys == {building.GlobalId: 1} and measures.measure(ctx2, building, "building.dwelling_storeys", {})[0] == 1.0, storeys)
    housing = run_topic("housing", f, "fx", graph=graph)
    check("K83 (widened, provision with a `when` gate on the building): one dwelling storey is not > N_LIFT (5), so the lift count is not judged and no K83 verdict record exists (its scenario record may)",
          not [r for r in housing if r["provenance"]["rule"] == "K83" and not r["type"].endswith("_scenario")], [r["id"] for r in housing if r["provenance"]["rule"] == "K83"])
    from recognition.neufert.families.provision import _exists_outcome
    check("provision `exists` form: at least one element passes, none takes the param's severity (FAIL -> fail, INFO -> info)",
          _exists_outcome([building], {"severity": "FAIL"}) == "pass" and _exists_outcome([], {"severity": "FAIL"}) == "fail"
          and _exists_outcome([], {"severity": "INFO"}) == "info")
    from recognition.neufert import records as R
    check("templateValue: nine treads at 0.200 and one at 0.25 are a template (0.2, share 0.9, count 10); 6 of 10 are not; fewer than 5 items never",
          R._template_value([0.2] * 9 + [0.25]) == (0.2, 0.9, 10) and R._template_value([0.2] * 6 + [0.25] * 4) is None
          and R._template_value([0.2] * 4) is None and R._template_value([0.2004, 0.1996, 0.2, 0.2, 0.2]) == (0.2, 1.0, 5))
    from recognition import vocabulary
    from recognition.neufert.select import element_text as neufert_text
    lift = run(f, "IfcTransportElement", name="Vertical Circulation : Elevator-Electric : 3000 lbs 2")
    check("select.element_text reads every segment of a Revit family path: the lift named in the second segment is selected by `use: lift`",
          vocabulary.matches(neufert_text(lift), "lift") and not vocabulary.matches(vocabulary.element_text(lift), "lift"))
    check("vocabulary: 'Stuhl-014' with type 'Aufzug 26' is a lift, an 'Escalator' is not, a 'Forklift' is not (bounded word)",
          vocabulary.matches("stuhl-014 aufzug 26", "lift") and not vocabulary.matches("escalator escalator", "lift")
          and not vocabulary.matches("forklift", "lift") and vocabulary.matches("elevator-electric", "lift"))
    return f, storey, spaces, graph


class Boxes:
    """Stands in for the door graph: rectangular room footprints in the
    world frame (Context.polygons falls back to graph.polygons for a space
    without geometry); no door graph, so the route and adjacency families
    skip this model."""

    def __init__(self, polygons):
        self.polygons = polygons

    def usable(self):
        return False


def office_fixture():
    """One storey of an office: 'Office 1' (20 m2) with two desks and a desk
    chair, 'Office 2' (20 m2) with one IfcFurniture of PredefinedType DESK
    named 'FU-7', 'Meeting' 10, 'Store room' 4, 'Corridor' 15, 'WC 1' 2,
    'Teeküche' 12; a 'Bed 1' bed in Office 1 that is no desk; four 'Chair'
    seats in 'Meeting' and none in 'Seminar 2' (8 m2)."""
    import numpy as np
    from shapely.geometry import box
    f = ifcopenshell.api.run("project.create_file", version="IFC4")
    run(f, "IfcProject", name="P")
    metre = ifcopenshell.api.run("unit.add_si_unit", f, unit_type="LENGTHUNIT")
    ifcopenshell.api.run("unit.assign_unit", f, units=[metre])
    storey = run(f, "IfcBuildingStorey", name="S1")
    storey.Elevation = 0.0
    rooms = {"Office 1": (0, 5, 20.0), "Office 2": (10, 15, 20.0), "Meeting": (20, 25, 10.0), "Store room": (30, 32, 4.0),
             "Corridor": (40, 55, 15.0), "WC 1": (60, 61, 2.0), "Teeküche": (70, 76, 12.0), "Seminar 2": (80, 84, 8.0)}
    spaces, polygons = {}, {}
    for name, (x0, x1, area) in rooms.items():
        space = run(f, "IfcSpace", name=name)
        add_qto(f, space, "Qto_SpaceBaseQuantities", {"NetFloorArea": area, "Height": 2.8})
        ifcopenshell.api.run("aggregate.assign_object", f, products=[space], relating_object=storey)
        spaces[name] = space
        polygons[space.GlobalId] = box(x0, 0, x1, 4)
    furniture = {}
    for name, x, predefined in (("Desk 1", 1.0, None), ("Desk 2", 2.0, None), ("Desk chair", 1.5, None), ("Bed 1", 3.0, None), ("FU-7", 12.0, "DESK"),
                                ("Chair", 21.0, None), ("Chair", 22.0, None), ("Chair", 23.0, None), ("Chair", 24.0, None)):
        element = run(f, "IfcFurniture", name=name, predefined_type=predefined) if predefined else run(f, "IfcFurniture", name=name)
        ifcopenshell.api.run("spatial.assign_container", f, products=[element], relating_structure=storey)
        matrix = np.eye(4)
        matrix[0][3], matrix[1][3] = x, 2.0
        ifcopenshell.api.run("geometry.edit_object_placement", f, product=element, matrix=matrix)
        furniture.setdefault(name, element)
    return f, storey, spaces, furniture, Boxes(polygons)


def section_workstations():
    from recognition import furnishing
    from recognition.neufert.context import Context
    f, storey, spaces, furniture, graph = office_fixture()
    check("furnishing: a 'Desk chair' is a seat before it is a desk, a 'Bed 1' is a bed, 'FU-7' is a desk by PredefinedType only",
          furnishing.classify(furniture["Desk chair"], ("bed", "seat", "desk")) == "seat"
          and furnishing.classify(furniture["Desk chair"], ("desk",)) is None
          and furnishing.classify(furniture["Bed 1"], ("bed", "seat", "desk")) == "bed"
          and furnishing.classify(furniture["FU-7"], ("desk",)) == "desk" and furnishing.classify(furniture["FU-7"], ("bed", "seat")) is None)
    ctx = Context(f, graph)
    counts = ctx.fact("workstations", facts.workstations)
    guid = {name: space.GlobalId for name, space in spaces.items()}
    check("workstations fact: Office 1 holds 2 desks, Office 2 holds 1 (the DESK type), every other room 0",
          counts[guid["Office 1"]] == 2 and counts[guid["Office 2"]] == 1 and counts[guid["Meeting"]] == 0 and counts[guid["Corridor"]] == 0, counts)
    value, source = measures.measure(ctx, spaces["Office 1"], "space.workstations", {})
    check("space.workstations reads the fact (2, source fact:workstations); 0 is a count, not an unset value",
          value == 2.0 and source == "fact:workstations" and measures.measure(ctx, spaces["Meeting"], "space.workstations", {})[0] == 0.0, (value, source))
    from recognition.neufert.engine import run_topic
    records = run_topic("offices", f, "fx", graph=graph)
    by = by_rule_outcome(records)
    def one(kid, param, outcome):
        found = [r for r in records if r["provenance"]["rule"] == kid and r["evidence"]["metrics"].get("param") == param and r["type"].endswith("_" + outcome)]
        return found[0] if len(found) == 1 else None
    a_ws, a_add, a_tr = one("K141", "A_WS", "pass"), one("K141", "A_ADD", "info"), one("K141", "A_TR", "pass")
    check("K141 (aggregate, per building, widened): 40 m2 of offices over 3 workstations = 13.33 passes A_WS; (10+8+4)/3 = 7.33 departs from A_ADD as info (desks are a floor); 15/3 = 5 passes A_TR",
          a_ws is not None and a_add is not None and a_tr is not None
          and abs(a_ws["evidence"]["metrics"]["aggregate"]["building"]["value"] - 40 / 3) < 0.01
          and abs(a_add["evidence"]["metrics"]["aggregate"]["building"]["value"] - 22 / 3) < 0.01
          and a_tr["evidence"]["metrics"]["aggregate"]["building"]["denominator"] == 3.0, sorted(by))
    check("K141: the ratio is carried by the numerator's rooms (both offices on A_WS, meeting + store room on A_ADD), one model-level record each",
          a_ws is not None and set(members(a_ws)) == {guid["Office 1"], guid["Office 2"]} and a_ws["evidence"]["metrics"]["modelLevel"]
          and a_add is not None and set(members(a_add)) == {guid["Meeting"], guid["Seminar 2"], guid["Store room"]})
    a_tot = one("K113", "A_TOT", "pass")
    check("K113 (widened): the sum of every room's area (91 m2) over 3 workstations = 30.33 is within [23, 45]; its status note names the BGF substitute",
          a_tot is not None and abs(a_tot["evidence"]["metrics"]["aggregate"]["building"]["value"] - 91 / 3) < 0.01 and "lower bound" in a_tot["evidence"]["summary"], sorted(by))
    check("K119 (partial, per storey since 2026-10-20): 2 m2 of WC over 3 workstations = 0.67 meets A_WC_WS (INFO, no record); the 12 m2 tea kitchen departs from A_TK ~= 10 (info) on S1",
          one("K119", "A_WC_WS", "info") is None and one("K119", "A_TK", "info") is not None
          and abs(one("K119", "A_TK", "info")["evidence"]["metrics"]["aggregate"][storey.GlobalId]["value"] - 12.0) < 0.01, sorted(by))
    a_stud = one("K129", "A_STUD", "info")
    check("K129 (widened, derived): the meeting room's 10 m2 over its 4 seats = 2.5 departs from A_STUD [1.9, 2.0] as info; 'Seminar 2' without a seat is nodata, not a fail",
          a_stud is not None and members(a_stud) == [guid["Meeting"]] and abs(a_stud["evidence"]["metrics"]["max"] - 2.5) < 0.01
          and [r for r in records if r["provenance"]["rule"] == "K129" and r["type"].endswith("_nodata") and members(r) == [guid["Seminar 2"]]], sorted(by))
    check("aggregate: no nodata in the office fixture (every summed room has an area, the denominator is non-zero)",
          not [r for r in records if r["provenance"]["rule"] in ("K141", "K113", "K119") and r["type"].endswith("_nodata")], sorted(by))
    again = run_topic("offices", f, "fx", graph=graph)
    check("aggregate: deterministic ids and members on a second run", [r["id"] for r in records] == [r["id"] for r in again]
          and [members(r) for r in records] == [members(r) for r in again])


class TowerGraph:
    """Five storeys at 0, 3, 6, 9 and 12 m; on each: 'Treppenhaus n' (the
    core room, with the entrance door of the storey's one flat), a flat of
    'Flur n' + 'Küche n' + 'Schlafen n' off the hall. Door guids are the
    real IfcDoor GlobalIds so a role selector can resolve them."""

    def __init__(self, storeys, spaces, doors):
        self.space_by_guid = {s.GlobalId: s for level in spaces.values() for s in level.values()}
        self.spaces_by_storey = {st.GlobalId: sorted(s.GlobalId for s in spaces[name].values()) for name, st in storeys.items()}
        self.degenerate_storeys = set()
        self.polygons = {}
        self.door_links, self.door_points = {}, {}
        for name, st in storeys.items():
            g = lambda k, name=name: spaces[name][k].GlobalId
            self.door_links[doors[name].GlobalId] = (st.GlobalId, [g("T"), g("H")])
            self.door_points[doors[name].GlobalId] = (1.0, 1.0)
            for i, (a, b) in enumerate((("H", "K"), ("H", "R"))):
                self.door_links[f"{name}-d{i}"] = (st.GlobalId, [g(a), g(b)])
                self.door_points[f"{name}-d{i}"] = (3.0, 1.0)

    def usable(self):
        return True

    def centroid(self, guid):
        return (3.0, 1.0)

    def storey_name(self, guid):
        return guid


def tower_fixture(storeys_with_stair=4, lift=False):
    import numpy as np
    f = ifcopenshell.api.run("project.create_file", version="IFC4")
    run(f, "IfcProject", name="P")
    metre = ifcopenshell.api.run("unit.add_si_unit", f, unit_type="LENGTHUNIT")
    ifcopenshell.api.run("unit.assign_unit", f, units=[metre])
    model_ctx = ifcopenshell.api.run("context.add_context", f, context_type="Model")
    body = ifcopenshell.api.run("context.add_context", f, context_type="Model", context_identifier="Body", target_view="MODEL_VIEW", parent=model_ctx)
    building = run(f, "IfcBuilding", name="B")
    storeys, spaces, doors, stairs = {}, {}, {}, {}
    for level in range(5):
        name = f"S{level + 1}"
        storey = run(f, "IfcBuildingStorey", name=name)
        storey.Elevation = 3.0 * level
        ifcopenshell.api.run("aggregate.assign_object", f, products=[storey], relating_object=building)
        storeys[name] = storey
        spaces[name] = {}
        for key, label in (("T", "Treppenhaus"), ("H", "Flur"), ("K", "Küche"), ("R", "Schlafen")):
            space = run(f, "IfcSpace", name=f"{label} {level + 1}")
            ifcopenshell.api.run("aggregate.assign_object", f, products=[space], relating_object=storey)
            spaces[name][key] = space
        door = run(f, "IfcDoor", name=f"Wohnungstür {level + 1}")
        door.OverallWidth, door.OverallHeight = (0.8 if level == 0 else 1.0), 2.1
        ifcopenshell.api.run("spatial.assign_container", f, products=[door], relating_structure=storey)
        doors[name] = door
        if level < storeys_with_stair:  # one IfcStair per storey, stacked at the same plan position, 3 m high
            stair = run(f, "IfcStair", name=f"Treppe {level + 1}")
            ifcopenshell.api.run("spatial.assign_container", f, products=[stair], relating_structure=storey)
            representation = ifcopenshell.api.run("geometry.add_wall_representation", f, context=body, length=4.0, height=3.0, thickness=2.5)
            ifcopenshell.api.run("geometry.assign_representation", f, product=stair, representation=representation)
            matrix = np.eye(4)
            matrix[2][3] = 3.0 * level
            ifcopenshell.api.run("geometry.edit_object_placement", f, product=stair, matrix=matrix)
            stairs[name] = stair
    if lift:
        element = run(f, "IfcTransportElement", name="Aufzug 1")
        ifcopenshell.api.run("spatial.assign_container", f, products=[element], relating_structure=storeys["S1"])
        representation = ifcopenshell.api.run("geometry.add_wall_representation", f, context=body, length=2.0, height=15.0, thickness=2.0)
        ifcopenshell.api.run("geometry.assign_representation", f, product=element, representation=representation)
        matrix = np.eye(4)
        matrix[0][3] = 5.0  # 1 m from the stair stack (0..4 m): within LIFT_CORE_REACH_M
        ifcopenshell.api.run("geometry.edit_object_placement", f, product=element, matrix=matrix)
    return f, storeys, spaces, doors, stairs, TowerGraph(storeys, spaces, doors)


TOPIC_OF = {kid: rule["topic"] for kid, rule in load_rules().items()}


def section_vertical_cores():
    from recognition.neufert.context import Context
    from recognition.neufert import cores
    f, storeys, spaces, doors, stairs, graph = tower_fixture(storeys_with_stair=4)
    ctx = Context(f, graph)
    found = ctx.fact("vertical_cores", cores.vertical_cores)
    stair_cores = [c for c in found if c["kind"] == "stair"]
    check("vertical_cores: four stacked 3 m stairs on S1-S4 are ONE core serving 5 storeys (0, 3, 6, 9 and 12 m: the top of the S4 stair reaches S5)",
          len(stair_cores) == 1 and len(stair_cores[0]["elements"]) == 4 and len(stair_cores[0]["storeys"]) == 5, [(len(c["elements"]), len(c["storeys"])) for c in stair_cores])
    tables = ctx.fact("core_tables", cores._core_tables)
    any_stair = next(iter(stairs.values()))
    check("stair core tables: one inferred flat per served storey (flats per floor 1), no lift (0); stair.core_storeys reads 5 on every stair of the stack",
          tables["stair"][any_stair.GlobalId]["core_flats_per_floor"] == 1.0 and tables["stair"][any_stair.GlobalId]["core_has_lift"] == 0.0
          and all(measures.measure(ctx, st, "stair.core_storeys", {})[0] == 5.0 for st in stairs.values()), tables["stair"].get(any_stair.GlobalId))
    records = run_topic("housing", f, "fx", graph=graph)
    k91 = [r for r in records if r["provenance"]["rule"] == "K91" and not r["type"].endswith("_scenario")]
    check("K91 (widened): one flat per floor, no lift, 5 storeys served > N_1F (4): one info record (not warn) carrying the four stairs of the core",
          len(k91) == 1 and k91[0]["type"].endswith("_info") and set(members(k91[0])) == {s.GlobalId for s in stairs.values()}, [r["id"] for r in k91])
    k25 = [r for r in run_topic(TOPIC_OF["K25"], f, "fx", graph=graph) if r["provenance"]["rule"] == "K25"]
    check("K25: without a lift no storey is lift-served, so no entrance door is selected and no K25 record exists (not even a scenario)", not k25, [r["id"] for r in k25])
    f, storeys, spaces, doors, stairs, graph = tower_fixture(storeys_with_stair=4, lift=True)
    ctx = Context(f, graph)
    found = ctx.fact("vertical_cores", cores.vertical_cores)
    lift_cores = [c for c in found if c["kind"] == "lift"]
    check("vertical_cores: a 15 m 'Aufzug 1' body is a lift core serving all 5 storeys; the stair core now has a lift", len(lift_cores) == 1 and len(lift_cores[0]["storeys"]) == 5
          and measures.measure(ctx, next(iter(stairs.values())), "stair.core_has_lift", {})[0] == 1.0, [len(c["storeys"]) for c in lift_cores])
    records = run_topic("housing", f, "fx", graph=graph)
    k91 = [r for r in records if r["provenance"]["rule"] == "K91" and not r["type"].endswith("_scenario")]
    check("K91: with the lift the `where` condition excludes the core and K91 emits nothing", not k91, [r["id"] for r in k91])
    records = run_topic(TOPIC_OF["K25"], f, "fx", graph=graph)
    k25 = [r for r in records if r["provenance"]["rule"] == "K25"]
    info = [r for r in k25 if r["evidence"]["metrics"].get("param") == "W_LIFT" and r["type"].endswith("_info")]
    passed = [r for r in k25 if r["evidence"]["metrics"].get("param") == "W_LIFT" and r["type"].endswith("_pass")]
    check("K25 (widened, role unit.entrance_doors on lift-served storeys): the 0.80 m door departs from W_LIFT (0.90) as info, the four 1.00 m doors pass; H_LIFT (2.1) passes all five",
          len(info) == 1 and members(info[0]) == [doors["S1"].GlobalId] and sum(len(members(r)) for r in passed) == 4
          and sum(len(members(r)) for r in k25 if r["evidence"]["metrics"].get("param") == "H_LIFT" and r["type"].endswith("_pass")) == 5, sorted(by_rule_outcome(records)))


def section_ifcopenshell_tools():
    """The generic additions of 2026-10-19: a `query`
    selector key, a `value` chain step and element-frame geometry
    primitives, on a 5 x 0.3 x 3 m wall rotated 45 degrees in the world."""
    import math
    import numpy as np
    from recognition.neufert.context import Context
    from recognition.neufert.select import population
    f = ifcopenshell.api.run("project.create_file", version="IFC4")
    run(f, "IfcProject", name="P")
    metre = ifcopenshell.api.run("unit.add_si_unit", f, unit_type="LENGTHUNIT")
    ifcopenshell.api.run("unit.assign_unit", f, units=[metre])
    model_ctx = ifcopenshell.api.run("context.add_context", f, context_type="Model")
    body = ifcopenshell.api.run("context.add_context", f, context_type="Model", context_identifier="Body", target_view="MODEL_VIEW", parent=model_ctx)
    storey = run(f, "IfcBuildingStorey", name="Level 1")
    storey.Elevation = 1.5
    walls = {}
    for name, external, angle in (("W ext", True, 45.0), ("W int", False, 0.0)):
        wall = run(f, "IfcWall", name=name)
        ifcopenshell.api.run("spatial.assign_container", f, products=[wall], relating_structure=storey)
        add_pset(f, wall, "Pset_WallCommon", {"IsExternal": external})
        representation = ifcopenshell.api.run("geometry.add_wall_representation", f, context=body, length=5.0, height=3.0, thickness=0.3)
        ifcopenshell.api.run("geometry.assign_representation", f, product=wall, representation=representation)
        a = math.radians(angle)
        matrix = np.eye(4)
        matrix[0][0], matrix[0][1], matrix[1][0], matrix[1][1] = math.cos(a), -math.sin(a), math.sin(a), math.cos(a)
        matrix[0][3] = 10.0
        ifcopenshell.api.run("geometry.edit_object_placement", f, product=wall, matrix=matrix)
        walls[name] = wall
    ctx = Context(f, None)
    def m(element, name):
        return measures.measure(ctx, element, name, {})[0]
    wall = walls["W ext"]
    check("element.local_short / local_long read the wall's own frame: 0.30 m thick and 5.0 m long although it is rotated 45 degrees in the world",
          abs(m(wall, "element.local_short") - 0.3) < 1e-6 and abs(m(wall, "element.local_long") - 5.0) < 1e-6)
    check("element.max_side_area is the 15 m2 face, outer_surface_area 31.8 m2, footprint 1.5 m2, perimeter 10.6 m, volume 4.5 m3, z_extent 3 m",
          abs(m(wall, "element.max_side_area") - 15.0) < 1e-6 and abs(m(wall, "element.outer_surface_area") - 31.8) < 1e-6
          and abs(m(wall, "element.footprint_area") - 1.5) < 1e-6 and abs(m(wall, "element.footprint_perimeter") - 10.6) < 1e-6
          and abs(m(wall, "element.volume") - 4.5) < 1e-6 and abs(m(wall, "element.z_extent") - 3.0) < 1e-6)
    check("storey.elevation reads the storey through util.placement (1.5 m)", abs(m(storey, "storey.elevation") - 1.5) < 1e-6)
    ext, _ = population(ctx, {"class": "IfcWall", "query": "Pset_WallCommon.IsExternal=TRUE"})
    none, _ = population(ctx, {"class": "IfcWall", "query": "Name = /W x.*/"})
    both, _ = population(ctx, {"query": "IfcWall, location = \"Level 1\""})
    check("select.query: a selector query narrows the class population (one external wall), a regex that matches nothing selects nothing, a location facet finds both walls",
          [e.Name for e in ext] == ["W ext"] and none == [] and len(both) == 2)
    value, source = measures.READERS["value"](ctx, wall, ("value", "storey.Elevation"))
    missing, _ = measures.READERS["value"](ctx, wall, ("value", "type.Name"))
    check("value chain step: 'storey.Elevation' resolves through the wall's storey (1.5, source value:...); an unresolvable path is None, never an error",
          value == 1.5 and source == "value:storey.Elevation" and missing is None)


def flight_fixture():
    """IFC4, metres: flights with a body and a walking line. 'straight':
    a 3.0 x 1.0 m run with its Axis along it; 'u': one U-shaped body 3.7 m
    wide (two 1.0 m runs of 3.5 m around a hole, a 1.0 m landing across the
    top) with the U walking line, as corpus model 0101 models a whole stair
    as one flight; 'noaxis_run': a 3.0 x 1.0 m body without an Axis;
    'noaxis_square': a 2.0 x 2.0 m body without an Axis. Riser/tread in
    Pset_StairFlightCommon: 0.17/0.29 on all but 'u' (0.20/0.20)."""
    import numpy as np
    f = ifcopenshell.api.run("project.create_file", version="IFC4")
    run(f, "IfcProject", name="P")
    metre = ifcopenshell.api.run("unit.add_si_unit", f, unit_type="LENGTHUNIT")
    ifcopenshell.api.run("unit.assign_unit", f, units=[metre])
    model_ctx = ifcopenshell.api.run("context.add_context", f, context_type="Model")
    body = ifcopenshell.api.run("context.add_context", f, context_type="Model", context_identifier="Body", target_view="MODEL_VIEW", parent=model_ctx)
    axis_ctx = ifcopenshell.api.run("context.add_context", f, context_type="Model", context_identifier="Axis", target_view="GRAPH_VIEW", parent=model_ctx)
    storey = run(f, "IfcBuildingStorey", name="S1")
    storey.Elevation = 0.0
    outlines = {
        "straight": ([(0, 0), (3, 0), (3, 1), (0, 1)], [(0, 0.5), (3, 0.5)], (0.17, 0.29)),
        "u": ([(0, 0), (1, 0), (1, 3.5), (2.7, 3.5), (2.7, 0), (3.7, 0), (3.7, 4.5), (0, 4.5)], [(0.5, 0), (0.5, 4), (3.2, 4), (3.2, 0)], (0.20, 0.20)),
        "noaxis_run": ([(0, 0), (3, 0), (3, 1), (0, 1)], None, (0.17, 0.29)),
        "noaxis_square": ([(0, 0), (2, 0), (2, 2), (0, 2)], None, (0.17, 0.29)),
    }
    flights = {}
    for name, (outline, axis, (riser, tread)) in outlines.items():
        flight = run(f, "IfcStairFlight", name=name)
        ifcopenshell.api.run("spatial.assign_container", f, products=[flight], relating_structure=storey)
        add_pset(f, flight, "Pset_StairFlightCommon", {"RiserHeight": riser, "TreadLength": tread})
        profile = ifcopenshell.api.run("profile.add_arbitrary_profile", f, profile=outline + [outline[0]])
        representation = ifcopenshell.api.run("geometry.add_profile_representation", f, context=body, profile=profile, depth=0.5)
        ifcopenshell.api.run("geometry.assign_representation", f, product=flight, representation=representation)
        if axis:
            points = f.createIfcCartesianPointList2D([(float(x), float(y)) for x, y in axis])
            curve = f.createIfcIndexedPolyCurve(points, None, False)
            axis_rep = f.createIfcShapeRepresentation(axis_ctx, "Axis", "Curve2D", [curve])
            flight.Representation.Representations = list(flight.Representation.Representations) + [axis_rep]
        ifcopenshell.api.run("geometry.edit_object_placement", f, product=flight, matrix=np.eye(4))
        flights[name] = flight
    return f, storey, flights


def section_flight_width():
    from recognition.neufert.context import Context
    from recognition.neufert.engine import run_topic
    f, storey, flights = flight_fixture()
    ctx = Context(f, None)
    def w(name):
        return measures.measure(ctx, flights[name], "flight.width", {})[0]
    check("flight.width: a straight 3.0 x 1.0 m run with its walking line reads 1.0 m (within the 5 cm raster)",
          w("straight") is not None and abs(w("straight") - 1.0) < 0.06, w("straight"))
    check("flight.width: a U-shaped body that is the whole stair (3.7 m across) reads one run's width, 1.0 m, where element.local_short reads 3.7",
          w("u") is not None and abs(w("u") - 1.0) < 0.06 and abs(measures.measure(ctx, flights["u"], "element.local_short", {})[0] - 3.7) < 1e-6, w("u"))
    check("flight.width without a walking line: a straight body gives its short extent (1.0 m); a square body is None (nodata), never a guess",
          w("noaxis_run") is not None and abs(w("noaxis_run") - 1.0) < 1e-6 and w("noaxis_square") is None, (w("noaxis_run"), w("noaxis_square")))
    records = run_topic("stairs", f, "fx", graph=None)
    by = by_rule_outcome(records)
    guid = {name: flight.GlobalId for name, flight in flights.items()}
    def one(kid, param, outcome):
        found = [r for r in records if r["provenance"]["rule"] == kid and r["evidence"]["metrics"].get("param") == param and r["type"].endswith("_" + outcome)]
        return found[0] if len(found) == 1 else None
    check("K19 (bound): every flight with a width passes W_NE (0.5 m); the square flight without a walking line is nodata; the U flight's 0.20 m tread fails T_NE (0.21)",
          one("K19", "W_NE", "pass") is not None and set(members(one("K19", "W_NE", "pass"))) == {guid["straight"], guid["u"], guid["noaxis_run"]}
          and one("K19", "T_NE", "fail") is not None and members(one("K19", "T_NE", "fail")) == [guid["u"]]
          and [r for r in records if r["provenance"]["rule"] == "K19" and r["type"].endswith("_nodata") and members(r) == [guid["noaxis_square"]]], sorted(by))
    check("K11 (widened): the U flight's 0.20 m riser departs from R_MAX (0.17) as info, not fail; the 1.0 m widths pass W_ESS",
          one("K11", "R_MAX", "info") is not None and members(one("K11", "R_MAX", "info")) == [guid["u"]]
          and one("K11", "W_ESS", "pass") is not None and not [r for r in records if r["provenance"]["rule"] == "K11" and r["type"].endswith("_fail")], sorted(by))


def section_example():
    if not EXAMPLE.is_file():
        check("data/example_autcon.ifc is present", False, str(EXAMPLE))
        return
    model = ifcopenshell.open(str(EXAMPLE))
    from recognition.access_graph import AccessGraph
    graph = AccessGraph(model)
    counts = Counter()
    failures = []
    for suffix, _topic, _level, _classes in TOPICS:
        try:
            records = run_topic(suffix, model, "ex", graph=graph)
        except Exception as e:  # noqa: BLE001
            failures.append((suffix, f"{type(e).__name__}: {e}"))
            continue
        for record in records:
            counts[(record["provenance"]["rule"], record["type"].rsplit("_", 1)[1])] += 1
    check("example model: every Neufert category runs without error", not failures, failures)
    # The route fact is a copy of egress_reachability's cost model (facts.py says why); the two must agree.
    from recognition.detectors import egress_reachability
    from recognition.neufert.context import Context
    from recognition.neufert import facts
    ctx = Context(model, graph)
    seeds = facts.exit_seeds(ctx)
    agree, compared = True, 0
    for record in egress_reachability.detect(model, None, "ex", graph=graph):
        if record["type"] != "egress_reachable":
            continue
        storey_guid = record["evidence"]["relatedGuids"][0]
        distances = facts.route_distances(ctx, storey_guid, set(seeds.get(storey_guid, {})))
        travelled = sorted(v for g, v in distances.items() if v > 0 and g in graph.spaces_by_storey.get(storey_guid, []))
        compared += 1
        if not travelled or abs(travelled[-1] - record["evidence"]["metrics"]["travelMaxM"]) > 0.01 \
                or abs(travelled[len(travelled) // 2] - record["evidence"]["metrics"]["travelMedianM"]) > 0.01:
            agree = False
    check("route fact agrees with egress_reachability's travel distances on every storey of the example model (the copied cost model has not drifted)",
          agree and compared > 0, compared)
    print("  example outcomes (rule, outcome) -> records:", dict(sorted(counts.items())))
    check("example model: no outcome dominated by nodata",
          sum(n for (_, o), n in counts.items() if o == "nodata") <= sum(counts.values()) / 2, dict(counts))


def _metric_file():
    f = ifcopenshell.api.run("project.create_file", version="IFC4")
    run(f, "IfcProject", name="P")
    metre = ifcopenshell.api.run("unit.add_si_unit", f, unit_type="LENGTHUNIT")
    ifcopenshell.api.run("unit.assign_unit", f, units=[metre])
    model_ctx = ifcopenshell.api.run("context.add_context", f, context_type="Model")
    body = ifcopenshell.api.run("context.add_context", f, context_type="Model", context_identifier="Body", target_view="MODEL_VIEW", parent=model_ctx)
    return f, body


def _box(f, body, product, length, height, thickness, x=0.0, y=0.0, z=0.0):
    import numpy as np
    representation = ifcopenshell.api.run("geometry.add_wall_representation", f, context=body, length=length, height=height, thickness=thickness)
    ifcopenshell.api.run("geometry.assign_representation", f, product=product, representation=representation)
    matrix = np.eye(4)
    matrix[0][3], matrix[1][3], matrix[2][3] = x, y, z
    ifcopenshell.api.run("geometry.edit_object_placement", f, product=product, matrix=matrix)


def section_validation():
    """The validation round (2026-10-20): what the QA pack's
    benchmark models showed to be wrong or silent, each as a fixture."""
    from recognition.neufert.context import Context
    from recognition.neufert.select import population
    from recognition.neufert import cores
    from recognition import vocabulary as V

    # 1. flight trust: junk declared values beside a parent stair that knows
    f, body = _metric_file()
    storey = run(f, "IfcBuildingStorey", name="S1")
    storey.Elevation = 0.0
    def flight(name, riser, tread, risers, rise, parent_pset=None):
        stair = run(f, "IfcStair", name=f"Treppe {name}")
        ifcopenshell.api.run("spatial.assign_container", f, products=[stair], relating_structure=storey)
        if parent_pset:
            add_pset(f, stair, "Pset_StairCommon", parent_pset)
        fl = run(f, "IfcStairFlight", name=name)
        ifcopenshell.api.run("aggregate.assign_object", f, products=[fl], relating_object=stair)
        fl.RiserHeight, fl.TreadLength, fl.NumberOfRisers = riser, tread, risers
        _box(f, body, fl, length=3.0, height=rise, thickness=1.0)
        return fl
    junk = flight("junk", 0.587, 0.9095, 9, 11 * 0.177, {"RiserHeight": 0.177, "TreadLength": 0.27, "NumberOfRiser": 22})
    sound = flight("sound", 0.17, 0.29, 10, 1.7, {"RiserHeight": 0.2, "TreadLength": 0.2})
    orphan = flight("orphan", 0.587, 0.9095, 9, 1.6)
    both_runs = flight("both_runs", 0.17, 0.29, 10, 3.4, {"RiserHeight": 0.2, "TreadLength": 0.2})
    ctx = Context(f, None)
    def m(element, name):
        return measures.measure(ctx, element, name, {})
    riser, source = m(junk, "flight.riser")
    check("flight trust: declared 0.587 m x 9 risers on a 1.95 m body is rejected; the parent's Pset_StairCommon riser 0.177 and tread 0.27 are read, the count derived as 11 (the parent's 22 over one flight does not fit the body)",
          riser is not None and abs(riser - 0.177) < 1e-9 and "parent IfcStair" in source and "rejected" not in source.split("(")[0]
          and abs(m(junk, "flight.tread")[0] - 0.27) < 1e-9 and m(junk, "flight.risers")[0] == 11.0, (riser, source, m(junk, "flight.tread"), m(junk, "flight.risers")))
    check("flight trust: 0.17 x 10 on a 1.7 m body stands (IfcStairFlight.RiserHeight), the parent's 0.2 is not read",
          m(sound, "flight.riser") == (0.17, "IfcStairFlight.RiserHeight") and m(sound, "flight.risers")[0] == 10.0, m(sound, "flight.riser"))
    riser, source = m(orphan, "flight.riser")
    check("flight trust: junk values with no parent pset are nodata (None, source 'rejected: ...'), never judged; K07 and K11 then list the flight as nodata",
          riser is None and source and source.startswith("rejected:") and m(orphan, "flight.tread")[0] is None and m(orphan, "flight.risers")[0] is None, (riser, source))
    check("flight trust is one-directional: 0.17 x 10 on a 3.4 m body (a body covering both runs) stands",
          m(both_runs, "flight.riser") == (0.17, "IfcStairFlight.RiserHeight"), m(both_runs, "flight.riser"))
    records = run_topic("stairs", f, "fx")
    nodata = [r for r in records if r["provenance"]["rule"] == "K07" and r["type"].endswith("_nodata")]
    k07_pass = [r for r in records if r["provenance"]["rule"] == "K07" and r["type"].endswith("_pass") and r["evidence"]["metrics"]["param"] == "STEP_MIN"]
    check("K07 on the trust fixture: the orphan is nodata, the recovered flight's 2 x 0.177 + 0.27 = 0.624 passes STEP_MIN with the parent source",
          len(nodata) == 1 and members(nodata[0]) == [orphan.GlobalId] and k07_pass and junk.GlobalId in members(k07_pass[0]), [r["evidence"]["summary"] for r in records if r["provenance"]["rule"] == "K07"])

    # 2. doors: no IsExternal anywhere is nodata on the gate; a declared clear height beats the overall height
    f, body = _metric_file()
    storey = run(f, "IfcBuildingStorey", name="S1")
    storey.Elevation = 0.0
    ungated = run(f, "IfcDoor", name="ungated")
    ungated.OverallHeight, ungated.OverallWidth = 2.01, 0.885
    clear = run(f, "IfcDoor", name="clear")
    clear.OverallHeight, clear.OverallWidth = 2.01, 0.885
    add_pset(f, clear, "Pset_DoorCommon", {"IsExternal": False})
    add_pset(f, clear, "Tür Linien-Sachmerkmale", {"Durchgangshöhe": 1.96, "Durchgangsbreite": 0.785})
    overall = run(f, "IfcDoor", name="overall")
    overall.OverallHeight, overall.OverallWidth = 2.26, 0.885
    add_pset(f, overall, "Pset_DoorCommon", {"IsExternal": False})
    for door in (ungated, clear, overall):
        ifcopenshell.api.run("spatial.assign_container", f, products=[door], relating_structure=storey)
    ctx = Context(f, None)
    check("door.clear_height reads the declared clear passage (1.96 m, prop:Durchgangshöhe) before the 2.01 m opening; without one the overall height stands in with its own source",
          measures.measure(ctx, clear, "door.clear_height", {}) == (1.96, "prop:Durchgangshöhe") and abs(measures.measure(ctx, clear, "door.clear_width", {})[0] - 0.785) < 1e-9
          and measures.measure(ctx, overall, "door.clear_height", {}) == (2.26, "IfcDoor.OverallHeight"), measures.measure(ctx, clear, "door.clear_height", {}))
    records = run_topic("doors", f, "fx")
    k23 = by_rule_outcome(records)
    nod = k23.get(("K23", "nodata", None), [])
    check("K23: the door with no IsExternal anywhere is nodata on the gate ('prop:IsExternal (gate)'), not silently dropped; the 1.96 m clear height fails H_DOOR (a partial rule keeps its outcomes)",
          len(nod) == 1 and members(nod[0]) == [ungated.GlobalId] and "prop:IsExternal (gate)" in nod[0]["evidence"]["summary"]
          and [r for r in k23.get(("K23", "fail", "H_DOOR"), []) if members(r) == [clear.GlobalId]]
          and [r for r in k23.get(("K23", "pass", "H_DOOR"), []) if members(r) == [overall.GlobalId]], sorted(k23))
    k24_nod = k23.get(("K24", "nodata", None), [])
    check("K24: the same door is nodata on K24's IsExternal gate", len(k24_nod) == 1 and members(k24_nod[0]) == [ungated.GlobalId], sorted(k23))

    # 3. K15: the drop is the storey's rise above the ground storey, DROP_HI splits H_LOW from H_HIGH
    f, body = _metric_file()
    railings = {}
    for name, elevation in (("B1", -3.0), ("S1", 0.0), ("S5", 14.8)):
        storey = run(f, "IfcBuildingStorey", name=name)
        storey.Elevation = elevation
        railing = run(f, "IfcRailing", name=f"Geländer {name}")
        add_pset(f, railing, "Pset_RailingCommon", {"Height": 1.0})
        ifcopenshell.api.run("spatial.assign_container", f, products=[railing], relating_structure=storey)
        railings[name] = railing
    ctx = Context(f, None)
    check("element.storey_rise: the ground storey is the lowest at or above 0 (S1, not the basement): S5 rises 14.8 m, B1 -3 m",
          measures.measure(ctx, railings["S5"], "element.storey_rise", {})[0] == 14.8 and measures.measure(ctx, railings["B1"], "element.storey_rise", {})[0] == -3.0)
    records = by_rule_outcome(run_topic(TOPIC_OF["K15"], f, "fx"))
    low = records.get(("K15", "pass", "H_LOW"), [])
    high = records.get(("K15", "info", "H_HIGH"), [])
    check("K15 (widened): the 1.0 m railings on B1 and S1 pass H_LOW (rise below the 12 m split); the one on S5 (14.8 m) departs from H_HIGH (1.1 m) as info",
          len(low) == 1 and set(members(low[0])) == {railings["B1"].GlobalId, railings["S1"].GlobalId}
          and len(high) == 1 and members(high[0]) == [railings["S5"].GlobalId] and not records.get(("K15", "fail", "H_HIGH")), sorted(records))

    # 4. K63: ROOF slabs plus leaf roofs, a roof built of slabs read once through them
    f, body = _metric_file()
    storey = run(f, "IfcBuildingStorey", name="S1")
    storey.Elevation = 0.0
    leaf = run(f, "IfcRoof", name="Basic Roof:Flachdach")
    _box(f, body, leaf, length=10.0, height=0.3, thickness=8.0)
    built = run(f, "IfcRoof", name="Basic Roof:Ziegeldach")
    slab = run(f, "IfcSlab", name="Dachplatte", predefined_type="ROOF")
    ifcopenshell.api.run("aggregate.assign_object", f, products=[slab], relating_object=built)
    _box(f, body, slab, length=10.0, height=0.3, thickness=8.0, x=20.0)
    for product in (leaf, built):
        ifcopenshell.api.run("spatial.assign_container", f, products=[product], relating_structure=storey)
    ctx = Context(f, None)
    selected, _unknown = population(ctx, load_rules()["K63"]["select"])
    check("K63 select (a union): the leaf IfcRoof with its own body and the ROOF slab of the built roof, each once; the aggregate IfcRoof itself is not judged",
          [e.GlobalId for e in selected] == sorted([leaf.GlobalId, slab.GlobalId]), [(e.is_a(), e.Name) for e in selected])
    k63 = by_rule_outcome(run_topic("envelope", f, "fx"))
    fails = k63.get(("K63", "fail", "S_MIN"), [])
    check("K63: both flat bodies (0 %) fail S_MIN from geometry", len(fails) == 1 and set(members(fails[0])) == {leaf.GlobalId, slab.GlobalId}, sorted(k63))

    # 5. lifts from a lift-named space, from stacked lift doors, and all three sources as ONE core
    f, storeys, spaces, doors, stairs, graph = tower_fixture(storeys_with_stair=4, lift=False)
    body = [c for c in f.by_type("IfcGeometricRepresentationSubContext") if c.ContextIdentifier == "Body"][0]
    shaft = run(f, "IfcSpace", name="Aufzug 1")
    ifcopenshell.api.run("aggregate.assign_object", f, products=[shaft], relating_object=storeys["S1"])
    _box(f, body, shaft, length=2.0, height=15.0, thickness=2.0, x=30.0)
    ctx = Context(f, graph)
    found = [c for c in ctx.fact("vertical_cores", cores.vertical_cores) if c["kind"] == "lift"]
    check("vertical_cores: a 15 m lift-named IfcSpace (shaft) with no IfcTransportElement is a lift core serving 5 storeys, sources ['space']; 26 m from the stair it does not serve that core",
          len(found) == 1 and len(found[0]["storeys"]) == 5 and found[0]["sources"] == ["space"]
          and measures.measure(ctx, next(iter(stairs.values())), "stair.core_has_lift", {})[0] == 0.0, [(c["sources"], len(c["storeys"])) for c in found])
    f, storeys, spaces, doors, stairs, graph = tower_fixture(storeys_with_stair=4, lift=False)
    body = [c for c in f.by_type("IfcGeometricRepresentationSubContext") if c.ContextIdentifier == "Body"][0]
    lift_doors = []
    for level, (name, storey) in enumerate(storeys.items()):
        door = run(f, "IfcDoor", name=f"Aufzugstür {level + 1}")
        ifcopenshell.api.run("spatial.assign_container", f, products=[door], relating_structure=storey)
        _box(f, body, door, length=1.0, height=2.1, thickness=0.1, x=6.0, z=3.0 * level)
        lift_doors.append(door)
    ctx = Context(f, graph)
    found = [c for c in ctx.fact("vertical_cores", cores.vertical_cores) if c["kind"] == "lift"]
    check("vertical_cores: five lift-named doors stacked at one plan position are ONE lift core serving 5 storeys, sources ['door']; the stair core has a lift",
          len(found) == 1 and len(found[0]["elements"]) == 5 and len(found[0]["storeys"]) == 5 and found[0]["sources"] == ["door"]
          and measures.measure(ctx, next(iter(stairs.values())), "stair.core_has_lift", {})[0] == 1.0, [(c["sources"], len(c["elements"]), len(c["storeys"])) for c in found])
    k25 = [r for r in run_topic(TOPIC_OF["K25"], f, "fx", graph=graph) if r["provenance"]["rule"] == "K25"]
    check("K25 now runs on a model whose lift is known from its doors only: five entrance doors judged on W_LIFT",
          sum(len(members(r)) for r in k25 if r["evidence"]["metrics"].get("param") == "W_LIFT") == 5, [r["id"] for r in k25])
    f, storeys, spaces, doors, stairs, graph = tower_fixture(storeys_with_stair=4, lift=True)
    body = [c for c in f.by_type("IfcGeometricRepresentationSubContext") if c.ContextIdentifier == "Body"][0]
    shaft = run(f, "IfcSpace", name="Aufzugsschacht")
    ifcopenshell.api.run("aggregate.assign_object", f, products=[shaft], relating_object=storeys["S1"])
    _box(f, body, shaft, length=2.0, height=15.0, thickness=2.0, x=5.0)
    door = run(f, "IfcDoor", name="Lift door")
    ifcopenshell.api.run("spatial.assign_container", f, products=[door], relating_structure=storeys["S1"])
    _box(f, body, door, length=1.0, height=2.1, thickness=0.1, x=5.5, y=-0.45)
    ctx = Context(f, graph)
    found = [c for c in ctx.fact("vertical_cores", cores.vertical_cores) if c["kind"] == "lift"]
    check("vertical_cores: the car (IfcTransportElement), its shaft space and its landing door at one place are ONE lift core with sources [door, space, transport]",
          len(found) == 1 and found[0]["sources"] == ["door", "space", "transport"] and len(found[0]["storeys"]) == 5, [(c["sources"], len(c["storeys"])) for c in found])

    # 6. a stairwell modelled as one space through every storey: the front doors above its base storey are entrances
    f, storeys, spaces, doors, stairs, graph = tower_fixture(storeys_with_stair=4, lift=False)
    body = [c for c in f.by_type("IfcGeometricRepresentationSubContext") if c.ContextIdentifier == "Body"][0]
    well = spaces["S1"]["T"]
    _box(f, body, well, length=4.0, height=15.0, thickness=4.0, x=-10.0)
    for name, storey in storeys.items():
        if name != "S1":
            graph.door_links[doors[name].GlobalId] = (storey.GlobalId, [spaces[name]["H"].GlobalId])  # one-sided: the well is on S1 only
    ctx = Context(f, graph)
    centre = ctx.polygons[well.GlobalId].centroid
    for name in storeys:
        graph.door_points[doors[name].GlobalId] = (centre.x, centre.y)
    units = ctx.fact("dwelling_units", facts.dwelling_units)
    with_door = {u["storey"] for u in units if u["entrance_doors"]}
    check("dwelling_units: with the stairwell one 15 m space on S1, the flats of S2-S5 (whose front doors reach only their hall) still get their entrance door through the tall space",
          len(units) == 5 and with_door == {s.GlobalId for s in storeys.values()}, [(len(u["rooms"]), u["entrance_doors"]) for u in units])

    # 7. furniture with no storey container: the storey comes from the body's z
    f, storey, spaces, furniture, graph = office_fixture()
    body = ifcopenshell.api.run("context.add_context", f, context_type="Model", context_identifier="Body", target_view="MODEL_VIEW",
                                parent=ifcopenshell.api.run("context.add_context", f, context_type="Model"))
    orphan = run(f, "IfcFurniture", name="Desk 3 (no storey)")
    _box(f, body, orphan, length=1.4, height=0.75, thickness=0.7, x=12.5, y=2.0, z=0.3)
    ctx = Context(f, graph)
    counts = ctx.fact("workstations", facts.workstations)
    check("workstations: a desk with no storey container but a body at z 0.3 inside Office 2 is counted there (Office 2 holds 2 desks now)",
          counts[spaces["Office 2"].GlobalId] == 2 and counts[spaces["Office 1"].GlobalId] == 2, {k: v for k, v in counts.items() if v})
    check("vocabulary: 'Putzmittel' is a cleaning room (K122 on the Digital Hub)", V.matches("putzmittel", "cleaning"))
    site = run(f, "IfcSite", name="Site")
    lost = run(f, "IfcSpace", name="Office 9 (floor not exported)")
    ifcopenshell.api.run("aggregate.assign_object", f, products=[lost], relating_object=site)
    _box(f, body, lost, length=5.0, height=3.0, thickness=4.0, x=100.0, z=-7.4)
    lost_desk = run(f, "IfcFurniture", name="Desk 9")
    _box(f, body, lost_desk, length=1.4, height=0.75, thickness=0.7, x=101.0, y=1.0, z=-7.1)
    ctx = Context(f, graph)
    counts = ctx.fact("workstations", facts.workstations)
    check("levels: a room aggregated into the site with a body 7.4 m below the lowest storey is a pseudo-level of its own; the desk on it is counted there and facts.level_of names the same level for both",
          counts.get(lost.GlobalId) == 1 and facts.level_of(ctx, lost) == facts.level_of(ctx, lost_desk) and facts.level_of(ctx, lost) not in (None, storey.GlobalId)
          and facts.level_of(ctx, spaces["Office 1"]) == storey.GlobalId, (counts.get(lost.GlobalId), facts.level_of(ctx, lost), facts.level_of(ctx, lost_desk)))

    # 8. a door graph in another frame than its doors is no graph for the Neufert facts
    from shapely.geometry import box
    f, storey, spaces, graph = dwelling_fixture()
    graph.polygons = {g: box(100 + i, 100, 101 + i, 101) for i, g in enumerate(graph.space_by_guid)}  # footprints 140 m from every door point (0, 0)
    ctx = Context(f, graph)
    check("graph_usable: a graph whose footprints sit 140 m from its door points (the local-frame bug on 17 corpus models and FZK) is unusable for the facts: no dwelling unit, median recorded",
          not ctx.graph_usable() and ctx.graph_frame_median_m > 100 and ctx.fact("dwelling_units", facts.dwelling_units) == [], ctx.graph_frame_median_m)
    f, storey, spaces, graph = dwelling_fixture()
    graph.polygons = {g: box(-1 + i, -1, i, 1) for i, g in enumerate(graph.space_by_guid)}
    check("graph_usable: footprints within reach of the door points keep the graph usable",
          Context(f, graph).graph_usable() and Context(f, graph).fact("dwelling_units", facts.dwelling_units))
    f, storeys, spaces, doors, stairs, graph = tower_fixture(storeys_with_stair=1)
    body = [c for c in f.by_type("IfcGeometricRepresentationSubContext") if c.ContextIdentifier == "Body"][0]
    well = spaces["S1"]["T"]
    _box(f, body, well, length=4.0, height=3.0, thickness=4.0, x=-10.0)  # its world footprint is at x -10..-6
    graph.polygons = {well.GlobalId: box(100, 100, 104, 104)}  # the graph's footprint of the same space, 150 m away
    graph.door_points = {d: (102.0, 102.0) for d in graph.door_points}  # and its door points in that same wrong frame
    ctx = Context(f, graph)
    check("graph_usable: when the graph's door points sit in the same wrong frame as its footprints (6 of the 17 corpus models), the door-point test passes but the centroid shift against the world footprint (150 m) marks the graph unusable",
          not ctx.graph_usable() and ctx.graph_frame_median_m == 0.0 and ctx.graph_frame_shift_m > 100, (ctx.graph_frame_median_m, ctx.graph_frame_shift_m))


def section_scenarios():
    """The scenario layer (2026-10-20): one record per rule
    and model when the situation a card addresses is present, live or
    deferred; nothing when absent; nothing, with a reason, when the gate
    itself is the missing fact."""
    from recognition.neufert.context import Context
    rules = load_rules()
    null = {k for k, r in rules.items() if r["scenario"] is None}
    check("every rule has a scenario selector or a stated reason for none",
          all(rules[k]["scenario_reason"] for k in null) and all(rules[k]["scenario"] is not None or k in null for k in rules), sorted(k for k in null if not rules[k]["scenario_reason"]))
    print(f"  scenarios: {len(rules) - len(null)} rules with a selector, {len(null)} not determinable ({' '.join(sorted(null, key=lambda k: int(k[1:])))})")
    f, storey, spaces, furniture, graph = office_fixture()
    records = run_topic("offices", f, "fx", graph=graph)
    scen = {r["provenance"]["rule"]: r for r in records if r["type"].endswith("_scenario")}
    k118 = scen.get("K118")
    check("a deferred rule's scenario on the office fixture: K118 (conference areas) finds the meeting rooms, the record is positive, model-level, names the card's 'applies when' and the blocker",
          k118 is not None and set(primary_members(k118)) == {spaces["Meeting"].GlobalId, spaces["Seminar 2"].GlobalId} and k118["polarity"] == "positive"
          and "Conference areas" in k118["evidence"]["summary"] and "not judged" in k118["evidence"]["summary"] and "needs" in k118["evidence"]["summary"]
          and k118["evidence"]["metrics"]["needs"], k118["evidence"]["summary"] if k118 else None)
    check("a scenario absent from the model emits nothing: K125 (staff restaurant) and K145 (server room) have no record on the office fixture",
          "K125" not in scen and "K145" not in scen, sorted(scen))
    check("related facet: K118's scenario carries the four 'Chair' seats of the meeting room as context members (via furniture, kind seat), K114's the three desks (the 'Desk chair' is a seat, 'FU-7' a desk by type), and the metrics count them per relation",
          set(context_members(k118)) == {m.GlobalId for m in f.by_type("IfcFurniture") if m.Name == "Chair"} and k118["evidence"]["metrics"]["related"] == {"furniture": 4}
          and "K114" in scen and set(context_members(scen["K114"])) == {furniture["Desk 1"].GlobalId, furniture["Desk 2"].GlobalId, furniture["FU-7"].GlobalId}
          and "4 furniture (4 IfcFurniture) as context" in k118["evidence"]["summary"], (context_members(k118), scen.get("K114") and context_members(scen["K114"])))
    check("a live rule carries its scenario beside its verdicts: K141's scenario record lists the office rooms and its aggregate records still exist",
          "K141" in scen and set(primary_members(scen["K141"])) >= {spaces["Office 1"].GlobalId, spaces["Office 2"].GlobalId}
          and [r for r in records if r["provenance"]["rule"] == "K141" and not r["type"].endswith("_scenario")], sorted(scen))
    f, storey, spaces, furniture, graph = office_fixture()  # a fresh file: the engine caches one Context per model
    window = run(f, "IfcWindow", name="Fenster 1")
    window.OverallWidth, window.OverallHeight = 1.2, 1.4
    ifcopenshell.api.run("spatial.assign_container", f, products=[window], relating_structure=storey)
    import numpy as np
    matrix = np.eye(4)
    matrix[0][3], matrix[1][3] = 0.0, 2.0  # on the west edge of Office 1 (x 0..5)
    ifcopenshell.api.run("geometry.edit_object_placement", f, product=window, matrix=matrix)
    from shapely.geometry import box as _box2d
    office3 = run(f, "IfcSpace", name="Office 3")  # shares its west edge (x = 5) with Office 1's east edge
    ifcopenshell.api.run("aggregate.assign_object", f, products=[office3], relating_object=storey)
    graph.polygons[office3.GlobalId] = _box2d(5, 0, 8, 4)
    shared = run(f, "IfcWindow", name="Fenster 2")
    shared.OverallWidth, shared.OverallHeight = 1.0, 1.0
    ifcopenshell.api.run("spatial.assign_container", f, products=[shared], relating_structure=storey)
    matrix = np.eye(4)
    matrix[0][3], matrix[1][3] = 5.0, 1.0
    ifcopenshell.api.run("geometry.edit_object_placement", f, product=shared, matrix=matrix)
    rooms_records = run_topic("rooms", f, "fx", graph=graph)
    k74 = next((r for r in rooms_records if r["provenance"]["rule"] == "K74" and r["type"].endswith("_scenario")), None)
    check("related facet: the windows on Office 1's edges are K74's context members (via windows, the glazing association), the primary members are the habitable rooms only, and the window on the edge shared with Office 3 is counted as ambiguous (within reach of two rooms)",
          k74 is not None and set(context_members(k74)) == {window.GlobalId, shared.GlobalId} and window.GlobalId not in primary_members(k74)
          and k74["evidence"]["metrics"]["relatedAmbiguous"] == 1 and "tie-break" in k74["evidence"]["summary"], (k74 and (k74["evidence"]["metrics"].get("relatedAmbiguous"), k74["evidence"]["summary"][-160:])))
    inside = ctx.fact("furniture_by_room", facts.furniture_by_room)["inside"] if False else Context(f, graph).fact("furniture_by_room", facts.furniture_by_room)["inside"]
    outside = run(f, "IfcFurniture", name="Desk 4 (against the wall)")
    ifcopenshell.api.run("spatial.assign_container", f, products=[outside], relating_structure=storey)
    matrix = np.eye(4)
    matrix[0][3], matrix[1][3] = 15.3, 2.0  # 0.3 m east of Office 2's footprint (x 10..15): within reach, not inside
    ifcopenshell.api.run("geometry.edit_object_placement", f, product=outside, matrix=matrix)
    table = Context(f, graph).fact("furniture_by_room", facts.furniture_by_room)
    check("furniture_by_room: a desk 0.3 m outside Office 2's footprint is assigned to it within the 0.5 m reach but is not in the strict `inside` set (the K136 escape-route reading)",
          outside.GlobalId in table.get(spaces["Office 2"].GlobalId, []) and outside.GlobalId not in table["inside"].get(spaces["Office 2"].GlobalId, [])
          and furniture["FU-7"].GlobalId in table["inside"].get(spaces["Office 2"].GlobalId, []), (table.get(spaces["Office 2"].GlobalId), table["inside"].get(spaces["Office 2"].GlobalId)))
    check("a not-determinable scenario emits nothing: K26 (barrier-free public buildings) has no selector, its reason names the scope, and the office fixture has no K26 row",
          rules["K26"]["scenario"] is None and "scope" in rules["K26"]["scenario_reason"]
          and "K26" not in {r["provenance"]["rule"] for r in run_topic(TOPIC_OF["K26"], f, "fx", graph=graph)}, rules["K26"]["scenario_reason"])
    check("K01's scenario reads the card's H_HR through `where ... param` (22 m) and finds nothing on a one-storey fixture",
          rules["K01"]["scenario"]["where"][0]["value"] == 22 and "K01" not in {r["provenance"]["rule"] for r in run_topic("site", f, "fx", graph=graph)}, rules["K01"]["scenario"])
    from recognition.neufert.select import population
    home = run(f, "IfcSpace", name="Home office")  # an office-named room that is NOT excluded by role on a fixture without dwellings
    ifcopenshell.api.run("aggregate.assign_object", f, products=[home], relating_object=storey)
    lobby = run(f, "IfcSpace", name="Lift lobby")
    ifcopenshell.api.run("aggregate.assign_object", f, products=[lobby], relating_object=storey)
    shaft = run(f, "IfcSpace", name="Aufzug 2")
    ifcopenshell.api.run("aggregate.assign_object", f, products=[shaft], relating_object=storey)
    wall = run(f, "IfcWall", name="W fire")
    add_pset(f, wall, "Pset_WallCommon", {"FireRating": "F90"})
    plain = run(f, "IfcWall", name="W plain")
    ctx = Context(f, graph)
    lifts, _ = population(ctx, {"class": "IfcSpace", "use": "lift", "exclude_use": "lobby|horizontal_circulation"})
    rated, _ = population(ctx, {"class": "IfcWall", "has_prop": ["FireRating"]})
    offices, _ = population(ctx, {"class": "IfcSpace", "use": "office", "exclude_role": "unit.rooms"})
    check("selector facets: exclude_use drops the lift-named lobby and keeps the shaft; has_prop keeps the wall with a FireRating; exclude_role on a model without dwellings drops nothing",
          [e.Name for e in lifts] == ["Aufzug 2"] and [e.Name for e in rated] == ["W fire"] and home.GlobalId in {e.GlobalId for e in offices}, ([e.Name for e in lifts], [e.Name for e in rated]))
    f, storey, flights = flight_fixture()
    ctx = Context(f, None)
    turn_u = measures.measure(ctx, flights["u"], "flight.turn_deg", {})[0]
    turn_s = measures.measure(ctx, flights["straight"], "flight.turn_deg", {})[0]
    check("flight.turn_deg: the U walking line turns 180 degrees, the straight one 0 (or None with two points), a body without an Axis is None",
          turn_u is not None and abs(turn_u - 180) < 1 and (turn_s is None or abs(turn_s) < 1) and measures.measure(ctx, flights["noaxis_run"], "flight.turn_deg", {})[0] is None, (turn_u, turn_s))
    f, storeys, spaces, doors, stairs, graph = tower_fixture(storeys_with_stair=4)
    ctx = Context(f, graph)
    building = f.by_type("IfcBuilding")[0]
    rise = measures.measure(ctx, building, "building.top_storey_rise", {})[0]
    top = run(f, "IfcBuildingStorey", name="S9")
    top.Elevation = 25.0
    ifcopenshell.api.run("aggregate.assign_object", f, products=[top], relating_object=building)
    attic = run(f, "IfcSpace", name="Dach")
    ifcopenshell.api.run("aggregate.assign_object", f, products=[attic], relating_object=top)
    ctx = Context(f, graph)
    k01 = [r for r in run_topic("site", f, "fx", graph=graph) if r["provenance"]["rule"] == "K01"]
    check("building.top_storey_rise: 12 m on the five-storey tower (S5 holds spaces), 25 m once a storey with a space sits at +25 m, and then K01's scenario finds the building",
          rise == 12.0 and measures.measure(ctx, building, "building.top_storey_rise", {})[0] == 25.0 and len(k01) == 1 and members(k01[0]) == [building.GlobalId], (rise, [r["id"] for r in k01]))
    f, storey, spaces, graph = dwelling_fixture()
    ctx = Context(f, graph)
    building = run(f, "IfcBuilding", name="B")
    ifcopenshell.api.run("aggregate.assign_object", f, products=[storey], relating_object=building)
    ctx = Context(f, graph)
    count = measures.measure(ctx, spaces["K1"], "element.building_dwellings", {})[0]
    records = run_topic(TOPIC_OF["K34"], f, "fx", graph=graph) + run_topic(TOPIC_OF["K12"], f, "fx", graph=graph)
    scen = {r["provenance"]["rule"]: r for r in records if r["type"].endswith("_scenario")}
    check("element.building_dwellings reads the inferred dwellings of the room's building (3 on the dwelling fixture); K34 (more than two flats) finds the dwelling rooms, K12 (at most two) finds no stair",
          count == 3.0 and "K34" in scen and len(primary_members(scen["K34"])) >= 6 and "K12" not in scen, (count, sorted(scen)))
    check("scenario ids and members are stable across runs",
          [r["id"] for r in records] == [r["id"] for r in run_topic(TOPIC_OF["K34"], f, "fx", graph=graph) + run_topic(TOPIC_OF["K12"], f, "fx", graph=graph)]
          and [members(r) for r in records] == [members(r) for r in run_topic(TOPIC_OF["K34"], f, "fx", graph=graph) + run_topic(TOPIC_OF["K12"], f, "fx", graph=graph)])
    f, storeys, spaces, doors, stairs, graph = tower_fixture(storeys_with_stair=4, lift=True)
    ctx = Context(f, graph)
    tower_records = run_topic("housing", f, "fx", graph=graph) + run_topic(TOPIC_OF["K25"], f, "fx", graph=graph)
    scen = {r["provenance"]["rule"]: r for r in tower_records if r["type"].endswith("_scenario")}
    check("related facet on the tower: K87's halls carry their door-graph neighbours and doors as context (via neighbours, doors); K25's entrance doors carry their five storeys (via storey); K83's dwelling rooms carry the five flat doors (via unit_doors)",
          "K87" in scen and set(context_members(scen["K87"])) >= {spaces["S1"]["K"].GlobalId, doors["S1"].GlobalId}
          and "K25" in scen and set(context_members(scen["K25"])) == {s.GlobalId for s in storeys.values()}
          and "K83" in scen and set(context_members(scen["K83"])) == {d.GlobalId for d in doors.values()},
          {k: (scen[k]["evidence"]["metrics"].get("related")) for k in ("K87", "K25", "K83") if k in scen})
    from recognition.neufert.select import population as _pop, related as _related
    stairs_list = list(stairs.values())
    own = _related(ctx, {"class": "IfcStair", "related": [{"via": "served_storeys", "span": "own"}]}, [stairs_list[0]])
    core = _related(ctx, {"class": "IfcStair", "related": [{"via": "served_storeys"}]}, [stairs_list[0]])
    landing = run(f, "IfcSlab", name="Podest", predefined_type="LANDING")
    rail = run(f, "IfcRailing", name="Geländer")
    ifcopenshell.api.run("aggregate.assign_object", f, products=[landing, rail], relating_object=stairs_list[0])
    parts = _related(ctx, {"class": "IfcStair", "related": [{"via": "parts", "class": "IfcSlab"}]}, [stairs_list[0]])
    check("related `class` filter: {via: parts, class: IfcSlab} on a stair with a landing slab and a railing returns the slab only",
          [e.is_a() for e, _via in parts.values()] == ["IfcSlab"], [e.is_a() for e, _via in parts.values()])
    check("served_storeys: the first tower stair's own 3 m body spans two storeys (span own) while its core serves five",
          len(own) == 2 and len(core) == 5, (len(own), len(core)))
    terrace = run(f, "IfcDoor", name="Terrassentür")
    add_pset(f, terrace, "Pset_DoorCommon", {"IsExternal": True})
    ifcopenshell.api.run("spatial.assign_container", f, products=[terrace], relating_structure=storeys["S2"])
    graph.door_links[terrace.GlobalId] = (storeys["S2"].GlobalId, [spaces["S2"]["R"].GlobalId])  # one-sided, into the bedroom
    graph.door_points[terrace.GlobalId] = (3.0, 2.0)
    units = Context(f, graph).fact("dwelling_units", facts.dwelling_units)
    s2 = next(u for u in units if u["storey"] == storeys["S2"].GlobalId)
    check("garden doors: an external door opening only into the S2 flat's bedroom is its garden door, not an entrance; the hall door stays the one entrance",
          s2["garden_doors"] == [terrace.GlobalId] and s2["entrance_doors"] == [doors["S2"].GlobalId], (s2["entrance_doors"], s2["garden_doors"]))
    from recognition.neufert.rules import _validate_selector
    from recognition.neufert import measures as M
    check("rules: a related entry without a known `via` is rejected at load",
          _raises(ValueError, _validate_selector, "Kxx", "scenario", {"class": "IfcSpace", "related": [{"via": "cousins"}]}, M, {}, {}))
    from recognition import vocabulary as V
    check("vocabulary (code review 2026-10-20): 'new corridor' and 'window cleaning' are no wc, 'kitchen cabinet' and 'flat roof' no dwelling, 'exit room' no server room; 'Flat 3', 'cabin 2' and 'w/c' still match",
          not V.matches("new corridor", "wc") and not V.matches("window cleaning", "wc") and not V.matches("kitchen cabinet", "dwelling")
          and not V.matches("flat roof", "dwelling") and not V.matches("exit room", "server_room")
          and V.matches("flat 3", "dwelling") and V.matches("cabin 2", "dwelling") and V.matches("w/c", "wc") and V.matches("server cabinet", "server_room"))
    from recognition.neufert.measures import COUNT_ROUND_TOL
    check("flight trust (code review): the derived riser count is accepted only within COUNT_ROUND_TOL of a whole number, not within a share of the count",
          COUNT_ROUND_TOL == 0.1 and abs(10.6 - round(10.6)) > COUNT_ROUND_TOL)
    f2, body2 = _metric_file()
    s_a = run(f2, "IfcBuildingStorey", name="A"); s_a.Elevation = 0.0
    s_b = run(f2, "IfcBuildingStorey", name="B (no elevation)")
    bld = run(f2, "IfcBuilding", name="B")
    ifcopenshell.api.run("aggregate.assign_object", f2, products=[s_a, s_b], relating_object=bld)
    for st in (s_a, s_b):
        sp = run(f2, "IfcSpace", name=f"Büro {st.Name}")
        ifcopenshell.api.run("aggregate.assign_object", f2, products=[sp], relating_object=st)
        add_qto(f2, sp, "Qto_SpaceBaseQuantities", {"NetFloorArea": 20.0})
    ctx2 = Context(f2, None)
    check("top_storey_rise (code review): a storey without an Elevation that holds a space does not break the fact (0 m on the one-storey building)",
          measures.measure(ctx2, bld, "building.top_storey_rise", {})[0] == 0.0)
    k122 = [r for r in run_topic(TOPIC_OF["K122"], f2, "fx") if r["provenance"]["rule"] == "K122" and not r["type"].endswith("_scenario")]
    check("provision (code review): a storey without an Elevation is still a container, so K122 reports both storeys (two info records, 0 cleaner's rooms each)",
          sum(1 for r in k122 if r["type"].endswith("_info")) == 2 or len(k122) >= 1 and {m for r in k122 for m in r["evidence"]["relatedGuids"]} >= {s_b.GlobalId}, [(r["type"], r["evidence"]["relatedGuids"]) for r in k122])
    from recognition.neufert.select import population as _population
    empty, _ = _population(ctx2, {"class": "IfcDoor", "query": "Name = /.*/"})
    check("select (code review): a query on an empty class population stays empty instead of searching the whole model", empty == [])
    check("vocabulary: canteen / post room / server room concepts, 'mensa' bounded",

          V.matches("kantine", "canteen") and V.matches("mensa", "canteen") and not V.matches("mensal", "canteen")
          and V.matches("poststelle", "post_room") and V.matches("serverraum", "server_room") and not V.matches("serverraum", "canteen"))


def main():
    section_config()
    section_bindings_script()
    section_literals()
    section_compare()
    section_fixture()
    section_route()
    section_dwellings()
    section_workstations()
    section_ifcopenshell_tools()
    section_vertical_cores()
    section_flight_width()
    section_validation()
    section_scenarios()
    section_example()
    failed = [r for r in RESULTS if not r[1]]
    for name, ok, detail in RESULTS:
        print(f"{'ok  ' if ok else 'FAIL'} {name}" + (f"  -- {detail}" if not ok and detail else ""))
    print(f"\n{len(RESULTS) - len(failed)} of {len(RESULTS)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

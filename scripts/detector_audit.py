"""Audit tooling behind the detector audit (2026-09-22). Three read-only probes over
src/recognition/ - nothing here writes a shard, a verdict or a cache entry.

    uv run python scripts/detector_audit.py profile data/test_5.ifc
        Time every registered detector on one model and count how often the
        two expensive shared inputs are recomputed: IfcSpace triangulation
        passes (extraction.geometry_iteration.iterate_shapes) and property-set
        walks (ifcopenshell.util.element.get_psets). get_psets recurses once
        into the element's type when it inherits, so the raw count is roughly
        2x the number of elements walked - the table reports both.

    uv run python scripts/detector_audit.py storeys data/test_3.ifc [more.ifc ...]
        Compare the three storey-lookup spellings the detectors carry
        (container-only / +Decomposes / +one more hop) against ifcopenshell's
        own get_parent(element, ifc_class="IfcBuildingStorey"), per class, and
        report storeys whose Elevation is None (every chain detector sorts on
        it).

    uv run python scripts/detector_audit.py placements data/test_3.ifc [...]
        Count IfcWindow/IfcDoor/IfcStairFlight instances with no
        ObjectPlacement. get_local_placement(None) returns the identity
        matrix, i.e. (0, 0), which a detector that does not check first will
        treat as a real position.
"""

import argparse
import collections
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))
sys.path.insert(0, str(REPO_ROOT / "src"))

import ifcopenshell  # noqa: E402
import ifcopenshell.util.element as ue  # noqa: E402


def cmd_profile(args):
    import recognize_intents as rp  # noqa: E402
    import extraction.geometry_iteration as gi  # noqa: E402
    from recognition.registry import CATEGORIES  # noqa: E402
    from recognition import access_graph  # noqa: E402
    import recognition.detectors.vertical as vert  # noqa: E402
    import recognition.detectors.circulation as circ  # noqa: E402

    path = Path(args.ifc)
    identity = rp.resolve_file_identity(path, path.name)
    key = identity["key"]
    needed = {k for c in CATEGORIES.values() for k in c["extraction_keys"]}
    t0 = time.time()
    extracted = rp.build_extracted(path, key, needed, use_cache=True)
    t_extract = time.time() - t0
    t0 = time.time()
    model = ifcopenshell.open(str(path))
    t_open = time.time() - t0

    current = [None]
    shape_calls, shape_elems, pset_calls = collections.Counter(), collections.Counter(), collections.Counter()
    original_iterate = gi.iterate_shapes

    def counting_iterate(settings, model, elements, kind):
        elements = list(elements)
        shape_calls[current[0]] += 1
        shape_elems[current[0]] += len(elements)
        return original_iterate(settings, model, elements, kind)

    # Every module that did `from ... import iterate_shapes` holds its own name.
    for module in (access_graph, vert, circ):
        module.iterate_shapes = counting_iterate
    original_psets = ue.get_psets

    def counting_psets(*a, **k):
        pset_calls[current[0]] += 1
        return original_psets(*a, **k)

    ue.get_psets = counting_psets

    rows = []
    for cid, info in CATEGORIES.items():
        current[0] = cid
        t = time.time()
        try:
            found = info["detector"](model, extracted, key)
            n, err = len(found), ""
        except Exception as e:  # noqa: BLE001 - reported, not hidden
            n, err = -1, f"{type(e).__name__}: {e}"
        rows.append((cid, n, time.time() - t, shape_calls[cid], shape_elems[cid], pset_calls[cid], err))

    print(f"file={path.name} key={key} open={t_open:.1f}s extraction={t_extract:.1f}s "
          f"spaces={len(model.by_type('IfcSpace'))} doors={len(model.by_type('IfcDoor'))} "
          f"windows={len(model.by_type('IfcWindow'))}")
    print(f"{'category':24} {'intents':>8} {'sec':>6} {'triPass':>7} {'triElem':>7} {'psetWalks':>9}")
    for cid, n, sec, calls, elems, psets, err in rows:
        print(f"{cid:24} {n:8d} {sec:6.1f} {calls:7d} {elems:7d} {psets:9d} {err}")
    print(f"TOTAL detectors={sum(r[2] for r in rows):.1f}s triangulation passes={sum(shape_calls.values())} "
          f"elements triangulated={sum(shape_elems.values())} get_psets calls={sum(pset_calls.values())} "
          f"(~{sum(pset_calls.values()) // 2} element walks after type inheritance)")


def _storey_container_only(element):
    return ue.get_container(element, ifc_class="IfcBuildingStorey")


def _storey_with_decomposes(element):
    storey = _storey_container_only(element)
    if storey is not None:
        return storey
    for rel in element.Decomposes:
        if rel.RelatingObject.is_a("IfcBuildingStorey"):
            return rel.RelatingObject
    return None


def _storey_two_hop(element):
    storey = _storey_with_decomposes(element)
    if storey is not None:
        return storey
    for rel in element.Decomposes:
        parent = _storey_container_only(rel.RelatingObject)
        if parent is not None:
            return parent
    return None


def _storey_ifcopenshell(element):
    return ue.get_parent(element, ifc_class="IfcBuildingStorey")


def _eid(entity):
    return entity.id() if entity is not None else None


def cmd_storeys(args):
    classes = ("IfcSpace", "IfcDoor", "IfcWindow", "IfcColumn", "IfcWall", "IfcBeam", "IfcSlab",
               "IfcPlate", "IfcMember", "IfcStair", "IfcCurtainWall", "IfcFurnishingElement")
    for path in args.ifc:
        try:
            model = ifcopenshell.open(path)
        except Exception as e:  # noqa: BLE001
            print(f"{Path(path).name}: cannot open ({type(e).__name__})")
            continue
        storeys = model.by_type("IfcBuildingStorey")
        elevations = [s.Elevation for s in storeys]
        print(f"{Path(path).name} ({model.schema}): {len(storeys)} storeys, "
              f"{sum(1 for e in elevations if e is None)} with Elevation=None, "
              f"{len(elevations) - len(set(elevations))} duplicate elevations")
        print(f"  {'class':22} {'n':>5} {'container':>9} {'+decomp':>8} {'+2hop':>6} {'get_parent':>10} {'disagree':>8}")
        for ifc_class in classes:
            try:
                elements = list({e.GlobalId: e for e in model.by_type(ifc_class)}.values())
            except RuntimeError:
                continue
            if not elements:
                continue
            a = sum(1 for e in elements if _storey_container_only(e) is not None)
            b = sum(1 for e in elements if _storey_with_decomposes(e) is not None)
            c = sum(1 for e in elements if _storey_two_hop(e) is not None)
            d = sum(1 for e in elements if _storey_ifcopenshell(e) is not None)
            disagree = sum(1 for e in elements if _eid(_storey_with_decomposes(e)) != _eid(_storey_ifcopenshell(e)))
            flag = "" if a == b == c == d == len(elements) and disagree == 0 else "  <-"
            print(f"  {ifc_class:22} {len(elements):5d} {a:9d} {b:8d} {c:6d} {d:10d} {disagree:8d}{flag}")


def cmd_placements(args):
    import ifcopenshell.util.placement as up  # noqa: E402
    identity = up.get_local_placement(None)
    print(f"get_local_placement(None) -> ({identity[0][3]:.0f}, {identity[1][3]:.0f})")
    for path in args.ifc:
        try:
            model = ifcopenshell.open(path)
        except Exception as e:  # noqa: BLE001
            print(f"{Path(path).name}: cannot open ({type(e).__name__})")
            continue
        parts = []
        for ifc_class in ("IfcWindow", "IfcDoor", "IfcStairFlight"):
            elements = model.by_type(ifc_class)
            missing = [e for e in elements if e.ObjectPlacement is None]
            no_storey = sum(1 for e in missing if _storey_ifcopenshell(e) is None)
            parts.append(f"{ifc_class} {len(missing)}/{len(elements)} without placement"
                         + (f" ({no_storey} of those also without storey)" if missing else ""))
        print(f"{Path(path).name}: " + "; ".join(parts))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("profile", help="time each detector and count recomputed shared inputs")
    p.add_argument("ifc")
    p.set_defaults(func=cmd_profile)
    p = sub.add_parser("storeys", help="compare storey-lookup spellings against ifcopenshell get_parent")
    p.add_argument("ifc", nargs="+")
    p.set_defaults(func=cmd_storeys)
    p = sub.add_parser("placements", help="count elements with no ObjectPlacement")
    p.add_argument("ifc", nargs="+")
    p.set_defaults(func=cmd_placements)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

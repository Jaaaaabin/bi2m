"""Self-checks for the recognition package's shared helper modules
(2026-10-09): storeys.py, chains.py, components.py, properties.py,
footprints.py, spaces.py and census.py. Each module replaced copies that
several detectors carried, so a change to one now moves several categories
at once; these checks pin the behaviour the copies had. Synthetic only:
in-memory IFC built with ifcopenshell.api, shapely boxes and edge lists,
no file read or written.

    uv run python scripts/verify_shared_modules.py

The adoption itself was checked differently: every category's shard,
before and after, on the 370 library models and data/example_autcon.ifc
under two hash seeds, byte for byte (2026-10-09).

Exit code 0 when every check passes, 1 otherwise.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

import ifcopenshell  # noqa: E402
import ifcopenshell.api  # noqa: E402
import ifcopenshell.guid  # noqa: E402

RESULTS = []


def check(name, condition, detail=""):
    RESULTS.append((name, bool(condition), detail))


def _entity(model, ifc_class, name):
    return ifcopenshell.api.run("root.create_entity", model, ifc_class=ifc_class, name=name)


def section_components():
    from recognition.components import connected_components
    found = connected_components([(1, 2), (2, 3), (5, 6)])
    check("edges sharing a member merge into one component", found == [{1, 2, 3}, {5, 6}], found)
    check("an id in no edge is in no component", not any(4 in c for c in connected_components([(1, 2), (3, 5)])))
    first = connected_components([(5, 6), (1, 2), (6, 7)])
    check("components come back in the order their roots are first met", first == [{5, 6, 7}, {1, 2}], first)
    check("no edges, no components", connected_components([]) == [])


def section_chains():
    from recognition.chains import adjacent_storey_edges, roles_by_rank
    roles = roles_by_rank([0, 0, 1, 2, 2])
    check("roles go by rank, ties included",
          roles == ["base", "base", "intermediate", "top", "top"], roles)
    by_storey = {"A": [(1, 0.0, 0.0)], "B": [(2, 0.04, 0.0), (3, 1.0, 1.0), (6, 0.0, 0.5)],
                 "C": [(4, 0.0, 0.05)], "D": [(5, 0.0, 0.0)]}
    edges = adjacent_storey_edges(["A", "B", "C"], by_storey, 0.05)
    check("adjacent storeys link entries within tolerance in x and in y", edges == [(1, 2), (2, 4)], edges)
    edges = adjacent_storey_edges(["A", "C"], by_storey, 0.05)
    check("adjacency follows the order given, not the storey names", edges == [(1, 4)], edges)
    check("a storey left out of the order is never linked",
          (1, 5) not in adjacent_storey_edges(["A", "B"], by_storey, 0.05))


def section_storeys():
    from recognition.storeys import get_storey, ordered_storeys_with
    f = ifcopenshell.file(schema="IFC4")
    upper, lower = _entity(f, "IfcBuildingStorey", "L1"), _entity(f, "IfcBuildingStorey", "L0")
    upper.Elevation, lower.Elevation = 3.0, 0.0
    space, wall = _entity(f, "IfcSpace", "R1"), _entity(f, "IfcWall", "W1")
    curtain_wall, plate = _entity(f, "IfcCurtainWall", "CW"), _entity(f, "IfcPlate", "P1")
    loose = _entity(f, "IfcColumn", "C1")
    ifcopenshell.api.run("aggregate.assign_object", f, products=[space], relating_object=lower)
    ifcopenshell.api.run("spatial.assign_container", f, products=[wall, curtain_wall], relating_structure=lower)
    ifcopenshell.api.run("aggregate.assign_object", f, products=[plate], relating_object=curtain_wall)
    check("a contained element resolves through its container", get_storey(wall) == lower)
    check("an aggregated space resolves through Decomposes", get_storey(space) == lower)
    check("a curtain-wall panel resolves through its curtain wall's container", get_storey(plate) == lower)
    # The one case the extra hop answers: contained in a building (not a
    # storey) and aggregated into a part that has a storey.
    building = _entity(f, "IfcBuilding", "B")
    odd = _entity(f, "IfcPlate", "P2")
    ifcopenshell.api.run("aggregate.assign_object", f, products=[odd], relating_object=curtain_wall)
    f.createIfcRelContainedInSpatialStructure(ifcopenshell.guid.new(), None, None, None, [odd], building)
    check("without the hop, a building container hides the aggregate's storey", get_storey(odd) is None)
    check("parent_container=True finds it through the aggregate parent",
          get_storey(odd, parent_container=True) == lower)
    check("an element on no storey resolves to None", get_storey(loose) is None and get_storey(loose, True) is None)
    ordered = ordered_storeys_with({upper.GlobalId: [1], lower.GlobalId: [2]}, f)
    check("storeys come back lowest elevation first", ordered == [lower.GlobalId, upper.GlobalId], ordered)
    check("only the storeys that carry entries come back",
          ordered_storeys_with({upper.GlobalId: [1]}, f) == [upper.GlobalId])


def section_properties():
    from recognition.properties import is_external, property_value
    f = ifcopenshell.file(schema="IFC4")
    wall, door, inner = _entity(f, "IfcWall", "W1"), _entity(f, "IfcDoor", "D1"), _entity(f, "IfcWall", "W2")
    pset = ifcopenshell.api.run("pset.add_pset", f, product=wall, name="Pset_WallCommon")
    ifcopenshell.api.run("pset.edit_pset", f, pset=pset, properties={"IsExternal": True})
    other = ifcopenshell.api.run("pset.add_pset", f, product=wall, name="Analytical Properties")
    ifcopenshell.api.run("pset.edit_pset", f, pset=other, properties={"ThermalTransmittance": 0.3})
    pset = ifcopenshell.api.run("pset.add_pset", f, product=inner, name="Pset_WallCommon")
    ifcopenshell.api.run("pset.edit_pset", f, pset=pset, properties={"IsExternal": False})
    check("a value is found in whichever set carries it",
          property_value(wall, ("ThermalTransmittance", "UValue")) == 0.3)
    check("a name no set carries reads None", property_value(wall, ("Span",)) is None)
    check("IsExternal True is external", is_external(wall))
    check("IsExternal False is not external", not is_external(inner))
    check("no property set at all is not external", not is_external(door))


def section_spaces():
    from shapely.geometry import Point, box
    from recognition.spaces import index_by_storey, nearest_space
    polygons = {"a": box(0, 0, 1, 1), "b": box(2, 0, 3, 1), "c": box(0, 0, 1, 1)}
    check("a point inside a room is at distance 0 from it",
          nearest_space(Point(0.5, 0.5), ["b", "a"], polygons) == ("a", 0.0))
    check("on a tie the first candidate wins", nearest_space(Point(1.5, 0.5), ["a", "b"], polygons) == ("a", 0.5))
    check("the scan stops at the first room containing the point",
          nearest_space(Point(0.5, 0.5), ["c", "not-in-polygons"], polygons) == ("c", 0.0))
    check("a point between rooms picks the nearer one",
          nearest_space(Point(2.6, 2.0), ["a", "b"], polygons)[0] == "b")
    check("no candidates gives (None, None)", nearest_space(Point(0, 0), [], polygons) == (None, None))
    f = ifcopenshell.file(schema="IFC4")
    storey = _entity(f, "IfcBuildingStorey", "L0")
    kept, unshaped, loose = (_entity(f, "IfcSpace", n) for n in ("R1", "R2", "R3"))
    ifcopenshell.api.run("aggregate.assign_object", f, products=[kept, unshaped], relating_object=storey)
    index = index_by_storey([kept, unshaped, loose], {kept.GlobalId: box(0, 0, 1, 1), loose.GlobalId: box(0, 0, 1, 1)})
    check("a space needs both a storey and a footprint to be indexed",
          dict(index) == {storey.GlobalId: [kept.GlobalId]}, dict(index))
    check("a storey with no indexed space reads as an empty list", index["no-such-storey"] == [])


def section_census():
    from recognition.census import elements_by_guid
    f = ifcopenshell.file(schema="IFC4")
    chair = _entity(f, "IfcFurniture", "Chair:A:1")
    desk = _entity(f, "IfcSystemFurnitureElement", "Desk:B:2")
    found = elements_by_guid(f, ("IfcFurniture", "IfcNotAClass", "IfcFurnishingElement"))
    check("subtypes swept twice are kept once (docs/detectors.md rule 3)", len(found) == 2, len(found))
    check("first-seen order is kept", list(found) == [chair.GlobalId, desk.GlobalId], list(found))
    check("a class the schema lacks is skipped", all(isinstance(k, str) for k in found))


def section_footprints():
    from recognition.footprints import CLOSED_LOOP_EDGE_LIMIT, info_polygon
    corners = [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)]
    square = {"location": [(corners[i], corners[(i + 1) % 4]) for i in range(4)]}
    polygon = info_polygon(square)
    check("one shape's ring becomes its footprint", polygon is not None and abs(polygon.area - 1.0) < 1e-9)
    steps = 60
    dense = []
    for i in range(4):
        (x0, y0, _), (x1, y1, _) = corners[i], corners[(i + 1) % 4]
        for k in range(steps):
            a, b = k / steps, (k + 1) / steps
            dense.append(((x0 + (x1 - x0) * a, y0 + (y1 - y0) * a, 0), (x0 + (x1 - x0) * b, y0 + (y1 - y0) * b, 0)))
    check("the dense mesh is past the closed-loop limit", len(dense) > CLOSED_LOOP_EDGE_LIMIT, len(dense))
    polygon = info_polygon({"location": dense})
    check("past the limit, polygonize gives the same outline",
          polygon is not None and abs(polygon.area - 1.0) < 1e-9, polygon and polygon.area)
    check("an open chain has no footprint", info_polygon({"location": square["location"][:3]}) is None)


def main():
    for section in (section_components, section_chains, section_storeys, section_properties,
                    section_spaces, section_census, section_footprints):
        try:
            section()
        except Exception as e:  # noqa: BLE001 - a crashing section is a failed check, not a crash
            check(f"{section.__name__} runs", False, f"{type(e).__name__}: {e}")
    failed = [r for r in RESULTS if not r[1]]
    for name, ok, detail in RESULTS:
        print(f"{'ok  ' if ok else 'FAIL'} {name}" + ("" if ok else f"  ->  {detail}"))
    print(f"\n{len(RESULTS) - len(failed)} of {len(RESULTS)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

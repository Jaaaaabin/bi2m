"""Checks the model session's interface (src/recognition/session.py, 2026-10-22)
and the per-graph storey views (room_graph.py, room_routes.py): the memo
keys, the failure rule, the implicit/explicit registry, and that the rebuilt
graphs and adjacencies are independent objects with identical order. Fixture
built in memory with ifcopenshell.api, nothing read or written on disk.

    uv run python scripts/verify_session.py
"""
import sys
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

import ifcopenshell  # noqa: E402
import ifcopenshell.api  # noqa: E402
import ifcopenshell.util.element as element_util  # noqa: E402

from recognition import properties, room_graph, room_routes, session  # noqa: E402
from recognition.access_graph import AccessGraph  # noqa: E402
from recognition.neufert.context import Context  # noqa: E402
from recognition.session import ModelSession, SessionClosed, psets_of  # noqa: E402

RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))


def add_pset(file, product, name, props):
    pset = ifcopenshell.api.run("pset.add_pset", file, product=product, name=name)
    ifcopenshell.api.run("pset.edit_pset", file, pset=pset, properties=props)


def fixture():
    f = ifcopenshell.file(schema="IFC4")
    ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcProject", name="p")
    door = ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcDoor", name="D1")
    wall = ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcWall", name="W1")
    add_pset(f, door, "Pset_DoorCommon", {"IsExternal": True})
    add_pset(f, wall, "Pset_WallCommon", {"IsExternal": False, "LoadBearing": True})
    return f, door, wall


class Counting:
    """Wraps ifcopenshell.util.element.get_psets with a call counter and an optional failure."""

    def __init__(self):
        self.calls = 0
        self.fail_next = False
        self.original = element_util.get_psets

    def __call__(self, element, *args, **kwargs):
        self.calls += 1
        if self.fail_next:
            self.fail_next = False
            raise RuntimeError("synthetic get_psets failure")
        return self.original(element, *args, **kwargs)


def section_psets_memo():
    f, door, wall = fixture()
    ModelSession.forget(f)
    counter = Counting()
    element_util.get_psets = counter
    try:
        first = psets_of(door)
        second = psets_of(door)
        check("psets: a second read of the same element is the memo's own object, one get_psets call",
              first is second and counter.calls == 1 and first["Pset_DoorCommon"]["IsExternal"] is True, f"{counter.calls} call(s)")
        qtos = psets_of(door, qtos_only=True)
        check("psets: qtos_only is a separate memo row", counter.calls == 2 and qtos is not first and "Pset_DoorCommon" not in qtos, f"{counter.calls} call(s)")
        verbose = psets_of(door, verbose=True)
        check("psets: verbose is a separate memo row (it changes the value shape)", counter.calls == 3 and verbose is not first, f"{counter.calls} call(s)")
        check("property_value reads through the memo: no new call", properties.property_value(door, ("IsExternal",)) is True and counter.calls == 3)
        check("is_external on the wall is False, one call for the wall", properties.is_external(wall) is False and counter.calls == 4)
        counter.fail_next = True  # the next MISS fails: the wall's quantities have not been read yet
        raised = False
        try:
            psets_of(wall, qtos_only=True)
        except RuntimeError:
            raised = True
        retry = psets_of(wall, qtos_only=True)
        check("a failing get_psets propagates and is NOT memoised: the next read succeeds", raised and isinstance(retry, dict) and counter.calls == 6, f"{counter.calls} call(s)")

        class Fake:
            def id(self):
                return 7

        fake_calls = counter.calls
        try:
            psets_of(Fake())
        except Exception:  # noqa: BLE001 - the real get_psets rejects a fake; the point is that it was called directly
            pass
        check("an element without .file is read directly (no session)", counter.calls == fake_calls + 1)
    finally:
        element_util.get_psets = counter.original
        ModelSession.forget(f)


def section_registry():
    f, door, wall = fixture()
    g, _d2, _w2 = fixture()
    ModelSession.forget(f)
    ModelSession.forget(g)
    implicit = ModelSession.current(f)
    check("current(): the implicit session is reused for the same model", ModelSession.current(f) is implicit)
    other = ModelSession.current(g)
    check("current(): another model replaces the implicit session", other is not implicit and ModelSession.current(f) is not implicit)
    explicit = ModelSession.of(f, file_key="fx")
    check("of(): the explicit session wins over the implicit one and survives another model asking",
          ModelSession.current(f) is explicit and (ModelSession.current(g), ModelSession.current(f))[1] is explicit)
    ModelSession.forget_implicit(f)
    check("forget_implicit never drops an explicit session", ModelSession.current(f) is explicit)
    explicit.psets(door)
    explicit.close()
    closed = False
    try:
        explicit.psets(door)
    except SessionClosed:
        closed = True
    check("close(): drops the registry entry and refuses further facts", closed and ModelSession.current(f) is not explicit)
    # a verify fixture mutated after a read: a fresh Context sees the new pset
    ModelSession.forget(f)
    before = Context(f, None).psets(door)
    add_pset(f, door, "Pset_Extra", {"Marker": 1})
    after = Context(f, None).psets(door)
    check("a fresh Context drops the implicit session: a pset added after a read is seen",
          "Pset_Extra" not in before and after.get("Pset_Extra", {}).get("Marker") == 1)
    ModelSession.forget(f)
    ModelSession.forget(g)


def hand_graph():
    """An AccessGraph without __init__, as verify_soft_signals builds one: three rooms on one
    storey, one door between A and B, one door reaching B and C, one door reaching only C."""
    from shapely.geometry import box

    graph = AccessGraph.__new__(AccessGraph)
    graph.spaces_by_storey = {"S": ["B", "A", "C"]}
    graph.polygons = {"A": box(0, 0, 4, 4), "B": box(4, 0, 8, 4), "C": box(8, 0, 12, 4)}
    graph.door_links = {"d2": ("S", ["B", "C"]), "d1": ("S", ["A", "B"]), "d3": ("S", ["C"])}
    graph.door_points = {"d1": (4.0, 2.0), "d2": (8.0, 2.0), "d3": (12.0, 2.0)}
    graph.degenerate_storeys = set()
    return graph


def section_storey_views():
    graph = hand_graph()
    G1, open1 = room_graph.storey_room_graph(graph, "S")
    G2, open2 = room_graph.storey_room_graph(graph, "S")
    shape = lambda G: [(n, list(G.adj[n]), [G.edges[n, m]["doors"] for m in G.adj[n]]) for n in G]  # noqa: E731
    check("storey_room_graph: two calls give independent graphs with identical node, neighbour and door order",
          G1 is not G2 and shape(G1) == shape(G2) and list(G1) == ["A", "B", "C"] and open1 == {"C": ["d3"]} and open1 is not open2)
    check("  built from one scan memoised on the graph instance", len(graph.__dict__.get("_storey_scans", {})) == 1)
    G1.remove_nodes_from(["A"])
    G3, _ = room_graph.storey_room_graph(graph, "S")
    check("  a caller editing its graph does not touch the next caller's", list(G3) == ["A", "B", "C"] and list(G1) == ["B", "C"])
    adj1 = room_routes.storey_adjacency(graph, "S", skip_doors=frozenset({"d3"}))
    adj2 = room_routes.storey_adjacency(graph, "S", skip_doors=frozenset({"d3"}))
    check("storey_adjacency: two calls give independent defaultdicts with identical list order",
          adj1 is not adj2 and dict(adj1) == dict(adj2) and isinstance(adj1, defaultdict) and [r for r, _w in adj1["B"]] == ["C", "A"])  # door_links order: d2 before d1
    distances = room_routes.shortest_distances(adj1, {"Z": 0.0})  # a seed room with no edges: the auto-insert
    adj3 = room_routes.storey_adjacency(graph, "S", skip_doors=frozenset({"d3"}))
    check("  shortest_distances' auto-insert does not leak into the next call", "Z" in adj1 and "Z" not in adj3 and distances == {"Z": 0.0})
    check("  one scan per (storey, skip set)", len(graph.__dict__.get("_adjacency_scans", {})) == 1)
    adj4 = room_routes.storey_adjacency(graph, "S")
    check("  a different skip set is a second scan", len(graph.__dict__.get("_adjacency_scans", {})) == 2 and len(adj4["C"]) == 1)


def main():
    for section in (section_psets_memo, section_registry, section_storey_views):
        try:
            section()
        except Exception as e:  # noqa: BLE001
            check(f"{section.__name__} ran without an exception", False, f"{type(e).__name__}: {e}")
    failed = [r for r in RESULTS if not r[1]]
    for name, ok, detail in RESULTS:
        print(f"{'ok  ' if ok else 'FAIL'} {name}" + (f" ({detail})" if detail else ""))
    print(f"{len(RESULTS) - len(failed)} of {len(RESULTS)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

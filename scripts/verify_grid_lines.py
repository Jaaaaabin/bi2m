"""Self-checks for src/modality/grid_lines.py and the sidecar merge of
scripts/grid_lines.py, on synthetic grids. No IFC file is read; the merge
checks write into a temporary folder that is removed afterwards.

    uv run python scripts/verify_grid_lines.py

Exit code 0 when every check passes, 1 otherwise.
"""

import importlib.util
import json
import math
import random
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from modality import declared_grid as dg  # noqa: E402
from modality import grid_lines as gl  # noqa: E402

RESULTS = []


def check(name, condition, detail=""):
    RESULTS.append((name, bool(condition), detail))


def load_cli():
    spec = importlib.util.spec_from_file_location("grid_lines_cli", REPO_ROOT / "scripts" / "grid_lines.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


XS = [0, 6, 12, 18]
YS = [0, 8]


def grid(guid, storey, extra=(), name="Raster"):
    axes = [dg.make_axis(str(i + 1), "U", guid, [(x, -2), (x, 10)]) for i, x in enumerate(XS)]
    axes += [dg.make_axis("AB"[j], "V", guid, [(-2, y), (20, y)]) for j, y in enumerate(YS)]
    for tag, family, p0, p1 in extra:
        axes.append(dg.make_axis(tag, family, guid, [p0, p1]))
    return {"guid": guid, "name": name, "predefinedType": None, "storey": storey, "axes": axes, "skippedAxes": []}


def storeys(n, z0=0.0, step=3.0):
    return [{"guid": f"S{k}", "name": f"Level {k}", "elevation": z0 + k * step, "z": z0 + k * step} for k in range(n)]


def build(grids, levels, heights=None):
    heights = heights if heights is not None else {g["guid"]: next(s["z"] for s in levels if s["guid"] == g["storey"])
                                                   for g in grids if g["storey"] is not None}
    variants, table = gl.grid_variants(grids, levels, heights)
    return variants, table, gl.line_specs(variants, {g["guid"]: g["name"] for g in grids})


def spec_problems(spec):
    """The subset of views/lineSpec.js normalizeLineSpec these specs rely on."""
    problems = []
    n = len(spec["points"])
    if spec["kind"] not in ("segment", "polyline") or (spec["kind"] == "segment") != (n == 2) or n < 2:
        problems.append("kind/points")
    if spec["space"] != "ifcPlan" or not all(len(p) == 2 and all(math.isfinite(v) for v in p) for p in spec["points"]):
        problems.append("points")
    if set(spec["height"]) != {"ifcZ"} or not math.isfinite(spec["height"]["ifcZ"]):
        problems.append("height")
    style = spec["style"]
    if not (isinstance(style["color"], str) and style["width"] >= 1 and 0 <= style["opacity"] <= 1):
        problems.append("style")
    if not spec["id"].startswith(gl.GRID_LINE_PREFIX) or not isinstance(spec["meta"].get("label"), str):
        problems.append("id/label")
    return problems


def main():
    # ---- Revit: one identical copy per storey ----
    levels = storeys(3)
    copies = [grid(f"g{k}", f"S{k}") for k in range(3)]
    variants, table, specs = build(copies, levels)
    check("identical copies on three storeys: one variant, one line per axis",
          len(variants) == 1 and len(specs) == 6, (len(variants), len(specs)))
    check("the variant is drawn at its lowest storey and lists all three",
          {s["height"]["ifcZ"] for s in specs} == {0.0} and specs[0]["meta"]["storeys"] == ["S0", "S1", "S2"],
          specs[0]["height"])
    check("every storey row names the variant, source own", all(r["source"] == "own" and r["variant"] == "S0" for r in table), table)
    check("the label names tag, family, grid and storeys",
          specs[0]["meta"]["label"] == "Axis 1 · F2 · Raster · Level 0, Level 1, Level 2", specs[0]["meta"]["label"])
    check("every spec has the shape lineSpec.js accepts", all(not spec_problems(s) for s in specs),
          [(s["id"], spec_problems(s)) for s in specs if spec_problems(s)])
    check("ids are unique and grid-prefixed", len({s["id"] for s in specs}) == len(specs)
          and all(s["id"].startswith("grid:S0:") for s in specs))

    # ---- the grid changes on the top storey ----
    changed = [grid("g0", "S0"), grid("g1", "S1"), grid("g2", "S2", extra=[("5", "U", (24, -2), (24, 10))])]
    variants, table, specs = build(changed, levels)
    check("a storey with an extra axis gets its own variant, at its own height",
          [v["id"] for v in variants] == ["S0", "S2"] and {s["height"]["ifcZ"] for s in specs if s["meta"]["variant"] == "S2"} == {6.0},
          [(v["id"], len(v["axes"])) for v in variants])
    check("the two variants carry 6 and 7 lines", sum(1 for s in specs if s["meta"]["variant"] == "S0") == 6
          and sum(1 for s in specs if s["meta"]["variant"] == "S2") == 7)
    partial_of = {(s["meta"]["variant"], s["meta"]["tags"][0]): s["meta"]["partial"] for s in specs}
    check("the extra axis lies past the V axes' ends, so they are partial there and only there",
          partial_of[("S2", "A")] and partial_of[("S2", "B")] and not partial_of[("S0", "A")], partial_of)

    # ---- a storey without a grid of its own ----
    variants, table, specs = build([grid("g0", "S0")], levels)
    check("borrowed storeys are not drawn", len(specs) == 6 and specs[0]["meta"]["storeys"] == ["S0"],
          [s["meta"]["storeys"] for s in specs[:1]])
    check("borrowed storeys are listed with their source and no variant",
          [(r["source"], r["variant"]) for r in table] == [("own", "S0"), ("borrowed", None), ("borrowed", None)], table)
    variants, table, specs = build([], levels)
    check("a model without a grid gives no lines and storeys of source none",
          specs == [] and all(r["source"] == "none" for r in table), table)

    # ---- a grid contained in no storey ----
    building = grid("gb", None)
    variants, table, specs = build([building], levels, heights={"gb": 99.0})
    check("a building-level grid is one variant at the lowest storey's z, not its own placement z",
          len(variants) == 1 and specs[0]["height"]["ifcZ"] == 0.0 and all(r["source"] == "building" for r in table),
          specs[0]["height"])

    # ---- the grid placement's z wins over the storey's ----
    variants, table, specs = build([grid("g0", "S0")], storeys(1), heights={"g0": -0.8})
    check("the height is the grid placement's z", specs[0]["height"] == {"ifcZ": -0.8}, specs[0]["height"])

    # ---- two grid objects overlapping on one storey ----
    twin = grid("g1", "S0", name="Raster copy")
    variants, table, specs = build([grid("g0", "S0"), twin], storeys(1))
    check("overlapping grid objects merge: one line per axis, both grids and names kept",
          len(specs) == 6 and specs[0]["meta"]["grids"] == ["g0", "g1"] and "Raster, Raster copy" in specs[0]["meta"]["label"],
          [s["meta"]["label"] for s in specs[:1]])

    # ---- families from geometry, not from the declared U/V/W lists ----
    revit_w = grid("g0", "S0", extra=[("7", "W", (3, -2), (3, 10)), ("D1", "W", (0, 0), (18, 8))])
    variants, table, specs = build([revit_w], storeys(1))
    by_tag = {s["meta"]["tags"][0]: s for s in specs}
    check("a W axis parallel to U takes U's family and colour, its declared family kept",
          by_tag["7"]["meta"]["family"] == by_tag["1"]["meta"]["family"]
          and by_tag["7"]["style"]["color"] == by_tag["1"]["style"]["color"]
          and by_tag["7"]["meta"]["declaredFamilies"] == ["W"], (by_tag["7"]["meta"], by_tag["1"]["meta"]["family"]))
    check("a diagonal is a third family with a third colour",
          len({s["style"]["color"] for s in specs}) == 3 and by_tag["D1"]["meta"]["family"] not in
          (by_tag["1"]["meta"]["family"], by_tag["A"]["meta"]["family"]), {t: s["meta"]["family"] for t, s in by_tag.items()})

    # ---- a partial axis ----
    partial = grid("g0", "S0", extra=[("2a", "U", (9, 0), (9, 4))])
    variants, table, specs = build([partial], storeys(1))
    p = next(s for s in specs if s["meta"]["tags"] == ["2a"])
    check("a partial axis is flagged and says so in its label",
          p["meta"]["partial"] is True and p["meta"]["label"].endswith("· partial"), p["meta"])
    check("full axes are not partial", all(s["meta"]["partial"] is False for s in specs if s is not p))

    # ---- a curved axis ----
    arc = grid("g0", "S0")
    arc["axes"].append(dg.make_axis("R", "W", "g0", [(10 + 5 * math.cos(t / 8 * math.pi), 4 + 5 * math.sin(t / 8 * math.pi))
                                                    for t in range(9)]))
    variants, table, specs = build([arc], storeys(1))
    r = next(s for s in specs if s["meta"]["tags"] == ["R"])
    check("a curved axis is a polyline with the ungrouped colour", r["kind"] == "polyline" and len(r["points"]) == 9
          and r["style"]["color"] == gl.UNGROUPED_COLOUR and r["meta"]["family"] is None, r["kind"])

    # ---- labels with many storeys ----
    many = storeys(6)
    variants, table, specs = build([grid(f"g{k}", f"S{k}") for k in range(6)], many)
    check("a label lists three storeys and counts the rest",
          specs[0]["meta"]["label"].endswith("Level 0, Level 1, Level 2 +3"), specs[0]["meta"]["label"])

    # ---- determinism ----
    reference = build(changed, levels)[2]
    shuffled = [dict(g, axes=list(g["axes"])) for g in changed]
    rng = random.Random(4)
    rng.shuffle(shuffled)
    for g in shuffled:
        rng.shuffle(g["axes"])
    check("specs do not depend on grid or axis input order", build(shuffled, levels)[2] == reference)
    check("specs are JSON", json.loads(json.dumps(reference)) == reference)

    # ---- the sidecar merge (scripts/grid_lines.py) ----
    cli = load_cli()
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)
        authored = {"id": "sidecar:circle", "kind": "circle", "radius": 1, "points": [[0, 0, 0]]}
        (out / "k1.json").write_text(json.dumps({"schema": 1, "model": "m.ifc", "note": "authored",
                                                 "lines": [authored, {"id": "grid:old:1", "points": [[0, 0], [1, 1]]}]}))
        (out / "index.json").write_text(json.dumps({"schema": 1, "files": {"k0": {"model": "other.ifc", "lines": 2, "note": "keep"},
                                                                           "k1": {"model": "m.ifc", "lines": 2, "note": "authored"}}}))
        summary = {"variants": [], "storeys": []}
        total, kept = cli.update_sidecar(out, "k1", "m.ifc", reference, summary)
        cli.update_index(out, "k1", "m.ifc", total, len(reference))
        doc = json.loads((out / "k1.json").read_text())
        check("authored lines and fields are kept, the old grid lines replaced",
              doc["lines"][0] == authored and doc["note"] == "authored" and kept == 1
              and [line["id"] for line in doc["lines"][1:]] == [s["id"] for s in reference], [line["id"] for line in doc["lines"][:3]])
        index = json.loads((out / "index.json").read_text())
        check("the index keeps other models and the note, and counts both kinds of line",
              index["files"]["k0"]["note"] == "keep" and index["files"]["k1"] ==
              {"model": "m.ifc", "lines": len(reference) + 1, "gridLines": len(reference), "note": "authored"}, index["files"]["k1"])
        before = (out / "k1.json").read_bytes()
        cli.update_sidecar(out, "k1", "m.ifc", reference, summary)
        check("a re-run gives the same bytes", (out / "k1.json").read_bytes() == before)
        cli.update_sidecar(out, "k1", "m.ifc", [], summary)
        doc = json.loads((out / "k1.json").read_text())
        check("a model that lost its grid keeps only the authored lines", doc["lines"] == [authored] and "grid" not in doc)
        check("a model without a grid and without a file gets no file",
              cli.update_sidecar(out, "k2", "n.ifc", [], summary) is None and not (out / "k2.json").exists())
        cli.update_sidecar(out, "k3", "new.ifc", reference, summary)
        cli.update_index(out, "k3", "new.ifc", len(reference), len(reference))
        index = json.loads((out / "index.json").read_text())
        check("a new model gets the generator note", index["files"]["k3"]["note"] == f"declared IfcGrid ({cli.GENERATOR})"
              and list(index["files"]) == sorted(index["files"]), index["files"]["k3"])

    failed = [r for r in RESULTS if not r[1]]
    for name, ok, detail in RESULTS:
        print(f"{'ok  ' if ok else 'FAIL'} {name}" + ("" if ok else f"  ->  {detail}"))
    print(f"\n{len(RESULTS) - len(failed)} of {len(RESULTS)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

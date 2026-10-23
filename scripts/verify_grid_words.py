"""Self-checks for src/modality: declared-grid cells, L1 grid words and L0
facade bands, on synthetic axes and elements. No IFC file is read and nothing
is written.

    uv run python scripts/verify_grid_words.py

Exit code 0 when every check passes, 1 otherwise.
"""

import json
import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from modality import declared_grid as dg  # noqa: E402
from modality import facade_bands as fb  # noqa: E402
from modality import grid_words as gw  # noqa: E402

RESULTS = []


def check(name, condition, detail=""):
    RESULTS.append((name, bool(condition), detail))


def rotate(point, angle_deg, about=(7.0, 3.0)):
    a = math.radians(angle_deg)
    x, y = point[0] - about[0], point[1] - about[1]
    return [about[0] + x * math.cos(a) - y * math.sin(a), about[1] + x * math.sin(a) + y * math.cos(a)]


XS = [0, 5, 13, 21, 29, 37, 45, 50]  # bays 5, 8, 8, 8, 8, 8, 5
YS = [0, 8, 16]


def base_axes(extra=(), angle=0.0):
    axes = [dg.make_axis(str(i + 1), "U", "g1", [rotate((x, -1), angle), rotate((x, 17), angle)])
            for i, x in enumerate(XS)]
    axes += [dg.make_axis("ABC"[j], "V", "g1", [rotate((-1, y), angle), rotate((51, y), angle)])
             for j, y in enumerate(YS)]
    for tag, grid, p0, p1 in extra:
        axes.append(dg.make_axis(tag, "U", grid, [rotate(p0, angle), rotate(p1, angle)]))
    return axes


def column(guid, x, y, angle=0.0):
    return {"guid": guid, "kind": "C", "storey": "s", "z": [0, 3], "point": rotate((x, y), angle)}


def segment(guid, kind, a, b, angle=0.0):
    return {"guid": guid, "kind": kind, "storey": "s", "z": [0, 3], "width": 0.2,
            "segment": [rotate(a, angle), rotate(b, angle)]}


def elements(angle=0.0):
    return [
        column("col-corner", 5.2, 8.1, angle),     # 0.22 m off the 5/B intersection
        column("col-side", 5.0, 4.0, angle),       # on axis 5, mid-side
        column("col-inner", 9.0, 4.0, angle),      # inside a cell, far from every axis
        segment("wall-1", "W", (5, 0), (5, 8), angle),      # along axis 2 (x = 5)
        segment("beam-1", "B", (13.3, 8), (21.0, 8), angle),  # along axis B, 7.7 of 8 m
        segment("wall-2", "W", (30, 2), (36, 2), angle),    # inside a cell
    ]


def run(axes, prims):
    geo = dg.storey_grid(axes)
    described = gw.describe_cells(geo["cells"], prims)
    symbols = {cid: d["symbol"] for cid, d in described.items()}
    return geo, described, gw.slot_words(geo["slots"], symbols)


def fingerprint(geo, described, words):
    return json.dumps({"cells": [[c["id"], round(c["area"], 3), described[c["id"]]] for c in geo["cells"]],
                       "words": words, "rhythm": {k: (v["word"], v.get("bandRhythm")) for k, v in geo["rhythm"].items()}},
                      sort_keys=True)


def main():
    # 1. uneven bays
    geo, described, words = run(base_axes(), elements())
    check("uneven bays: 7 x 2 cells", len(geo["cells"]) == 14, len(geo["cells"]))
    fam_x = next(n for n, f in geo["families"].items() if abs(f["angleDeg"] - 90) < 1)
    fam_y = next(n for n, f in geo["families"].items() if abs(f["angleDeg"]) < 1)
    check("uneven bays: rhythm ABBBBBA across x", geo["rhythm"][fam_x]["word"] == "ABBBBBA", geo["rhythm"][fam_x])
    check("uneven bays: rhythm AA across y", geo["rhythm"][fam_y]["word"] == "AA", geo["rhythm"][fam_y]["word"])
    check("two-family grid gets slot words", words is not None and len(words["rows"]) == 2, words)

    # elements: corner, side, interior; wall and beam along sides
    by_guid = {}
    for cid, d in described.items():
        for _, guids in d["corners"]:
            for g in guids:
                by_guid.setdefault(g, []).append(("corner", cid))
        for _, kinds in d["sides"]:
            for g in sum(kinds.values(), []):
                by_guid.setdefault(g, []).append(("side", cid))
        for g in sum(d["interior"].values(), []):
            by_guid.setdefault(g, []).append(("interior", cid))
    check("column 0.22 m off an intersection is a corner of 4 cells",
          [k for k, _ in by_guid.get("col-corner", [])] == ["corner"] * 4, by_guid.get("col-corner"))
    check("column on an axis between intersections is on a side of 2 cells",
          [k for k, _ in by_guid.get("col-side", [])] == ["side"] * 2, by_guid.get("col-side"))
    check("column inside a cell is interior to exactly 1 cell",
          [k for k, _ in by_guid.get("col-inner", [])] == ["interior"], by_guid.get("col-inner"))
    check("wall on axis 2 lies along a side of the 2 cells it separates",
          sorted(k for k, _ in by_guid.get("wall-1", [])) == ["side", "side"], by_guid.get("wall-1"))
    check("beam covering 7.7 of an 8 m side lies along 2 cells",
          sorted(k for k, _ in by_guid.get("beam-1", [])) == ["side", "side"], by_guid.get("beam-1"))
    check("wall inside a cell is interior to 1 cell",
          [k for k, _ in by_guid.get("wall-2", [])] == ["interior"], by_guid.get("wall-2"))
    check("symbols use C, B, W and '-'", all(len(d["symbol"]) == 3 and set(d["symbol"]) <= set("CBW-")
                                             for d in described.values()))

    # 2. a partial axis ending on two cross axes splits only the cells it crosses
    partial = (("1a", "g1", (2.5, 0), (2.5, 8)),)
    geo_p, described_p, words_p = run(base_axes(partial), [])
    check("partial axis: 15 cells (8 in the split row, 7 in the other)", len(geo_p["cells"]) == 15, len(geo_p["cells"]))
    axis_1a = next(a for a in geo_p["axes"] if a["id"] == "1a")
    check("partial axis is marked partial, with no dangling end",
          axis_1a["partial"] is True and axis_1a["danglingEnds"] == 0, (axis_1a["partial"], axis_1a["danglingEnds"]))
    spans = [t for row in words_p["rows"] for t in row.split() if "*" in t]
    check("the unsplit cell spans 2 slots in the other row", spans == ["---*2"], words_p["rows"])
    band = geo_p["rhythm"][fam_y].get("bandRhythm")
    check("band rhythm differs per row because of the partial axis",
          band is not None and len(set(band)) == 2, band)

    # 3. a dangling axis splits nothing and is kept on its cell
    dangling = (("D", "g1", (9, 2), (9, 6)),)
    geo_d, _, _ = run(base_axes(dangling), [])
    holders = [c["id"] for c in geo_d["cells"] if "D" in c["internalAxes"]]
    check("dangling axis: still 14 cells", len(geo_d["cells"]) == 14, len(geo_d["cells"]))
    check("dangling axis is recorded on exactly 1 cell", len(holders) == 1, holders)
    axis_d = next(a for a in geo_d["axes"] if a["id"] == "D")
    check("dangling axis has 2 dangling ends", axis_d["danglingEnds"] == 2, axis_d["danglingEnds"])

    # 4. the same line declared by two grid objects is merged
    duplicate = (("3'", "g2", (13, -1), (13, 17)),)
    geo_m, _, _ = run(base_axes(duplicate), [])
    merged = next(a for a in geo_m["axes"] if "3" in a["tags"])
    check("duplicate axis merged, tags and grids kept",
          merged["tags"] == ["3", "3'"] and merged["grids"] == ["g1", "g2"] and len(geo_m["cells"]) == 14,
          (merged["tags"], merged["grids"], len(geo_m["cells"])))

    # 5. rotation does not change cells, symbols or words
    reference = fingerprint(*run(base_axes(partial), elements()))
    rotated = fingerprint(*run(base_axes(partial, angle=30.0), elements(angle=30.0)))
    check("rotated by 30 degrees: identical cells, symbols and words", reference == rotated)

    # 6. input order does not change anything
    axes, prims = base_axes(partial), elements()
    random.Random(7).shuffle(axes)
    random.Random(8).shuffle(prims)
    check("shuffled axes and elements: identical output", fingerprint(*run(axes, prims)) == reference)

    # 7. a radial grid: 4 diameters and 2 rings give 16 cells and no slot table
    radial = []
    for k in range(4):
        a = math.radians(45 * k)
        radial.append(dg.make_axis(f"R{k}", "U", "g3", [(-11 * math.cos(a), -11 * math.sin(a)),
                                                         (11 * math.cos(a), 11 * math.sin(a))]))
    for r, tag in ((5.0, "r5"), (10.0, "r10")):
        ring = [(r * math.cos(math.radians(t)), r * math.sin(math.radians(t))) for t in range(0, 361, 5)]
        radial.append(dg.make_axis(tag, "V", "g3", ring))
    geo_r, _, words_r = run(radial, [])
    check("radial grid: 16 cells", len(geo_r["cells"]) == 16, len(geo_r["cells"]))
    check("radial grid: no slot words", words_r is None)

    # 8. a skewed grid: families at 0 and 60 degrees still get slots
    skew = [dg.make_axis(f"S{i}", "U", "g4", [(i * 6 - 10 * math.cos(math.radians(60)), -10 * math.sin(math.radians(60))),
                                             (i * 6 + 30 * math.cos(math.radians(60)), 30 * math.sin(math.radians(60)))])
            for i in range(4)]
    skew += [dg.make_axis(f"T{j}", "V", "g4", [(-20, j * 7.0), (60, j * 7.0)]) for j in range(4)]
    geo_s, _, words_s = run(skew, [])
    check("skewed grid: 3 x 3 cells and slot words", len(geo_s["cells"]) == 9 and words_s is not None,
          (len(geo_s["cells"]), words_s and words_s["rows"]))

    # 9. facade bands: a 20 x 10 m box of 0.3 m walls, four 1.5 m windows in the
    #    south wall, axes every 8 m plus one at 20 m
    def rect(guid, kind, x0, y0, x1, y1):
        return {"guid": guid, "kind": kind, "storey": "s", "rect": [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]}

    box = [rect("w-s", "W", -0.15, -0.15, 20.15, 0.15), rect("w-n", "W", -0.15, 9.85, 20.15, 10.15),
           rect("w-w", "W", -0.15, -0.15, 0.15, 10.15), rect("w-e", "W", 19.85, -0.15, 20.15, 10.15)]
    box += [rect(f"n{k}", "N", x, -0.1, x + 1.5, 0.1) for k, x in enumerate((2, 6, 10, 14))]
    box_axes = dg.merge_axes([dg.make_axis(t, "U", "g", [(x, -2), (x, 12)]) for t, x in (("1", 0), ("2", 8), ("3", 16), ("4", 20))]
                             + [dg.make_axis(t, "V", "g", [(-2, y), (22, y)]) for t, y in (("A", 0), ("B", 10))])
    runs, qa = fb.storey_bands(box, box_axes)
    check("box: 4 facade runs, the first along the south face", len(runs) == 4 and runs[0]["length"] == 20.3,
          [(r["id"], r["length"]) for r in runs])
    south = runs[0] if runs else {}
    check("south band: windows, bays split at the axes",
          south.get("band") == "W1 | W8 N6 W10 N6 W2 | W8 N6 W10 N6 W2 | W16 | W1", south.get("band"))
    check("the two window bays have the same word",
          [b["word"] for b in south.get("bays", [])][1:3] == ["W8 N6 W10 N6 W2"] * 2, south.get("bays"))
    check("coarse band uses size classes", south.get("bandCoarse", "").split()[:4] == ["W:XS", "|", "W:M", "N:M"],
          south.get("bandCoarse"))
    check("every window lands on a run", qa["windowsOnNoRun"] == 0 and qa["windows"] == 4, qa)
    shuffled = list(box)
    random.Random(9).shuffle(shuffled)
    check("facade bands do not depend on input order", fb.storey_bands(shuffled, box_axes)[0] == runs)

    failed = [r for r in RESULTS if not r[1]]
    for name, ok, detail in RESULTS:
        print(f"{'ok  ' if ok else 'FAIL'} {name}" + ("" if ok else f"  ->  {detail}"))
    print(f"\n{len(RESULTS) - len(failed)} of {len(RESULTS)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

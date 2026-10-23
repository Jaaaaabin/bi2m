"""Declared grids in the scene: the sidecar lines
scripts/grid_lines.py writes from a model's own IfcGrid, drawn by the Lines
(test) button.

For each model below: opens data/uploads/<key>/<key>.ifc through the upload
button's file chooser (a local open: nothing is uploaded, tiled or computed),
clicks Lines, and checks
  - every grid line of the model's sidecar is drawn, none skipped;
  - each sits at scene Y = ifcZ + T.y, T the model's coordinationMatrix
    translation (lineSpec.js `height: {ifcZ}`);
  - the model's own columns sit where Python puts them. IfcColumn GUIDs are
    read from the IFC text, their scene boxes from the viewer, and the share
    within 0.35 m of a drawn grid intersection (or of a drawn axis) is
    compared with the share measured with IfcOpenShell world shapes
    (grid_words.element_primitives against the same sidecar, 2026-10-06). A
    wrong translation or frame drives it to about 0.
The models cover both load paths. Two stream from tiles (the browser never
runs web-ifc on them, so T comes from the tile file): millimetres with a
second grid on its lowest storey, and centimetres. Two are parsed by web-ifc
(4558d77b has a tile folder but loads parsed): millimetres with the site
rotated -9 degrees, and metres. A plan-box comparison was tried and dropped
on 2026-10-06: a building box carries far-off elements (4558d77b's grid
covered 22 % of it while 0.889 of its columns sat on an axis, as in Python). The tiled fixture of
_common.STREAMED_MODEL (654d77285c2cbe1b) is not used.
Since 2026-10-21 a streamed model's column boxes come from the tile metadata
(cameraViews.computeGuidsBoundingBox), so
every column resolves whether or not its tile is fetched; the MIN_COLUMNS
SKIP stays for an older tile set with no box for a column. A model whose
upload or sidecar is missing is skipped. Writes nothing.
"""
import os, re, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import BASE_URL, CHROMIUM_ARGS
from playwright.sync_api import sync_playwright

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", ".."))
LINES_DIR = os.path.join(REPO, "Interfaces", "Frontend", "core", "public", "res", "lines")
V = "#viewerContainer1"
B = f"{V} .viewer-lines-btn"
TOL_M = 0.35  # grid_words.CORNER_TOL_M
MAX_COLUMNS = 150  # boxes are resolved one GUID at a time
MIN_COLUMNS = 5  # fewer resolved column boxes and the share check is skipped
# measure: "intersection" or "line"; expected: the IfcOpenShell share, all columns
MODELS = [
    {"key": "4558d77b1f18361e", "what": "parsed, site -9°, mm", "measure": "line", "expected": 0.889},
    {"key": "c99be381a798220e", "what": "tiled, mm, two grid variants", "measure": "line", "expected": 1.0},
    {"key": "3ef234726d638702", "what": "tiled, cm", "measure": "intersection", "expected": 1.0},
    {"key": "ca07d61c17be71f1", "what": "parsed by web-ifc", "measure": "intersection", "expected": 1.0},
]
# web-ifc 0.0.66 logs these while parsing; the first once per grid axis (it
# cannot mesh the IfcGrid's curve set). The fragments OPFS cache logs
# removeEntry on the streamed path after 60 s. None of them is this
# feature's error.
KNOWN_CONSOLE = re.compile(r"WEB-IFC|unexpected mesh type|bool aborted|removeEntry")

res = []
def check(n, ok, d=""):
    res.append(ok); print(f"  [{'PASS' if ok else 'FAIL'}] {n}" + (f" - {d}" if d else ""))

MODS = """
  const pick = (re, fallback) => performance.getEntriesByType('resource').map(e => e.name).filter(n => re.test(n)).pop() || fallback;
  const { viewerData } = await import(pick(/\\/viewerRegistry\\.js(\\?|$)/, '/viewerRegistry.js'));
  const lines = await import(pick(/\\/views\\/lines\\.js(\\?|$)/, '/views/lines.js'));
  const cv = await import(pick(/\\/cameraViews\\.js(\\?|$)/, '/cameraViews.js'));
  const vm = await import(pick(/\\/viewerModel\\.js(\\?|$)/, '/viewerModel.js'));
  const v = viewerData[0]; const world = v?.world; const model = v?.getCurrentModel?.() ?? null;
"""
LOADED_JS = "async () => {" + MODS + " return !!(v && v.hasModel && model); }"
DRAWN_JS = "async (guids) => {" + MODS + """
  const T = lines.coordinationTranslation(model);
  const grid = lines.listLines(world).filter(l => l.id.startsWith('grid:'))
    .map(l => ({ id: l.id, ifcZ: l.spec.height?.ifcZ ?? null, points: l.points }));
  const centres = [];
  for (const g of guids) {
    const b = await cv.computeGuidsBoundingBox(world.components, model, [g]);
    if (b) centres.push([(b.min.x + b.max.x) / 2, (b.min.z + b.max.z) / 2]);
  }
  return { T, grid, centres, streamed: !!vm.getModelContext(model)?.isStreamed };
}"""


def segments(lines):
    out = []
    for line in lines:
        pts = [(p[0], p[2]) for p in line["points"]]
        out += list(zip(pts, pts[1:]))
    return out


def intersections(segs):
    pts = []
    for i, (a, b) in enumerate(segs):
        for c, d in segs[i + 1:]:
            r = (b[0] - a[0], b[1] - a[1]); s = (d[0] - c[0], d[1] - c[1])
            den = r[0] * s[1] - r[1] * s[0]
            if abs(den) < 1e-12:
                continue
            t = ((c[0] - a[0]) * s[1] - (c[1] - a[1]) * s[0]) / den
            u = ((c[0] - a[0]) * r[1] - (c[1] - a[1]) * r[0]) / den
            if -1e-9 <= t <= 1 + 1e-9 and -1e-9 <= u <= 1 + 1e-9:
                pts.append((a[0] + t * r[0], a[1] + t * r[1]))
    return pts


def point_segment(p, a, b):
    ax, ay = b[0] - a[0], b[1] - a[1]
    n = ax * ax + ay * ay
    t = 0 if n == 0 else max(0, min(1, ((p[0] - a[0]) * ax + (p[1] - a[1]) * ay) / n))
    return ((p[0] - a[0] - t * ax) ** 2 + (p[1] - a[1] - t * ay) ** 2) ** 0.5


with sync_playwright() as p:
    b = p.chromium.launch(args=CHROMIUM_ARGS)
    for spec in MODELS:
        key = spec["key"]
        ifc = os.path.join(REPO, "data", "uploads", key, f"{key}.ifc")
        side_path = os.path.join(LINES_DIR, f"{key}.json")
        print(f"\n{key} ({spec['what']})")
        if not (os.path.exists(ifc) and os.path.exists(side_path)):
            print(f"  [SKIP] {key}: upload or sidecar missing (run scripts/grid_lines.py)")
            continue
        sidecar = json.load(open(side_path))
        expected_ids = {l["id"]: l for l in sidecar["lines"] if l["id"].startswith("grid:")}
        guids = sorted(set(re.findall(r"IFCCOLUMN\('([^']+)'", open(ifc, encoding="utf-8", errors="replace").read())))[:MAX_COLUMNS]

        pg = b.new_page(viewport={"width": 1400, "height": 900})
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.on("console", lambda m: m.type == "error" and not KNOWN_CONSOLE.search(m.text) and errs.append(m.text))
        pg.goto(BASE_URL, wait_until="networkidle")
        with pg.expect_file_chooser() as chooser:
            pg.click("#bulk-upload-btn")
        chooser.value.set_files(ifc)
        pg.wait_for_function(LOADED_JS, timeout=300000, polling=500)
        pg.wait_for_load_state("networkidle"); pg.wait_for_timeout(1500)

        pg.click(B)
        pg.wait_for_function(f"() => {{ const b = document.querySelector('{B}'); return b && !b.hasAttribute('aria-busy') && +document.querySelector('{V}').dataset.overlayLines > 0; }}", timeout=120000)
        pg.wait_for_timeout(500)
        got = pg.evaluate(DRAWN_JS, guids)
        drawn = {l["id"]: l for l in got["grid"]}
        check("every grid line of the sidecar is drawn, and nothing else under grid:",
              set(drawn) == set(expected_ids), f"{len(drawn)} drawn, {len(expected_ids)} in the sidecar")
        T = got["T"]
        heights_ok = all(abs(pt[1] - (expected_ids[i]["height"]["ifcZ"] + T[1])) < 1e-6
                         for i, l in drawn.items() for pt in l["points"])
        check("each sits at scene Y = ifcZ + T.y", heights_ok and len(drawn) > 0,
              f"T = [{T[0]:.3f}, {T[1]:.3f}, {T[2]:.3f}], {'streamed' if got['streamed'] else 'parsed'}")
        segs = segments(got["grid"])
        if spec["measure"] == "intersection":
            targets = intersections(segs)
            dist = [min(((c[0] - q[0]) ** 2 + (c[1] - q[1]) ** 2) ** 0.5 for q in targets) for c in got["centres"]] if targets else []
        else:
            dist = [min(point_segment(c, a, bb) for a, bb in segs) for c in got["centres"]]
        share = sum(d <= TOL_M for d in dist) / len(dist) if dist else 0.0
        what = f"columns on a drawn grid {spec['measure']} within {TOL_M} m: share matches IfcOpenShell's {spec['expected']}"
        detail = f"{share:.3f} of {len(got['centres'])} resolved of {len(guids)} columns read"
        if len(got["centres"]) >= MIN_COLUMNS:
            check(what, share >= spec["expected"] - 0.1, detail)
        else:
            # A streamed model fetches a tile's geometry only when the camera
            # comes near it.
            print(f"  [SKIP] {what} - {detail}, fewer than {MIN_COLUMNS} resolved")
        check("no page or console errors beyond web-ifc's known parse logs", not errs, "; ".join(errs[:3]))
        pg.close()
    b.close()

print(f"\n{sum(res)}/{len(res)} checks passed")

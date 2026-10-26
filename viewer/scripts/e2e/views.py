"""Views harness: the live checks behind the view-spec work.

Phase 0 ("pin and verify", nothing in the app changed yet) asks five questions
of the REAL viewer that no unit test can answer, and records a pose baseline
that later phases must reproduce to 1e-6:

  1. Axis mapping - a record's `x,y` (IFC plan coordinates, from the
     detectors) against where its members' geometry actually sits in the
     three.js scene (Y-up). Needed before any intent frame can be trusted.
  2. Roll at the pole - today's "Top" has an implicit azimuth 0 (screen-up is
     world -Z), and `rotateTo(theta, 0)` after a look-at keeps a chosen
     azimuth through `fitToSphere`. The vector round trip in
     tests/unit/direction.test.js cannot see this: roll is hidden state.
  3. Pose solver - views/pose.js reproduces camera-controls' fit distance
     (perspective) and fit zoom (orthographic) on the live canvas.
  4. Clipper - the plane's sign convention, and that the refer split's
     cloned materials are clipped too (renderer-level planes).
  5. Baseline - position/target/distance for every preset, the switcher,
     a Refer, and the orthographic zoom. `--baseline` writes
     out/views_baseline.json; a plain run compares against it.

Read-only on review state: loads example_autcon via the example flyout, clicks
presets / Ortho / Refer only. Never Accept, Reject, Compute or Run.
Run:  python3 scripts/e2e/views.py [--baseline]
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import BASE_URL, OUT, CHROMIUM_ARGS
import math
from playwright.sync_api import sync_playwright

URL, V = BASE_URL, "#viewerContainer1"
MODEL = "example_autcon.ifc"
HERE = os.path.dirname(os.path.abspath(__file__))
SHARD = os.path.join(HERE, "..", "..", "public", "res", "intents", "34b3f3dac339ade6.json")
BASELINE = os.path.join(OUT, "views_baseline.json")
WRITE_BASELINE = "--baseline" in sys.argv
POSE_TOL = 1e-6

res = []
def check(n, ok, d=""):
    res.append((n, ok)); print(f"  [{'PASS' if ok else 'FAIL'}] {n}" + (f" - {d}" if d else ""))

# ---- the records this harness is pinned to (content key 34b3f3dac339ade6) ----
shard = json.load(open(SHARD))["intents"]
COLSUPPORT = next(i for i in shard if i["type"] == "structural_column_support" and len(i["members"]) >= 4)
# The column row at X = 39.179 m: a per-storey row until 2026-10-07, a row
# claim across the storeys since `alignment` folds rows that recur. Either
# carries axis/value, which is all the frame and the box below read.
ALIGN_X = next(i for i in shard if i["type"] in ("alignment_column_group", "grid_line_consistency")
               and i["evidence"]["metrics"]["axis"] == "X" and abs(i["evidence"]["metrics"]["value"] - 39.179) < 0.01)
# Three column stacks whose (x, y) differ by more than a metre in BOTH axes,
# so the y -> z sign and the two offsets can be solved, not guessed.
COLSUPPORTS = []
for _rec in (i for i in shard if i["type"] == "structural_column_support"):
    _m = _rec["evidence"]["metrics"]
    if all(abs(_m["x"] - c["evidence"]["metrics"]["x"]) > 1 and abs(_m["y"] - c["evidence"]["metrics"]["y"]) > 1
           for c in COLSUPPORTS):
        COLSUPPORTS.append(_rec)
    if len(COLSUPPORTS) == 3:
        break

# ---- in-page module access -------------------------------------------------
# Resolve every URL from the resources Vite actually served: a bare path would
# import a SECOND module instance after any edit (cache-busting ?t=). The
# library bundles are reached the same way, so `OBC.Clipper` and `THREE` are
# the very classes the app is running.
MODS = """
  const pick = (re, fallback) => performance.getEntriesByType('resource').map(e => e.name)
    .filter(n => re.test(n)).pop() || fallback;
  const { viewerData } = await import(pick(/\\/viewerRegistry\\.js(\\?|$)/, '/viewerRegistry.js'));
  const cv = await import(pick(/\\/cameraViews\\.js(\\?|$)/, '/cameraViews.js'));
  const OBC = await import(pick(/@thatopen_components\\.js(\\?|$)/, '/node_modules/.vite/deps/@thatopen_components.js'));
  const THREE = await import(pick(/\\/deps\\/three\\.js(\\?|$)/, '/node_modules/.vite/deps/three.js'));
  const v = viewerData[0];
  const world = v.world, c = world.camera.controls;
  const model = v.fragments.groups.values().next().value;
  const components = world.components;
"""

POSE_JS = "async () => {" + MODS + """
  const p = c.getPosition(new THREE.Vector3()), t = c.getTarget(new THREE.Vector3());
  const d = [p.x - t.x, p.y - t.y, p.z - t.z]; const n = Math.hypot(...d) || 1;
  return {
    position: [p.x, p.y, p.z], target: [t.x, t.y, t.z],
    direction: d.map(x => x / n), distance: c.distance,
    elevation: 90 - Math.atan2(Math.hypot(d[0], d[2]), d[1]) * 180 / Math.PI,
    theta: c.azimuthAngle, polar: c.polarAngle,
    projection: world.camera.projection.current, zoom: world.camera.three.zoom,
    fov: world.camera.threePersp.fov, aspect: world.camera.threePersp.aspect,
  };
}"""

BOX_JS = "async (guids) => {" + MODS + """
  const box = await cv.computeGuidsBoundingBox(components, model, guids);
  if (!box) return null;
  const ctr = box.getCenter(new THREE.Vector3()), size = box.getSize(new THREE.Vector3());
  return { center: [ctr.x, ctr.y, ctr.z], size: [size.x, size.y, size.z] };
}"""

BUILDING_JS = "async () => {" + MODS + """
  const box = cv.computeBuildingBoundingBox(components, v.classifier, model);
  const s = box.getBoundingSphere(new THREE.Sphere());
  const o = world.camera.threeOrtho;
  return { radius: s.radius, center: [s.center.x, s.center.y, s.center.z],
           min: [box.min.x, box.min.y, box.min.z], max: [box.max.x, box.max.y, box.max.z],
           fitDistance: c.getDistanceToFitSphere(s.radius),
           ortho: { width: o.right - o.left, height: o.top - o.bottom } };
}"""

# Where a world point lands on screen, in NDC, through the ACTIVE camera.
PROJECT_JS = "async ([x, y, z]) => {" + MODS + """
  // An instant camera-controls move is written onto the camera by its next
  // update(); under SwiftShader a frame can take longer than a CDP round
  // trip, so settle explicitly (the same one update(0) applyView.js makes).
  c.update(0);
  const cam = world.camera.three; cam.updateMatrixWorld(true); cam.updateProjectionMatrix();
  const p = new THREE.Vector3(x, y, z).project(cam);
  return [p.x, p.y, p.z];
}"""

# Phase-0 item 2's mechanism: a look-at straight down, then an explicit theta
# at the pole, then the same fitToSphere the presets use.
ROLL_JS = "async ([azDeg]) => {" + MODS + """
  const box = cv.computeBuildingBoundingBox(components, v.classifier, model);
  const s = box.getBoundingSphere(new THREE.Sphere());
  const t = c.getTarget(new THREE.Vector3());
  const R = Math.max(c.distance, 1);
  await c.setLookAt(t.x, t.y + R, t.z, t.x, t.y, t.z, false);
  const thetaAfterLookAt = c.azimuthAngle;
  await c.rotateTo(azDeg * Math.PI / 180, 0, false);
  await c.fitToSphere(s, false);
  return { thetaAfterLookAt, theta: c.azimuthAngle, polar: c.polarAngle, distance: c.distance };
}"""

# Distinct-colour count of the live render, sampled every 97th pixel - the
# same measure camera_panel.py uses to tell a blank frame from a real one.
COLOURS_JS = "async () => {" + MODS + """
  const { captureWorldPng } = await import(pick(/\\/snapshot\\.js(\\?|$)/, '/snapshot.js'));
  const live = captureWorldPng(world);
  const img = new Image(); img.src = live.dataUrl; await img.decode();
  const cnv = document.createElement('canvas'); cnv.width = img.width; cnv.height = img.height;
  const g = cnv.getContext('2d'); g.drawImage(img, 0, 0);
  const d = g.getImageData(0, 0, cnv.width, cnv.height).data;
  const seen = new Set();
  for (let i = 0; i < d.length; i += 4 * 97) seen.add(`${d[i]},${d[i+1]},${d[i+2]}`);
  return seen.size;
}"""

CLIP_JS = "async ([nx, ny, nz, px, py, pz]) => {" + MODS + """
  const clipper = components.get(OBC.Clipper);
  clipper.deleteAll();
  const plane = clipper.createFromNormalAndCoplanarPoint(world, new THREE.Vector3(nx, ny, nz), new THREE.Vector3(px, py, pz));
  plane.visible = false;           // the helper quad must not be in the picture
  world.renderer.update();
  return { planes: clipper.list.length, rendererPlanes: world.renderer.three.clippingPlanes.length,
           local: world.renderer.three.localClippingEnabled };
}"""

UNCLIP_JS = "async () => {" + MODS + """
  components.get(OBC.Clipper).deleteAll();
  world.renderer.update();
  return world.renderer.three.clippingPlanes.length;
}"""

def rel(a, b):
    return abs(a - b) / max(abs(b), 1e-12)

with sync_playwright() as p:
    b = p.chromium.launch(args=CHROMIUM_ARGS)
    pg = b.new_page(viewport={"width": 1400, "height": 900})
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.on("console", lambda m: m.type == "error" and errs.append(m.text))
    pg.goto(URL, wait_until="networkidle")
    pg.click("#example-models-btn")
    pg.wait_for_selector(f'.example-models-item[data-file-name="{MODEL}"]', timeout=20000)
    pg.click(f'.example-models-item[data-file-name="{MODEL}"]')
    pg.wait_for_selector(f"{V} .intent-row", timeout=180000, state="attached")
    pg.wait_for_load_state("networkidle")
    if not pg.locator(V).evaluate("el => el.classList.contains('camera-open')"):
        pg.click(f"{V} .viewer-camera-toggle-btn")
    pg.wait_for_timeout(600)

    pose = lambda: pg.evaluate(POSE_JS)

    def wait_pose(predicate, what, tries=60):
        """Polls the pose until `predicate` holds twice in a row - a click returns
        when the event dispatches, never when the handler's fit has landed."""
        ok = 0
        for _ in range(tries):
            s = pose()
            ok = ok + 1 if predicate(s) else 0
            if ok >= 2:
                return s
            pg.wait_for_timeout(100)
        raise AssertionError(f"{what}: pose never settled (last {s})")

    def dot(a, b):
        return sum(x * y for x, y in zip(a, b))

    def click_direction(selector, expected_dir, what):
        pg.click(f"{V} {selector}")
        return wait_pose(lambda s: dot(s["direction"], expected_dir) > 0.9999, what)

    SQ = math.sqrt(0.5)
    SIDE45 = [SQ * math.cos(math.radians(45)), math.sin(math.radians(45)), SQ * math.cos(math.radians(45))]

    # ======================================================================
    print("\n=== 5. Baseline poses: the presets, the switcher ===")
    baseline = {}
    baseline["top"] = click_direction(".viewer-fit-max-btn", [0, 1, 0], "Top")
    baseline["side45"] = click_direction(".viewer-side-view-btn", SIDE45, "Side 45")
    for label, d in [("front", [0, 0, 1]), ("back", [0, 0, -1]), ("left", [-1, 0, 0]), ("right", [1, 0, 0])]:
        shown = pg.inner_text(f"{V} .viewer-elevation-view-btn").strip().lower()
        check(f"switcher offers '{label}' next", shown == label, shown)
        baseline[label] = click_direction(".viewer-elevation-view-btn", d, label)
    print("  poses:", {k: (round(s["distance"], 3), round(s["elevation"], 2)) for k, s in baseline.items()})

    # ======================================================================
    print("\n=== 2. Roll at the pole ===")
    top = click_direction(".viewer-fit-max-btn", [0, 1, 0], "Top")
    check("Top lands at elevation 90", abs(top["elevation"] - 90) < 0.01, f"{top['elevation']:.4f}")
    theta_top = math.remainder(top["theta"], 2 * math.pi)
    check("Top's implicit azimuth is 0 (theta = atan2(0,0) after setLookAt)", abs(theta_top) < 1e-6,
          f"theta {theta_top:.2e} rad")
    R = top["distance"]
    t = top["target"]
    ndc = pg.evaluate(PROJECT_JS, [t[0], t[1], t[2] - R * 0.25])
    check("in Top, world -Z lands straight ABOVE screen centre (screen-up = -Z)", abs(ndc[0]) < 1e-3 and ndc[1] > 0.05,
          f"ndc {ndc[0]:.4f}, {ndc[1]:.4f}")
    roll = pg.evaluate(ROLL_JS, [45])
    check("a straight-down look-at reports theta 0", abs(math.remainder(roll["thetaAfterLookAt"], 2 * math.pi)) < 1e-6)
    check("rotateTo(45 deg, 0) then fitToSphere keeps theta = 45 deg",
          abs(math.degrees(math.remainder(roll["theta"], 2 * math.pi)) - 45) < 1e-4, f"{math.degrees(roll['theta']):.6f} deg")
    check("  and stays at the pole (polar = makeSafe epsilon)", roll["polar"] < 1e-4, f"polar {roll['polar']:.2e}")
    check("  while the elevation readout still says 90",
          abs(float(pg.input_value(f"{V} .viewer-camera-angle-value")) - 90) < 0.06, pg.input_value(f"{V} .viewer-camera-angle-value"))
    ndc2 = pg.evaluate(PROJECT_JS, [t[0], t[1], t[2] - R * 0.25])
    asp = top["aspect"]
    # Measured 2026-10-01: with theta = +45 deg the -Z point lands upper-RIGHT,
    # i.e. a positive theta rolls the picture clockwise by theta. Recorded as
    # the sign convention frame.js has to use for "az = yaw + 180" plans.
    ang = math.degrees(math.atan2(ndc2[0] * asp, ndc2[1]))
    check("  and world -Z now lands 45 deg clockwise of vertical: the azimuth became the roll", abs(ang - 45) < 1.0,
          f"{ang:.2f} deg (ndc {ndc2[0]:.3f}, {ndc2[1]:.3f})")
    back = click_direction(".viewer-fit-max-btn", [0, 1, 0], "Top again")
    check("clicking Top again returns theta to 0 (the preset carries no azimuth)",
          abs(math.remainder(back["theta"], 2 * math.pi)) < 1e-6, f"{back['theta']:.2e}")
    check("  at the same distance as before", abs(back["distance"] - top["distance"]) < 1e-6,
          f"{back['distance']:.6f} vs {top['distance']:.6f}")

    # ======================================================================
    print("\n=== 3. Pose solver vs camera-controls ===")
    side = click_direction(".viewer-side-view-btn", SIDE45, "Side 45")
    bld = pg.evaluate(BUILDING_JS)
    r, fov, aspect = bld["radius"], side["fov"], side["aspect"]
    vfov = math.radians(fov); hfov = 2 * math.atan(math.tan(vfov / 2) * aspect)
    solver = r / math.sin((vfov if aspect > 1 else hfov) / 2)
    check("perspective: controls.distance after the fit == r / sin(fov_lim / 2)", rel(side["distance"], solver) < 1e-6,
          f"{side['distance']:.6f} vs {solver:.6f} (r {r:.3f}, fov {fov}, aspect {aspect:.4f})")
    check("  and equals controls.getDistanceToFitSphere(r)", rel(bld["fitDistance"], solver) < 1e-9,
          f"{bld['fitDistance']:.6f}")
    pg.click(f"{V} .viewer-projection-toggle-btn")
    wait_pose(lambda s: s["projection"] == "Orthographic", "to ortho")
    pg.click(f"{V} .viewer-side-view-btn")
    pg.wait_for_timeout(400)
    ortho = pose(); bld2 = pg.evaluate(BUILDING_JS)
    zoom_solver = min(bld2["ortho"]["width"] / (2 * r), bld2["ortho"]["height"] / (2 * r))
    check("orthographic: zoom after the fit == min(w, h) / 2r", rel(ortho["zoom"], zoom_solver) < 1e-6,
          f"{ortho['zoom']:.6f} vs {zoom_solver:.6f} (frustum {bld2['ortho']['width']:.3f} x {bld2['ortho']['height']:.3f})")
    baseline["side45_ortho"] = ortho
    pg.click(f"{V} .viewer-projection-toggle-btn")
    wait_pose(lambda s: s["projection"] == "Perspective", "to persp")

    MAPPING = None  # (x_off, z_off, y_to_z_sign, t_sense) once Phase 1 has solved it, for the BCF camera check
    # ======================================================================
    print("\n=== 1. Axis mapping: record metrics vs scene geometry ===")
    # The detectors measure `x,y` in the IFC file's own plan coordinates
    # (ifc_units.placement_xy, metres). The viewer loads through
    # OBC.IfcLoader.load(data, coordinate = true), which shifts the model to
    # the origin and records the shift on the group as `coordinationMatrix`.
    # So the mapping to look for is: a Y-up axis swap PLUS that translation.
    # Three stacks with distinct (x, y) separate the two possible y -> z signs.
    coord = pg.evaluate("async () => {" + MODS + """
      const e = model.coordinationMatrix.elements;
      return { translation: [e[12], e[13], e[14]], elements: Array.from(e) };
    }""")
    T = coord["translation"]
    print(f"  coordinationMatrix translation: {[round(v, 3) for v in T]}")
    samples = []
    for rec in COLSUPPORTS:
        mm = rec["evidence"]["metrics"]
        box = pg.evaluate(BOX_JS, [m_["guid"] for m_ in rec["members"]])
        if box:
            samples.append((mm["x"], mm["y"], box["center"], box["size"]))
    check("three column stacks with distinct (x, y) have geometry to measure", len(samples) == 3,
          f"{len(samples)} of {len(COLSUPPORTS)}")
    if len(samples) == 3:
        # For each hypothesis the per-record offset must be the SAME constant.
        hyps = {}
        for sign, label in ((-1, "z = -y + c"), (+1, "z = +y + c")):
            cs = [c[2] - sign * y for _, y, c, _ in samples]
            hyps[label] = (sum(cs) / 3, max(cs) - min(cs))
        xs = [c[0] - x for x, _, c, _ in samples]
        x_off, x_spread = sum(xs) / 3, max(xs) - min(xs)
        best = min(hyps, key=lambda k: hyps[k][1])
        z_off, z_spread = hyps[best]
        check("the x offset is one constant across the three stacks (IFC x -> three x + c)", x_spread < 0.05,
              f"c = {x_off:+.3f}, spread {x_spread:.4f}")
        check(f"one y -> z sign is consistent across the three stacks: {best}", z_spread < 0.05,
              f"c = {z_off:+.3f}, spread {z_spread:.4f}; other hypothesis spread {max(h[1] for h in hyps.values()):.3f}")
        # Does the coordination matrix explain the offsets? Try it and its inverse.
        explained = (abs(x_off - T[0]) < 0.05 and abs(z_off - T[2]) < 0.05)
        explained_inv = (abs(x_off + T[0]) < 0.05 and abs(z_off + T[2]) < 0.05)
        check("the offsets ARE the coordinationMatrix translation (or its inverse)", explained or explained_inv,
              f"offsets ({x_off:+.3f}, {z_off:+.3f}) vs T ({T[0]:+.3f}, {T[2]:+.3f}); " +
              ("direct" if explained else "inverse" if explained_inv else "neither"))
        print(f"  MAPPING: scene = (x {x_off:+.3f}, Y-up, {best.replace(' + c', f' {z_off:+.3f}')})" +
              f"  [{'coordinationMatrix' if explained else 'inverse coordinationMatrix' if explained_inv else 'unexplained'}]")
        if explained or explained_inv:
            MAPPING = (x_off, z_off, +1 if best.startswith("z = +y") else -1, +1 if explained else -1)
        heights = [(c[1] - s[1] / 2, c[1] + s[1] / 2) for _, _, c, s in samples]
        print(f"  stacks span y {min(h[0] for h in heights):.2f}..{max(h[1] for h in heights):.2f} m")
    am = ALIGN_X["evidence"]["metrics"]
    abox = pg.evaluate(BOX_JS, [mm["guid"] for mm in ALIGN_X["members"]])
    if abox and len(samples) == 3:
        check("alignment 'axis X' group is thin in x, long in z, at scene x == value + c",
              abs(abox["center"][0] - (am["value"] + x_off)) < 0.5 and abox["size"][0] < abox["size"][2],
              f"value {am['value']} + c -> {am['value'] + x_off:.3f}; centre x {abox['center'][0]:.3f}, size x {abox['size'][0]:.2f} z {abox['size'][2]:.2f}")

    # ======================================================================
    print("\n=== 4. Clipper ===")
    before = pg.evaluate(COLOURS_JS)
    cx_, _, cz_ = bld["center"]; floor = bld["min"][1]
    reg = pg.evaluate(CLIP_JS, [0, -1, 0, cx_, floor - 1.0, cz_])
    check("a plane registers with the renderer (renderer-level, local clipping on)",
          reg["planes"] == 1 and reg["rendererPlanes"] == 1 and reg["local"], str(reg))
    clipped = pg.evaluate(COLOURS_JS)
    check("normal (0,-1,0) below the model clips EVERYTHING above it", clipped <= max(3, before * 0.25),
          f"{before} colours before, {clipped} after")
    pg.evaluate(UNCLIP_JS)
    pg.evaluate(CLIP_JS, [0, 1, 0, cx_, floor - 1.0, cz_])
    kept = pg.evaluate(COLOURS_JS)
    check("normal (0,+1,0) at the same point clips nothing", kept >= before * 0.75, f"{before} -> {kept}")
    left = pg.evaluate(UNCLIP_JS)
    check("deleteAll leaves no plane on the renderer", left == 0, str(left))

    # ---- Refer, then clip again: are the split-off clones clipped too? ----
    print("\n=== Refer baseline + clipping of the referred clones ===")
    click_direction(".viewer-side-view-btn", SIDE45, "Side 45 before Refer")
    rid = COLSUPPORT["id"]
    pg.evaluate("""(id) => {
      const row = document.querySelector(`#viewerContainer1 [data-intent-id="${id}"]`);
      for (let el = row; el; el = el.parentElement) if (el.tagName === 'DETAILS') el.open = true;
    }""", rid)
    pg.click(f'{V} [data-intent-id="{rid}"] .intent-refer-btn')
    pg.wait_for_selector(f'{V} [data-intent-id="{rid}"][data-refer-status="done"]', timeout=60000)
    pg.wait_for_timeout(300)
    baseline["refer_colsupport_after_side45"] = pose()
    print("  refer pose:", round(baseline["refer_colsupport_after_side45"]["distance"], 3), "m")
    with_refer = pg.evaluate(COLOURS_JS)
    pg.evaluate(CLIP_JS, [0, -1, 0, cx_, floor - 1.0, cz_])
    clipped_refer = pg.evaluate(COLOURS_JS)
    check("with a Refer active, the clip-all plane also removes the referred (cloned) members",
          clipped_refer <= max(3, with_refer * 0.25), f"{with_refer} colours -> {clipped_refer}")
    pg.evaluate(UNCLIP_JS)

    # ======================================================================
    print("\n=== Baseline file ===")
    keep = {k: {f: s[f] for f in ("position", "target", "direction", "distance", "elevation", "projection", "zoom")}
            for k, s in baseline.items()}
    keep["_meta"] = {"model": MODEL, "fov": side["fov"], "aspect": side["aspect"], "viewport": [1400, 900]}
    if WRITE_BASELINE or not os.path.exists(BASELINE):
        json.dump(keep, open(BASELINE, "w"), indent=1)
        print(f"  wrote {BASELINE}")
    else:
        ref = json.load(open(BASELINE))
        if ref.get("_meta", {}).get("aspect") and abs(ref["_meta"]["aspect"] - side["aspect"]) > 1e-6:
            print(f"  NOTE: aspect differs from the baseline ({ref['_meta']['aspect']} vs {side['aspect']}); distances will not compare")
        for k, s in keep.items():
            if k == "_meta" or k not in ref:
                continue
            d = max(abs(a - b) for a, b in zip(s["position"] + s["target"], ref[k]["position"] + ref[k]["target"]))
            dz = abs(s["zoom"] - ref[k]["zoom"])
            check(f"pose '{k}' matches the baseline to {POSE_TOL:g}", d < POSE_TOL and dz < POSE_TOL,
                  f"max |delta| {d:.2e}, zoom delta {dz:.2e}")

    # ======================================================================
    # Phase 1 (2026-10-01): presets and Refer are view specs now; the camera
    # panel gained a closed-by-default "View" disclosure with the azimuth
    # readout, a frame select and a View-JSON box whose Apply is the DOM
    # contract a script uses (data-view-status + the view-applied event).
    print("\n=== Phase 1: view specs through the panel ===")
    click_direction(".viewer-side-view-btn", SIDE45, "Side 45")
    az_text = pg.input_value(f"{V} .viewer-camera-azimuth-value").strip()
    check("the azimuth input reads 45 after Side 45 (owner's 2026-10-01 layout: elevation · azimuth · distance)",
          abs(float(az_text) - 45) < 0.11, az_text)
    pg.evaluate(f"""() => {{
      window.__views = [];
      document.querySelector('{V}').addEventListener('view-applied', e => window.__views.push(e.detail.record));
    }}""")

    # A spec is applied the way the batch driver does it: the app's own
    # applyView through the module hook. The contract
    # stays observable - data-view-status on the tile and the view-applied
    # event are set by applyView itself, which is what the checks below read.
    APPLY_JS = "async ([spec]) => {" + MODS + """
      const m = await import(pick(/\\/views\\/applyView\\.js(\\?|$)/, '/views/applyView.js'));
      try {
        const record = await m.applyView(world, spec, { chosenBy: 'manual', score: true });
        const r = record.resolved;
        const msg = `${record.label} → az ${r.worldAzimuthDeg.toFixed(1)}° el ${r.worldElevationDeg.toFixed(1)}° · `
          + (r.projection === 'Orthographic' ? `${r.zoom.toFixed(2)}×` : `${r.distance.toFixed(1)} m`)
          + (r.frame.kind === 'world' ? '' : ` · ${r.frame.kind} frame ${r.frame.yawDeg.toFixed(1)}° (${r.frame.source})`);
        return { status: document.querySelector('#viewerContainer1').dataset.viewStatus, message: msg };
      } catch (e) {
        return { status: document.querySelector('#viewerContainer1').dataset.viewStatus, message: 'error: ' + (e?.message ?? String(e)) };
      }
    }"""

    def apply_json(spec):
        r = pg.evaluate(APPLY_JS, [spec])
        return r["status"], r["message"]

    st, msg = apply_json({"direction": {"azimuthDeg": 90, "elevationDeg": 90}})
    s = pose()
    th = math.degrees(s["theta"]) % 360
    check("a pasted plan with azimuth 90 applies: status done, theta 90°, at the pole",
          st == "done" and abs(th - 90) < 1e-3 and s["polar"] < 1e-4,
          f"status {st}, theta {th:.4f}°, polar {s['polar']:.1e}; {msg}")
    t = s["target"]
    ndc4 = pg.evaluate(PROJECT_JS, [t[0], t[1], t[2] - s["distance"] * 0.25])
    ang4 = math.degrees(math.atan2(ndc4[0] * s["aspect"], ndc4[1])) % 360
    check("  and the picture is rolled 90° clockwise (world -Z points right)", abs(ang4 - 90) < 1.0, f"{ang4:.2f}°")
    rec = pg.evaluate("() => window.__views.at(-1)")
    check("view-applied carried the record: spec az 90 / el 90, resolved world az 90, chosenBy manual, this model's key",
          rec is not None and rec["spec"]["direction"] == {"azimuthDeg": 90, "elevationDeg": 90}
          and abs(rec["resolved"]["worldAzimuthDeg"] - 90) < 1e-3 and rec["log"]["chosenBy"] == "manual"
          and rec["model"]["fileKey"] == "34b3f3dac339ade6",
          json.dumps({k: rec[k] for k in ("label", "log", "model")}) if rec else "no record")

    st, msg = apply_json({"scope": {"kind": "building"}, "frame": {"kind": "building"},
                          "direction": {"azimuthDeg": 0, "elevationDeg": 0}})
    rec = pg.evaluate("() => window.__views.at(-1)")
    fr = (rec or {}).get("resolved", {}).get("frame", {})
    check("a building-frame spec resolves the frame from the walls",
          st == "done" and fr.get("source") == "walls" and 0 <= fr.get("yawDeg", -1) < 90,
          f"yaw {fr.get('yawDeg')}, source {fr.get('source')}, share {fr.get('share')}, count {fr.get('count')}; {msg}")
    s = pose()
    world_az = math.degrees(s["theta"]) % 360
    check("  and the camera's world azimuth equals the frame yaw",
          abs(math.remainder(world_az - fr.get("yawDeg", 0), 360)) < 0.01, f"camera {world_az:.3f}° vs yaw {fr.get('yawDeg', 0)}")
    check("  at the whole-building fit distance of the baseline", abs(s["distance"] - keep["side45"]["distance"]) < 1e-6,
          f"{s['distance']:.6f} vs {keep['side45']['distance']:.6f}")

    st, msg = apply_json({"scene": {"outlines": True}})
    check("a spec using the one unbuilt field is refused by name, with the reason", st == "error" and "PostproductionRenderer" in msg, f"{st}: {msg[:80]}")
    st, msg = apply_json({"scope": {"kind": "intent", "intentId": rid}, "direction": {"azimuthDeg": 45, "elevationDeg": 20}})
    rec = pg.evaluate("() => window.__views.at(-1)")
    check("an intent scope by id frames that intent (4 members) from the requested angle",
          st == "done" and rec and rec["intentId"] == rid and rec["resolved"]["scope"]["guidCount"] == 4
          and abs(rec["resolved"]["worldElevationDeg"] - 20) < 1e-3, f"{st}; {msg}")

    # ---- saved views persist across a reload ----
    click_direction(".viewer-side-view-btn", SIDE45, "Side 45 before saving")
    pg.fill(f"{V} .viewer-view-name-input", "phase1")
    pg.click(f"{V} .viewer-save-view-btn")
    saved_pose = pose()
    names = pg.locator(f"{V} .viewer-saved-view-name").all_inner_texts()
    check("Save adds a row named from the box", "phase1" in names, " | ".join(names))
    pg.reload(wait_until="networkidle")
    pg.click("#example-models-btn")
    pg.wait_for_selector(f'.example-models-item[data-file-name="{MODEL}"]', timeout=20000)
    pg.click(f'.example-models-item[data-file-name="{MODEL}"]')
    pg.wait_for_selector(f"{V} .intent-row", timeout=180000, state="attached")
    pg.wait_for_load_state("networkidle")
    if not pg.locator(V).evaluate("el => el.classList.contains('camera-open')"):
        pg.click(f"{V} .viewer-camera-toggle-btn")
    pg.wait_for_timeout(600)
    names = pg.locator(f"{V} .viewer-saved-view-name").all_inner_texts()
    check("the saved view is back after a reload (bi2m:views:<content key>)", names == ["phase1"], " | ".join(names))
    if "phase1" in names:
        pg.click(f"{V} .viewer-saved-view-name")
        pg.wait_for_selector(f'{V} .viewer-saved-view-name[data-recall-status="done"]', timeout=20000)
        s = pose()
        d = max(abs(a - b) for a, b in zip(s["position"] + s["target"], saved_pose["position"] + saved_pose["target"]))
        check("  and recalling it lands on the saved pose", d < 1e-6, f"max |delta| {d:.2e}")
        pg.click(f"{V} .viewer-saved-view-delete")

    # ---- Refer carries its record ----
    pg.evaluate(f"""() => {{ window.__refer = null;
      document.querySelector('{V}').addEventListener('intent-refer-complete', e => window.__refer = e.detail); }}""")
    pg.evaluate("""(id) => {
      const row = document.querySelector(`#viewerContainer1 [data-intent-id="${id}"]`);
      for (let el = row; el; el = el.parentElement) if (el.tagName === 'DETAILS') el.open = true;
    }""", rid)
    pg.click(f'{V} [data-intent-id="{rid}"] .intent-refer-btn')
    pg.wait_for_selector(f'{V} [data-intent-id="{rid}"][data-refer-status="done"]', timeout=60000)
    detail = pg.evaluate("() => window.__refer")
    rec = (detail or {}).get("record") or {}
    check("intent-refer-complete now carries the view record (the id first, as before)",
          bool(detail) and detail.get("intentId") == rid and rec.get("intentId") == rid
          and rec.get("log", {}).get("chosenBy") == "refer" and rec.get("resolved", {}).get("scope", {}).get("guidCount") == 4,
          json.dumps({"log": rec.get("log"), "label": rec.get("label")}) if rec else str(detail))

    # ======================================================================
    # Phase 2 (2026-10-01): framing by scale (boxFill), metres per pixel, a
    # fixed-size offscreen render, the resolution check, and the BCF export
    # that phase 1 built without exercising.
    print("\n=== Phase 2: fill, metres per pixel, offscreen image, BCF ===")
    pg.evaluate(f"""() => {{
      window.__views = [];
      document.querySelector('{V}').addEventListener('view-applied', e => window.__views.push(e.detail.record));
    }}""")
    last_record = lambda: pg.evaluate("() => window.__views.at(-1)")

    st, msg = apply_json({"scope": {"kind": "intent", "intentId": rid}, "framing": {"mode": "fill", "fill": 0.6},
                          "direction": {"azimuthDeg": 45, "elevationDeg": 20}})
    rec = last_record() or {}
    bf = rec.get("resolved", {}).get("boxFill")
    check("perspective fill 0.6 lands within 2% (two measure-and-step rounds)", st == "done" and bf is not None and abs(bf - 0.6) < 0.012,
          f"boxFill {bf}; {msg}")
    st, msg = apply_json({"scope": {"kind": "intent", "intentId": rid}, "framing": {"mode": "fill", "fill": 0.6},
                          "lens": {"projection": "orthographic"}, "direction": {"azimuthDeg": 45, "elevationDeg": 20}})
    rec = last_record() or {}
    bf = rec.get("resolved", {}).get("boxFill")
    check("orthographic fill 0.6 is exact (linear in zoom)", st == "done" and bf is not None and abs(bf - 0.6) < 1e-6
          and rec["resolved"]["projection"] == "Orthographic", f"boxFill {bf}; {msg}")

    st, msg = apply_json({"scope": {"kind": "intent", "intentId": rid}, "lens": {"projection": "orthographic", "metresPerPixel": 0.05},
                          "direction": {"azimuthDeg": 0, "elevationDeg": 90}})
    rec = last_record() or {}
    r = rec.get("resolved", {})
    check("orthographic metres per pixel 0.05 is exact on the canvas", st == "done" and abs(r.get("metresPerPixel", 0) - 0.05) < 1e-9,
          f"mpp {r.get('metresPerPixel')}, canvas {r.get('canvas')}; {msg}")
    reso = r.get("resolution") or {}
    check("  and the resolution check says a 5 cm tolerance is 1 px there, below the 3 px floor",
          reso.get("toleranceM") == 0.05 and abs(reso.get("pixels", 0) - 1.0) < 1e-6 and reso.get("ok") is False, str(reso))
    st, msg = apply_json({"scope": {"kind": "intent", "intentId": rid}, "lens": {"projection": "orthographic", "metresPerPixel": 0.01},
                          "direction": {"azimuthDeg": 0, "elevationDeg": 90}})
    reso = (last_record() or {}).get("resolved", {}).get("resolution") or {}
    check("  at 1 cm/px the same tolerance is 5 px and passes", abs(reso.get("pixels", 0) - 5.0) < 1e-6 and reso.get("ok") is True, str(reso))
    st, msg = apply_json({"scope": {"kind": "building"}, "lens": {"projection": "perspective"}, "direction": {"azimuthDeg": 45, "elevationDeg": 45}})
    check("back to the perspective whole-building Side 45 at the baseline distance",
          st == "done" and abs(pose()["distance"] - keep["side45"]["distance"]) < 1e-6, f"{pose()['distance']:.6f}")

    # ---- offscreen render: equals the canvas at the canvas size, and sees past the live culling ----
    OFFSCREEN_JS = "async ([w, h, dpr, az, el]) => {" + MODS + """
      const render = await import(pick(/\\/views\\/render\\.js(\\?|$)/, '/views/render.js'));
      const snap = await import(pick(/\\/snapshot\\.js(\\?|$)/, '/snapshot.js'));
      const decode = async (url) => {
        const img = new Image(); img.src = url; await img.decode();
        const cnv = document.createElement('canvas'); cnv.width = img.width; cnv.height = img.height;
        const g = cnv.getContext('2d'); g.drawImage(img, 0, 0);
        return { data: g.getImageData(0, 0, cnv.width, cnv.height).data, w: cnv.width, h: cnv.height };
      };
      const coverage = (d, bg) => { let n = 0, tot = 0; for (let i = 0; i < d.data.length; i += 4 * 13) { tot++;
        if (Math.abs(d.data[i] - bg[0]) + Math.abs(d.data[i+1] - bg[1]) + Math.abs(d.data[i+2] - bg[2]) > 18) n++; } return n / tot; };
      const live = await decode(snap.captureWorldPng(world).dataUrl);
      const bg = [live.data[0], live.data[1], live.data[2]];
      // 1. same size, same pose: pixel-equal (sampled)
      const canvas = world.renderer.three.domElement;
      const pr = world.renderer.three.getPixelRatio();
      const same = await decode(render.frameToPngDataUrl(render.renderOffscreen(world, { width: canvas.width / pr, height: canvas.height / pr, pixelRatio: pr })));
      let equal = 0, total = 0, sum = 0, within48 = 0;
      for (let i = 0; i < live.data.length; i += 4 * 7) { total++;
        const dd = Math.max(Math.abs(live.data[i] - same.data[i]), Math.abs(live.data[i+1] - same.data[i+1]), Math.abs(live.data[i+2] - same.data[i+2]));
        if (dd === 0) equal++; if (dd <= 48) within48++; sum += dd; }
      // 2. a different size and a different pose: a whole-building Side 45 camera while the live camera is tight on an intent
      const box = cv.computeBuildingBoundingBox(components, v.classifier, model);
      const s = box.getBoundingSphere(new THREE.Sphere());
      const camLive = world.camera.three;
      const cam = camLive.clone();
      const a = az * Math.PI / 180, e = el * Math.PI / 180;
      const dir = new THREE.Vector3(Math.cos(e) * Math.sin(a), Math.sin(e), Math.cos(e) * Math.cos(a));
      const vfov = camLive.fov * Math.PI / 180, hfov = 2 * Math.atan(Math.tan(vfov / 2) * (w / h));
      const dist = s.radius / Math.sin((w / h > 1 ? vfov : hfov) / 2);
      cam.position.copy(s.center).addScaledVector(dir, dist); cam.lookAt(s.center); cam.aspect = w / h;
      cam.updateProjectionMatrix(); cam.updateMatrixWorld(true);
      let culled = 0; for (const g of v.fragments.groups.values()) for (const f of g.items) if (f.mesh && !f.mesh.visible) culled++;
      const far = await decode(render.frameToPngDataUrl(render.renderOffscreen(world, { width: w, height: h, pixelRatio: dpr, camera: cam })));
      let culledAfter = 0; for (const g of v.fragments.groups.values()) for (const f of g.items) if (f.mesh && !f.mesh.visible) culledAfter++;
      const sized = snap.captureViewerPng(world, { width: 320, height: 200 });
      const sizedImg = await decode(sized.dataUrl);
      return { sameW: same.w, sameH: same.h, liveW: live.w, liveH: live.h, equalFraction: equal / total, meanDiff: sum / total, within48: within48 / total,
               culled, culledAfter, farW: far.w, farH: far.h, farCoverage: coverage(far, bg), liveCoverage: coverage(live, bg),
               sizedW: sizedImg.w, sizedH: sizedImg.h, sizedCoverage: coverage(sizedImg, bg) };
    }"""
    # Coverage is compared at the live canvas's own size: a wider frame has
    # more empty background around the same building, so the two must share
    # an aspect to be comparable.
    canvas_css = pg.evaluate("async () => {" + MODS + "const el = world.renderer.three.domElement, pr = world.renderer.three.getPixelRatio(); return [el.width / pr, el.height / pr, pr]; }")
    side_cov = pg.evaluate(OFFSCREEN_JS, [*canvas_css, 45, 45])["liveCoverage"]  # the live canvas IS Side 45 right now, Refer active
    # Nothing transparent: clear the Refer phase 1 left active, then compare exactly.
    pg.click(f"{V} .intent-clear-btn")
    pg.wait_for_timeout(500)
    plain = pg.evaluate(OFFSCREEN_JS, [*canvas_css, 45, 45])
    check("with nothing transparent, offscreen at the canvas size and the live pose is pixel-equal to captureWorldPng (sRGB target, 4x MSAA)",
          plain["sameW"] == plain["liveW"] and plain["sameH"] == plain["liveH"] and plain["equalFraction"] > 0.995,
          f"{plain['sameW']}x{plain['sameH']} vs {plain['liveW']}x{plain['liveH']}, equal {plain['equalFraction']:.4f}, mean |d| {plain['meanDiff']:.3f}")
    # Refer again (the model ghosted to 90%) and go tight on the intent, so
    # the live frustum culls most of the building: the offscreen blend of
    # transparent geometry is in linear space, the canvas's in encoded space
    # (views/render.js) - a small, bounded difference, pinned here.
    pg.click(f'{V} [data-intent-id="{rid}"] .intent-refer-btn')
    pg.wait_for_selector(f'{V} [data-intent-id="{rid}"][data-refer-status="done"]', timeout=60000)
    st, msg = apply_json({"scope": {"kind": "intent", "intentId": rid}, "framing": {"context": 0.0},
                          "direction": {"azimuthDeg": 45, "elevationDeg": 20}})
    off = pg.evaluate(OFFSCREEN_JS, [*canvas_css, 45, 45])
    # Measured 2026-10-01: mean 4.5/255 at a whole-building view, 8.6/255
    # tight on the intent (more ghosted pixels in frame), every pixel within 48.
    check("with a Refer active (ghosted model) the offscreen render stays within a small bounded error of the canvas",
          off["meanDiff"] <= 12 and off["within48"] >= 0.99,
          f"mean |d| {off['meanDiff']:.3f}/255, {off['within48']*100:.2f}% of pixels within 48, {off['equalFraction']*100:.1f}% identical")
    check("the live frustum has culled fragments at the tight intent view", off["culled"] > 0, f"{off['culled']} meshes culled")
    check("an offscreen whole-building render at another pose shows the whole building regardless (forced visible, then restored)",
          off["farW"] == off["liveW"] and off["farH"] == off["liveH"] and off["culledAfter"] == off["culled"]
          and abs(off["farCoverage"] - side_cov) < max(0.02, side_cov * 0.1),
          f"coverage offscreen {off['farCoverage']:.3f} vs live Side 45 {side_cov:.3f}; culled {off['culled']} -> {off['culledAfter']}")
    check("captureViewerPng with a size renders 320x200 with content", off["sizedW"] == 320 and off["sizedH"] == 200 and off["sizedCoverage"] > 0.02,
          f"{off['sizedW']}x{off['sizedH']}, coverage {off['sizedCoverage']:.3f}")

    st, msg = apply_json({"scope": {"kind": "building"}, "direction": {"azimuthDeg": 45, "elevationDeg": 45}, "image": {"width": 640, "height": 480}})
    rec = last_record() or {}
    img = pg.evaluate("async () => {" + MODS + "const i = v.lastViewImage; if (!i) return null; const im = new Image(); im.src = i.dataUrl; await im.decode(); return { w: im.width, h: im.height, rw: i.width, rh: i.height }; }")
    check("a spec with image {640x480} records the size and leaves a decodable PNG of that size on the viewer entry",
          st == "done" and rec.get("image") == {"width": 640, "height": 480, "pixelRatio": 1} and img and img["w"] == 640 and img["h"] == 480,
          f"record.image {rec.get('image')}, png {img}")
    check("  and the record's metres per pixel then refers to the image height",
          abs(rec["resolved"]["metresPerPixel"] - 2 * rec["resolved"]["halfHeightM"] / 480) < 1e-9, f"{rec['resolved'].get('metresPerPixel')}")

    # ---- BCF export, with a Refer active ----
    pg.evaluate("""(id) => {
      const row = document.querySelector(`#viewerContainer1 [data-intent-id="${id}"]`);
      for (let el = row; el; el = el.parentElement) if (el.tagName === 'DETAILS') el.open = true;
    }""", rid)
    pg.click(f'{V} [data-intent-id="{rid}"] .intent-refer-btn')
    pg.wait_for_selector(f'{V} [data-intent-id="{rid}"][data-refer-status="done"]', timeout=60000)
    bcf = pg.evaluate("async () => {" + MODS + """
      const m = await import(pick(/\\/views\\/bcfExport\\.js(\\?|$)/, '/views/bcfExport.js'));
      const guids = v.cameraScope?.guids ?? [];
      const xml = await m.currentViewToBcfXml(components, world, { title: 'views harness', model, guids });
      return { xml, guids: guids.length, viewpointsLeft: components.list.size };
    }""")
    xml = bcf["xml"]
    check("BCF export yields a VisualizationInfo with a perspective camera",
          "<VisualizationInfo" in xml and "<PerspectiveCamera>" in xml and "<CameraViewPoint>" in xml, xml[:120].replace("\n", " "))
    sel = xml[xml.find("<Selection>"):xml.find("</Selection>")] if "<Selection>" in xml else ""
    check("  carrying one IfcGuid component per referred member in <Selection> (the Coloring block repeats them per colour)",
          bcf["guids"] == 4 and sel.count("IfcGuid=") == 4,
          f"{sel.count('IfcGuid=')} in Selection, {xml.count('IfcGuid=')} overall, for {bcf['guids']} guids; coloring: {'<Coloring>' in xml}, exceptions: {'<Exceptions>' in xml}")
    exc = xml[xml.find("<Exceptions>"):xml.find("</Exceptions>")] if "<Exceptions>" in xml else ""
    check("  and none of them is listed as an exception (hidden)", exc.count("IfcGuid=") == 0, f"{exc.count('IfcGuid=')} exceptions")

    # ---- The camera block, written by bcfExport.js itself since 2026-10-21 ----
    import xml.etree.ElementTree as ET, shutil, subprocess, tempfile
    SCHEMA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schemas", "visinfo.xsd")
    XMLLINT = shutil.which("xmllint")
    def validate(xml_text, what):
        if not XMLLINT:
            print(f"  [SKIP] xmllint not on PATH - {what} not validated against the BCF 3.0 schema")
            return
        with tempfile.NamedTemporaryFile("w", suffix=".bcfv", delete=False) as f:
            f.write(xml_text); path = f.name
        proc = subprocess.run([XMLLINT, "--noout", "--schema", SCHEMA, path], capture_output=True, text=True)
        os.unlink(path)
        check(f"{what} validates against BCF 3.0 visinfo.xsd", proc.returncode == 0, " | ".join(l.strip() for l in proc.stderr.strip().splitlines()[:2])[:300] if proc.returncode else "")
    def camera_of(xml_text):
        root = ET.fromstring(xml_text)
        cam = root.find("OrthogonalCamera")
        if cam is None: cam = root.find("PerspectiveCamera")
        vec = lambda tag: [float(cam.find(tag).find(a).text) for a in "XYZ"]
        return { "kind": cam.tag, "order": [c.tag for c in cam], "children": [c.tag for c in root],
                 "point": vec("CameraViewPoint"), "direction": vec("CameraDirection"), "up": vec("CameraUpVector"),
                 "scale": float(cam.findtext("ViewToWorldScale")) if cam.find("ViewToWorldScale") is not None else None,
                 "fov": float(cam.findtext("FieldOfView")) if cam.find("FieldOfView") is not None else None,
                 "aspect": float(cam.findtext("AspectRatio")) }
    EXPORT_JS = "async () => {" + MODS + """
      const m = await import(pick(/\\/views\\/bcfExport\\.js(\\?|$)/, '/views/bcfExport.js'));
      const guids = v.cameraScope?.guids ?? [];
      const xml = await m.currentViewToBcfXml(components, world, { title: 'views harness', model, guids });
      c.update(0); const cam = world.camera.three; cam.updateMatrixWorld(true);
      const p = c.getPosition(new THREE.Vector3());
      const o = world.camera.threeOrtho; const size = world.renderer.getSize();
      const col = (i) => { const v3 = new THREE.Vector3().setFromMatrixColumn(cam.matrixWorld, i); return [v3.x, v3.y, v3.z]; };
      const topics = components.get(OBC.BCFTopics); const versionBefore = topics.config.version;
      return { xml, position: [p.x, p.y, p.z], forward: col(2).map(x => -x), up: col(1), projection: world.camera.projection.current,
               zoom: o.zoom, frustumHeight: o.top - o.bottom, fov: world.camera.threePersp.fov, aspect: size.width / size.height,
               version: topics.config.version, versionBefore, viewpointsLeft: components.get(OBC.Viewpoints).list.size };
    }"""
    def dot(a, b): return sum(x * y for x, y in zip(a, b))
    def norm(a): return sum(x * x for x in a) ** 0.5
    def zup(v): return [v[0], -v[2], v[1]]
    def camera_checks(r, label):
        cam = camera_of(r["xml"])
        expect_kind = "OrthogonalCamera" if r["projection"] == "Orthographic" else "PerspectiveCamera"
        check(f"{label}: one {expect_kind} right after Components, in the 3.0 sequence with AspectRatio last",
              cam["kind"] == expect_kind and cam["children"][:2] == ["Components", expect_kind]
              and cam["order"] == ["CameraViewPoint", "CameraDirection", "CameraUpVector", "ViewToWorldScale" if expect_kind == "OrthogonalCamera" else "FieldOfView", "AspectRatio"],
              f"{cam['kind']} children {cam['children']} order {cam['order']}")
        check(f"  direction and up are the camera's own axes in IFC Z-up (x, -z, y), unit length and perpendicular",
              norm([a - b for a, b in zip(cam["direction"], zup(r["forward"]))]) < 1e-6 and norm([a - b for a, b in zip(cam["up"], zup(r["up"]))]) < 1e-6
              and abs(norm(cam["up"]) - 1) < 1e-6 and abs(dot(cam["direction"], cam["up"])) < 1e-6,
              f"dir {[round(x, 4) for x in cam['direction']]} up {[round(x, 4) for x in cam['up']]}")
        if MAPPING:
            x_off, z_off, sign, sense = MAPPING
            exp_x = r["position"][0] - x_off; exp_y = sign * (r["position"][2] - z_off)
            check("  CameraViewPoint is the scene position un-shifted by the loader's coordination (Phase 1's mapping) in plan",
                  abs(cam["point"][0] - exp_x) < 0.05 and abs(cam["point"][1] - exp_y) < 0.05,
                  f"got ({cam['point'][0]:.3f}, {cam['point'][1]:.3f}) expected ({exp_x:.3f}, {exp_y:.3f})")
        check("  AspectRatio is the canvas aspect", abs(cam["aspect"] - r["aspect"]) < 1e-9, f"{cam['aspect']:.6f} vs {r['aspect']:.6f}")
        if expect_kind == "OrthogonalCamera":
            check("  ViewToWorldScale is the visible vertical size in metres: (top - bottom) / zoom",
                  abs(cam["scale"] - r["frustumHeight"] / r["zoom"]) < 1e-9, f"{cam['scale']:.6f} vs {r['frustumHeight']:.3f} / {r['zoom']:.6f}")
        else:
            check("  FieldOfView is the vertical lens angle", abs(cam["fov"] - r["fov"]) < 1e-9, f"{cam['fov']} vs {r['fov']}")
        validate(r["xml"], label)
    r = pg.evaluate(EXPORT_JS)
    check("the manager's BCF version is restored after the export (set to 3 for the call only) and no viewpoint is left behind",
          r["version"] == r["versionBefore"] and r["viewpointsLeft"] == 0, f"version {r['version']!r} (before {r['versionBefore']!r}), {r['viewpointsLeft']} viewpoints left")
    camera_checks(r, "perspective export")
    before = pose()
    pg.evaluate("async () => {" + MODS + " await cv.toggleProjection(world); c.update(0); }")
    r = pg.evaluate(EXPORT_JS)
    check("switched to orthographic for the export", r["projection"] == "Orthographic", r["projection"])
    camera_checks(r, "orthographic export")
    pg.evaluate("async () => {" + MODS + " await cv.toggleProjection(world); c.update(0); }")
    after = pose()
    check("and back to perspective at the same pose (toggleProjection's lossless round trip)",
          after["projection"] == "Perspective" and max(abs(a - b) for a, b in zip(after["position"], before["position"])) < 1e-3
          and abs(after["distance"] - before["distance"]) < 1e-3, f"distance {before['distance']:.4f} -> {after['distance']:.4f}")

    # ======================================================================
    # Phase 3 (2026-10-01): cuts, scene settings, intent frames, per-type rules.
    print("\n=== Phase 3: cuts, scene, intent frames, rules ===")
    SCENE_JS = "async () => {" + MODS + """
      const planes = world.renderer.three.clippingPlanes.map(p => ({ normal: [p.normal.x, p.normal.y, p.normal.z], constant: p.constant }));
      const labels = world.scene.three.getObjectByName('bi2m-view-labels');
      const vs = v.viewScene;
      return { planes, labels: labels ? labels.children.length : 0,
               hiddenFragments: vs && vs.hiddenMap ? Object.keys(vs.hiddenMap).length : 0,
               cloneColors: vs && vs.cloneColors ? vs.cloneColors.length : 0,
               theme: document.documentElement.getAttribute('data-theme') };
    }"""
    coverage_js = "async () => {" + MODS + """
      const snap = await import(pick(/\\/snapshot\\.js(\\?|$)/, '/snapshot.js'));
      const img = new Image(); img.src = snap.captureWorldPng(world).dataUrl; await img.decode();
      const cnv = document.createElement('canvas'); cnv.width = img.width; cnv.height = img.height;
      const g = cnv.getContext('2d'); g.drawImage(img, 0, 0);
      const d = g.getImageData(0, 0, cnv.width, cnv.height).data; const bg = [d[0], d[1], d[2]];
      let n = 0, tot = 0; for (let i = 0; i < d.length; i += 4 * 13) { tot++;
        if (Math.abs(d[i] - bg[0]) + Math.abs(d[i+1] - bg[1]) + Math.abs(d[i+2] - bg[2]) > 18) n++; }
      return n / tot;
    }"""
    coverage = lambda: pg.evaluate(coverage_js)

    # ---- intent frames ----
    st, msg = apply_json({"scope": {"kind": "intent", "intentId": rid}, "frame": {"kind": "intent"}, "direction": {"azimuthDeg": 0, "elevationDeg": 5}})
    rec = last_record() or {}
    fr = rec.get("resolved", {}).get("frame", {})
    check("an intent frame for a column stack: origin at the stack (the phase-0 mapping), the building's yaw",
          st == "done" and fr.get("source") == "metrics.xy" and abs(fr.get("origin", [0])[0] - 9.913) < 0.05
          and abs(fr.get("origin", [0, 0, 0])[2] + 5.384) < 0.05 and fr.get("yawDeg") == 0,
          f"{fr}; {msg}")
    aid = ALIGN_X["id"]
    st, msg = apply_json({"scope": {"kind": "intent", "intentId": aid}, "frame": {"kind": "intent"}, "direction": {"azimuthDeg": 0, "elevationDeg": 5}})
    rec = last_record() or {}
    fr = rec.get("resolved", {}).get("frame", {})
    check("an intent frame for an 'axis X' alignment: along the line (yaw 0), origin on x = value + T.x",
          st == "done" and fr.get("source") == "metrics.axis" and fr.get("yawDeg") == 0 and abs(fr.get("origin", [0])[0] - 9.913) < 0.05,
          f"{fr}; {msg}")

    # ---- cuts ----
    st, msg = apply_json({"scope": {"kind": "building"}, "direction": {"azimuthDeg": 45, "elevationDeg": 45}})
    cov_uncut = coverage()
    storeys = pg.evaluate("async () => {" + MODS + "const cuts = await import(pick(/\\/views\\/cuts\\.js(\\?|$)/, '/views/cuts.js')); return cuts.storeyNames(v.classifier); }")
    check("the model offers storeys to cut at (ghost groups of earlier models excluded)", len(storeys) >= 2, " | ".join(storeys))
    lowest = storeys[0]
    st, msg = apply_json({"scope": {"kind": "building"}, "direction": {"azimuthDeg": 45, "elevationDeg": 45},
                          "cut": {"kind": "storeyPlan", "storey": lowest, "heightM": 1.2}})
    rec = last_record() or {}
    cut = rec.get("resolved", {}).get("cut") or {}
    sc = pg.evaluate(SCENE_JS)
    cov_cut = coverage()
    check(f"a storey-plan cut at '{lowest}' + 1.2 m: one plane, normal (0,-1,0), at floorY + 1.2",
          st == "done" and cut.get("kind") == "storeyPlan" and len(sc["planes"]) == 1 and sc["planes"][0]["normal"] == [0, -1, 0]
          and abs(cut.get("cutY", 0) - (cut.get("floorY", 0) + 1.2)) < 1e-9 and abs(sc["planes"][0]["constant"] - cut.get("cutY", 0)) < 1e-6,
          f"cut {cut}; planes {sc['planes']}; {msg}")
    check("  and the picture lost most of the building above the cut", cov_cut < cov_uncut * 0.75, f"coverage {cov_uncut:.3f} -> {cov_cut:.3f}")
    st, msg = apply_json({"scope": {"kind": "intent", "intentId": rid}, "framing": {"context": 0.5}, "direction": {"azimuthDeg": 45, "elevationDeg": 45},
                          "cut": {"kind": "sectionBox", "marginM": 0.5}})
    sc = pg.evaluate(SCENE_JS)
    cov_box = coverage()
    check("a section box around the intent: six planes, and far less of the building in frame",
          st == "done" and len(sc["planes"]) == 6 and cov_box < cov_uncut * 0.75, f"{len(sc['planes'])} planes, coverage {cov_box:.3f}; {msg}")
    st, msg = apply_json({"scope": {"kind": "building"}, "direction": {"azimuthDeg": 45, "elevationDeg": 45}})
    sc = pg.evaluate(SCENE_JS)
    check("a spec without a cut clears the planes (the spec is the whole view)", st == "done" and len(sc["planes"]) == 0, str(sc["planes"]))
    st, msg = apply_json({"cut": {"kind": "storeyPlan", "storey": "Nowhere 9", "heightM": 1.2}})
    check("an unknown storey is refused by name", st == "error" and "not in this model" in msg, f"{st}: {msg[:90]}")

    # ---- scene: hidden classes, colour modes, theme ----
    # Hiding is checked on the fragments themselves (visible instance counts),
    # not on pixels: with the model ghosted to 90% a plan's coverage barely
    # moves when slabs vanish.
    VISIBLE_JS = "async () => {" + MODS + """
      const names = ['IFCSLAB', 'IFCROOF'].filter(n => v.classifier.list.entities[n]);
      const map = v.classifier.find({ entities: names }) || {};
      let count = 0, frags = 0; for (const id of Object.keys(map)) { const f = v.fragments.list.get(id); if (f?.mesh) { frags++; count += f.mesh.count; } }
      return { frags, visibleInstances: count };
    }"""
    before = pg.evaluate(VISIBLE_JS)
    st, msg = apply_json({"scope": {"kind": "building"}, "direction": {"azimuthDeg": 0, "elevationDeg": 90},
                          "scene": {"hiddenClasses": ["IFCSLAB", "IFCROOF"]}})
    sc = pg.evaluate(SCENE_JS)
    hidden = pg.evaluate(VISIBLE_JS)
    st2, _ = apply_json({"scope": {"kind": "building"}, "direction": {"azimuthDeg": 0, "elevationDeg": 90}})
    restored = pg.evaluate(VISIBLE_JS)
    check("hiddenClasses [IFCSLAB, IFCROOF] hides their instances for the view and the next spec restores them exactly",
          st == "done" and sc["hiddenFragments"] > 0 and hidden["visibleInstances"] < before["visibleInstances"]
          and st2 == "done" and restored["visibleInstances"] == before["visibleInstances"],
          f"{before['frags']} slab/roof fragments: {before['visibleInstances']} visible instances -> {hidden['visibleInstances']} hidden -> {restored['visibleInstances']} restored")
    pg.evaluate("""(id) => {
      const row = document.querySelector(`#viewerContainer1 [data-intent-id="${id}"]`);
      for (let el = row; el; el = el.parentElement) if (el.tagName === 'DETAILS') el.open = true;
    }""", rid)
    pg.click(f'{V} [data-intent-id="{rid}"] .intent-refer-btn')
    pg.wait_for_selector(f'{V} [data-intent-id="{rid}"][data-refer-status="done"]', timeout=60000)
    st, msg = apply_json({"scope": {"kind": "intent", "intentId": rid}, "scene": {"colorMode": "single"}})
    sc = pg.evaluate(SCENE_JS)
    check("colorMode 'single' with a Refer active recolours the referred clones (and remembers their colours)",
          st == "done" and sc["cloneColors"] > 0, f"{sc['cloneColors']} clone fragment(s) recoloured; {msg}")
    st, msg = apply_json({"scope": {"kind": "intent", "intentId": rid}, "scene": {"colorMode": "numbered"}})
    sc = pg.evaluate(SCENE_JS)
    check("colorMode 'numbered' puts one label per member in the scene (4), and the single colour is gone",
          st == "done" and sc["labels"] == 4 and sc["cloneColors"] == 0, f"labels {sc['labels']}, cloneColors {sc['cloneColors']}; {msg}")
    theme_before = pg.evaluate("() => document.documentElement.getAttribute('data-theme')")
    st, msg = apply_json({"scope": {"kind": "intent", "intentId": rid}, "scene": {"theme": "dark"}})
    sc = pg.evaluate(SCENE_JS)
    st2, _ = apply_json({"scope": {"kind": "intent", "intentId": rid}})
    sc2 = pg.evaluate(SCENE_JS)
    check("theme 'dark' switches the page for the view; the next spec puts the previous theme back, and clears the labels",
          st == "done" and sc["theme"] == "dark" and st2 == "done" and sc2["theme"] == theme_before and sc2["labels"] == 0,
          f"before {theme_before!r} -> {sc['theme']!r} -> {sc2['theme']!r}; labels {sc2['labels']}")

    # ======================================================================
    # Phase 4 (2026-10-01): the visibility score - an ID pass per view.
    print("\n=== Phase 4: visibility score ===")
    SCORE_JS = "async ([guids]) => {" + MODS + """
      const vis = await import(pick(/\\/views\\/visibility\\.js(\\?|$)/, '/views/visibility.js'));
      const before = [];
      for (const s of v.referSplits ?? []) before.push(Array.from(s.referredFragment.mesh.instanceColor.array));
      const t0 = performance.now();
      const scores = await vis.measureVisibility(world, { guids });
      const ms = performance.now() - t0;
      const after = [];
      for (const s of v.referSplits ?? []) after.push(Array.from(s.referredFragment.mesh.instanceColor.array));
      const restored = JSON.stringify(before) === JSON.stringify(after);
      return { scores, ms, restored };
    }"""
    member_guids = [m["guid"] for m in COLSUPPORT["members"] if m.get("role") != "context"]
    # A Refer on the column stack is active from the colour-mode checks above.
    # First its own view from outside: once everything is opaque, interior columns
    # are behind walls and slabs - the score must say so, and still know how
    # big they would be unoccluded.
    st, msg = apply_json({"scope": {"kind": "intent", "intentId": rid}, "framing": {"context": 0.3}, "direction": {"azimuthDeg": 45, "elevationDeg": 20}})
    r1 = pg.evaluate(SCORE_JS, [member_guids])
    sc1 = r1["scores"]
    px1 = [(m["visiblePx"], m["unoccludedPx"]) for m in sc1["members"]]
    check("the ID pass locates all 4 members, and from outside with everything opaque they are (almost) fully occluded",
          sc1["membersLocated"] == 4 and all(u > 20 for _v, u in px1) and all(v <= 0.2 * u for v, u in px1),
          f"visible/unoccluded {px1} in {r1['ms']:.0f} ms")
    check("  no pixel carried an unknown id, and visible never exceeds unoccluded",
          sc1["unknownPx"] == 0 and all(v <= u for v, u in px1), f"other {sc1['otherPx']}, unknown {sc1['unknownPx']}")
    check("  and the clones' instance colours are byte-identical afterwards", r1["restored"])
    # A section box around the intent removes what hid them: visible rises to
    # unoccluded - the argument for cuts, measured.
    st, msg = apply_json({"scope": {"kind": "intent", "intentId": rid}, "framing": {"context": 0.3}, "direction": {"azimuthDeg": 45, "elevationDeg": 20},
                          "cut": {"kind": "sectionBox", "marginM": 0.5}})
    r2 = pg.evaluate(SCORE_JS, [member_guids])
    sc2 = r2["scores"]
    px2 = [(m["visiblePx"], m["unoccludedPx"]) for m in sc2["members"]]
    # The slabs passing through the stack stay inside the 0.5 m margin and
    # still hide the columns' feet and heads; measured 80-95 % visible.
    check("with a section box around the intent every member is seen, most of each (what the slabs inside the margin still hide excepted)",
          st == "done" and sc2["membersDistinct"] == 4 and all(v > 20 and v >= 0.6 * u for v, u in px2),
          f"visible/unoccluded {px2}, frameFill {sc2['frameFill']:.4f}")
    check("  frame fill is a sensible fraction", 0 < sc2["frameFill"] < 0.5, f"{sc2['frameFill']:.4f}")
    # A storey-plan cut at the lowest floor, seen from the side: the columns
    # above the cut are gone (0 visible AND 0 unoccluded: the cut removes
    # them), the base below it is still there.
    st, msg = apply_json({"scope": {"kind": "intent", "intentId": rid}, "framing": {"context": 0.3}, "direction": {"azimuthDeg": 45, "elevationDeg": 20},
                          "cut": {"kind": "storeyPlan", "storey": lowest, "heightM": 1.2}})
    r3 = pg.evaluate(SCORE_JS, [member_guids])
    px3 = [(m["visiblePx"], m["unoccludedPx"]) for m in r3["scores"]["members"]]
    check("with a storey-plan cut at the lowest floor, the members above the cut score 0 (visible and unoccluded) and the base does not",
          st == "done" and sum(1 for v, u in px3 if v == 0 and u == 0) >= 2 and any(u > 0 for _v, u in px3), f"visible/unoccluded {px3}")
    apply_json({"scope": {"kind": "intent", "intentId": rid}, "framing": {"context": 0.3}, "direction": {"azimuthDeg": 45, "elevationDeg": 20}})

    check("no console or page errors", not errs, "; ".join(errs[:3]))
    bad = [n for n, ok in res if not ok]
    print(f"\n{len(res)-len(bad)}/{len(res)} checks passed" + (f"\nFAILED: {bad}" if bad else ""))
    b.close()
    sys.exit(1 if bad else 0)

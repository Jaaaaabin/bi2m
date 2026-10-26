"""Refer-zoom regression check: does Refer zoom to an intent while leaving the
rest of the building visible?

Read-only: loads test_1 via /api/example-models, clicks Refer / Context /
view presets / Clear Selection only. Never Accept, Reject, Compute or Run, so
no verdict or intent state is persisted.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import BASE_URL, OUT
import re, sys, time
from PIL import Image, ImageChops, ImageDraw
from playwright.sync_api import sync_playwright

URL, V = BASE_URL, "#viewerContainer1"
# This harness is pinned to ONE intent in ONE model, and that is the point:
# every number below is a reference value measured on it, not a tolerance the
# current build gets to define. The fixture is `test_1.ifc`, content key
# da5e13147b9f8075.
#
# **Skipped since 2026-09-24**, when the owner reduced `data/` to a single
# `example_autcon.ifc` (content key 34b3f3dac339ade6) and this file left with
# the rest. It is deliberately NOT re-baselined against the surviving model:
# these four distances are what tell a regression from a redesign, and numbers
# recorded today from whatever the new fixture happens to do would enshrine
# the current behaviour instead of checking it - including any breakage.
# Restore `data/test_1.ifc` and this runs again unchanged.
MODEL = "test_1.ifc"
# 8-member "Vertical circulation: IfcStair run across 4 storeys" - the same
# intent whose scoped reference value below is 31.9 m for this file.
PID = "da5e13147b9f8075-circulation-3YkyhMiA95M9Su0XKJ5IuM-3aSQe5aG99cPcLWgYJ8Z$F-3aSQe5aG99cPcLWgYJ8Ze4-3aSQe5aG99cPcLWgYJ8Zel"
MEMBERS = 8
REF = {"whole": 94.6, "scoped": 31.9, "ctx0": 16.2, "ctx100": 94.6}  # verified reference values
BG_TOL = 6          # per-channel deviation still counted as background
results = []

def example_models():
    """What the dev server currently offers, so this harness can skip cleanly
    instead of timing out on a fixture that is no longer in data/."""
    import json, urllib.request
    try:
        with urllib.request.urlopen(f"{BASE_URL}/api/example-models", timeout=10) as r:
            return json.load(r).get("files", [])
    except Exception:
        return []


def check(name, ok, detail=""):
    results.append((name, ok, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" - {detail}" if detail else ""))
    return ok

def num(s):
    m = re.sub(r"[^0-9.\-]", "", s or "")
    return float(m) if m not in ("", "-", ".") else None

def readout(pg):
    return (num(pg.input_value(f"{V} .viewer-camera-distance-value")),
            num(pg.input_value(f"{V} .viewer-camera-angle-value")))

# --- live camera/scope state, read from the app's own module instance ---
# Under vite dev a dynamic import of the same URL returns the module the app
# is already using, so this is the real viewerData - no debug global needed.
STATE_JS = """async () => {
  const __u = performance.getEntriesByType('resource').map(e => e.name)
    .filter(n => /\\/viewerRegistry\\.js(\\?|$)/.test(n)).pop() || '/viewerRegistry.js';
  const {viewerData} = await import(__u);
  const e = viewerData[0];
  const cam = e.world.camera.three;
  const V3 = cam.position.constructor;
  cam.updateMatrixWorld();
  const proj = (box) => {
    if (!box) return null;
    const pts = [];
    for (const x of [box.min.x, box.max.x])
      for (const y of [box.min.y, box.max.y])
        for (const z of [box.min.z, box.max.z]) {
          const v = new V3(x, y, z).project(cam);
          pts.push([v.x, v.y, v.z]);
        }
    const xs = pts.map(p => p[0]), ys = pts.map(p => p[1]);
    const inFrustum = pts.filter(p =>
      Math.abs(p[0]) <= 1.001 && Math.abs(p[1]) <= 1.001 && p[2] >= -1.001 && p[2] <= 1.001).length;
    const size = box.getSize(new V3());
    return {minX: Math.min(...xs), maxX: Math.max(...xs),
            minY: Math.min(...ys), maxY: Math.max(...ys),
            inFrustum, diagonal: size.length()};
  };
  const sc = e.cameraScope;
  const pos = e.world.camera.controls.getPosition(new V3());
  const tgt = e.world.camera.controls.getTarget(new V3());
  const rect = e.container.querySelector('.viewer-canvas-area').getBoundingClientRect();
  return {
    hasScope: !!sc, guids: sc?.guids?.length ?? null,
    scope: proj(sc?.box), building: proj(sc?.buildingBox),
    pos: [pos.x, pos.y, pos.z], tgt: [tgt.x, tgt.y, tgt.z],
    distance: e.world.camera.controls.distance,
    minDistance: e.world.camera.controls.minDistance,
    maxDistance: e.world.camera.controls.maxDistance,
    canvas: {x: rect.x, y: rect.y, w: rect.width, h: rect.height},
    projection: cam.type,
  };
}"""

# Rects of everything painted OVER the canvas; filled with the background
# colour before counting so panel chrome is never mistaken for geometry.
OVERLAY_JS = """() => {
  const sel = '#sidebar-panel, .viewer-filter-panel, .viewer-intent-panel, .viewer-camera-panel, .ifc-name-label, .viewer-loading, .viewer-error, .viewer-resize-handle, .viewer-canvas-area button, .viewer-settings-btn, .viewer-intent-toggle-btn, .viewer-shortcuts-toggle-btn';  // tile-level buttons since 2026-09-23
  return [...document.querySelectorAll(sel)]
    .filter(el => getComputedStyle(el).display !== 'none' && getComputedStyle(el).visibility !== 'hidden')
    .map(el => { const r = el.getBoundingClientRect();
                 return {x: r.x, y: r.y, w: r.width, h: r.height}; })
    .filter(r => r.w > 0 && r.h > 0);
}"""

def shoot(pg, path):
    """Capture now; measure later - see load_frame()."""
    pg.screenshot(path=path)
    return path

def load_frame(path, state, overlays, bg=None):
    """Crop to the canvas and blank overlay chrome with the background colour.

    The mask must be IDENTICAL for every frame being compared. It is captured
    once, after a Refer, because the camera panel grows taller then (the
    Context block appears) - measuring the baseline under the shorter mask and
    a later frame under the taller one silently hides geometry in the
    difference and reads as "the building shrank".
    """
    img = Image.open(path).convert("RGB")
    c = state["canvas"]
    img = img.crop((int(c["x"]), int(c["y"]), int(c["x"] + c["w"]), int(c["y"] + c["h"])))
    # background sampled from the live render, not from the CSS token: three.js
    # colour management shifts the value by a few levels.
    if bg is None:
        bg = img.getpixel((2, 2))
    d = ImageDraw.Draw(img)
    for r in overlays:
        d.rectangle([r["x"] - c["x"], r["y"] - c["y"],
                     r["x"] - c["x"] + r["w"], r["y"] - c["y"] + r["h"]], fill=bg)
    return img, bg

def deviation(img, bg):
    """Grayscale |img - bg|: 0 = background, small = ghosted, large = opaque."""
    return ImageChops.difference(img, Image.new("RGB", img.size, bg)).convert("L")

def stats(dev, exclude=None):
    """Pixels deviating from background, optionally outside a screen rect."""
    if exclude:
        dev = dev.copy()
        ImageDraw.Draw(dev).rectangle(exclude, fill=0)
    h = dev.histogram()
    n = sum(h[BG_TOL + 1:])
    mean = sum(i * h[i] for i in range(BG_TOL + 1, 256)) / n if n else 0.0
    return {"count": n, "total": sum(h), "frac": n / sum(h), "mean": mean}

def ndc_rect(p, w, h, pad=0):
    """Projected NDC bbox -> pixel rect in the cropped canvas image."""
    x0 = (p["minX"] * 0.5 + 0.5) * w; x1 = (p["maxX"] * 0.5 + 0.5) * w
    y0 = (1 - (p["maxY"] * 0.5 + 0.5)) * h; y1 = (1 - (p["minY"] * 0.5 + 0.5)) * h
    return [max(0, x0 - pad), max(0, y0 - pad), min(w, x1 + pad), min(h, y1 + pad)]

with sync_playwright() as p:
    b = p.chromium.launch(args=["--use-gl=swiftshader", "--enable-unsafe-swiftshader"])
    pg = b.new_page(viewport={"width": 1400, "height": 900})
    errors = []
    pg.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
    pg.on("console", lambda m: m.type == "error" and errors.append(f"console: {m.text}"))

    if not any(f.get("fileName") == MODEL for f in example_models()):
        print(f"  [SKIP] refer-zoom reference values - {MODEL} is not in data/"
              f" (see this file's header: deliberately not re-baselined)")
        b.close()
        sys.exit(0)
    print(f"=== load {MODEL} ===")
    t0 = time.time()
    pg.goto(URL, wait_until="networkidle")
    pg.click("#example-models-btn")
    pg.wait_for_selector(f'.example-models-item[data-file-name="{MODEL}"]', timeout=20000)
    pg.click(f'.example-models-item[data-file-name="{MODEL}"]')
    pg.wait_for_selector(f"{V} .intent-row", timeout=180000, state="attached")
    pg.wait_for_load_state("networkidle")
    # Panels are opened ONCE, before the baseline, and never toggled again -
    # they change the scoped framing, so every frame below is
    # taken under identical panel state.
    (pg.locator("#viewerContainer1").evaluate("el => el.classList.contains('intent-open')") or pg.click(f"{V} .viewer-intent-toggle-btn")); pg.wait_for_timeout(250)
    (pg.locator("#viewerContainer1").evaluate("el => el.classList.contains('camera-open')") or pg.click(f"{V} .viewer-camera-toggle-btn")); pg.wait_for_timeout(300)

    # Fragments keep streaming after .intent-row exists, so wait for the
    # framing itself to stop moving rather than trusting the row selector.
    prev, stable = None, 0
    for _ in range(60):
        d, _a = readout(pg)
        stable = stable + 1 if (d is not None and prev is not None and abs(d - prev) < 0.05) else 0
        prev = d
        if stable >= 3: break
        pg.wait_for_timeout(500)
    d_whole, a_whole = readout(pg)
    print(f"  loaded+settled in {time.time()-t0:.1f}s   whole model: {d_whole} m, elevation {a_whole}")

    st_whole = pg.evaluate(STATE_JS)
    shoot(pg, f"{OUT}/01_whole_model.png")   # measured below, once the mask is fixed

    print("\n=== baseline matches the 'Camera System' reference values ===")
    check("whole-model framing == 94.6 m", abs(d_whole - REF["whole"]) / REF["whole"] < 0.05,
          f"got {d_whole} m")

    print("\n=== Refer the 8-member circulation intent ===")
    row = pg.locator(f'{V} .intent-row[data-intent-id="{PID}"]')
    row.evaluate("el => { const s = el.closest('.intent-category-section'); if (s) s.open = true; }")
    row.locator(".intent-refer-btn").click()
    pg.wait_for_selector(f'{V} .intent-row[data-intent-id="{PID}"][data-refer-status="done"]',
                         timeout=90000, state="attached")
    pg.wait_for_timeout(500)
    d_ref, a_ref = readout(pg)
    st = pg.evaluate(STATE_JS)

    check("Refer zoomed the camera in", d_ref < d_whole, f"{d_whole} m -> {d_ref} m")
    check("scoped framing == 31.9 m", abs(d_ref - REF["scoped"]) / REF["scoped"] < 0.05, f"got {d_ref} m")
    check("orbit direction preserved", abs(a_ref - a_whole) < 0.6,
          f"elevation {a_whole} -> {a_ref}")
    # The elevation readout alone doesn't cover azimuth; compare the actual
    # eye->target unit vectors, which fitToSphere should leave untouched.
    def dirvec(s):
        d = [a - b for a, b in zip(s["pos"], s["tgt"])]
        n = sum(x * x for x in d) ** 0.5
        return [x / n for x in d]
    dot = sum(a * b for a, b in zip(dirvec(st_whole), dirvec(st)))
    check("view direction preserved (azimuth AND elevation)", dot > 0.9999, f"cos={dot:.6f}")
    # computeGuidsBoundingBox returns null when no GUID resolves, and the
    # handler then silently skips both the zoom and setCameraScope.
    check("camera scope was actually set", st["hasScope"] and st["guids"] == MEMBERS,
          f"hasScope={st['hasScope']} guids={st['guids']}")
    # The Context slider left the camera panel on 2026-10-01 (owner decision);
    # context is a view-spec parameter now, swept below through applyView.
    print(f"  camera pos {[round(v,2) for v in st['pos']]} -> target {[round(v,2) for v in st['tgt']]}")
    print(f"  dolly clamps: minDistance={st['minDistance']:.3f} maxDistance={st['maxDistance']:.1f}")

    print("\n=== geometry: intent framed, building overflows the frame ===")
    sp, bd = st["scope"], st["building"]
    check("all 8 intent-box corners inside the frustum", sp["inFrustum"] == 8,
          f"{sp['inFrustum']}/8")
    area = ((sp["maxX"] - sp["minX"]) / 2) * ((sp["maxY"] - sp["minY"]) / 2)
    check("intent does not fill the viewport", area < 0.5,
          f"intent occupies {area*100:.1f}% of frame area")
    # Corner containment, not the NDC min/max: once the camera sits close to
    # (or inside) the building's extent, corners behind the near plane project
    # to mirrored garbage, so the bbox range is informational only.
    check("building overflows the frame (still zoomed in)", bd["inFrustum"] < 8,
          f"{bd['inFrustum']}/8 building corners in frustum; NDC range "
          f"x[{bd['minX']:.2f},{bd['maxX']:.2f}] y[{bd['minY']:.2f},{bd['maxY']:.2f}] (unreliable when < -1)")

    print("\n=== pixels: is the rest of the building actually still rendered? ===")
    shoot(pg, f"{OUT}/02_referred_ctx20.png")
    # Captured now, with the Context block showing, and reused for every frame.
    overlays = pg.evaluate(OVERLAY_JS)
    img_whole, bg = load_frame(f"{OUT}/01_whole_model.png", st_whole, overlays)
    s_whole = stats(deviation(img_whole, bg))
    W, H = img_whole.size
    print(f"  canvas {W}x{H}  bg={bg}  opaque baseline covers {s_whole['frac']*100:.1f}% of canvas, "
          f"mean deviation {s_whole['mean']:.1f}")
    img_ref, _ = load_frame(f"{OUT}/02_referred_ctx20.png", st, overlays, bg)
    dev_ref = deviation(img_ref, bg)
    rect = ndc_rect(sp, W, H, pad=8)
    s_all = stats(dev_ref)
    s_out = stats(dev_ref, exclude=rect)     # everything except the intent
    s_in = stats(dev_ref.crop([int(v) for v in rect]))
    print(f"  intent screen rect {[round(v) for v in rect]}")
    print(f"  rendered geometry: {s_all['frac']*100:.1f}% of canvas "
          f"({s_out['frac']*100:.1f}% outside the intent rect)")
    print(f"  mean deviation inside intent rect {s_in['mean']:.1f} vs outside {s_out['mean']:.1f} "
          f"(all-opaque baseline {s_whole['mean']:.1f})")
    check("building still rendered around the intent",
          s_out["frac"] > 0.05, f"{s_out['frac']*100:.1f}% of canvas outside the intent rect")
    check("that surrounding geometry is ghosted, not opaque",
          s_out["mean"] < s_whole["mean"], f"{s_out['mean']:.1f} < {s_whole['mean']:.1f}")

    print("\n=== Context slider sweep ===")
    dists, mono = [], True
    APPLY_CTX = """async (ctx) => {
      const pick = (re, fb) => performance.getEntriesByType('resource').map(e => e.name).filter(n => re.test(n)).pop() || fb;
      const { viewerData } = await import(pick(/\\/viewerRegistry\\.js(\\?|$)/, '/viewerRegistry.js'));
      const { applyView } = await import(pick(/\\/views\\/applyView\\.js(\\?|$)/, '/views/applyView.js'));
      await applyView(viewerData[0].world, { framing: { context: ctx } }, { chosenBy: 'manual' });
    }"""
    for pct in (0, 20, 50, 80, 100):
        pg.evaluate(APPLY_CTX, pct / 100); pg.wait_for_timeout(400)
        d, _a = readout(pg)
        if dists and d <= dists[-1][1]: mono = False
        dists.append((pct, d))
        print(f"    context={pct:>3}%  distance={d} m")
    check("context is strictly monotonic", mono, " -> ".join(f"{d}" for _p, d in dists))
    check("context 0% == 16.2 m", abs(dists[0][1] - REF["ctx0"]) / REF["ctx0"] < 0.05, f"got {dists[0][1]} m")
    check("context 100% == whole-model framing",
          abs(dists[-1][1] - d_whole) / d_whole < 0.05, f"{dists[-1][1]} m vs {d_whole} m")
    st100 = pg.evaluate(STATE_JS)
    b100 = st100["building"]
    check("at context 100% the whole building is back inside the frame",
          b100["inFrustum"] == 8, f"{b100['inFrustum']}/8 corners in frustum")

    # Controlled comparison: at context 100% the camera is back at the exact
    # baseline framing (same distance, same direction, same centre), so the
    # ONLY difference from the pre-Refer frame is the 90% ghosting plus the
    # opaque stair. Comparing against the 94.6 m baseline here isolates
    # transparency; comparing the 31.9 m frame against it would have
    # confounded ghosting with zoom.
    img100, _ = load_frame(shoot(pg, f"{OUT}/03_context_100.png"), st100, overlays, bg)
    s100 = stats(deviation(img100, bg))
    print(f"  same framing as baseline: coverage {s100['frac']*100:.1f}% vs {s_whole['frac']*100:.1f}%, "
          f"mean deviation {s100['mean']:.1f} vs {s_whole['mean']:.1f}")
    check("ghosted frame covers the same area as the opaque baseline",
          abs(s100["frac"] - s_whole["frac"]) < 0.04,
          f"{s100['frac']*100:.1f}% vs {s_whole['frac']*100:.1f}%")
    check("...but renders far fainter (transparency isolated from zoom)",
          s100["mean"] < 0.6 * s_whole["mean"], f"{s100['mean']:.1f} vs {s_whole['mean']:.1f}")

    # back to the default before the preset check
    pg.evaluate(APPLY_CTX, 0.2); pg.wait_for_timeout(400)
    d_scoped, _ = readout(pg)

    print("\n=== view presets stay scoped ===")
    pg.click(f"{V} .viewer-side-view-btn"); pg.wait_for_timeout(400)
    d_side, a_side = readout(pg)
    check("Side View keeps the intent framed, not the building",
          abs(d_side - d_scoped) / d_scoped < 0.05, f"{d_scoped} m -> {d_side} m (elevation {a_side})")
    pg.screenshot(path=f"{OUT}/04_side_view_scoped.png")

    print("\n=== Clear Selection restores the whole-building view ===")
    pg.click(f"{V} .intent-clear-btn"); pg.wait_for_timeout(500)
    check("global transparency back to 0%",
          pg.inner_text("#transparency-value").strip() == "0%",
          pg.inner_text("#transparency-value").strip())
    st_clear = pg.evaluate(STATE_JS)
    check("camera scope cleared", not st_clear["hasScope"])
    pg.click(f"{V} .viewer-side-view-btn"); pg.wait_for_timeout(400)
    d_back, _ = readout(pg)
    check("presets frame the whole building again",
          abs(d_back - d_whole) / d_whole < 0.05, f"got {d_back} m vs {d_whole} m")
    pg.screenshot(path=f"{OUT}/05_cleared.png")

    check("no console or page errors", not errors, "; ".join(errors[:3]) if errors else "")

    failed = [n for n, ok, _ in results if not ok]
    print(f"\n{'='*64}\n{len(results)-len(failed)}/{len(results)} checks passed")
    if failed:
        print("FAILED: " + ", ".join(failed))
    b.close()
    sys.exit(1 if failed else 0)

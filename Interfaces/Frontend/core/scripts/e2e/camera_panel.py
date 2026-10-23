import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import BASE_URL, OUT
import re
from PIL import Image
from playwright.sync_api import sync_playwright

URL, V = BASE_URL, "#viewerContainer1"
OLD_MAX = 420.0          # previous max-width, the width actually rendered before
EXPECT = [("Front", [0, 0, 1]), ("Back", [0, 0, -1]),
          ("Left", [-1, 0, 0]), ("Right", [1, 0, 0])]  # short labels since 2026-09-23 (were "Front View" etc.)
res = []
def check(n, ok, d=""):
    res.append((n, ok)); print(f"  [{'PASS' if ok else 'FAIL'}] {n}" + (f" - {d}" if d else ""))

DIR_JS = """async () => {
  const __u = performance.getEntriesByType('resource').map(e => e.name)
    .filter(n => /\\/viewerRegistry\\.js(\\?|$)/.test(n)).pop() || '/viewerRegistry.js';
  const {viewerData} = await import(__u);
  const c = viewerData[0].world.camera.controls;
  const V3 = viewerData[0].world.camera.three.position.constructor;
  const p = c.getPosition(new V3()), t = c.getTarget(new V3());
  const d = [p.x-t.x, p.y-t.y, p.z-t.z];
  const n = Math.hypot(...d);
  return d.map(v => v/n);
}"""

# Distinct-colour count of the live canvas, read two ways: once straight off
# the element (the cleared buffer) and once through snapshot.js's own
# capture. Resolved from performance entries so it hits the same module
# instance Vite already served the page, like DIR_JS above.
SNAPSHOT_JS = """async (v) => {
  const pick = (re, fallback) => performance.getEntriesByType('resource').map(e => e.name)
    .filter(n => re.test(n)).pop() || fallback;
  const { captureWorldPng } = await import(pick(/\\/snapshot\\.js(\\?|$)/, '/snapshot.js'));
  const { viewerData } = await import(pick(/\\/viewerRegistry\\.js(\\?|$)/, '/viewerRegistry.js'));
  const world = viewerData[0].world;
  const canvas = world.renderer.three.domElement;
  const count = async (url) => {
    const img = new Image(); img.src = url; await img.decode();
    const c = document.createElement('canvas');
    c.width = img.width; c.height = img.height;
    const g = c.getContext('2d'); g.drawImage(img, 0, 0);
    const d = g.getImageData(0, 0, c.width, c.height).data;
    const seen = new Set();
    for (let i = 0; i < d.length; i += 4 * 97) seen.add(`${d[i]},${d[i+1]},${d[i+2]},${d[i+3]}`);
    return seen.size;
  };
  const stale = await count(canvas.toDataURL('image/png'));  // no re-render: the cleared buffer
  const live = captureWorldPng(world);                       // render + read, one synchronous block
  return { stale, fresh: await count(live.dataUrl), w: live.width, h: live.height,
           canvasW: canvas.width, canvasH: canvas.height,
           preserve: !!world.renderer.three.getContext().getContextAttributes().preserveDrawingBuffer };
}"""

with sync_playwright() as p:
    b = p.chromium.launch(args=["--use-gl=swiftshader", "--enable-unsafe-swiftshader"])
    pg = b.new_page(viewport={"width": 1400, "height": 900})
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.on("console", lambda m: m.type == "error" and errs.append(m.text))
    pg.goto(URL, wait_until="networkidle")
    pg.click("#example-models-btn")
    pg.wait_for_selector('.example-models-item[data-file-name="example_autcon.ifc"]', timeout=20000)
    pg.click('.example-models-item[data-file-name="example_autcon.ifc"]')
    pg.wait_for_selector(f"{V} .intent-row", timeout=180000, state="attached")
    pg.wait_for_load_state("networkidle")
    (pg.locator("#viewerContainer1").evaluate("el => el.classList.contains('camera-open')") or pg.click(f"{V} .viewer-camera-toggle-btn"))
    pg.wait_for_timeout(600)

    # ---- the pose a model OPENS on (2026-09-24) ----
    # 45 degrees, perspective. Pinned here because it is a default rather than
    # a button: nothing else in the suite would notice it drifting. Measured
    # across six library models before the change - coverage moves only from
    # 21.9% to 26.0% between a 30-degree view and straight down, so the angle
    # is a readability choice, not a framing one (cameraViews.js).
    open_elev = float(pg.input_value(f"{V} .viewer-camera-angle-value"))
    check("a model opens at 20 degrees above horizontal", abs(open_elev - 20.0) < 1.0,
          f"{open_elev}\u00b0")
    fov = pg.evaluate(f"""async () => {{
      const pick=(re,f)=>performance.getEntriesByType('resource').map(e=>e.name).filter(n=>re.test(n)).pop()||f;
      const {{viewerData}}=await import(pick(/\\/viewerRegistry\\.js(\\?|$)/,'/viewerRegistry.js'));
      return viewerData[0].world.camera.threePersp.fov;
    }}""")
    check("through a 38-degree lens, not the library's inherited 60", abs(fov - 38) < 0.01, f"fov {fov}")
    check("and in perspective, not orthographic",
          pg.inner_text(f"{V} .viewer-projection-toggle-btn").strip() == "Ortho",
          "the toggle offers Ortho, so the camera is perspective")

    print("=== panel width ===")
    box = pg.locator(f"{V} .viewer-camera-panel").bounding_box()
    pct = box["width"] / OLD_MAX * 100
    print(f"  {box['width']:.0f}px wide (was {OLD_MAX:.0f}px) = {pct:.0f}% of previous")
    check("narrowed to ~60% of previous width", 55 <= pct <= 65, f"{pct:.0f}%")

    # nothing may spill outside the panel now that it is narrower
    over = pg.evaluate("""(v) => {
      const p = document.querySelector(v + ' .viewer-camera-panel');
      const pr = p.getBoundingClientRect();
      return [...p.querySelectorAll('button, input, .viewer-camera-readout-row')]
        .filter(el => { const r = el.getBoundingClientRect();
                        return r.width > 0 && (r.right > pr.right + 1 || r.left < pr.left - 1); })
        .map(el => (el.textContent || el.placeholder || '').trim().slice(0, 30));
    }""", V)
    check("no control overflows the narrower panel", not over, ", ".join(over) if over else "")

    print("\n=== elevation switcher ===")
    btns = pg.locator(f"{V} .viewer-camera-actions button")
    labels = [btns.nth(i).inner_text().strip() for i in range(btns.count())]
    check("camera actions reduced to 4 buttons", btns.count() == 4, " | ".join(labels))
    sw = pg.locator(f"{V} .viewer-elevation-view-btn")
    check("switcher starts on 'Front'", sw.inner_text().strip() == "Front", sw.inner_text().strip())

    for i, (clicked, want) in enumerate(EXPECT):
        shown = sw.inner_text().strip()
        check(f"click {i+1} offers '{clicked}'", shown == clicked, f"shows '{shown}'")
        sw.click(); pg.wait_for_timeout(700)
        got = pg.evaluate(DIR_JS)
        dot = sum(a * b for a, b in zip(got, want))
        nxt = EXPECT[(i + 1) % len(EXPECT)][0]
        elev = pg.input_value(f"{V} .viewer-camera-angle-value") + "°"
        check(f"  -> applied {clicked} (elevation {elev})", dot > 0.999,
              f"direction {[round(v,3) for v in got]} vs {want}")
        check(f"  -> label advanced to '{nxt}'", sw.inner_text().strip() == nxt, sw.inner_text().strip())

    check("wraps back to the start", sw.inner_text().strip() == "Front")

    # ---- projection round trip (2026-09-24) ----
    # Toggling out to orthographic and back must land exactly where it
    # started, and a zoom done IN orthographic must survive the way back.
    # Neither held before: the two projections frame by different variables
    # (perspective by controls.distance, orthographic by threeOrtho.zoom,
    # with controls.distance pinned to a hardcoded 200), and the library
    # reconciled them either not at all or with `atan` where the trigonometry
    # wants `tan`. cameraViews.js toggleProjection() carries the visible
    # half-height across instead.
    cam_state = """async () => {
      const pick=(re,f)=>performance.getEntriesByType('resource').map(e=>e.name).filter(n=>re.test(n)).pop()||f;
      const {viewerData}=await import(pick(/\\/viewerRegistry\\.js(\\?|$)/,'/viewerRegistry.js'));
      const c=viewerData[0].world.camera, ct=c.controls;
      const V3=c.three.position.constructor; const p=ct.getPosition(new V3());
      return {dist:+ct.distance.toFixed(3), zoom:+c.threeOrtho.zoom.toFixed(3),
              pos:[p.x,p.y,p.z].map(n=>+n.toFixed(2))};
    }"""
    proj_btn = f"{V} .viewer-projection-toggle-btn"
    start = pg.evaluate(cam_state)
    for _ in range(2):
        pg.click(proj_btn); pg.wait_for_timeout(1100)
    back = pg.evaluate(cam_state)
    check("a projection round trip lands exactly where it started",
          abs(back["dist"] - start["dist"]) < 0.01 and back["pos"] == start["pos"],
          f"{start['dist']} -> {back['dist']}")
    pg.click(proj_btn); pg.wait_for_timeout(1000)          # into orthographic
    pg.mouse.move(700, 450)
    for _ in range(4):
        pg.mouse.wheel(0, -240); pg.wait_for_timeout(250)
    pg.wait_for_timeout(700)
    zoomed = pg.evaluate(cam_state)
    pg.click(proj_btn); pg.wait_for_timeout(1200)          # back to perspective
    after = pg.evaluate(cam_state)
    check("a zoom made in orthographic survives the switch back",
          zoomed["zoom"] > 2 and after["dist"] < start["dist"] * 0.6,
          f"zoom {zoomed['zoom']}x -> distance {start['dist']} to {after['dist']}")
    # leave the camera as the rest of this harness expects
    pg.click(f"{V} .viewer-fit-max-btn"); pg.wait_for_timeout(600)
    pg.click(f"{V} .viewer-side-view-btn"); pg.wait_for_timeout(600)

    print("\n=== layout (2026-09-23): five rows, the toggle button in the bottom row ===")
    bb = lambda loc: loc.bounding_box()

    # The filter panel's width is ANIMATED (transition: width), so every
    # geometry read across a filters-open toggle has to wait for the width to
    # stop moving, not for a fixed number of milliseconds. A 400ms sleep read
    # a shift of exactly 0px once under a full-suite run on 2026-09-24. Two
    # things produce exactly 0px - a transition that had not advanced yet on a
    # busy machine, or a click that never registered - and the sleep could not
    # tell them apart. The wait_for_function on `filters-open` below now does:
    # it fails loudly on the second, and this settles the first.
    def settle(sel, tries=40):
        last = None
        for _ in range(tries):
            now = pg.evaluate(f"() => document.querySelector('{sel} .viewer-canvas-area').getBoundingClientRect().width")
            if last is not None and abs(now - last) < 0.5:
                return now
            last = now
            pg.wait_for_timeout(50)
        return last

    # Opening/closing the camera panel is a class toggle with no transition on
    # geometry, but assert the class rather than assume the click landed.
    def toggle_camera(want_open):
        pg.click(f"{V} .viewer-camera-toggle-btn")
        pg.wait_for_function(
            f"() => document.querySelector('{V}').classList.contains('camera-open') === {str(want_open).lower()}",
            timeout=10000)
    rows = pg.locator(f"{V} .viewer-camera-actions")
    check("presets and switchers sit in two rows of two", rows.count() == 2
          and rows.nth(0).locator("button").count() == 2 and rows.nth(1).locator("button").count() == 2,
          " | ".join(rows.nth(i).inner_text().strip().replace("\n", " / ") for i in range(rows.count())))
    a1 = bb(rows.nth(1))
    ang, dist = bb(pg.locator(f"{V} .viewer-camera-angle-value")), bb(pg.locator(f"{V} .viewer-camera-distance-value"))
    check("elevation and distance share one line below the switchers",
          abs(ang["y"] - dist["y"]) < 2 and ang["y"] > a1["y"] + a1["height"] - 1, f"elevation y={ang['y']:.0f} distance y={dist['y']:.0f}")
    az = bb(pg.locator(f"{V} .viewer-camera-azimuth-value"))
    check("azimuth sits between elevation and distance on that line (owner's 2026-10-01 layout)",
          ang["x"] < az["x"] < dist["x"] and abs(az["y"] - ang["y"]) < 2, f"x: {ang['x']:.0f} < {az['x']:.0f} < {dist['x']:.0f}")
    check("all three readouts are number inputs with spinners (click to step)",
          pg.evaluate(f"() => ['angle', 'azimuth', 'distance'].every(k => document.querySelector('{V} .viewer-camera-' + k + '-value')?.type === 'number')"))
    check("the Context slider is gone from the panel (owner decision 2026-10-01; context stays a spec parameter)",
          pg.locator(f"{V} .viewer-camera-context-slider").count() == 0 and pg.locator(f"{V} .viewer-camera-scope").count() == 0)
    save = pg.locator(f"{V} .viewer-save-view-btn")
    check("Save is an icon button (archive glyph) with an accessible name",
          save.locator("use[href='#icon-archive']").count() == 1 and save.get_attribute("aria-label") == "Save" and not save.inner_text().strip())
    name, sv = bb(pg.locator(f"{V} .viewer-view-name-input")), bb(save)
    check("view name and Save share the bottom row, name first",
          abs(name["y"] + name["height"] / 2 - (sv["y"] + sv["height"] / 2)) < 2 and name["x"] < sv["x"])
    panel, tog = bb(pg.locator(f"{V} .viewer-camera-panel")), bb(pg.locator(f"{V} .viewer-camera-toggle-btn"))
    inside = (tog["x"] >= panel["x"] and tog["x"] + tog["width"] <= panel["x"] + panel["width"] + 0.5
              and tog["y"] >= panel["y"] and tog["y"] + tog["height"] <= panel["y"] + panel["height"] + 0.5)
    aligned = abs((tog["y"] + tog["height"] / 2) - (sv["y"] + sv["height"] / 2)) <= 2 and tog["x"] > sv["x"] + sv["width"]
    check("camera toggle sits inside the open panel, at the right end of the bottom row", inside and aligned,
          f"toggle y {tog['y']:.0f}-{tog['y']+tog['height']:.0f} x..{tog['x']+tog['width']:.0f} | panel y {panel['y']:.0f}-{panel['y']+panel['height']:.0f} x..{panel['x']+panel['width']:.0f} | save y mid {sv['y']+sv['height']/2:.0f}")
    check("the toggle is the element under its own centre (above the panel)",
          pg.evaluate(f"() => {{ const b = document.querySelector('{V} .viewer-camera-toggle-btn').getBoundingClientRect(); const el = document.elementFromPoint(b.x + b.width / 2, b.y + b.height / 2); return !!(el && el.closest('.viewer-camera-toggle-btn')); }}"))
    pg.click(f"{V} .viewer-camera-toggle-btn"); pg.wait_for_timeout(300)
    check("clicking it closes the panel", not pg.locator(V).evaluate("el => el.classList.contains('camera-open')"))
    pg.click(f"{V} .viewer-camera-toggle-btn"); pg.wait_for_timeout(300)
    check("and reopens it", pg.locator(V).evaluate("el => el.classList.contains('camera-open')"))

    # The docked filter panel narrows the canvas: panel and toggle must move together (same containing block).
    pg.click(f"{V} .viewer-settings-btn")
    pg.wait_for_function(f"() => document.querySelector('{V}').classList.contains('filters-open')", timeout=10000)
    settle(V)
    panel2, tog2 = bb(pg.locator(f"{V} .viewer-camera-panel")), bb(pg.locator(f"{V} .viewer-camera-toggle-btn"))
    shift_panel = (panel2["x"] + panel2["width"]) - (panel["x"] + panel["width"])
    shift_tog = (tog2["x"] + tog2["width"]) - (tog["x"] + tog["width"])
    check("filters open: panel and toggle shift by the same amount", shift_panel < -100 and abs(shift_panel - shift_tog) < 1,
          f"panel {shift_panel:.0f}px, toggle {shift_tog:.0f}px")
    pg.click(f"{V} .viewer-settings-btn")
    pg.wait_for_function(f"() => !document.querySelector('{V}').classList.contains('filters-open')", timeout=10000)
    settle(V)

    print("\n=== Snapshot button (2026-09-24): Save / Snapshot / Camera, left to right ===")
    # Runs after the filters test, and re-measures its own neighbours rather
    # than reusing that test's boxes: the filter panel's width is animated, so
    # anything measured across that toggle has to be re-read once it settles.
    settle(V)
    snap = pg.locator(f"{V} .viewer-snapshot-btn")
    check("Snapshot is an icon button with an accessible name of its own",
          snap.locator("use[href='#icon-screenshot']").count() == 1
          and snap.get_attribute("aria-label") == "Snapshot" and not snap.inner_text().strip())
    sn, sv2 = bb(snap), bb(pg.locator(f"{V} .viewer-save-view-btn"))
    cam, pan = bb(pg.locator(f"{V} .viewer-camera-toggle-btn")), bb(pg.locator(f"{V} .viewer-camera-panel"))
    check("bottom row reads Save -> Snapshot -> Camera, all on one line",
          sv2["x"] + sv2["width"] <= sn["x"] and sn["x"] + sn["width"] <= cam["x"]
          and abs((sn["y"] + sn["height"] / 2) - (sv2["y"] + sv2["height"] / 2)) <= 2,
          f"save x..{sv2['x']+sv2['width']:.0f} | snapshot x {sn['x']:.0f}..{sn['x']+sn['width']:.0f} | camera x {cam['x']:.0f}")
    check("Snapshot sits inside the open panel and is clickable above it",
          sn["x"] >= pan["x"] and sn["x"] + sn["width"] <= pan["x"] + pan["width"] + 0.5
          and pg.evaluate(f"() => {{ const b = document.querySelector('{V} .viewer-snapshot-btn').getBoundingClientRect(); const el = document.elementFromPoint(b.x + b.width / 2, b.y + b.height / 2); return !!(el && el.closest('.viewer-snapshot-btn')); }}"))
    # "Static location", like the filters and intent toggles: opening or closing
    # the panel must not move it, which is the whole reason it is a corner button
    # and not a child of the panel.
    toggle_camera(False)
    sn_closed = bb(snap)
    check("Snapshot stays put with the panel closed", snap.is_visible()
          and abs(sn_closed["x"] - sn["x"]) < 0.5 and abs(sn_closed["y"] - sn["y"]) < 0.5,
          f"{sn['x']:.0f},{sn['y']:.0f} -> {sn_closed['x']:.0f},{sn_closed['y']:.0f}")
    toggle_camera(True)

    # The capture itself. preserveDrawingBuffer is OFF and stays off, so a
    # bare toDataURL() reads back a cleared buffer - a valid, empty,
    # entirely plausible PNG. These checks are what tells the two apart: the
    # same canvas read WITHOUT a re-render first must be uniform, and the
    # module's own capture must not be.
    shot = pg.evaluate(SNAPSHOT_JS, V)
    check("preserveDrawingBuffer still off", shot["preserve"] is False)
    check("reading the canvas without re-rendering first yields a blank frame",
          shot["stale"] <= 2, f"{shot['stale']} distinct colours")
    check("captureWorldPng renders and reads in one tick, so the frame has content",
          shot["fresh"] > 5 and shot["w"] == shot["canvasW"] and shot["h"] == shot["canvasH"],
          f"{shot['fresh']} distinct colours at {shot['w']}x{shot['h']} (canvas {shot['canvasW']}x{shot['canvasH']})")

    # And end to end: the button downloads that PNG, named after the model
    # file's stem plus the view-name box next to it and a YYYYMMDD-HHMMSS stamp
    # (2026-10-01; it was the content key until then).
    pg.fill(f"{V} .viewer-view-name-input", "Roof Level 2!")
    with pg.expect_download() as dl:
        pg.click(f"{V} .viewer-snapshot-btn")
    download = dl.value
    path = f"{OUT}/11_snapshot.png"
    download.save_as(path)
    check("file name is <model stem>-<slugified view name>-<timestamp>.png",
          re.fullmatch(r".+-roof-level-2-\d{8}-\d{6}\.png", download.suggested_filename) is not None,
          download.suggested_filename)
    with Image.open(path) as im:
        im.load()
        colours = im.convert("RGB").getcolors(maxcolors=1 << 20) or []
        check("the downloaded PNG is the canvas, at canvas size, and is not blank",
              im.size == (shot["canvasW"], shot["canvasH"]) and len(colours) > 5,
              f"{im.size[0]}x{im.size[1]}, {len(colours)} colours")
    pg.fill(f"{V} .viewer-view-name-input", "")
    with pg.expect_download() as dl2:
        pg.click(f"{V} .viewer-snapshot-btn")
    dl2.value.cancel()
    check("an empty view-name box falls back to '<model stem>-snapshot-<timestamp>.png'",
          re.fullmatch(r".+-snapshot-\d{8}-\d{6}\.png", dl2.value.suggested_filename) is not None,
          dl2.value.suggested_filename)

    print("\n=== Snapshot metadata: the Meta switch (2026-10-22) ===")
    import json
    meta_btn = f"{V} .viewer-snapshot-meta-btn"
    check("the camera panel's bottom row carries a Meta switch, off by default, with an accessible name",
          pg.get_attribute(meta_btn, "aria-pressed") == "false" and pg.get_attribute(meta_btn, "aria-label") == "Snapshot metadata")
    pg.evaluate(f"() => document.querySelector('{meta_btn}').click()")
    check("pressing it turns it on and stores the browser preference",
          pg.get_attribute(meta_btn, "aria-pressed") == "true" and pg.evaluate("() => localStorage.getItem('bi2m:snapshotMetadata')") == "1")
    # Refer an intent so the picture has a selection and a ghost
    rid = pg.evaluate(f"""() => {{
      const row = document.querySelector('{V} .intent-row[data-intent-id]');
      for (let el = row; el; el = el.parentElement) if (el.tagName === 'DETAILS') el.open = true;
      return row && row.dataset.intentId;
    }}""")
    pg.click(f'{V} [data-intent-id="{rid}"] .intent-refer-btn')
    pg.wait_for_selector(f'{V} [data-intent-id="{rid}"][data-refer-status="done"]', timeout=60000)
    members = pg.evaluate(f"""() => {{
      const __u = performance.getEntriesByType('resource').map(e => e.name).filter(n => /\\/viewerRegistry\\.js(\\?|$)/.test(n)).pop() || '/viewerRegistry.js';
      const __m = performance.getEntriesByType('resource').map(e => e.name).filter(n => /\\/viewerModel\\.js(\\?|$)/.test(n)).pop() || '/viewerModel.js';
      return Promise.all([import(__u), import(__m)]).then(([reg, vm]) => {{
        const v = reg.viewerData[0]; const model = v.getCurrentModel();
        const intent = (vm.getModelContext(model).intents || []).find(i => i.id === v.cameraScope.intentId);
        return {{ member: [...new Set(intent.members.filter(m => m.role !== 'context').map(m => m.guid))], context: [...new Set(intent.members.filter(m => m.role === 'context').map(m => m.guid))] }};
      }});
    }}""")
    downloads = []
    pg.on("download", lambda d: downloads.append(d))
    pg.fill(f"{V} .viewer-view-name-input", "meta test")
    pg.click(f"{V} .viewer-snapshot-btn")
    for _ in range(60):
        if len(downloads) >= 2: break
        pg.wait_for_timeout(250)
    names = sorted(d.suggested_filename for d in downloads)
    check("with Meta on, one click downloads the PNG and a JSON of the same name", len(downloads) == 2 and names[0].endswith(".json") and names[1].endswith(".png") and names[0][:-5] == names[1][:-4], str(names))
    meta = None
    for d in downloads:
        if d.suggested_filename.endswith(".json"):
            p = f"{OUT}/12_snapshot_meta.json"; d.save_as(p); meta = json.load(open(p))
        else:
            d.cancel()
    if meta:
        check("the JSON carries schema 1, the picture join, the pose and the rule",
              meta["schema"] == 1 and meta["image"]["file"] == names[1] and meta["image"]["width"] == shot["canvasW"]
              and meta["pose"]["projection"] in ("Perspective", "Orthographic") and meta["visibleRule"]["name"] == "ghost-transparent" and meta["visibleRule"]["transparency"] == 90,
              json.dumps({k: meta[k] for k in ("schema", "image", "visibleRule")})[:200])
        check("`selected` is the referred intent's judged members and `selectedContext` its context-role members",
              set(meta["selected"]) == set(members["member"]) and len(members["member"]) > 0 and set(meta["selectedContext"]) == set(members["context"]) - set(members["member"]),
              f"{len(meta['selected'])} selected, {len(members['member'])} members; {len(meta['selectedContext'])} context")
        check("at the Refer's own view the referred elements are visible through the ghost (picture-faithful rule)",
              len(meta["selectedVisible"]) > 0 and set(meta["selectedVisible"]) <= set(meta["selected"]), f"{len(meta['selectedVisible'])} of {len(meta['selected'])} visible, {len(meta['selectedHidden'])} hidden")
        check("the ghosted building is listed as `ghosted`, not as visible, and the lists do not overlap",
              len(meta["ghosted"]) > 0 and not (set(c["guid"] for c in meta["ghosted"]) & set(v["guid"] for v in meta["visible"]))
              and not (set(meta["visibleOnly"]) & set(meta["selected"])) and meta["visibleRule"]["ghostedRule"] == "front-most ghost layer",
              f"{len(meta['ghosted'])} ghosted, {len(meta['visible'])} visible, {len(meta['visibleOnly'])} visible-only")
        check("every visible entry has a pixel count at or above the minimum", all(v["px"] >= meta["visibleRule"]["minPixels"] for v in meta["visible"]))
    pg.click(f"{V} .intent-clear-btn"); pg.wait_for_timeout(300)
    pg.evaluate(f"() => document.querySelector('{meta_btn}').click()")
    downloads.clear()
    pg.click(f"{V} .viewer-snapshot-btn")
    pg.wait_for_timeout(2500)
    check("with Meta off again, one click downloads the picture only", len(downloads) == 1 and downloads[0].suggested_filename.endswith(".png")
          and pg.get_attribute(meta_btn, "aria-pressed") == "false", str([d.suggested_filename for d in downloads]))
    for d in downloads: d.cancel()
    pg.fill(f"{V} .viewer-view-name-input", "")

    print("\n=== Stepping the readouts moves the camera ===")
    pg.click(f"{V} .viewer-side-view-btn"); pg.wait_for_timeout(500)
    def readouts():
        return [float(pg.input_value(f"{V} .viewer-camera-{k}-value")) for k in ("angle", "azimuth", "distance")]
    e0, a0, d0 = readouts()
    check("after Side 45 the inputs read elevation 45, azimuth 45, and a distance in metres",
          abs(e0 - 45) < 0.11 and abs(a0 - 45) < 0.11 and d0 > 1, f"{e0}, {a0}, {d0}")
    pg.fill(f"{V} .viewer-camera-angle-value", "30"); pg.dispatch_event(f"{V} .viewer-camera-angle-value", "change"); pg.wait_for_timeout(1500)
    e1, a1, d1 = readouts()
    check("typing 30 into elevation orbits to 30° and leaves azimuth and distance alone",
          abs(e1 - 30) < 0.11 and abs(a1 - a0) < 0.11 and abs(d1 - d0) < 0.05, f"{e1}, {a1}, {d1}")
    pg.fill(f"{V} .viewer-camera-azimuth-value", "135"); pg.dispatch_event(f"{V} .viewer-camera-azimuth-value", "change"); pg.wait_for_timeout(1500)
    e2, a2, d2 = readouts()
    check("typing 135 into azimuth turns the camera to 135° at the same elevation and distance",
          abs(a2 - 135) < 0.11 and abs(e2 - 30) < 0.11 and abs(d2 - d0) < 0.05, f"{e2}, {a2}, {d2}")
    pg.fill(f"{V} .viewer-camera-distance-value", str(round(d0 * 0.8, 1))); pg.dispatch_event(f"{V} .viewer-camera-distance-value", "change"); pg.wait_for_timeout(1500)
    e3, a3, d3 = readouts()
    check("typing a shorter distance dollies in without turning", abs(d3 - round(d0 * 0.8, 1)) < 0.11 and abs(a3 - 135) < 0.11, f"{d3} (asked {round(d0 * 0.8, 1)})")
    check("BCF sits in the bottom row left of Save, as a square icon button with an accessible name",
          pg.locator(f"{V} .viewer-camera-bottom-row .viewer-view-bcf-btn").count() == 1
          and bb(pg.locator(f"{V} .viewer-view-bcf-btn"))["x"] < bb(pg.locator(f"{V} .viewer-save-view-btn"))["x"]
          and pg.get_attribute(f"{V} .viewer-view-bcf-btn", "aria-label") == "BCF")
    pg.screenshot(path=f"{OUT}/10_narrow_panel.png")
    check("no console or page errors", not errs, "; ".join(errs[:3]))
    bad = [n for n, ok in res if not ok]
    print(f"\n{len(res)-len(bad)}/{len(res)} checks passed" + (f"\nFAILED: {bad}" if bad else ""))
    b.close()

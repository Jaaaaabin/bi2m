"""Tier 1 foundations: self-hosted engine, fonts
and icons; cross-origin isolation; inspector placement; landmarks, headings,
labels; settings migration; gated logging; tile parity. Writes no verdicts.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import BASE_URL, CHROMIUM_ARGS, STREAMED_MODEL, skip_streamed
from playwright.sync_api import sync_playwright

V = "#viewerContainer1"
# Errors this app does not own and cannot fix from here - excluded from the
# "no other console errors" check so a real regression still fails it:
#  - "Shader"      the known SwiftShader compile complaint (F12), headless only.
#  - "removeEntry" @thatopen/fragments' OPFS file cache sweeps itself on a 10s
#                  timer and deletes every entry whose localStorage last-access
#                  stamp is older than maxDeadTime (60s), calling
#                  rootDir.removeEntry(name) with neither `await` nor
#                  {recursive: true} (dist/index.mjs:7704). A non-empty
#                  directory therefore rejects asynchronously and lands in the
#                  console. Streamed path only, and intermittent by
#                  construction: it depends on whether a run crosses that 60s
#                  mark before streaming.
def known_library_error(message):
    return "Shader" in message or "removeEntry" in message

res = []
def check(n, ok, d=""):
    res.append(ok); print(f"  [{'PASS' if ok else 'FAIL'}] {n}" + (f" - {d}" if d else ""))

with sync_playwright() as p:
    b = p.chromium.launch(args=CHROMIUM_ARGS)
    pg = b.new_page(viewport={"width": 1600, "height": 900})
    errs, logs, reqs = [], [], []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.on("console", lambda m: (errs.append(m.text) if m.type == "error" else None) or (logs.append(m.text) if m.type == "log" else None))
    pg.on("request", lambda r: reqs.append(r.url))
    # legacy settings keys present before the app runs -> must be migrated
    pg.add_init_script("try { if (!localStorage.getItem('__migrated')) { localStorage.setItem('ifcviewer-theme', 'light'); localStorage.setItem('ifcviewer-sidebar-collapsed', '0'); localStorage.setItem('__migrated', '1'); } } catch (e) {}")
    pg.goto(BASE_URL, wait_until="networkidle")

    # ---- 1.9 settings migration ----
    st = pg.evaluate("() => ({ newTheme: localStorage.getItem('bi2m:theme'), oldTheme: localStorage.getItem('ifcviewer-theme'), newSb: localStorage.getItem('bi2m:sidebarCollapsed'), oldSb: localStorage.getItem('ifcviewer-sidebar-collapsed') })")
    check("legacy settings keys migrated to bi2m:*", st["newTheme"] == "light" and st["oldTheme"] is None and st["newSb"] == "0" and st["oldSb"] is None, str(st))
    pg.evaluate("() => { localStorage.removeItem('bi2m:theme'); localStorage.removeItem('bi2m:sidebarCollapsed'); localStorage.removeItem('__migrated'); }")

    # ---- 1.2 fonts + icons, 1.8 landmarks ----
    check("no .material-symbols-outlined elements", pg.locator(".material-symbols-outlined").count() == 0)
    # 18 since 2026-09-24: 17 Material Symbols plus the hand-drawn icon-eject;
    # 19 since 2026-10-01: the hand-drawn icon-polyline for the Lines (test) button.
    # icon-screenshot arrived with the Snapshot button, icon-chevron_left left
    # with the sidebar collapse toggle.
    check("icon sprite present with 19 symbols", pg.locator("svg symbol[id^='icon-']").count() == 19)
    check("sidebar buttons render SVG icons", pg.locator("#sidebar-panel svg.icon use").count() >= 5)
    fonts = pg.evaluate("async () => { await document.fonts.ready; return [...document.fonts].filter(f => f.family.replace(/\"/g,'') === 'Space Grotesk' && f.status === 'loaded').length; }")
    check("Space Grotesk loaded from a local @font-face", fonts >= 1, f"{fonts} face(s) loaded")
    check("sidebar is an <aside> landmark", pg.locator("aside#sidebar-panel[aria-label]").count() == 1)
    check("not cross-origin isolated by default (multi-thread web-ifc rejected 2026-09-21, opt-in via ?coi=1)", pg.evaluate("() => window.crossOriginIsolated") is False)

    # ---- 1.2 the two icons that change at runtime ----
    href0 = pg.get_attribute("#theme-toggle-icon use", "href")
    pg.click("#theme-toggle-btn"); pg.wait_for_timeout(150)
    href1 = pg.get_attribute("#theme-toggle-icon use", "href"); theme1 = pg.evaluate("() => localStorage.getItem('bi2m:theme')")
    pg.click("#theme-toggle-btn"); pg.wait_for_timeout(150)
    check("theme toggle swaps its SVG icon and stores bi2m:theme", href0 != href1 and href1 in ("#icon-light_mode", "#icon-dark_mode") and theme1 in ("light", "dark"), f"{href0} -> {href1}, stored {theme1}")
    pg.evaluate("() => localStorage.removeItem('bi2m:theme')")

    # ---- the one-column sidebar (2026-09-24) ----
    # One mode, not two: the collapse toggle and its chevron are gone, every
    # control is stacked in a single 44px column, and the transparency slider
    # is vertical so it fits in the 32px of usable width.
    check("the collapse toggle and its chevron glyph are gone",
          pg.locator("#sidebar-collapse-btn").count() == 0
          and pg.locator("symbol#icon-chevron_left").count() == 0
          and not pg.evaluate("() => document.body.classList.contains('sidebar-collapsed')"))
    # The pointer is still parked on the theme button from the click above, and
    # .sidebar-buttons button:hover carries transform: scale(1.05) - a hovered
    # button's client rect is 1.5px wider and half that further left, which is
    # enough to read as a second column. offsetLeft is the LAYOUT position and
    # ignores transforms, so the column test is immune to where the mouse is;
    # the pointer is moved off anyway, for the rect-based reads below.
    pg.mouse.move(600, 500)
    sb = pg.evaluate("""() => {
      const panel = document.getElementById('sidebar-panel');
      const pr = panel.getBoundingClientRect();
      const slider = document.getElementById('global-opacity-slider').getBoundingClientRect();
      const btns = [...panel.querySelectorAll('button')];
      const lefts = new Set(btns.map(b => b.offsetLeft));
      return {width: Math.round(pr.width), height: Math.round(pr.height),
              order: btns.map(b => b.id), columns: lefts.size,
              sliderH: slider.height, sliderW: Math.round(slider.width),
              ratio: slider.height / pr.height};
    }""")
    check("one 44px column, Theme first and the four viewer controls last",
          sb["width"] == 44 and sb["columns"] == 1
          and sb["order"] == ["theme-toggle-btn", "bulk-upload-btn", "example-models-btn",
                              "library-models-btn", "panels-default-btn", "add-viewer-btn",
                              "remove-viewer-btn", "sync-cam-btn", "match-sizes-btn"],
          f"{sb['width']}px, {sb['columns']} column(s), {sb['order']}")
    check("transparency slider is vertical and at most a fifth of the panel tall",
          sb["sliderW"] < sb["sliderH"] and sb["ratio"] <= 0.2 + 1e-6,
          f"{sb['sliderW']}x{sb['sliderH']:.0f}px = {sb['ratio']*100:.1f}% of {sb['height']}px")
    # Orientation, tested by driving it rather than by reading CSS: the thumb
    # is a pseudo-element and cannot be measured, but clicking the track can.
    sbox = pg.locator("#global-opacity-slider").bounding_box()
    pg.mouse.click(sbox["x"] + sbox["width"] / 2, sbox["y"] + sbox["height"] - 4)
    low = pg.eval_on_selector("#global-opacity-slider", "el => Number(el.value)")
    pg.mouse.click(sbox["x"] + sbox["width"] / 2, sbox["y"] + 4)
    high = pg.eval_on_selector("#global-opacity-slider", "el => Number(el.value)")
    check("0% is at the bottom of the track and 100% at the top",
          low < 15 and high > 85, f"bottom -> {low}%, top -> {high}%")
    pg.evaluate("() => { const s = document.getElementById('global-opacity-slider'); s.value = '0'; s.dispatchEvent(new Event('input', {bubbles: true})); }")

    # ---- load a model: engine files, external origins ----
    pg.click("#example-models-btn")
    pg.wait_for_selector('#example-models-flyout .example-models-item[data-file-name="example_autcon.ifc"]', timeout=20000)
    pg.click('#example-models-flyout .example-models-item[data-file-name="example_autcon.ifc"]')
    pg.wait_for_selector(f"{V} .intent-row", timeout=180000, state="attached")
    pg.wait_for_load_state("networkidle"); pg.wait_for_timeout(1000)
    ext = sorted({u for u in reqs if not u.startswith(BASE_URL.split("/", 3)[0] + "//" + BASE_URL.split("/")[2])})
    check("zero requests to third-party origins across load", not ext, "; ".join(u[:60] for u in ext[:3]))
    wasm = [u for u in reqs if "/wasm/" in u]
    check("web-ifc engine served from /wasm/", any(u.endswith(".wasm") for u in wasm), "; ".join(os.path.basename(u) for u in wasm))
    check("single-thread engine (web-ifc.wasm), no pthread workers", any(u.endswith("/web-ifc.wasm") for u in wasm) and not any("worker" in u for u in wasm), "; ".join(os.path.basename(u) for u in wasm))
    check("no unpkg requests", not any("unpkg.com" in u for u in reqs))

    # ---- 1.8 headings / labels ----
    check("no h4 inside the viewer panels (heading order h1 > h2 > h3)", pg.locator(f"{V} h4").count() == 0 and pg.locator(f"{V} h2, {V} h3").count() > 0)
    check("the three camera readouts are labelled number inputs", pg.evaluate(f"() => ['angle', 'azimuth', 'distance'].every(k => {{ const i = document.querySelector('{V} .viewer-camera-' + k + '-value'); return i && i.tagName === 'INPUT' && i.type === 'number' && !!i.closest('label'); }})"))
    check("a reduced-motion rule exists", pg.evaluate("() => [...document.styleSheets].flatMap(s => { try { return [...s.cssRules]; } catch { return []; } }).some(r => r.media && /reduced-motion/.test(r.media.mediaText))"))
    check("no `transition: all` left in the stylesheet", pg.evaluate("() => ![...document.styleSheets].flatMap(s => { try { return [...s.cssRules]; } catch { return []; } }).some(r => r.style && /^all\\b/.test(r.style.transitionProperty || '') && r.style.transitionProperty.split(',').some(p => p.trim() === 'all'))"))

    # ---- 1.6 gated logging: 30 slider events -> 0 console.log ----
    logs.clear()
    pg.evaluate("() => { const s = document.getElementById('global-opacity-slider'); for (let i = 0; i <= 30; i++) { s.value = String(i * 3); s.dispatchEvent(new Event('input', {bubbles: true})); } s.value = '0'; s.dispatchEvent(new Event('input', {bubbles: true})); }")
    pg.wait_for_timeout(200)
    check("transparency slider logs nothing without ?debug", len(logs) == 0, f"{len(logs)} log lines")

    # ---- 1.10 tile parity ----
    check("first tile has no private min-width/min-height", pg.evaluate(f"() => {{ const c = getComputedStyle(document.querySelector('{V}')); return c.minWidth === '280px' && c.minHeight === '200px' || c.minWidth; }}") is True
          or pg.evaluate(f"() => getComputedStyle(document.querySelector('{V}')).minWidth") in ("280px", "520px", "740px"),
          pg.evaluate(f"() => getComputedStyle(document.querySelector('{V}')).minWidth + ' x ' + getComputedStyle(document.querySelector('{V}')).minHeight"))

    # ---- 1.7 inspector placement: select an element, no overlap with the camera panel or the tile's top buttons ----
    c = pg.locator(f"{V} .viewer-canvas-area canvas").first; bb = c.bounding_box()
    hit = False
    for dx, dy in [(0, 0), (40, 0), (-40, 0), (0, 40), (0, -40), (80, 40), (-80, -40), (120, 0)]:
        pg.mouse.click(bb["x"] + bb["width"] * 0.6 + dx, bb["y"] + bb["height"] * 0.5 + dy); pg.wait_for_timeout(600)
        if pg.locator(".inspector-panel").count(): hit = True; break
    if hit:
        def overlap(a, b):
            ox = max(0, min(a["x"] + a["width"], b["x"] + b["width"]) - max(a["x"], b["x"]))
            oy = max(0, min(a["y"] + a["height"], b["y"] + b["height"]) - max(a["y"], b["y"]))
            return ox * oy
        ib = pg.locator(".inspector-panel").bounding_box()
        cam = pg.locator(f"{V} .viewer-camera-panel").bounding_box()
        check("inspector does not overlap the camera panel", overlap(ib, cam) == 0, f"{overlap(ib, cam):.0f} px²")
        btns = [pg.locator(f"{V} .{c}").bounding_box() for c in ["viewer-close-btn", "viewer-unload-btn", "viewer-settings-btn"]]
        check("inspector does not overlap the tile's top buttons", all(overlap(ib, x) == 0 for x in btns))
        check("inspector fully on screen", ib["x"] >= 0 and ib["y"] >= 0 and ib["x"] + ib["width"] <= 1600 and ib["y"] + ib["height"] <= 900)
        pg.click(".inspector-close")
    else:
        check("inspector opened for an element click", False, "no element hit")

    # ---- streamed path smoke: shader error gone (F12) ----
    if not skip_streamed("streamed load: no shader compile error, no other console errors"):
        pg.click("#add-viewer-btn")
        pg.wait_for_selector(".viewer-container:nth-child(2) .viewer-empty-example-item", timeout=15000)
        errs.clear()
        pg.click(f'.viewer-container:nth-child(2) .viewer-empty-example-item[data-file-name="{STREAMED_MODEL}"]')
        pg.wait_for_selector(".viewer-container:nth-child(2) .intent-row", timeout=180000, state="attached")
        pg.wait_for_load_state("networkidle"); pg.wait_for_timeout(1500)
        check("streamed load logs no shader compile error", not any("Shader" in e for e in errs), "; ".join(e[:80] for e in errs[:1]))
        other = [e for e in errs if not known_library_error(e)]
        check("no other console or page errors", not other,
              f"{len(other)} unknown, {len(errs) - len(other)} known-library " + "; ".join(e[:80] for e in other[:2]))

    # ---- ?hud: the dev performance HUD (Tier 3) ----
    pg3 = b.new_page(viewport={"width": 1400, "height": 900})
    sep = "&" if "?" in BASE_URL else "?"
    pg3.goto(BASE_URL + sep + "hud", wait_until="networkidle")
    pg3.wait_for_selector("#perf-hud", timeout=15000); pg3.wait_for_timeout(700)
    hud_text = pg3.locator("#perf-hud").inner_text()
    check("?hud shows the performance HUD with frame, draw and heap lines", "frame" in hud_text and "draw" in hud_text and "heap" in hud_text, hud_text.replace("\n", " | ")[:120])
    check("no HUD without the flag", pg.locator("#perf-hud").count() == 0)
    pg3.close()

    # ---- an isolated document (COOP/COEP on, ?coi=1) must still load: the app pins web-ifc single-thread ----
    pg2 = b.new_page(viewport={"width": 1400, "height": 900}); errs2 = []
    pg2.on("console", lambda m: errs2.append(m.text) if m.type == "error" else None)
    sep = "&" if "?" in BASE_URL else "?"
    pg2.goto(BASE_URL + sep + "coi=1", wait_until="networkidle")
    iso = pg2.evaluate("() => window.crossOriginIsolated")
    pg2.wait_for_selector(f"{V} .viewer-empty-example-item", timeout=15000)
    pg2.click(f'{V} .viewer-empty-example-item[data-file-name="example_autcon.ifc"]')
    loaded = True
    try:
        pg2.wait_for_selector(f"{V} .intent-row", timeout=90000, state="attached")
    except Exception:
        loaded = False
    check("isolated document (?coi=1) still loads a model - web-ifc pinned single-thread", iso is True and loaded and not any("worker sent an error" in e for e in errs2), f"isolated={iso} loaded={loaded} workerErrors={sum('worker sent an error' in e for e in errs2)}")
    b.close()

print(f"\n{sum(res)}/{len(res)} checks passed")
sys.exit(0 if all(res) else 1)

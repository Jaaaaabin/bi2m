"""Frontend performance + a11y audit of the running viewer (dev server on :3000).
Software GL (swiftshader) - absolute fps is NOT representative of a GPU; the JS
main-thread numbers (long tasks, DOM build, slider loop) are what matter here.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import BASE_URL, OUT
import json, sys, time
from playwright.sync_api import sync_playwright

MODEL = sys.argv[1] if len(sys.argv) > 1 else "example_autcon.ifc"
V = "#viewerContainer1"
INIT = """
window.__lt = []; window.__frames = []; window.__rec = false;
try { new PerformanceObserver(l => { for (const e of l.getEntries()) window.__lt.push({s: Math.round(e.startTime), d: Math.round(e.duration)}); }).observe({type: 'longtask', buffered: true}); } catch (e) {}
window.__startFrames = () => { window.__frames = []; window.__rec = true; let last = performance.now();
  const tick = (t) => { window.__frames.push(t - last); last = t; if (window.__rec) requestAnimationFrame(tick); }; requestAnimationFrame(tick); };
window.__stopFrames = () => { window.__rec = false; return window.__frames.slice(1); };
"""
report = {"model": MODEL}
with sync_playwright() as p:
    b = p.chromium.launch(args=["--use-gl=swiftshader", "--enable-unsafe-swiftshader"])
    pg = b.new_page(viewport={"width": 1600, "height": 900})
    pg.add_init_script(INIT)
    errs, warns, logs = [], [], 0
    def on_console(m):
        global logs
        logs += 1
        if m.type == "error": errs.append(m.text)
        elif m.type == "warning": warns.append(m.text)
    pg.on("console", on_console); pg.on("pageerror", lambda e: errs.append(str(e)))
    reqs = []
    pg.on("response", lambda r: reqs.append(r))
    t0 = time.time()
    pg.goto(BASE_URL, wait_until="networkidle")
    report["page_ready_s"] = round(time.time() - t0, 2)
    nav = pg.evaluate("() => { const n = performance.getEntriesByType('navigation')[0]; return {dcl: Math.round(n.domContentLoadedEventEnd), load: Math.round(n.loadEventEnd)}; }")
    report["nav"] = nav
    res = pg.evaluate("() => performance.getEntriesByType('resource').map(r => ({n: r.name.split('/').slice(-1)[0].slice(0,40), t: r.initiatorType, sz: r.transferSize || r.encodedBodySize || 0, dur: Math.round(r.duration)}))")
    report["initial_requests"] = len(res)
    report["initial_bytes_kb"] = round(sum(r["sz"] for r in res) / 1024)
    report["top_resources"] = sorted(res, key=lambda r: -r["sz"])[:8]
    report["longtasks_boot"] = pg.evaluate("() => window.__lt.splice(0)")
    report["dom_nodes_boot"] = pg.evaluate("() => document.querySelectorAll('*').length")

    # ---- load a model ----
    pg.click("#example-models-btn")
    pg.wait_for_selector(f'.example-models-item[data-file-name="{MODEL}"]', timeout=20000)
    t1 = time.time()
    pg.click(f'.example-models-item[data-file-name="{MODEL}"]')
    pg.wait_for_selector(f"{V} .viewer-loading", state="visible", timeout=30000)
    pg.wait_for_selector(f"{V} .viewer-loading", state="hidden", timeout=300000)
    report["model_visible_s"] = round(time.time() - t1, 2)
    pg.wait_for_selector(f"{V} .intent-row, {V} .intent-empty", timeout=300000, state="attached")
    report["panel_ready_s"] = round(time.time() - t1, 2)
    pg.wait_for_load_state("networkidle"); pg.wait_for_timeout(1500)
    report["longtasks_load"] = pg.evaluate("() => window.__lt.splice(0)")
    report["console_msgs_during_load"] = logs
    report["dom_nodes_after_load"] = pg.evaluate("() => document.querySelectorAll('*').length")
    report["panel_nodes"] = pg.evaluate(f"() => document.querySelectorAll('{V} .viewer-intent-panel *').length")
    report["intent_rows"] = pg.locator(f"{V} .intent-row").count()
    report["mem_mb"] = pg.evaluate("() => performance.memory ? Math.round(performance.memory.usedJSHeapSize/1048576) : null")
    report["fragments"] = pg.evaluate("""async () => {
      const url = performance.getEntriesByType('resource').map(r => r.name).find(n => /viewerRegistry\\.js/.test(n));
      if (!url) return null; const m = await import(url); const e = m.viewerData[0]; if (!e) return null;
      let frags = 0, inst = 0; for (const g of e.fragments.groups.values()) for (const f of g.items) { frags++; inst += f.mesh?.count ?? 0; }
      return {groups: e.fragments.groups.size, fragments: frags, instances: inst, drawCalls: e.world.renderer.three.info.render.calls, tris: e.world.renderer.three.info.render.triangles};
    }""")
    pg.screenshot(path=f"{OUT}/audit_light.png")

    # ---- orbit: frame pacing + long tasks ----
    canvas = pg.locator(f"{V} .viewer-canvas-area canvas").first
    bb = canvas.bounding_box()
    cx, cy = bb["x"] + bb["width"] / 2, bb["y"] + bb["height"] / 2
    pg.evaluate("() => { window.__lt.length = 0; window.__startFrames(); }")
    pg.mouse.move(cx, cy); pg.mouse.down()
    for i in range(40):
        pg.mouse.move(cx + i * 6, cy + (i % 7) * 3, steps=2); pg.wait_for_timeout(16)
    pg.mouse.up(); pg.wait_for_timeout(300)
    frames = pg.evaluate("() => window.__stopFrames()")
    if frames:
        frames_sorted = sorted(frames)
        report["orbit_frames"] = {"n": len(frames), "avg_ms": round(sum(frames)/len(frames), 1), "p95_ms": round(frames_sorted[int(len(frames)*0.95)-1], 1), "max_ms": round(max(frames), 1)}
    report["longtasks_orbit"] = pg.evaluate("() => window.__lt.splice(0)")

    # ---- open the largest category, measure toggle cost ----
    t = pg.evaluate(f"""() => {{
      const secs = [...document.querySelectorAll('{V} .intent-category-section')];
      secs.sort((a,b) => b.querySelectorAll('.intent-row').length - a.querySelectorAll('.intent-row').length);
      const s = secs[0]; if (!s) return null; const t0 = performance.now(); s.open = true; s.querySelector('.intent-row:last-child').getBoundingClientRect(); return {{rows: s.querySelectorAll('.intent-row').length, ms: Math.round((performance.now()-t0)*10)/10}};
    }}""")
    report["open_largest_category"] = t

    # ---- transparency slider: 30 input events ----
    slider_ms = pg.evaluate("""() => {
      const s = document.getElementById('global-opacity-slider'); const t0 = performance.now();
      for (let i = 0; i <= 30; i++) { s.value = String(i * 3); s.dispatchEvent(new Event('input', {bubbles: true})); }
      return Math.round((performance.now() - t0) * 10) / 10;
    }""")
    report["slider_30_events_ms"] = slider_ms
    pg.evaluate("() => { const s = document.getElementById('global-opacity-slider'); s.value = '0'; s.dispatchEvent(new Event('input', {bubbles: true})); }")

    # ---- theme toggle cost + dark screenshot ----
    pg.click("#theme-toggle-btn"); pg.wait_for_timeout(400)
    pg.screenshot(path=f"{OUT}/audit_dark.png")
    pg.click("#theme-toggle-btn"); pg.wait_for_timeout(200)

    # ---- CSS/type facts ----
    report["font_sizes"] = pg.evaluate(f"""() => {{
      const c = {{}}; for (const el of document.querySelectorAll('{V} .viewer-intent-panel *, #sidebar-panel *, {V} .viewer-camera-panel *')) {{
        if (!el.textContent.trim() || el.children.length) continue; const fs = getComputedStyle(el).fontSize; c[fs] = (c[fs]||0)+1; }} return c; }}""")
    report["reduced_motion_rules"] = pg.evaluate("() => [...document.styleSheets].flatMap(s => { try { return [...s.cssRules]; } catch { return []; } }).filter(r => r.media && /reduced-motion/.test(r.media.mediaText)).length")
    report["focusable_without_label"] = pg.evaluate("() => [...document.querySelectorAll('button, [role=button], input, textarea')].filter(el => !(el.getAttribute('aria-label') || el.textContent.trim() || el.getAttribute('title') || el.labels?.length || el.getAttribute('placeholder'))).map(el => el.className || el.id).slice(0, 12)")

    # ---- axe-core (best effort, needs internet) ----
    try:
        pg.add_script_tag(url="https://cdnjs.cloudflare.com/ajax/libs/axe-core/4.10.2/axe.min.js")
        axe = pg.evaluate("async () => { const r = await axe.run(document, {resultTypes: ['violations']}); return r.violations.map(v => ({id: v.id, impact: v.impact, n: v.nodes.length, help: v.help, sample: v.nodes.slice(0,2).map(n => n.target.join(' '))})); }")
        report["axe_violations"] = axe
    except Exception as e:
        report["axe_violations"] = f"skipped: {e}"

    # ---- narrow viewport behaviour ----
    pg.set_viewport_size({"width": 820, "height": 900}); pg.wait_for_timeout(600)
    report["narrow_overflow_x"] = pg.evaluate("() => document.documentElement.scrollWidth - document.documentElement.clientWidth")
    pg.screenshot(path=f"{OUT}/audit_narrow.png")

    report["errors"] = errs[:6]; report["warnings"] = warns[:6]; report["console_total"] = logs
    b.close()

print(json.dumps(report, indent=1))
json.dump(report, open(f"{OUT}/perf_{MODEL.replace('.ifc','')}.json", "w"), indent=1)

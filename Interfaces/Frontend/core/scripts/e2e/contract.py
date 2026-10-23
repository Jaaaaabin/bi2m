"""Automation contract.

Asserts the selectors, data attributes and events that the batch driver
(scripts/autocamera.py) and every other harness in this directory rely on. A row redesign
that breaks one of these fails HERE, loudly, instead of silently breaking a
script written against the old markup. Writes no verdicts.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import BASE_URL, CHROMIUM_ARGS
from playwright.sync_api import sync_playwright

V = "#viewerContainer1"
res = []
def check(n, ok, d=""):
    res.append(ok); print(f"  [{'PASS' if ok else 'FAIL'}] {n}" + (f" - {d}" if d else ""))

with sync_playwright() as p:
    b = p.chromium.launch(args=CHROMIUM_ARGS)
    pg = b.new_page(viewport={"width": 1400, "height": 900})
    errs = []; pg.on("pageerror", lambda e: errs.append(str(e))); pg.on("console", lambda m: m.type == "error" and errs.append(m.text))
    pg.goto(BASE_URL, wait_until="networkidle")
    pg.click("#example-models-btn")
    pg.wait_for_selector('#example-models-flyout .example-models-item[data-file-name="example_autcon.ifc"]', timeout=20000)
    pg.click('#example-models-flyout .example-models-item[data-file-name="example_autcon.ifc"]')
    pg.wait_for_selector(f"{V} .intent-row", timeout=180000, state="attached")
    pg.wait_for_load_state("networkidle"); pg.wait_for_timeout(1000)

    # ---- structure ----
    rows = pg.locator(f"{V} .intent-row")
    n = rows.count()
    check("rows exist with data-intent-id", n > 0 and pg.locator(f"{V} .intent-row[data-intent-id]").count() == n, f"{n} rows")
    ids = pg.evaluate(f"() => [...document.querySelectorAll('{V} .intent-row')].map(r => r.dataset.intentId)")
    check("intent ids are unique", len(set(ids)) == n)
    for cls in ["intent-refer-btn", "intent-accept-btn", "intent-reject-btn", "intent-reset-btn"]:
        check(f"every row has .{cls}", pg.locator(f"{V} .intent-row .{cls}").count() == n)
    check("every row has .intent-status-icon, .intent-index, .intent-label, .intent-evidence",
          all(pg.locator(f"{V} .intent-row .{c}").count() == n for c in ["intent-status-icon", "intent-index", "intent-label", "intent-evidence"]))
    check("category sections are <details> with .intent-category-header <summary>",
          pg.locator(f"{V} details.intent-category-section > summary.intent-category-header").count() == pg.locator(f"{V} .intent-category-section").count() > 0)
    check("domain sections are <details> with .intent-domain-header <summary>",
          pg.locator(f"{V} details.intent-domain-section > summary.intent-domain-header").count() == pg.locator(f"{V} .intent-domain-section").count() > 0)
    check("bulk actions present (.intent-show-all-btn, .intent-clear-btn, .intent-export-btn)",
          all(pg.locator(f"{V} .{c}").count() == 1 for c in ["intent-show-all-btn", "intent-clear-btn", "intent-export-btn"]))
    check("camera panel controls present", all(pg.locator(f"{V} .{c}").count() == 1 for c in
          ["viewer-fit-max-btn", "viewer-side-view-btn", "viewer-elevation-view-btn", "viewer-projection-toggle-btn",
           "viewer-camera-angle-value", "viewer-camera-azimuth-value", "viewer-camera-distance-value",
           "viewer-view-bcf-btn", "viewer-view-name-input", "viewer-save-view-btn"]))
    check("tile chrome present", all(pg.locator(f"{V} .{c}").count() == 1 for c in
          ["viewer-close-btn", "viewer-unload-btn", "viewer-settings-btn", "viewer-camera-toggle-btn", "viewer-intent-toggle-btn", "viewer-resize-handle", "ifc-name-label"]))

    # ---- Refer lifecycle: data-refer-status pending -> done, aria-busy, events ----
    row = rows.first
    row.evaluate("el => { el.closest('.intent-category-section').open = true; }")
    pg.evaluate(f"""() => {{
      window.__ev = {{ complete: 0, scope: 0, progress: 0, busySeen: false, pendingSeen: false }};
      const c = document.querySelector('{V}');
      c.addEventListener('intent-refer-complete', e => {{ window.__ev.complete++; window.__ev.completeId = e.detail.intentId; }});
      c.addEventListener('camera-scope-change', e => {{ window.__ev.scope++; window.__ev.lastScope = e.detail.scope ? 'set' : 'cleared'; }});
      c.addEventListener('intent-review-progress', () => window.__ev.progress++);
      const r = document.querySelector('{V} .intent-row');
      new MutationObserver(() => {{
        if (r.dataset.referStatus === 'pending') window.__ev.pendingSeen = true;
        if (r.querySelector('.intent-refer-btn').getAttribute('aria-busy') === 'true') window.__ev.busySeen = true;
      }}).observe(r, {{ attributes: true, subtree: true }});
    }}""")
    row.locator(".intent-refer-btn").click()
    pg.wait_for_selector(f'{V} .intent-row[data-refer-status="done"]', timeout=60000)
    ev = pg.evaluate("() => window.__ev")
    check("Refer: data-refer-status went pending -> done", ev["pendingSeen"] and row.get_attribute("data-refer-status") == "done")
    check("Refer: aria-busy set during, cleared after", ev["busySeen"] and row.locator(".intent-refer-btn").get_attribute("aria-busy") is None)
    check("Refer: intent-refer-complete bubbled with the intent id", ev["complete"] == 1 and ev.get("completeId") == ids[0])
    check("Refer: camera-scope-change fired and left a scope set", ev["scope"] >= 1 and ev.get("lastScope") == "set")
    check("Refer button carries .is-active", row.locator(".intent-refer-btn").evaluate("el => el.classList.contains('is-active')"))

    pg.click(f"{V} .intent-clear-btn"); pg.wait_for_timeout(300)
    ev = pg.evaluate("() => window.__ev")
    check("Clear Selection: camera-scope-change fired with a cleared scope", ev.get("lastScope") == "cleared")
    check("Clear Selection: refer button released", not row.locator(".intent-refer-btn").evaluate("el => el.classList.contains('is-active')"))
    check("Clear Selection: transparency slider back to 0", pg.input_value("#global-opacity-slider") == "0")

    # ---- saved view recall completion signal ----
    (pg.locator(V).evaluate("el => el.classList.contains('camera-open')") or pg.click(f"{V} .viewer-camera-toggle-btn"))
    pg.fill(f"{V} .viewer-view-name-input", "contract"); pg.click(f"{V} .viewer-save-view-btn")
    pg.evaluate(f"() => document.querySelector('{V}').addEventListener('saved-view-recall-complete', e => window.__recall = e.detail.name)")
    pg.click(f"{V} .viewer-saved-view-name")
    pg.wait_for_selector(f'{V} .viewer-saved-view-name[data-recall-status="done"]', timeout=20000)
    check("Saved view recall: data-recall-status=done and saved-view-recall-complete fired", pg.evaluate("() => window.__recall") == "contract")

    check("no console or page errors", not errs, "; ".join(errs[:2]))
    b.close()

print(f"\n{sum(res)}/{len(res)} checks passed")
sys.exit(0 if all(res) else 1)

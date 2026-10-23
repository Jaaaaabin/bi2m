"""Unload model (2026-09-21): the per-tile Unload button releases the model
but keeps the viewer, and a tile can then load another model into itself.

Also pins down where the top-row buttons live after that change - Unload sits
immediately left of Reset camera, and the close button moved to the top-LEFT
corner, clear of the model-name label.

Writes no verdicts and never triggers Compute/Run.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import BASE_URL, CHROMIUM_ARGS, STREAMED_MODEL, skip_streamed
from playwright.sync_api import sync_playwright

V = "#viewerContainer1"
V2 = ".viewer-container:nth-child(2)"
# Whichever tile the last #add-viewer-btn click created - :last-child rather
# than :nth-child(3) because the streamed section above adds a tile only when
# there is a tiled fixture, so the index is not fixed.
V3 = "#viewer-wrapper > .viewer-container:last-child"

# classifier.list has no DOM representation, so the Floors/Categories the
# filter panel is built from are read straight off the viewer entry, through
# the same live-state hook the camera harnesses use.
CLASSIFIER_JS = """async (sel) => {
  const __u = performance.getEntriesByType('resource').map(e => e.name)
    .filter(n => /\\/viewerRegistry\\.js(\\?|$)/.test(n)).pop() || '/viewerRegistry.js';
  const {viewerData} = await import(__u);
  const id = document.querySelector(sel).id;
  const v = viewerData.find(e => e.container.id === id);
  const names = (system) => Object.keys(system || {}).sort();
  return {storeys: names(v.classifier.list.spatialStructures),
          entities: names(v.classifier.list.entities)};
}"""
res = []
def check(n, ok, d=""):
    res.append(ok); print(f"  [{'PASS' if ok else 'FAIL'}] {n}" + (f" - {d}" if d else ""))

def box(pg, sel):
    return pg.locator(sel).bounding_box()

def overlap(a, b):
    ox = max(0, min(a["x"] + a["width"], b["x"] + b["width"]) - max(a["x"], b["x"]))
    oy = max(0, min(a["y"] + a["height"], b["y"] + b["height"]) - max(a["y"], b["y"]))
    return ox * oy

with sync_playwright() as p:
    b = p.chromium.launch(args=CHROMIUM_ARGS)
    pg = b.new_page(viewport={"width": 1400, "height": 900})
    errs = []; pg.on("pageerror", lambda e: errs.append(str(e))); pg.on("console", lambda m: m.type == "error" and errs.append(m.text))
    pg.goto(BASE_URL, wait_until="networkidle")

    # ---- an empty tile still SHOWS Unload (always visible since 2026-09-21),
    # it is simply inert: unloadModelFromViewer returns unless hasModel ----
    check("empty tile has no .has-model but still shows Unload",
          pg.locator(f"{V}.has-model").count() == 0 and pg.locator(f"{V} .viewer-unload-btn").is_visible())
    pg.click(f"{V} .viewer-unload-btn"); pg.wait_for_timeout(400)
    check("clicking Unload on an empty tile is a no-op",
          pg.locator(f"{V} .viewer-empty-placeholder").count() == 1 and pg.locator(".viewer-container").count() == 1)

    pg.click("#example-models-btn")
    pg.wait_for_selector('#example-models-flyout .example-models-item[data-file-name="example_autcon.ifc"]', timeout=20000)
    pg.click('#example-models-flyout .example-models-item[data-file-name="example_autcon.ifc"]')
    pg.wait_for_selector(f"{V} .intent-row", timeout=180000, state="attached")
    pg.wait_for_load_state("networkidle"); pg.wait_for_timeout(1000)

    rows_before = pg.locator(f"{V} .intent-row").count()
    # Floors and categories are <bim-checkbox> elements built from
    # classifier.list - a stale entry surviving the unload would show up here
    # as a duplicate.
    filters_before = pg.locator(f"{V} .viewer-filter-section bim-checkbox").count()
    check("model loaded -> .has-model set and Unload visible",
          pg.locator(f"{V}.has-model").count() == 1 and pg.locator(f"{V} .viewer-unload-btn").is_visible(),
          f"{rows_before} intent rows")

    # ---- layout (2026-09-23): close + Unload top-left, filters toggle alone
    # top-right and anchored to the tile, name label centred, Reset camera gone ----
    unload, settings = box(pg, f"{V} .viewer-unload-btn"), box(pg, f"{V} .viewer-settings-btn")
    close, canvas = box(pg, f"{V} .viewer-close-btn"), box(pg, f"{V} .viewer-canvas-area")
    tile = box(pg, V)
    check("Reset camera (home) button is gone", pg.locator(f"{V} .viewer-reset-btn").count() == 0)
    # Measured against .viewer-canvas-area: close and Unload anchor to the canvas
    # so they stay over the 3D viewport when the docked intent panel (order:-1,
    # LEFT of the canvas) is open.
    check("close button in the canvas's top-LEFT corner, Unload right beside it on the same row",
          close["x"] - canvas["x"] < 40 and round(close["y"]) == round(unload["y"])
          and 0 < unload["x"] - (close["x"] + close["width"]) < 10,
          f"close x offset {close['x'] - canvas['x']:.0f}px, gap to Unload {unload['x'] - (close['x'] + close['width']):.0f}px")
    top_right = pg.locator(f"{V} button").evaluate_all(
        "els => els.filter(b => { const r = b.getBoundingClientRect(), t = b.closest('.viewer-container').getBoundingClientRect(); return r.width > 0 && r.top - t.top < 60 && t.right - r.right < 130 && !b.closest('.viewer-filter-panel'); }).map(b => b.className)")
    check("filters toggle is the only button in the tile's top-right, on the same row",
          top_right == ["viewer-settings-btn"] and round(settings["y"]) == round(close["y"]), str(top_right))
    label = box(pg, f"{V} .ifc-name-label")
    check("model-name label centred on the canvas, clear of the top-left pair",
          abs((label["x"] + label["width"] / 2) - (canvas["x"] + canvas["width"] / 2)) < 2
          and overlap(label, close) == 0 and overlap(label, unload) == 0,
          f"label centre {label['x'] + label['width'] / 2:.0f} vs canvas centre {canvas['x'] + canvas['width'] / 2:.0f}")
    pg.click(f"{V} .viewer-settings-btn"); pg.mouse.move(5, 5); pg.wait_for_timeout(450)  # mouse away: hover scales the button 1.1x
    settings_open, canvas_open = box(pg, f"{V} .viewer-settings-btn"), box(pg, f"{V} .viewer-canvas-area")
    centre = lambda b: (b["x"] + b["width"] / 2, b["y"] + b["height"] / 2)
    check("filters toggle stays put when the filter panel opens (canvas narrowed, button did not move)",
          abs(centre(settings_open)[0] - centre(settings)[0]) < 1 and abs(centre(settings_open)[1] - centre(settings)[1]) < 1
          and canvas_open["width"] < canvas["width"] - 100,
          f"button centre x {centre(settings)[0]:.0f} -> {centre(settings_open)[0]:.0f}, canvas width {canvas['width']:.0f} -> {canvas_open['width']:.0f}")
    first_section = pg.locator(f"{V} .viewer-filter-panel-inner > *").first.bounding_box()
    check("filter panel content starts below the floating toggle",
          first_section["y"] >= settings_open["y"] + settings_open["height"],
          f"first section y {first_section['y']:.0f}, toggle bottom {settings_open['y'] + settings_open['height']:.0f}")
    pg.click(f"{V} .viewer-settings-btn"); pg.wait_for_timeout(450)
    # Bottom-left pair (2026-09-23): intent toggle and shortcuts toggle are tile-anchored
    # too, so they stay in the tile's lower-left whether the intent panel is open or closed.
    pat, sc = box(pg, f"{V} .viewer-intent-toggle-btn"), box(pg, f"{V} .viewer-shortcuts-toggle-btn")
    check("intent toggle in the tile's lower-left with the shortcuts toggle right beside it",
          pat["x"] - tile["x"] < 40 and (tile["y"] + tile["height"]) - (pat["y"] + pat["height"]) < 40
          and round(pat["y"]) == round(sc["y"]) and 0 < sc["x"] - (pat["x"] + pat["width"]) < 10,
          f"intent x offset {pat['x'] - tile['x']:.0f}px, gap to shortcuts {sc['x'] - (pat['x'] + pat['width']):.0f}px")
    was_open = pg.locator(V).evaluate("el => el.classList.contains('intent-open')")
    pg.click(f"{V} .viewer-intent-toggle-btn"); pg.mouse.move(5, 5); pg.wait_for_timeout(450)
    pat2, canvas2 = box(pg, f"{V} .viewer-intent-toggle-btn"), box(pg, f"{V} .viewer-canvas-area")
    check("intent toggle stays put when the intent panel toggles (canvas moved, button did not)",
          abs(centre(pat2)[0] - centre(pat)[0]) < 1 and abs(centre(pat2)[1] - centre(pat)[1]) < 1
          and abs(canvas2["x"] - canvas["x"]) > 100,
          f"button centre x {centre(pat)[0]:.0f} -> {centre(pat2)[0]:.0f}, canvas x {canvas['x']:.0f} -> {canvas2['x']:.0f}")
    pg.click(f"{V} .viewer-intent-toggle-btn"); pg.wait_for_timeout(450)
    assert pg.locator(V).evaluate("el => el.classList.contains('intent-open')") == was_open
    # Permanently --color-danger (#e05252 light / its dark-mode value), with no
    # hover involved - the icon inherits it through `color`, fill:currentColor.
    icon_color = pg.evaluate(f"() => getComputedStyle(document.querySelector('{V} .viewer-unload-btn .icon')).color")
    danger = pg.evaluate("() => getComputedStyle(document.documentElement).getPropertyValue('--color-danger').trim()")
    def rgb(hex_or_rgb):
        s = hex_or_rgb.strip()
        if s.startswith("#"):
            return tuple(int(s[i:i + 2], 16) for i in (1, 3, 5))
        return tuple(int(v) for v in s[s.index("(") + 1:s.index(")")].split(",")[:3])
    check("Unload icon is the warning-red token, unhovered", rgb(icon_color) == rgb(danger),
          f"icon {icon_color} vs --color-danger {danger}")

    # ---- unload ----
    errs.clear()
    pg.click(f"{V} .viewer-unload-btn"); pg.wait_for_timeout(1200)
    check("placeholder is back with its example models",
          pg.locator(f"{V} .viewer-empty-placeholder").count() == 1
          and pg.locator(f"{V} .viewer-empty-example-item").count() > 0)
    check("model-name label removed", pg.locator(f"{V} .ifc-name-label").count() == 0)
    check("intent panel emptied", pg.locator(f"{V} .intent-row").count() == 0)
    check("filter panel emptied", pg.locator(f"{V} .viewer-filter-panel-inner").count() == 0)
    check("camera panel emptied", pg.locator(f"{V} .viewer-fit-max-btn").count() == 0)
    check("panels closed", pg.evaluate(f"() => {{ const c=document.querySelector('{V}'); return !['filters-open','camera-open','intent-open','shortcuts-open'].some(k=>c.classList.contains(k)); }}"))
    check(".has-model cleared, Unload still shown (and now inert)",
          pg.locator(f"{V}.has-model").count() == 0 and pg.locator(f"{V} .viewer-unload-btn").is_visible())
    check("the viewer itself is still open", pg.locator(".viewer-container").count() == 1 and pg.locator(f"{V} canvas").count() >= 1)
    check("no console or page errors while unloading", not errs, "; ".join(errs[:2]))

    # ---- the classifier is pruned, not just re-populated (2026-09-24) ----
    # Until that day the reload below was the only evidence here, and it could
    # not see the bug: it reloads the SAME model, so a leaked group carries a
    # name the new model also has and the count is unchanged either way.
    # @thatopen's disposal empties a group's fragment map and then fails to
    # delete the group (it tests `Object.values(group).length === 0` on a
    # `{map, id, name}` object), so classifier.list used to be the union of
    # every model the tile had held. unloadModelFromViewer prunes it now.
    # Read through the live-state hook, since classifier.list has no DOM.
    lists = pg.evaluate(CLASSIFIER_JS, V)
    check("after unload the classifier holds no leftover groups",
          lists["storeys"] == [] and lists["entities"] == [],
          f"storeys={lists['storeys'][:4]} entities={lists['entities'][:4]}")

    # ---- reload into the same tile: the model comes back intact ----
    errs.clear()
    pg.click(f'{V} .viewer-empty-example-item[data-file-name="example_autcon.ifc"]')
    pg.wait_for_selector(f"{V} .intent-row", timeout=180000, state="attached")
    pg.wait_for_load_state("networkidle"); pg.wait_for_timeout(1000)
    rows_after = pg.locator(f"{V} .intent-row").count()
    filters_after = pg.locator(f"{V} .viewer-filter-section bim-checkbox").count()
    check("same model reloads into the same tile", rows_after == rows_before > 0, f"{rows_before} -> {rows_after} rows")
    check("no duplicated floors/categories after the round trip", filters_after == filters_before > 0,
          f"{filters_before} -> {filters_after} floor/category checkboxes")
    check("no console or page errors while reloading", not errs, "; ".join(errs[:2]))


    # ---- streamed model: a different disposal path (disposeStreamedGroup) ----
    if not skip_streamed("unloading a streamed model (disposeStreamedGroup)"):
        pg.click("#add-viewer-btn"); pg.wait_for_selector(f"{V2} .viewer-empty-example-item", timeout=15000)
        pg.click(f'{V2} .viewer-empty-example-item[data-file-name="{STREAMED_MODEL}"]')
        pg.wait_for_selector(f"{V2} .intent-row", timeout=180000, state="attached")
        pg.wait_for_load_state("networkidle"); pg.wait_for_timeout(1500)
        errs.clear()
        pg.click(f"{V2} .viewer-unload-btn"); pg.wait_for_timeout(1500)
        check("streamed model unloads too", pg.locator(f"{V2} .viewer-empty-placeholder").count() == 1
              and pg.locator(f"{V2} .intent-row").count() == 0 and pg.locator(f"{V2}.has-model").count() == 0)
        shader = [e for e in errs if "shader" in e.lower() or "GL_INVALID" in e]
        # Known library defect, first seen 2026-09-24 when this section stopped
        # skipping: disposing a STREAMED group races IfcStreamer's own culler
        # pass. unloadLostGeometries() throws "Fragment group not found!" for a
        # group that disposeGroup has already removed (components-front
        # index.js:27208), where the sibling loader path two methods above it
        # returns quietly for exactly the same condition (:27157). The OPFS
        # variant surfaces as a NotFoundError instead, depending on which part
        # of the teardown wins. The unload itself completes - every structural
        # check above this one passes - so this is enumerated rather than
        # failed, and anything NOT on the list still fails.
        # Matched by FAMILY, not by exact string. The race has shown at least
        # three faces across runs - the thrown "Fragment group not found!", a
        # NotFoundError from the OPFS side, and a NoModificationAllowedError
        # from `removeEntry` on a directory handle - because which part of the
        # teardown loses is timing-dependent. Enumerating literals meant a new
        # face read as a regression; this matches the two sources instead.
        teardown = [e for e in errs
                    if "Fragment group not found" in e
                    or "FileSystemDirectoryHandle" in e
                    or "could not be found at the time an operation was processed" in e]
        unexpected = [e for e in errs if e not in shader and e not in teardown]
        check("no unexpected console or page errors while unloading a streamed model",
              not unexpected,
              f"unexpected={len(unexpected)} streamer-teardown(known)={len(teardown)} shader(known F12)={len(shader)}"
              + (f" | {unexpected[:2]}" if unexpected else ""))
        check("the first viewer was untouched", pg.locator(f"{V}.has-model").count() == 1 and pg.locator(f"{V} .intent-row").count() == rows_before)

    # ---- a DIFFERENT model into the same tile: the symptom the prune fixes.
    # The reused tile's storeys must equal a fresh tile's for the same file -
    # the comparison the same-model reload above cannot make.
    #
    # Needs TWO distinct fixtures and `data/` has held exactly one since
    # 2026-09-24, so this skips unless a second example model is present. It
    # is the only check in this file that can see the classifier leak; the
    # prune itself is still covered by "after unload the classifier holds no
    # leftover groups" above, which needs just one model.
    others = [el.get_attribute("data-file-name")
              for el in pg.locator(f"{V} .viewer-empty-example-item").all()]
    second = next((n for n in others if n and n != "example_autcon.ifc"), None)
    if second is None:
        print("  [SKIP] a reused tile reports the same storeys as a fresh one"
              " - needs a second example model in data/")
        print(f"\n{sum(res)}/{len(res)} checks passed"); b.close()
        sys.exit(0 if all(res) else 1)
    pg.click(f"{V} .viewer-unload-btn"); pg.wait_for_timeout(1200)
    pg.click(f'{V} .viewer-empty-example-item[data-file-name="{second}"]')
    pg.wait_for_selector(f"{V} .intent-row", timeout=180000, state="attached")
    pg.wait_for_load_state("networkidle"); pg.wait_for_timeout(1200)
    reused = pg.evaluate(CLASSIFIER_JS, V)
    pg.click("#add-viewer-btn"); pg.wait_for_selector(f"{V3} .viewer-empty-example-item", timeout=15000)
    pg.click(f'{V3} .viewer-empty-example-item[data-file-name="{second}"]')
    pg.wait_for_selector(f"{V3} .intent-row", timeout=180000, state="attached")
    pg.wait_for_load_state("networkidle"); pg.wait_for_timeout(1200)
    fresh = pg.evaluate(CLASSIFIER_JS, V3)
    check("a reused tile reports the same storeys as a fresh one",
          reused["storeys"] == fresh["storeys"] and reused["storeys"] != [],
          f"reused={reused['storeys']} fresh={fresh['storeys']}")
    check("and the same categories", reused["entities"] == fresh["entities"] and reused["entities"] != [],
          f"{len(reused['entities'])} vs {len(fresh['entities'])}")

    print(f"\n{sum(res)}/{len(res)} checks passed"); b.close()
sys.exit(0 if all(res) else 1)

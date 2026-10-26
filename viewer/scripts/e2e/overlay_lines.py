"""Lines in the scene: the Lines (test) button and the engine behind it.

Loads example_autcon.ifc, clicks `.viewer-lines-btn`, checks `data-overlay-lines`
against the scene group, the straightness of the alignment polylines, the room
outlines and footprints against the elements' boxes, the
authored sidecar, the toggle off, then drives the module API directly
(views/lines.js through the dev server, the way views.py imports modules): raw
scene and ifcPlan segments, every shape kind, the change event, an anchor
without geometry, a malformed spec, and the Unload clear. Writes nothing; no
verdicts.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import BASE_URL, CHROMIUM_ARGS, OUT
from playwright.sync_api import sync_playwright

V = "#viewerContainer1"
B = f"{V} .viewer-lines-btn"
res = []
def check(n, ok, d=""):
    res.append(ok); print(f"  [{'PASS' if ok else 'FAIL'}] {n}" + (f" - {d}" if d else ""))

MODS = """
  const pick = (re, fallback) => performance.getEntriesByType('resource').map(e => e.name).filter(n => re.test(n)).pop() || fallback;
  const { viewerData } = await import(pick(/\\/viewerRegistry\\.js(\\?|$)/, '/viewerRegistry.js'));
  const lines = await import(pick(/\\/views\\/lines\\.js(\\?|$)/, '/views/lines.js'));
  const cv = await import(pick(/\\/cameraViews\\.js(\\?|$)/, '/cameraViews.js'));
  const v = viewerData[0]; const world = v.world; const model = v.getCurrentModel?.() ?? null;
  const boxOf = async (guid) => { const b = await cv.computeGuidsBoundingBox(world.components, model, [guid]); return b ? { min: [b.min.x, b.min.y, b.min.z], max: [b.max.x, b.max.y, b.max.z] } : null; };
  const group = () => world.scene.three.getObjectByName(lines.LINES_GROUP_NAME) || null;
"""
SCENE_JS = "async () => {" + MODS + """
  const g = group();
  const kids = g ? g.children : [];
  return { present: !!g, children: kids.length, allLines: kids.every(o => (o.isLine && o.geometry.attributes.position.count >= 2) || (o.isLine2 && o.geometry.attributes.instanceStart.count >= 1)),
           fat: kids.filter(o => o.isLine2).length, fatResolutionOk: kids.filter(o => o.isLine2).every(o => { const s = world.renderer.three.getSize(o.material.resolution.clone()); return o.material.resolution.x === s.x && o.material.resolution.y === s.y; }),
           dashed: kids.filter(o => o.isLine2 && o.material.dashed).length,
           listed: lines.listLines(world).map(l => ({ id: l.id, kind: l.spec.kind, type: l.spec.meta.type, shape: l.spec.meta.shape ?? null, source: l.spec.meta.source ?? null, sortAlong: l.spec.sortAlong, guid: l.spec.kind === 'outline' ? l.spec.points[0].guid : (l.spec.height?.guid ?? null), points: l.points, polylines: l.polylines })) };
}"""

with sync_playwright() as p:
    b = p.chromium.launch(args=CHROMIUM_ARGS)
    pg = b.new_page(viewport={"width": 1400, "height": 900})
    errs = []; pg.on("pageerror", lambda e: errs.append(str(e))); pg.on("console", lambda m: m.type == "error" and errs.append(m.text))
    pg.goto(BASE_URL, wait_until="networkidle")

    # ---- before a model: present, inert ----
    check("button present on an empty tile, not pressed, no count attribute",
          pg.locator(B).count() == 1 and pg.locator(B).get_attribute("aria-pressed") == "false"
          and pg.locator(V).get_attribute("data-overlay-lines") is None)
    pg.click(B); pg.wait_for_timeout(300)
    check("a click with no model does nothing", pg.locator(V).get_attribute("data-overlay-lines") is None and pg.evaluate(SCENE_JS)["present"] is False)

    pg.click("#example-models-btn")
    pg.wait_for_selector('#example-models-flyout .example-models-item[data-file-name="example_autcon.ifc"]', timeout=20000)
    pg.click('#example-models-flyout .example-models-item[data-file-name="example_autcon.ifc"]')
    pg.wait_for_selector(f"{V} .intent-row", timeout=180000, state="attached")
    pg.wait_for_load_state("networkidle"); pg.wait_for_timeout(800)
    expected = pg.evaluate("async () => {" + MODS + """
      const il = await import(pick(/\\/views\\/intentLines\\.js(\\?|$)/, '/views/intentLines.js'));
      const sc = await import(pick(/\\/views\\/lineSidecar\\.js(\\?|$)/, '/views/lineSidecar.js'));
      const vm = await import(pick(/\\/viewerModel\\.js(\\?|$)/, '/viewerModel.js'));
      const ctx = vm.getModelContext(model);
      const demo = il.demoLineSpecs(ctx?.intents ?? []); const side = await sc.loadLineSidecar(ctx?.key);
      const t0 = performance.now(); await lines.addLines(world, demo, { model }); const ms = Math.round(performance.now() - t0);
      const outlines = lines.listLines(world).filter(l => l.spec.kind === 'outline').length; lines.clearLines(world);
      return { demo: demo.length, sidecar: side.length, ms, outlines };
    }""")
    print(f"  demo set {expected['demo']} specs ({expected['outlines']} room outlines resolved) + sidecar {expected['sidecar']}: addLines took {expected['ms']} ms")
    expected = expected["demo"] + expected["sidecar"]

    # ---- the button ----
    pg.click(B)
    pg.wait_for_function(f"() => {{ const b = document.querySelector('{B}'); return b && !b.hasAttribute('aria-busy') && +document.querySelector('{V}').dataset.overlayLines > 0; }}", timeout=60000)
    count = int(pg.locator(V).get_attribute("data-overlay-lines"))
    scene = pg.evaluate(SCENE_JS)
    check("click draws the demo set: count attribute > 0 and equals the scene group's children",
          count > 0 and scene["present"] and scene["children"] == count, f"{count} lines; {expected} demo specs")
    check("every child is a THREE.Line with at least two points, or a fat Line2 with at least one segment", scene["allLines"])
    check("fat lines (style.width above 1) are Line2 objects whose material resolution is the canvas size", scene["fat"] > 0 and scene["fatResolutionOk"], f"{scene['fat']} fat, {scene['dashed']} dashed")
    check("the button reads pressed", pg.locator(B).get_attribute("aria-pressed") == "true")
    check("no more lines than demo specs (anchors without geometry are skipped, never invented)", count <= expected, f"{count} <= {expected}")
    align = [l for l in scene["listed"] if l["sortAlong"] in ("x", "z") and l["type"] and l["type"].startswith(("alignment", "grid_line"))]
    k = {"x": 0, "z": 2}
    # An X alignment runs along scene z: its points share one x (within the detector's tolerance plus box-centre noise); sorted along z; extended past the members.
    spreads = [max(pt[2 - k[l["sortAlong"]]] for pt in l["points"]) - min(pt[2 - k[l["sortAlong"]]] for pt in l["points"]) for l in align]
    ordered = all(all(l["points"][i][k[l["sortAlong"]]] <= l["points"][i + 1][k[l["sortAlong"]]] for i in range(len(l["points"]) - 1)) for l in align)
    check("alignment polylines are straight: across-line spread within 0.10 m", bool(align) and max(spreads) <= 0.10, f"{len(align)} lines, max spread {max(spreads) if spreads else 0:.3f} m")
    check("alignment polylines are sorted along their axis", ordered)
    yspread = [max(pt[1] for pt in l["points"]) - min(pt[1] for pt in l["points"]) for l in align]
    check("alignment polylines are flat: vertical spread within 0.05 m (multi-storey grid lines flattened to the lowest foot)",
          bool(align) and max(yspread) <= 0.05, f"max vertical spread {max(yspread) if yspread else 0:.3f} m")
    stacks = [l for l in scene["listed"] if l["sortAlong"] == "y"]
    check("stack polylines climb: y strictly non-decreasing", bool(stacks) and all(all(l["points"][i][1] <= l["points"][i + 1][1] for i in range(len(l["points"]) - 1)) for l in stacks), f"{len(stacks)} stacks")
    # ---- shapes from the records ----
    outlines = [l for l in scene["listed"] if l["kind"] == "outline"]
    closed = all(all(pl[0] == pl[-1] and len(pl) >= 4 for pl in l["polylines"]) for l in outlines)
    check("room outlines drawn: each loop closed with at least three corners", bool(outlines) and closed, f"{len(outlines)} rooms, corners {sorted(len(l['points']) - 1 for l in outlines)}")
    irregular = [l for l in outlines if len(l["points"]) - 1 > 4]
    check("at least one room is not a rectangle (irregular shape read from geometry)", len(irregular) >= 1, f"{len(irregular)} with more than four corners")
    boxes = pg.evaluate("async (guids) => {" + MODS + """ const out = {}; for (const g of guids) out[g] = await boxOf(g); return out; }""", [l["guid"] for l in outlines])
    def extent_ok(l):
        b = boxes.get(l["guid"]);
        if not b: return False
        xs = [p[0] for p in l["points"]]; zs = [p[2] for p in l["points"]]; ys = [p[1] for p in l["points"]]
        return abs(min(xs) - b["min"][0]) <= 0.05 and abs(max(xs) - b["max"][0]) <= 0.05 and abs(min(zs) - b["min"][2]) <= 0.05 and abs(max(zs) - b["max"][2]) <= 0.05 and all(abs(y - b["min"][1]) <= 0.05 for y in ys)
    check("every outline lies at its room's floor and spans its room's box in plan (BoundingBoxer as the oracle)", bool(outlines) and all(extent_ok(l) for l in outlines))
    footprints = [l for l in scene["listed"] if l["shape"] == "footprint"]
    check("footprint rectangles drawn: five points, closed, flat on the first member's floor",
          bool(footprints) and all(len(l["points"]) == 5 and l["points"][0] == l["points"][-1] and len({p[1] for p in l["points"]}) == 1 for l in footprints), f"{len(footprints)} footprints")
    sidecar = [l for l in scene["listed"] if l["source"] == "sidecar"]
    check("the authored sidecar is drawn with the demo set: one of each shape kind", sorted(l["kind"] for l in sidecar) == ["arc", "circle", "outline", "polygon", "spline"], f"{[l['kind'] for l in sidecar]}")
    # ---- Refer-linked lines: with the button on, a Refer draws the referred record's line ----
    def refer(intent_id):
        pg.evaluate("(id) => { const row = document.querySelector(`#viewerContainer1 .intent-row[data-intent-id=\"${id}\"]`); const d = row?.closest('details'); if (d) d.open = true; row?.scrollIntoView({ block: 'center' }); }", intent_id)
        pg.click(f'{V} .intent-row[data-intent-id="{intent_id}"] .intent-refer-btn')
        pg.wait_for_selector(f'{V} .intent-row[data-intent-id="{intent_id}"][data-refer-status="done"]', timeout=60000); pg.wait_for_timeout(400)
    ids = pg.evaluate("async () => {" + MODS + """ const vm = await import(pick(/\\/viewerModel\\.js(\\?|$)/, '/viewerModel.js')); const its = vm.getModelContext(model)?.intents ?? [];
      return { align: its.find(i => i.type === 'alignment_column_group' || i.type === 'grid_line_consistency')?.id, stack: its.find(i => i.type === 'structural_column_support')?.id }; }""")
    refer_list = lambda: pg.evaluate("async () => {" + MODS + """ return lines.listLines(world).filter(l => l.id.startsWith('refer:')).map(l => ({ id: l.id, intentId: l.spec.meta.intentId, width: l.spec.style.width })); }""")
    refer(ids["align"]); r1 = refer_list()
    check("Refer on an alignment row draws its line under refer: with the record's id, 3 px", len(r1) >= 1 and all(l["intentId"] == ids["align"] and l["width"] == 3 for l in r1), f"{[l['id'] for l in r1]}")
    refer(ids["stack"]); r2 = refer_list()
    check("Refer on a stack row replaces it: the alignment's line is gone, the stack's present", len(r2) >= 1 and all(l["intentId"] == ids["stack"] for l in r2), f"{[l['id'] for l in r2]}")
    pg.click(f"{V} .intent-clear-btn"); pg.wait_for_timeout(500)
    check("Clear selection removes the Refer-linked line and the count is back to the button's set", refer_list() == [] and int(pg.locator(V).get_attribute("data-overlay-lines")) == count)
    check("the button still reads pressed: its own lines are there", pg.locator(B).get_attribute("aria-pressed") == "true")

    # ---- an override (ID) pass never contains the lines; offscreen renders keep the fat-line resolution ----
    idpass = pg.evaluate("async () => {" + MODS + """
      const THREE = await import(pick(/\\/deps\\/three\\.js(\\?|$)/, '/node_modules/.vite/deps/three.js'));
      const render = await import(pick(/\\/views\\/render\\.js(\\?|$)/, '/views/render.js'));
      const override = new THREE.MeshBasicMaterial({ color: 0xffffff, toneMapped: false });
      const opts = { width: 320, height: 240, linear: true, background: null, overrideMaterial: override };
      const a = render.renderOffscreen(world, opts).pixels;
      const g = group(); g.visible = false; const b = render.renderOffscreen(world, opts).pixels; g.visible = true;
      let diff = 0; for (let i = 0; i < a.length; i++) if (a[i] !== b[i]) diff++;
      const plain = render.renderOffscreen(world, { width: 320, height: 240 });
      const fat = g.children.find(o => o.isLine2); const size = world.renderer.three.getSize(new THREE.Vector2());
      return { diff, total: a.length, restored: fat ? fat.material.resolution.x === size.x && fat.material.resolution.y === size.y : null, plainBytes: plain.pixels.length, groupVisible: g.visible };
    }""")
    check("an override (ID) pass renders the same with or without the lines: they are hidden for it", idpass["diff"] == 0, f"{idpass['diff']} of {idpass['total']} bytes differ")
    check("an offscreen render leaves the fat-line resolution at the canvas size and the group visible", idpass["restored"] is True and idpass["plainBytes"] == 320 * 240 * 4 and idpass["groupVisible"])

    # ---- picking: hovering names a drawn line, clicking announces it ----
    pos = pg.evaluate("async () => {" + MODS + """
      const THREE = await import(pick(/\\/deps\\/three\\.js(\\?|$)/, '/node_modules/.vite/deps/three.js'));
      const l = lines.listLines(world).find(x => x.id === 'sidecar:circle-foot'); if (!l) return null;
      world.camera.three.updateMatrixWorld(true);
      const rect = world.renderer.three.domElement.getBoundingClientRect();
      for (const p of l.points) { const v = new THREE.Vector3(...p).project(world.camera.three); if (Math.abs(v.x) < 0.95 && Math.abs(v.y) < 0.95)
        return { x: rect.left + (v.x + 1) / 2 * rect.width, y: rect.top + (1 - v.y) / 2 * rect.height, rect: { x: rect.left, y: rect.top, w: rect.width, h: rect.height } }; }
      return null;
    }""")
    if pos:
        pg.mouse.move(pos["x"], pos["y"]); pg.wait_for_timeout(300)
        tip = pg.locator(f"{V} .viewer-line-tooltip")
        check("hovering the sidecar circle shows its label in the tooltip", tip.evaluate("el => el.classList.contains('is-visible')") and "Circle" in tip.inner_text(), tip.inner_text())
        pg.evaluate("() => { window.__lineSelected = []; document.querySelector('#viewerContainer1').addEventListener('line-selected', e => window.__lineSelected.push(e.detail.id)); }")
        pg.mouse.click(pos["x"], pos["y"]); pg.wait_for_timeout(500)
        check("clicking it announces line-selected with its id", pg.evaluate("() => window.__lineSelected") == ["sidecar:circle-foot"])
        if pg.locator(".inspector-close").count(): pg.click(".inspector-close"); pg.wait_for_timeout(200)
        pg.mouse.move(pos["rect"]["x"] + 4, pos["rect"]["y"] + pos["rect"]["h"] - 4); pg.wait_for_timeout(300)
        check("moving off the line hides the tooltip", not tip.evaluate("el => el.classList.contains('is-visible')"))
    else:
        check("a point of the sidecar circle is on screen to hover", False)
    pg.screenshot(path=os.path.join(OUT, "overlay_lines.png"))

    pg.click(B); pg.wait_for_timeout(300)
    scene2 = pg.evaluate(SCENE_JS)
    check("second click clears: count 0, group removed, button not pressed",
          pg.locator(V).get_attribute("data-overlay-lines") == "0" and scene2["present"] is False and pg.locator(B).get_attribute("aria-pressed") == "false")
    refer(ids["align"])
    check("with the button off a Refer draws nothing: label-free views stay label-free", refer_list() == [] and pg.locator(V).get_attribute("data-overlay-lines") == "0")
    pg.click(f"{V} .intent-clear-btn"); pg.wait_for_timeout(400)

    # ---- the module API: raw coordinates, the event, errors ----
    api = pg.evaluate("async () => {" + MODS + """
      const container = document.querySelector('#viewerContainer1');
      const events = []; const onChange = (e) => events.push(e.detail); container.addEventListener('overlay-lines-changed', onChange);
      const r1 = await lines.addLines(world, [
        { id: 't-scene', points: [[0, 0, 0], [5, 0, 0]] },
        { id: 't-plan', space: 'ifcPlan', height: 0, points: [[39.179, 43.365], [39.179, 50]], extend: 0 },
      ]);
      const listed = lines.listLines(world);
      const plan = listed.find(l => l.id === 't-plan');
      const r2 = await lines.addLines(world, [{ id: 't-bad', points: [{ guid: 'no-such-guid-1' }, { guid: 'no-such-guid-2' }] }]);
      let thrown = null; try { await lines.addLines(world, [{ id: 't-short', points: [[0, 0, 0]] }]); } catch (e) { thrown = e.message; }
      const removed = lines.removeLines(world, ['t-scene', 'never-there']);
      const afterRemove = container.dataset.overlayLines;
      const cleared = lines.clearLines(world);
      container.removeEventListener('overlay-lines-changed', onChange);
      return { r1, r2, thrown, removed, afterRemove, cleared, listed: listed.map(l => l.id), planFirst: plan ? plan.points[0] : null,
               events: events.map(e => ({ count: e.count, added: e.added, removed: e.removed, skipped: e.skipped.length })), groupAfter: !!group(), attr: container.dataset.overlayLines };
    }""")
    check("addLines with raw scene and ifcPlan coordinates draws both", api["r1"]["added"] == ["t-scene", "t-plan"] and api["listed"] == ["t-scene", "t-plan"])
    pf = api["planFirst"] or [0, 0, 0]
    check("ifcPlan converts with the measured formula (x + T.x, height, -y + T.z)", abs(pf[0] - 9.913) < 0.002 and pf[1] == 0 and abs(pf[2] + 5.384) < 0.002, f"{[round(c, 3) for c in pf]}")
    check("overlay-lines-changed fires with {count, added, removed, skipped}",
          len(api["events"]) >= 4 and api["events"][0] == {"count": 2, "added": ["t-scene", "t-plan"], "removed": [], "skipped": 0})
    check("an anchor without geometry is skipped, not drawn and not thrown", api["r2"]["added"] == [] and len(api["r2"]["skipped"]) == 1 and api["events"][1]["skipped"] == 1)
    check("a malformed spec throws from normalisation", api["thrown"] is not None and "needs an explicit kind" in api["thrown"], api["thrown"])
    check("removeLines removes known ids only and updates the count", api["removed"] == ["t-scene"] and api["afterRemove"] == "1")
    check("clearLines empties the registry and removes the group", api["cleared"] == 1 and api["groupAfter"] is False and api["attr"] == "0")

    # ---- the shape kinds through the API, on real anchors ----
    shapes = pg.evaluate("async () => {" + MODS + """
      const vm = await import(pick(/\\/viewerModel\\.js(\\?|$)/, '/viewerModel.js'));
      const intents = vm.getModelContext(model)?.intents ?? [];
      const stack = intents.find(i => i.type === 'structural_column_support' && i.members.length >= 3);
      const guids = stack.members.map(m => m.guid);
      const r = await lines.addLines(world, [
        { id: 's-circle', kind: 'circle', radius: 2, segments: 16, points: [{ guid: guids[0], at: 'bottom' }] },
        { id: 's-arc', kind: 'arc', radius: 2, startDeg: 0, endDeg: 90, segments: 4, points: [{ guid: guids[0], at: 'bottom' }] },
        { id: 's-spline', kind: 'spline', samples: 5, points: guids.map(g => ({ guid: g, at: 'center' })) },
        { id: 's-polygon', kind: 'polygon', points: [[0, 0, 0], [3, 0, 0], [3, 0, 2], [1, 0, 3]] },
      ], { model });
      const foot = await boxOf(guids[0]); const centres = []; for (const g of guids) { const b = await boxOf(g); centres.push([(b.min[0] + b.max[0]) / 2, (b.min[1] + b.max[1]) / 2, (b.min[2] + b.max[2]) / 2]); }
      const L = Object.fromEntries(lines.listLines(world).map(l => [l.id, l.points]));
      lines.clearLines(world);
      return { added: r.added, skipped: r.skipped, L, foot, centres };
    }""")
    L = shapes["L"]; fx, fy, fz = [(shapes["foot"]["min"][i] + shapes["foot"]["max"][i]) / 2 for i in range(3)]; fy = shapes["foot"]["min"][1]
    circ = L.get("s-circle", [])
    check("circle on a column foot: 17 points, all 2 m from the foot's centre, flat at the foot", len(circ) == 17 and all(abs(((p[0] - fx) ** 2 + (p[2] - fz) ** 2) ** 0.5 - 2) < 1e-6 and abs(p[1] - fy) < 1e-9 for p in circ) and circ[0] == circ[-1], f"{len(circ)} points; first {[round(c, 3) for c in circ[:1][0]] if circ else None}, foot ({fx:.3f}, {fy:.3f}, {fz:.3f})")
    arc = L.get("s-arc", [])
    check("arc 0..90 degrees: starts at +x, ends at +z of the centre", len(arc) == 5 and abs(arc[0][0] - (fx + 2)) < 1e-6 and abs(arc[-1][2] - (fz + 2)) < 1e-6 and abs(arc[-1][0] - fx) < 1e-6)
    sp = L.get("s-spline", [])
    through = all(any(all(abs(p[k] - c[k]) < 1e-6 for k in range(3)) for p in sp) for c in shapes["centres"])
    check("spline through a column stack passes through every member centre", len(sp) == 5 * (len(shapes["centres"]) - 1) + 1 and through, f"{len(sp)} points, {len(shapes['centres'])} centres")
    poly = L.get("s-polygon", [])
    check("raw polygon closes itself", len(poly) == 5 and poly[0] == poly[-1])

    # ---- Unload clears whatever is drawn ----
    pg.click(B)
    pg.wait_for_function(f"() => +document.querySelector('{V}').dataset.overlayLines > 0 && !document.querySelector('{B}').hasAttribute('aria-busy')", timeout=60000)
    pg.click(f"{V} .viewer-unload-btn"); pg.wait_for_timeout(800)
    scene3 = pg.evaluate(SCENE_JS)
    check("Unload clears the lines: count 0, group gone, button not pressed",
          pg.locator(V).get_attribute("data-overlay-lines") == "0" and scene3["present"] is False and pg.locator(B).get_attribute("aria-pressed") == "false")

    check("no console errors", len(errs) == 0, "; ".join(errs[:2]))
    print(f"\n{sum(res)}/{len(res)} checks passed")
    b.close()
    sys.exit(0 if all(res) else 1)

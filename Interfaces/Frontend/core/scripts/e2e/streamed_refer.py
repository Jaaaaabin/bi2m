"""Refer on a STREAMED model (works since 2026-10-21):
the scope box is measured from the tile set's own metadata (tileBounds.js)
with no geometry in the scene, the camera moves, the culler then fetches the
tiles under the new view, and the Refer is re-applied to the batches that
carry its members so they arrive coloured and ghosted.

Fixture: data/uploads/<key>/<key>.ifc opened through the upload button's file
chooser (a local open: nothing is uploaded, tiled or computed), for a key
whose tile set the running dev server serves (declared_grid.py uses the same
two). Skips, exit 0, when neither upload nor tile set is there. Read-only:
Refer, Clear and Unload only. Never Accept, Reject, Compute or Run.
"""
import os, re, sys, json, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import BASE_URL, CHROMIUM_ARGS
from playwright.sync_api import sync_playwright

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", ".."))
KEYS = os.environ.get("BI2M_E2E_STREAMED_KEYS", "c99be381a798220e,3ef234726d638702").split(",")
V = "#viewerContainer1"
# web-ifc never runs on a streamed model; the fragments OPFS cache logs
# removeEntry after 60 s.
KNOWN_CONSOLE = re.compile(r"removeEntry|Shader")
res = []
def check(n, ok, d=""):
    res.append((n, ok)); print(f"  [{'PASS' if ok else 'FAIL'}] {n}" + (f" - {d}" if d else ""))

MODS = """
  const pick = (re, fallback) => performance.getEntriesByType('resource').map(e => e.name)
    .filter(n => re.test(n)).pop() || fallback;
  const { viewerData } = await import(pick(/\\/viewerRegistry\\.js(\\?|$)/, '/viewerRegistry.js'));
  const cv = await import(pick(/\\/cameraViews\\.js(\\?|$)/, '/cameraViews.js'));
  const vm = await import(pick(/\\/viewerModel\\.js(\\?|$)/, '/viewerModel.js'));
  const tb = await import(pick(/\\/tileBounds\\.js(\\?|$)/, '/tileBounds.js'));
  const OBC = await import(pick(/@thatopen_components\\.js(\\?|$)/, '/node_modules/.vite/deps/@thatopen_components.js'));
  const THREE = await import(pick(/\\/deps\\/three\\.js(\\?|$)/, '/node_modules/.vite/deps/three.js'));
  const v = viewerData[0]; const world = v.world, c = world.camera.controls;
  const model = v.fragments.groups.values().next().value; const components = world.components;
  const ctx = model ? vm.getModelContext(model) : null;
  const settle = (ms) => new Promise(r => setTimeout(r, ms));
"""
LOADED_JS = "async () => {" + MODS + " return !!(v && v.hasModel && model); }"

def served(key):
    try:
        with urllib.request.urlopen(f"{BASE_URL}tiles/{key}/tileset.json", timeout=10) as r:
            return "json" in (r.headers.get("Content-Type") or "")
    except Exception:
        return False

fixture = next((k for k in KEYS if os.path.exists(os.path.join(REPO, "data", "uploads", k, f"{k}.ifc")) and served(k)), None)
if not fixture:
    print(f"  [SKIP] no streamed fixture: none of {KEYS} has both data/uploads/<key>/<key>.ifc and a tile set this dev server serves")
    print("\n0/0 checks passed"); sys.exit(0)
ifc = os.path.join(REPO, "data", "uploads", fixture, f"{fixture}.ifc")
print(f"fixture {fixture} ({os.path.getsize(ifc) // 1024} KB)")

with sync_playwright() as p:
    b = p.chromium.launch(args=CHROMIUM_ARGS)
    pg = b.new_page(viewport={"width": 1400, "height": 900})
    errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.on("console", lambda m: m.type == "error" and not KNOWN_CONSOLE.search(m.text) and errs.append(m.text))
    pg.goto(BASE_URL, wait_until="networkidle")
    with pg.expect_file_chooser() as chooser:
        pg.click("#bulk-upload-btn")
    chooser.value.set_files(ifc)
    pg.wait_for_function(LOADED_JS, timeout=300000, polling=500)
    pg.wait_for_selector(f"{V} .intent-row", timeout=120000, state="attached")
    pg.wait_for_load_state("networkidle"); pg.wait_for_timeout(1500)

    info = pg.evaluate("async () => {" + MODS + """
      const tiles = ctx.tileMetadata; const d = tiles?.descriptor;
      const whole = tiles ? tb.boxOfTileAssets([...tiles.assetsById.values()], tiles.geometries, model.matrixWorld) : null;
      const shipped = tiles ? tb.tileSetBoundingBox(d, 'worldBoundingBox', model.matrixWorld) : null;
      const building = cv.computeBuildingBoundingBox(components, v.classifier, model);
      const same = whole && shipped && whole.min.distanceTo(shipped.min) < 1e-6 && whole.max.distanceTo(shipped.max) < 1e-6;
      // the geometry actually in the scene must lie inside the metadata's world box
      const bb = components.get(OBC.BoundingBoxer); bb.reset(); bb.add(model); const resident = bb.get().clone(); bb.reset();
      const residentInside = whole && !resident.isEmpty() && whole.clone().expandByScalar(0.05).containsBox(resident);
      return { streamed: !!ctx.isStreamed, tiles: !!tiles, assets: tiles?.assetsById.size, guids: tiles ? Object.keys(tiles.guidSeed).length : 0,
               trusted: !!tiles?.trusted, convention: d?.boxConvention ?? null, same, residentInside,
               residentBox: [resident.min.toArray().map(x => +x.toFixed(2)), resident.max.toArray().map(x => +x.toFixed(2))],
               wholeBox: whole ? [whole.min.toArray().map(x => +x.toFixed(2)), whole.max.toArray().map(x => +x.toFixed(2))] : null,
               resident: v.fragments.list.size, manifest: Object.keys(model.getFragmentMap()).length, building: !!building,
               identity: model.matrixWorld.elements.every((e, i) => Math.abs(e - (i % 5 === 0 ? 1 : 0)) < 1e-12),
               rows: document.querySelectorAll('#viewerContainer1 .intent-row').length };
    }""")
    check("the upload streamed from its tile set and the model context carries the tile metadata", info["streamed"] and info["tiles"], json.dumps(info))
    if info["trusted"]:
        check("the metadata box over every asset equals the box tileIfc.mjs shipped in tileset.json (same code, tileBounds.js)", info["same"])
    else:
        print(f"  [NOTE] tile set predates the box fix (boxConvention {info['convention']}): the viewer recomputed its boxes from the metadata")
    check("the geometry resident in the scene lies inside the metadata's world box", info["residentInside"], f"resident {info['residentBox']} in {info['wholeBox']}")
    check("the building box is there before the tiles are (from the metadata, not the few resident fragments)", info["building"])
    check("the model group sits at identity (first model of its viewer)", info["identity"])

    # pick the first intent row whose members the tile set has geometry for
    pick = pg.evaluate("async () => {" + MODS + """
      const tiles = ctx.tileMetadata;
      for (const it of ctx.intents) {
        const guids = it.members.map(m => m.guid);
        const withGeometry = guids.filter(g => tiles.assetsById.has(tiles.guidSeed[g]));
        if (withGeometry.length >= 2 && withGeometry.length === guids.length) {
          const box = await cv.computeGuidsBoundingBox(components, model, guids);
          const fragMap = model.getFragmentMap(withGeometry.map(g => tiles.guidSeed[g]));
          const residentBefore = Object.keys(fragMap).filter(id => v.fragments.list.has(id)).length;
          return { id: it.id, label: it.label, members: guids.length, fragments: Object.keys(fragMap).length, residentBefore,
                   box: box ? { min: box.min.toArray(), max: box.max.toArray() } : null };
        }
      }
      return null;
    }""")
    check("an intent whose members all have tile geometry exists", bool(pick), json.dumps(pick)[:200])
    if pick:
        print(f"  intent {pick['label']} ({pick['members']} members, {pick['fragments']} fragments, {pick['residentBefore']} resident before Refer)")
        check("its scope box is measured from the metadata before any of its fragments is resident", pick["box"] is not None and pick["residentBefore"] < pick["fragments"],
              f"box {pick['box'] and [round(x, 2) for x in pick['box']['min']]}..{pick['box'] and [round(x, 2) for x in pick['box']['max']]}")
        before = pg.evaluate("async () => {" + MODS + " c.update(0); return { distance: c.distance, scope: !!v.cameraScope }; }")
        pg.evaluate("""(id) => {
          const row = document.querySelector(`#viewerContainer1 [data-intent-id="${id}"]`);
          for (let el = row; el; el = el.parentElement) if (el.tagName === 'DETAILS') el.open = true;
        }""", pick["id"])
        pg.click(f'{V} [data-intent-id="{pick["id"]}"] .intent-refer-btn')
        pg.wait_for_selector(f'{V} [data-intent-id="{pick["id"]}"][data-refer-status="done"]', timeout=60000)
        after = pg.evaluate("async () => {" + MODS + """
          c.update(0);
          return { distance: c.distance, scope: v.cameraScope ? { intentId: v.cameraScope.intentId, guids: v.cameraScope.guids.length, box: !!v.cameraScope.box } : null,
                   streamedRefer: v.streamedRefer ? v.streamedRefer.intent.id : null, contextRow: !!document.querySelector('#viewerContainer1 .camera-context-row, #viewerContainer1 [data-camera-context]') };
        }""")
        check("Refer set a camera scope for the intent (was silently null on a streamed model before)", after["scope"] and after["scope"]["intentId"] == pick["id"] and after["scope"]["box"], json.dumps(after["scope"]))
        check("  and moved the camera", abs(after["distance"] - before["distance"]) > 0.5, f"{before['distance']:.2f} -> {after['distance']:.2f} m")
        check("  and registered the Refer for the streamed-batch watch", after["streamedRefer"] == pick["id"], str(after["streamedRefer"]))
        # the culler now fetches the tiles under the new view; wait for the members' fragments to turn up
        pg.wait_for_function("async (id) => {" + MODS + """
          const tiles = ctx.tileMetadata; const it = ctx.intents.find(i => i.id === id);
          const fragMap = model.getFragmentMap(it.members.map(m => tiles.guidSeed[m.guid]).filter(x => x !== undefined));
          return Object.keys(fragMap).some(f => v.fragments.list.has(f));
        }""", arg=pick["id"], timeout=90000, polling=500)
        pg.wait_for_timeout(2500)  # a batch or two more, plus the re-apply
        r = pg.evaluate("async (id) => {" + MODS + """
          const tiles = ctx.tileMetadata; const it = ctx.intents.find(i => i.id === id); const guids = it.members.map(m => m.guid);
          const ids = guids.map(g => tiles.guidSeed[g]).filter(x => x !== undefined);
          const fragMap = model.getFragmentMap(ids);
          const resident = Object.keys(fragMap).filter(f => v.fragments.list.has(f));
          // the parsed path's measurement, over the fragments that are resident now
          const bb = components.get(OBC.BoundingBoxer); bb.reset();
          const residentMap = {}; for (const f of resident) residentMap[f] = fragMap[f];
          bb.addFragmentIdMap(residentMap); const measured = bb.get(); bb.reset();
          const meta = await cv.computeGuidsBoundingBox(components, model, guids);
          const splits = v.referSplits ? v.referSplits.length : 0;
          const splitFragments = v.referSplits ? v.referSplits.map(s => s.fragment.id) : [];
          const contained = !measured.isEmpty() && meta.containsBox(measured.clone().expandByScalar(-0.05));
          const metaSize = meta.getSize(new THREE.Vector3()).length(), measuredSize = measured.isEmpty() ? 0 : measured.getSize(new THREE.Vector3()).length();
          return { resident: resident.length, of: Object.keys(fragMap).length, splits, splitResident: splitFragments.filter(f => resident.includes(f)).length,
                   contained, metaSize, measuredSize, scope: v.cameraScope ? v.cameraScope.intentId : null };
        }""", pick["id"])
        print(f"  {r['resident']} of {r['of']} member fragments resident after the fit; {r['splits']} refer splits")
        check("the tiles under the new view were fetched (member fragments resident)", r["resident"] > 0, f"{r['resident']} of {r['of']}")
        check("the Refer was re-applied to the arriving batches: the resident member fragments are split out (coloured, opaque)", r["splits"] > 0 and r["splitResident"] == r["resident"], f"{r['splitResident']} split of {r['resident']} resident")
        # Refer lines (views/referLines.js) clear on the scope churn of a re-apply and must come back
        pg.click(f"{V} .viewer-lines-btn")
        pg.wait_for_function(f"() => {{ const b = document.querySelector('{V} .viewer-lines-btn'); return b && !b.hasAttribute('aria-busy'); }}", timeout=60000)
        pg.click(f'{V} [data-intent-id="{pick["id"]}"] .intent-refer-btn')
        pg.wait_for_selector(f'{V} [data-intent-id="{pick["id"]}"][data-refer-status="done"]', timeout=60000)
        pg.wait_for_timeout(1500)
        lines_before = pg.evaluate("async () => {" + MODS + " const ln = await import(pick(/\\/views\\/lines\\.js(\\?|$)/, '/views/lines.js')); return ln.listLines(world).filter(l => l.id.startsWith('refer:')).length; }")
        reapplied = pg.evaluate("async (id) => {" + MODS + """
          let n = 0; v.container.addEventListener('intent-refer-reapplied', () => n++);
          // pull the camera off and back so the culler fetches another batch under the view
          const p = c.getPosition(new THREE.Vector3()), t = c.getTarget(new THREE.Vector3());
          await c.setLookAt(p.x + 40, p.y + 30, p.z + 40, t.x, t.y, t.z, false); await settle(2500);
          await c.setLookAt(p.x, p.y, p.z, t.x, t.y, t.z, false); await settle(3500);
          const ln = await import(pick(/\\/views\\/lines\\.js(\\?|$)/, '/views/lines.js'));
          return { reapplies: n, lines: ln.listLines(world).filter(l => l.id.startsWith('refer:')).length };
        }""", pick["id"])
        check(f"with Lines on, the refer lines survive a streamed re-apply ({reapplied['reapplies']} re-apply event(s) seen)",
              reapplied["lines"] == lines_before, f"{reapplied['lines']} lines after, {lines_before} before")
        pg.click(f"{V} .viewer-lines-btn"); pg.wait_for_timeout(500)
        # the filter panel's GUID section joins the queue and drops the streamed registration
        gsec = pg.evaluate("async () => {" + MODS + """
          const btn = document.querySelector('#viewerContainer1 .viewer-guid-clear-btn'); if (!btn) return null;
          btn.click(); await settle(800);
          return { streamedRefer: v.streamedRefer, scope: v.cameraScope };
        }""")
        if gsec is None:
            print("  [SKIP] GUID section not found in the filter panel")
        else:
            check("the filter panel's GUID Clear drops the streamed Refer registration and the scope", gsec == {"streamedRefer": None, "scope": None}, json.dumps(gsec)[:120])
            # back to A for the remaining checks
            pg.click(f'{V} [data-intent-id="{pick["id"]}"] .intent-refer-btn')
            pg.wait_for_selector(f'{V} [data-intent-id="{pick["id"]}"][data-refer-status="done"]', timeout=60000)
            pg.wait_for_timeout(1500)
        check("  and the camera scope survived the re-apply", r["scope"] == pick["id"], str(r["scope"]))
        check("the metadata box contains the parsed-path measurement of the resident fragments (eight corners vs BoundingBoxer's min/max)", r["contained"], f"meta diag {r['metaSize']:.2f} m, measured {r['measuredSize']:.2f} m")
        check("  and is not inflated: within 25 % of it on the diagonal", r["measuredSize"] > 0 and r["metaSize"] <= r["measuredSize"] * 1.25 + 0.5, f"{r['metaSize']:.2f} vs {r['measuredSize']:.2f}")

        # A second Refer straight after the first, while that one's batches may
        # still be landing: the viewer's work queue must leave B on screen.
        other = pg.evaluate("async (id) => {" + MODS + """
          const tiles = ctx.tileMetadata;
          for (const it of ctx.intents) {
            if (it.id === id) continue;
            const guids = it.members.map(m => m.guid);
            if (guids.length >= 2 && guids.every(g => tiles.assetsById.has(tiles.guidSeed[g]))) return { id: it.id, label: it.label, members: guids.length };
          }
          return null;
        }""", pick["id"])
        if other:
            pg.evaluate("""(id) => {
              const row = document.querySelector(`#viewerContainer1 [data-intent-id="${id}"]`);
              for (let el = row; el; el = el.parentElement) if (el.tagName === 'DETAILS') el.open = true;
            }""", other["id"])
            pg.click(f'{V} [data-intent-id="{pick["id"]}"] .intent-refer-btn')  # A again, so batches queue a re-apply of A ...
            pg.click(f'{V} [data-intent-id="{other["id"]}"] .intent-refer-btn')  # ... and B lands right behind it
            pg.wait_for_selector(f'{V} [data-intent-id="{other["id"]}"][data-refer-status="done"]', timeout=60000)
            pg.wait_for_timeout(4000)  # let the batches under B's view land and re-apply
            r = pg.evaluate("async (ids) => {" + MODS + """
              const tiles = ctx.tileMetadata; const [a, b] = ids;
              const members = (id) => new Set(ctx.intents.find(i => i.id === id).members.map(m => tiles.guidSeed[m.guid]));
              const bIds = members(b), aIds = members(a);
              const splitIds = new Set(); for (const s of v.referSplits ?? []) for (const i of s.itemIds) splitIds.add(i);
              const onlyA = [...aIds].filter(i => !bIds.has(i));
              return { streamedRefer: v.streamedRefer?.intent.id, scope: v.cameraScope?.intentId, splits: splitIds.size,
                       strayA: onlyA.filter(i => splitIds.has(i)).length, fromB: [...bIds].filter(i => splitIds.has(i)).length,
                       active: document.querySelector('#viewerContainer1 .intent-refer-btn.is-active')?.closest('[data-intent-id]')?.dataset.intentId };
            }""", [pick["id"], other["id"]])
            check(f"a second Refer ({other['label']}) right behind the first wins: scope, registration and the active row are B's",
                  r["streamedRefer"] == other["id"] and r["scope"] == other["id"] and r["active"] == other["id"], json.dumps(r))
            check("  and no fragment of A alone is left split out by a late re-apply", r["strayA"] == 0 and r["fromB"] > 0, json.dumps(r))
        else:
            print("  [SKIP] no second intent with full tile geometry - the queued second Refer is not exercised")

    pg.click(f"{V} .intent-clear-btn")
    pg.wait_for_timeout(2500)  # a batch landing after the Clear must not paint the Refer back
    r = pg.evaluate("async () => {" + MODS + " return { streamedRefer: v.streamedRefer, splits: v.referSplits, scope: v.cameraScope }; }")
    check("Clear drops the streamed Refer registration, the splits and the scope, and a later batch paints nothing back", r == {"streamedRefer": None, "splits": None, "scope": None}, json.dumps(r)[:120])
    check("no unexpected console or page errors", not errs, "; ".join(errs[:3]))
    bad = [n for n, ok in res if not ok]
    print(f"\n{len(res)-len(bad)}/{len(res)} checks passed" + (f"\nFAILED: {bad}" if bad else ""))
    b.close()
    sys.exit(1 if bad else 0)

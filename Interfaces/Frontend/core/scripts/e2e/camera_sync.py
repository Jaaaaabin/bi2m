"""Camera monitor (cameraMonitor.js, 2026-10-21): frustum culling that follows
the CURRENT camera and settles exactly on rest/sleep, and the cross-viewer
sync that mirrors position, target, projection and orthographic scale onto
the other viewers without ever echoing a received pose back.

Read-only: loads example_autcon.ifc into two viewers, moves cameras, toggles
Sync cameras and the projection. Never Accept, Reject, Compute or Run.
"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import BASE_URL, CHROMIUM_ARGS
from playwright.sync_api import sync_playwright

V1, V2 = "#viewerContainer1", ".viewer-container:nth-child(2)"
MODEL = "example_autcon.ifc"
res = []
def check(n, ok, d=""):
    res.append((n, ok)); print(f"  [{'PASS' if ok else 'FAIL'}] {n}" + (f" - {d}" if d else ""))

MODS = """
  const pick = (re, fallback) => performance.getEntriesByType('resource').map(e => e.name)
    .filter(n => re.test(n)).pop() || fallback;
  const { viewerData } = await import(pick(/\\/viewerRegistry\\.js(\\?|$)/, '/viewerRegistry.js'));
  const cv = await import(pick(/\\/cameraViews\\.js(\\?|$)/, '/cameraViews.js'));
  const cm = await import(pick(/\\/cameraMonitor\\.js(\\?|$)/, '/cameraMonitor.js'));
  const THREE = await import(pick(/\\/deps\\/three\\.js(\\?|$)/, '/node_modules/.vite/deps/three.js'));
  const [a, b] = viewerData; const ca = a.world.camera.controls, cb = b ? b.world.camera.controls : null;
  const frames = (n) => new Promise(r => { let k = 0; const step = () => (++k >= n ? r() : requestAnimationFrame(step)); requestAnimationFrame(step); });
  const settle = (ms) => new Promise(r => setTimeout(r, ms));
  // Under SwiftShader with other harnesses running, a frame can take longer
  // than any fixed settle: wait for the condition, up to a ceiling.
  const until = async (fn, ms = 8000) => { const t0 = performance.now(); while (!(await fn()) && performance.now() - t0 < ms) await new Promise(r => requestAnimationFrame(r)); return fn(); };
  const visibleCount = (entry) => { let n = 0; for (const g of entry.fragments.groups.values()) for (const f of g.items) if (f.mesh && f.mesh.visible) n++; return n; };
  const rested = (ctrl) => new Promise(r => { const done = () => { ctrl.removeEventListener('rest', done); ctrl.removeEventListener('sleep', done); r(); }; ctrl.addEventListener('rest', done); ctrl.addEventListener('sleep', done); });
"""

# Exact visibility, recomputed here from the same world-space boxes the
# monitor caches (full instance count), against what the loader left on
# `mesh.visible`.
CULL_JS = "async () => {" + MODS + """
  const meshes = []; for (const g of a.fragments.groups.values()) for (const f of g.items) if (f.mesh) meshes.push(f.mesh);
  const cam = a.world.camera.three; cam.updateMatrixWorld();
  const fr = new THREE.Frustum().setFromProjectionMatrix(new THREE.Matrix4().multiplyMatrices(cam.projectionMatrix, cam.matrixWorldInverse));
  let exact = 0, visible = 0, wrong = 0;
  for (const m of meshes) {
    const n = m.count; m.count = m.instanceMatrix.count; const box = new THREE.Box3().setFromObject(m); m.count = n;
    const inView = fr.intersectsBox(box); exact += inView; visible += m.visible; wrong += (inView !== m.visible);
  }
  return { total: meshes.length, exact, visible, wrong };
}"""

POSE_JS = "async (i) => {" + MODS + """
  const w = viewerData[i].world; const c = w.camera.controls; c.update(0);
  const p = c.getPosition(new THREE.Vector3(), false), t = c.getTarget(new THREE.Vector3(), false);
  return { position: [p.x, p.y, p.z], target: [t.x, t.y, t.z], projection: w.camera.projection.current,
           halfHeight: cm.readPose(w).halfHeight, distance: c.distance };
}"""

def load(pg, sel):
    pg.wait_for_selector(f"{sel} .viewer-empty-examples .viewer-empty-example-item", timeout=20000)
    pg.click(f'{sel} .viewer-empty-examples .viewer-empty-example-item[data-file-name="{MODEL}"]')
    pg.wait_for_selector(f"{sel} .intent-row", timeout=180000, state="attached")
    pg.wait_for_load_state("networkidle"); pg.wait_for_timeout(1500)

def close(p, q, tol=1e-6):
    return max(abs(x - y) for x, y in zip(p, q)) < tol

with sync_playwright() as p:
    b = p.chromium.launch(args=CHROMIUM_ARGS)
    pg = b.new_page(viewport={"width": 1400, "height": 900})
    errs = []; pg.on("pageerror", lambda e: errs.append(str(e))); pg.on("console", lambda m: m.type == "error" and errs.append(m.text))
    pg.goto(BASE_URL, wait_until="networkidle")
    load(pg, V1)

    print("\n=== Frustum culling follows the current camera ===")
    r0 = pg.evaluate(CULL_JS)
    check("the opening fit leaves every fragment visible and exact", r0["wrong"] == 0 and r0["visible"] == r0["total"], json.dumps(r0))
    r = pg.evaluate("async () => {" + MODS + """
      const d0 = ca.distance; const total = visibleCount(a);
      await ca.dollyTo(d0 * 0.08, false);                                     // instant close zoom: an exact pass hides most
      await until(() => visibleCount(a) < total); await settle(100);
      const closeState = await (""" + CULL_JS + """)();
      const r1 = rested(ca); await ca.dollyTo(d0, true); await r1; await settle(100);   // animated back out: the stale case before the fix
      const outState = await (""" + CULL_JS + """)();
      return { d0, closeState, outState };
    }""")
    check("an instant close zoom culls exactly (most fragments hidden)", r["closeState"]["wrong"] == 0 and r["closeState"]["visible"] < r["closeState"]["total"] * 0.6, json.dumps(r["closeState"]))
    check("after an ANIMATED zoom back out the settled view is exact again (was 1,923 of 2,425 visible, stale, before 2026-10-21)",
          r["outState"]["wrong"] == 0 and r["outState"]["visible"] == r["outState"]["total"], json.dumps(r["outState"]))
    r = pg.evaluate("async () => {" + MODS + """
      const box = cv.computeBuildingBoundingBox(a.world.components, a.classifier, a.fragments.groups.values().next().value);
      const ctr = box.getCenter(new THREE.Vector3()), size = box.getSize(new THREE.Vector3());
      // animated move to a corner inside the building's extent: the frustum changes shape every frame
      const r1 = rested(ca); await ca.setLookAt(ctr.x + size.x * 0.4, ctr.y + 2, ctr.z + size.z * 0.1, ctr.x, ctr.y, ctr.z, true); await r1; await settle(100);
      return await (""" + CULL_JS + """)();
    }""")
    check("after an animated move into the building the settled culling is exact", r["wrong"] == 0 and r["visible"] < r["total"], json.dumps(r))

    print("\n=== Cross-viewer sync ===")
    pg.click("#add-viewer-btn"); load(pg, V2)
    pg.evaluate("async () => {" + MODS + " await ca.setLookAt(60, 40, 60, 0, 5, 0, false); await settle(200); }")
    pa, pb = pg.evaluate(POSE_JS, 0), pg.evaluate(POSE_JS, 1)
    check("with sync off the second viewer keeps its own pose", not close(pa["position"], pb["position"], 1e-3))
    pg.click("#sync-cam-btn"); pg.wait_for_timeout(300)
    r = pg.evaluate("async () => {" + MODS + """
      // count every setLookAt that reaches the LEADER from now on: the only legitimate one is the test's own
      let leaderCalls = 0; const orig = ca.setLookAt.bind(ca); ca.setLookAt = (...args) => { leaderCalls++; return orig(...args); };
      let followerCalls = 0; const origB = cb.setLookAt.bind(cb); cb.setLookAt = (...args) => { followerCalls++; return origB(...args); };
      await ca.setLookAt(30, 25, 45, 2, 3, 4, false);
      await until(() => followerCalls >= 1); await settle(300);  // then a grace period for any echo to show up
      const out = { leaderCalls, followerCalls };
      ca.setLookAt = orig; cb.setLookAt = origB; return out;
    }""")
    pa, pb = pg.evaluate(POSE_JS, 0), pg.evaluate(POSE_JS, 1)
    check("an instant move on the leader lands on the follower exactly", close(pa["position"], pb["position"]) and close(pa["target"], pb["target"]),
          f"leader {[round(x, 3) for x in pa['position']]} follower {[round(x, 3) for x in pb['position']]}")
    check("  the follower received it once, and nothing came back to the leader (no echo)", r == {"leaderCalls": 1, "followerCalls": 1}, json.dumps(r))
    check("  the leader's pose is the one it was given", close(pa["position"], [30, 25, 45]) and close(pa["target"], [2, 3, 4]))
    pg.evaluate("async () => {" + MODS + " const r = rested(ca); await ca.setLookAt(10, 30, 70, -5, 2, 3, true); await r; await until(() => cb.getPosition(new THREE.Vector3(), false).distanceTo(ca.getPosition(new THREE.Vector3(), false)) < 1e-5); }")
    pa, pb = pg.evaluate(POSE_JS, 0), pg.evaluate(POSE_JS, 1)
    check("an animated move is mirrored frame by frame and the two agree exactly once settled (the tail goes out on rest)", close(pa["position"], pb["position"], 1e-5) and close(pa["target"], pb["target"], 1e-5),
          f"{[round(x, 3) for x in pa['position']]} vs {[round(x, 3) for x in pb['position']]}")
    pg.evaluate("async () => {" + MODS + " await cv.toggleProjection(a.world); await until(() => b.world.camera.projection.current === 'Orthographic'); await settle(300); }")
    pa, pb = pg.evaluate(POSE_JS, 0), pg.evaluate(POSE_JS, 1)
    check("switching the leader to orthographic switches the follower too", pa["projection"] == "Orthographic" and pb["projection"] == "Orthographic", f"{pa['projection']} / {pb['projection']}")
    check("  at the same visible half-height in metres", pa["halfHeight"] and pb["halfHeight"] and abs(pa["halfHeight"] - pb["halfHeight"]) < 1e-6 * pa["halfHeight"],
          f"{pa['halfHeight']:.4f} vs {pb['halfHeight']:.4f}" if pa["halfHeight"] and pb["halfHeight"] else str((pa["halfHeight"], pb["halfHeight"])))
    pg.evaluate("async () => {" + MODS + " await ca.zoomTo(a.world.camera.threeOrtho.zoom * 1.7, false); await until(() => Math.abs(cm.readPose(b.world).halfHeight - cm.readPose(a.world).halfHeight) < 1e-6); await settle(100); }")
    pa, pb = pg.evaluate(POSE_JS, 0), pg.evaluate(POSE_JS, 1)
    check("an orthographic zoom on the leader (no position change) reaches the follower", abs(pa["halfHeight"] - pb["halfHeight"]) < 1e-6 * pa["halfHeight"], f"{pa['halfHeight']:.4f} vs {pb['halfHeight']:.4f}")
    pg.evaluate("async () => {" + MODS + " await cv.toggleProjection(a.world); await until(() => b.world.camera.projection.current === 'Perspective'); await settle(300); }")
    pa, pb = pg.evaluate(POSE_JS, 0), pg.evaluate(POSE_JS, 1)
    check("and back to perspective on both", pa["projection"] == "Perspective" and pb["projection"] == "Perspective", f"{pa['projection']} / {pb['projection']}")
    # the follower drives too: sync is symmetric
    pg.evaluate("async () => {" + MODS + " await cb.setLookAt(-20, 15, 40, 1, 1, 1, false); await until(() => ca.getPosition(new THREE.Vector3(), false).distanceTo(new THREE.Vector3(-20, 15, 40)) < 1e-6); await settle(100); }")
    pa, pb = pg.evaluate(POSE_JS, 0), pg.evaluate(POSE_JS, 1)
    check("a move on the second viewer reaches the first", close(pa["position"], [-20, 15, 40]) and close(pa["target"], [1, 1, 1]), f"{[round(x, 3) for x in pa['position']]}")
    pg.click("#sync-cam-btn"); pg.wait_for_timeout(200)
    pg.evaluate("async () => {" + MODS + " await ca.setLookAt(50, 50, 50, 0, 0, 0, false); await settle(800); }")
    pa, pb = pg.evaluate(POSE_JS, 0), pg.evaluate(POSE_JS, 1)
    check("sync off again: the follower stays put", close(pb["position"], [-20, 15, 40]) and not close(pa["position"], pb["position"], 1e-3))
    check("culling in the second viewer is exact after all that", pg.evaluate(CULL_JS.replace("a.fragments", "b.fragments").replace("a.world", "b.world"))["wrong"] == 0)

    check("no console or page errors", not errs, "; ".join(errs[:3]))
    bad = [n for n, ok in res if not ok]
    print(f"\n{len(res)-len(bad)}/{len(res)} checks passed" + (f"\nFAILED: {bad}" if bad else ""))
    b.close()
    sys.exit(1 if bad else 0)

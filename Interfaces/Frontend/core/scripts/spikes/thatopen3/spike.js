// ThatOpen 3 / Fragments 3 feasibility spike - minimal pipeline, standalone.
// Loads an example model through IfcLoader (v3: web-ifc -> IfcImporter ->
// .frag buffer -> FragmentsModels worker), renders it, then exercises the
// item-level primitives the locked behaviours need: per-item opacity (ghost),
// per-item colour (intent highlight), per-item visibility (Hider), boxes for
// a GUID list (camera scope). Results on window.__spike for Playwright.
import * as OBC from "@thatopen/components";
import * as OBCF from "@thatopen/components-front";
import * as THREE from "three";

const logEl = document.getElementById("log");
const out = { steps: [], errors: [] };
window.__spike = out;
const log = (msg, data) => {
  out.steps.push({ t: Math.round(performance.now()), msg, ...(data || {}) });
  logEl.textContent += `${(performance.now() / 1000).toFixed(2)}s ${msg} ${data ? JSON.stringify(data) : ""}\n`;
};
window.addEventListener("error", (e) => out.errors.push(String(e.message)));
window.addEventListener("unhandledrejection", (e) =>
  out.errors.push(String(e.reason?.message ?? e.reason)),
);

const params = new URLSearchParams(location.search);
const fileKey = params.get("model") || "test_1";

async function main() {
  const components = new OBC.Components();
  components.init();
  const worlds = components.get(OBC.Worlds);
  const world = worlds.create();
  world.scene = new OBC.SimpleScene(components);
  world.scene.setup();
  world.scene.three.background = new THREE.Color("#f0f0f0");
  world.renderer = new OBC.SimpleRenderer(components, document.getElementById("view"));
  world.camera = new OBC.OrthoPerspectiveCamera(components);
  await world.camera.controls.setLookAt(60, 40, 60, 0, 0, 0);

  const fragments = components.get(OBC.FragmentsManager);
  const workerUrl = await OBC.FragmentsManager.getWorker();
  fragments.init(workerUrl);
  log("fragments worker initialised", { workerUrl: workerUrl.slice(0, 40) });

  // v3: models need the camera to decide LOD/tiles; update on camera rest.
  world.camera.controls.addEventListener("rest", () => fragments.core.update(true));
  fragments.list.onItemSet.add(({ value: model }) => {
    model.useCamera(world.camera.three);
    world.scene.three.add(model.object);
    fragments.core.update(true);
  });

  const loader = components.get(OBC.IfcLoader);
  await loader.setup({ autoSetWasm: false, wasm: { path: "/wasm/", absolute: true } });
  log("ifc loader set up", { wasm: loader.settings.wasm });

  const t0 = performance.now();
  const res = await fetch(`/api/example-models?fileKey=${fileKey}`);
  const bytes = new Uint8Array(await res.arrayBuffer());
  log("bytes fetched", { mb: +(bytes.length / 1048576).toFixed(1) });

  const t1 = performance.now();
  const model = await loader.load(bytes, true, fileKey);
  const t2 = performance.now();
  log("loaded", { loadMs: Math.round(t2 - t1), modelId: model.modelId });
  out.loadMs = Math.round(t2 - t1);

  await fragments.core.update(true);
  await new Promise((r) => setTimeout(r, 1500)); // let tiles settle
  await fragments.core.update(true);
  await new Promise((r) => requestAnimationFrame(r));

  const box = model.box;
  const sphere = box.getBoundingSphere(new THREE.Sphere());
  await world.camera.controls.fitToSphere(sphere, false);
  await fragments.core.update(true);
  await new Promise((r) => setTimeout(r, 1500));
  await fragments.core.update(true);
  await new Promise((r) => requestAnimationFrame(r));
  const info = world.renderer.three.info.render;
  out.render = { calls: info.calls, triangles: info.triangles };
  log("rendered", out.render);

  const ids = await model.getItemsIdsWithGeometry();
  out.itemsWithGeometry = ids.length;
  const cats = await model.getCategories();
  out.categories = cats.length;
  log("items", { withGeometry: ids.length, categories: cats.length });

  // ---- locked-behaviour primitives ----
  // 1. gray base: colour everything
  let t = performance.now();
  await model.setColor(undefined, new THREE.Color("#9e9e9e"));
  await fragments.core.update(true);
  out.grayMs = Math.round(performance.now() - t);

  // 2. ghost: whole model 10% opacity, a subset back to 1 + coloured (Refer)
  const subset = ids.slice(0, 8);
  t = performance.now();
  await model.setOpacity(undefined, 0.1);
  await model.setOpacity(subset, 1);
  await model.setColor(subset, new THREE.Color("#7a2e2e"));
  await fragments.core.update(true);
  out.ghostMs = Math.round(performance.now() - t);
  const hl = await model.getHighlight(subset);
  out.subsetHighlight = hl.slice(0, 1).map((h) => ({
    opacity: h?.opacity,
    transparent: h?.transparent,
    color: h?.color?.getHexString?.(),
  }));
  const rest = await model.getHighlight(ids.slice(8, 9));
  out.restHighlight = rest.map((h) => ({ opacity: h?.opacity, transparent: h?.transparent }));
  log("ghost applied", {
    ghostMs: out.ghostMs,
    subset: out.subsetHighlight,
    rest: out.restHighlight,
  });

  // 3. boxes for a GUID list (camera scope)
  const guids = await model.getGuidsByLocalIds(subset);
  const localIds = await model.getLocalIdsByGuids(guids.filter(Boolean));
  const boxes = await model.getBoxes(localIds.filter((x) => x !== null));
  const union = new THREE.Box3();
  for (const b of boxes) union.union(b);
  out.guidRoundTrip = {
    guids: guids.filter(Boolean).length,
    resolved: localIds.filter((x) => x !== null).length,
    boxDiag: +union.getSize(new THREE.Vector3()).length().toFixed(2),
  };
  log("guid round trip + boxes", out.guidRoundTrip);

  // 4. visibility (Hider) and reset
  const hider = components.get(OBC.Hider);
  await hider.set(false, { [model.modelId]: new Set(ids.slice(8, 200)) });
  await fragments.core.update(true);
  const vis = await model.getItemsByVisibility(false);
  out.hidden = vis.length;
  await hider.set(true, { [model.modelId]: new Set(ids.slice(8, 200)) });
  await model.resetHighlight();
  await fragments.core.update(true);
  log("hider round trip", { hidden: out.hidden });

  // 5. classifier by storey / category and relations
  const classifier = components.get(OBC.Classifier);
  await classifier.byIfcBuildingStorey({ classificationName: "Storeys" });
  await classifier.byCategory({ classificationName: "Categories" });
  const storeys = classifier.list.get("Storeys");
  const categories = classifier.list.get("Categories");
  out.classifier = {
    storeys: storeys ? [...storeys.keys()] : null,
    categories: categories ? categories.size : null,
  };
  log("classifier", {
    storeys: out.classifier.storeys?.length,
    categories: out.classifier.categories,
  });
  const tree = await model.getSpatialStructure();
  out.spatialRoot = tree?.category ?? null;

  // 6. Highlighter component (components-front) - style + highlightByID
  const highlighter = components.get(OBCF.Highlighter);
  highlighter.setup({ world, selectEnabled: true, hoverEnabled: false });
  highlighter.add({
    customId: "intent-1",
    color: new THREE.Color("#2a78d6"),
    opacity: 1,
    transparent: false,
    renderedFaces: 0,
  });
  await highlighter.highlightByID(
    "intent-1",
    { [model.modelId]: new Set(ids.slice(20, 30)) },
    false,
    false,
  );
  await fragments.core.update(true);
  out.highlighterOk = true;
  log("highlighter ok");

  // 7. BoundingBoxer
  const bboxer = components.get(OBC.BoundingBoxer);
  await bboxer.addFromModelIdMap({ [model.modelId]: new Set(subset) });
  out.bboxerDiag = +bboxer.get().getSize(new THREE.Vector3()).length().toFixed(2);
  bboxer.list.clear();
  log("bboxer", { diag: out.bboxerDiag });

  // 8. export .frag buffer size (the v3 "tile set" equivalent)
  const buf = await model.getBuffer(false);
  out.fragMb = +(buf.byteLength / 1048576).toFixed(1);
  log("frag buffer", { mb: out.fragMb });

  out.done = true;
  log("done");
}

main().catch((err) => {
  out.errors.push(String(err?.stack || err));
  out.done = true;
  log("FAILED " + err.message);
});

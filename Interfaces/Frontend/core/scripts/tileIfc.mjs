#!/usr/bin/env node
/**
 * Offline IFC -> tile-set conversion.
 *
 * Runs @thatopen/components' IfcGeometryTiler (parses raw IFC via web-ifc
 * ONCE, splits geometry into small tile files + a manifest) and writes the
 * result to a static directory the viewer can stream from at runtime via
 * @thatopen/components-front's IfcStreamer - instead of every browser
 * session re-parsing the full raw IFC file through OBC.IfcLoader.
 *
 * Usage: node scripts/tileIfc.mjs <input.ifc> [outputDir]
 * Default outputDir: public/tiles/<contentKey>/ - the SAME content-addressed
 * key the browser and src/file_identity.py derive for the same bytes (see
 * ../fileIdentity.js), not the input file's basename. That is what lets the
 * viewer ask "is there a tile set for the model I just opened?" and get a
 * correct answer regardless of what that file happens to be named locally.
 * Served statically by Vite, per the no-live-backend-for-v1 constraint.
 *
 * Output layout, and WHY each piece exists (reverse-engineered from
 * @thatopen/components-front's IfcStreamer.load() source, since the
 * library's own docs aren't available offline):
 *
 *   <fileKey>-processed-global.frag  - the manifest: a small FragmentsGroup
 *     (same binary format FragmentsManager.export()/.load() use elsewhere)
 *     fetched by IfcStreamer.load() via its `globalDataFileId` setting.
 *     MUST be named with exactly this "-processed-global" suffix -
 *     IfcStreamer derives the loaded model's display name by stripping it
 *     verbatim (`u.name = o.replace("-processed-global", "")`), not a
 *     naming choice made here.
 *   geometries/tile_NNNNN.frag       - actual triangle-mesh tile files,
 *     fetched LAZILY at runtime by IfcStreamer's internal camera-driven
 *     culler, only for geometry currently visible/near the camera. This is
 *     the actual "don't pay full cost for what you don't need" mechanism.
 *   geometries.json                  - EVERY geometry's {boundingBox,
 *     hasHoles, geometryFile} in one place, keyed by geometry id -
 *     `geometryFile` is what tells the runtime culler which tile file to
 *     fetch for a given geometry. IfcStreamer.load() expects this ALREADY
 *     PARSED (not fetched internally) - the browser-side loader must fetch
 *     + JSON.parse this itself before calling streamer.load().
 *   assets.json                      - EVERY element's placement (id,
 *     [{geometryID, transformation, color}]) in one flat array. Also
 *     expected already-parsed by the caller, same as geometries.json -
 *     lightweight (no geometry), so IfcStreamer keeps all of it in memory
 *     rather than streaming it.
 */
import { createHash } from "node:crypto";
import * as THREE from "three";
import * as WEBIFC from "web-ifc";

import { boxOfTileAssets, TILE_BOX_CONVENTION } from "../tileBounds.js";
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { resolve } from "node:path";

// OBC.Components' generic per-frame update loop needs these browser globals;
// IfcGeometryTiler itself does no rendering, so a setTimeout-based stand-in
// is enough. Must be set before importing @thatopen/components.
globalThis.requestAnimationFrame = (cb) => setTimeout(() => cb(performance.now()), 16);
globalThis.cancelAnimationFrame = (id) => clearTimeout(id);

const { default: OBC } = await import("@thatopen/components").then((m) => ({ default: m }));

const [, , inputPathArg, outputDirArg] = process.argv;
if (!inputPathArg) {
  console.error("Usage: node scripts/tileIfc.mjs <input.ifc> [outputDir]");
  process.exit(1);
}

const inputPath = resolve(inputPathArg);
const inputBytes = readFileSync(inputPath);
// Must stay identical to fileIdentity.js's computeContentKey() and
// src/file_identity.py's compute_content_key(): SHA-256 over the raw bytes,
// first 16 lowercase hex chars.
const fileKey = createHash("sha256").update(inputBytes).digest("hex").slice(0, 16);
const outDir = outputDirArg ? resolve(outputDirArg) : resolve(`public/tiles/${fileKey}`);
mkdirSync(`${outDir}/geometries`, { recursive: true });

const components = new OBC.Components();
await components.init();
const tiler = components.get(OBC.IfcGeometryTiler);
// Empty, non-absolute path: the node build of web-ifc already knows its own
// wasm file's location relative to itself when given no extra prefix -
// confirmed empirically (an explicit prefix double-resolves the path and
// fails with ENOENT).
tiler.settings.wasm = { path: "", absolute: false };

const allAssets = [];
const allGeometries = {};
let tileIndex = 0;

// Registered BEFORE streamFromBuffer() runs, not after - onIfcLoaded fires
// DURING that call, not after it resolves. Registering late means the
// event has already fired and this would hang forever (hit for real while
// prototyping this).
const manifestReady = new Promise((resolveManifest) => {
  tiler.onIfcLoaded.add((buffer) => resolveManifest(buffer));
});

tiler.onGeometryStreamed.add(({ buffer, data }) => {
  tileIndex++;
  const fileName = `geometries/tile_${String(tileIndex).padStart(5, "0")}.frag`;
  writeFileSync(`${outDir}/${fileName}`, buffer);
  for (const [id, geomData] of Object.entries(data)) {
    allGeometries[id] = { ...geomData, geometryFile: fileName };
  }
});

tiler.onAssetStreamed.add((assets) => {
  allAssets.push(...assets);
});

let lastLoggedPercent = -1;
tiler.onProgress.add((p) => {
  const percent = Math.floor(p * 100);
  if (percent !== lastLoggedPercent) {
    lastLoggedPercent = percent;
    process.stdout.write(`\rConverting... ${percent}%`);
  }
});

const bytes = new Uint8Array(inputBytes);
console.log(`Tiling ${inputPath} (${bytes.length} bytes, key ${fileKey}) -> ${outDir}`);
const start = performance.now();
await tiler.streamFromBuffer(bytes);
const manifestBuffer = await manifestReady;
const elapsed = performance.now() - start;
console.log(`\nStreaming done in ${elapsed.toFixed(0)}ms.`);

const manifestFileName = `${fileKey}-processed-global.frag`;
writeFileSync(`${outDir}/${manifestFileName}`, manifestBuffer);

// ---- Properties ----
// Geometry alone is not enough for this viewer: the intent panel resolves
// IFC GlobalIds to fragments, the filter panel classifies by entity type and
// by storey, and the inspector shows an element's properties - all of which
// read properties that a geometry-only tile set simply does not contain.
// Streaming geometry without them would load a model that renders but can't
// be referred, filtered or inspected, so IfcPropertiesTiler runs here too.
//
// Layout is what IfcStreamer's own StreamPropertiesSettings expects:
//   <fileKey>-processed-properties.frag-<n>
//                              one batch of property rows, keyed by expressID.
//                              The name is NOT a choice: IfcStreamer derives
//                              it as globalDataFileId.replace("-global",
//                              "-properties") and then appends "-<n>"
//                              (confirmed in its source), so the files have to
//                              be written exactly where it will look.
//   properties-indexes.json    the serialized relations index. IfcStreamer
//                              fetches and applies this itself during load().
//   properties-settings.json   {ids, types, indexesFile} - the lookup table
//                              saying which batch file holds which element
//
// properties-settings.json is deliberately its OWN file rather than a field
// inside tileset.json: its `ids` map has one entry per element (111,940 on
// test_7.ifc, 2.3MB of JSON), and tileset.json is the descriptor the viewer
// fetches for EVERY model just to ask "does a tile set exist for this one?".
// Keeping that probe small is the whole point of having it.
// Must match IfcStreamer's own derivation exactly - see the layout note above.
const propertiesBaseFileName = manifestFileName.replace("-global", "-properties");

const propsTiler = components.get(OBC.IfcPropertiesTiler);
propsTiler.settings.wasm = { path: "", absolute: false };

const propertyIds = {};
const propertyTypes = {};
// GlobalId -> expressID, harvested while the property rows stream past. The
// viewer needs exactly this map to resolve a recognized intent's member
// GUIDs to elements; without it, a streamed model would have to fetch all
// 1000+ property batch files just to find them. Emitting it here turns that
// into one small fetch.
const guidToExpressId = {};
// IfcSite/IfcGeographicElement (terrain/topography) are routinely many times
// larger than the building itself - on a real file here a single
// IFCGEOGRAPHICELEMENT accounted for ~99% of the model's bounding-box
// diagonal. The viewer already excludes them when framing a PARSED model
// (CAMERA_FIT_EXCLUDED_CLASSES in cameraViews.js); this collects the same
// exclusion offline so the streamed path can frame the building, not the site.
const CAMERA_FIT_EXCLUDED_TYPES = new Set([WEBIFC.IFCSITE, WEBIFC.IFCGEOGRAPHICELEMENT]);
const siteContextIds = new Set();
const indexesFileName = "properties-indexes.json";
let propsBatch = 0;
const propsWrites = [];

propsTiler.onPropertiesStreamed.add(({ type, data }) => {
  if (!propertyTypes[type]) propertyTypes[type] = [];
  propertyTypes[type].push(propsBatch);
  for (const expressID of Object.keys(data)) {
    propertyIds[expressID] = propsBatch;
    const guid = data[expressID]?.GlobalId?.value ?? data[expressID]?.GlobalId;
    if (typeof guid === "string" && guid) guidToExpressId[guid] = Number(expressID);
    if (CAMERA_FIT_EXCLUDED_TYPES.has(data[expressID]?.type)) siteContextIds.add(Number(expressID));
  }
  writeFileSync(`${outDir}/${propertiesBaseFileName}-${propsBatch}`, JSON.stringify(data));
  propsBatch++;
});

// The relations index (IfcRelAggregates/IfcRelContainedInSpatialStructure/...)
// that IfcRelationsIndexer would otherwise have to derive by walking every
// property itself. Serialized here once, offline, and handed straight to
// indexer.setRelationMap() at load time - which is what keeps the filter
// panel's Floors section working on a streamed model.
let serializedRelations = null;
propsTiler.onIndicesStreamed.add((relations) => {
  const indexer = components.get(OBC.IfcRelationsIndexer);
  serializedRelations = indexer.serializeRelations(relations);
});

const propsStart = performance.now();
await propsTiler.streamFromBuffer(bytes);
await Promise.all(propsWrites);
console.log(
  `Properties streamed in ${(performance.now() - propsStart).toFixed(0)}ms (${propsBatch} batch file(s)).`,
);

const propertiesSettingsFileName = "properties-settings.json";
// ---- World bounding box, computed offline ----
// A streamed model has NO geometry in the scene at the moment it finishes
// loading - the culler only fetches tiles once it knows where the camera is -
// so the viewer's usual "BoundingBoxer over everything in the scene" fit
// computes a nearly-empty box and parks the camera inside the building
// (measured: a 104.8m fit on the parsed path became 22.4m when streamed).
// The extents are fully known here, offline, so they are computed once and
// shipped in the descriptor for the viewer to fit from immediately.
//
// How each geometry's `boundingBox` and each instance's placement compose,
// and why every corner is transformed, is documented once in tileBounds.js -
// the viewer reads the same metadata at runtime for a streamed Refer.
const worldBox = boxOfTileAssets(allAssets, allGeometries);
const buildingBox = boxOfTileAssets(
  allAssets.filter((asset) => !siteContextIds.has(asset.id)),
  allGeometries,
);
const boxToJson = (box) => (box ? { min: box.min.toArray(), max: box.max.toArray() } : null);
const worldBoundingBox = boxToJson(worldBox);
// Falls back to the full extents when a model is ALL site context (or carries
// no type info), mirroring computeBuildingBoundingBox()'s own fallback.
const buildingBoundingBox = boxToJson(buildingBox) ?? worldBoundingBox;

const guidsFileName = "guids.json";
// Restricted to elements that actually have geometry in this tile set. Every
// IFC entity with a GlobalId streams past above (80,197 of them on
// test_7.ifc, 2.5MB), but the viewer only ever resolves a GUID in order to
// colour, refer or hide something on screen - an entity with no asset has
// nothing to resolve to. Filtering against the geometry tiler's own asset
// list drops this to the ~5k elements that can actually be shown.
const assetIds = new Set(allAssets.map((asset) => asset.id));
const renderableGuids = {};
for (const [guid, expressID] of Object.entries(guidToExpressId)) {
  if (assetIds.has(expressID)) renderableGuids[guid] = expressID;
}
writeFileSync(`${outDir}/${guidsFileName}`, JSON.stringify(renderableGuids));
if (serializedRelations) {
  writeFileSync(`${outDir}/${indexesFileName}`, serializedRelations);
  writeFileSync(
    `${outDir}/${propertiesSettingsFileName}`,
    JSON.stringify({
      ids: propertyIds,
      types: propertyTypes,
      indexesFile: indexesFileName,
    }),
  );
}
writeFileSync(`${outDir}/assets.json`, JSON.stringify(allAssets));
writeFileSync(`${outDir}/geometries.json`, JSON.stringify(allGeometries));
// A tiny descriptor the viewer fetches FIRST to decide whether a usable tile
// set exists for a model at all - one small request instead of probing for
// several large files and interpreting 404s. Also records what produced it,
// so a stale tile set from an older tiler is identifiable rather than
// silently loaded.
writeFileSync(
  `${outDir}/tileset.json`,
  JSON.stringify(
    {
      tilesetVersion: 1,
      fileKey,
      globalDataFileId: manifestFileName,
      assetCount: allAssets.length,
      geometryCount: Object.keys(allGeometries).length,
      tileCount: tileIndex,
      sourceBytes: bytes.length,
      generatedAt: new Date().toISOString(),
      // Name of the sidecar holding IfcStreamer.load()'s third argument, or null
      // when properties could not be tiled (geometry-only set - the viewer then
      // declines to stream it, since it could render but not be referred).
      propertiesFile: serializedRelations ? propertiesSettingsFileName : null,
      propertyBatchCount: propsBatch,
      propertyElementCount: Object.keys(propertyIds).length,
      guidsFile: guidsFileName,
      guidCount: Object.keys(renderableGuids).length,
      // {min:[x,y,z], max:[x,y,z]} in the tile set's own (re-centred) world space,
      // or null if no geometry carried usable bounds.
      worldBoundingBox,
      // Same box minus IfcSite/IfcGeographicElement - what the camera frames.
      buildingBoundingBox,
      // How the two boxes above were composed (tileBounds.js). A tile set
      // without this field was written with the +/-0.5 cube of before
      // 2026-10-21; the viewer then recomputes its boxes at load time.
      boxConvention: TILE_BOX_CONVENTION,
    },
    null,
    2,
  ),
);

console.log("\nWrote:");
console.log(`  ${manifestFileName} (${manifestBuffer.length} bytes)`);
console.log(`  assets.json (${allAssets.length} assets)`);
console.log(
  `  geometries.json (${Object.keys(allGeometries).length} geometries, ${tileIndex} tile files)`,
);
console.log(
  `  ${propertiesBaseFileName}-0..${propsBatch - 1} (${propsBatch} batch files, ${Object.keys(propertyIds).length} elements)`,
);
console.log(
  `  ${indexesFileName}${serializedRelations ? "" : " (SKIPPED - no relations index streamed)"}`,
);
if (serializedRelations) console.log(`  ${propertiesSettingsFileName}`);
console.log(
  `  ${guidsFileName} (${Object.keys(renderableGuids).length} renderable GlobalIds of ${Object.keys(guidToExpressId).length} total)`,
);
console.log(
  `  tileset.json${
    worldBoundingBox
      ? ` (world ${worldBox
          .getSize(new THREE.Vector3())
          .toArray()
          .map((n) => n.toFixed(1))
          .join(" x ")} m, building ${
          buildingBox.isEmpty()
            ? "n/a"
            : buildingBox
                .getSize(new THREE.Vector3())
                .toArray()
                .map((n) => n.toFixed(1))
                .join(" x ")
        } m)`
      : " (no world bbox)"
  }`,
);

process.exit(0);

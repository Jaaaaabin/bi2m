// ======== Tile-Set Streaming ========
// An ADDITIONAL load path, not a replacement: when a pre-converted tile set
// exists for the exact model being opened, geometry and properties stream in
// from it instead of the browser re-parsing the whole raw IFC through
// OBC.IfcLoader/web-ifc. When no tile set exists - or anything about it fails -
// the caller falls back to that raw path unchanged.
//
// What made this wireable at all is content-addressed identity
// (docs/architecture.md "One key for everything"): a tile set is stored
// under the content key of the bytes it was built from (scripts/tileIfc.mjs),
// so "is there a tile set for the model this user just dropped?" is a single
// exact lookup rather than a guess based on a filename that may have been
// renamed, copied or re-exported.
//
// Deliberately strict about what counts as usable: a geometry-only tile set
// is REFUSED (see probeTileSet). Such a set renders a model that cannot be
// referred, filtered by storey, or inspected - every feature this viewer
// exists for - so silently streaming it would look like a working load and
// behave like a broken one. Better to spend the parse and have a whole model.

import * as OBCF from "@thatopen/components-front";
import * as FRAG from "@thatopen/fragments";

import { tileSetBoundingBox } from "./tileBounds.js";

export { tileSetBoundingBox };

const TILESET_VERSION = 1;
// The common prefix every tile set lives under. Kept as the page-wide static
// FragmentsGroup.url so that only the per-model part varies (see the
// baseFileName rewrite in loadStreamedModel).
const TILES_ROOT = "./tiles/";

/**
 * Looks for a usable tile set for `fileKey`. Returns a descriptor (with the
 * base URL folded in) or null. Never throws: a missing tile set is the normal
 * case, not an error.
 */
export async function probeTileSet(fileKey) {
  const base = `${TILES_ROOT}${encodeURIComponent(fileKey)}/`;
  let descriptor;
  try {
    const res = await fetch(`${base}tileset.json`);
    if (!res.ok) return null;
    descriptor = await res.json();
  } catch {
    return null;
  }

  // An older or newer generator's output is not assumed compatible - the
  // layout below is reverse-engineered from IfcStreamer's own expectations
  // and could legitimately change.
  if (descriptor?.tilesetVersion !== TILESET_VERSION) {
    console.warn(
      `⚠️ Ignoring tile set for ${fileKey}: unsupported tilesetVersion ${descriptor?.tilesetVersion}.`,
    );
    return null;
  }
  if (!descriptor.propertiesFile || !descriptor.guidsFile) {
    console.warn(
      `⚠️ Ignoring tile set for ${fileKey}: geometry-only (no properties/GUID sidecar), ` +
        "which would render a model that cannot be referred, filtered or inspected. " +
        "Re-run scripts/tileIfc.mjs to regenerate it.",
    );
    return null;
  }
  return { ...descriptor, base };
}

const fetchJson = async (url) => {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`${url} -> ${res.status}`);
  return res.json();
};

/**
 * Streams the model in. Returns {model, guidSeed, assets, geometries}: the
 * tile set's GlobalId -> expressID map (see below) and the parsed
 * assets.json / geometries.json, which the viewer keeps on the model context
 * (`tileMetadata`) to measure a Refer's scope box without any geometry in
 * the scene (tileBounds.js, since 2026-10-21).
 *
 * `assets`/`geometries`/the property settings are all handed to
 * IfcStreamer.load() ALREADY PARSED - it does not fetch them itself, only the
 * individual geometry tile files, lazily, driven by its own camera culler.
 */
// The streamer's GeometryCullerRenderer (components-front 2.4.3) gives
// opaque instances a MeshBasicMaterial and TRANSPARENT ones (instanceColor
// alpha < 0.9) a bare `new RawShaderMaterial()` - no shader source at all, so
// three falls back to a default vertex shader that references undeclared
// `projectionMatrix`/`modelViewMatrix`/`position` and logs a compile error on
// every streamed load.
// The culler only reads back colour ids from its off-screen pass, so the
// honest local fix is to give transparent instances the same material as
// opaque ones: they then take part in culling exactly like everything else
// (slightly conservative - glass can occlude what is behind it until the
// camera moves). Applied to the property the culler reads when it creates
// its meshes, before load(), so no mesh ever sees the broken material.
function patchCullerTransparentMaterial(streamer) {
  const culler = streamer.culler;
  const broken = culler?._materialT;
  if (
    !broken ||
    broken.type !== "RawShaderMaterial" ||
    typeof culler._material?.clone !== "function"
  )
    return;
  culler._materialT = culler._material.clone();
  broken.dispose?.();
}

export async function loadStreamedModel({ components, world, descriptor }) {
  const streamer = components.get(OBCF.IfcStreamer);
  streamer.world = world;
  streamer.url = descriptor.base;
  patchCullerTransparentMaterial(streamer);

  const [assets, geometries, properties, guidSeed] = await Promise.all([
    fetchJson(`${descriptor.base}assets.json`),
    fetchJson(`${descriptor.base}geometries.json`),
    fetchJson(`${descriptor.base}${descriptor.propertiesFile}`),
    fetchJson(`${descriptor.base}${descriptor.guidsFile}`),
  ]);

  const model = await streamer.load(
    { assets, geometries, globalDataFileId: descriptor.globalDataFileId },
    true, // coordinate: re-center, same as a normal IfcLoader load
    properties,
  );

  // load() already fetched descriptor's indexesFile and called
  // indexer.setRelationMap() for us (confirmed in IfcStreamer's source), so
  // the relations the filter panel's Floors section needs are in place - no
  // separate step here.
  //
  // What it does NOT get right for a multi-viewer app: it sets
  // `FragmentsGroup.url`, which is a STATIC (class-level, page-wide) property,
  // to this streamer's own per-viewer url. Property files are then fetched
  // from `FragmentsGroup.url + baseFileName + "-" + fileID`, so opening a
  // SECOND streamed model in another viewer would repoint that static url and
  // silently break the first model's property fetches - and this app's whole
  // premise is several viewers side by side.
  //
  // Fixed by moving the per-model part of the path out of the static url and
  // into `baseFileName`, which IS per-group: every streamed model then
  // resolves its own properties correctly no matter how many are open.
  FRAG.FragmentsGroup.url = TILES_ROOT;
  model.streamSettings.baseFileName = `${descriptor.fileKey}/${model.streamSettings.baseFileName}`;

  return { model, guidSeed, assets, geometries };
}

/**
 * Turns the tile set's {GlobalId: expressID} sidecar into the
 * {GlobalId: {fragmentID, expressID}} index the rest of the app resolves
 * GUIDs against.
 *
 * This is the streamed counterpart of highlighting.js's buildGuidIndex(), and
 * it is strictly cheaper: that one walks every element's properties
 * (O(elements)); this one reads a map the offline tiler already built, and
 * only has to find which fragment currently holds each expressID.
 */
export function buildGuidIndexFromSeed(model, guidSeed) {
  const expressIdToFragment = new Map();
  for (const [fragmentID, expressIDs] of Object.entries(model.getFragmentMap())) {
    for (const expressID of expressIDs) expressIdToFragment.set(Number(expressID), fragmentID);
  }

  const guidToLocation = new Map();
  for (const [guid, expressID] of Object.entries(guidSeed)) {
    const fragmentID = expressIdToFragment.get(expressID);
    if (fragmentID !== undefined) guidToLocation.set(guid, { fragmentID, expressID });
  }
  return guidToLocation;
}

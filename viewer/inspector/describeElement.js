// ======== Element description: everything the inspector shows ========
// The loader's whole share of the inspector is two calls: indexGeometry()
// once per loaded model, and describeElement() for each clicked element. What
// the panel shows - GUID, name, IFC class, the element's flat attributes and
// its geometry label - is gathered here, the same way for a parsed and a
// streamed model (attributes come from ThatOpen's properties, which a
// streamed model reads from its property tiles).
//
// The geometry label is the one thing ThatOpen cannot supply: see
// geometryLabels.js. indexGeometry() runs that scan in a Worker after the
// model is on screen; a click that arrives before it finishes waits for it.

import * as OBC from "@thatopen/components";

import { getModelContext } from "../viewerModel.js";
import { friendlyTypeLabel } from "./geometryLabels.js";

// Shown in the panel's header and meta rows instead, or not meaningful as a
// flat value.
const HIDDEN_KEYS = new Set([
  "expressID",
  "type",
  "Name",
  "GlobalId",
  "RepresentationIdentifier",
  "RepresentationType",
]);

function unwrap(value) {
  if (value && typeof value === "object" && "value" in value) return value.value;
  return value;
}

// `properties.type` is web-ifc's numeric type code (IFCWALL = 2391406946);
// OBC.IfcCategoryMap is the library's own code -> "IFCWALL" table, the
// spelling the Categories panel uses too.
function ifcClassName(properties) {
  const code = unwrap(properties?.type);
  if (typeof code === "number") return OBC.IfcCategoryMap?.[code] ?? String(code);
  return typeof code === "string" && code ? code : null;
}

function scanInWorker(bytes) {
  return new Promise((resolve, reject) => {
    const worker = new Worker(new URL("./geometryLabels.worker.js", import.meta.url), {
      type: "module",
    });
    worker.onmessage = (event) => {
      worker.terminate();
      if (event.data.ok) resolve(new Map(event.data.labels));
      else reject(new Error(event.data.error));
    };
    worker.onerror = (event) => {
      worker.terminate();
      reject(new Error(event.message || "geometry label worker failed"));
    };
    worker.postMessage({ buffer: bytes.buffer }, [bytes.buffer]);
  });
}

/**
 * Starts reading the model's geometry labels from its file bytes, in a
 * Worker. The bytes are TRANSFERRED: the caller must not read them again.
 * Never rejects; a failed scan only leaves the "Geometry:" row empty.
 * @param {any} model the loaded FragmentsGroup
 * @param {Uint8Array} bytes the whole IFC file
 */
export function indexGeometry(model, bytes) {
  const pending = scanInWorker(bytes).catch((err) => {
    console.warn(
      "⚠️ Could not read geometry types (the inspector's Geometry row stays empty):",
      err.message,
    );
    return new Map();
  });
  const context = getModelContext(model);
  if (context) context.geometryLabels = pending;
  return pending;
}

/**
 * @typedef {object} ElementDescription
 * @property {number} expressID
 * @property {string} fileName
 * @property {string|null} guid
 * @property {string|null} name
 * @property {string|null} ifcClass   e.g. "IFCWALL"
 * @property {[string, any][]} attributes  flat attributes, in file order
 * @property {{label: string, detail: string}|null} geometry  e.g. "Swept Solid", "IFCEXTRUDEDAREASOLID"
 */

/**
 * @param {any} model the FragmentsGroup the element belongs to
 * @param {number} expressID
 * @returns {Promise<ElementDescription>}
 */
export async function describeElement(model, expressID) {
  let properties = {};
  try {
    const local = model.getLocalProperties?.();
    properties = (local ? local[expressID] : await model.getProperties(expressID)) ?? {};
  } catch (err) {
    console.warn("⚠️ Could not read properties for the selected element:", err.message);
  }

  let geometry = null;
  const shapeId = unwrap(properties.Representation);
  const labels = await getModelContext(model)?.geometryLabels;
  const label = typeof shapeId === "number" ? labels?.get(shapeId) : undefined;
  if (label) {
    geometry = {
      label: friendlyTypeLabel(label.type) || "(unspecified)",
      detail: label.itemClasses.filter(Boolean).join(", "),
    };
  }

  const attributes = Object.entries(properties)
    .filter(([key]) => !HIDDEN_KEYS.has(key))
    .map(([key, value]) => /** @type {[string, any]} */ ([key, unwrap(value)]))
    .filter(([, value]) => value !== null && value !== undefined && typeof value !== "object");

  return {
    expressID,
    fileName: model.name,
    guid: unwrap(properties.GlobalId) ?? null,
    name: unwrap(properties.Name) ?? null,
    ifcClass: ifcClassName(properties),
    attributes,
    geometry,
  };
}

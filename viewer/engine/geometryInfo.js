/**
 * Resolves the actual geometry representation used to render a selected element,
 * for DISPLAY purposes in InspectorPanel.jsx - not a renderability gate (see
 * stepIndex.js's hasRenderableRepresentation/isPreviewable for that; this module
 * reuses the same attribute-index conventions but walks one level deeper, into
 * the chosen IfcShapeRepresentation's items, to name the actual geometry classes
 * involved (e.g. distinguishing a Faceted Brep from an Advanced Brep, or
 * resolving a mapped/instanced item to the type it's an instance of).
 *
 * Pure, synchronous, and cheap: reuses StepFileIndex's already-built id->offset
 * map (argsOf/getType), no new file scan and no async round-trip.
 */
import { collectRefs } from "./stepIndex.js";

/** Boundary-representation solid entity types - "is this a B-rep" for display. */
const BREP_ITEM_TYPES = new Set([
  "IFCFACETEDBREP",
  "IFCFACETEDBREPWITHVOIDS",
  "IFCMANIFOLDSOLIDBREP",
  "IFCADVANCEDBREP",
  "IFCADVANCEDBREPWITHVOIDS",
]);

/** Friendlier labels for IfcShapeRepresentation.RepresentationType values. */
const FRIENDLY_TYPE_LABELS = {
  SweptSolid: "Swept Solid",
  AdvancedSweptSolid: "Advanced Swept Solid",
  Brep: "Boundary Representation (B-rep)",
  AdvancedBrep: "Advanced Boundary Representation (B-rep)",
  SurfaceModel: "Surface Model",
  CSG: "Constructive Solid Geometry (CSG)",
  Clipping: "Boolean Clipping",
  Tessellation: "Tessellated Mesh",
  MappedRepresentation: "Mapped (Instanced) Geometry",
};

function unquote(raw) {
  if (!raw || raw[0] !== "'") {
    return undefined;
  }
  return raw.slice(1, raw.endsWith("'") ? -1 : undefined).replace(/''/g, "'");
}

/**
 * Resolves an IfcRepresentationItem's entity class, following one level of
 * IfcMappedItem indirection so a mapped (instanced) door/window/furniture piece
 * reports the underlying shape's class(es) instead of the uninformative
 * "IFCMAPPEDITEM".
 */
function resolveItemClass(index, itemId) {
  const itemType = index.getType(itemId);
  if (itemType !== "IFCMAPPEDITEM") {
    return itemType;
  }
  // IfcMappedItem(MappingSource, MappingTarget) -
  // MappingSource -> IfcRepresentationMap(MappingOrigin, MappedRepresentation).
  const mapArgs = index.argsOf(itemId);
  const mapSourceId = collectRefs(mapArgs[0] ?? "")[0];
  if (mapSourceId === undefined) {
    return itemType;
  }
  const repMapArgs = index.argsOf(mapSourceId);
  const mappedRepId = collectRefs(repMapArgs[1] ?? "")[0];
  if (mappedRepId === undefined) {
    return itemType;
  }
  const mappedItemIds = collectRefs(index.argsOf(mappedRepId)[3] ?? "");
  if (mappedItemIds.length === 0) {
    return itemType;
  }
  return mappedItemIds.map((id) => index.getType(id)).join("+");
}

/**
 * Describes the geometry representation of `id` (a product or a bare geometry
 * item - see stepIndex.js's isRenderableGeometryItem for the latter).
 *
 * Returns `{ identifier, type, itemClasses }` for the "Body" representation
 * (falling back to the first representation if there's no "Body"), or `null`
 * if `id` has no resolvable representation at all.
 */
export function describeGeometry(index, id) {
  // Bare geometry item (no product Representation attribute at all) - the
  // synthetic-wrapper case extractSubModel handles for "Preview in 3D".
  const bareType = index.geometryItemRepType(id);
  if (bareType !== undefined) {
    return { identifier: undefined, type: bareType, itemClasses: [index.getType(id)] };
  }

  const args = index.argsOf(id);
  if (args.length < 7) {
    return null;
  }
  const shapeId = collectRefs(args[6] ?? "")[0];
  if (shapeId === undefined) {
    return null;
  }
  // IfcProductRepresentation(Name, Description, Representations) - list at index 2.
  const reps = collectRefs(index.argsOf(shapeId)[2] ?? "");
  if (reps.length === 0) {
    return null;
  }

  let chosen;
  for (const repId of reps) {
    if (unquote(index.argsOf(repId)[1]) === "Body") {
      chosen = repId;
      break;
    }
  }
  if (chosen === undefined) {
    chosen = reps[0];
  }

  // IfcRepresentation(ContextOfItems, RepresentationIdentifier, RepresentationType, Items).
  const repArgs = index.argsOf(chosen);
  const identifier = unquote(repArgs[1]);
  const type = unquote(repArgs[2]);
  const itemIds = collectRefs(repArgs[3] ?? "");
  const itemClasses = itemIds.map((itemId) => resolveItemClass(index, itemId));

  return { identifier, type, itemClasses };
}

/** True if any resolved item class is a boundary-representation solid. */
export function isBrepGeometry(itemClasses) {
  return (itemClasses || []).some((cls) => cls && BREP_ITEM_TYPES.has(cls.split("+")[0]));
}

/** A human-readable label for a RepresentationType string, or the raw value if unmapped. */
export function friendlyTypeLabel(type) {
  if (!type) {
    return undefined;
  }
  return FRIENDLY_TYPE_LABELS[type] || type;
}

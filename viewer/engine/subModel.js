/**
 * Builds a minimal, self-contained IFC STEP model for a single element by walking
 * the reference graph around it. This is what makes per-element preview cheap even
 * on huge files: instead of handing a 180 MB model to the geometry engine, we emit
 * a few dozen lines containing only the element's geometry/placement closure.
 *
 * Ported from NepomukWolf/vscode-ifc's `src/viewer/subModel.ts` (MIT licensed; see
 * engine/README.md) - adapted from Node's `Buffer`/`Buffer.concat` to manual
 * `Uint8Array` assembly, with TypeScript types dropped. Logic is otherwise
 * unchanged.
 *
 * Original `#id` numbers are preserved verbatim, so the engine's express ids map
 * 1:1 back to the source STEP ids.
 *
 * Pure JS, no DOM/framework dependency - unit-testable standalone (e.g. in Node).
 */
import { REL_VOIDS, STYLED_ITEM, collectRefs } from "./stepIndex.js";

// A logical upper bound from the original project's perf tests. Maybe useful to tune later.
const DEFAULT_MAX_INSTANCES = 500_000;
const ARG_RELATING = 4; // RelatingObject / RelatingBuildingElement
const ARG_RELATED = 5; // RelatedObjects / RelatedOpeningElement
/** A valid-charset 22-char IFC GlobalId for synthetic wrapper products. */
const PREVIEW_GUID = "0previewprimitive00000";
/**
 * Non-physical products that web-ifc's `StreamAllMeshes` skips even though they
 * carry real `Body` geometry - openings are subtractions, spaces are void volumes.
 * Re-present their shape under a synthetic proxy so direct previews still render
 * their volume.
 */
const WEB_IFC_SKIPPED_PRODUCT_TYPES = new Set([
  "IFCOPENINGELEMENT",
  "IFCOPENINGSTANDARDCASE",
  "IFCSPACE",
  "IFCSPATIALZONE",
]);

function firstRef(arg) {
  if (!arg) {
    return undefined;
  }
  return collectRefs(arg)[0];
}

/**
 * @param {import("./stepIndex.js").StepFileIndex} index
 * @param {number} rootId
 * @param {{includeChildren?: boolean, includeVoids?: boolean, includeStyles?: boolean, maxInstances?: number}} [options]
 * @returns {{
 *   ifcBytes: ArrayBuffer,
 *   rootId: number,
 *   renderIds: number[],
 *   rootType: string | undefined,
 *   schema: string | undefined,
 *   includedIds: number[],
 *   childCount: number,
 *   truncated: boolean,
 *   pickRemap: Map<number, number>,
 * }}
 */
export function extractSubModel(index, rootId, options = {}) {
  const includeChildren = options.includeChildren ?? true;
  const includeVoids = options.includeVoids ?? true;
  const includeStyles = options.includeStyles ?? true;
  const maxInstances = options.maxInstances ?? DEFAULT_MAX_INSTANCES;

  if (!index.hasId(rootId)) {
    throw new Error(`#${rootId} is not defined in this file.`);
  }

  const included = new Set();
  let truncated = false;

  /** BFS the forward `#ref` closure of the given seeds into `included`. */
  const addClosure = (seeds) => {
    const queue = [...seeds];
    while (queue.length > 0) {
      const id = queue.pop();
      if (included.has(id) || !index.hasId(id)) {
        continue;
      }
      if (included.size >= maxInstances) {
        truncated = true;
        return;
      }
      included.add(id);
      for (const ref of index.refsOf(id)) {
        if (!included.has(ref)) {
          queue.push(ref);
        }
      }
    }
  };

  // 1. The element itself (placement chain, representation, profiles, points...).
  const renderIds = new Set([rootId]);
  addClosure([rootId]);

  // 2. The singleton IfcProject closure: units, geometric contexts, true north.
  if (index.projectId !== undefined) {
    addClosure([index.projectId]);
  }

  // 3. Descendants. BFS the combined decomposition + spatial-containment graph:
  //    assembly parts (IfcStair -> flights) and, for a spatial container, every
  //    physical element on it (IfcRelContainedInSpatialStructure). Spatial
  //    containers/spaces are recursed *through* but never rendered - they are
  //    organizational/void volumes that would obscure the physical elements.
  let childCount = 0;
  if (includeChildren && !truncated) {
    const visited = new Set([rootId]);
    const queue = [rootId];
    while (queue.length > 0 && !truncated) {
      const parent = queue.shift();
      for (const child of index.decompositionChildrenOf(parent)) {
        if (visited.has(child) || !index.hasId(child)) {
          continue;
        }
        visited.add(child);
        queue.push(child); // recurse even through containers, to reach their contents
        if (!index.isSpatialContainer(child)) {
          renderIds.add(child);
          childCount++;
          addClosure([child]);
          if (included.size >= maxInstances) {
            truncated = true;
            break;
          }
        }
      }
    }
  }

  // 4. Openings: include the void relationship + opening geometry so solids show
  //    their cut-outs (web-ifc performs the boolean when both are present).
  if (includeVoids && !truncated) {
    for (const relId of index.relIdsOfType(REL_VOIDS)) {
      const args = index.argsOf(relId);
      const relating = firstRef(args[ARG_RELATING]);
      if (relating !== undefined && included.has(relating)) {
        const opening = firstRef(args[ARG_RELATED]);
        included.add(relId);
        if (opening !== undefined) {
          addClosure([opening]);
        }
      }
    }
  }

  // 5. Styles/colors: include styled items whose target representation item is in
  //    scope, plus their style closure (IfcSurfaceStyle -> colour).
  if (includeStyles && !truncated) {
    for (const relId of index.relIdsOfType(STYLED_ITEM)) {
      const args = index.argsOf(relId);
      const item = firstRef(args[0]); // IfcStyledItem.Item
      if (item !== undefined && included.has(item)) {
        addClosure([relId]);
      }
    }
  }

  // 6. Bare geometry item (a brep/solid/tessellation, not a product). web-ifc
  //    streams product meshes, so wrap the item in a synthetic IfcBuildingElementProxy
  //    + shape representation. The item keeps its real id (so its closure renders
  //    unchanged); pick-to-reveal maps the wrapper back to it via `pickRemap`.
  const pickRemap = new Map();
  const extraLines = [];
  const itemRepType = index.geometryItemRepType(rootId);
  if (itemRepType !== undefined && !truncated) {
    let nextId = index.maxExpressId() + 1;
    const alloc = () => nextId++;

    // Anchor in an existing 3D context if the file has one (pulled in via the
    // project closure); otherwise mint a minimal context so the rep stands alone.
    let contextId = index.geometricContextId();
    if (contextId !== undefined) {
      addClosure([contextId]);
    } else {
      const originId = alloc();
      const wcsId = alloc();
      contextId = alloc();
      extraLines.push(`#${originId}=IFCCARTESIANPOINT((0.,0.,0.));`);
      extraLines.push(`#${wcsId}=IFCAXIS2PLACEMENT3D(#${originId},$,$);`);
      extraLines.push(
        `#${contextId}=IFCGEOMETRICREPRESENTATIONCONTEXT($,'Model',3,1.E-5,#${wcsId},$);`,
      );
    }

    const shapeRepId = alloc();
    const prodDefId = alloc();
    const productId = alloc();
    extraLines.push(
      `#${shapeRepId}=IFCSHAPEREPRESENTATION(#${contextId},'Body','${itemRepType}',(#${rootId}));`,
    );
    extraLines.push(`#${prodDefId}=IFCPRODUCTDEFINITIONSHAPE($,$,(#${shapeRepId}));`);
    extraLines.push(
      `#${productId}=IFCBUILDINGELEMENTPROXY('${PREVIEW_GUID}',$,'Geometry Preview',$,$,$,#${prodDefId},$,$);`,
    );

    renderIds.clear();
    renderIds.add(productId);
    pickRemap.set(productId, rootId);
  }

  // 7. Openings/spaces: products with real geometry that web-ifc won't stream.
  //    Re-present their existing shape + placement under a synthetic proxy so the
  //    direct preview renders the opening as its solid "plug"; pick-to-reveal maps
  //    the proxy back to the source.
  const rootType = index.getType(rootId);
  if (
    itemRepType === undefined &&
    !truncated &&
    rootType &&
    WEB_IFC_SKIPPED_PRODUCT_TYPES.has(rootType)
  ) {
    const args = index.argsOf(rootId);
    const shapeRef = collectRefs(args[6] ?? "")[0]; // Representation -> IfcProductDefinitionShape
    if (shapeRef !== undefined && index.hasId(shapeRef)) {
      const placement = args[5]?.startsWith("#") ? args[5] : "$"; // reuse ObjectPlacement if present
      const productId = index.maxExpressId() + 1;
      extraLines.push(
        `#${productId}=IFCBUILDINGELEMENTPROXY('${PREVIEW_GUID}',$,'Geometry Preview',$,$,${placement},#${shapeRef},$,$);`,
      );
      // Drop the original space/opening instance; the proxy reuses its
      // still-present shape + placement. Any contained elements stay in renderIds.
      included.delete(rootId);
      renderIds.delete(rootId);
      renderIds.add(productId);
      pickRemap.set(productId, rootId);
    }
  }

  const includedIds = [...included].sort((a, b) => a - b);
  const ifcBytes = assemble(index, includedIds, extraLines);

  return {
    ifcBytes,
    rootId,
    renderIds: [...renderIds].sort((a, b) => a - b),
    rootType: index.getType(rootId),
    schema: index.schema,
    includedIds,
    childCount,
    truncated,
    pickRemap,
  };
}

const textEncoder = new TextEncoder();
const NEWLINE_BYTE = 0x0a;

/** ASCII-only string -> bytes (synthetic wrapper lines are guaranteed ASCII). */
function asciiEncode(line) {
  const bytes = new Uint8Array(line.length);
  for (let i = 0; i < line.length; i++) {
    bytes[i] = line.charCodeAt(i);
  }
  return bytes;
}

/** Stitch the header + selected instance bytes into a valid STEP file, preserving
 *  the original bytes verbatim (no latin1/UTF-8 round-trip) so non-ASCII content
 *  survives intact on its way to the geometry engine. Returns a plain `ArrayBuffer`
 *  sized exactly to the assembled content. */
function assemble(index, ids, extraLines = []) {
  const parts = [index.headerBytes()];
  for (const id of ids) {
    const bytes = index.sliceInstanceBytes(id);
    if (bytes) {
      parts.push(new Uint8Array([NEWLINE_BYTE]), bytes);
    }
  }
  // Synthetic wrapper instances (ASCII-only) appended after the verbatim source.
  for (const line of extraLines) {
    parts.push(new Uint8Array([NEWLINE_BYTE]), asciiEncode(line));
  }
  parts.push(textEncoder.encode("\nENDSEC;\nEND-ISO-10303-21;\n"));

  let total = 0;
  for (const part of parts) {
    total += part.byteLength;
  }
  const out = new Uint8Array(total);
  let offset = 0;
  for (const part of parts) {
    out.set(part, offset);
    offset += part.byteLength;
  }
  return out.buffer;
}

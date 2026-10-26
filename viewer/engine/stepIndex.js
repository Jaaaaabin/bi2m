/**
 * A lightweight, quote-aware index over an IFC STEP (ISO-10303-21 / "P21") file.
 *
 * Ported from NepomukWolf/vscode-ifc's `src/viewer/stepIndex.ts` (MIT licensed;
 * see engine/README.md) - adapted from Node's `Buffer` to the browser-native
 * `Uint8Array`, with TypeScript types dropped. Logic is otherwise unchanged.
 *
 * The index is built in a single byte scan and stores only `expressId -> byte
 * offset` (plus small buckets of relationship-instance offsets), so memory stays
 * proportional to the number of instances rather than the file size. Instance
 * text, types and references are sliced/parsed on demand. This keeps it usable on
 * very large federated models (hundreds of MB) where loading the whole file into a
 * JS string would be wasteful.
 *
 * STEP specifics handled here:
 *  - Single-quoted strings with `''` escaping. `#`, `;`, `(`, `)`, `,` inside a
 *    string must be ignored.
 *  - `/* ... *\/` comments between/within statements.
 *  - Instances span multiple lines and end at the first `;` at top level (STEP
 *    forbids unescaped `;` inside argument lists outside of strings).
 *
 * Pure JS, no DOM/framework dependency - unit-testable standalone (e.g. in Node).
 */

// Byte constants.
const HASH = 0x23; // #
const SEMI = 0x3b; // ;
const LPAREN = 0x28; // (
const RPAREN = 0x29; // )
const QUOTE = 0x27; // '
const SLASH = 0x2f; // /
const STAR = 0x2a; // *
const EQUALS = 0x3d; // =
const ZERO = 0x30;
const NINE = 0x39;

/** Relationship/style entity types we keep offset buckets for (inverse lookups). */
export const REL_AGGREGATES = "IFCRELAGGREGATES";
export const REL_NESTS = "IFCRELNESTS";
export const REL_VOIDS = "IFCRELVOIDSELEMENT";
export const REL_CONTAINED = "IFCRELCONTAINEDINSPATIALSTRUCTURE";
export const STYLED_ITEM = "IFCSTYLEDITEM";
const WATCHED_TYPES = new Set([REL_AGGREGATES, REL_NESTS, REL_VOIDS, REL_CONTAINED, STYLED_ITEM]);

/** Entity types a product's `Representation` attribute legitimately points at. */
const REPRESENTATION_HOLDERS = new Set(["IFCPRODUCTDEFINITIONSHAPE", "IFCPRODUCTREPRESENTATION"]);

/**
 * Spatial structure containers. They carry no geometry of their own (a storey,
 * building or site is an organizational grouping; a space is a void volume), so
 * we never render them *as elements* inside an assembly/floor walk - they'd just
 * obscure the real building elements.
 * They are still recursed *through* to reach the physical elements they contain
 * (`extractSubModel` follows `IfcRelContainedInSpatialStructure`), which is how a
 * "preview the whole floor" works. A spatial element with its *own* geometry (an
 * IfcSpace volume, IfcSite terrain) still previews directly via the proxy wrapper.
 */
const SPATIAL_CONTAINER_TYPES = new Set([
  "IFCPROJECT",
  "IFCSITE",
  "IFCBUILDING",
  "IFCBUILDINGSTOREY",
  "IFCSPACE",
  "IFCSPATIALZONE",
  "IFCSPATIALSTRUCTUREELEMENT",
  "IFCSPATIALELEMENT",
]);
/** The absolute project root - previewing it would mean the entire model. */
const PROJECT_ROOT_TYPE = "IFCPROJECT";

/**
 * `IfcRepresentation.RepresentationType` values that carry no surface/solid the
 * geometry engine would tessellate - curves, annotations, 2D, bounding boxes. A
 * representation whose type is one of these produces no mesh in web-ifc, so an
 * element whose *only* representations are these should not advertise a preview.
 * The set is an exclusion list (not a whitelist) so the long tail of solid types
 * - SweptSolid, Brep, AdvancedBrep, CSG, Clipping, Tessellation, SurfaceModel,
 * MappedRepresentation, ... - stays renderable without enumeration.
 */
const NON_RENDERABLE_REPRESENTATION_TYPES = new Set([
  "AXIS",
  "ANNOTATION",
  "ANNOTATION2D",
  "BOUNDINGBOX",
  "BOX",
  "FOOTPRINT",
  "PROFILE",
  "CURVE2D",
  "CURVE3D",
  "GEOMETRICCURVESET",
  "SURVEY",
  "REFERENCE",
  "LIGHTSOURCE",
]);

/**
 * Bare `IfcRepresentationItem` entity types that web-ifc tessellates into a
 * surface/solid mesh, mapped to the `IfcShapeRepresentation.RepresentationType`
 * we stamp on the synthetic product wrapper used to preview them (see
 * `subModel.js`). web-ifc keys meshing off the item entity itself, so the string
 * is mostly metadata - but our own renderable gate inspects it, so it must be a
 * non-excluded type.
 *
 * Scope is Tier A: solids and bounded surfaces. Curves (Polyline/CompositeCurve/
 * TrimmedCurve), unbounded surfaces (IfcPlane) and points are intentionally out -
 * they need a line/gizmo render path in the engines and are tracked separately.
 */
const RENDERABLE_ITEM_TYPES = new Map([
  // Swept area solids
  ["IFCEXTRUDEDAREASOLID", "SweptSolid"],
  ["IFCEXTRUDEDAREASOLIDTAPERED", "SweptSolid"],
  ["IFCREVOLVEDAREASOLID", "SweptSolid"],
  ["IFCREVOLVEDAREASOLIDTAPERED", "SweptSolid"],
  ["IFCSURFACECURVESWEPTAREASOLID", "AdvancedSweptSolid"],
  ["IFCFIXEDREFERENCESWEPTAREASOLID", "AdvancedSweptSolid"],
  ["IFCDIRECTRIXDERIVEDREFERENCESWEPTAREASOLID", "AdvancedSweptSolid"],
  ["IFCSWEPTDISKSOLID", "AdvancedSweptSolid"],
  ["IFCSWEPTDISKSOLIDPOLYGONAL", "AdvancedSweptSolid"],
  ["IFCSECTIONEDSOLID", "AdvancedSweptSolid"],
  ["IFCSECTIONEDSOLIDHORIZONTAL", "AdvancedSweptSolid"],
  // Boundary-representation solids and surface models
  ["IFCFACETEDBREP", "Brep"],
  ["IFCFACETEDBREPWITHVOIDS", "Brep"],
  ["IFCMANIFOLDSOLIDBREP", "Brep"],
  ["IFCADVANCEDBREP", "AdvancedBrep"],
  ["IFCADVANCEDBREPWITHVOIDS", "AdvancedBrep"],
  ["IFCSHELLBASEDSURFACEMODEL", "SurfaceModel"],
  ["IFCFACEBASEDSURFACEMODEL", "SurfaceModel"],
  // CSG / boolean / primitive solids
  ["IFCCSGSOLID", "CSG"],
  ["IFCBOOLEANRESULT", "CSG"],
  ["IFCBOOLEANCLIPPINGRESULT", "Clipping"],
  ["IFCBLOCK", "CSG"],
  ["IFCRECTANGULARPYRAMID", "CSG"],
  ["IFCRIGHTCIRCULARCONE", "CSG"],
  ["IFCRIGHTCIRCULARCYLINDER", "CSG"],
  ["IFCSPHERE", "CSG"],
  // Tessellated geometry
  ["IFCTRIANGULATEDFACESET", "Tessellation"],
  ["IFCPOLYGONALFACESET", "Tessellation"],
  ["IFCTRIANGULATEDIRREGULARNETWORK", "Tessellation"],
]);

function isDigit(b) {
  return b >= ZERO && b <= NINE;
}

function isKeywordByte(b) {
  return (
    (b >= 0x41 && b <= 0x5a) || // A-Z
    (b >= 0x61 && b <= 0x7a) || // a-z
    (b >= ZERO && b <= NINE) ||
    b === 0x5f // _
  );
}

/**
 * True ISO-8859-1 (latin1) byte->codepoint decode: byte value N maps directly to
 * code point N for every N in 0-255. Deliberately NOT `TextDecoder("latin1")` -
 * per the WHATWG Encoding spec, browsers alias that label to windows-1252, which
 * substitutes printable characters into the 0x80-0x9F range instead of the true
 * latin1 C1 controls. Using a manual loop keeps this byte-identical to Node's
 * `Buffer.toString("latin1")`, which the original implementation relies on for
 * exact source-byte round-tripping.
 */
function latin1Decode(buf, start, end) {
  const chars = new Array(end - start);
  for (let i = start; i < end; i++) {
    chars[i - start] = String.fromCharCode(buf[i]);
  }
  return chars.join("");
}

export class StepFileIndex {
  /** Cache for `decompositionChildren()`; built on first descendant lookup. */
  #childrenByParent;

  constructor(buf, headerEndOffset, startById, relBuckets, schema, projectId) {
    this.buf = buf;
    /** Byte offset immediately after the `DATA;` token (start of data section). */
    this.headerEndOffset = headerEndOffset;
    this.startById = startById;
    this.relBuckets = relBuckets;
    this.schema = schema;
    this.projectId = projectId;
  }

  get instanceCount() {
    return this.startById.size;
  }

  stats() {
    return { instanceCount: this.instanceCount, schema: this.schema, projectId: this.projectId };
  }

  hasId(id) {
    return this.startById.has(id);
  }

  /** Verbatim header bytes (`ISO-10303-21; ... DATA;`), preserving the schema. */
  headerBytes() {
    return this.buf.subarray(0, this.headerEndOffset);
  }

  /** Raw bytes of the full instance `#id=KEYWORD(...);`, or undefined if unknown.
   *  A view into the source buffer - copy before mutating. */
  sliceInstanceBytes(id) {
    const start = this.startById.get(id);
    if (start === undefined) {
      return undefined;
    }
    return this.buf.subarray(start, findStatementEnd(this.buf, start));
  }

  /** The full instance text `#id=KEYWORD(...);`, or undefined if id is unknown. */
  sliceInstance(id) {
    const start = this.startById.get(id);
    if (start === undefined) {
      return undefined;
    }
    const end = findStatementEnd(this.buf, start);
    return latin1Decode(this.buf, start, end);
  }

  /** Uppercased entity keyword for an id (e.g. `IFCWALLSTANDARDCASE`). */
  getType(id) {
    const start = this.startById.get(id);
    if (start === undefined) {
      return undefined;
    }
    return readTypeKeyword(this.buf, start);
  }

  /** Forward `#ref` ids appearing in this instance's arguments (excludes self). */
  refsOf(id) {
    const text = this.sliceInstance(id);
    if (text === undefined) {
      return [];
    }
    const body = instanceBody(text);
    return collectRefs(body);
  }

  /** Top-level (paren/quote-aware) argument strings of an instance. */
  argsOf(id) {
    const text = this.sliceInstance(id);
    if (text === undefined) {
      return [];
    }
    return splitTopLevelArgs(instanceBody(text));
  }

  /** 0-based editor position of an id's `#` token (for reveal/scroll-to). */
  positionOf(id) {
    const start = this.startById.get(id);
    if (start === undefined) {
      return undefined;
    }
    let line = 0;
    let lineStart = 0;
    for (let i = 0; i < start; i++) {
      if (this.buf[i] === 0x0a) {
        line++;
        lineStart = i + 1;
      }
    }
    return { line, character: start - lineStart };
  }

  /** The `Name` attribute (arg index 2 for IfcRoot entities), unquoted. */
  nameOf(id) {
    const raw = this.argsOf(id)[2];
    if (!raw || raw === "$" || raw === "*" || raw[0] !== "'") {
      return undefined;
    }
    return raw.slice(1, raw.endsWith("'") ? -1 : undefined).replace(/''/g, "'");
  }

  /**
   * True if the instance is a geometric product whose representation the engine
   * would actually mesh - i.e. it should advertise a 3D preview. This deliberately
   * mirrors what the renderer produces, so the "eye" and the geometry agree:
   *
   *  1. The `Representation` attribute sits at index 6 (`GlobalId, OwnerHistory,
   *     Name, Description, ObjectType, ObjectPlacement, Representation`) for *every*
   *     product across IFC2X3/4/4X3 - schema-agnostic, covering MEP, furniture,
   *     proxies, assemblies, reinforcement, ... rather than a fixed type list. We
   *     require it to resolve to an `IfcProductDefinitionShape`/`IfcProductRepre-
   *     sentation`; this rejects non-products that merely carry a `#ref` at index 6
   *     (e.g. `IfcGeometricRepresentationSubContext`, whose `ParentContext` lands
   *     there and would otherwise yield a preview with no geometry).
   *  2. At least one of its representations must be renderable - not a curve/
   *     annotation/2D/bounding-box `RepresentationType` the engine skips, which
   *     would likewise produce an empty preview (e.g. axis-only members, grids).
   */
  hasRenderableRepresentation(id) {
    const args = this.argsOf(id);
    if (args.length < 7) {
      return false;
    }
    const representation = args[6];
    if (!representation || representation === "$" || representation === "*") {
      return false;
    }
    const shapeId = collectRefs(representation)[0];
    if (shapeId === undefined) {
      return false;
    }
    const shapeType = this.getType(shapeId);
    if (!shapeType || !REPRESENTATION_HOLDERS.has(shapeType)) {
      return false;
    }
    // IfcProductRepresentation(Name, Description, Representations) - list at index 2.
    const reps = collectRefs(this.argsOf(shapeId)[2] ?? "");
    return reps.some((repId) => this.isRenderableRepresentation(repId));
  }

  /**
   * True if `id` is a bare `IfcRepresentationItem` the engines mesh on its own
   * (a solid or bounded surface - see `RENDERABLE_ITEM_TYPES`), rather than a
   * product. These have no `Representation` attribute, so `extractSubModel` wraps
   * them in a synthetic product to feed the (product-only) geometry pipelines.
   */
  isRenderableGeometryItem(id) {
    return this.geometryItemRepType(id) !== undefined;
  }

  /**
   * The `IfcShapeRepresentation.RepresentationType` to stamp when wrapping a bare
   * geometry item for preview, or undefined if `id` is not a meshable item type.
   */
  geometryItemRepType(id) {
    const type = this.getType(id);
    return type ? RENDERABLE_ITEM_TYPES.get(type) : undefined;
  }

  /**
   * True if `id` is a decomposition/assembly parent (e.g. IfcStair, IfcRamp,
   * IfcRoof, IfcCurtainWall, IfcElementAssembly) that carries no own geometry but
   * whose `IfcRelAggregates`/`IfcRelNests` descendants do. Such elements render
   * fine - `extractSubModel`'s `includeChildren` walk pulls the children's
   * geometry - so the preview lens should be offered for them too. Walks the
   * (cached) parent->children graph transitively, cycle-guarded.
   */
  hasRenderableDescendant(id) {
    if (this.getType(id) === PROJECT_ROOT_TYPE) {
      return false; // the whole model is not a "preview"
    }
    const children = this.decompositionChildren();
    const seen = new Set([id]);
    const stack = [...(children.get(id) ?? [])];
    while (stack.length > 0) {
      const child = stack.pop();
      if (seen.has(child)) {
        continue;
      }
      seen.add(child);
      if (this.isRenderablePhysicalElement(child)) {
        return true;
      }
      const grandchildren = children.get(child);
      if (grandchildren) {
        stack.push(...grandchildren);
      }
    }
    return false;
  }

  /**
   * A descendant worth rendering inside an assembly/floor: something with real
   * geometry that is itself an element, not a spatial container/space (those are
   * recursed through but never drawn - see `SPATIAL_CONTAINER_TYPES`).
   */
  isRenderablePhysicalElement(id) {
    if (this.isSpatialContainer(id)) {
      return false;
    }
    return this.hasRenderableRepresentation(id) || this.isRenderableGeometryItem(id);
  }

  /** True if `id` is a spatial structure element (project/site/building/storey/space). */
  isSpatialContainer(id) {
    const type = this.getType(id);
    return type !== undefined && SPATIAL_CONTAINER_TYPES.has(type);
  }

  /** Decomposition + spatial-containment children of `id` (cached graph). */
  decompositionChildrenOf(id) {
    return this.decompositionChildren().get(id) ?? [];
  }

  /**
   * Single source of truth for "does this element get a Preview in 3D button?":
   *  - its own geometry, or a bare geometry item we can wrap; or
   *  - (when child decomposition is on) an assembly/spatial container whose
   *    descendants carry geometry - IfcStair flights, a whole building storey, ...
   */
  isPreviewable(id, includeChildren) {
    return (
      this.hasRenderableRepresentation(id) ||
      this.isRenderableGeometryItem(id) ||
      (includeChildren && this.hasRenderableDescendant(id))
    );
  }

  /**
   * Lazily-built parent -> children map spanning both decomposition
   * (`IfcRelAggregates`/`IfcRelNests`: RelatingObject@4 -> RelatedObjects@5) and
   * spatial containment (`IfcRelContainedInSpatialStructure`: RelatingStructure@5
   * -> RelatedElements@4 - note the reversed argument order). Walking both lets a
   * storey/building reach the physical elements placed on it, not just its spaces.
   */
  decompositionChildren() {
    if (this.#childrenByParent) {
      return this.#childrenByParent;
    }
    const map = new Map();
    const addEdges = (parent, kids) => {
      if (parent === undefined || kids.length === 0) {
        return;
      }
      const existing = map.get(parent);
      if (existing) {
        existing.push(...kids);
      } else {
        map.set(parent, [...kids]);
      }
    };
    for (const typeName of [REL_AGGREGATES, REL_NESTS]) {
      for (const relId of this.relIdsOfType(typeName)) {
        const args = this.argsOf(relId);
        addEdges(collectRefs(args[4] ?? "")[0], collectRefs(args[5] ?? ""));
      }
    }
    for (const relId of this.relIdsOfType(REL_CONTAINED)) {
      const args = this.argsOf(relId);
      addEdges(collectRefs(args[5] ?? "")[0], collectRefs(args[4] ?? ""));
    }
    this.#childrenByParent = map;
    return map;
  }

  /** Largest express id present, used to allocate collision-free synthetic ids. */
  maxExpressId() {
    let max = 0;
    for (const id of this.startById.keys()) {
      if (id > max) {
        max = id;
      }
    }
    return max;
  }

  /** A 3D `IfcGeometricRepresentationContext` to anchor a synthetic shape rep, if any. */
  geometricContextId() {
    return this.findFirstOfType(["IFCGEOMETRICREPRESENTATIONCONTEXT"]);
  }

  /** True if a representation's `RepresentationType` is one the engine tessellates. */
  isRenderableRepresentation(repId) {
    // IfcRepresentation(ContextOfItems, RepresentationIdentifier, RepresentationType, Items).
    const repType = this.argsOf(repId)[2];
    if (repType?.[0] !== "'") {
      // Missing/unspecified type: stay permissive rather than hide real geometry.
      return true;
    }
    const value = repType.slice(1, repType.endsWith("'") ? -1 : undefined).toUpperCase();
    return !NON_RENDERABLE_REPRESENTATION_TYPES.has(value);
  }

  /** First express id (in file order) whose entity type matches one of `types`. */
  findFirstOfType(types) {
    const wanted = new Set();
    for (const t of types) {
      wanted.add(t.toUpperCase());
    }
    for (const [id, start] of this.startById) {
      const type = readTypeKeyword(this.buf, start);
      if (type && wanted.has(type)) {
        return id;
      }
    }
    return undefined;
  }

  /** Express ids of every instance of a watched relationship/style type. */
  relIdsOfType(typeName) {
    const offsets = this.relBuckets.get(typeName);
    if (!offsets) {
      return [];
    }
    const ids = [];
    for (const off of offsets) {
      const id = readId(this.buf, off);
      if (id !== undefined) {
        ids.push(id);
      }
    }
    return ids;
  }

  /** Build an index from raw IFC file bytes (a `Uint8Array`). */
  static build(buf) {
    // Header is always small; read a bounded prefix to find `DATA;` and schema.
    const prefixLen = Math.min(buf.length, 1 << 16);
    const prefix = latin1Decode(buf, 0, prefixLen);
    const dataMatch = /\bDATA\s*;/i.exec(prefix);
    if (!dataMatch) {
      throw new Error("Not a STEP/IFC data file: no DATA section found.");
    }
    const headerEndOffset = dataMatch.index + dataMatch[0].length;
    const schemaMatch = /FILE_SCHEMA\s*\(\s*\(\s*'([^']+)'/i.exec(prefix);
    const schema = schemaMatch ? schemaMatch[1] : undefined;

    const startById = new Map();
    const relBuckets = new Map();
    let projectId;

    let pos = headerEndOffset;
    const len = buf.length;
    while (pos < len) {
      pos = skipTrivia(buf, pos);
      if (pos >= len) {
        break;
      }
      const b = buf[pos];
      if (b === HASH) {
        const start = pos;
        const id = readId(buf, start);
        const end = findStatementEnd(buf, start);
        if (id !== undefined) {
          startById.set(id, start);
          const type = readTypeKeyword(buf, start);
          if (type) {
            if (type === "IFCPROJECT" && projectId === undefined) {
              projectId = id;
            }
            if (WATCHED_TYPES.has(type)) {
              const bucket = relBuckets.get(type);
              if (bucket) {
                bucket.push(start);
              } else {
                relBuckets.set(type, [start]);
              }
            }
          }
        }
        pos = end;
      } else if (matchesKeyword(buf, pos, "ENDSEC")) {
        break;
      } else {
        // Unexpected token in DATA section; skip to the next statement end.
        pos = findStatementEnd(buf, pos);
      }
    }

    return new StepFileIndex(buf, headerEndOffset, startById, relBuckets, schema, projectId);
  }
}

/** Skip whitespace and `/* *\/` comments; returns the next significant offset. */
function skipTrivia(buf, pos) {
  const len = buf.length;
  while (pos < len) {
    const b = buf[pos];
    if (b === SLASH && pos + 1 < len && buf[pos + 1] === STAR) {
      pos += 2;
      while (pos + 1 < len && !(buf[pos] === STAR && buf[pos + 1] === SLASH)) {
        pos++;
      }
      pos += 2;
      continue;
    }
    if (b === 0x20 || b === 0x09 || b === 0x0a || b === 0x0d) {
      pos++;
      continue;
    }
    return pos;
  }
  return pos;
}

/** Offset just past the terminating `;` of the statement beginning at `from`. */
function findStatementEnd(buf, from) {
  const len = buf.length;
  let pos = from;
  let inString = false;
  while (pos < len) {
    const b = buf[pos];
    if (inString) {
      if (b === QUOTE) {
        if (pos + 1 < len && buf[pos + 1] === QUOTE) {
          pos += 2; // escaped quote
          continue;
        }
        inString = false;
      }
      pos++;
      continue;
    }
    if (b === QUOTE) {
      inString = true;
      pos++;
      continue;
    }
    if (b === SLASH && pos + 1 < len && buf[pos + 1] === STAR) {
      pos += 2;
      while (pos + 1 < len && !(buf[pos] === STAR && buf[pos + 1] === SLASH)) {
        pos++;
      }
      pos += 2;
      continue;
    }
    if (b === SEMI) {
      return pos + 1;
    }
    pos++;
  }
  return len;
}

/** Parse `#<digits>` at `start`; undefined if not a valid id. */
function readId(buf, start) {
  if (buf[start] !== HASH) {
    return undefined;
  }
  let pos = start + 1;
  let value = 0;
  let any = false;
  while (pos < buf.length && isDigit(buf[pos])) {
    value = value * 10 + (buf[pos] - ZERO);
    any = true;
    pos++;
  }
  return any ? value : undefined;
}

/** Uppercased entity keyword following `#id=` for the instance at `start`. */
function readTypeKeyword(buf, start) {
  const len = buf.length;
  let pos = start + 1;
  while (pos < len && isDigit(buf[pos])) {
    pos++;
  }
  pos = skipTrivia(buf, pos);
  if (pos >= len || buf[pos] !== EQUALS) {
    return undefined;
  }
  pos = skipTrivia(buf, pos + 1);
  const ksStart = pos;
  while (pos < len && isKeywordByte(buf[pos])) {
    pos++;
  }
  if (pos === ksStart) {
    return undefined;
  }
  return latin1Decode(buf, ksStart, pos).toUpperCase();
}

/** Case-insensitive check that `word` begins at `pos` (word-boundary aware). */
function matchesKeyword(buf, pos, word) {
  if (pos + word.length > buf.length) {
    return false;
  }
  for (let i = 0; i < word.length; i++) {
    const b = buf[pos + i];
    const upper = b >= 0x61 && b <= 0x7a ? b - 0x20 : b;
    if (upper !== word.charCodeAt(i)) {
      return false;
    }
  }
  const after = pos + word.length < buf.length ? buf[pos + word.length] : 0;
  return !isKeywordByte(after);
}

/** Substring between the outermost parentheses of an instance text. */
export function instanceBody(text) {
  const open = text.indexOf("(");
  if (open < 0) {
    return "";
  }
  let depth = 0;
  let inString = false;
  for (let i = open; i < text.length; i++) {
    const c = text.charCodeAt(i);
    if (inString) {
      if (c === QUOTE) {
        if (text.charCodeAt(i + 1) === QUOTE) {
          i++;
          continue;
        }
        inString = false;
      }
      continue;
    }
    if (c === QUOTE) {
      inString = true;
    } else if (c === LPAREN) {
      depth++;
    } else if (c === RPAREN) {
      depth--;
      if (depth === 0) {
        return text.slice(open + 1, i);
      }
    }
  }
  return text.slice(open + 1);
}

/** Split a parenthesised body into top-level args (paren/quote-aware). */
export function splitTopLevelArgs(body) {
  const args = [];
  let depth = 0;
  let inString = false;
  let start = 0;
  for (let i = 0; i < body.length; i++) {
    const c = body.charCodeAt(i);
    if (inString) {
      if (c === QUOTE) {
        if (body.charCodeAt(i + 1) === QUOTE) {
          i++;
          continue;
        }
        inString = false;
      }
      continue;
    }
    if (c === QUOTE) {
      inString = true;
    } else if (c === LPAREN) {
      depth++;
    } else if (c === RPAREN) {
      depth--;
    } else if (c === 0x2c /* , */ && depth === 0) {
      args.push(body.slice(start, i).trim());
      start = i + 1;
    }
  }
  args.push(body.slice(start).trim());
  return args;
}

/** Collect all `#<digits>` references in a string, ignoring those in strings. */
export function collectRefs(s) {
  const refs = [];
  let inString = false;
  for (let i = 0; i < s.length; i++) {
    const c = s.charCodeAt(i);
    if (inString) {
      if (c === QUOTE) {
        if (s.charCodeAt(i + 1) === QUOTE) {
          i++;
          continue;
        }
        inString = false;
      }
      continue;
    }
    if (c === QUOTE) {
      inString = true;
      continue;
    }
    if (c === HASH) {
      let j = i + 1;
      let value = 0;
      let any = false;
      while (j < s.length && s.charCodeAt(j) >= ZERO && s.charCodeAt(j) <= NINE) {
        value = value * 10 + (s.charCodeAt(j) - ZERO);
        any = true;
        j++;
      }
      if (any) {
        refs.push(value);
        i = j - 1;
      }
    }
  }
  return refs;
}

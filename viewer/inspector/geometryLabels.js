// ======== Geometry labels: what kind of shape defines each element ========
// The inspector's "Geometry:" row ("Swept Solid", "Tessellated Mesh", ...).
// ThatOpen's properties cannot answer it: they leave out every geometry
// entity, so an element's Representation attribute points at an
// IfcProductDefinitionShape the viewer never sees. This module reads that
// chain straight from the IFC (STEP) text, once per loaded model, and keeps
// only the answer - one small record per shape - so the file's bytes can be
// let go.
//
// Keyed by the IfcProductDefinitionShape's express id, which the selected
// element's own properties carry (`Representation`), so no product list is
// needed here. Per shape: the "Body" IfcShapeRepresentation (else the first),
// its RepresentationType, and the classes of its items - an IfcMappedItem is
// followed one level to the shape it instances, so a typed door reports
// "IFCFACETEDBREP" rather than "IFCMAPPEDITEM".
//
// Two passes over the bytes: the first keeps the arguments of the four entity
// kinds the chain runs through, the second only the class names of the items
// those point at. Pure (no DOM, no Worker), so Node tests run it directly;
// geometryLabels.worker.js runs it off the main thread.

const KEEP = new Set([
  "IFCPRODUCTDEFINITIONSHAPE",
  "IFCSHAPEREPRESENTATION",
  "IFCMAPPEDITEM",
  "IFCREPRESENTATIONMAP",
]);

const HASH = 0x23; // #
const EQUALS = 0x3d; // =
const QUOTE = 0x27; // '
const SEMICOLON = 0x3b; // ;
const OPEN = 0x28; // (
const SLASH = 0x2f; // /
const STAR = 0x2a; // *

const latin1 = new TextDecoder("latin1");

function isSpace(byte) {
  return byte === 0x20 || byte === 0x0a || byte === 0x0d || byte === 0x09;
}

function isKeywordByte(byte) {
  return (byte >= 0x41 && byte <= 0x5a) || (byte >= 0x30 && byte <= 0x39) || byte === 0x5f;
}

/** Offset just after "DATA;" (0 if absent), so header entities are never read. */
function dataStart(bytes) {
  const marker = [0x44, 0x41, 0x54, 0x41, SEMICOLON]; // DATA;
  outer: for (let i = 0; i + marker.length <= bytes.length; i++) {
    for (let k = 0; k < marker.length; k++) if (bytes[i + k] !== marker[k]) continue outer;
    return i + marker.length;
  }
  return 0;
}

/**
 * Calls `visit(id, keywordStart, keywordEnd, argsStart, end)` for every `#id=KEYWORD(...);`
 * instance in the DATA section; `end` is the offset of its `;`. Quote-aware:
 * a `;` inside a string does not end an instance ('' is an escaped quote,
 * which simply toggles twice).
 */
function scanInstances(bytes, visit) {
  let i = dataStart(bytes);
  const n = bytes.length;
  while (i < n) {
    const byte = bytes[i];
    if (isSpace(byte)) {
      i++;
      continue;
    }
    if (byte === SLASH && bytes[i + 1] === STAR) {
      const close = bytes.indexOf(SLASH, i + 2);
      i = close < 0 ? n : close + 1;
      continue;
    }
    if (byte !== HASH) {
      // Not an instance (ENDSEC;, END-ISO-10303-21;): skip to the next `;`.
      const next = bytes.indexOf(SEMICOLON, i);
      i = next < 0 ? n : next + 1;
      continue;
    }
    let j = i + 1;
    let id = 0;
    while (j < n && bytes[j] >= 0x30 && bytes[j] <= 0x39) id = id * 10 + (bytes[j++] - 0x30);
    while (j < n && isSpace(bytes[j])) j++;
    if (bytes[j] !== EQUALS) {
      i = j;
      continue;
    }
    j++;
    while (j < n && isSpace(bytes[j])) j++;
    const kwStart = j;
    while (j < n && isKeywordByte(bytes[j])) j++;
    const kwEnd = j;
    let inString = false;
    let argsStart = -1;
    for (; j < n; j++) {
      const c = bytes[j];
      if (c === QUOTE) inString = !inString;
      else if (!inString) {
        if (c === OPEN && argsStart < 0) argsStart = j + 1;
        else if (c === SEMICOLON) break;
      }
    }
    visit(id, kwStart, kwEnd, argsStart, j);
    i = j + 1;
  }
}

/** Top-level arguments of an instance's argument text, split on depth-0 commas. */
export function splitArgs(text) {
  const out = [];
  let depth = 0;
  let inString = false;
  let start = 0;
  for (let k = 0; k < text.length; k++) {
    const c = text[k];
    if (c === "'") inString = !inString;
    else if (!inString) {
      if (c === "(") depth++;
      else if (c === ")") {
        if (depth === 0) {
          out.push(text.slice(start, k).trim());
          return out;
        }
        depth--;
      } else if (c === "," && depth === 0) {
        out.push(text.slice(start, k).trim());
        start = k + 1;
      }
    }
  }
  out.push(text.slice(start).trim());
  return out;
}

/** Every `#id` reference in an argument (a single ref or a list), in order. */
export function refsIn(arg) {
  const out = [];
  for (const match of (arg ?? "").matchAll(/#(\d+)/g)) out.push(Number(match[1]));
  return out;
}

function unquote(arg) {
  if (!arg || arg[0] !== "'") return undefined;
  return arg.slice(1, arg.endsWith("'") ? -1 : undefined).replace(/''/g, "'");
}

/**
 * @typedef {{ identifier?: string, type?: string, itemClasses: string[] }} GeometryLabel
 * @param {Uint8Array} bytes the whole IFC file
 * @returns {Map<number, GeometryLabel>} IfcProductDefinitionShape id -> label
 */
export function buildGeometryLabels(bytes) {
  /** @type {Map<number, {keyword: string, args: string[]}>} */
  const kept = new Map();
  scanInstances(bytes, (id, kwStart, kwEnd, argsStart, end) => {
    if (argsStart < 0) return;
    const keyword = latin1.decode(bytes.subarray(kwStart, kwEnd));
    if (!KEEP.has(keyword)) return;
    kept.set(id, { keyword, args: splitArgs(latin1.decode(bytes.subarray(argsStart, end))) });
  });

  // IfcShapeRepresentation(ContextOfItems, RepresentationIdentifier, RepresentationType, Items)
  const chosenRep = new Map(); // shape id -> representation id
  const wanted = new Set(); // item ids whose class names pass 2 reads
  const itemsOfRep = (repId) => refsIn(kept.get(repId)?.args[3]);
  const mappedItemsOf = (itemId) => {
    // IfcMappedItem(MappingSource, ...) -> IfcRepresentationMap(Origin, MappedRepresentation)
    const map = kept.get(refsIn(kept.get(itemId)?.args[0])[0]);
    return map ? itemsOfRep(refsIn(map.args[1])[0]) : [];
  };
  for (const [id, entity] of kept) {
    if (entity.keyword !== "IFCPRODUCTDEFINITIONSHAPE") continue;
    // IfcProductDefinitionShape(Name, Description, Representations)
    const reps = refsIn(entity.args[2]).filter(
      (r) => kept.get(r)?.keyword === "IFCSHAPEREPRESENTATION",
    );
    if (!reps.length) continue;
    const rep = reps.find((r) => unquote(kept.get(r).args[1]) === "Body") ?? reps[0];
    chosenRep.set(id, rep);
    for (const item of itemsOfRep(rep)) {
      wanted.add(item);
      if (kept.get(item)?.keyword === "IFCMAPPEDITEM")
        for (const inner of mappedItemsOf(item)) wanted.add(inner);
    }
  }

  const classOf = new Map();
  if (wanted.size) {
    scanInstances(bytes, (id, kwStart, kwEnd) => {
      if (wanted.has(id)) classOf.set(id, latin1.decode(bytes.subarray(kwStart, kwEnd)));
    });
  }

  const labels = new Map();
  for (const [shapeId, rep] of chosenRep) {
    const args = kept.get(rep).args;
    const itemClasses = itemsOfRep(rep).map((item) => {
      const cls = classOf.get(item);
      if (cls !== "IFCMAPPEDITEM") return cls;
      const inner = mappedItemsOf(item)
        .map((x) => classOf.get(x))
        .filter(Boolean);
      return inner.length ? inner.join("+") : cls;
    });
    labels.set(shapeId, { identifier: unquote(args[1]), type: unquote(args[2]), itemClasses });
  }
  return labels;
}

/** Friendlier names for IfcShapeRepresentation.RepresentationType values. */
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

/** A human-readable name for a RepresentationType, or the raw value if unmapped. */
export function friendlyTypeLabel(type) {
  if (!type) return undefined;
  return FRIENDLY_TYPE_LABELS[type] || type;
}

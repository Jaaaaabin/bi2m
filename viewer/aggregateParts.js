// ======== Members whose geometry lives in their parts ========
// An IFC aggregate - IfcStair, IfcRamp, IfcRoof, an IfcCurtainWall - often
// has no shape of its own: its geometry is carried by the elements it is
// decomposed into (IfcRelAggregates: stair flights, landings, railings, roof
// slabs, plates). Detectors name the aggregate, because that is the element
// the rule is about; the viewer can only colour, ghost and frame what has
// geometry. Measured on data/example_autcon.ifc (2026-10-26): every
// IfcStair, IfcRamp and IfcRoof member resolved to nothing, so a Refer on a
// stair-run record showed only its grey context doors and framed those.
//
// This module replaces such a member by its parts, recursively, keeping the
// member's role. A member that has geometry itself is left alone, and so is a
// spatial element (site, building, storey, space): a storey "decomposes" into
// its spaces, and colouring every space of a storey is not what a record that
// names the storey means. Pure: the caller supplies the model lookups.

/**
 * @typedef {{ guid: string, role?: string, [key: string]: any }} Member
 * @typedef {object} PartsLookup
 * @property {(guid: string) => boolean} hasGeometry
 * @property {(guid: string) => number | undefined} expressIdOf   any entity with a GlobalId
 * @property {(expressID: number) => boolean} isSpatial
 * @property {(expressID: number) => number[]} partsOf            IsDecomposedBy, one level
 * @property {(expressID: number) => string | undefined} guidOf
 */

/**
 * The GUIDs with geometry that stand for `guid`: itself if it has geometry,
 * otherwise its parts (at any depth) that do. Empty when there are none.
 * @param {string} guid
 * @param {PartsLookup} lookup
 * @returns {string[]}
 */
export function geometryGuidsFor(guid, lookup) {
  if (lookup.hasGeometry(guid)) return [guid];
  const root = lookup.expressIdOf(guid);
  if (root === undefined || lookup.isSpatial(root)) return [];
  const found = [];
  const seen = new Set([root]);
  const stack = [...lookup.partsOf(root)];
  while (stack.length) {
    const id = stack.pop();
    if (seen.has(id) || lookup.isSpatial(id)) continue;
    seen.add(id);
    const partGuid = lookup.guidOf(id);
    if (partGuid && lookup.hasGeometry(partGuid)) found.push(partGuid);
    else stack.push(...lookup.partsOf(id));
  }
  return found.sort();
}

/**
 * The members with each geometry-less aggregate replaced by its parts, each
 * part keeping the aggregate's role and recording it in `partOf`. Members
 * without geometry and without parts stay as they are (nothing to draw
 * either way). Returns the input array itself when nothing changed.
 * @param {Member[]} members
 * @param {PartsLookup} lookup
 * @returns {Member[]}
 */
export function expandMembersToParts(members, lookup) {
  let changed = false;
  const out = [];
  for (const member of members) {
    const guids = geometryGuidsFor(member.guid, lookup);
    if (guids.length === 1 && guids[0] === member.guid) {
      out.push(member);
    } else if (guids.length) {
      changed = true;
      for (const guid of guids) out.push({ ...member, guid, partOf: member.guid });
    } else {
      out.push(member);
    }
  }
  return changed ? out : members;
}

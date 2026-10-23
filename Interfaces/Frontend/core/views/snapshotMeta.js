// ======== Snapshot metadata: the GUIDs a picture shows (2026-10-22) ========
// The pure half of the "snapshot with metadata" feature (snapshot.js,
// views/visibility.js visibleElements): the id encoding the whole-model ID
// pass paints into instance colours, and the document written next to the
// PNG when the camera panel's Meta switch is on.
//
// The document is deliberately smaller than a BCF viewpoint: GUIDs and the
// few numbers needed to join them to the picture. `selected` is what the
// viewer has referred as the subject: every non-context member of an intent
// (roles member, base, top, intermediate: the judged elements), or a pasted
// GUID list; the intent's role-"context"
// members (the related elements a Neufert facet lists, painted base grey)
// go to `selectedContext`, never into `selected`. `visible` is every
// element with at least `minPixels` of its own pixels in the picture after
// occlusion; `ghosted` the elements on screen only as the Refer's ghost
// (transparent material, the picture-faithful rule chosen on 2026-10-22: a
// ghost neither occludes nor counts as visible). "Context" is kept for the
// member role alone, so the two never get confused. The two lists the owner
// asked for are derived: `selectedVisible` and `visibleOnly` (visible but
// not selected). `selectedHidden` says which referred elements the picture
// does not show at all, which is what a batch driver needs to reject a
// frame.
//
// Ids: 24 bits across the red, green and blue bytes of an instance colour,
// 1 .. 16,777,214. Zero is the cleared background ("nothing"); 0xFFFFFF is
// the white a mesh without an instance colour (or an overlay line) renders
// under the pass's white override material ("uncounted"). Either sentinel
// decodes to -1.

export const SNAPSHOT_META_SCHEMA = 1;
export const VISIBLE_RULE = "ghost-transparent";
/** Pass C draws the ghost meshes solid, so a ghost behind another ghost is not listed. */
export const GHOSTED_RULE = "front-most ghost layer";
export const ID_NONE = 0;
export const ID_UNCOUNTED = 0xffffff;

/** The three colour channels (0..1) that carry `id` through the pass. */
export function encodeId(id) {
  if (!Number.isInteger(id) || id <= ID_NONE || id >= ID_UNCOUNTED) throw new RangeError(`snapshot id out of range: ${id}`);
  return [(id & 0xff) / 255, ((id >> 8) & 0xff) / 255, ((id >> 16) & 0xff) / 255];
}

/** The id a read-back pixel carries, or -1 for the two sentinels. */
export function decodeId(r, g, b) {
  const id = r + (g << 8) + (b << 16);
  return id === ID_NONE || id === ID_UNCOUNTED ? -1 : id;
}

/**
 * The metadata document for one picture.
 *
 * @param {{
 *   fileKey: string | null, isStreamed?: boolean,
 *   image: {file: string, width: number, height: number},
 *   pose: Record<string, any> | null,
 *   selected: string[], selectedContext?: string[],
 *   visible: Array<{guid: string, px: number}>,
 *   ghosted: Array<{guid: string, px: number}>,
 *   minPixels: number, transparency?: number | null, unresolved?: number,
 *   capturedAt?: string,
 * }} parts
 */
export function buildSnapshotMetadata(parts) {
  const selected = [...new Set(parts.selected ?? [])].sort();
  const selectedSet0 = new Set(selected);
  const selectedContext = [...new Set(parts.selectedContext ?? [])].filter((g) => !selectedSet0.has(g)).sort();
  const visible = [...(parts.visible ?? [])].sort((a, b) => (a.guid < b.guid ? -1 : a.guid > b.guid ? 1 : 0));
  const ghosted = [...(parts.ghosted ?? [])].sort((a, b) => (a.guid < b.guid ? -1 : a.guid > b.guid ? 1 : 0));
  const visibleGuids = new Set(visible.map((v) => v.guid));
  const selectedSet = new Set(selected);
  return {
    schema: SNAPSHOT_META_SCHEMA,
    capturedAt: parts.capturedAt ?? new Date().toISOString(),
    model: { fileKey: parts.fileKey ?? null, isStreamed: !!parts.isStreamed },
    image: { file: parts.image.file, width: parts.image.width, height: parts.image.height },
    pose: parts.pose ?? null,
    visibleRule: {
      name: VISIBLE_RULE,
      minPixels: parts.minPixels,
      ghost: "material opacity below 1",
      ghostedRule: GHOSTED_RULE,
      transparency: parts.transparency ?? null,
      unresolved: parts.unresolved ?? 0,
    },
    selected,
    selectedContext,
    visible,
    ghosted,
    selectedVisible: selected.filter((g) => visibleGuids.has(g)),
    selectedHidden: selected.filter((g) => !visibleGuids.has(g)),
    visibleOnly: visible.map((v) => v.guid).filter((g) => !selectedSet.has(g)),
  };
}

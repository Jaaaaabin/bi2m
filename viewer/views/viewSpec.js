// ======== ViewSpec: one declarative, serializable description of a view ========
// Each view gets one record; this is the half of that record a caller WRITES.
// A spec says what to look at (scope), what directions are measured against
// (frame), where the camera stands (direction), how tightly it frames
// (framing), through what lens, with which cuts and scene settings, at what
// image size. The other half - what the camera actually did - is the record
// applyView.js measures after the fact.
//
// EVERY DEFAULT IS TODAY'S BEHAVIOUR. An empty spec `{}` resolves to: frame
// the current scope (an active Refer, else the whole building), keep the
// camera's orbit direction, the Context slider's current value, the edge
// padding cameraViews.js has always used, the current projection and lens, no
// cut, no scene change, the live canvas. The camera system's behaviour is
// locked, and this is how the presets and Refer stay byte-identical: they are
// specs whose every unset field falls through to what they did before.
//
// Every planned view field is accepted and validated here. The one exception
// is `scene.outlines`, which needs @thatopen's PostproductionRenderer in
// place of the SimpleRenderer the viewer uses and is refused by name until
// that swap is decided.
//
// Pure: no THREE, no DOM, unit-tested in tests/unit/viewSpec.test.js.

export const VIEW_SPEC_SCHEMA = 1;

export const SCOPE_KINDS = ["current", "building", "intent", "guids"];
export const FRAME_KINDS = ["world", "building", "intent"];
export const FRAMING_MODES = ["context", "fill"];
export const FIT_METHODS = ["sphere"];
export const PROJECTIONS = ["current", "perspective", "orthographic"];
export const CUT_KINDS = ["none", "storeyPlan", "sectionPlane", "sectionBox"];
export const COLOR_MODES = ["category", "single", "numbered"];
export const THEMES = ["current", "light", "dark"];

/** The edge padding cameraViews.js's scopeFitSphere has always applied at context 0. */
export const DEFAULT_PADDING = 0.15;
/** Bounds for a fixed image size; WebGL targets above 8192 px fail on common GPUs. */
export const IMAGE_MIN_PX = 64;
export const IMAGE_MAX_PX = 8192;
/** A storey plan is cut this far above the storey's floor unless the spec says otherwise. */
export const DEFAULT_CUT_HEIGHT_M = 1.2;
/** A section box extends this far beyond the scope's box unless the spec says otherwise. */
export const DEFAULT_SECTION_MARGIN_M = 0.5;
export const CUT_KEEP = ["below", "above"];

/**
 * A fresh copy of the defaults. `null` means "leave as it is" wherever a
 * live value exists to leave alone (direction, context, fov, transparency).
 */
export function defaultViewSpec() {
  return {
    schema: VIEW_SPEC_SCHEMA,
    scope: { kind: "current", intentId: null, guids: null },
    frame: { kind: "world" },
    direction: null,
    framing: { mode: "context", context: null, fill: null, padding: DEFAULT_PADDING, fit: "sphere" },
    lens: { projection: "current", fovDeg: null, metresPerPixel: null },
    cut: { kind: "none" },
    scene: {
      nonMemberTransparency: null,
      hiddenClasses: [],
      colorMode: "category",
      color: null,
      outlines: false,
      theme: "current",
    },
    image: null,
    transition: false,
  };
}

const isObject = (v) => v !== null && typeof v === "object" && !Array.isArray(v);
const isFinite_ = (v) => typeof v === "number" && Number.isFinite(v);

/** Shallow-merges one group of fields over its defaults, dropping unknown keys into `problems`. */
function mergeGroup(name, defaults, given, problems) {
  if (given === undefined) return defaults;
  if (!isObject(given)) {
    problems.push(`${name} must be an object`);
    return defaults;
  }
  const out = { ...defaults };
  for (const [key, value] of Object.entries(given)) {
    if (!(key in defaults)) problems.push(`${name}.${key} is not a known field`);
    else out[key] = value;
  }
  return out;
}

/**
 * Fills a partial spec with the defaults and validates it. Throws one Error
 * listing every problem, so a pasted spec is corrected in one round.
 *
 * Also the place where not-yet-built fields are refused by name: a field
 * that the schema reserves but no phase has implemented yet is reported as
 * "not implemented (phase N)" rather than ignored.
 *
 * @param {Record<string, any>} [partial]
 * @returns {ReturnType<typeof defaultViewSpec>}
 */
export function resolveViewSpec(partial = {}) {
  const problems = [];
  if (!isObject(partial)) throw new Error("view spec: must be a JSON object");
  const d = defaultViewSpec();

  for (const key of Object.keys(partial)) {
    if (!(key in d)) problems.push(`${key} is not a known field`);
  }
  if (partial.schema !== undefined && partial.schema !== VIEW_SPEC_SCHEMA) {
    problems.push(`schema ${partial.schema} is not ${VIEW_SPEC_SCHEMA}`);
  }

  const scope = mergeGroup("scope", d.scope, partial.scope, problems);
  if (!SCOPE_KINDS.includes(scope.kind)) problems.push(`scope.kind must be one of ${SCOPE_KINDS.join(", ")}`);
  if (scope.kind === "intent" && typeof scope.intentId !== "string") problems.push("scope.intentId is required for scope.kind 'intent'");
  if (scope.kind === "guids" && !(Array.isArray(scope.guids) && scope.guids.length > 0 && scope.guids.every((g) => typeof g === "string"))) {
    problems.push("scope.guids must be a non-empty list of GlobalIds for scope.kind 'guids'");
  }

  const frame = mergeGroup("frame", d.frame, partial.frame, problems);
  if (!FRAME_KINDS.includes(frame.kind)) problems.push(`frame.kind must be one of ${FRAME_KINDS.join(", ")}`);

  let direction = d.direction;
  if (partial.direction !== undefined && partial.direction !== null) {
    if (!isObject(partial.direction)) problems.push("direction must be null or {azimuthDeg, elevationDeg}");
    else {
      const { azimuthDeg, elevationDeg, ...rest } = partial.direction;
      for (const key of Object.keys(rest)) problems.push(`direction.${key} is not a known field`);
      if (!isFinite_(azimuthDeg)) problems.push("direction.azimuthDeg must be a finite number");
      if (!isFinite_(elevationDeg) || elevationDeg < -90 || elevationDeg > 90) {
        problems.push("direction.elevationDeg must be a number in [-90, 90]");
      }
      direction = { azimuthDeg, elevationDeg };
    }
  }

  const framing = mergeGroup("framing", d.framing, partial.framing, problems);
  if (!FRAMING_MODES.includes(framing.mode)) problems.push(`framing.mode must be one of ${FRAMING_MODES.join(", ")}`);
  if (framing.mode === "fill" && !(isFinite_(framing.fill) && framing.fill > 0 && framing.fill <= 1.5)) {
    problems.push("framing.fill must be a number in (0, 1.5] when framing.mode is 'fill'");
  }
  if (framing.fill !== null && !(isFinite_(framing.fill) && framing.fill > 0 && framing.fill <= 1.5)) {
    problems.push("framing.fill must be null or a number in (0, 1.5]");
  }
  if (framing.context !== null && !(isFinite_(framing.context) && framing.context >= 0 && framing.context <= 1)) {
    problems.push("framing.context must be null or a number in [0, 1]");
  }
  if (!(isFinite_(framing.padding) && framing.padding >= 0 && framing.padding < 5)) problems.push("framing.padding must be a number in [0, 5)");
  if (!FIT_METHODS.includes(framing.fit)) problems.push(`framing.fit must be one of ${FIT_METHODS.join(", ")}`);

  const lens = mergeGroup("lens", d.lens, partial.lens, problems);
  if (!PROJECTIONS.includes(lens.projection)) problems.push(`lens.projection must be one of ${PROJECTIONS.join(", ")}`);
  if (lens.fovDeg !== null && !(isFinite_(lens.fovDeg) && lens.fovDeg >= 10 && lens.fovDeg <= 120)) {
    problems.push("lens.fovDeg must be null or a number in [10, 120]");
  }
  if (lens.metresPerPixel !== null && !(isFinite_(lens.metresPerPixel) && lens.metresPerPixel > 0)) {
    problems.push("lens.metresPerPixel must be null or a positive number");
  }
  if (lens.metresPerPixel !== null && framing.mode === "fill") {
    problems.push("framing.mode 'fill' and lens.metresPerPixel both set the scale; use one");
  }

  let cut = d.cut;
  if (partial.cut !== undefined) {
    if (!isObject(partial.cut)) problems.push("cut must be an object");
    else if (!CUT_KINDS.includes(partial.cut.kind)) problems.push(`cut.kind must be one of ${CUT_KINDS.join(", ")}`);
    else cut = resolveCut(partial.cut, problems);
  }

  const scene = mergeGroup("scene", d.scene, partial.scene, problems);
  if (
    scene.nonMemberTransparency !== null &&
    !(isFinite_(scene.nonMemberTransparency) && scene.nonMemberTransparency >= 0 && scene.nonMemberTransparency <= 100)
  ) {
    problems.push("scene.nonMemberTransparency must be null or a number in [0, 100]");
  }
  if (!Array.isArray(scene.hiddenClasses) || !scene.hiddenClasses.every((n) => typeof n === "string" && n.length > 0)) {
    problems.push("scene.hiddenClasses must be a list of IFC class names (e.g. IFCROOF)");
  }
  if (!COLOR_MODES.includes(scene.colorMode)) problems.push(`scene.colorMode must be one of ${COLOR_MODES.join(", ")}`);
  if (scene.color !== null && !/^#[0-9a-f]{6}$/i.test(String(scene.color))) problems.push("scene.color must be null or a #rrggbb colour");
  if (scene.outlines !== false) problems.push("scene.outlines is not implemented (needs PostproductionRenderer)");
  if (!THEMES.includes(scene.theme)) problems.push(`scene.theme must be one of ${THEMES.join(", ")}`);

  let image = d.image;
  if (partial.image !== undefined && partial.image !== null) {
    if (!isObject(partial.image)) problems.push("image must be null or {width, height, pixelRatio}");
    else {
      const { width, height, pixelRatio = 1, ...rest } = partial.image;
      for (const key of Object.keys(rest)) problems.push(`image.${key} is not a known field`);
      const sizeOk = (v) => Number.isInteger(v) && v >= IMAGE_MIN_PX && v <= IMAGE_MAX_PX;
      if (!sizeOk(width) || !sizeOk(height)) problems.push(`image.width and image.height must be integers in [${IMAGE_MIN_PX}, ${IMAGE_MAX_PX}]`);
      if (!(isFinite_(pixelRatio) && pixelRatio > 0 && pixelRatio <= 4)) problems.push("image.pixelRatio must be a number in (0, 4]");
      image = { width, height, pixelRatio };
    }
  }

  const transition = partial.transition === undefined ? d.transition : partial.transition;
  if (typeof transition !== "boolean") problems.push("transition must be true or false");

  if (problems.length) throw new Error(`view spec: ${problems.join("; ")}`);
  return { schema: VIEW_SPEC_SCHEMA, scope, frame, direction, framing, lens, cut, scene, image, transition };
}

const isVec3 = (v) => Array.isArray(v) && v.length === 3 && v.every(isFinite_);

/** Validates one `cut` group by kind; unknown fields are reported, defaults filled. */
function resolveCut(given, problems) {
  const known = {
    none: [],
    storeyPlan: ["storey", "heightM", "keep"],
    sectionPlane: ["point", "normal", "offsetM", "flip"],
    sectionBox: ["marginM"],
  }[given.kind];
  for (const key of Object.keys(given)) {
    if (key !== "kind" && !known.includes(key)) problems.push(`cut.${key} is not a field of cut.kind '${given.kind}'`);
  }
  switch (given.kind) {
    case "none":
      return { kind: "none" };
    case "storeyPlan": {
      const { storey, heightM = DEFAULT_CUT_HEIGHT_M, keep = "below" } = given;
      if (typeof storey !== "string" || !storey.length) problems.push("cut.storey must name a storey (as the Floors list does)");
      if (!(isFinite_(heightM) && heightM >= 0 && heightM <= 50)) problems.push("cut.heightM must be a number in [0, 50]");
      if (!CUT_KEEP.includes(keep)) problems.push(`cut.keep must be one of ${CUT_KEEP.join(", ")}`);
      return { kind: "storeyPlan", storey, heightM, keep };
    }
    case "sectionPlane": {
      const { point = null, normal = null, offsetM = 0, flip = false } = given;
      if (point !== null && !isVec3(point)) problems.push("cut.point must be null or [x, y, z]");
      if (normal !== null && !(isVec3(normal) && Math.hypot(...normal) > 0)) problems.push("cut.normal must be null or a non-zero [x, y, z]");
      if (!isFinite_(offsetM)) problems.push("cut.offsetM must be a number");
      if (typeof flip !== "boolean") problems.push("cut.flip must be true or false");
      return { kind: "sectionPlane", point, normal, offsetM, flip };
    }
    case "sectionBox": {
      const { marginM = DEFAULT_SECTION_MARGIN_M } = given;
      if (!(isFinite_(marginM) && marginM >= 0)) problems.push("cut.marginM must be a number >= 0");
      return { kind: "sectionBox", marginM };
    }
    default:
      return { kind: "none" };
  }
}

/**
 * A short human label: "az 45° · el 20°", "plan (roll 180°)", "keep direction".
 * Used for a saved view's default name and the record.
 * @param {Record<string, any>} spec - a resolved spec (or any spec-shaped object)
 * @returns {string}
 */
export function describeViewSpec(spec) {
  const parts = [];
  if (!spec.direction) parts.push("keep direction");
  else if (spec.direction.elevationDeg >= 90) parts.push(spec.direction.azimuthDeg ? `plan (roll ${round1(spec.direction.azimuthDeg)}°)` : "plan");
  else if (spec.direction.elevationDeg <= -90) parts.push("looking up");
  else parts.push(`az ${round1(spec.direction.azimuthDeg)}° · el ${round1(spec.direction.elevationDeg)}°`);
  if (spec.frame.kind !== "world") parts.push(`${spec.frame.kind} frame`);
  if (spec.scope.kind === "building") parts.push("whole building");
  else if (spec.scope.kind === "intent") parts.push("intent");
  else if (spec.scope.kind === "guids") parts.push(`${spec.scope.guids.length} element(s)`);
  if (spec.framing.context !== null) parts.push(`context ${Math.round(spec.framing.context * 100)}%`);
  if (spec.lens.projection !== "current") parts.push(spec.lens.projection);
  if (spec.cut.kind === "storeyPlan") parts.push(`${spec.cut.keep === "above" ? "ceiling" : "plan"} cut at ${spec.cut.storey}`);
  else if (spec.cut.kind !== "none") parts.push(spec.cut.kind === "sectionBox" ? "section box" : "section");
  return parts.join(" · ");
}

const round1 = (n) => Math.round(n * 10) / 10;

"""Intent-category registry - the single source of truth for which
detectors exist. Adding a detector = one new entry here; nothing else in
scripts/recognize_intents.py or writers.py needs to change.

Before writing one, read docs/detectors.md "Writing a detector": thirteen
house rules, each recording a real bug that produced silent,
plausible-looking-but-wrong output on this corpus.

Each category's id is also what every intent record it produces stamps
into provenance.detector - the same id a future frontend category
filter (or, later, a UI-triggered recompute) would select by, via the
res/intent_categories.json manifest write_category_manifest() generates
from this dict.

`extraction_keys` names which `extracted` dict keys (see
scripts/recognize_intents.py's build_extracted()) a category's detector
needs - empty for a detector that's fully self-contained off the raw model
(connection.py, vertical.py, circulation.py). This replaces a plain
requires_extraction boolean so build_extracted() only ever computes what's
actually asked for, per-key, rather than an all-or-nothing extraction pass.

Taxonomy - `level` x `domain` since 2026-10-08, `maturity` as a
cross-cutting tag; the field bullets below define them. What follows up to
the table is the 2026-09-18 history of the first four domains, written when
the grid was domain x scope: read its "same storey" column as level storey
and "across storeys" as level building.
The first 4 detectors aren't 4 independent things - they fall into a clean
2x2 (circulation.py, labeled "Vertical Circulation", shares spatial/vertical
with vertical.py - both find a vertical connection between storeys - but is
a distinct signal, not a refinement of vertical.py's: it chains real
IfcStair/IfcRamp entities by their own flight geometry and verifies each
storey with door evidence, where vertical.py instead buckets IfcSpace
instances by recurring footprint. The two can and do disagree - e.g.
vertical.py finding a same-named IfcSpace on a storey circulation.py finds
no matching IfcStair for at all - which is useful, not a bug). envelope.py
adds a THIRD spatial/vertical signal, again distinct rather than a
refinement of the other two: it tracks the building's own floor/roof
footprint continuing (or stepping back) from level to level - not spaces,
not stairs.

A THIRD domain, "daylight" (windows, and sight), opened 2026-09-18 -
window_alignment.py (scope=vertical) is its first category, a direct
reapplication of structural.py's own column-chaining logic to IfcWindow
(x, y) placement instead of a column's, recovering repeated vertical
facade bays. lighting_clusters.py (scope=vertical) is its second: IfcWindow
instances of the SAME window type, clustered by (x, y) proximity ACROSS
ALL FLOORS (not confined to one storey) - a repeated window family
concentrated in one area of the building reads as one daylight zone
regardless of which floor each instance is on. Distinct from
window_alignment.py's tight-tolerance exact-position stacking: a lighting
cluster's proximity threshold is deliberately loose enough to merge a
whole run of ribbon windows into one zone (see lighting_clusters.py's own
docstring for the measured evidence behind that threshold). Started as
"Horizontal Window Sightline" (scope=storey, grouped by (storey,
exterior-view verdict)) 2026-09-18, replaced same-day by this clustering
approach per explicit request - the per-window exterior-sightline
classification itself (does a 2D ray toward the nearest storey-footprint
edge clear the building?) was kept and folded into each cluster's
evidence, not discarded.

A FOURTH domain, "circulation", opened 2026-09-18 by pulling circulation.py
("Vertical Circulation") and circulation_horizontal.py ("Horizontal
Circulation") out of "spatial" into their own domain - these two aren't
"just another spatial relationship" the way connection.py/vertical.py/
envelope.py are (all about how ROOMS relate to each other or their
bounding elements); they're about how PEOPLE move through the building,
a different question entirely, so they get their own top-level panel
section instead of being nested under SPATIAL.

                    same storey (horizontal)   across storeys (vertical)
    structural      alignment                  structural
    (columns/walls) (grid coordinate match)    (load-path continuity)

    spatial         connection                 vertical, envelope
    (spaces/rooms)  (IfcRelSpaceBoundary)       (space footprint recurrence;
                                                 floor/roof footprint
                                                 overlap level-to-level)

    daylight        (none yet)                 window_alignment,
    (windows)                                  lighting_clusters
                                                (repeated vertical facade
                                                 bay; same-type windows
                                                 clustered by proximity
                                                 across floors)

    circulation     circulation_horizontal     circulation
    (movement)      (named-space movement      (door-verified stair/ramp
                     path per storey)           runs)

- `domain`: "structural" (columns/walls carrying load), "spatial" (rooms
  and how they relate to each other/their bounding elements), "daylight"
  (windows/openings and sight), or "circulation" (how people move through
  the building). A content tag: it drove the panel's top-level grouping
  until 2026-10-08, when `level` took that over.
- `level` (2026-10-08, in place of `scope`): "room", "storey" or
  "building" - the largest IFC spatial level a category's claim reaches,
  read off the records (how many storeys a record relates to; whether the
  members are one space and its walls). Drives the panel's top-level
  grouping, Room -> Storey -> Building. `scope` ("storey", "vertical",
  "building") was retired with it: nothing in the viewer read it, and it
  had been mislabelling its own members since lighting_clusters, which
  IGNORES storeys, was registered "vertical".
- `maturity`: "verified" (deterministic rule, or a real IFC-native relation)
  or "draft" (a heuristic still needing more human validation before being
  trusted like the others - see vertical.py's docstring). A TRUST BADGE ONLY:
  the panel renders it as the DRAFT tag and nothing else reads it. Until
  2026-09-20 it also gated the CLI's default run (draft = opt-in), which meant
  a bare run executed 4 of 21 categories; every run now executes all of them
  and a failing detector is skipped rather than aborting the run (see
  scripts/recognize_intents.py). What "verified" should mean going forward -
  deterministic rule, or human-validated output - is still an open decision;
  no category has been human-validated yet.

- `signals` (2026-09-21): the model-level facts the
  detector needs, in preflight.py's grammar ("IfcSpace", "IfcStair|IfcRamp",
  "prop:IsExternal"). preflight.py probes them once per model and the shard
  records which categories cannot apply to that model and why, so "0
  intents" and "no input here" stop looking identical. Empty = always
  applicable. Derived from what each detector's own code reads
  (by_type()/property names), checked 2026-09-21; the CLI warns if a
  category flagged inapplicable still produces intents, which would mean
  this table is wrong for that model. Five under-declared gates were added
  2026-09-23 after the library sweep: flights for
  `circulation`, `Span` for `beam_framing`, doors for `unit_typology`, parts
  for `curtainwall_assembly`, spaces for `fire_compartments`.
- `section` (2026-10-18): an entry with its own top-level panel section,
  grouped there instead of under `level`; only the thirteen Neufert Topic
  categories carry it ("neufert"). The manifest emits it when present.
- `soft_signals` (2026-10-08): the
  same grammar plus `true:Name@Class`, `vocab:<concept>` and
  `footprints:usable` (preflight.py's docstring has the table). A failed
  soft signal does not make the category inapplicable; it is reported as
  "unlikely to produce output here", with the reason, and the category
  runs. This is how a merged category keeps its parts' explanations: Egress
  and Fire says "no door carries a FireRating" although it is applicable.

Domains: the narrative above covers the first four (structural, spatial,
daylight, circulation). Five more opened on 2026-09-19 against measured
coverage gaps - environmental, functional, services, constructional,
regulatory - for nine in total; each new category's own docstring says which
gap it fills. `scope` gained its third value, "building", the same day.

Space syntax, 2026-09-23: `space_syntax` (circulation/storey) and
`unit_layout` (spatial/building) read the shared door graph as a GRAPH
through room_graph.py - the storey's most integrated room and its rings,
and door layouts that recur by isomorphism. Neither reads a room name to
decide anything, so both work where the keyword-matched categories go
blind. No new domain; both sit in cells that existed.

Levels and merges, 2026-10-08 (docs/detectors.md "Retired entries"): every
entry carries `level`; ten categories whose records overlapped on the same
rooms, doors and windows folded into four - room_access (space_access,
space_syntax, circulation_horizontal), egress_fire (egress_reachability,
egress_access, fire_compartments), window_patterns (window_alignment,
lighting_clusters) and repeated_units (unit_typology, unit_layout) - each
appended at the end and running its parts' modules unchanged
(detectors/merged.py). The ten entries stay as TOMBSTONES at their
positions, with `retired` naming the successor: 17 live categories, 11
tombstones (grid_claims is the eleventh). Removing an entry would recolour
every later category; the panel's Compute list hides tombstones instead.
"""

from .detectors import (
    alignment,
    beam_framing,
    circulation,
    connection,
    convention_outlier,
    curtainwall_assembly,
    daylight_rooms,
    egress_fire,
    envelope,
    furniture_occupancy,
    grid_claims,
    repeated_units,
    retired,
    room_access,
    sanitary_provision,
    structural,
    thermal_envelope,
    vertical,
    window_patterns,
)

CATEGORIES = {
    # Merged 2026-10-07 with `grid_claims` (see its tombstone below): rows of
    # columns per storey, and row claims across the building.
    "alignment": {
        "label": "Column Alignment",
        "intent_types": ["alignment_column_group", "grid_line_consistency", "grid_line_gap"],
        "detector": alignment.detect,
        "extraction_keys": ("info_st_columns",),
        "domain": "structural",
        "level": "building",
        "maturity": "verified",
        "signals": ("IfcColumn",),
    },
    "connection": {
        "label": "Horizontal Space Boundary",
        "intent_types": ["connection_boundary_adjacency"],
        "detector": connection.detect,
        "extraction_keys": (),
        "domain": "spatial",
        "level": "room",
        "maturity": "verified",
        "signals": ("IfcSpace", "IfcRelSpaceBoundary"),
    },
    "structural": {
        "label": "Vertical Placement Continuity",
        "intent_types": ["structural_column_support", "structural_wall_support",
                          "structural_unsupported_base", "structural_stack_termination"],
        "detector": structural.detect,
        "extraction_keys": ("info_st_columns", "info_st_walls"),
        "domain": "structural",
        "level": "building",
        "maturity": "verified",
        "signals": ("IfcColumn|IfcWall",),
    },
    "vertical": {
        "label": "Vertical Space Alignment",
        "intent_types": ["vertical_space_connection"],
        "detector": vertical.detect,
        "extraction_keys": (),
        "domain": "spatial",
        "level": "building",
        "maturity": "verified",
        "signals": ("IfcSpace",),
    },
    "circulation": {
        "label": "Vertical Circulation",
        "intent_types": ["circulation_vertical_link"],
        "detector": circulation.detect,
        "extraction_keys": (),
        "domain": "circulation",
        "level": "building",
        "maturity": "draft",
        # Anchors are the FLIGHT children's placements; a stair without flights
        # (test_6: 7 stairs, 0 flights) yields nothing.
        "signals": ("IfcStair|IfcRamp", "IfcStairFlight|IfcRampFlight"),
    },
    "envelope": {
        "label": "Vertical Envelope Continuity",
        "intent_types": ["envelope_footprint_continuity", "envelope_setback"],
        "detector": envelope.detect,
        "extraction_keys": ("info_envelope_shapes",),
        "domain": "spatial",
        "level": "building",
        "maturity": "draft",
        "signals": ("IfcSlab|IfcRoof",),
    },
    "window_alignment": {
        "label": "Vertical Window Alignment (retired, now in Window Stacks and Clusters)",
        "intent_types": [],
        "detector": retired.detect,
        "extraction_keys": (),
        "domain": "daylight",
        "level": "building",
        "maturity": "draft",
        "signals": (),
        "retired": "window_patterns",
    },
    "lighting_clusters": {
        "label": "Lighting Clusters (retired, now in Window Stacks and Clusters)",
        "intent_types": [],
        "detector": retired.detect,
        "extraction_keys": (),
        "domain": "daylight",
        "level": "building",
        "maturity": "draft",
        "signals": (),
        "retired": "window_patterns",
    },
    "circulation_horizontal": {
        "label": "Horizontal Circulation (retired, now in Room Access)",
        "intent_types": [],
        "detector": retired.detect,
        "extraction_keys": (),
        "domain": "circulation",
        "level": "storey",
        "maturity": "draft",
        "signals": (),
        "retired": "room_access",
    },
    "beam_framing": {
        "label": "Beam Framing Modules",
        "intent_types": ["beam_framing_module"],
        "detector": beam_framing.detect,
        "extraction_keys": (),
        "domain": "structural",
        "level": "storey",
        "maturity": "draft",
        # Groups on the declared Span; beams without it are inapplicable.
        "signals": ("IfcBeam", "prop:Span"),
    },
    "egress_access": {
        "label": "External Access Points (retired, now in Egress and Fire)",
        "intent_types": [],
        "detector": retired.detect,
        "extraction_keys": (),
        "domain": "circulation",
        "level": "storey",
        "maturity": "draft",
        "signals": (),
        "retired": "egress_fire",
    },
    "space_access": {
        "label": "Room Access Network (retired, now in Room Access)",
        "intent_types": [],
        "detector": retired.detect,
        "extraction_keys": (),
        "domain": "circulation",
        "level": "storey",
        "maturity": "draft",
        "signals": (),
        "retired": "room_access",
    },
    "unit_typology": {
        "label": "Repeated Unit Types (retired, now in Repeated Units)",
        "intent_types": [],
        "detector": retired.detect,
        "extraction_keys": (),
        "domain": "spatial",
        "level": "building",
        "maturity": "draft",
        "signals": (),
        "retired": "repeated_units",
    },
    "daylight_rooms": {
        "label": "Room Daylight Provision",
        "intent_types": ["daylight_room_group", "daylight_deficit"],
        "detector": daylight_rooms.detect,
        "extraction_keys": (),
        "domain": "daylight",
        "level": "storey",
        "maturity": "draft",
        "signals": ("IfcSpace", "IfcWindow"),
    },
    "furniture_occupancy": {
        "label": "Furnished Occupancy",
        "intent_types": ["furniture_occupancy"],
        "detector": furniture_occupancy.detect,
        "extraction_keys": (),
        "domain": "functional",
        "level": "storey",
        "maturity": "draft",
        "signals": ("IfcSpace",),  # fixtures are matched by name inside spaces, any class - test_4 has none typed IfcFurnishingElement yet yields 5
        "soft_signals": ("vocab:seating|sleeping",),
    },
    "sanitary_provision": {
        "label": "Sanitary Provision",
        "intent_types": ["sanitary_provision"],
        "detector": sanitary_provision.detect,
        "extraction_keys": (),
        "domain": "services",
        "level": "storey",
        "maturity": "draft",
        "signals": ("IfcSpace",),  # same: sanitary fixtures matched by name over several classes, incl. proxies (test_4)
        "soft_signals": ("vocab:sanitary_fixture",),
    },
    "curtainwall_assembly": {
        "label": "Curtain Wall Assemblies",
        "intent_types": ["curtainwall_assembly"],
        "detector": curtainwall_assembly.detect,
        "extraction_keys": (),
        "domain": "constructional",
        "level": "storey",
        "maturity": "draft",
        # The record is the aggregated parts; test_6 has 165 curtain walls and
        # not one IfcMember/IfcPlate.
        "signals": ("IfcCurtainWall", "IfcMember|IfcPlate"),
    },
    "fire_compartments": {
        "label": "Fire Compartments (retired, now in Egress and Fire)",
        "intent_types": [],
        "detector": retired.detect,
        "extraction_keys": (),
        "domain": "regulatory",
        "level": "storey",
        "maturity": "draft",
        "signals": (),
        "retired": "egress_fire",
    },
    "egress_reachability": {
        "label": "Egress Reachability (retired, now in Egress and Fire)",
        "intent_types": [],
        "detector": retired.detect,
        "extraction_keys": (),
        "domain": "regulatory",
        "level": "storey",
        "maturity": "draft",
        "signals": (),
        "retired": "egress_fire",
    },
    "convention_outlier": {
        "label": "Convention Outliers",
        "intent_types": ["convention_outlier"],
        "detector": convention_outlier.detect,
        "extraction_keys": (),
        "domain": "constructional",
        "level": "building",
        "maturity": "draft",
        "signals": (),
    },
    "thermal_envelope": {
        "label": "External Envelope Boundary",
        "intent_types": ["envelope_thermal_boundary"],
        "detector": thermal_envelope.detect,
        "extraction_keys": (),
        "domain": "environmental",
        "level": "storey",
        "maturity": "draft",
        "signals": ("prop:IsExternal",),
    },
    # Appended 2026-09-21 - at the END, per docs/detectors.md
    # rule 5. Retired 2026-10-07: its row claims are written by
    # `alignment` now (alignment.py, grid_claims.py). Kept as a TOMBSTONE at
    # this position because the panel's colours follow the manifest order:
    # no types, no inputs, no signals, a detector that returns nothing (which
    # clears its old records from a shard when it, or its successor, is
    # recomputed). It still
    # shows as a checkbox in the panel's Compute list, hence the label.
    "grid_claims": {
        "label": "Column Alignment Continuity (retired, now in Column Alignment)",
        "intent_types": [],
        "detector": grid_claims.detect,
        "extraction_keys": (),
        "domain": "structural",
        "level": "building",
        "maturity": "draft",
        "signals": (),
        "retired": "alignment",
    },
    # Appended 2026-09-23 - at the END, per docs/detectors.md rule 5. Both
    # read the shared AccessGraph as a GRAPH (depth, rings, isomorphism)
    # through room_graph.py; see each module's docstring for the measurements.
    # Retired 2026-10-08 into room_access and repeated_units (tombstones).
    "space_syntax": {
        "label": "Space Syntax (retired, now in Room Access)",
        "intent_types": [],
        "detector": retired.detect,
        "extraction_keys": (),
        "domain": "circulation",
        "level": "storey",
        "maturity": "draft",
        "signals": (),
        "retired": "room_access",
    },
    "unit_layout": {
        "label": "Unit Layouts (retired, now in Repeated Units)",
        "intent_types": [],
        "detector": retired.detect,
        "extraction_keys": (),
        "domain": "spatial",
        "level": "building",
        "maturity": "draft",
        "signals": (),
        "retired": "repeated_units",
    },
    # Appended 2026-10-08 - at the END, per docs/detectors.md rule 5. Four
    # merged categories: each runs the part modules it
    # names (detectors/merged.py) and stamps its own id on their records, so
    # record ids, types, rules and metrics are those the parts always wrote.
    # The parts' own entries above are tombstones. `signals` is what none of
    # a category's rules can fire without: the intersection of the parts'.
    "room_access": {
        "label": "Room Access",
        "intent_types": [
            "access_reachable_group", "access_isolated_space", "access_door_anomaly",
            "access_storey_without_rooms", "syntax_integration_core", "syntax_ring",
            "circulation_horizontal_space",
        ],
        "detector": room_access.detect,
        "extraction_keys": (),
        "domain": "circulation",
        "level": "storey",
        "maturity": "draft",
        "signals": ("IfcSpace",),
        # Soft (2026-10-08, preflight.py): absent -> "unlikely", the category still runs.
        "soft_signals": ("IfcDoor", "vocab:horizontal_circulation", "footprints:usable"),
    },
    "egress_fire": {
        "label": "Egress and Fire",
        "intent_types": ["egress_reachable", "egress_unreachable", "egress_external_access", "fire_compartment",
                         "fire_compartment_singletons"],  # the last added 2026-10-08 (every door rated)
        "detector": egress_fire.detect,
        "extraction_keys": (),
        "domain": "regulatory",
        "level": "storey",
        "maturity": "draft",
        "signals": ("IfcDoor",),
        "soft_signals": ("true:IsExternal@IfcDoor|IfcWall", "prop:FireRating@IfcDoor", "footprints:usable"),
    },
    "window_patterns": {
        "label": "Window Stacks and Clusters",
        "intent_types": ["window_vertical_alignment", "window_bay_interrupted", "window_lighting_cluster"],
        "detector": window_patterns.detect,
        "extraction_keys": ("info_envelope_shapes",),
        "domain": "daylight",
        "level": "building",
        "maturity": "draft",
        "signals": ("IfcWindow",),
    },
    "repeated_units": {
        "label": "Repeated Units",
        "intent_types": ["unit_type_recurrence", "unit_layout_recurrence"],
        "detector": repeated_units.detect,
        "extraction_keys": (),
        "domain": "spatial",
        "level": "building",
        "maturity": "draft",
        "signals": ("IfcSpace", "IfcDoor"),
        "soft_signals": ("footprints:usable",),
    },
}


# Appended 2026-10-18 - at the END, per docs/detectors.md rule 5. The
# thirteen Neufert Topic categories: every K-rule of neufert_logic.md is
# data under config/neufert/, run by the generic families in
# recognition/neufert/; a Topic entry is a label plus the rules that carry
# that Topic. `section`
# puts them in their own panel section instead of the level sections
# (2026-10-18: not merged with the level-grouped detectors); `level` stays
# the honest claim-reach tag. `signals` is empty (the families report per
# rule); `soft_signals` names the classes the Topic's bound rules select.
from .neufert.engine import topic_detector  # noqa: E402
from .neufert.topics import SECTION as NEUFERT_SECTION, TOPICS as NEUFERT_TOPICS  # noqa: E402
from .neufert.topics import category_id as _neufert_id, intent_types as _neufert_types  # noqa: E402

for _suffix, _topic, _level, _classes in NEUFERT_TOPICS:
    CATEGORIES[_neufert_id(_suffix)] = {
        "label": f"Neufert: {_topic}",
        "intent_types": _neufert_types(_suffix),
        "detector": topic_detector(_suffix),
        "extraction_keys": (),
        "domain": NEUFERT_SECTION,
        "level": _level,
        "section": NEUFERT_SECTION,
        "maturity": "draft",
        "signals": (),
        "soft_signals": tuple(_classes),
    }


# Appended 2026-10-26 (branch zihan_dev1) - at the END, per docs/detectors.md rule 5. Our Neufert rules (rules/):
# one category per design-decision topic, in their own panel section "rules". Each record is one rule x outcome
# (pass / fail / unknown / scenario) with the verbatim Neufert quote and the measured values; see
# src/recognition/zihan_rules.py. They read the graphs in runs/graphs/, so they produce nothing for a model that
# has none.
from .zihan_rules import SECTION as _ZR_SECTION, TOPICS as _ZR_TOPICS  # noqa: E402
from .zihan_rules import detector as _zr_detector, intent_types as _zr_types  # noqa: E402

for _t in _ZR_TOPICS:
    CATEGORIES[_t["category"]] = {
        "label": _t["label"],
        "intent_types": _zr_types(_t["category"]),
        "detector": _zr_detector(_t["category"]),
        "extraction_keys": (),
        "domain": _ZR_SECTION,
        "level": _t["level"],
        "section": _ZR_SECTION,
        "maturity": "draft",
        "signals": (),
        "soft_signals": (),
    }

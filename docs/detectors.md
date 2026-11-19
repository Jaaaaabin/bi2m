# Detectors

What the recognition pipeline looks for, and the rules for adding to it. The
registry (`src/recognition/registry.py`) is the source of truth; this page
describes it, and `uv run python scripts/recognize_intents.py --list-categories`
prints the current list.

## How categories are organised

A **category** is one registry entry and one function,
`detect(model, extracted, file_key[, graph=])`, that returns **intent
records**. A record is a group of element GUIDs (its **members**, each with a
role) plus the evidence that made them a group, a `polarity`, and the id of
the detector that produced it. Every category has three tags:

- **level**: how far its claim reaches. `room`, `storey` or `building`. The
  viewer groups categories by level.
- **domain**: what kind of intent it is about: `spatial`, `circulation`,
  `structural`, `daylight`, `regulatory`, `constructional`, `services`,
  `functional`, `environmental`, plus `neufert` for the rule-card categories.
- **maturity**: `verified` or `draft`. A `draft` category is a heuristic that
  still needs human validation before it is trusted like a real IFC relation
  or a deterministic geometric rule. Four categories are `verified`.

Records with `polarity: "negative"` assert an absence, a violation or an
anomaly (an isolated room, a column stack that stops, a door that reaches
nothing). A review queue can put those first.

Before a run, `preflight.py` probes each model for the classes and properties
a category reads (its `signals`) and reports which categories cannot apply
and why. A category whose soft signals fail is reported as "unlikely" but still
runs. A category that runs and finds nothing is recorded as a zero-output case.

## The 17 live categories

| id | level / domain | maturity | claim |
|---|---|---|---|
| `alignment` | building / structural | verified | Rows of columns on one storey, and whether each row continues through the building; also carries the former `grid_claims` record types (grid-line consistency and gaps) |
| `connection` | room / spatial | verified | Per `IfcSpace`, the walls linked to it through `IfcRelSpaceBoundary` |
| `structural` | building / structural | verified | A column or load-bearing wall whose footprint recurs above another, storey after storey: a continuous vertical load path, with a negative record where a stack stops or starts unsupported |
| `vertical` | building / spatial | verified | Spaces on different storeys that recur at nearly the same footprint: a stairwell, shaft or atrium modelled one room per floor |
| `circulation` | building / circulation | draft | A vertical run of stairs or ramps, chained storey to storey and checked against door evidence on each storey |
| `envelope` | building / spatial | draft | Storeys whose floor-slab footprint continues from level to level, capped by the roof; setbacks are negative records |
| `beam_framing` | storey / structural | draft | Load-bearing beams that share one span on a storey (a repeated bay), and whether that span repeats up the building |
| `daylight_rooms` | storey / daylight | draft | Rooms by glazing ratio (window area serving the room over its floor area): those that meet a conventional provision and those with glazing that falls short |
| `furniture_occupancy` | storey / functional | draft | How many people the modelled seating and sleeping furniture accommodates, per room and storey |
| `sanitary_provision` | storey / services | draft | WC, washing, bathing and kitchen fixtures, placed in the rooms they serve and counted per storey |
| `curtainwall_assembly` | storey / constructional | draft | Each curtain wall with its mullions and panels, and how many other assemblies share its exact composition |
| `convention_outlier` | building / constructional | draft | The few elements that break a rule almost all their siblings follow (a wall with another location line, a door at another height) |
| `thermal_envelope` | storey / environmental | draft | The elements the model declares external (`IsExternal`), one record per storey, with their thermal specification |
| `room_access` | storey / circulation | draft | The storey's rooms-and-doors readings as one category: reachable groups, isolated rooms, door anomalies, storeys with doors but no rooms, integration cores and rings, horizontal circulation |
| `egress_fire` | storey / regulatory | draft | Reachability of exits, external access, and fire compartments |
| `window_patterns` | building / daylight | draft | Windows stacked vertically, bays with a window missing, lighting clusters |
| `repeated_units` | building / spatial | draft | Recurring room groups: the same unit type, and the same layout |

The four `verified` categories (`alignment`, `connection`, `structural`,
`vertical`) are frozen: they are not edited.

## The 9 Neufert rules

Since 2026-10-28 the Neufert section holds one category per rule: the nine
rules the Neufert QA Workbench's Rules pilot marks final. Each id is
`neufert_` plus the rule id.

Since 2026-10-29 each rule only **selects**: it lists the elements its
requirement may concern, with related elements as context, and judges
nothing. Rules about the same element select it the same way. A condition
the model can state (storey height, flat count, `IsExternal`, room names)
narrows the selection, and an element whose value for it cannot be read is
left out. A condition the model cannot state ("legally essential stair",
"public building", "heated room") is ignored, so the selection is wider.

| Rule | Level | Selects | Context |
|---|---|---|---|
| `neufert_r04` steps per flight, landings | storey | stairs on storeys at least 2.75 m high | all its parts (flights, landings, railings, members), the storeys it spans |
| `neufert_r05` essential stair width, 17/28 | storey | every stair | as R04 |
| `neufert_r07` door clear height and width | room | internal doors | host wall |
| `neufert_r10` daylight depth | room | office rooms outside flats | their windows |
| `neufert_r24` enclosed stairwell | storey | stairwell rooms | their doors, neighbouring rooms |
| `neufert_r25` essential stairs, non-residential | storey | stairs of buildings with no inferred flat (needs the door graph) | as R04 |
| `neufert_r43` emergency exit doors | room | external doors | host wall, the rooms they open into |
| `neufert_r44` insulating glazing | room | external windows and curtain walls | the windows' host walls, the rooms they light |
| `neufert_r56` non-essential stairs | storey | every stair | as R04 |

The context relations, since 2026-10-29 (after a check of the IfcOpenShell
API, `research/neufert/ifcopenshell_api_check_2026-10-29.md`, not in git):

- A door or window's **host wall** is the wall it fills (FillsVoids). Failing
  that, it is the curtain wall or wall it is a panel of, or, for the panel of a
  composite window, the wall that window fills.
- A door's **rooms** and a room's doors come from one table. Where the door
  graph is usable, they are its links. Where it is switched off (a frame
  guard), they come from the same 0.4 m reach redone on the context's own
  world-frame footprints, at most two rooms per door.
- A window's **room** and a room's windows also come from one table. That
  table is the proximity association. Where that association is switched off
  (frame-suspect), it is the room within 0.6 m of the window's body in
  IfcOpenShell's BVH tree (`geom.tree.clash_clearance_many`).

R10's judging (switched off with the rest) measures the room depth from the
daylight face. The room's footprint is cut along each external window's
facade normal, which is the window's local Y axis. That axis is the wall
normal on all 34,412 corpus windows that sit in a wall. Each facade reads its
deepest window, and the room reads its shallowest facade.

These are not hand-written detectors. Each rule is a **rule card**, a YAML
file in `config/neufert/rules/`. The card holds the workbench's rule as it
stands and bi2m's thresholds, each naming the workbench value it comes from.
`bindings.yaml` holds each rule's selection (its `scenario` selector) and
ties the card to one of a small set of generic **families** in
`src/recognition/neufert/families/` (`measure`, `provision`, `route`,
`adjacency`, `aggregate`). The families judge a requirement against the
card's thresholds. That judging is switched off (`JUDGE` in
`src/recognition/neufert/pilot.py`) and kept as a later second step;
`verify_neufert.py` still tests it. No code under `src/recognition/neufert/`
knows a rule number. `verify_neufert.py` fails on a float literal outside
the named constants, so thresholds live only in the cards. The family tests
run on fixture rules in `scripts/fixtures/neufert_families/`.

Each Neufert category emits one record type, `_scenario`: one record per
rule and model when its selection is not empty. With judging switched on it
would also emit `_pass`, `_fail`, `_warn`, `_info` and `_nodata`. All are
`draft`. They sit in their own section of the panel, after the level
sections.

## Retired entries

When categories were merged, the old entries stayed in the registry as
tombstones, so colours and old record ids keep working. A tombstone has no
types and no detector output; recomputing it, or its successor, removes its old
records from a shard.

| retired | successor |
|---|---|
| `space_access`, `space_syntax`, `circulation_horizontal` | `room_access` |
| `egress_reachability`, `egress_access`, `fire_compartments` | `egress_fire` |
| `window_alignment`, `lighting_clusters` | `window_patterns` |
| `unit_typology`, `unit_layout` | `repeated_units` |
| `grid_claims` | `alignment` |
| `neufert_stairs` | `neufert_r05` |
| `neufert_doors`, `neufert_accessibility` | `neufert_r07` |
| `neufert_offices`, `neufert_daylight` | `neufert_r10` |
| `neufert_escape` | `neufert_r24` |
| `neufert_envelope` | `neufert_r44` |
| `neufert_site`, `neufert_rooms`, `neufert_housing`, `neufert_highrise`, `neufert_bedrooms`, `neufert_walls` (no Neufert rule took them over) | `neufert_r04` |

## Writing a detector

Each rule below records a bug that produced plausible-looking, wrong output on
a real corpus. The failures were silent, which is why they are rules.

1. **Sort members deterministically, with the member's GUID as the tie-break.**
   Python set iteration and the geometry iterator's worker order change between
   runs, and ids built from member GUIDs change with them, which orphans every
   verdict keyed to them. Check with two `--no-cache` runs and diff the shard,
   ignoring `generatedAt`.
2. **Measure every threshold and record the measurement in the module
   docstring.** A 0.6 m de-duplication radius swallowed four urinals into
   neighbouring toilets; the real fixtures were 0.36 m apart. If a number is a
   convention rather than a measurement, say so and make it a parameter.
3. **`by_type()` returns subtypes. De-duplicate by GUID.** Otherwise a count
   doubles (144 beds reported in a file with 72).
4. **Revit names are `Family:Variant:Id`. Match only the first segment.** "Seat"
   inside a dimension descriptor made 50 WCs look like workplace seats.
5. **Append new registry entries at the end of `CATEGORIES`.** The panel colour
   comes from insertion order, so inserting mid-dict recolours every later
   category. Never remove an entry; retire it as a tombstone.
6. **Prefer a signal the whole corpus carries.** `IsExternal` is on every model
   checked, `IfcRelSpaceBoundary` on very few. Check availability before you
   commit to a signal and state the count in the docstring.
7. **Reuse the shared modules** instead of copying: `access_graph.py` (the door
   and room graph), `storeys.py`, `chains.py`, `components.py`,
   `properties.py`, `footprints.py`, `spaces.py`, `census.py`, `room_routes.py`,
   `furnishing.py`. Read property sets through `properties.py`, which uses the
   per-model memo in `session.py`, instead of calling `get_psets` directly. The
   four frozen categories keep their own copies on purpose.
8. **Set `polarity`.** `"negative"` for any record asserting an absence,
   violation or anomaly.
9. **Key anything durable on `id`, never on `index`.** The `<category>-NNN`
   display handle is re-derived on every write.
10. **Geometry is not uniformly trustworthy.** Column and stair placements can
    resolve to the origin with the real offset in the body representation; beam
    axes are often unusable; door shapes can sit at a local origin. `IfcSpace`
    and `IfcWindow` were clean everywhere checked. Never hand an unbounded mesh
    to a cycle enumeration (`find_closed_loops` is exponential); switch to
    shapely `polygonize` above 200 edges.
11. **Declare `signals` in the registry entry**: the classes and property values
    the detector reads (`"IfcSpace"`, `"IfcStair|IfcRamp"`,
    `"prop:IsExternal"`). `soft_signals` are inputs a category can run without
    but rarely finds anything without. Probe with the detector's own readers,
    never a parallel list. A category computed from another's output declares
    `derived_from`.
12. **Emit the negative companion where the positive rule has one.** A stack
    that stops, a footprint that steps back, a bay with a hole and a grid line
    with a gap are records a reviewer can judge, not an absence in the output.
    Reuse the positive record's sorted members and id construction with a
    distinct infix.
13. **Every coordinate is metres, and a raw placement goes through
    `src/ifc_units.py`.** `ifcopenshell.geom` shapes arrive in metres, but
    placements and raw attributes arrive in the file's own unit (millimetres,
    centimetres, feet). Call `scale = length_scale(model)` once per `detect()`
    and read points with `placement_xy(element, scale)`. `verify_units.py`
    checks that a metre model re-read as millimetres gives identical ids.

A new detector is checked by `verify_registry.py` (structure and the merged
categories), `verify_units.py` (units and stored-id reproduction) and
`verify_soft_signals.py`. See [CONTRIBUTING.md](../CONTRIBUTING.md).

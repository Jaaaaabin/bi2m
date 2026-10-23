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

## The 13 Neufert categories

`neufert_site`, `neufert_rooms`, `neufert_housing`, `neufert_offices`,
`neufert_highrise` (building level); `neufert_stairs`, `neufert_accessibility`,
`neufert_escape`, `neufert_bedrooms` (storey level); `neufert_daylight`,
`neufert_doors`, `neufert_envelope`, `neufert_walls` (room level).

These are not hand-written detectors. Each rule from the Neufert source is a
**rule card**, a YAML file in `config/neufert/rules/`: a selector, named
measures and thresholds. `bindings.yaml` ties each card to one of a small set
of generic **families** in `src/recognition/neufert/families/` (`measure`,
`provision`, `route`, `adjacency`, `aggregate`) that runs it; `families.yaml`
maps cards to families, and rules that cannot be checked yet are listed with a
reason in `deferred_reasons.yaml`. No code under `src/recognition/neufert/`
knows a rule number, and `verify_neufert.py` fails on a float literal outside
the named constants, so thresholds live only in the cards.

Each Neufert category emits records of six types: `_pass`, `_fail`, `_warn`,
`_info`, `_nodata` (the model lacks what the rule needs) and `_scenario`.
All are `draft`. They sit in their own section of the panel, after the level
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

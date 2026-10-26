# Architecture

How a model gets from an IFC file to a reviewed set of intents. Paths are
relative to the repository root.

```
                     Python (src/, scripts/)                          Node + browser (viewer/)
 IFC file ─┬─> file_identity ──> content key ─────────────────────────────┐
           │                                                              │
           ├─> extraction ──> data/extracted/<key>/  (cache)              │
           │                        │                                     │
           └─> recognition: preflight ─> detectors ─> corroboration ─> writers
                                                                  │
                                       public/res/intents/<key>.json   (one shard per model)
                                                                  │
 IFC file ─> tileIfc.mjs ─> public/tiles/<key>/ (optional)        │
           │                        │                             ▼
           └────────────────────────┴──────────────────> viewer: load, highlight, review ─> verdicts
                                                          server/: upload, run, tiles
```

## One key for everything

Every join in the system uses one per-model value, the **content key**: the
first 16 hex characters of the SHA-256 of the file's bytes. It names the
shard, the extraction cache, the tile set, the upload folder and the browser's
stored verdicts, so the same model is found again whatever the file is called,
and two different files with the same name never collide.

Four implementations compute it and must agree: `src/file_identity.py`,
`viewer/fileIdentity.js` (browser, `crypto.subtle`),
`server/api.mjs` (`node:crypto`) and `scripts/tileIfc.mjs` (the last three under
`viewer/`). `crypto.subtle`
needs a secure context, so the viewer must be opened on `localhost` or over
https; elsewhere it warns and falls back to a filename key. The IFC header's own
identifiers (file name, author, project GUID) are kept only as local provenance.
The only one that reaches a shard is the opaque project GUID, because a header
file name can contain a person's name or an absolute path.

## Extraction (`src/extraction/`)

Reads an IFC file with `ifcopenshell` and produces the per-element data the
detectors need: walls, columns, floors and storeys, curtain walls, with
geometry iterated in a worker pool. Units are read from the file
(`src/ifc_units.py`); detectors work in metres.

`scripts/recognize_intents.py` asks for only the extraction keys the requested
categories declare, and caches them in
`data/extracted/<key>/recognition_cache.json` (versioned, lists sorted by GUID so
output does not depend on iteration order). `--no-cache` ignores it.
`scripts/extract_batch.py` runs the full extraction on its own.

## Recognition (`src/recognition/`, `scripts/recognize_intents.py`)

One run, per model:

1. **Identity and extraction**: compute the content key, load or build the
   cache.
2. **Shared graph**: one door and room graph (`access_graph.py`) is built and
   passed to every detector that accepts `graph=`, instead of once per
   detector. Property sets and shapes are memoised per model
   (`session.py`, the Neufert `context.py`).
3. **Pre-flight** (`preflight.py`): which categories cannot apply to this
   model, which are unlikely, with reasons.
4. **Detectors**: each registry entry's `detect()` runs; a failing detector is
   reported, its previous results are kept, and the run exits 2.
5. **Corroboration**: when another category's record covers substantially the
   same elements, each record lists the other in `corroborates`, so the panel can
   say "also found by ..." and a reviewer is not shown the same fact twice
   without being told why.
6. **Write** (`writers.py`): results are merged into the model's shard
   *by category*, so re-running one category does not erase another's records.

The registry (`registry.py`) is the single place that says which detectors
exist and how they are labelled and coloured. See [detectors.md](detectors.md).

## The shard

`viewer/public/res/intents/<key>.json`:

```
storeVersion   2
fileKey        the content key
projectGuid    the IfcProject GlobalId, opaque
generatedAt    ISO time
preflight      signals, inapplicable, unlikely, zeroOutput
intents        [ record, ... ]
```

A record has `id` (stable across runs: built from the content key and member
GUIDs), `type`, `polarity` (`positive` or `negative`), `label`, `members`
(GUID, role, IFC class), `evidence` (a summary and metrics),
`provenance` (detector, rule, confidence), `corroborates`, and a display
`index` such as `room_access-009`. Anything durable is keyed on `id`, never on
`index`, which is re-derived on every write.

`public/res/intent_categories.json` is the manifest the viewer reads for the
category list, generated from the registry. The viewer fetches one shard
lazily, for the model that is open. Only a few fixture shards are tracked in
git; every other shard is local output.

## Viewer (`viewer/`)

Plain JavaScript on Vite, three.js and the That Open Components libraries
(web-ifc, fragments), with one small React component for the inspector. There is
no custom IFC parsing in the viewer.

- **`ThatOpenCompanyLoader.js`** orchestrates: viewer tiles, file intake, the
  load sequence, closing and unloading. `viewerRegistry.js` tracks the open
  viewers; `viewerModel.js` holds per-model context (key, STEP index, GUID index,
  intents).
- **Two load paths.** Default: parse the IFC in the browser (web-ifc), classify,
  index the spatial structure, apply highlights. If a tile set exists for
  exactly this content key, `tileSet.js` streams geometry and properties from it
  instead and skips the parse; if anything about it fails, the parse path runs.
  A geometry-only tile set is refused, because it cannot be referred, filtered or
  inspected.
- **Panels**: `panels/filterPanel.js` (floors, categories, GUID refer, the camera
  strip), `panels/intentPanel.js` (the recognised intents, grouped by level, with
  the Neufert categories in their own section, and accept and reject), `panels/computeSection.js` (upload and run).
- **Highlighting** (`highlighting.js`): the GUID index, highlight, refer
  (isolate) and gray-out, and the per-category colours.
- **Views and snapshots** (`views/`, `cameraViews.js`, `snapshot.js`): a view is
  a spec (camera, clipping, scope) that can be applied, captured as a record,
  exported as a BCF viewpoint, and rendered to a PNG with optional metadata. The
  batch driver `scripts/autocamera.py` renders one image per intent per view.
- **Lines** (`views/lines.js` and friends): authored or recognised grid and
  alignment lines drawn in the scene; a line can be hovered and picked.
- **Inspector**: `InspectorPanel.jsx` is a React island, loaded on the first
  element click and coupled to the rest only through an `element-selected`
  event. "Preview in 3D" uses `engine/`, a small separate engine that extracts
  one element's reference closure from the raw STEP bytes and renders it with
  web-ifc directly (ported from vscode-ifc, MIT; see `engine/README.md`).
- **Verdicts** (`verdicts.js`): accept and reject are kept in the browser's
  `localStorage`, keyed by content key and intent id. This is the known gap
  ([roadmap.md](roadmap.md)).

Heavy parts are split into their own chunks (`three`, `web-ifc`, `thatopen`,
`react`), and `scripts/checkBundleSize.mjs` enforces a per-chunk budget.
Paths in this section are relative to `viewer/`.

## Server (`viewer/server/`)

`server/api.mjs` holds the routes; `vite dev` mounts them as middleware and
`server/serve.mjs` serves them together with the built viewer (`npm start`, the
Docker image). There is no login, so it listens on loopback unless `HOST` says
otherwise.

| Route | What |
|---|---|
| `POST /api/upload-ifc` | stores the body under `data/uploads/<key>/`, with the key computed from the bytes that arrived; starts a background tile build. Refuses bodies over `BI2M_MAX_UPLOAD_MB` (default 500) with 413 |
| `POST /api/recognize-intents` | spawns `scripts/recognize_intents.py` for a file key and a category list (with `BI2M_PYTHON`, or `uv run python` otherwise) and returns its outcome |
| `GET /api/tile-status?fileKey=` | `ready`, `building`, `failed` or `none` |
| `GET /api/example-models[?fileKey=]` | lists, or streams, the `example_*.ifc` and `test_*.ifc` files in `data/`; nothing else in `data/` can be reached through it |
| `GET /api/library-models` | an IFC corpus listed by content key, read from `BI2M_IFC_CORPUS` and an index in `BI2M_VIS_DIR` |

Detection itself always runs in Python, never in the browser. `spawn` passes
arguments without a shell, so a hostile file key can only reach `argparse` as a
string.

## Where state lives

| What | Where | In git |
|---|---|---|
| Models | `data/*.ifc`, `data/uploads/<key>/` | no |
| Extraction cache | `data/extracted/<key>/` | no |
| Recognition shards | `public/res/intents/<key>.json` | five fixtures only |
| Tile sets | `public/tiles/<key>/` | no |
| Verdicts | browser `localStorage` | no |
| Neufert rules | `config/neufert/` | yes |
| Paths | `paths.yaml` | yes |

`paths.yaml` lists repository-relative paths (forward slashes only) so that the
Python and Node sides agree on where things are.

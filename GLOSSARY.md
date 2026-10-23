# Glossary

Domain terms as the code and the docs use them. Architecture words (module,
interface, seam, adapter, depth, leverage, locality) follow the
codebase-design vocabulary and are not redefined here. Extend it when a new
module is named after a concept, and correct a term when it sharpens.

- **Model**: one opened IFC file (an `ifcopenshell.file` in the backend, a
  loaded FragmentsGroup in the viewer). Identified by its **content key**
  (`file_identity.py` / `fileIdentity.js`), the first 16 hex of the SHA-256
  of its bytes.
- **Category / detector**: a registry entry (`recognition/registry.py`) and
  the `detect(model, extracted, file_key[, graph=])` function behind it.
  Four detectors are **frozen** (alignment, connection, structural,
  vertical) and are never edited.
- **Intent record** (`intent`): one recognised design intention with its
  **members** (element GUIDs with a role) and evidence; written per model
  into a **shard** (`public/res/intents/<key>.json`).
- **Topic**: a Neufert category; its rules are **rule cards**
  (`config/neufert/rules/K*.yaml`) bound through `bindings.yaml`; a rule runs
  through a **family** (measure, provision, route, adjacency, aggregate).
- **Context**: the Neufert per-model object (`neufert/context.py`) that
  memoises shapes, property sets, text and **facts** for one (model, graph).
- **AccessGraph** (door graph): the per-model door/space adjacency; a
  **storey view** is its per-storey derivation (room graph, open rooms,
  adjacency, groups), built once per storey.
- **Footprint**: a space's 2D polygon. A **footprint kind** names frame and
  pipeline together: "graph" (the AccessGraph's pipeline, local frame
  wherever a placement is not identity) or "world" (the Context's
  world-frame pipeline). Never defaulted.
- **Model session**: the per-model object (`recognition/session.py`) that
  owns the facts that are a function of the model alone, for one run or one
  warm server lifetime. Today it holds the property-set memo, which readers
  reach through `properties.psets_of(element)` without a new parameter;
  storey views, footprints and the recognition loop are meant to move into it
  (not done yet).
- **Extraction cache**: `extracted/<key>/recognition_cache.json`, the
  geometry extraction the detectors read; versioned, GUID-sorted.
- **Preflight**: the per-model probe of which categories can apply (hard
  signals) or are unlikely to produce output (soft signals); stored in the
  shard and merged across runs.
- **Viewer entry**: the per-viewer record in `viewerRegistry.js` (world,
  panels, camera scope, work queue); **model context**: the per-model record
  in `viewerModel.js` (key, GUID index, intents, tile metadata).
- **Refer**: highlight, ghost (90 % transparency of the rest) and zoom to an
  intent; its measured box is the **scope box**, an H0-locked value.
- **Building box**: the model's box minus IfcSite and IfcGeographicElement;
  **model extents**: a planned per-model memo of model, building, storey
  and per-element boxes (not built).
- **Snapshot metadata**: the JSON written beside a snapshot PNG while the
  camera panel's Meta switch is on (`views/snapshotMeta.js`): `selected`
  (every non-context member of the referred intent: roles member, base, top,
  intermediate), `selectedContext` (its context-role members), `visible` (elements with their own pixels in the picture, after
  occlusion, picture-faithful rule) and `ghosted` (on screen only through
  the Refer's ghost), with the derived `selectedVisible`, `selectedHidden`
  and `visibleOnly`.
- **View record / view spec**: the camera pose and its reproducible
  description (`views/applyView.js`).
- **Tile set / streamed model**: a model loaded from pre-converted fragments
  under `public/tiles/<key>/`; its **tile metadata** (assets, geometries,
  guids) gives boxes without geometry in the scene.

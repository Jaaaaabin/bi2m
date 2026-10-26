# Roadmap

Why the viewer exists, what works, and what is deliberately not built yet.

## Goal

The viewer is a **validation tool for a recognition pipeline**, not only a
geometry viewer. The pipeline proposes design intents in a building model, such
as columns that line up, rooms that form a unit, or a stair that serves every
storey. A person looks at each proposal in 3D and accepts or rejects it. Those
verdicts are what would later tune thresholds and show which heuristics deserve
to be called verified.

Three decisions shape everything else:

- **Recognition is inclusive.** The scope is the spatial arrangement and
  relationships of building components and spaces, not one relationship type.
  New categories are placed in a `level` x `domain` cell and start as `draft`.
- **Detection stays rule-based and in Python.** A language model, if used, only
  labels candidates the rules already found. It does not propose candidates, and
  it must run locally because project data is confidential.
- **Results are static data.** The pipeline writes JSON shards and the viewer
  reads them. Running recognition from the UI starts the same command line
  tool, so no detection logic lives in JavaScript.

## What works today

- Extraction and 41 registry entries (17 live, 13 Neufert, 11 retired); see
  [detectors.md](detectors.md).
- Per-model shards with positive and negative records, pre-flight reports, and
  cross-references between categories that find the same fact.
- A viewer with multi-model tiles, filtering by storey and category, refer and
  gray-out by GUID, saved views and BCF export, line overlays, snapshots with
  metadata, and an element inspector.
- Streaming of pre-converted tile sets, on request or automatically for large uploads
  (`BI2M_AUTO_TILE`, off by default). A streamed model loads all of its geometry
  once; true view-dependent streaming (only what is in view) does not suit a
  ghosted building and is not used.
- Self-hosting with Docker or `npm start`, with upload, Compute and tiling.
- Review packets: `scripts/autocamera.py` renders one image per intent per view
  with its full view record.

## Not built yet

**Durable verdicts.** Accept and reject are stored in the browser's
`localStorage`. There is no shareable, analysable verdict store. This is the
standing blocker: threshold tuning, a labelled set for any language model, the
false-positive rates, and promoting a `draft` category all wait on it.

**Recognition**

- Egress in 3D: joining the per-storey access graphs to the vertical circulation
  chains.
- A single-element record shape (today a record is a group).
- A local language-model labeller for categories that match by keyword, and for
  `convention_outlier`'s missing sense of direction.
- A parallel batch runner for extraction.
- Neufert rules still deferred. Each is listed with a reason in
  `config/neufert/deferred_reasons.yaml`; typical reasons are a fact the model
  does not provide or a selector that does not exist yet.

**Waiting on data, not code**

- Cross-model drift needs two revisions of one building.
- Several detectors fire on only one or two of the models tried, because few
  models carry `IfcSpace`, `IfcRelSpaceBoundary`, fire ratings or windows.
- An `aesthetic` domain was prototyped and rejected; it would need a soft method.

**Viewer and service**

- Editing or correcting an intent in the viewer; only accept and reject exist.
- A shared, hosted service with accounts, isolation and quotas. The server has no
  login and is meant for one user on one machine.
- A way for project-specific supporting material to feed a local language model.

## Engineering gaps

- The `verify_*` scripts and the browser tests are not run in CI yet. The
  example model is in the repository now, so the scripts could run there
  (all but `verify_neufert`'s source-plan check); the browser tests also need
  a dev server and a browser on the runner.
- Grid optimisation (GA-driven) is parked outside the repository.

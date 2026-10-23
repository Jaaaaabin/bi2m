# bi2m

Design-intent recognition for IFC building models, with a browser viewer for
reviewing what was recognised.

A Python pipeline reads an IFC file, runs a set of detectors over it (aligned
columns, door and room graphs, egress, daylight, Neufert design rules, ...) and
writes the findings as **intent records**: groups of element GUIDs plus the
evidence that made them a group. The viewer draws each record on the model so
a person can accept or reject it. The aim is a human-checked set of
recognised intents, not another geometry viewer.

```
IFC file ──> src/extraction ──> src/recognition ──> one JSON shard per model ──> viewer
              (per-element data)  (41 registry entries)   public/res/intents/      (review, accept/reject)
```

## Requirements

- Python 3.12 and [uv](https://docs.astral.sh/uv/)
- Node 24 (what CI and the Docker image use)
- Optional: Docker (self-hosting), Chromium via Playwright (end-to-end tests)

## Quick start

```bash
uv sync                                  # Python dependencies
cd Interfaces/Frontend/core
npm ci
npm run dev                              # http://localhost:3000
```

No IFC models are stored in git. Drop any `.ifc` file onto a viewer tile, or
put files in `data/`: those named `example_*.ifc` or `test_*.ifc` are listed in
an empty tile (nothing else in `data/` is offered to the browser).
Press **Compute** in the intent panel to run recognition on the open model
(the dev server starts the same CLI command you can run by hand, below).

Add `?hud` to the page URL for a live frame-time and draw-call overlay.

## Command line

Run from the repository root.

```bash
uv run python scripts/recognize_intents.py                       # every category, every .ifc in data/
uv run python scripts/recognize_intents.py --files model.ifc --categories structural,room_access
uv run python scripts/recognize_intents.py --list-categories     # id, level/domain, maturity
uv run python scripts/recognize_intents.py --no-cache            # ignore the extraction cache
uv run python scripts/extract_batch.py                           # extraction only, every .ifc in data/
uv run python scripts/coverage_report.py                         # element coverage per model and class
```

A detector that fails is skipped and the run exits 2. Results go to
`Interfaces/Frontend/core/public/res/intents/<contentKey>.json`, where
`<contentKey>` is a hash of the file's bytes, so the same model is found again
whatever it is called locally (`src/file_identity.py`). Each run prints a
pre-flight line per model saying which categories cannot apply and why.

Optional: convert a model to a streamable tile set. The viewer then streams
it instead of parsing the raw IFC in the browser. Uploads are converted in the
background automatically, so the second open of an uploaded model streams;
the command below is for a model that is already in `data/`.

```bash
cd Interfaces/Frontend/core
node scripts/tileIfc.mjs ../../../data/<model>.ifc
```

## Host it yourself

`npm run dev` is the development setup. To run bi2m as an app on your own
machine instead, use Docker or a production build. Both serve the same viewer
and the same API (`Interfaces/Frontend/core/server/`), so upload, Compute
(recognition) and tiling work as they do under `npm run dev`.

**With Docker** (Docker with the Compose plugin; on Ubuntu
`sudo apt install docker-compose-v2` if `docker compose` is missing):

```bash
docker compose up -d --build    # from the repository root
```

Open <http://localhost:3000> and drop an `.ifc` file onto a viewer tile.
Recognition results and tile sets are kept in Docker volumes and survive
restarts; uploads, extraction caches and verdicts land in `./data`. Settings
go in the environment or a `.env` file next to `docker-compose.yml`:

| Variable | Meaning |
|---|---|
| `BI2M_PORT` | host port, default 3000 |
| `BI2M_DATA` | host folder mounted as `data/`, default `./data`; `example_*.ifc` files in it are listed in an empty viewer tile |
| `BI2M_UID`, `BI2M_GID` | your `id -u` / `id -g` when they are not 1000, so files written to `BI2M_DATA` stay yours |
| `BI2M_COI` | `1` tries web-ifc's multi-threaded build; untested, off by default |

The port is published on `127.0.0.1` only, because the API accepts uploads and
runs recognition without any login. To use it from other machines, put a
reverse proxy with authentication in front rather than opening the port. The
model library (lightning-bolt button) needs an IFC corpus and its index: see
the commented corpus lines in `docker-compose.yml` (outside Docker, set them
in `.env`, see `.env.example`). Without Compose:
`docker build -t bi2m . && docker run -d -p 127.0.0.1:3000:3000 -v "$PWD/data:/app/data" bi2m`.

**Without Docker** (Node 24 and uv, as for development):

```bash
uv sync
cd Interfaces/Frontend/core
npm ci && npm run build
npm start                       # http://127.0.0.1:3000; PORT and HOST change it
```

## What is in the box

| Path | What |
|---|---|
| `src/extraction/` | IFC to per-element data (walls, floors, columns, curtain walls) and the extraction cache the detectors read |
| `src/recognition/` | the category registry, the detectors, the shared door and room graph, the Neufert rule families, the shard writer |
| `src/modality/` | readers for declared grids (`IfcGrid`) and facade bands |
| `src/tempo/` | deferred grid-optimisation code; needs extra packages that are not installed |
| `config/neufert/` | the Neufert rules as data: one card per rule, bound to a generic family |
| `scripts/` | command-line entry points, plus `verify_*.py` checks |
| `Interfaces/Frontend/core/` | the viewer (Vite, three.js, That Open Components), its production server in `server/`, unit tests in `tests/`, browser tests in `scripts/e2e/` (all under that folder) |
| `data/` | your models, uploads, extraction caches and verdicts; all ignored by git |
| `paths.yaml` | repository-relative paths shared by the Python and Node sides |

The registry holds 41 entries: 17 live categories, 13 Neufert topic
categories (`neufert_*`) and 11 retired entries kept so colours and old ids
stay stable. Four categories (`alignment`, `connection`, `structural`,
`vertical`) are verified; everything else is `draft`, meaning a heuristic
that still needs human validation. See [docs/detectors.md](docs/detectors.md).

## Documentation

| | |
|---|---|
| [CONTRIBUTING.md](CONTRIBUTING.md) | how to run the checks, what CI runs, fixtures and conventions |
| [docs/architecture.md](docs/architecture.md) | how extraction, recognition, shards and the viewer fit together |
| [docs/detectors.md](docs/detectors.md) | every category: what it claims, where it applies, how mature it is |
| [docs/roadmap.md](docs/roadmap.md) | why the viewer is a validation tool, and what is not built yet |
| [GLOSSARY.md](GLOSSARY.md) | the terms the code and docs use |

## Status and limits

- Recognition output is a set of candidates, not facts. Verdicts are kept in
  the browser (`localStorage`); a durable, shareable verdict store is the main
  open item ([roadmap](docs/roadmap.md)).
- The server has no login and listens on loopback by default. Serving several
  users from one host is out of scope.
- IFC models are not part of the repository. Results depend on how a model was
  authored (units, storeys, spaces, doors), and the pre-flight line says when
  a category cannot apply.

## License

[MIT](LICENSE). The vendored preview engine under
`Interfaces/Frontend/core/engine/` is ported from vscode-ifc and keeps its own
MIT notice in `engine/README.md`. Dependencies keep their own licenses.

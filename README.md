# bi2m

Design-intent recognition for IFC building models, with a browser viewer for
reviewing the results.

Detectors (aligned columns, door and room graphs, egress, daylight, Neufert
rules, ...) turn an IFC file into **intent records**: groups of elements plus
the evidence for them. The viewer shows each record on the model so a person
can accept or reject it.

![The bi2m viewer: one column-alignment record highlighted on the example model](docs/screenshot.png)

```
IFC file ──> src/extraction ──> src/recognition ──> JSON shard per model ──> viewer
```

## Getting started

There are three ways to run bi2m. All of them serve the same viewer and API
on http://localhost:3000.

| | Quick start (uv) | Without Docker | Docker |
|---|---|---|---|
| Purpose | development | self-hosting | self-hosting |
| Needs on the host | uv and Node 24 | uv and Node 24 | Docker only |
| Commands | `uv sync`, `npm ci`, `npm run dev` | `uv sync`, `npm ci && npm run build && npm start` | `docker compose up -d --build` |
| Result | same viewer and API on port 3000, with live reload | same, as a production build | same, in a container |

Once it runs, an empty viewer tile lists `example_autcon`, the one model in
the repository (`data/example_autcon.ifc`). Pick it, or drop your own `.ifc`
file onto a tile, then press **Compute** to run recognition.

### 1. Quick start with uv

Needs [uv](https://docs.astral.sh/uv/) (it installs Python 3.12 itself) and
Node 24.

```bash
uv sync
cd Interfaces/Frontend/core
npm ci
npm run dev        # http://localhost:3000, with live reload
```

To self-host without Docker, build the viewer once and serve the build
instead:

```bash
uv sync
cd Interfaces/Frontend/core
npm ci && npm run build && npm start
```

### 2. Start with Docker

Needs only Docker, with its Compose and Buildx plugins (on Ubuntu's
`docker.io`: `sudo apt install docker-compose-v2 docker-buildx`).

```bash
docker compose up -d --build    # http://localhost:3000
```

Settings go in `.env` next to `docker-compose.yml`:

| Variable | Meaning |
|---|---|
| `BI2M_PORT` | host port (default 3000) |
| `BI2M_DATA` | host folder mounted as `data/` (default `./data`) |
| `BI2M_UID`, `BI2M_GID` | your user and group id, if not 1000 |

Without the Compose plugin, plain Docker does the same:

```bash
docker build -t bi2m .
docker run -d --name bi2m --restart unless-stopped \
  -p 127.0.0.1:3000:3000 --user "$(id -u):$(id -g)" \
  -v "$PWD/data:/app/data" \
  -v bi2m-intents:/app/Interfaces/Frontend/core/public/res/intents \
  -v bi2m-tiles:/app/Interfaces/Frontend/core/public/tiles \
  bi2m
```

### Before you expose it

Self-hosted either way, the server has no login and listens on `127.0.0.1`
only. Put a reverse proxy with authentication in front before exposing it.
The model library needs an IFC corpus: see `.env.example`.

## Command line

From the repository root:

```bash
uv run python scripts/recognize_intents.py                    # all categories, every .ifc in data/
uv run python scripts/recognize_intents.py --files model.ifc --categories structural
uv run python scripts/recognize_intents.py --list-categories
```

Results go to `Interfaces/Frontend/core/public/res/intents/<contentKey>.json`,
keyed by a hash of the file's bytes.

## Layout

| Path | What |
|---|---|
| `src/recognition/` | category registry, detectors, Neufert rule families, shard writer |
| `src/extraction/`, `src/modality/` | per-element data, declared grids, facade bands |
| `config/neufert/` | Neufert rules as data |
| `scripts/` | command-line tools and `verify_*.py` checks |
| `Interfaces/Frontend/core/` | the viewer, its server (`server/`) and tests |
| `data/` | the example model; your models, uploads and caches (not in git) |

41 registry entries: 17 live categories, 13 Neufert categories and 11 retired
ones. Four are verified; the rest are drafts awaiting human validation.

## Documentation

- [CONTRIBUTING.md](CONTRIBUTING.md): checks, CI and conventions
- [docs/architecture.md](docs/architecture.md): how the parts fit together
- [docs/detectors.md](docs/detectors.md): every category and how mature it is
- [docs/roadmap.md](docs/roadmap.md): what is not built yet
- [GLOSSARY.md](GLOSSARY.md): terms

## License

[MIT](LICENSE). The ported engine in `Interfaces/Frontend/core/engine/` keeps
its own MIT notice. The example model `data/example_autcon.ifc` is licensed
under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).

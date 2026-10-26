# bi2m: Building Intent Information Modeling

bi2m adds design intent to building information modeling. It recognises the
intent in an IFC building model (aligned columns, door and room graphs,
egress, daylight, Neufert rules, ...) and stores it as **intent records**:
groups of elements plus the evidence for them, kept beside the model. A
browser viewer shows each record on the model so a person can accept or
reject it.

![The bi2m viewer: one column-alignment record highlighted on the example model](docs/screenshot.png)

```
IFC file ──> src/extraction ──> src/recognition ──> JSON shard per model ──> viewer
```

## Getting started

There are two ways to run bi2m: **uv** for development, when you work on the
code, and **Docker** for hosting, when you only want to use it. Both serve the
same viewer and API on http://localhost:3000.

Either way, first get the code (needs [git](https://git-scm.com/downloads)):

```bash
git clone https://github.com/Jaaaaabin/bi2m.git
cd bi2m
```

Once it runs, an empty viewer tile lists `example_autcon`, the one model in
the repository (`data/example_autcon.ifc`). Pick it, or drop your own `.ifc`
file onto a tile, then press **Compute** to run recognition.

### 1. Quick start with uv (development)

For working on the code: the viewer reloads as you edit. Needs
[uv](https://docs.astral.sh/uv/getting-started/installation/) (it installs
Python 3.12 itself) and [Node 24](https://nodejs.org/en/download) (`node
--version` should print `v24.x`). Works on Linux, macOS and Windows (x64). On
Windows on ARM, use Docker: ifcopenshell has no build for it.

```bash
uv sync
cd viewer
npm ci
npm run dev        # http://localhost:3000, with live reload
```

Settings, such as the model library's corpus folder, go in a `.env` file at
the repository root: copy `.env.example`.

### 2. Host with Docker

For running bi2m as a service, without installing Python or Node. Needs only
Docker, with its Compose and Buildx plugins.

If you do not have Docker yet:

- **Windows, macOS:** install [Docker Desktop](https://docs.docker.com/desktop/)
  and start it. It includes Compose and Buildx. On Windows it runs on WSL 2,
  which the installer sets up.
- **Linux:** install Docker Engine for your distribution
  ([docs.docker.com/engine/install](https://docs.docker.com/engine/install/));
  Docker's own packages include Compose and Buildx. With Ubuntu's `docker.io`
  instead, add them: `sudo apt install docker-compose-v2 docker-buildx`. To run
  `docker` without `sudo`, add yourself to the `docker` group
  (`sudo usermod -aG docker $USER`, then log out and in); that group is
  root-equivalent, so skip this if you would rather type `sudo`.

`docker compose version` should then print a version. Then, from the
repository root:

```bash
docker compose up -d --build    # http://localhost:3000
```

The first build downloads and builds everything (several minutes, about
1.3 GB). `docker compose down` stops it; your models and results stay in
`data/` and in Docker volumes.

Settings go in `.env` next to `docker-compose.yml`:

| Variable | Meaning |
|---|---|
| `BI2M_PORT` | host port (default 3000) |
| `BI2M_DATA` | host folder mounted as `data/` (default `./data`) |
| `BI2M_UID`, `BI2M_GID` | your user and group id, if not 1000 |
| `BI2M_MAX_UPLOAD_MB` | largest model you can upload, in MB (default 500) |

On Linux without the Compose plugin, plain Docker does the same (a bash
command; on Windows and macOS, use Compose as above):

```bash
docker build -t bi2m .
docker run -d --name bi2m --restart unless-stopped \
  -p 127.0.0.1:3000:3000 --user "$(id -u):$(id -g)" \
  -v "$PWD/data:/app/data" \
  -v bi2m-intents:/app/viewer/public/res/intents \
  -v bi2m-tiles:/app/viewer/public/tiles \
  bi2m
```

### Before you expose it

The server has no login and listens on `127.0.0.1` only. Put a reverse proxy
with authentication in front before exposing it. The model library needs an
IFC corpus: see `.env.example`. To report a security problem, see
[SECURITY.md](SECURITY.md).

## Command line

From the repository root:

```bash
uv run python scripts/recognize_intents.py                    # all categories, every .ifc in data/
uv run python scripts/recognize_intents.py --files model.ifc --categories structural
uv run python scripts/recognize_intents.py --list-categories
```

Results go to `viewer/public/res/intents/<contentKey>.json`,
keyed by a hash of the file's bytes.

## Layout

| Path | What |
|---|---|
| `src/recognition/` | category registry, detectors, Neufert rule families, shard writer |
| `src/extraction/`, `src/modality/` | per-element data, declared grids, facade bands |
| `config/neufert/` | Neufert rules as data |
| `scripts/` | command-line tools and `verify_*.py` checks ([what each one is for](scripts/README.md)) |
| `viewer/` | the viewer, its server (`server/`) and tests |
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

[MIT](LICENSE). The ported engine in `viewer/engine/` keeps
its own MIT notice. The example model `data/example_autcon.ifc` is licensed
under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). The viewer's
font, Space Grotesk, is under the SIL Open Font License 1.1
([`viewer/public/fonts/OFL.txt`](viewer/public/fonts/OFL.txt)).

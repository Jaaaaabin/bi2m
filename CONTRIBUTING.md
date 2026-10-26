# Working on bi2m

Setup is in the [README](README.md). This page is about changing the code:
which checks to run, what CI runs, and the conventions that keep results
reproducible.

## Checks before you push

**Viewer** (`Interfaces/Frontend/core`):

```bash
npm test             # ESLint + tsc over the pure modules + Vitest unit tests
npm run build:check  # production build, then the per-chunk size budget
```

`npm run format` (Prettier) exists, but the tree is not kept Prettier-clean
and CI does not check it; format only the files you touch.

**Python** (repository root):

```bash
uv run python -m compileall -q src scripts
uv run python scripts/recognize_intents.py --list-categories
uv run python scripts/verify_units.py    # first: builds the example's extraction cache
for f in scripts/verify_*.py; do echo "== $f"; uv run python "$f" || echo "FAILED: $f"; done
git status --short    # the verify runs must not change any tracked file
```

CI (`.github/workflows/ci.yml`) runs the viewer checks above, the first two
Python lines and one recognition run on the example model, each on Linux,
macOS and Windows, plus a Docker build with a smoke test of the server on
Linux. It does not run the `verify_*` scripts or the browser tests yet.

### The `verify_*` scripts

They are plain scripts that print `ok` / `FAIL` per check and exit non-zero on
a failure. None of them writes to the real shard directory.

| Script | Needs |
|---|---|
| `verify_units`, `verify_shared_modules` | `data/example_autcon.ifc` and its stored shard (both tracked) |
| `verify_registry`, `verify_soft_signals` | the same, plus the example's extraction cache, which a `verify_units` run writes to `data/extracted/` |
| `verify_rollups`, `verify_session`, `verify_grid_lines`, `verify_grid_words` | nothing outside the repository |
| `verify_neufert` | the Neufert source plan (`neufert_logic.md`), a maintainer file that is not in the repository; on a fresh clone one of its checks fails, so skip it |

`verify_units.py --library DIR` adds checks on a folder of real millimetre and
centimetre models. If you changed anything under `src/recognition/`, also
confirm that a recognition run still reproduces the stored ids; `verify_units`
does this for every `.ifc` in `data/`.

### Browser tests

```bash
cd Interfaces/Frontend/core
npm run dev                                     # in one terminal
uv run playwright install chromium              # once; on Linux add --with-deps (sudo) for its system libraries
uv run python scripts/e2e/run_all.py --quick    # in another; drops the 2-minute perf audit
```

They drive a real browser against the dev server and need
`data/example_autcon.ifc`. The suite expects that model to be parsed, not
tiled, so do not run `tileIfc.mjs` on it.

Add `?hud` to the page URL for a live frame-time and draw-call overlay.

### Bundle budget

`Interfaces/Frontend/core/scripts/checkBundleSize.mjs` fails the build when a chunk grows more than 10%
past its gzip budget. Raise a budget deliberately, in that file, with the
reason next to the number. When the app-code chunk trips, lazy-load before you
raise it. A new lazy chunk needs its own budget entry; a chunk without one is
never checked.

## Data and models

- One IFC model is in git: `data/example_autcon.ifc`, which the checks and
  browser tests run on. Keep it byte-identical, because its content key names
  its tracked shard. Every other `data/*.ifc` and `data/uploads/` is ignored.
  Get a model into `data/` by hand, or drop it onto the viewer.
- A model is identified by its **content key** (first 16 hex of the SHA-256 of
  its bytes), never by its file name. Keys name shard files, extraction caches,
  tile sets and upload folders.
- Five fixture shards are tracked in `Interfaces/Frontend/core/public/res/intents/`.
  Every other shard comes from pressing Compute on a model that other people do
  not have, so new ones are ignored. Add one deliberately with `git add -f`.
  `index.json` there is a local catalogue and is not tracked.
- Machine-specific paths live in a gitignored `.env` at the repository root
  (copy `.env.example`): `BI2M_IFC_CORPUS` (folder of IFC files, also the
  viewer's model library), `BI2M_VIS_DIR` (their visual outputs and the library
  index) and `BI2M_IFC_ROOT` (parent folder of several corpora). The scripts
  (`src/local_env.py`) and the server (`server/api.mjs`) read it; a variable set
  in the environment wins. `paths.yaml` holds repository-relative paths with
  forward slashes; never commit an absolute path.

## Adding or changing a detector

- A category is a registry entry (`src/recognition/registry.py`) plus a
  function `detect(model, extracted, file_key[, graph=])` that returns intent
  records. Say which `level` (room, storey or building), `domain` and
  `maturity` it has; new heuristics start as `draft`.
- Four categories are frozen (`alignment`, `connection`, `structural`,
  `vertical`): do not edit them.
- Record ids must be reproducible: the same model gives the same ids on every
  run. `verify_units` and `verify_registry` check this.
- Merged categories keep their former parts as retired entries, so old ids and
  colours keep working. Do not delete a retired entry.
- Neufert rules are data under `config/neufert/`: add or change a rule card and
  its binding, and let the generic families in `src/recognition/neufert/` run
  it, instead of writing a new detector.

## License

The project is MIT licensed ([LICENSE](LICENSE)); contributions are accepted
under the same license.

## Documentation

[docs/](docs/) describes the system as it is now; source comments point into
it where a topic is covered there.

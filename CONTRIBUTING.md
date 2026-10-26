# Working on bi2m

Setup is in the [README](README.md). This page is about changing the code:
which checks to run, what CI runs, the conventions that keep results
reproducible, and what each script in `scripts/` is for.

## Checks before you push

**Viewer** (`viewer`):

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
cd viewer
npm run dev                                     # in one terminal
uv run playwright install chromium              # once; on Linux add --with-deps (sudo) for its system libraries
uv run python scripts/e2e/run_all.py --quick    # in another; drops the 2-minute perf audit
```

They drive a real browser against the dev server and need
`data/example_autcon.ifc`. The suite expects that model to be parsed, not
tiled, so do not run `tileIfc.mjs` on it.

Add `?hud` to the page URL for a live frame-time and draw-call overlay.

### Bundle budget

`viewer/scripts/checkBundleSize.mjs` fails the build when a chunk grows more than 10%
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
- Five fixture shards are tracked in `viewer/public/res/intents/`.
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

Read [docs/detectors.md](docs/detectors.md), "Writing a detector": thirteen
rules, each from a bug that gave plausible but wrong output. A new heuristic
starts as `draft`; the four frozen categories are not edited; a retired entry
is never deleted; and a Neufert rule is a card under `config/neufert/`, not a
new detector. `verify_registry` and `verify_units` check the result.

## Scripts

Command-line tools, run from the repository root with `uv run python
scripts/<name>.py`. Each script's own docstring has the details and options.
The viewer's own scripts (tiling, bundle budget, browser tests) are in
`viewer/scripts/`. The `verify_*.py` checks are described
[above](#the-verify_-scripts).

**Recognition**: what most people need.

| Script | What it does |
|---|---|
| `recognize_intents.py` | Runs the detectors on IFC models and writes one shard per model (see the README, "Command line"). |
| `grid_lines.py` | Writes a model's declared grids (IfcGrid) as line files for the viewer's overlay. |
| `tile_corpus.py` | Converts many models into tile sets the viewer streams instead of parsing. |

**Corpus research**: these work on a folder of IFC models (`BI2M_IFC_CORPUS`,
and `BI2M_VIS_DIR` for visual output; see `.env.example`). Without such a
corpus, you do not need them.

| Script | What it does |
|---|---|
| `autocamera.py` | Snapshots of every model in the library, taken through the viewer. |
| `build_vis_index.py` | Index of the per-model visual outputs, which the viewer's model library reads. |
| `library_annotations.py` | Per-model notes for the model library (unit, residual issues). |
| `detector_sweep.py` | Runs every detector over many models and reports exceptions and odd outputs. |
| `eligibility_survey.py` | Which categories could run on which models, without running a detector. |
| `input_survey.py` | What each model offers the detectors, counted from the file text alone. |
| `grid_survey.py` | The declared grids of many models, one JSON row per model. |
| `grid_words.py` | Grid words and facade bands for models that declare a grid. |
| `unit_sweep.py` | Detector results with and without the unit helper, across many models. |
| `coverage_report.py` | Share of a model's elements that appear in at least one intent record. |
| `detector_audit.py` | Read-only probes of the detectors: timing, storeys and placements. |
| `compare_models.py` | Prototype: compares whole models with each other. |
| `extract_batch.py` | Runs the extraction step alone over a set of models. |
| `validate_neufert.py` | Checks the Neufert rules against a QA pack (`neufert_validation_pack.json`, not in the repository). |

**Maintenance**

| Script | What it does |
|---|---|
| `neufert_bindings.py` | Regenerates `config/neufert/` from the Neufert source plan (a maintainer file, not in the repository). |
| `prune_uploads.py` | Removes duplicate upload folders left by an older upload scheme. Dry run by default. |
| `load_paths.py` | Reads `paths.yaml`; used by other scripts. Run it alone to print the resolved paths. |

## License

The project is MIT licensed ([LICENSE](LICENSE)); contributions are accepted
under the same license.

## Documentation

[docs/](docs/) describes the system as it is now; source comments point into
it where a topic is covered there. They cite `docs/architecture.md` and
`docs/detectors.md` by section heading and by rule number, so when you rename a
heading or renumber a rule, update the citations too
(`grep -rn 'docs/detectors.md' src scripts viewer config`).

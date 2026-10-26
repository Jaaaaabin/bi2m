# scripts/

Command-line tools, run from the repository root with `uv run python
scripts/<name>.py`. Each script's own docstring has the details and options.
The viewer's own scripts (tiling, bundle budget, browser tests) are in
`viewer/scripts/`.

## Recognition

What most people need.

| Script | What it does |
|---|---|
| `recognize_intents.py` | Runs the detectors on IFC models and writes one shard per model (see the README, "Command line"). |
| `grid_lines.py` | Writes a model's declared grids (IfcGrid) as line files for the viewer's overlay. |
| `tile_corpus.py` | Converts many models into tile sets the viewer streams instead of parsing. |

## Checks

`verify_*.py`: self-checks that print `ok` or `FAIL` per check.
[CONTRIBUTING.md](../CONTRIBUTING.md) says which to run, in which order, and
what each needs.

## Corpus research

These work on a folder of IFC models (`BI2M_IFC_CORPUS`, and `BI2M_VIS_DIR`
for visual output; see `.env.example`). Without such a corpus, you do not
need them.

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

## Maintenance

| Script | What it does |
|---|---|
| `neufert_bindings.py` | Regenerates `config/neufert/` from the Neufert source plan (a maintainer file, not in the repository). |
| `prune_uploads.py` | Removes duplicate upload folders left by an older upload scheme. Dry run by default. |
| `load_paths.py` | Reads `paths.yaml`; used by other scripts. Run it alone to print the resolved paths. |

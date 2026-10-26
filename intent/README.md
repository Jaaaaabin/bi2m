# intent/ — Neufert design-intent extraction (pilot)

Extracts structured *design intents* (rules, recommendations, typical values, tacit
figure-implied principles) from the parsed Neufert dataset in `data/neufert/dataset/`.

## Pipeline

```
pages.jsonl + index.jsonl
   │  corpus.render()  — one page = body text (with ids) + all captions + tables
   ▼
extract  ── A: gpt-5.6-sol (OpenAI structured output)
         └─ B: claude-sonnet-5 (Anthropic structured output)      → raw_a/, raw_b/
   ▼
judge    ── claude-opus-5 sees page + A + B, returns index-based decisions
            (prefer A|B, field fixes, rejections); Python assembles records → judged/
   ▼
report   ── verify every quote verbatim against the page (exact / fuzzy / failed),
            merge to intents.jsonl, stats.json, review_sample.md
```

## Run

```bash
# from project root
.venv/bin/python -m intent.run_pilot --chapter "Residential buildings" --stage all
.venv/bin/python -m intent.run_pilot --only page_0169 --stage judge --force
.venv/bin/python -m intent.run_pilot --stage report          # recompute stats only
```

Stages are idempotent: existing per-page JSON is skipped unless `--force`.
Keys are read from `.env` (`OA_OPENAI_KEY`, `Anthropic_KEY`).

## Record schema (see `schema.py`)

| field | meaning |
|---|---|
| statement | self-contained normalized rule |
| kind | hard_constraint / soft_principle / typical_value / tacit |
| modality | must / should / typical / may |
| scope | element_class, ifc_entity, space_type, qualifier |
| condition | building_type, room_type, occupancy, adjacency, storey, orientation, other |
| prescription | property, op (>=, <=, =, ~, range, qualitative), value_min/max, unit, qualitative |
| rationale | concept (fixed vocabulary of 18 + other), text, **stated** (true only if the book says why) |
| source | paragraph_ids, figure_ids, **quote** (verbatim, checked by `verify.py`) |
| ifc_checkable | direct / relational / not_checkable, + check_sketch |
| provenance | both / A_only / B_only (added by judge) |

## Output layout

```
runs/intent_pilot_residential/
  raw_a/page_XXXX.json      extractor A output
  raw_b/page_XXXX.json      extractor B output
  judged/page_XXXX.json     merged records + rejected + raw decisions
  intents.jsonl             final records with quote_verified + figure image paths
  stats.json                distributions (kind, modality, concept, checkable, stated, provenance)
  review_sample.md          50 stratified rows for human verdicts
  _usage.json               token usage per model
```

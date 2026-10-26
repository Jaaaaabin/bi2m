# ifc-bench Neufert subset

Source: https://huggingface.co/datasets/sylvainHellin/ifc-bench (v2, questions/ifc-bench-v2.csv)
Downloaded: 2026-09-30

9 projects (4351 and duplex, the two IFC2X3 models, were dropped on 2026-10-20); MEP questions ignored. Only `arc.ifc` per project — all Neufert-relevant
questions target the architectural model.

Excluded:
- dental_clinic, wbdg_office — by choice
- hitos, molio, schependomlaan, sixty5, smiley_west — held out as "license, quality, or
  redundancy issues" in data/questions/splits.json of
  https://github.com/sylvainHellin/ecppm-2026-du-hellin-fuchs-borrmann (Du et al., ECPPM 2026)

## Files
- `neufert_qa.csv` / `.json` — 67 Neufert-relevant QA pairs across all projects
- `all_qa.csv` — all 452 v2 QA pairs of these 9 projects
- `ifc_bench_neufert_qa.csv`, `ifc_bench_detail_qa.csv` — earlier tagging passes over the same questions (neufert_tier / detail_topic columns)
- `<project>/arc.ifc` (the knowledge points, hard QA and rules that use these models live in `../../knowledge/` and `../../rules/`)
- `<project>/arc.ifc`, `model_card.md`, `license.txt`, `snapshot.png`
- `<project>/neufert_qa.csv`, `<project>/all_qa.csv` — per-project subsets

Columns: id, question, ground_truth, ifc_model, project, category (1–4), split (from
eval-split-hellin2026.csv), neufert_tier, neufert_topic.

## Neufert tagging (manual, subjective)
- tier1 (13): answering needs Neufert-type norms / typical values / design judgement
  (escape & accessibility, occupancy & area ratios, unit layout typology, parking, stair spec)
- tier2 (72): dimension/space data readable from the IFC for which Neufert gives typical
  values — convertible into intent checks (room program, door widths, storey/ceiling heights,
  window sizes, furniture per room, space use by function, stairs/railings)

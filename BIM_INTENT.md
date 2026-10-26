# 4_bim_intent — Neufert design knowledge → rules → IFC

> **On branch `zihan_dev1` of bi2m.** This file was the top-level README of the `4_bim_intent` folder; bi2m's own
> README.md stays as it is. Not in git (see the `zihan_dev1` block in `.gitignore`): the Neufert book and its full
> parse (`data/neufert/`), the 370-model corpus and its extracted graphs (`data/model_ifc4_0001-0370/`, `runs/graphs/`),
> the ifc-bench `.ifc` files, `.env`. The scripts expect them at those paths locally.


Goal: extract design knowledge from Neufert *Architects' Data*, rewrite it as context → requirement
rules, map the rules onto IFC models (ifc-bench subset) and use the result to probe what LLMs know.
Reorganised 2026-10-20; the old numbered stage folders (`0_archi`, `1_agentic_framework`, `2_intent`,
`3_cuatesting`) are gone — see the map below.

```
data/
  neufert/            the book: Neufert-4th-edition.pdf, vlm_pages.sqlite (VLM parse), embeddings.sqlite
    dataset/          figure-centric export: pages.jsonl (592 pages), index.jsonl + figures/ (3967 illustrations)
  ifc_bench/          9 ifc-bench projects: <project>/arc.ifc + model_card, license, snapshot, per-project QA csv
                      neufert_qa.csv/.json (67 Neufert-tagged QA), all_qa.csv (452), earlier tagging csvs
knowledge/            Neufert knowledge base built on the hard QA
  build_hard_qa.py    knowledge-hidden QA items (items/<project>.py, items/x_g*.py) → hard_qa.jsonl / .csv
  tools/knowledge_md.py  hard QA quotes → 122 knowledge points: KNOWLEDGE.md, knowledge_probes.jsonl
  knowledge/          per-point metadata: _levels.json (BOT level, IFC needs), _scope.json, _extra_cites.json, x_*.json
  tools/              exact_check.py (verbatim-quote audit), nsearch.py (grep the book), facts.py (IFC fact sheets)
  GUIDE.md            how to write hard QA items
  model_ifc4_0001-0370/  370 anonymised IFC4 models (0001.ifc … 0370.ifc, 4.1 GB); 0204 is the first one mapped
rules/                knowledge rewritten as context → requirement rules (103 rules from 119 knowledge points)
  rules_pilot.jsonl   R01–R12 pilot rules; rules_office.jsonl R13–R47 (build_rules_office.py); rules_general.jsonl R48–R103
                      (build_rules_general.py: residential, accessibility, high-rise, envelope, area measurement; adds
                      context.grounding + context.concreteness). Every builder verifies its quotes before writing.
  extract_graph.py    ifc → graph.json (nodes = rule-relevant entities, edges = ifc + derived); output in runs/graphs/
  instances_*.jsonl   rule instances per model: fantasy_office_building_1 (12), ifc4_0204 (103, build_instances_0204.py)
  match_rules.py      rules × all graphs → runs/scan370/ (matches.jsonl, summary.md/.csv) + scan370_summary.json for the site
  build_decisions.py  17 design-decision topics (core / secondary / convention) grouping the rules → decisions.json
  build_scenarios.py  scenario layer for the active rules (target element, context elements + parameters read, graph
                      relations, situation in words) → scenarios.jsonl; shown inside each rule card on the site
  archive_rules.py    active / archived status per rule from the intersection with the colleague's sweep
                      (neufert_applicability_*.json at the repo root) → _status.json; nothing is deleted
  PILOT.md            rule schema, findings on both models, the context-representation / grounding discussion
site/                 Neufert QA Workbench (static page): build_site.py → index.html
intent/               design-intent extraction pipeline (two extractors + judge); output in runs/intent_pilot_residential
qa_agent/             closed-book QA agent + judge that answers the knowledge probes; output in runs/qa_probes
runs/                 all generated outputs: intent_pilot_residential/, qa_probes/<timestamp>/, judge_tune/
archive/              legacy, not maintained: 0_archi_rag_agent (first RAG agent + tier-1 KB), 3_cuatesting (desktop CUA test)
```

## Rebuild chain (run from this directory, `.venv/bin/python` has the deps)

```bash
python3 knowledge/build_hard_qa.py          # verifies every citation against data/neufert/embeddings.sqlite
python3 knowledge/tools/knowledge_md.py     # KNOWLEDGE.md + knowledge_probes.jsonl (fails if a point has no quote)
python3 knowledge/tools/exact_check.py      # audit: every quote verbatim on its page
python3 rules/build_rules_office.py         # rules_office.jsonl
.venv/bin/python rules/build_rules_general.py   # rules_general.jsonl (reads knowledge_probes.jsonl for the quotes)
.venv/bin/python rules/extract_graph.py data/model_ifc4_0001-0370/0204.ifc runs/graphs/ifc4_0204.json   # needs ifcopenshell (in .venv)
.venv/bin/python rules/build_instances_0204.py  # instances_ifc4_0204.jsonl
python3 site/build_site.py                  # site/index.html (reads knowledge/, rules/*.jsonl, runs/qa_probes/)
.venv/bin/python -m qa_agent.run_probes --models sonnet --formats mcq --limit 5     # see qa_agent/README.md
.venv/bin/python -m intent.run_pilot --chapter "Residential buildings" --stage all  # see intent/README.md
```

Quotes everywhere (hard QA, knowledge points, rules) must be verbatim substrings of a text / caption / table row
in `data/neufert/embeddings.sqlite`; the builders refuse to write otherwise.

## Page ids

`page_XXXX` is the PDF page key used by the dataset and the databases; the printed book page is `XXXX − 12`.

## Keys

`.env` — `OA_OPENAI_KEY`, `Anthropic_KEY`, `Gemini_KET`, `JEV_KEY` (read by `qa_agent/config.py` and `intent/llm.py`).

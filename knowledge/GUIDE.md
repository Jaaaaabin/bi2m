# Writing knowledge-hidden QA ("进阶题")

## Scope

The benchmark tests **early design stage** knowledge only: massing, layout, room sizes and
proportions, circulation, openings (doors and windows), envelope and wall construction choices,
and building-regulation thresholds (escape routes, fire compartments, accessibility, habitable-room
minimums).

Out of scope — do not write items on, or cite rules about: MEP sizing and rates (ventilation
openings and air flows, smoke-extraction vents), product specifications (e.g. glazing type,
self-closing/smoke-proof door closures), interior fit-out details (worktop heights, wheel stops and
similar fittings), and acoustic finishes (reverberation, absorption areas).

Goal: upgrade every Neufert-tagged ifc-bench question into a harder question where a Neufert
rule is **hidden in the question**. The solver must (1) know the rule, (2) read the matching
facts from the IFC model, (3) combine them. The question never states the rule or threshold.

Reference implementation: the `fantasy_residential_building_1` items in
`build_hard_qa.py`. Read them before writing — match their tone, length and rigour.

## Pairing rule (strict)

- Every row of `data/ifc_bench/<project>/neufert_qa.csv` gets **at least one `paired` item** with that id in
  `derived_from`. A paired item asks about **the same object and the same data** as the original
  (same room, same door, same storey heights …), only with the rule hidden inside.
- Two originals may share one item if they are about the same object (e.g. laundry room +
  bathroom count). Put both ids in `derived_from`.
- A good question that is not about the same object as any original → `pairing='supplement'`
  (optionally `derived_from=[related id]` or `[]`). Supplements are fine but optional.
- If the original's data is genuinely unusable (e.g. the model has no such element), still write
  a paired item about what the model *does* hold for that object, or about why the rule cannot be
  checked from this model (see the fantasy_residential kitchen item) — never skip an original.

## Question types (`question_type`)

| type | meaning |
|---|---|
| compliance | a hidden threshold decides a verdict |
| diagnosis | spot what is off / which element governs, and explain |
| derivation | compute a value that needs a rule |
| intent | why the designer did X / what the layout is meant for (answer must still be defensible from rule + data) |

Aim for a mix; avoid writing only compliance items.

## Item format

```python
ITEMS += [
    dict(project='fzk_house', derived_from=[514], question_type='compliance',   # pairing defaults to 'paired'
         question='...',            # English, concrete, names the model's own rooms/elements, never states the rule
         answer='...',              # English, short paragraph: verdict/number first, then the reasoning with numbers
         evidence=['...', '...'],   # IFC facts used: entity/type names, values, GlobalIds or space names
         hidden_knowledge='...',    # one line: the rule(s) the solver must bring
         basis=[C['stride'], cite('page_0133', 'verbatim quote', 'page_0133_intent_00X')],
         rubric=['...', '...']),    # 2–4 gradeable key points
]
```

Each file `items/<project>.py` contains only `ITEMS += [...]` (plus `C['new_key'] = cite(...)`
lines if you add reusable citations). `cite`, `C`, `ITEMS` are provided by the build script.

## Citations

- `cite(page_id, quote, intent_id=None)` — the quote must occur **exactly, character for
  character including whitespace, line breaks and tabs**, in a text/caption/table row of that page in
  `data/neufert/embeddings.sqlite` (same text as `data/neufert/vlm_pages.sqlite`). Copy quotes from the database, not from
  `pages.jsonl` output. `tools/exact_check.py` re-checks every quote. LaTeX in the source text must be copied as is, e.g. `\\( \\geq 2.75 \\)`.
  The build fails on a mismatch, so run it after every few items.
- `intent_id` only for residential intents in `runs/intent_pilot_residential/intents.jsonl`
  (pages 0147–0178). For other chapters (offices, hotels, building components, basics) cite the
  page text directly.
- Reusable citations already in `C` (see `build_hard_qa.py`): stride, ideal_ratio, landing,
  run_len, two_flats, essential, escape_35, guard, guard_low, guard_high, bf_door,
  bf_toilet_door, door_bath, door_room, door_front, door_frame, lift_door, lift_req,
  two_per_floor, laundry, balcony_pct, balcony_size, bed_twin, bed_single, bed_generous,
  kitchen_hab, kitchen_work, kitchen_dining, kitchen_L, hab_room, bf_corridor,
  no_sliding_exit, bath_min, bath_next_bed, kitchen_width, kitchen_move, open_air, open_kitchen.
- Only use a rule that the book actually states. If you cannot find a quote, choose another
  angle. Never invent thresholds or attribute DIN numbers the text does not give.

## Finding rules

```bash
python3 knowledge/tools/nsearch.py "REGEX" "Chapter regex" 250
```
Chapters: Basics (pp.1–41, incl. barrier-free pp.21–25), Building components (pp.66–134:
windows ~p.96–97, doors pp.113–117, stairs pp.120–126, lifts p.127ff), Residential buildings
(pp.135–166), Accommodation (hotels, pp.167–187), Administration and offices (pp.231–253),
Building services. The page id is `page_%04d` of the pdf index (book page + 12), printed by the
search tool as `page_XXXX_text_NNN`.

Useful office/hotel anchors already found: offices ceiling height 2.75 m (min 2.50 m for
sedentary work) `page_0255`;
restaurants: dining ceiling heights by area, aisles 0.80 m, doors 0.90 m, 1.0 m exit width per
150 people `page_0187`; residential homes: rooms ≥8 m², 2.40 m, window 1/8, two escape routes
`page_0179`; workplace windows: sill heights 0.85–1.25 m, visual connection ≥1/10 of wall width
`page_0109`.

## Facts

`hard_qa/facts/<project>.json` — storeys, spaces (area, height, bbox dims), doors (type,
operation, width/height, bounding or containing spaces), windows (size, approx. sill, spaces),
stairs (risers, tread, width props), railings (height), furniture by space. Also read the
original QA (`data/ifc_bench/<project>/neufert_qa.csv`, `all_qa.csv`) — original ground truths contain extra
facts (and sometimes errors; prefer the IFC when they disagree and say so).

For anything else, query the IFC directly:
```bash
/private/tmp/claude-501/-Users-zihandeng-Desktop-1-Projects-4-bim-intent/2dfcda58-4516-468f-9f06-6959e3555173/scratchpad/ifcenv/bin/python -c "import ifcopenshell; ..."
```
(if that venv is gone: `python3 -m venv /tmp/x && /tmp/x/bin/pip install ifcopenshell numpy`).

## IFC pitfalls (put them to use as hidden knowledge where apt)

- `OverallWidth` of a door is the overall/nominal size, not the clear passage width.
- Revit imperial defaults (1.219 m = 4 ft, 0.914 m = 3 ft, 36"/84" doors) signal software
  defaults, not design intent. (the dropped `4351` model was in feet; watch for imperial values if it ever comes back.)
- Space bounding boxes are axis-aligned approximations — say "≈" and "geometry bounding box".
- `fantasy_hotel_1` and `samuel_macalister_sample_house` spaces carry no area; use bbox only as
  an approximation and say so, or use the original answers' areas.
- Storey names like "Ceiling", "Roof Line", "TO Parapet" are reference levels, not floors.

## Quality bar

- Every number in `answer` must be traceable to `evidence` or to arithmetic on it.
- The verdict must follow from the cited rule; state assumptions explicitly.
- Don't build an item on an original answer's estimate unless the evidence says so.
- One question = one clear task. No multi-part questions with more than ~3 asks.
- Check with `HARD_ONLY=<project>[,<project>] python3 knowledge/build_hard_qa.py`
  from the project root (dry run: loads only your item files, writes nothing). It must print your
  projects with `unpaired []` and `not-a-neufert-id []`. Do not run it without HARD_ONLY.

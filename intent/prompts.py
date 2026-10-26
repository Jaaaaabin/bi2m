"""System prompts for extractor and judge."""

from .schema import CONCEPT_GLOSSARY

_CONCEPTS = "\n".join(f"  - {k}: {v}" for k, v in CONCEPT_GLOSSARY.items())

EXTRACTOR_SYSTEM = f"""You are extracting DESIGN INTENTS from one page of Neufert's *Architects' Data*
(English edition). A design intent is any statement that prescribes, recommends, or
gives a typical value for how a building, room, or building element should be
sized, placed, oriented, arranged, or related to other elements.

You will receive one page: header (chapter, subheadings), all body-text paragraphs
with IDs, and all figure captions with IDs (plus any attached tables).

## What counts as an intent (extract ALL of these — over-extract rather than miss)
- hard_constraint: a minimum/maximum/required value or rule ("at least 8 m²", "must",
  "not less than"), including values coming from standards/regulations.
- soft_principle: a recommendation or design principle ("should be", "desirable",
  "preferably", "avoid", "good practice") with or without numbers.
- typical_value: a typical/normal/usual dimension, area, ratio or count ("normally",
  "usually", "approx.", "average", table rows of standard sizes).
- tacit: a rule that is only implied by a figure caption or by an example
  (e.g. a caption "Privacy" next to a plan implies a rule). Use sparingly on text-only
  input; mainly rely on captions.

## What does NOT count
- Pure history, typology description with no prescriptive content, definitions of terms,
  page-navigation text, index entries, unit conversions.

## Granularity rules
- ONE intent per distinct prescription. If a sentence gives a value for parents' bedroom
  AND a value for a single bedroom, output TWO intents.
- Every table row that carries a value is a candidate intent.
- Keep condition fields tight: who/where does this apply (building type, room type,
  occupancy, adjacency, storey, orientation).
- `statement` must be self-contained: a reader must understand it WITHOUT the page.
  Include the applicability context inside the sentence.

## Source and quote — anti-hallucination
- `source.quote` MUST be copied verbatim (character for character, <=200 chars) from ONE
  paragraph, caption or table row on THIS page. Do not paraphrase. Do not merge two
  places. If you cannot find a verbatim supporting span, do not output the intent.
- List every paragraph/figure ID you used.

## Prescription operators
- "minimum", "at least", "not less than", "minimal space of approx. X" -> op ">=" (value_min=X)
- "maximum", "not more than" -> op "<=" (value_max=X)
- "approx.", "about", "average" with no min/max sense -> op "~"
- "X-Y" or "between" -> op "range" (value_min, value_max)
- exact size stated as fact -> op "="

## Rationale
- `rationale.concept` from this fixed list:
{_CONCEPTS}
- `rationale.stated` = true ONLY when the page text itself gives the reason.
  Otherwise stated=false and phrase `rationale.text` as an inference
  ("Inferred: ...").

## IFC checkability
- direct: computable from ONE element/space's own geometry or properties
  (area, height, width, sill height, window/floor ratio, count).
- relational: needs relations between elements, spaces or storeys (adjacency,
  alignment across storeys, stacking of wet rooms, door position relative to room,
  orientation of a window relative to site north).
- not_checkable: material choice, colour, climate/process advice, taste, cost.
- `check_sketch`: one line describing the check (e.g. "IfcSpace.LongName=='bedroom' ->
  net area >= 8"), or null.

Output must follow the provided JSON schema exactly. Set `page` to the page ID given.
"""

JUDGE_SYSTEM = """You are the adjudicator in a two-extractor pipeline that pulls design intents
from one page of Neufert's *Architects' Data*. You receive the page text and two candidate
lists, A and B, produced independently by two models with the same schema. Candidates are
numbered A0, A1, ... and B0, B1, ...

Produce ONE merged list for the page as a list of DECISIONS. Each decision references the
candidate index/indices it is built from; do not rewrite records — just point and fix.

Rules
1. Same intent in A and B -> ONE decision with both a_index and b_index. Choose `prefer`
   = the side whose record is more precise/correct (values, operator, condition, quote).
   Add `fixes` for any field on the preferred record that the other side got better.
2. Intent only in A (or only in B) -> decision with the other index null.
3. Every candidate index must appear exactly once: either in a decision or in `rejected`.
4. REJECT only: not prescriptive (history, definitions, descriptions), quote not on the
   page or meaning not supported by it, out of this page's scope, or too vague to be a
   rule. When in doubt KEEP — recall matters more than precision here.
5. Check and fix via `fixes` where needed:
   - prescription.op: "minimum/at least/minimal" must be ">=", "approx." alone "~".
   - rationale.stated: true ONLY if the page text literally gives the reason.
   - ifc_checkable / check_sketch: sensible?
   - source.quote: must be verbatim and on the page; fix to exact span if slightly off.
   - statement: must be self-contained (context inside the sentence).
6. Never invent intents that neither A nor B proposed.
7. `fixes[].value` is a JSON literal string: 12.5 / true / null / plain text for strings.

Output must follow the provided JSON schema exactly.
"""

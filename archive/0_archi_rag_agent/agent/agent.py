"""Neufert agent: takes a room-design case, pulls relevant Neufert knowledge from sqlite."""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

from .tools import TOOLS, dispatch


SYSTEM_PROMPT = """You are a Neufert ('Architects' Data') research assistant.

The user gives a structured room description. Typical fields:
- room_type (bedroom, meeting room, kitchen, bathroom, office, lab, ...)
- area (m²) and height (m)
- storey + building type + climate
- adjacency list (each neighbouring room with its type)
- **boundary topology** (when provided) — explicit per-element layout:
    * walls labelled W1, W2, W3, ... — each may be `interior partition shared with
      <neighbour(s)>` or `exterior (facade)`
    * one wall may straddle TWO or more neighbours (e.g. `W3 shared with hallway,
      office_priv`) — treat as TWO segments with potentially different acoustic
      requirements
    * doors are mapped to a specific wall: `W1 with 1 basic_door → hallway`
    * windows are mapped to a specific wall: `W4 with 2 basic_window → exterior`
    * slabs are typed: `basic_slab (floor)` / `(ceiling)` / `(roof)`

Use the user's W-IDs verbatim in your output. Do NOT renumber.

The user does NOT supply boundary dimensions. They want you to LOOK UP in Neufert
what dimensions, types, materials, and performance values are appropriate FOR THIS
room type and EACH boundary's specific adjacency. You are specifying the boundaries,
not validating them.

Your job: produce a COMPREHENSIVE Neufert specification for this exact room — an
architect should be able to draw the room and order each W1/W2/W3/W4 + door + window
+ slab build-up from your output without opening the book.

Adjacency-driven chapter triggers:
- adjacent room of type `lab` / `laboratory` → also pull LABORATORY / BIOLOGICAL
  ENGINEERING chapter (lab walls, doors, ventilation, fire/chem rules)
- adjacent `bathroom_wc` → BATHROOMS chapter (moisture, plumbing-noise rules)
- adjacent `kitchen` → KITCHEN chapter
- adjacent `hallway` and any escape concern → FIRE PROTECTION chapter
- exterior wall (facade) present → BUILDING PHYSICS / Thermal insulation, plus
  the building-type chapter's facade & sun-shading guidance

═══════════════════════════════════════════════════════════════════════════
RETRIEVAL WORKFLOW — do all of these, do not skip steps
═══════════════════════════════════════════════════════════════════════════

1. **Room-type chapter**: identify the building-type chapter for this room
   (RESIDENTIAL BUILDINGS / OFFICE BUILDINGS / HOTELS / SCHOOLS / HOSPITALS / ...).
   For ambiguous cases use `list_subheadings`.

2. **Component chapters** — always include:
   DOORS, WINDOWS, ROOMS, ACCESSIBLE BUILDING, LIGHTING, BUILDING PHYSICS.
   Add FIRE PROTECTION if the case mentions escape, basement, hotel, public.
   Add HOUSING DENSITY for scale-relevant residential.

3. **Adjacency chapters**: for EACH adjacent room type in the case, look up its
   own chapter — adjacency rules often live in the neighbour's chapter
   (e.g. bedroom-bathroom moisture is in BATHROOM section).

4. **Use semantic_search at least 4 times** with distinct angles:
   - room-type query: "<room_type> area requirements"
   - acoustic / privacy query: "sound insulation between <room_type> and <neighbour>"
   - daylight query: "<room_type> window size daylight ratio"
   - one bonus topic relevant to the case (storey, climate, furniture, ventilation)

5. **keyword_search** for exact strings: the room_type word, each neighbour type,
   "ceiling height", "sill", "dB".

6. **Read full pages** with `get_page` / `get_pages_bulk`. Never answer from snippets.

7. **Figures**: call `list_figures_on_page` on the most relevant pages, then save
   **6–12 figures** with `save_figures`. Prioritise:
   - typical floor-plan figures of this room type
   - figures showing per-boundary dimensions (door width, window sill, dB values)
   - tables of area / height / lux / dB
   Reference each in markdown as `![caption](filename.png)`.

═══════════════════════════════════════════════════════════════════════════
OUTPUT FORMAT (Markdown, user's language)
═══════════════════════════════════════════════════════════════════════════

## Case summary
One-line restatement + computed extras: floor area, volume.

## Applicable Neufert sections
Bullet list `subheading — page_XXXX`.

## Dimensional standards
- Area minimums and recommended ranges for this room type (range + average).
- Ceiling-height minimums for this room/building type.
- Modular grids if applicable.

## Boundary specification (Neufert-derived)

**Iterate by the user's element IDs**, not by element type. For every W1, W2, W3,
... and every door, window, slab in the topology, give a dedicated subsection.

**Heading discipline:** every per-element subsection uses `###` (H3), and any
sub-segment inside it (e.g. one segment of a wall that straddles two neighbours)
uses `####` (H4). Never use `##` for individual elements — `##` is reserved for
the top-level report sections (Case summary / Applicable Neufert sections /
Dimensional standards / Boundary specification / Adjacency review / ...).

Do NOT invent dimensions — pull every number from the book and cite the page.

For EACH wall (use the user's W-ID and adjacency):

  ### W<n> — <interior partition shared with X> | <exterior (facade)>
  - **Construction type** (masonry / stud / framed / sandwich / concrete) suited
    to this exact adjacency
  - **Thickness / build-up** if Neufert gives one
  - **Fire class** (F30 / F60 / F90) per Neufert's wall table
  - **Airborne sound R'w (dB)** for this adjacency from DIN 4109 — if the wall
    straddles 2 neighbours, give R'w per neighbour separately
  - **For exterior walls only**: U-value (W/m²K) per EnEV, thermal-bridge note,
    sound attenuation vs outdoor noise, sun-shading approach for windows on it
  - **For wall-to-lab adjacency**: any extra Neufert lab-wall rules
    (gas-tightness, chemical resistance, services routing)

For EACH door (use the user's mapping `door → wall → neighbour`):

  ### Door <n> on W<m> → <neighbour>
  - clear width (mm) from Neufert's room-type table
  - clear height (mm) and modular wall-opening size (DIN 18100)
  - door type (panel / acoustic / fire-rated / lab-door) suited to this adjacency
  - opening direction rule
  - sound-insulation Rw (dB) — must be consistent with the host wall's R'w

For EACH window (use the user's mapping `window → wall`):

  ### Window <n> on W<m>
  - required glazed area for this room = floor_area × Neufert ratio (1/8 or 1/10);
    when there are N windows on the same wall, divide and give per-window minimum
  - sill height (m)
  - suggested width × height respecting Neufert's ≥65% of room width rule
  - glazing type and Uw / Ug per EnEV
  - sun-shading approach (orientation-aware if user supplied facing)
  - escape-window rule if storey or use demands it

For EACH slab (respect the typed kind — floor / ceiling / roof):

  ### Slab <n> — <floor | ceiling | roof>
  - ground-contact floor → thermal U-value (EnEV), damp-proofing, build-up, traffic
    load
  - intermediate / separating ceiling → R'w + L'n,w from Neufert's slab table,
    floating-screed build-up
  - roof → roof type, U-value, vapour control, fire class
  - fire class per Neufert
  - traffic / live load if Neufert specifies for this room/building type

## Adjacency review
For EACH adjacent room from the case, list:
- typical relationship (privacy / noise / moisture / smell / traffic)
- required wall and door treatment (sound insulation dB, door class, vapour barrier)
- layout do/don'ts (e.g. avoid bedroom door directly facing bathroom)

## Daylight & lighting
- Minimum daylight factor / window area ratio for this room type.
- Recommended artificial lighting (lux) and lighting class.
- Sill heights, view requirements.

## Acoustics & ventilation
- Sound-insulation values for partitions and doors (DIN 4109 if relevant).
- Air-change rate / ventilation requirements.
- HVAC, services notes.

## Sanity check vs the case
Numerical comparisons (only for what the user DID give):
- Is the room area within Neufert's recommended range for this room type?
- Does ceiling height meet residential minimum and recommended values?
- Is the count of doors, windows, slabs reasonable for this room type?
- Storey-specific flags (basement → daylight; ground → privacy / thermal bridge; ...).
- Adjacency-specific flags from the actual neighbour list.

Do NOT comment on door / window / slab dimensions because they were not supplied —
your job in the Boundary specification section is to recommend them.

## Figures
Embed `![caption](filename.png)` for each saved figure.

## Sources
Final list of unique pages cited.

═══════════════════════════════════════════════════════════════════════════
STRICT RULES
═══════════════════════════════════════════════════════════════════════════
- Cite `page_XXXX` after every concrete fact.
- If a topic has no data in Neufert, write "Not covered in Neufert" — never invent.
- Never invent boundary dimensions. Every number must come from Neufert.
- semantic_search ≥ 4 times; keyword + subheading alone are insufficient.
- Save 6–12 figures, no fewer.
- The Adjacency review must address each neighbour from the case individually.
- The Boundary specification must use the user's W-IDs verbatim and iterate one
  H3 subsection per element, not per element type.
- A wall straddling two neighbours gets two H4 sub-segments inside its H3, with
  separate R'w values (one per neighbour segment).
- Exterior walls always get U-value + thermal-bridge note in addition to R'w.
- Slabs are treated by their typed kind (floor vs ceiling vs roof), not generically.
"""


def load_client() -> OpenAI:
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
    key = os.getenv("OA_OPENAI_KEY") or os.getenv("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OA_OPENAI_KEY not found in .env")
    return OpenAI(api_key=key)


def _slugify(text: str, max_len: int = 50) -> str:
    s = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]+", "_", text)[:max_len].strip("_").lower()
    return s or "case"


def run_agent(
    case: str,
    model: str = "gpt-5.4",
    max_iters: int = 30,
    verbose: bool = True,
    output_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Run the agent on one case. Returns {answer, output_dir, messages}."""
    client = load_client()

    if output_dir is None:
        output_dir = Path("outputs") / f"{_slugify(case)}_{int(time.time())}"
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    ctx = {"output_dir": str(output_dir)}

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": case},
    ]

    usage_total = {"prompt": 0, "completion": 0, "total": 0}

    for step in range(max_iters):
        resp = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
        )
        if resp.usage:
            usage_total["prompt"] += resp.usage.prompt_tokens
            usage_total["completion"] += resp.usage.completion_tokens
            usage_total["total"] += resp.usage.total_tokens
        msg = resp.choices[0].message
        assistant_msg: dict[str, Any] = {"role": "assistant", "content": msg.content}
        if msg.tool_calls:
            assistant_msg["tool_calls"] = [tc.model_dump() for tc in msg.tool_calls]
        messages.append(assistant_msg)

        if not msg.tool_calls:
            if verbose:
                print(f"[agent] finished after {step + 1} step(s)")
                print(f"[usage] prompt={usage_total['prompt']:,} "
                      f"completion={usage_total['completion']:,} "
                      f"total={usage_total['total']:,}")
            answer = msg.content or ""
            (output_dir / "answer.md").write_text(answer, encoding="utf-8")
            (output_dir / "_usage.json").write_text(
                json.dumps({"model": model, **usage_total}, indent=2),
                encoding="utf-8",
            )
            return {
                "answer": answer,
                "output_dir": str(output_dir),
                "messages": messages,
                "usage": usage_total,
            }

        for tc in msg.tool_calls:
            name = tc.function.name
            args = json.loads(tc.function.arguments or "{}")
            if verbose:
                print(f"[tool] {name}({json.dumps(args, ensure_ascii=False)[:120]})")
            result = dispatch(name, args, ctx=ctx)
            messages.append(
                {"role": "tool", "tool_call_id": tc.id, "content": result}
            )

    return {
        "answer": "[agent] max iterations reached without final answer",
        "output_dir": str(output_dir),
        "messages": messages,
    }

"""Knowledge-hidden QA built on top of the Neufert-tagged ifc-bench questions.

Each item hides a Neufert rule inside the question: the solver has to bring the rule,
read the matching facts from the IFC model, and combine them. Every Neufert citation is
checked verbatim against data/neufert/dataset/pages.jsonl (body text + figure captions) or against
runs/intent_pilot_residential/intents.jsonl before anything is written.

Run from the project root:  python3 knowledge/build_hard_qa.py
"""
import collections, csv, json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'knowledge')

# ---------------------------------------------------------------------------
# Neufert sources
# ---------------------------------------------------------------------------
pages = {}
DATASET = os.path.join(ROOT, 'data', 'neufert', 'dataset')
for line in open(os.path.join(DATASET, 'pages.jsonl'), encoding='utf-8'):
    p = json.loads(line)
    pages[p['page']] = p
captions = {}
for line in open(os.path.join(DATASET, 'index.jsonl'), encoding='utf-8'):
    x = json.loads(line)
    for c in (x.get('captions') or []) + ([x['caption']] if x.get('caption') else []):
        t = c if isinstance(c, str) else (c.get('text') if isinstance(c, dict) else None)
        if t:
            captions.setdefault(x['page'], []).append(t)
intents = {}
for line in open(os.path.join(ROOT, 'runs', 'intent_pilot_residential', 'intents.jsonl'), encoding='utf-8'):
    r = json.loads(line)
    intents[r['id']] = r


def norm(s):
    return re.sub(r'\s+', ' ', s).strip()


import sqlite3
_db = sqlite3.connect(os.path.join(ROOT, 'data', 'neufert', 'embeddings.sqlite'))
SOURCE = {}
for _pg, _c in _db.execute('select page, content from embeddings'):
    SOURCE.setdefault(_pg, []).append(_c)


def cite(page, quote, intent=None):
    """page: 'page_0133'; quote must occur EXACTLY (character for character, whitespace included)
    in a text/caption/table row of that page in embeddings.sqlite (the parsed Neufert text)."""
    p = pages[page]
    if not any(quote in c for c in SOURCE.get(page, [])):
        hint = ' (matches only after collapsing whitespace)' if any(norm(quote) in norm(c) for c in SOURCE.get(page, [])) else ''
        sys.exit(f'QUOTE NOT EXACT on {page}{hint}: {quote!r}')
    if intent and intent not in intents:
        sys.exit(f'unknown intent id {intent}')
    return dict(page=page, book_page=p['book_page'], chapter=p['chapter'], quote=quote, intent_id=intent)


# ---------------------------------------------------------------------------
# Reusable citations
# ---------------------------------------------------------------------------
C = dict(
    stride=cite('page_0133', 'In order to determine a suitable pitch with the lowest energy requirement, this formula applies: 2 r + t = 59–65 cm.'),
    ideal_ratio=cite('page_0133', 'the best use of \'climbing effort\' is at a stair pitch of 30° and a ratio of riser (r) to tread (t) of 17/29.'),
    landing=cite('page_0133', 'Stairs with landings are required in legally essential stairways with a storey height of \\( \\geq 2.75 \\) m.'),
    run_len=cite('page_0132', 'Length of runs on legally essential stairs is \\( \\geq 3 \\) steps up to \\( \\leq 18 \\) steps'),
    two_flats=cite('page_0132', 'residential buildings with no more than two flats must have a usable stair width min. 0.80 m, 17/28 riser to tread ratio'),
    essential=cite('page_0132', 'legally essential stairs 1.00 m, 17/28'),
    escape_35=cite('page_0133', 'Every location in inhabited rooms and basements must be \\( \\leq 35 \\) m from the stairwell of at least one legally essential stairway or exit.'),
    guard=cite('page_0134', 'Galleries, mezzanines, balconies and circle seating in theatres must have a protective guard rail (height h), compulsory from 1 m height difference:'),
    guard_low=cite('page_0134', 'drop <12 m, h = 0.90 m'),
    guard_high=cite('page_0134', 'drop >12 m, h = 1.10 m'),
    bf_door=cite('page_0034', 'Clear passage width of doors \\( \\geq 0.90 \\) m'),
    bf_toilet_door=cite('page_0034', 'Doors to toilets, showers and changing rooms must open outward.'),
    door_bath=cite('page_0125', 'bath, WC        approx. 70 cm'),
    door_room=cite('page_0125', 'room doors      approx. 80 cm'),
    door_front=cite('page_0125', 'entrance doors\n    to flats      min. 90 cm\nfront doors      up to 115 cm'),
    door_frame=cite('page_0126', 'difference between structural opening and clear pass-through dimension'),
    lift_door=cite('page_0158', 'front doors of flats which are accessed by lifts must have a clear opening width of 90 cm (for wheelchair access). The door height in this case should be at least 2.10 m.', 'page_0158_intent_001'),
    lift_req=cite('page_0154', 'Lifts are required for residential buildings of more than five full floors', 'page_0154_intent_006'),
    two_per_floor=cite('page_0154', 'Two flats per floor is the most common access method, with balanced advantages of residential quality and value for money.', 'page_0154_intent_009'),
    laundry=cite('page_0173', 'If there is no laundry room, the bathroom must be designed with space and connections for a washing machine, washer/dryer and laundry basket.', 'page_0173_intent_004'),
    balcony_pct=cite('page_0167', 'Balconies, loggias and terraces are a part of the living areas, for which they are normally calculated as 25–50%', 'page_0167_intent_010'),
    balcony_size=cite('page_0167', 'B = 9.0 m^2 balcony for 5–6 people', 'page_0167_intent_017'),
    bed_twin=cite('page_0169', 'bedrooms with minimal space of approx. 13 m² (as parents’ room or twin bedroom)', 'page_0169_intent_001'),
    bed_single=cite('page_0169', 'approx. 8 m² (single room).', 'page_0169_intent_002'),
    bed_generous=cite('page_0169', 'a generous twin bedroom of 16.5 m²', 'page_0169_intent_013'),
    kitchen_hab=cite('page_0161', 'As a habitable room, the kitchen must have a clear ceiling height of at least 2.40 m and a window area (structural dimensions) of at least 1/8 of the net floor area.', 'page_0161_intent_024'),
    kitchen_work=cite('page_0162', 'This results in practical working spaces on a floor area of between 5.5 m² and 9.5 m²', 'page_0162_intent_004'),
    kitchen_dining=cite('page_0162', 'Kitchens with dining areas can be planned from approx. 10 m².', 'page_0162_intent_010'),
    kitchen_L=cite('page_0162', 'A good arrangement is an L shape with doors connecting to the living room and corridor: area approx. 14 m²', 'page_0162_intent_014'),
    hab_room=cite('page_0179', 'minimum requirements for floor area (8 m^2), ceiling height (2.40 m), orientation, ventilation and lighting (window area 1/8 of the room area)'),
    bf_corridor=cite('page_0037', 'Corridors and entrance halls must be at least 1.50 m wide.'),
    no_sliding_exit=cite('page_0125', 'Sliding doors and revolving doors are not permissible at emergency exits, which they can block in circumstances of danger.'),
    bath_min=cite('page_0172', 'according to building regulations, belongs to the minimum equipment of a flat or house.', 'page_0172_intent_001'),
    bath_next_bed=cite('page_0172', 'The bathroom is normally next to the bedroom', 'page_0172_intent_007'),
    kitchen_width=cite('page_0161', 'this results in a minimum kitchen width of 2.70 m (min 2.40 m)', 'page_0161_intent_019'),
    kitchen_move=cite('page_0161', 'A movement area of 1.50 m (min. 1.20 m) is therefore required between the stretches of worktop.', 'page_0161_intent_017'),
    open_air=cite('page_0167', 'They generally have a spatial relationship to living and working areas and dining rooms', 'page_0167_intent_001'),
    stair_public=cite('page_0132', 'Stair width in public buildings is calculated according to the required evacuation time'),
    mbo_flats=cite('page_0037', 'In buildings with more than two flats, the flats on one floor must be accessible.'),
    open_kitchen=cite('page_0162', 'Open kitchens require good ventilation and extraction in order not to impair the living and dining room areas with cooking smells.', 'page_0162_intent_016'),
)

# question_type: compliance (hidden threshold decides a verdict) | intent (why / what the designer meant)
#                | diagnosis (spot what is off and explain) | derivation (compute a value that needs a rule)
ITEMS = [
    # ------------------------------------------------------------------ fantasy_residential_building_1
    dict(project='fantasy_residential_building_1', derived_from=[495, 497], question_type='diagnosis',
         question='The ground- and first-floor flats each contain one room type that the two second-floor flats lack. Which room type is it, and what does its absence require of another room in the second-floor flats?',
         answer='The second-floor flats have no utility (laundry) room. Without a laundry room, the bathroom has to be planned with space and connections for a washing machine, washer/dryer and laundry basket, so the two second-floor bathrooms (spaces 42 and 49, 13.37 m² each) must take over the laundry function.',
         evidence=['Utility rooms exist only on Ground Floor (spaces 10, 19) and First Floor (27, 35), 9.42 m² each; none on Second Floor.',
                   'Second Floor has spaces 36–49: wardrobe, toilet, kitchen/dining, living, bedroom, office, bathroom per flat, no utility room.',
                   'Second-floor bathrooms: space 42 and space 49, 13.37 m² each.'],
         hidden_knowledge='A dwelling without a laundry room must provide laundry space and connections in the bathroom.',
         basis=[C['laundry']],
         rubric=['Names the utility/laundry room as missing on the second floor', 'States that the bathroom must then host washing machine/dryer space and connections', 'Identifies the second-floor bathrooms (42, 49)']),
    dict(project='fantasy_residential_building_1', derived_from=[476], question_type='diagnosis',
         question='Each stairwell climbs a 3.40 m storey in a single 17-riser run with 20 cm risers and 27 cm treads, and no landing is modelled. Judged as the building\'s legally essential stair, what is acceptable about this stair and what is not?',
         answer='Acceptable: 17 steps stay within the 3–18 steps allowed per run, and 17 × 0.20 m matches the 3.40 m storey height. Not acceptable: (1) the stride 2r + t = 2 × 20 + 27 = 67 cm exceeds the comfortable 59–65 cm range; (2) with a storey height of 3.40 m ≥ 2.75 m, a legally essential stairway needs a landing, but none is modelled; (3) 20/27 is steeper than the 17/28 ratio that German standards set for legally essential stairs in residential buildings (with a minimum usable width of 1.00 m); the building has 6 flats, so the relaxation for houses with no more than two flats (0.80 m) does not apply.',
         evidence=['Four IfcStair (two per stairwell, Ground→First, First→Second): Pset_StairCommon NumberOfRiser 17, RiserHeight 0.20 m, TreadLength 0.27 m; one IfcStairFlight "Run 1" each, PredefinedType WINDER.',
                   'Storey elevations 0.00 / 3.40 / 6.80 m.', 'No landing slab or second flight in the stair decomposition.', 'Six flats (two per floor).'],
         hidden_knowledge='Stride formula 2r + t = 59–65 cm; landings required for legally essential stairs at storey height ≥ 2.75 m; max 18 steps per run; per German standards for residential buildings, legally essential stairs min. 1.00 m usable width and 17/28 (≤ 2 flats: 0.80 m).',
         basis=[C['stride'], C['landing'], C['run_len'], C['essential']],
         rubric=['Computes 2r + t = 67 cm and flags it above 65 cm', 'Flags the missing landing because 3.40 m ≥ 2.75 m', 'Accepts 17 ≤ 18 steps', 'Notes 20/27 is steeper than 17/28 (optional)']),
    dict(project='fantasy_residential_building_1', derived_from=[498], pairing='supplement', question_type='intent',
         question='Every railing in the model, including the balcony guards on the second floor, is 1.219 m high. What minimum guard height would apply to these balconies, and what does the exact figure 1.219 m suggest about how the height was chosen?',
         answer='Balconies need a guard rail once the height difference reaches 1 m. The highest balconies are on the Second Floor at +6.80 m (roof at +10.20 m), so the drop is below 12 m and the guard must be at least 0.90 m (1.00 m would apply only to workplaces). 1.219 m exceeds this by about 0.32 m. The value is exactly 4 ft (48 in), which points to the software railing family\'s imperial default rather than a height derived from the fall-protection rule.',
         evidence=['31 IfcRailing, all with height 1.219 m (types "Geländer:Glas - Ohne Pfosten" and "Geländer:Holzhandlauf").',
                   'Balconies on First Floor (+3.40 m) and Second Floor (+6.80 m); roof storey +10.20 m.'],
         hidden_knowledge='Galleries, mezzanines and balconies need guard rails from 1 m height difference; 0.90 m for drops under 12 m (1.00 m for workplaces), 1.10 m above 12 m. 1.219 m = 4 ft.',
         basis=[C['guard'], C['guard_low'], C['guard_high']],
         rubric=['Establishes the drop is < 12 m', 'Gives 0.90 m as the minimum', 'Recognises 1.219 m = 4 ft as an imperial default rather than a code value']),
    dict(project='fantasy_residential_building_1', derived_from=[498], question_type='derivation',
         question='When calculating the living area of the first-floor flat that owns Balcony 1, how many square metres would Balcony 1 normally contribute, and how does the balcony compare with a typical family balcony?',
         answer='Balconies are normally counted at 25–50 % of their area, so Balcony 1 (88.74 m²) contributes about 22.2–44.4 m². A typical balcony for 5–6 people is about 9 m², so Balcony 1 is roughly ten times that size and functions as a roof terrace rather than a balcony.',
         evidence=['Balcony 1 (space 50, First Floor): 88.74 m².'],
         hidden_knowledge='Balconies, loggias and terraces are normally counted at 25–50 % toward living area; typical balcony sizes are 6–10 m².',
         basis=[C['balcony_pct'], C['balcony_size']],
         rubric=['Applies 25–50 % to 88.74 m²', 'Gives ≈22.2–44.4 m²', 'Compares with a ≈9 m² typical balcony']),
    dict(project='fantasy_residential_building_1', derived_from=[478], question_type='compliance',
         question='Each flat has one bedroom and a small office. Could the office serve as a child\'s bedroom by minimum room size, and how many people could the flat then sleep?',
         answer='Yes, just. The office is 8.18 m², above the ≈8 m² minimum for a single bedroom (margin 0.18 m²). The bedroom (26.42 m²) is well above the ≈13 m² minimum for a parents\' or twin bedroom. The flat could therefore sleep 3 people (2 + 1).',
         evidence=['Office: 8.18 m² in every flat (spaces 8, 17, 25, 33, 41, 48).', 'Bedroom: 26.42 m² in every flat (spaces 7, 16, 24, 32, 40, 47).'],
         hidden_knowledge='Minimum bedroom sizes: ≈13 m² parents\'/twin room, ≈8 m² single room.',
         basis=[C['bed_twin'], C['bed_single']],
         rubric=['Compares 8.18 m² with ≈8 m²', 'Compares 26.42 m² with ≈13 m²', 'Concludes 3 sleeping places']),
    dict(project='fantasy_residential_building_1', derived_from=[477, 480], question_type='compliance',
         question='The building has three storeys, two flats per floor and a lift. Is the lift actually required, and which requirement on the flat entrance doors does its presence trigger? Do the modelled entrance doors satisfy it?',
         answer='The lift is not required: lifts become mandatory only above five full floors, and this building has three. Two flats per floor is the most common access type. Because the flats are reached by lift, the MBO requires their front doors to have a clear opening width of 90 cm (for wheelchair access), and the door height should then be at least 2.10 m. The six front doors ("TU DF 1 - Haustüre: Front Door", one per flat) are 1.135 m × 2.43 m overall, which leaves room for a ≥ 0.90 m clear width after frame deductions and exceeds the 2.10 m height, so they comply.',
         evidence=['Storeys: Ground, First, Second Floor (+ Roof).', 'Lift doors "TU SF 2 - Lift Zentral" on every floor.',
                   'Front doors "TU DF 1 - Haustüre:Front Door": 2 per floor, OverallWidth 1.135 m, OverallHeight 2.43 m.'],
         hidden_knowledge='Lift required above five full floors; lift-accessed flats need front doors with 90 cm clear width (MBO), and the door height should then be ≥ 2.10 m.',
         basis=[C['lift_req'], C['lift_door'], C['two_per_floor']],
         rubric=['Lift not required (3 ≤ 5 floors)', 'States the 90 cm clear-width requirement (and the recommended ≥ 2.10 m height)', 'Checks 1.135 × 2.43 m against it']),
    dict(project='fantasy_residential_building_1', derived_from=[480], question_type='compliance',
         question='The most common hinged interior door in the model is listed with a width of 0.885 m. Would these doors pass a barrier-free check, and why is the listed width on its own not enough to decide?',
         answer='No. With six flats, the building falls under the rule that in buildings with more than two flats the flats on one floor must be accessible; Neufert gives no separate door width for housing, so the check uses, by analogy, the clear passage width of at least 0.90 m stated for doors in accessible public buildings. 0.885 m is already below that. The listed value is the door\'s overall (nominal) width; the clear pass-through width is smaller once the frame and rebate are deducted, so the real clear width is lower still. A proper check needs the clear opening, not the overall size.',
         evidence=['19 doors of type "Drehflügel 1-flg - Stahlzarge:88.5 x 2.26": OverallWidth 0.885 m, OverallHeight 2.26 m (6 GF, 6 FF, 7 SF).'],
         hidden_knowledge='Buildings with more than two flats: flats on one floor must be accessible; door clear passage width ≥ 0.90 m (stated for accessible public buildings, applied here by analogy); structural/overall door size ≠ clear pass-through width.',
         basis=[C['mbo_flats'], C['bf_door'], C['door_frame'], C['door_room']],
         rubric=['Verdict: fails', 'Cites the 0.90 m clear-width threshold (public-building figure, applied by analogy to the dwellings)', 'Explains overall vs clear width']),
    dict(project='fantasy_residential_building_1', derived_from=[494], question_type='derivation',
         question='Space 5 is a 38.45 m² kitchen and dining room. What minimum window area and ceiling height would it need to count as a habitable room, and can the window requirement be checked from this model\'s window objects alone?',
         answer='It needs a clear ceiling height of at least 2.40 m and a window area of at least 1/8 of its floor area: 38.45 / 8 ≈ 4.81 m². This cannot be checked from the window objects alone. The model has only 10 IfcWindow elements; most glazing is in 42 curtain walls and the sliding glass doors, and there are no space boundaries linking openings to spaces, so the glazing facing space 5 has to be measured geometrically. The spaces also carry no height attribute.',
         evidence=['Space 5 "Kitchen and Dining room": 38.45 m².', '10 IfcWindow, 42 IfcCurtainWall, 51 sliding glass doors (1.829 × 2.134 m).',
                   'No IfcRelSpaceBoundary in the file; IfcSpace has no height property.'],
         hidden_knowledge='Habitable kitchen: clear height ≥ 2.40 m and window area ≥ 1/8 of net floor area.',
         basis=[C['kitchen_hab']],
         rubric=['Computes ≈4.81 m²', 'States 2.40 m', 'Explains why windows alone cannot decide (curtain walls, no boundaries)']),

]


def load_item_files():
    """items/<project>.py files extend ITEMS; they see cite(), C, ITEMS and may add citations to C."""
    import glob
    only = [x for x in os.environ.get('HARD_ONLY', '').split(',') if x]
    files = [x for x in os.environ.get('HARD_FILES', '').split(',') if x]
    for path in sorted(glob.glob(os.path.join(OUT, 'items', '*.py'))):
        name = os.path.basename(path)[:-3]
        if only and name not in only:
            continue
        if files and name not in files:
            continue
        ns = dict(cite=cite, C=C, ITEMS=ITEMS)
        before = len(ITEMS)
        exec(compile(open(path, encoding='utf-8').read(), path, 'exec'), ns)
        for it in ITEMS[before:]:
            it['_src'] = name
        print(f'  {os.path.basename(path)}: +{len(ITEMS) - before} items')


REQUIRED = ['project', 'derived_from', 'question_type', 'question', 'answer', 'evidence', 'hidden_knowledge', 'basis', 'rubric']


def check(rows):
    ok = True
    for r in rows:
        miss = [k for k in REQUIRED if k not in r or r[k] in (None, '')]
        if miss or r['question_type'] not in ('compliance', 'diagnosis', 'derivation', 'intent') or r['pairing'] not in ('paired', 'supplement') or not r['basis']:
            print('BAD ITEM', r.get('hid'), miss, r.get('question_type'), r.get('pairing')); ok = False
    for proj in sorted({r['project'] for r in rows}):
        orig = [int(x['id']) for x in csv.DictReader(open(os.path.join(ROOT, 'data', 'ifc_bench', proj, 'neufert_qa.csv'), encoding='utf-8'))]
        paired = {d for r in rows if r['project'] == proj and r['pairing'] == 'paired' for d in r['derived_from']}
        missing = [o for o in orig if o not in paired]
        stray = sorted(d for d in paired if d not in orig)
        print(f'  {proj:34s} originals {len(orig):2d}  items {sum(r["project"] == proj for r in rows):2d}  unpaired {missing}  not-a-neufert-id {stray}')
    return ok


def main():
    load_item_files()
    os.makedirs(OUT, exist_ok=True)
    counters = {}
    rows = []
    for it in ITEMS:
        n = counters.get(it['project'], 0) + 1
        counters[it['project']] = n
        rows.append(dict(hid=f"H-{it['project']}-{n:02d}", **({'pairing': 'paired'} | it)))
    files = [x for x in os.environ.get('HARD_FILES', '').split(',') if x]
    if files:
        rows = [r for r in rows if r.get('_src') in files]
        bad = [r['hid'] for r in rows if not all(k in r and r[k] not in (None, '') for k in REQUIRED) or r['pairing'] != 'supplement']
        print(f'dry run for files {files}: {len(rows)} items, {sum(len(r["basis"]) for r in rows)} citations verified (nothing written)')
        print('  by project:', dict(collections.Counter(r['project'] for r in rows)))
        if bad: sys.exit(f'items missing fields or not pairing=supplement: {bad}')
        return
    only = [x for x in os.environ.get('HARD_ONLY', '').split(',') if x]
    if only:
        rows = [r for r in rows if r['project'] in only]
    if not check(rows):
        sys.exit('fix the items above')
    if only:
        print(f'dry run for {only}: {len(rows)} items, {sum(len(r["basis"]) for r in rows)} citations verified (nothing written)')
        return
    with open(os.path.join(OUT, 'hard_qa.jsonl'), 'w', encoding='utf-8') as f:
        for r in rows:
            f.write(json.dumps({k: v for k, v in r.items() if k != '_src'}, ensure_ascii=False) + '\n')
    cols = ['hid', 'project', 'derived_from', 'pairing', 'question_type', 'question', 'answer', 'evidence', 'hidden_knowledge', 'neufert_basis', 'rubric']
    with open(os.path.join(OUT, 'hard_qa.csv'), 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow(dict(hid=r['hid'], project=r['project'], derived_from=';'.join(map(str, r['derived_from'])), pairing=r['pairing'],
                            question_type=r['question_type'], question=r['question'], answer=r['answer'],
                            evidence=' | '.join(r['evidence']), hidden_knowledge=r['hidden_knowledge'],
                            neufert_basis=' | '.join(f"p.{b['book_page']}: \"{b['quote']}\"" for b in r['basis']),
                            rubric=' | '.join(r['rubric'])))
    print(f'{len(rows)} items, all {sum(len(r["basis"]) for r in rows)} citations verified ->', OUT)


if __name__ == '__main__':
    main()

# digital_hub: RWTH Aachen DigitalHub office building (Revit 2019, IFC4).
# B01_OKRD -3.37 / E00_OKRD -0.15 / E01_OKRD +3.75 m; 64 spaces; no IfcRelSpaceBoundary.

C['park_230'] = cite('page_0404', 'The Garage (multi-storey car park) Regulations require a minimum width for parking spaces of 2.30 m.')
C['park_250'] = cite('page_0404', 'The Research Company for Roads and Traffic (FGSV), however, recommends a minimum width of 2.50 m for all publicly accessible parking spaces on account of the increasing size of cars.')
C['park_90'] = cite('page_0402', '90° parking, access 5.50 m wide, parking space 2.50 m wide')
C['park_bf'] = cite('page_0034', 'min. 1.50 m deep ...\nin front of therapy facilities (e.g. bath, couch), in front of wheelchair parking places, next to the long side of the vehicle of a wheelchair user in car parks')
C['dh_off_height'] = cite('page_0255', 'Ceiling height 2.75 m according to Vst regulation (enables the later installation of raised floor and deeper suspended ceilings).')
C['dh_corridor_h'] = cite('page_0255', 'Corridors and sanitary facilities are permitted to be 2.30 m high (this can be exploited for installation runs).')
C['dh_toilets'] = cite('page_0250', 'A good ratio is one toilet unit per 50–80 workstations. Space requirement ~0.6–0.8 m² per workstation.')
C['dh_conf_seat'] = cite('page_0250', 'A conference area requires about 2.5 m^2 per seat (without subsidiary areas).')
C['group_office'] = cite('page_0251', 'The experience with the open-plan layout led to the development of group offices with approx. 4–16 workstations')
C['bf_wc'] = cite('page_0034', 'At least one toilet must be provided for wheelchair users in all sanitary facilities.')
C['dh_bf_public'] = cite('page_0037', 'This requirement applies notably to cultural, educational, sport, leisure and health facilities, offices, administration buildings and courts, sales and catering establishments, parking, garages and toilets.')
C['bf_lift_car'] = cite('page_0034', 'Cars of lifts must have a min. clear width of 1.10 m and a clear depth of 1.40 m.')
C['bf_lift_front'] = cite('page_0034', 'The movement area in front of the doors must be as large as the floor area of the car, but min. 1.50 m wide and 1.50 m deep')
C['dh_bf_no_steps'] = cite('page_0034', 'All levels of buildings designed in accordance with the principles of accessibility must be accessible without steps, i.e. using a lift or a ramp.')
C['rest_height'] = cite('page_0187', 'The ceiling heights of dining areas with a floor area ≤50 m² = 2.50 m, > 50 m² = 2.75 m and >100 m² ≥3.00 m')
C['rest_doors'] = cite('page_0187', 'Minimum clear width of aisles in restaurants 0.80 m, doors 0.90 m')
C['landing_len'] = cite('page_0132', 'landing length = \\( n \\) times length of stride + 1 depth of tread')

ITEMS += [
    # ------------------------------------------------------------------ digital_hub (paired, ordered by id)
    dict(project='digital_hub', derived_from=[144], question_type='compliance',
         question='The parking lot holds 26 bays (Revit family "Parkplatz - 01 90: 2500 x 5000") in two facing rows of 13, with about 9.55 m of driving aisle between them; the lot covers about 637 m². Are the bays and the aisle sized appropriately for the building\'s staff and visitors, and could any bay serve a wheelchair user?',
         answer='Bays: 2.50 × 5.00 m at 90°. That is above the 2.30 m minimum of the garage regulations and equal to the 2.50 m minimum recommended for publicly accessible parking. Aisle: Neufert\'s 90° parking example pairs 2.50 m bays with a 5.50 m access aisle, so 9.55 m is about 4 m more than that layout uses; the lot uses 637.33 / 26 ≈ 24.5 m² per bay, compared with about 32.5 × (5 + 5.5 + 5) / 26 ≈ 19.4 m² for a 5.50 m aisle. Wheelchair use: in publicly accessible buildings the parts serving the public, notably including offices and parking, must be usable by disabled people without outside help, and a wheelchair user needs a movement area at least 1.50 m deep beside the long side of the car. All 26 bays are identical 2.50 m bays in continuous rows, and none is flagged for wheelchairs (Rollstuhl = False), so, assuming the lot serves visitors, it has no accessible bay although one would be needed.',
         evidence=['26 IfcBuildingElementProxy "Parkplatz - 01 90:2500 x 5000": Abmessungen Breite 2.50 m, Länge 5.00 m; type property Sonstige.Rollstuhl = False.',
                   'Geometry: rows at y 7.17–12.17 m and 21.72–26.72 m, x 94.13–126.72 m (13 bays each); aisle 21.72 − 12.17 = 9.55 m; bounding rectangle ≈32.6 × 19.55 m ≈ 637 m².',
                   'Original ifc-bench answer #144: gross area 637.33 m², 26 spaces; 13 charging stations and 26 bollards at the outer row ends (#145).'],
         hidden_knowledge='Parking bays ≥ 2.30 m (Garage Regulations), 2.50 m recommended by FGSV for publicly accessible parking; Neufert\'s 90° example: 2.50 m bays with a 5.50 m aisle; publicly accessible buildings (notably offices, parking) must be usable by disabled people in their public parts; 1.50 m movement area beside a wheelchair user\'s car.',
         basis=[C['park_230'], C['park_250'], C['park_90'], C['dh_bf_public'], C['park_bf']],
         rubric=['2.50 m meets the 2.50 m public recommendation (≥ 2.30 m)', 'Aisle 9.55 m vs ≈5.50 m in the 90° example; ≈24.5 m² per bay', 'No wheelchair bay (needs 1.50 m side movement area)']),
    dict(project='digital_hub', derived_from=[152], question_type='derivation',
         question='The original answer lists the ceiling heights as 3.22 m (B01), 3.90 m (E00) and 3.65 m (E01). What do those figures actually measure, and what clear ceiling height do the ground- and first-floor offices really have compared with the usual office requirement?',
         answer='They are not clear ceiling heights. 3.22 m and 3.90 m are the storey heights between structural slab tops (B01_OKRD −3.37 → E00_OKRD −0.15 → E01_OKRD +3.75; the stairwell spaces span exactly these), and 3.65 m is the Height property stored on the E01 spaces. In the offices the clear height is fixed by the modelled suspended ceilings. On E00, the finished floor is at 0.00 m (150 mm floor build-up on the −0.15 m slab) and the ceiling underside at +3.00 m, giving 3.00 m clear. On E01 the floor is at +3.90 m and the ceiling at +6.90 m, again 3.00 m. That is 0.25 m above the 2.75 m standard office ceiling height, with a ≈0.50 m void above the ceiling (to the slab soffit at +3.50 / +7.40 m) for services.',
         evidence=['Storeys B01_OKRD −3.37, E00_OKRD −0.15, E01_OKRD +3.75 m; roof slab soffit +7.40 m.',
                   'Floor build-up "Geschossdecke:FB 150 leer" −0.15→0.00 m and +3.75→+3.90 m; structural slab "STB 250" +3.50→+3.75 m.',
                   '38 IfcCovering "Abgehängte Decke - Rigips Die Dicke 25" (CEILING) at z 3.00–3.03 m (E00) and 6.90–6.92 m (E01).',
                   'Office spaces (e.g. 1-4 Gruppenbüro 1, 2-4 Gruppenbüro 7): Qto Height 3.50 / 3.65 m, geometry 0.00→3.50 m and 3.90→7.40 m; stairwells 1-17 3.90 m, 0-11 3.22 m.'],
         hidden_knowledge='Office ceiling height 2.75 m (Vst), which leaves room for raised floors and suspended ceilings; storey height ≠ clear height.',
         basis=[C['dh_off_height']],
         rubric=['Identifies 3.22 / 3.90 as slab-to-slab storey heights (3.65 = space property)', 'Derives 3.00 m clear from floor build-up and suspended ceiling', 'Compares with 2.75 m (+0.25 m)']),
    dict(project='digital_hub', derived_from=[162], question_type='compliance',
         question='The door schedule gives an average door width of 1.00 m, ranging from 0.80 m to 1.64 m. Which doors define the 0.80 m minimum, and what does that mean for wheelchair users in this office building?',
         answer='The 0.80 m doors are the eight toilet doors ("Stahl-Eckzarge Falztüre: DL - 800 x 2000", 0.87 m overall, 0.80 m clear passage), one for each of the eight WCs on E00 and E01. Neufert requires doors in accessible public buildings to have at least 0.90 m clear passage width, so none of the toilets can be entered in a wheelchair. Where the building is publicly accessible, its parts serving the public (offices and toilets are named explicitly) must be usable by wheelchair users without outside help, and every sanitary facility needs at least one wheelchair-usable toilet, so this is a real deficiency for any public use. The 44 room doors (1.09 m overall, 1.00 m clear) do pass.',
         evidence=['8 IfcDoor "TU DF 1 - Stahl-Eckzarge Falztüre:DL - 800 x 2000": OverallWidth 0.87 m, Abmessungen Durchgangsbreite / Angabe Lichter Durchgang Breite 0.80 m; one per WC space (WC Damen/Herren West/Ost, EG and OG).',
                   '44 IfcDoor "TU DF 1 - Rahmenstock flächenbündig:DL - 1000 x 2000": OverallWidth 1.09 m, clear 1.00 m.',
                   'No space named or typed as an accessible WC; 8 WC spaces 9.81–14.20 m².'],
         hidden_knowledge='Accessible public buildings: door clear passage width ≥ 0.90 m and at least one wheelchair toilet in every sanitary facility; publicly accessible buildings, notably offices and toilets, must be usable by disabled people in their public parts.',
         basis=[C['bf_door'], C['bf_wc'], C['dh_bf_public']],
         rubric=['Identifies the 0.80 m doors as the WC doors', 'Compares 0.80 m with 0.90 m → fails', 'Concludes no wheelchair-accessible toilet in the building']),
    dict(project='digital_hub', derived_from=[163], question_type='diagnosis',
         question='A naive query of IfcDoor.OverallWidth reports 2.27 m as the widest door, while the original answer gives 1.64 m. Which is right, which door is actually widest, and is it adequate for the room it serves?',
         answer='1.64 m is right. Four of the eight "Fluchttüre Endausgang EN 179 - 1010 x 2250" exit doors have OverallWidth and OverallHeight swapped (2.27 × 0.95 m); their quantities give 1.01 × 2.25 m. The widest real door is the double door "ML - 1635 x 2135" (1.635 m) into the 114.5 m² Cafeteria; there are two of them. Opened fully, each gives 1.545–1.60 m clear, well above the 0.90 m minimum for restaurant doors. The active leaf alone, however, is only 0.80 m clear, which fails 0.90 m unless the second leaf is opened. The Cafeteria has 3.00 m clear under its suspended ceiling, exactly the ≥ 3.00 m required for dining areas over 100 m².',
         evidence=['4 × "TU DF 1 - Fluchttüre Endausgang:EN 179 - ML - 1010 x 2250": OverallWidth 2.27, OverallHeight 0.95 (e.g. GlobalId 0YVU7tDBX86u6UVVsSmdwk) vs Qto_DoorBaseQuantities Width 1.01, Height 2.25.',
                   '2 × "TU DF 2 - Rahmenstock flächenbündig:ML - 1635 x 2135" (DOUBLE_DOOR_SINGLE_SWING): OverallWidth 1.635 m; Angabe Lichter Durchgang Breite 1.60, Durchgangsbreite 1.545, Durchgangsbreite Gehflügel 0.80 m; between Cafeteria and Eingangsbereich / Flur.',
                   '1-2 Cafeteria 114.452 m²; suspended ceiling 20.8 × 5.51 m at +3.00 m over finished floor 0.00 m.'],
         hidden_knowledge='Restaurant doors ≥ 0.90 m clear; dining areas > 100 m² need ≥ 3.00 m ceiling height; overall size ≠ clear width.',
         basis=[C['rest_doors'], C['rest_height'], C['door_frame']],
         rubric=['Explains the 2.27 m as swapped width/height on four exit doors', 'Identifies the 1.635 m cafeteria double door as widest', 'Both leaves ≥ 0.90 m but active leaf 0.80 m < 0.90 m', 'Cafeteria 3.00 m clear meets ≥ 3.00 m (optional)']),
    dict(project='digital_hub', derived_from=[168], question_type='diagnosis',
         question='The two "spaces" with the tallest ceiling height are Aufzug Ost and Aufzug West at 10.77 m. What are they really, and is their footprint big enough for a lift that a wheelchair user can use?',
         answer='They are lift shafts, not rooms. Each runs from the basement floor (−3.37 m) to the underside of the roof slab (+7.40 m), and the 10.77 m is the shaft height. A shaft that serves B01, E00 and E01 lets every level be reached without steps. Its footprint is about 2.00 × 2.58 m (5.15 m²), which can hold a car of the barrier-free minimum 1.10 × 1.40 m clear and leaves about 0.90 m and 1.18 m for walls, guides and doors. The car itself and its doors are not modelled (no IfcTransportElement), so the car size and the movement area in front of the doors (at least as large as the car floor area, and min. 1.50 m wide × 1.50 m deep, i.e. ≥ 2.25 m²) cannot be confirmed from the IFC.',
         evidence=['300 Aufzug West, 400 Aufzug Ost: 5.15 m², Qto Height 10.77 m, geometry z −3.37 → +7.40 m, bounding box ≈2.00 × 2.58 m.',
                   'Storeys B01 −3.37, E00 −0.15, E01 +3.75 m.', 'IfcTransportElement count 0.'],
         hidden_knowledge='Accessible buildings: all levels reachable without steps (lift/ramp); lift car ≥ 1.10 × 1.40 m clear; movement area in front of lift doors at least as large as the car floor area, min. 1.50 × 1.50 m.',
         basis=[C['dh_bf_no_steps'], C['bf_lift_car'], C['bf_lift_front']],
         rubric=['Identifies the spaces as lift shafts spanning all levels', 'Compares 2.00 × 2.58 m with the 1.10 × 1.40 m car minimum', 'Notes car/door/forecourt are not modelled']),
    dict(project='digital_hub', derived_from=[169], question_type='diagnosis',
         question='The function breakdown lists Office 594.8 m² (20.9 %), Restroom 93.6 m² and Conference/Meeting 86.4 m², with 38.9 % as "Other". Is the office share plausible, and by common office-planning ratios how many workstations do the restrooms serve and how many seats do the meeting rooms provide?',
         answer='The office share is understated. "Office" is only the 16 Gruppenbüros (594.85 m²). The two Open Workspaces (113.16 + 112.59 = 225.75 m²) are workplaces as well, so offices total about 820.6 m² (28.9 %). The ≈37 m² rooms are group offices, which Neufert sizes for about 4–16 workstations. At about 0.6–0.8 m² of sanitary area per workstation, 93.57 m² of WCs serves roughly 117–156 workstations. At about 2.5 m² per conference seat, the four 21.3–21.9 m² Konferenzräume (86.37 m²) provide about 34 seats, roughly 8–9 per room.',
         evidence=['16 spaces "Gruppenbüro 1–16": 36.72–37.69 m², total 594.85 m².', '1-7 Open Workspace EG 113.163 m², 2-7 Open Workspace 2 112.59 m².',
                   '8 WC spaces, total 93.57 m².', '2-2/2-3/2-11/2-12 Konferenzraum 1–4: 21.317–21.87 m², total 86.37 m².', 'All 64 spaces total 2842.12 m².'],
         hidden_knowledge='Group offices ≈4–16 workstations; toilets ≈0.6–0.8 m² per workstation; conference ≈2.5 m² per seat.',
         basis=[C['group_office'], C['dh_toilets'], C['dh_conf_seat']],
         rubric=['Adds the open workspaces to office area (≈820 m², ≈29 %)', 'Derives ≈117–156 workstations from 93.6 m²', 'Derives ≈34 seats from 86.4 m²']),

    # ------------------------------------------------------------------ digital_hub (supplementary)
    dict(project='digital_hub', derived_from=[152], pairing='supplement', question_type='compliance',
         question='The two stairwell stairs climb 3.90 m from E00 to E01 in 22 risers of 17.7 cm with 27 cm treads, split into two runs of 11 around a 1.24 m deep half landing, and are 1.30 m wide. Do they meet the requirements for a legally essential stair?',
         answer='Yes. The stride is 2 × 17.7 + 27 = 62.4 cm, inside the 59–65 cm range. A storey height of 3.90 m (≥ 2.75 m) requires a landing; it is provided, and each run of 11 steps is within 3–18. The landing must be at least one stride plus one tread, 62.4 + 27 ≈ 89 cm, so 1.24 m is enough. Width 1.30 m also exceeds the 1.00 m minimum usable width that German standards set for legally essential stairs in residential buildings; for public buildings Neufert sizes stair width by evacuation time, so here the 1.00 m (and 17/28) serves only as a benchmark. The pitch 17.7/27 is a little steeper than 17/28, which suits quick movement between office floors. The basement stairs (18 × 17.9 cm, 27.7 cm treads, runs of 9, 3.22 m) also pass: 2r + t ≈ 63.5 cm.',
         evidence=['IfcStair "Fertigbetontreppe:Treppe:2421059" and ":2423903" (E00, HALF_TURN_STAIR): NumberOfRiser 22, RiserHeight 0.177 m, TreadLength 0.27 m; two IfcStairFlight of 11; Tatsächliche Laufbreite 1.30 m.',
                   'Landing slabs 2.80 × 1.24 m at +1.71 → +1.95 m.', 'B01 stairs ":2421041", ":2423887": 18 risers × 0.179 m, tread 0.277 m, two runs of 9.'],
         hidden_knowledge='2r + t = 59–65 cm; landings for storey height ≥ 2.75 m; 3–18 steps per run; landing length = n strides + 1 tread; German standards for residential buildings: legally essential stairs min. 1.00 m usable width, 17/28 (public buildings: width from evacuation time, so applied here as a benchmark).',
         basis=[C['stride'], C['landing'], C['run_len'], C['landing_len'], C['essential'], C['stair_public']],
         rubric=['2r + t = 62.4 cm within range', 'Landing present, runs of 11 ≤ 18, landing ≥ ≈0.89 m', 'Width 1.30 ≥ 1.00 m residential benchmark (noting public-building widths follow evacuation time)']),
]

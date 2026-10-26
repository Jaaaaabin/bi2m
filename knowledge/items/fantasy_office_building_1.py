# fantasy_office_building_1 (TUM student model, Revit export). Storeys EG 0.00 / OG1 4.80 / OG2 9.60 /
# OG3 14.40 / OG4 19.20 m. Space areas from BIM.fundamentals.Area; space height 2.75 m (Qto).
# Only EG and OG1 working spaces are furnished (30 desk combinations); sanitary terminals only on EG/OG1.

C['high_rise'] = cite('page_0256', 'High-rise buildings are those intended for long-term human occupation whose upper-most floor on one side of the building is more than 22 m above ground level.')
C['hr_stairs'] = cite('page_0258', 'High-rise buildings up to 60 m high: at least two emergency stairs must be available, which must be located opposite in two separate fire compartments. Their walking width must be at least 1.25 m.')
C['group_office'] = cite('page_0251', 'The experience with the open-plan layout led to the development of group offices with approx. 4–16 workstations; each office is used by a single team or department.')
C['open_plan'] = cite('page_0251', 'Large-scale office landscapes with 100 or more workstations are made possible by artificial lighting and ventilation')
C['daylight_7'] = cite('page_0253', 'Daylight can mostly be exploited into a room depth of about 7.00 m.')
C['move_area'] = cite('page_0248', 'There should be a free movement area of at least 1.5 m² at the workstation.')
C['desk_area'] = cite('page_0248', 'The desktop working area should be at least 120 × 80 cm (few documents, predominantly screen work; for specialist employees, at least 200 × 80 cm)')
C['conf_seat'] = cite('page_0250', 'A conference area requires about 2.5 m^2 per seat (without subsidiary areas).')
C['conf_access'] = cite('page_0250', 'Conference areas should be directly accessible from the entrance area.')
C['conf_sub'] = cite('page_0250', 'store rooms and a pantry for catering (these subsidiary rooms require about 1/3 of the conference area)')
C['wc_ratio'] = cite('page_0250', 'A good ratio is one toilet unit per 50–80 workstations. Space requirement ~0.6–0.8 m² per workstation.')
C['wc_lobby'] = cite('page_0282', 'Toilet facilities consist of a lobby with washbasins (at least one washbasin per five WCs) and a completely separate room with at least one WC (unless the facilities contain only one toilet and have no direct access to a work, social, changing, wash or sanitary room).')
C['wc_gender'] = cite('page_0282', 'If there are more than five employees, separate toilets must be provided for women and men and these should be available exclusively to employees.')
C['wc_distance'] = cite('page_0282', 'These are to be provided at a distance from each workstation of not more than 100 m or, at the farthest, one storey height')
C['bf_levels'] = cite('page_0034', 'All levels of buildings designed in accordance with the principles of accessibility must be accessible without steps, i.e. using a lift or a ramp.')
C['bf_public'] = cite('page_0037', 'This requirement applies notably to cultural, educational, sport, leisure and health facilities, offices, administration buildings and courts')

ITEMS += [
    dict(project='fantasy_office_building_1', derived_from=[378], question_type='diagnosis',
         question='Every storey of this office building is 4.80 m high, and each of the 14 stairs climbs one storey in a single flight of 24 risers. Which stair rules does this arrangement break, and which does it satisfy?',
         answer='Satisfied: 24 × 0.20 m = 4.80 m matches the storey height, and the stride 2r + t is 2 × 20 + 23.5 = 63.5 cm (straight EG flights and the helical stairs) or 2 × 20 + 20 = 60 cm (straight upper flights), both inside 59–65 cm. Broken: (1) a single run of 24 steps exceeds the maximum of 18 steps per run; (2) with a storey height of 4.80 m ≥ 2.75 m a landing is required, but every stair consists of one "Run 1" flight with no landing; (3) 20 cm risers are steeper than the 17/28 that German standards, as Neufert cites them for residential buildings, set for legally essential stairs (applied here by analogy; for workplaces the health-and-safety rules govern), and on the upper straight flights 20/20 cm gives a 45° pitch, which the stride check alone hides. At about 17 cm the height would need ≈28 risers, i.e. two runs of 14 with a landing.',
         evidence=['14 IfcStair, all Pset_StairCommon NumberOfRiser 24, RiserHeight 0.20 m; TreadLength 0.235 m (Ortbetontreppe EG, helical "Zusammengebaute Treppe" ≈3.4 × 3.4 m) or 0.20 m (straight flights 487526, 512980, 527153, 527346).',
                   'Each stair decomposes into one IfcStairFlight "Run 1", stringers and railings; no landing slab.',
                   'Straight flights 1.50 m wide, 5.45 m (EG) / 4.60 m (upper) long; storeys 0.00 / 4.80 / 9.60 / 14.40 / 19.20 m.'],
         hidden_knowledge='≤ 18 steps per run (a should rule); landing at storey height ≥ 2.75 m; 2r + t = 59–65 cm; legally essential stairs 17/28 (German standards, residential context, applied by analogy).',
         basis=[C['run_len'], C['landing'], C['stride'], C['essential']],
         rubric=['Flags 24 > 18 steps per run', 'Flags the missing landing at 4.80 m', 'Computes 2r + t = 63.5 / 60 cm as within range', 'Notes the 20/20 (45°) or 20 cm riser steepness']),

    dict(project='fantasy_office_building_1', derived_from=[378], question_type='derivation',
         question='The levels are EG 0.00, OG1 4.80, OG2 9.60, OG3 14.40 and OG4 19.20 m. Does the building count as a high-rise, and how many further storeys of the same height could be added before it would?',
         answer='Not a high-rise, but none. A building is high-rise when its uppermost occupied floor is more than 22 m above ground. Here the top floor is OG4 at 19.20 m, which leaves 2.80 m (assuming EG ±0.00 is at ground level). One more 4.80 m storey would put the new top floor at 24.00 m > 22 m, so the building is already at its limit. An added storey would trigger high-rise rules: for high-rise buildings up to 60 m, at least two emergency stairs located opposite each other in two separate fire compartments, each with a walking width of at least 1.25 m (a single staircase only by exceptional approval), a level of escape provision the current open single-flight stairs do not resemble.',
         evidence=['IfcBuildingStorey elevations: EG 0.0, OG1 4.8, OG2 9.6, OG3 14.4, OG4 19.2 m.', 'OG4 holds spaces 41–44 (working spaces and WCs); roofs at ≈19.3 m (wings) and ≈24.2 m (centre blocks).'],
         hidden_knowledge='High-rise: uppermost floor > 22 m above ground; high-rise buildings up to 60 m need at least two opposite emergency stairs in separate fire compartments, ≥ 1.25 m wide (one only by exception).',
         basis=[C['high_rise'], C['hr_stairs']],
         rubric=['Uses 19.20 m vs 22 m', 'Next floor at 24.00 m → zero further storeys', 'States the ground-level assumption', 'Mentions a consequence of high-rise status (optional)']),

    dict(project='fantasy_office_building_1', derived_from=[379], question_type='intent',
         question='All 14 work areas are simply named "Working Space" (34.91, 53.52 and 103.83 m²); only the ground-floor and OG1 ones are furnished, with 7–8 desk combinations each. In the standard office typology, what kind of office are these rooms, and would even the largest one become an open-plan office if furnished like OG1?',
         answer='They are group offices. Neufert describes group offices with about 4–16 workstations, each used by one team, while open-plan offices are office landscapes with 100 or more workstations. The furnished rooms hold 7 (EG, 34.91 m²) and 8 (OG1, 53.52 m²) workstations. At the OG1 density of 53.52 / 8 ≈ 6.7 m² per workstation, the 103.83 m² wing rooms would take about 103.83 / 6.7 ≈ 15, still within 4–16. None comes close to 100, so none is open-plan. The shallow plan supports this reading: depths are ≈4.26 m (and ≈3.58 m for the 31 m-long wings), well within the ≈7 m daylight depth.',
         evidence=['Working spaces: 6, 28 (EG, 34.914 m², bbox 9.38 × 4.26 m, 7 desks each); 10, 13 (OG1, 53.52 m², 13.26 × 4.26 m, 8 desks each); 17, 22, 37, 40, 41, 44 (53.52 m², unfurnished); 14, 19, 31, 32 (103.83 m², 3.58 × 31.26 m, unfurnished).',
                   'Desk combinations "Schreibtisch-Kombination-02 mit PC": 30 in total, all in spaces 6, 28, 10, 13.'],
         hidden_knowledge='Group offices ≈4–16 workstations; open-plan ≥ 100 workstations; daylight depth ≈7 m.',
         basis=[C['group_office'], C['open_plan'], C['daylight_7']],
         rubric=['Classifies as group offices (4–16)', 'Extrapolates ≈15 workstations for 103.83 m²', 'Rejects open-plan (≥ 100)']),

    dict(project='fantasy_office_building_1', derived_from=[381], question_type='derivation',
         question='Working Space 28 (34.91 m²) holds seven "Schreibtisch-Kombination-02 mit PC" desk-and-chair combinations, each ≈1.42 × 1.90 m in plan. How much floor area does each person get, and is there still room for the minimum free movement area at every workstation?',
         answer='About 4.99 m² per workstation (34.914 / 7). The combinations take 7 × 1.42 × 1.90 ≈ 18.9 m². Adding the free movement area of at least 1.5 m² that each workstation should have (7 × 1.5 = 10.5 m²) gives ≈29.4 m², which fits into 34.91 m² with ≈5.5 m² (≈0.8 m² per person) left for circulation and the door. So the room works, but tightly. The model does not record the desktop size inside the combination, so the recommended desktop of at least 120 × 80 cm (for predominantly screen work with few documents; at least 200 × 80 cm for specialist employees) can only be assumed from the 1.42 × 1.90 m footprint of these PC workstations.',
         evidence=['Space 28 "Working Space", EG: 34.914 m², bbox 9.38 × 4.26 m.', '7 × "Schreibtisch-Kombination-02 mit PC:Typ1", geometry ≈1.42 × 1.90 × 1.05 m each (one straddles the boundary with Lobby 29); no size properties on the type.'],
         hidden_knowledge='Free movement area of at least 1.5 m² per workstation (should); desktop should be ≥ 120 × 80 cm for predominantly screen work (≥ 200 × 80 cm for specialists).',
         basis=[C['move_area'], C['desk_area']],
         rubric=['≈4.99 m² per workstation', '7 × (2.70 + 1.5) ≈ 29.4 m² ≤ 34.91 m²', 'Notes desktop size is not in the model (optional)']),

    dict(project='fantasy_office_building_1', derived_from=[394], question_type='compliance',
         question='The two meeting rooms on OG1 (spaces 8 and 9) each contain one conference table set for eight. Are the rooms large enough for eight seats, and how many seats would their area properly support?',
         answer='No. A conference area needs about 2.5 m² per seat, not counting subsidiary areas, so 8 seats need ≈20.0 m². Each room has 16.34 m², ≈2.04 m² per seat and ≈3.7 m² short. At 2.5 m² per seat 16.34 m² supports about 6 seats (16.34 / 2.5 ≈ 6.5). The model also has no pantry or store next to them, although such subsidiary rooms take about one third of the conference area again (≈5.4 m² per room).',
         evidence=['Spaces 8 and 9 "Meeting Room", OG1: 16.338 m² each (bbox 3.58 × 4.57 m).', 'One "Tisch-Stuhl-Kombination-08 Konferenz:2400 x 1000 x 750 - 8 Stühle" in each.', 'No pantry or store space on OG1 (only working spaces 10, 13 and WCs 11, 12).'],
         hidden_knowledge='Conference rooms ≈2.5 m² per seat; subsidiary rooms ≈1/3 of the conference area.',
         basis=[C['conf_seat'], C['conf_sub']],
         rubric=['8 × 2.5 = 20 m² vs 16.34 m²', '≈2.04 m² per seat → undersized', '≈6 seats supportable', 'Missing subsidiary rooms (optional)']),

    dict(project='fantasy_office_building_1', derived_from=[394], question_type='intent',
         question='Meeting rooms 8 and 9 sit at the two ends of Working Space 10 on OG1. Trace how a visitor arriving at the main entrance reaches them. Why are they placed there, and what does that placement still fail to provide?',
         answer='No door connects either meeting room to Working Space 10. Each meeting-room door (0.885 m) opens south onto an OG1 gallery slab in the wing (x ≈ 6.1–9.9 m for room 8, mirrored for room 9). The straight stair rising from the double-height entrance lobby (Lobby 1 / Lobby 24, with the 2.34 × 4.74 m glazed façade doors) lands on that gallery at y ≈ 2.1 m. A visitor therefore goes lobby → stair → gallery → meeting room without passing through any workspace. This follows Neufert\'s rule that conference areas should be directly accessible from the entrance area. What it lacks is step-free access, which a building designed to accessibility principles must provide to all its levels (by lift or ramp): the building has no lift, so a wheelchair user cannot reach the meeting rooms at all.',
         evidence=['Meeting Room 8: x 6.36–9.94, y 5.82–10.38 (OG1); door "Drehflügel 1-flg 88.5 x 2.26" at y 5.61–5.83. Room 9 mirrored at x −11.96…−8.38.',
                   'OG1 slab x 6.11–9.89, y 0.56–10.63; stair Ortbetontreppe 484754 in Lobby 1 rises from y ≈ −3.4 (EG) to y ≈ 2.1 (OG1); mirrored stair 527118 in Lobby 24.',
                   'Working Space 10: x −7.64…5.62; OG1 doors only to WCs and the two meeting rooms.', 'No IfcTransportElement and no lift space.'],
         hidden_knowledge='Conference areas should be directly accessible from the entrance; in buildings designed for accessibility all levels must be reachable without steps (lift or ramp).',
         basis=[C['conf_access'], C['bf_levels']],
         rubric=['Route: lobby → stair → gallery → meeting room, not through Working Space 10', 'Links it to direct access from the entrance', 'Notes the missing lift / step-free access']),

    dict(project='fantasy_office_building_1', derived_from=[395], question_type='diagnosis',
         question='The building has 24 WC rooms, each a single small room. Looking at where their doors open and how they are labelled, what is wrong with this sanitary layout under the workplace toilet rules (Workplace Regulations) that apply to workplaces generally?',
         answer='Two things. (1) 18 of the 24 WC rooms (EG 7, 30; OG1 11, 12; OG2 15, 16, 18, 20, 21, 23; OG3 33–36, 38, 39; OG4 42, 43) open directly into a working space. A single-toilet room may do without an anteroom only if it has no direct access to a work room, so these need a lobby. Only the six EG WCs 2–4 and 25–27 open onto the entrance lobbies. (2) None of the rooms is assigned to women or men; only WCs 2 and 25 contain a urinal. With more than five employees, separate toilets for women and men are required. The positive side: every storey has its own WCs, so no workstation is more than one storey (and well under 100 m) away from a toilet. These rules appear in Neufert\'s Industry and trade chapter as workplace regulations; they are applied here because the offices are workplaces.',
         evidence=['Doors "Drehflügel 1-flg - Stahlzarge:88.5 x 2.26" bounding WC + Working Space: EG 2, OG1 2, OG2 6, OG3 6, OG4 2; bounding WC + Lobby: 6 (EG).',
                   'Spaces named only "WC" (2.626–4.871 m²); urinals ("Urinal 02") in WC 2 and 25 only; WC + washbasin per room on EG/OG1, no sanitary terminals on OG2–OG4.',
                   '30 desk combinations modelled (EG 14, OG1 16).'],
         hidden_knowledge='Workplace regulations (Industry chapter): toilets need a washbasin lobby unless a single toilet has no direct access to a work room; > 5 employees → separate women/men toilets; toilets ≤ 100 m or at most one storey (without escalator) from each workstation.',
         basis=[C['wc_lobby'], C['wc_gender'], C['wc_distance']],
         rubric=['Identifies the 18 WCs opening into working spaces', 'Applies the anteroom/lobby requirement', 'Flags missing gender separation', 'Notes WCs on every storey (optional)']),

    dict(project='fantasy_office_building_1', derived_from=[395], question_type='derivation',
         question='OG1 has 16 modelled workstations (8 each in Working Spaces 10 and 13) and two WC rooms of 2.63 m² each. Is that sanitary provision adequate by number of toilets and by floor area? Explain why the two checks disagree.',
         answer='By number, more than adequate: one toilet unit per 50–80 workstations means 16 workstations need one, and there are two. By area, inadequate: 0.6–0.8 m² per workstation gives 16 × 0.6–0.8 = 9.6–12.8 m², while the two WCs total 5.25 m² (≈0.33 m² per workstation). The likely reason the two checks disagree is that the area figure fits proper toilet facilities as the workplace regulations describe them (a washbasin lobby plus separate WC rooms, separated by sex above five employees), not bare cells. OG1 has only two 2.02 × 1.30 m single cells, each with WC and basin, opening straight into the working spaces. Several small cells score well on unit count but provide too little floor area.',
         evidence=['OG1: Working Space 10 and 13 (53.52 m², 8 desk combinations each).', 'WC 11 and 12: 2.626 m² each, bbox 2.02 × 1.30 m; each with "WC 01" and "Waschbecken 05" (900 mm); doors to Working Space 10/13.'],
         hidden_knowledge='Offices: one toilet unit per 50–80 workstations; ~0.6–0.8 m² of toilet area per workstation; workplace toilets consist of a washbasin lobby and a separate WC room.',
         basis=[C['wc_ratio'], C['wc_lobby']],
         rubric=['Count: 2 ≥ 1 needed → adequate', 'Area: 9.6–12.8 m² needed vs 5.25 m² → short', 'Explains the discrepancy (no lobby/separated facilities)']),

    dict(project='fantasy_office_building_1', derived_from=[394], pairing='supplement', question_type='compliance',
         question='This five-storey office building is entered through glazed lobby doors and its meeting rooms are on OG1. Can a visitor in a wheelchair reach the meeting rooms, and what does standard design guidance say about accessibility of office buildings in this respect?',
         answer='No. Under the building-code provision Neufert quotes, publicly accessible buildings must, in their parts serving the public, be usable by disabled people without outside help, and offices and administration buildings are named among them; separately, all levels of a building designed to accessibility principles must be reachable without steps, by lift or ramp. Meeting rooms receiving visitors are such public-serving parts. The model has no lift (no IfcTransportElement and no lift shaft space) and no ramp. Every level from OG1 to OG4 is reached only by stairs (24-riser flights and helical stairs). The internal doors are also only 0.885 m wide overall, below a 0.90 m clear width. The meeting rooms, and all upper floors, are therefore not wheelchair-accessible, so the building does not meet that accessibility standard for its visitor areas.',
         evidence=['No IfcTransportElement; no space or element named lift/Aufzug; 14 IfcStair as the only vertical circulation.', 'Internal doors "Drehflügel 1-flg - Stahlzarge:88.5 x 2.26": OverallWidth 0.885 m.', 'Meeting rooms 8, 9 on OG1 (+4.80 m).'],
         hidden_knowledge='Public-serving parts of publicly accessible buildings (offices named) must be usable by disabled people without help; accessible buildings have all levels step-free via lift or ramp; doors in accessible public buildings ≥ 0.90 m clear.',
         basis=[C['bf_public'], C['bf_levels'], C['bf_door']],
         rubric=['Verdict: not accessible', 'No lift or ramp in the model', 'Cites the public-parts accessibility rule for offices and the step-free/lift requirement', 'Door 0.885 m < 0.90 m (optional)']),
]

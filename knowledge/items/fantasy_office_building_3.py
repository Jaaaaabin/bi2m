# fantasy_office_building_3 (TUM student model, Revit export). Storeys EG 0.00 / OG1 3.70 / OK OG2 7.40 /
# OK OG3 11.10 / OK OG4 14.80 / OK OG5 18.50 m (OK OG5 = roof level: only roof, slabs, beams).
# Space areas from PSet_Room.Area; space geometry height 2.75 m. Workstations counted from desk furniture
# per space: EG 15, OG1 15, OG2 21, OG3 21, OG4 7 (79 in total).
# Uses C[...] keys defined in fantasy_office_building_1.py where available; redefined here so the file is self-contained.

C['o3_high_rise'] = cite('page_0256', 'High-rise buildings are those intended for long-term human occupation whose upper-most floor on one side of the building is more than 22 m above ground level.')
C['o3_ceiling'] = cite('page_0255', 'Ceiling height 2.75 m according to Vst regulation (enables the later installation of raised floor and deeper suspended ceilings).')
C['o3_ceiling_low'] = cite('page_0255', 'Corridors and sanitary facilities are permitted to be 2.30 m high')
C['o3_group'] = cite('page_0251', 'The experience with the open-plan layout led to the development of group offices with approx. 4–16 workstations; each office is used by a single team or department.')
C['o3_open'] = cite('page_0251', 'Large-scale office landscapes with 100 or more workstations are made possible by artificial lighting and ventilation')
C['o3_single'] = cite('page_0245', 'Single-room offices are suitable for independent or concentrated work, as a single-person room or for a few people in very small groups who need to exchange information constantly.')
C['o3_mixed'] = cite('page_0244', 'the requirement for a mixed provision of single and group rooms')
C['o3_daylight'] = cite('page_0253', 'Daylight can mostly be exploited into a room depth of about 7.00 m.')
C['o3_move'] = cite('page_0248', 'There should be a free movement area of at least 1.5 m² at the workstation.')
C['o3_wc_ratio'] = cite('page_0250', 'A good ratio is one toilet unit per 50–80 workstations. Space requirement ~0.6–0.8 m² per workstation.')
C['o3_wc_lobby'] = cite('page_0282', 'Toilet facilities consist of a lobby with washbasins (at least one washbasin per five WCs) and a completely separate room with at least one WC')
C['o3_wc_gender'] = cite('page_0282', 'If there are more than five employees, separate toilets must be provided for women and men')
C['o3_room_380'] = cite('page_0252', 'Room widths of 3.80 m (~18 m^2 usable area) enable:')
C['o3_two_ws'] = cite('page_0252', 'two computer workstations with a depth of 0.90 m, as recommended by accident insurance companies')
C['o3_conf_seat'] = cite('page_0250', 'A conference area requires about 2.5 m^2 per seat (without subsidiary areas).')
C['o3_tea'] = cite('page_0250', 'For every approx. 50–100 workplaces, one ~10 m² kitchen.')
C['o3_bf_entrance'] = cite('page_0037', 'must be accessible through an entrance with a clear opening width of at least 0.90 m without steps.')

ITEMS += [
    dict(project='fantasy_office_building_3', derived_from=[444], question_type='diagnosis',
         question='The storeys are 3.70 m apart. Two kinds of stair climb them: the stairs in the two staircase cores (one per storey) and two steel stairs from EG to OG1 in the central hall. Judge both kinds against the standard stair design rules. Which pass, and what is wrong with the other kind?',
         answer='The core stairs pass. Each has 21 risers of 17.6 cm (21 × 0.176 ≈ 3.70 m), split into runs of 11 + 10 with a ≈1.23 m deep landing, and 1.20 m wide flights. Stride 2r + t is 2 × 17.6 + 27.0 = 62.2 cm (west, precast) and 2 × 17.6 + 28.3 = 63.5 cm (east, in-situ), both within 59–65 cm. 11 and 10 steps per run are ≤ 18, the landing meets the requirement for storeys ≥ 2.75 m, the width exceeds the 1.00 m minimum usable width, and the ratio is close to 17/28 (the values German standards set for legally essential stairs, which Neufert gives for residential buildings and which are applied here by analogy). The steel stairs fail: each climbs 3.70 m in a single run of 19 risers (≈19.5 cm) with 20 cm treads and no landing. That is more than 18 steps per run, no landing at ≥ 2.75 m, and a stride of 2 × 19.5 + 20 = 59 cm at the very bottom of the range with an unusually short 20 cm tread. They can only be secondary feature stairs; the cores serve as the essential stairs.',
         evidence=['Core stairs "Betonfertigteil-Treppe" (west, 4×) and "Ortbetontreppe" (east, 4×), EG→OK OG4: NumberOfRiser 21, RiserHeight 0.1762 m, TreadLength 0.27 / 0.2826 m; IfcStairFlight Run 1 (11 risers) + Run 2 (10 risers), flight width 1.20 m; IfcSlab "Landing 1" ≈2.59 × 1.23 m / 2.64 × 1.24 m.',
                   'Steel stairs "Zusammengebaute Treppe:Stahl - Stufen Stahl" 695194 and 695335 (EG): NumberOfRiser 19, RiserHeight 0.195 m, TreadLength 0.20 m, one "Run 1", no landing; located between Loby (y ≤ 0.45) and Open-plan office 1 (y ≥ 7.2) in a zone without IfcSpace.'],
         hidden_knowledge='2r + t = 59–65 cm; ≤ 18 steps per run; landing at storey height ≥ 2.75 m; legally essential stairs min. usable width 1.00 m, 17/28 (German standards, residential context, applied by analogy).',
         basis=[C['stride'], C['run_len'], C['landing'], C['essential']],
         rubric=['Core stairs: 2r + t 62.2 / 63.5 cm, 11 + 10 steps, landing → pass', 'Steel stairs: 19 > 18 steps, no landing → fail', 'Steel stairs 2r + t = 59 cm at the limit with a 20 cm tread', 'Width 1.20 m ≥ 1.00 m (optional)']),

    dict(project='fantasy_office_building_3', derived_from=[444], question_type='derivation',
         question='With levels at 0.00, 3.70, 7.40, 11.10, 14.80 and 18.50 m, and rooms modelled 2.75 m high, does the office ceiling height match the standard figure for office buildings, how much of each storey is left for slab and services, and how many further office storeys could be added before the building becomes a high-rise?',
         answer='It matches exactly: Neufert gives 2.75 m as the office ceiling height according to the Vst regulation (to allow later raised floors and deeper suspended ceilings), leaving 3.70 − 2.75 = 0.95 m per storey for slab, floor build-up and ceiling void. Corridors and toilets, also modelled at 2.75 m, are permitted at 2.30 m, which would free ≈0.45 m for service runs. On the high-rise question, OK OG5 (+18.50 m) holds only roof slabs and beams, so the uppermost occupied floor is OK OG4 at 14.80 m. One more storey would put the top floor at 18.50 m (< 22 m); a second would put it at 22.20 m (> 22 m), making the building a high-rise. So exactly one more storey is possible, assuming EG ±0.00 is at ground level.',
         evidence=['IfcBuildingStorey: EG 0.0, OG1 3.7, OK OG2 7.4, OK OG3 11.1, OK OG4 14.8, OK OG5 18.5 m; OK OG5 contains only 2 IfcRoof, 2 IfcSlab, 8 IfcBeam.',
                   'All 87 IfcSpace have a geometry height of 2.75 m (no height property), including corridors 018/019… and toilets 010/020….'],
         hidden_knowledge='Office ceiling height 2.75 m according to Vst regulation (corridors/sanitary 2.30 m permitted); high-rise when the top floor is > 22 m above ground.',
         basis=[C['o3_ceiling'], C['o3_ceiling_low'], C['o3_high_rise']],
         rubric=['2.75 m = the office ceiling height Neufert gives (Vst regulation)', '0.95 m left per storey (≈0.45 m more possible in corridors/WCs)', 'Top occupied floor 14.80 m; OK OG5 is the roof', 'One more storey (18.50) OK, second (22.20) → high-rise']),

    dict(project='fantasy_office_building_3', derived_from=[447], question_type='intent',
         question='The building has three office types: six "Open-plan offices" (≈55–57 m², 6–8 desks each), five "Small office spaces" (27.28 m², 3 desks) and twenty "Individual offices" (≈11 m², 1 desk). How do these map onto the standard office typology, and what organisational idea does the mix express?',
         answer='None of them is an open-plan office in Neufert\'s sense, which means office landscapes with 100 or more workstations. The "open-plan offices" hold 8 (Open-plan office 1) or 6 (Open-plan office 2) workstations, so they are group offices of about 4–16 workstations for one team. The individual offices (1 person) and small offices (3 people) are single-room offices, suited to concentrated work by one person or a very small group. Of the 79 modelled workstations, 44 are in group rooms (4 × 8 + 2 × 6), 15 in small offices and 20 in individual rooms. Each floor also has two meeting rooms and a kitchen. The mix expresses the mixed provision of single and group rooms Neufert recommends, close to a combi-office idea: team rooms for shared work next to cells for concentrated work.',
         evidence=['Open-plan office 1 (008, 108, 208, 308): 54.57 m², 8 × "Schreibtisch-Kombination-01"; Open-plan office 2 (213, 313): 56.60/56.67 m², 6 each.',
                   'Small office space (009–409): 27.28 m², 3 × "Schreibtisch-Kombination-02 mit PC"; Individual office 1–4 on EG–OK OG4: 10.96–11.26 m², 1 each.',
                   'Per floor: Meeting room 1 and 2, Kitchen (27.28 m²).'],
         hidden_knowledge='Open-plan ≥ 100 workstations; group offices ≈4–16; single-room offices for concentrated work; mixed provision of single and group rooms.',
         basis=[C['o3_open'], C['o3_group'], C['o3_single'], C['o3_mixed']],
         rubric=['"Open-plan" rooms are group offices (6–8 ≪ 100)', 'Small/individual offices = single-room offices', 'Counts 79 workstations or the 44/15/20 split', 'Interprets the mix as single + group (combi-like) provision']),

    dict(project='fantasy_office_building_3', derived_from=[449], question_type='derivation',
         question='Open-plan office 1 on the ground floor (54.57 m²) contains eight "Schreibtisch-Kombination-01" desk units of about 1.42 × 1.75 m each. How much area does each workstation get, how much free floor remains per person, and can daylight reach every desk?',
         answer='Each workstation gets 54.57 / 8 ≈ 6.8 m². The desk units take 8 × 1.42 × 1.75 ≈ 19.9 m², leaving ≈34.7 m², about 4.3 m² per person. That is well above the free movement area of at least 1.5 m² that each workstation should have, although part of it is circulation. The room is only ≈3.40 m deep (16.05 × 3.40 m), far less than the ≈7 m into which daylight can usefully reach, so every desk lies in the daylit zone. It is glazed with eight 2.0 m-wide floor-to-ceiling elements along its long side.',
         evidence=['Space 008 "Open-plan office 1", EG: 54.57 m² (PSet_Room.Area), bbox 16.05 × 3.40 m.', '8 × "Schreibtisch-Kombination-01:Typ1", geometry ≈1.42 × 1.75 × 0.89 m.', '8 windows "FE TÜR 2 tlg - Fix im Rahmen:2000 x 3000" (2.0 × 3.2 m) bounding 008.'],
         hidden_knowledge='Free movement area of at least 1.5 m² per workstation (should); daylight reaches ≈7 m room depth.',
         basis=[C['o3_move'], C['o3_daylight']],
         rubric=['≈6.8 m² per workstation', '≈4.3 m² free per person ≥ 1.5 m²', 'Depth 3.40 m ≤ 7 m → all desks daylit']),

    dict(project='fantasy_office_building_3', derived_from=[450], question_type='derivation',
         question='On OK OG2 the restrooms are "Toilet men" (8.34 m²) and "Toilet women" (8.77 m²). Count the workstations on that floor and check the restrooms against the usual office design guidance by floor area and by number of toilets, and against the workplace toilet rules. Is there anything the model does not let you verify?',
         answer='OK OG2 has 21 workstations: 8 in Open-plan office 1, 6 in Open-plan office 2, 3 in the small office and 1 in each of 4 individual offices. Area: 0.6–0.8 m² per workstation gives 12.6–16.8 m², and the restrooms total 17.11 m², just above the upper value, so adequate. Number: one toilet unit per 50–80 workstations means 21 people need one; there are 6 WCs (3 + 3) and 5 urinals, so the floor is generously equipped. Under the workplace regulations Neufert gives in the Industry and trade chapter (applied here to the office workplaces), toilets must be separate for women and men with more than five employees, which they are, and toilet facilities consist of a washbasin lobby (at least one basin per five WCs; each room has a double washbasin) and a completely separate WC room. Not verifiable: each restroom is a single space with one corridor door and no internal doors, so the separation between the washbasin lobby and the WC rooms is not modelled.',
         evidence=['OK OG2 desks: 208 Open-plan office 1 (8), 213 Open-plan office 2 (6), 209 Small office (3), 214–217 Individual offices (1 each).',
                   '220 Toilet men 8.34 m²: 3 × "WC 02", 5 × "Urinal 02", 1 × "Waschtisch-Kombi-Doppel WB"; 210 Toilet women 8.77 m²: 3 × "WC 02", 1 × double washbasin.',
                   'One door per toilet (to Corridor west/east); no IfcDoor inside either toilet.'],
         hidden_knowledge='Offices: ~0.6–0.8 m² toilet area per workstation, one toilet unit per 50–80 workstations; workplace regulations (Industry chapter): separate sexes above five employees, washbasin lobby separated from WCs.',
         basis=[C['o3_wc_ratio'], C['o3_wc_gender'], C['o3_wc_lobby']],
         rubric=['Counts 21 workstations', '12.6–16.8 m² vs 17.11 m² → adequate', '6 WCs ≫ 1 per 50–80 → generous', 'Notes lobby/cubicle separation is not modelled']),

    dict(project='fantasy_office_building_3', derived_from=[451], question_type='intent',
         question='Each floor has four individual offices of about 11 m² (44.34 m² per floor), each about 2.7 m wide and 4.0–4.1 m deep with one desk. Could two people share one of these rooms, and what kind of work are they designed for?',
         answer='Not comfortably. For the 1.35 m module, Neufert gives a room width of 3.80 m (about 18 m² usable) as enabling, among other layouts, two computer workstations of 0.90 m depth (the depth recommended by accident insurance companies). These rooms are only ≈2.69–2.76 m wide and ≈11 m², about a metre narrower and 7 m² smaller, so they are single-person rooms. That matches their single "Schreibtisch-Kombination-02 mit PC" each. Single-room offices of this kind are meant for independent, concentrated work, the counterpart to the shared open rooms on the same floors. Their width is close to two 1.35 m grid modules (2.70 m).',
         evidence=['Individual office 1–4 per floor: 10.96, 11.08, 11.26, 11.04 m² (sum 44.34 m²); bbox ≈2.69–2.76 × 3.99–4.12 m.', 'One "Schreibtisch-Kombination-02 mit PC" (≈1.42 × 1.90 m) in each of the 20 individual offices.', 'Each has one 2.0 × 3.2 m glazing element and a 1.0 m door to the corridor.'],
         hidden_knowledge='In the 1.35 m module, a room width of 3.80 m (~18 m²) enables two computer workstations of 0.90 m depth (accident-insurer recommendation); single-room offices are for concentrated work.',
         basis=[C['o3_room_380'], C['o3_two_ws'], C['o3_single']],
         rubric=['Compares ≈2.7 m / ≈11 m² with 3.80 m / ≈18 m²', 'Concludes single-person rooms', 'Links to concentrated / independent work']),

    dict(project='fantasy_office_building_3', derived_from=[447], pairing='supplement', question_type='compliance',
         question='Every floor has two meeting rooms of about 15.2 m², each with a conference table set for six, and a 27.28 m² kitchen. Are the meeting rooms sized correctly for their seats, and is the kitchen provision in line with the usual design guidance for 79 workstations?',
         answer='The meeting rooms just fit. About 2.5 m² per seat gives 6 × 2.5 = 15.0 m², and the rooms have 15.16 m² (EG–OK OG3) or 15.07 m² (OK OG4), a margin of only 0.07–0.16 m². The kitchens are far more generous than needed: Neufert gives one tea kitchen of about 10 m² per 50–100 workplaces, so 79 workstations need one 10 m² kitchen, but the building has five of 27.28 m² each (≈136 m²). Each kitchen has a kitchen unit and two table-and-bench sets, so they work as break or lunch rooms rather than tea kitchens.',
         evidence=['Meeting room 1/2: 15.16 m² (EG–OK OG3), 15.07 m² (OK OG4); each one "Tisch-Stuhl-Kombination-08 Konferenz:2000 x 1000 x 750 - 6 Stühle".',
                   'Kitchen 005, 105, 205, 305, 405: 27.28 m² each; "Küchenzeile-02 Kombination" + 2 × "Tisch-Bank-Kombination-07".', '79 desk workstations in total.'],
         hidden_knowledge='Conference rooms ≈2.5 m² per seat; one ~10 m² tea kitchen per 50–100 workplaces.',
         basis=[C['o3_conf_seat'], C['o3_tea']],
         rubric=['6 × 2.5 = 15.0 m² ≤ 15.07–15.16 m² → just complies', '1 kitchen needed vs 5 × 27.28 m² provided', 'Interprets kitchens as break rooms (optional)']),

    dict(project='fantasy_office_building_3', pairing='supplement', derived_from=[], question_type='diagnosis',
         question='The lobby\'s only external door is a revolving door ("TU Karussell"). The two corridors each end in an external door of type "Fluchttüre Endausgang: EN 179 - DL - 900 x 2175". Which of these can serve as emergency exits and as the accessible entrance, and why?',
         answer='The revolving door can be neither. Revolving and sliding doors are not permitted at emergency exits because they can jam in an emergency. A revolving door also has no fixed clear opening of at least 0.90 m for the step-free entrance that publicly accessible buildings (offices are named) must have. The two corridor doors are hinged single-swing doors with a nominal 900 mm clear opening (1.05 m overall) and EN 179 emergency-exit hardware, so they are the building\'s real exits and are wide enough as accessible entrances. The design works only if visitors who cannot use the revolving door are directed to a corridor door; the lobby itself has no side swing door.',
         evidence=['"TU Karussell:ML - 2010 x 2250": OperationType REVOLVING, OverallWidth 2.475 m, bounds only Loby (013), IsExternal true.',
                   '"TU DF 1 - Fluchttüre Endausgang:EN 179 - DL - 900 x 2175": SINGLE_SWING, OverallWidth 1.05 m, OverallHeight 2.43 m; external at Corridor west (019) and Corridor east (018) on EG.',
                   'No other external door on Loby.'],
         hidden_knowledge='No sliding or revolving doors at emergency exits; publicly accessible buildings (offices named) need a step-free entrance of ≥ 0.90 m clear opening width; door size (structural opening) ≠ clear pass-through dimension.',
         basis=[C['no_sliding_exit'], C['o3_bf_entrance'], C['door_frame']],
         rubric=['Revolving door not permissible as an emergency exit', 'Corridor EN 179 swing doors serve as exits', '900 mm nominal clear ≥ 0.90 m for accessible entry', 'Notes the lobby lacks a swing door']),
]

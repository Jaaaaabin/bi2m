# fantasy_hotel_1 (TUM student model, Revit 2024 export; usage "motel" per project data).
# IfcSpaces carry no area/height properties: areas below are footprints computed from the space
# geometry (all spaces are rectangles, so footprint = bounding-box product) and are marked "≈".

C['motel_size'] = cite('page_0198', 'Room sizes 4 × 4 m – 5 × 5 m, with bathroom and sometimes kitchenette')
C['motel_storey'] = cite('page_0198', 'In contrast to city hotels, motels are mostly single-storey, widely spread facilities')
C['motel_parking'] = cite('page_0198', 'The access road normally leads to the registration (short-term parking), then to a car park or carport as near to the room as possible.')
C['dehoga_1'] = cite('page_0184', '1 Star (Tourist): single room 8 m², double room 12 m² (minimum area for 75% of the hotel rooms, without bathroom), bed, wardrobe, seat, washbasin in the room')
C['dehoga_2'] = cite('page_0184', '2 Stars (Standard): as before, but single room 12 m², double room 16 m² (minimum area for 75% of the hotel rooms, including bathroom and corridor), bathroom in room (for 70% of hotel rooms)')
C['dehoga_3'] = cite('page_0184', '3 Stars (Comfort): as before, but single room 14 m², double room 18 m² (minimum area, see above), bathroom in room (for all rooms in the hotel)')
C['dehoga_4'] = cite('page_0184', '4 Stars (First Class): as before, but single room 16 m², double room 22 m² (minimum area, see above)')
C['dehoga_5'] = cite('page_0184', '5 Stars (Luxury): as before, but single room 18 m², double room 26 m²')
C['escape_window'] = cite('page_0109', 'If the window serves as an escape route, it must have a clear opening of at least 0.9 × 1.2 m and a sill height of max. 1.2 m above floor level.')
C['parking_90'] = cite('page_0402', '90° parking, access 5.50 m wide, parking space 2.50 m wide')

ITEMS += [
    dict(project='fantasy_hotel_1', derived_from=[334], question_type='compliance',
         question='The motel\'s guest rooms are the 18 spaces furnished with beds, nine per floor. Measured against the usual design guidance for motel rooms, which of them have a suitable size, and how does the building as a whole differ from the typical motel layout?',
         answer='Only the 8 large rooms ("MASTER BEDROOM") fit. Neufert gives motel rooms of 4 × 4 m to 5 × 5 m, i.e. about 16–25 m², with a bathroom. The large rooms are ≈18.2–24.8 m² (ground floor 106/107/110/112: ≈22.4–24.8 m²; first floor 118/120/121/123: ≈18.2–20.9 m²), within the range, although they are long and narrow (≈2.7–3.7 × 6.0–7.7 m) rather than square. The 10 small rooms ("LIVING ROOM"/"Room Name", one double bed each) are only ≈7.6–11.1 m², well below 16 m². The building also differs in section: it stacks rooms on two floors (+0.00 and +4.90 m) where motels are mostly single-storey, widely spread facilities. (The original answer counts 20 guest rooms, 11 on the ground floor; the model has 18 bed-furnished spaces, 9 per floor.)',
         evidence=['Bed-furnished spaces, ground floor: 100, 101, 103, 104, 105 (≈10.8–11.1 m²) and 106, 107, 110, 112 (≈24.8, 22.4, 23.1, 24.8 m²); first floor: 114, 115, 124, 125, 126 (≈7.6–10.4 m²) and 118, 120, 121, 123 (≈18.6, 20.9, 20.3, 18.2 m²); footprints from space geometry (no area property).',
                   'Large rooms ≈3.73 × 6.0–6.66 m (ground) and ≈2.73 × 6.66–7.65 m (first floor), geometry bounding boxes.',
                   'Storeys GROUND FLOOR 0.00 m, FIRST FLOOR +4.90 m (L3 +9.80 roof, Mumti +11.80).',
                   'Original ifc-bench answer #334: 20 guest rooms (11 ground, 9 first).'],
         hidden_knowledge='Motel rooms are about 4 × 4 m to 5 × 5 m with a bathroom; motels are mostly single-storey.',
         basis=[C['motel_size'], C['motel_storey']],
         rubric=['Converts 4×4–5×5 m into ≈16–25 m²', 'Large rooms (≈18–25 m²) fit, small rooms (≈7.6–11.1 m²) do not', 'Notes two storeys vs the typically single-storey motel', 'Counts 18 bed-furnished rooms (or flags the 20 vs 18 discrepancy)']),

    dict(project='fantasy_hotel_1', derived_from=[335], question_type='derivation',
         question='The ground and first floors are 4.90 m apart. How many risers and what tread would a comfortable stair need for this height, how would it have to be split, and how much longer would it be than the stairs actually built?',
         answer='Aiming at a riser of about 17 cm gives 4.90 / 0.17 ≈ 28.8, so 29 risers of ≈16.9 cm. With 2r + t ≈ 63 cm the tread is about 63 − 33.8 ≈ 29.2 cm, close to the ideal 17/29. Since a run may have at most 18 steps and a storey height of ≥ 2.75 m needs a landing anyway, the stair must be split into two runs (e.g. 15 + 14 risers) with a landing. Its 28 treads give a going of about 28 × 0.292 ≈ 8.2 m plus the landing. The built stairs pack the height into 18 risers of 27.2 cm with 17 treads of 27.5 cm, a going of 17 × 0.275 ≈ 4.7 m, so a comfortable stair needs roughly 3.5 m more going plus a landing. The levels L3 (+9.80) and Mumti (+11.80) are the roof and a 2.0 m stair-head room, not guest floors.',
         evidence=['Storeys: GROUND FLOOR 0.00, FIRST FLOOR +4.90, L3 +9.80, Mumti +11.80 m.',
                   'Four IfcStair "Assembled Stair:M_Stair-Metal-Plate Stringer": Pset_StairCommon NumberOfRiser 18, NumberOfTreads 17, RiserHeight 0.2722 m, TreadLength 0.275 m; two GF→FF, two FF→L3.'],
         hidden_knowledge='Ideal 17/29; stride 2r + t = 59–65 cm; ≤ 18 steps per run; landing at storey height ≥ 2.75 m.',
         basis=[C['ideal_ratio'], C['stride'], C['run_len'], C['landing']],
         rubric=['≈29 risers of ≈16.9 cm', 'Tread ≈29 cm from 2r + t', 'Two runs with a landing (≤ 18 steps, ≥ 2.75 m)', 'Going ≈8.2 m vs ≈4.7 m built']),

    dict(project='fantasy_hotel_1', derived_from=[365], question_type='diagnosis',
         question='The four stairs have no width property. Measure what you can from the model and judge whether they would pass as the building\'s legally essential stairs. What is acceptable and what is not?',
         answer='Width is acceptable: each stair fits in a ≈2.48 × 2.51 m footprint and its flights are ≈1.1 m wide between outer and inner stringers, above the 1.00 m minimum usable width that German standards set for legally essential stairs in residential buildings (Neufert sizes stairs in public buildings by evacuation time, so for a motel this is a benchmark applied by analogy). Steps per run are acceptable: 18 risers is exactly the maximum of 18 for one run. Not acceptable: (1) the risers are 27.2 cm with 27.5 cm treads, far steeper than 17/28, almost a 45° ladder-like stair; (2) the stride 2r + t = 2 × 27.2 + 27.5 = 81.9 cm is far above the 59–65 cm range; (3) at a 4.90 m storey height (≥ 2.75 m) a landing is required, but each stair is a single "Run 1" with no landing element. The stairs fit a 4.90 m storey into a 2.5 m square only by making each step 27 cm high.',
         evidence=['IfcStair 1644242/1646359 (GROUND FLOOR) and 1751844/1752399 (FIRST FLOOR): 18 risers × 0.2722 m, tread 0.275 m, no width in any pset.',
                   'Decomposition: one IfcStairFlight "Run 1" (bbox ≈2.48 × 2.51 × 4.89 m), 8 stringers, handrails; no landing slab.',
                   'Stringer 1 at y = 8.26 and Stringer 6 at y = 9.38 (stair 1644242) → flight width ≈1.1 m.'],
         hidden_knowledge='Legally essential stairs (German standards, residential; applied to the motel by analogy): min. 1.00 m usable width, 17/28; stride 59–65 cm; ≤ 18 steps per run; landing at ≥ 2.75 m storey height.',
         basis=[C['essential'], C['stair_public'], C['stride'], C['run_len'], C['landing']],
         rubric=['Derives a width of ≈1.1 m from geometry and accepts it against the 1.00 m residential benchmark', 'Computes 2r + t ≈ 82 cm and rejects it', 'Flags 27 cm risers vs 17/28', 'Flags the missing landing at 4.90 m']),

    dict(project='fantasy_hotel_1', derived_from=[338], question_type='compliance',
         question='The model uses three window sizes: 910 × 910 mm, 1524 × 610 mm and 600 × 900 mm. Could any of them serve as the escape window of a first-floor guest room? What do first-floor guests have to rely on instead?',
         answer='None of them. An escape window needs a clear opening of at least 0.9 × 1.2 m and a sill no higher than 1.2 m. The 910 × 910 mm window is too low (0.91 m < 1.2 m), and its clear opening is smaller still once the frame is deducted. The 1524 × 610 mm awning window is only 0.61 m high, below even 0.9 m. The 600 × 900 mm window is too narrow and too low; it exists only on the ground floor anyway. Turning the windows does not help, because each has one dimension below 0.9 m or both below 1.2 m. First-floor rooms therefore depend on the stairs: the floor needs two independent escape routes, and only the two internal stairs (18 × 27.2 cm risers) lead down.',
         evidence=['Windows: 51 × "Windows_Sgl_Plain:910x910mm" (0.91 × 0.91 m), 12 × "Window-Awning-Triple-Horizontal:60" x 24"" (1.524 × 0.61 m, first floor, sill ≈0.91 m), 10 × "M_Window-Fixed:600 x 900mm" (ground floor).',
                   'First-floor guest rooms 114, 115, 124–126 have 910 × 910 windows (sill ≈0.8–1.2 m); 118, 120, 121, 123 have the awning windows.',
                   'Two IfcStair GROUND FLOOR → FIRST FLOOR (1644242, 1646359).'],
         hidden_knowledge='Escape windows: clear opening ≥ 0.9 × 1.2 m, sill ≤ 1.2 m; two independent escape routes per floor.',
         basis=[C['escape_window'], C['hab_room']],
         rubric=['Cites 0.9 × 1.2 m clear opening', 'Rejects all three sizes with the failing dimension', 'Notes clear opening < overall size', 'First floor relies on the two stairs']),

    dict(project='fantasy_hotel_1', derived_from=[340], question_type='derivation',
         question='The 1.524 m-wide windows (12 in total) are the awning windows of the first-floor master bedrooms. Taking only these windows into account, do bedrooms 118, 120, 121 and 123 reach the window area needed for a habitable room, and what decides the outcome for the rooms that fall short?',
         answer='Each awning window is 1.524 × 0.61 ≈ 0.93 m². The rule is window area ≥ 1/8 of the floor area. 118 (≈18.6 m², needs ≈2.33 m²) and 123 (≈18.2 m², needs ≈2.27 m²) each have three windows ≈2.79 m², so they pass. 120 (≈20.9 m², needs ≈2.61 m²) and 121 (≈20.3 m², needs ≈2.54 m²) have only two, ≈1.86 m², so they fall short by ≈0.7 m². What decides it for them is their storefront curtain wall: ≈5.3 m (120) and ≈5.0 m (121) wide and 2.9 m high, which supplies far more than the missing area. The 1524 × 610 mm size is exactly 60 × 24 in, an imperial family size, not a metric choice.',
         evidence=['"Window-Awning-Triple-Horizontal:60" x 24"": 1.524 × 0.61 m; 3 in 118, 2 in 120, 2 in 121, 3 in 123, 1 in staircase 119, 1 at the unspaced second stair.',
                   'Footprints (space geometry): 118 ≈18.64, 120 ≈20.85, 121 ≈20.31, 123 ≈18.16 m².',
                   'IfcCurtainWall "M_Storefront" on FIRST FLOOR: ≈1.8 × 2.9 m (118, 123), ≈5.3 × 2.9 m (120), ≈5.0 × 2.9 m (121).'],
         hidden_knowledge='Window area of habitable rooms ≥ 1/8 of the floor area.',
         basis=[C['hab_room']],
         rubric=['0.93 m² per window', '118/123 pass (≈2.79 vs ≈2.3 m²)', '120/121 fail on awning windows alone (≈1.86 vs ≈2.6 m²)', 'Storefront glazing decides 120/121']),

    dict(project='fantasy_hotel_1', derived_from=[350], question_type='compliance',
         question='Room 112 is furnished with two double beds, a sofa, an oval dining table and storage furniture. Using the German hotel classification (DEHOGA), which category does it reach by floor area, and does the room\'s equipment support that category?',
         answer='By area, 4 stars: ≈24.8 m² (3.73 × 6.66 m) meets the 22 m² double-room minimum area for 4 stars but not the 26 m² for 5 stars (these minimums apply to 75 % of a hotel\'s rooms). The equipment does not support it. Room 112 has no bathroom (no sanitary terminal and no door to a sanitary room), but 3 stars and above require a bathroom in every room. It does not even have the washbasin in the room that 1 star requires. The generous furniture (two 1.35 × 1.88 m double beds, a 2.1 m sofa, a dining table) cannot make up for that: as modelled, the room is a large room with shared sanitary facilities, below the 1-star room standard.',
         evidence=['Space 112 "MASTER BEDROOM", GROUND FLOOR: ≈24.83 m² (geometry 3.73 × 6.66 m).',
                   'Furniture in 112: 2 × Bed-Box Double 53" × 74" (1.35 × 1.88 m), Furniture_Sofa_2 2100 mm, 3 × lateral file cabinet, storage cabinet 1200 × 550 × 2100, M_Table-Dining Oval 0915 × 1830.',
                   'Only door: Doors_IntAys_1 1210 × 2110 to the outside; no IfcFlowTerminal (WC, sink) in 112.'],
         hidden_knowledge='DEHOGA double-room minimum areas (for 75 % of rooms) 12/16/18/22/26 m² for 1–5 stars (1 star without bathroom); washbasin in room from 1 star, bathroom in room for 70 % (2 stars) or all rooms (3 stars+).',
         basis=[C['dehoga_1'], C['dehoga_3'], C['dehoga_4'], C['dehoga_5']],
         rubric=['24.8 m² ≥ 22 m² but < 26 m² → 4 stars by area', 'No bathroom → fails 3-star+', 'No washbasin → fails the 1-star room feature', 'Area uses geometry (no area property)']),

    dict(project='fantasy_hotel_1', derived_from=[352], question_type='compliance',
         question='The model has four sanitary spaces: BATHROOM 108 and 109 on the ground floor, BATH 116 and WASH BASIN 117 on the first floor. Considering which guest rooms can actually reach them from inside the room, what hotel category does the sanitary provision allow, and what would a motel normally offer instead?',
         answer='At most 1 star. Only two of the 18 guest rooms have an en-suite room: 108 opens off master bedroom 107 and 109 off master bedroom 110, which is 2/18 ≈ 11 %. 2 stars require a bathroom in 70 % of the rooms, and 3 stars in all rooms. On the first floor, 116 and 117 are communal: they are entered from outside through a 0.85 m door and serve no room directly. None of the four spaces has a shower or bath; they hold WCs, urinals and floor sinks. Motel rooms are normally planned with their own bathroom, so a motel layout would need about 18 en-suite bathrooms rather than 2 attached plus 2 shared rooms.',
         evidence=['108 BATHROOM (≈5.22 m²): WC, urinal, corner floor sink; door "300 x 2000mm" to 107. 109 BATHROOM (≈4.94 m²): WC, urinal, corner floor sink; door "300 x 2000mm" to 110.',
                   '117 WASH BASIN (≈3.24 m²): floor sink, urinal; external door "Vision_Lite 750 x 2000mm" (0.85 m overall). 116 BATH (≈4.59 m²): floor sink; reached only through 117.',
                   '18 bed-furnished guest rooms; no bath or shower terminal anywhere in the model.'],
         hidden_knowledge='DEHOGA: bathroom in room for 70 % of rooms (2 stars) and for all rooms (3 stars); motel rooms with bathroom.',
         basis=[C['dehoga_2'], C['dehoga_3'], C['motel_size']],
         rubric=['Only 2 of 18 rooms en-suite (≈11 %)', 'Fails the 70 % (2-star) threshold → ≤ 1 star', 'First-floor sanitary rooms are communal, entered from outside', 'Motel guidance expects a bathroom per room']),

    dict(project='fantasy_hotel_1', derived_from=[352], question_type='diagnosis',
         question='Bathrooms 108 and 109 are each entered from a master bedroom, and BATH 116 from WASH BASIN 117, through doors of type "M_Door-Interior-Single-1_Panel-Wood:300 x 2000mm". Could a guest actually use these doors, and what does the type name tell you?',
         answer='No. The doors are 0.35 m wide overall (nominal 300 mm), so the clear opening is under 0.35 m. Neufert gives about 70 cm clear for bath/WC doors in dwellings, and 0.90 m clear for doors in accessible public buildings. These doors are about half the conventional size and less than 40 % of the 0.90 m accessible width. Nobody can walk through a 30 cm leaf. "300 x 2000mm" is the smallest size of a stock Revit door family, so the door was probably placed with a default or wrong size, not deliberately sized. As modelled, the two en-suite bathrooms and BATH 116 cannot be entered.',
         evidence=['3 × "M_Door-Interior-Single-1_Panel-Wood:300 x 2000mm": OverallWidth 0.35 m, OverallHeight 2.025 m; between 107↔108, 110↔109 (GROUND FLOOR) and 117↔116 (FIRST FLOOR).',
                   'Other doors: 1.0 m passage doors, 1.21 m double doors, 0.85 m Vision_Lite door.'],
         hidden_knowledge='Bath/WC doors in dwellings ≈70 cm clear (taken as the conventional size); doors in accessible public buildings ≥ 0.90 m clear; overall width ≠ clear width.',
         basis=[C['door_bath'], C['bf_door'], C['door_frame']],
         rubric=['Verdict: unusable (0.35 m)', 'Compares with ≈70 cm and 0.90 m', 'Recognises a family default/modelling error']),

    dict(project='fantasy_hotel_1', derived_from=[368], question_type='derivation',
         question='The model contains no parking spaces, but east of the building there is an asphalt surface ("Floor:10cm asphalt") of about 15.6 × 37.2 m. Could it hold one car per guest room in a standard 90° layout, and does its position follow the usual design guidance on where motel parking should be?',
         answer='Capacity, yes. Using Neufert\'s 90° parking example (bays 2.50 m wide, 5.50 m access aisle), 37.2 / 2.50 gives 14 bays per row. Two rows along the 15.6 m width leave (15.6 − 5.5) / 2 ≈ 5.05 m of depth per row, enough for about 28 cars against 18 guest rooms. Position, only partly. Motel guidance places parking as near to the rooms as possible, with short-term parking at registration. Here the asphalt starts ≈13 m east of the building (x ≈ 11.3 vs façade ≈ −1.9) behind a grass strip, and the guest-room doors open to the north, south and the inner courtyards, up to ≈24 m away from the asphalt (master-bedroom doors at x ≈ −12.3). Nobody parks at their door. The original answer\'s ≈518 m² "exterior space" is actually the area of the L3 roof slab (518.5 m², the building footprint), not a parking area.',
         evidence=['IfcSlab "Floor:10cm asphalt" (GROUND FLOOR): ≈578.6 m², x 11.3…26.9, y −18.0…19.2 m; road centre-line slabs at x ≈ 31.',
                   'Grass slab x −1.7…6.3 between building and asphalt; L3 roof slab "slab 200 mm 2": 518.5 m², x −16.2…−1.9.',
                   'Guest-room doors: 1.0 m doors on the north (y 16.2) and south (y −15.3) façades and courtyard side; 1.21 m double doors of master bedrooms at x ≈ −12.3.',
                   'No parking IfcSpace; 18 bed-furnished guest rooms.'],
         hidden_knowledge='Motels: car park or carport as near to the room as possible; Neufert\'s 90° parking example uses 2.50 m bays and a 5.50 m aisle.',
         basis=[C['motel_parking'], C['parking_90']],
         rubric=['≈14 bays per row, ≈28 total ≥ 18 rooms', 'Uses 2.50 m bays and 5.50 m aisle', 'Notes the parking is remote from room doors (≈13–24 m)', 'Flags 518 m² as the roof slab, not parking (optional)']),
]

# x_g4 — expansion group 4: non-residential buildings, structure and modular planning.
# New knowledge points (offices: cleaning/caretaker, archives, entrance area, canteen location, group-room
# window distance, corridors in small use units; hotels/catering: essential hotel areas, restaurant
# kitchen/servery layout; parking: bay depth lost to protection bows; structure: slab spans, structural
# vs. fitting-out/façade grid, modular coordination, bracing of frame/wall structures).
# All items are supplements (pairing='supplement').

# ---------------------------------------------------------------- structure and modular planning
C['g4_slab_span'] = cite('page_0257', 'Solid reinforced concrete slabs span 2.5–5.5 m, ribbed slabs 5.0–7.5 m, both with a maximum 12.5 m between main beams.')
C['g4_ribbed'] = cite('page_0255', 'Ribbed slabs: Only economical over longer spans (less self-weight, higher labour costs for formwork).')
C['g4_grid'] = cite('page_0252', 'Grid module spacings define possible room sizes through the resulting spacing of columns and façades. The fitting out and façade grids must be the same in order to enable the partitions to connect to the windows.')
C['g4_grid_offset'] = cite('page_0252', 'The structural grid can be offset against the fitting out grid. This reduces the problem of connecting the partitions to columns, but loses space in the rooms, which contain columns.')
C['g4_mullion'] = cite('page_0252', 'Vertical profiles in the façade, which lie on the modular grid, should be wide enough to connect a partition.')
C['g4_module_M'] = cite('page_0047', 'The units of the modular system are the basic module M = 100 mm and the multi-modules 3 M = 300 mm, 6 M = 600 mm and 12 M = 1200 mm.')
C['g4_nominal'] = cite('page_0046', 'Structural dimensions or nominal dimensions (for construction types with joints and wall finishes) are derived from modular dimensions by deducting or adding the component for the joint or the finish thickness.')
C['g4_brick'] = cite('page_0046', 'Example: modular dimension for the length of a brick = 25 cm; thickness of the vertical joint = 1 cm; nominal dimension for the length of the brick = 24 cm; modular dimension for the thickness of poured concrete walls = nominal dimension = 25 cm')
C['g4_frame10'] = cite('page_0257', 'Frame structures without special wind bracing are economic only up to about 10 storeys.')
C['g4_bracing'] = cite('page_0255', 'Bracing through walls acting as deep beams, storey frames and the provision of solid access cores and end-fixed side zones.')
C['g4_walls'] = cite('page_0255', 'Solid partition walls can replace columns and supporting beams')

# ---------------------------------------------------------------- offices
C['g4_cleaner'] = cite('page_0250', 'A cleaner’s room should be provided on every floor, as a store for cleaning equipment and ideally with water supply and bucket sink.')
C['g4_caretaker'] = cite('page_0250', 'The caretaker should have a rest room, store and workshop in a central location.')
C['g4_archive_load'] = cite('page_0250', 'Archive rooms should be designed for an increased floor loading of 7.5–12.5 kN/m² (for mobile units)')
C['g4_archive_dry'] = cite('page_0249', 'The rooms must be dry, so attic and cellar are inadvisable.')
C['g4_archive_h'] = cite('page_0249', 'ceiling clearance height 2.10 m (2 storeys of normal office space = 3 storeys of filing)')
C['g4_entrance'] = cite('page_0250', 'Connection between public and working areas. The important functions are lobby, access control, information, visitor registration and waiting zone.')
C['g4_entrance_ci'] = cite('page_0250', 'Important area for the company’s corporate identity – the first impression is decisive!')
C['g4_canteen'] = cite('page_0250', 'Location near the reception and outside the access control allows outside visitors in.')
C['g4_group_window'] = cite('page_0245', 'via the size of the workplace surroundings (max. 7.5 m to a window)')
C['g4_group_rooms'] = cite('page_0245', 'Group rooms (smaller open-plan) are suitable for work groups with constant information exchange.')
C['g4_unit400'] = cite('page_0253', 'For combined use units of less than 400 m², the corridors are not subject to the requirements for escape routes.')
C['g4_group_4_16'] = cite('page_0251', 'The experience with the open-plan layout led to the development of group offices with approx. 4–16 workstations')
C['g4_daylight7'] = cite('page_0253', 'Daylight can mostly be exploited into a room depth of about 7.00 m.')

# ---------------------------------------------------------------- hotels and catering
C['g4_hotel_areas'] = cite('page_0183', 'The essential areas are: hotel lobby and reception as the central, well-arranged and prestigious nerve centre between the various parts of the operation, catering area in connection with the hotel lobby')
C['g4_reception_1star'] = cite('page_0184', 'reception as a separate area')
C['g4_rest_group'] = cite('page_0187', 'Kitchen, side rooms, toilets and sanitary installations should be grouped around the dining room')
C['g4_servery'] = cite('page_0192', 'Servery for restaurant kitchens with counter or self-service, ideally situated between the preparation area and the dining room.')

# ---------------------------------------------------------------- parking
C['g4_bay_size'] = cite('page_0412', 'Parking space size (2.50 × 5.00 m = 12.50 m²)')
C['g4_aisle90'] = cite('page_0402', '90° parking, access 5.50 m wide, parking space 2.50 m wide')

ITEMS += [
    # ============================================================ structure and modular planning
    dict(project='fzk_house', derived_from=[], pairing='supplement', question_type='derivation',
         question='The FZK house is 12.00 × 10.00 m in plan, its external walls are 30 cm and its internal walls 24 cm thick (both "Leichtbeton" masonry), and the floors are 2.70 m apart. Express these dimensions in the units of the modular coordination system. Which are modular, which belong to the coarser multi-modules, and how is the 24 cm wall explained?',
         answer='With M = 100 mm: 12.00 m = 120 M, which is also 40 × 3M, 20 × 6M and 10 × 12M; 10.00 m = 100 M but is not a multiple of 3M, 6M or 12M (10.00 / 0.30 = 33.3), so the short side only fits the basic module. The storey height 2.70 m = 27 M = 9 × 3M, and the 30 cm external wall = 3M. The 24 cm internal wall is not modular itself but a nominal dimension: in the masonry series the modular length is 25 cm and the nominal size is obtained by deducting the 1 cm joint (25 − 1 = 24 cm). So the plan, storey and outer walls are set out in modular dimensions, the inner walls follow the joint-reduced nominal masonry size.',
         evidence=['IfcSlab "Bodenplatte" 12.00 × 10.00 m; external walls Wand-Ext-ERDG-1…4 0.30 m thick, outer faces at x 0.00/12.00 and y 0.00/10.00 m (type "Leichtbeton 102890359 300").',
                   'Internal walls Wand-Int-ERDG-1…5 0.24 m thick (type "Leichtbeton 102890359 240").',
                   'Storeys Erdgeschoss 0.00 m, Dachgeschoss +2.70 m; Slab-033 0.20 m at +2.50–2.70 m.'],
         hidden_knowledge='Modular coordination: M = 100 mm, multi-modules 3M/6M/12M; nominal dimension = modular dimension minus joint (brick 25 cm → 24 cm).',
         basis=[C['g4_module_M'], C['g4_nominal'], C['g4_brick']],
         rubric=['Converts 12.00, 10.00, 2.70, 0.30 m into M / 3M multiples correctly', 'Notes 10.00 m is not a multiple of 3M/6M/12M', 'Explains 24 cm as 25 cm modular minus 1 cm joint (nominal dimension)']),
    dict(project='ac20', derived_from=[], pairing='supplement', question_type='diagnosis',
         question='The institute has five levels: a basement with meeting, seminar, lab and four "Technikraum" rooms, three office floors with WCs, and an attic. On the ground floor, room 104 is labelled "Buero Hausmeister" (12.4 m²), next to the central entrance hall. What is missing in the building for cleaning and caretaking, and what is done right?',
         answer='No room on any floor is a cleaner\'s room: every level holds only offices, labs, meeting rooms, WCs, technical rooms and corridors. Neufert asks for a cleaner\'s room on every floor, ideally with water supply and bucket sink, so five such stores (or at least one per office floor) are missing; cleaning equipment would have to be kept in the WCs or carried from the basement up the single stair. For the caretaker the location is right: office 104 lies centrally beside the entrance hall 117 and the stair. But the caretaker only gets a 12.4 m² office; the rest room, store and workshop Neufert lists are not provided (the basement Technikräume are plant rooms, not a workshop).',
         evidence=['IfcSpace names per storey: Keller 001–017 (Besprechungsraum I/II, Technikraum I–IV, Seminarraum, WC Herren/Damen, Labor K1–K5, Flur), Erdgeschoss 101–118 (Buero …, Labor I/II, WC, Flur), 1./2. Obergeschoss 201–222 / 301–322 (Buero, WC Herren/Damen, Flur), Dachgeschoss 401–403 (Flur, Dachboden-1/2).',
                   'Space 104 "Buero Hausmeister": 12.377 m², ≈2.9 × 4.4 m (x 15.1–18.0, y 2.3–6.7), adjacent to 117 "Flur EG Eingang" (x 18.3–23.7) with the central stair.',
                   'No space named Putzraum/Reinigung or similar on any level.'],
         hidden_knowledge='A cleaner\'s room on every floor (store, water, bucket sink); caretaker needs rest room, store and workshop in a central location.',
         basis=[C['g4_cleaner'], C['g4_caretaker']],
         rubric=['States no cleaner\'s room exists on any floor', 'Cites the one-per-floor requirement', 'Accepts the central location of the caretaker office', 'Notes missing rest room / store / workshop']),
    dict(project='digital_hub', derived_from=[], pairing='supplement', question_type='compliance',
         question='The only room for cleaning materials is "Putzmittel" (0-2, 10.3 m²) in the basement B01, next to the west lift. The ground floor (≈1,157 m² of spaces) and the first floor hold offices, seminar rooms, the cafeteria and WCs. Is the cleaning provision adequate for an office building?',
         answer='No. Neufert asks for a cleaner\'s room on every floor, as a store for cleaning equipment and ideally with water and a bucket sink. The building has one, on B01 only; E00 and E01, where all the offices, the cafeteria and the WCs are, have none. Its position next to the west lift (300) at least lets trolleys reach the upper floors without stairs, which softens but does not replace the missing per-floor stores; a small room near each WC core on E00 and E01 would be needed.',
         evidence=['Space 0-2 "Putzmittel": 10.335 m², x 14.13–18.10, y 19.70–22.30 m, storey B01_OKRD; 300 "Aufzug West" at x 17.13–19.13, y 15.52–18.10 m.',
                   'E00_OKRD spaces (26, ≈1,157 m²) and E01_OKRD spaces: Gruppenbüro, Open Workspace, Cafeteria, Küche, Seminar/Konferenz, WC Damen/Herren, Treppenhaus, Flur; no cleaning room.',
                   'Original answer #139: space list per level.'],
         hidden_knowledge='A cleaner\'s room should be provided on every floor.',
         basis=[C['g4_cleaner']],
         rubric=['Finds the single cleaning room on B01', 'Applies the every-floor rule → E00 and E01 lack one', 'Mentions lift adjacency as partial mitigation (optional)']),
    dict(project='ac20', derived_from=[], pairing='supplement', question_type='compliance',
         question='The institute has no archive room. Someone proposes to store the paper files in the two attic rooms Dachboden-1 and Dachboden-2 (each about 17.7 × 11.4 m in plan, under the pitched roof, on a 30 cm slab at +9.00 m). Is this a suitable archive location?',
         answer='No. Neufert advises that filing and archive rooms must be dry, which is why attics and cellars are inadvisable. The attic also lacks height: the roof underside reaches only about +10.64 m at the ridge, so the clear height is at most ≈1.64 m, well below the 2.10 m that Neufert names as a favourable ceiling clearance for filing (2 office storeys = 3 filing storeys). Finally, archive rooms should be designed for an increased floor loading of 7.5–12.5 kN/m² (the book\'s figure for mobile units); the 30 cm attic slab would have to be checked for that, since nothing in the model shows it was designed as a storage floor. (The space table\'s 2.70 m height for the attic rooms is a default, not the real geometry.)',
         evidence=['Spaces 402 Dachboden-1 and 403 Dachboden-2: 71.08 m² each, ≈17.7 × 11.4 m, floor +9.00 m, geometry top +10.64 m (bbox height 1.64 m); space table height 2.70 m.',
                   'IfcSlab "Decke-002" 0.30 m at +8.70–9.00 m; IfcSlab "Dach-001" roof planes, underside at the ridge ≈ +10.64 m.',
                   'No space named Archiv/Registratur in any storey.'],
         hidden_knowledge='Filing rooms must be dry (attic and cellar inadvisable), a favourable ceiling clearance for filing is 2.10 m; archive rooms should be designed for 7.5–12.5 kN/m² (for mobile units).',
         basis=[C['g4_archive_dry'], C['g4_archive_h'], C['g4_archive_load']],
         rubric=['Rejects the attic because archives must be dry (attic/cellar inadvisable)', 'Compares ≈1.64 m clear height with the favourable 2.10 m (a recommendation, not a fixed minimum)', 'Raises the 7.5–12.5 kN/m² (mobile units) floor loading check']),
    dict(project='fantasy_office_building_1', derived_from=[], pairing='supplement', question_type='intent',
         question='Each wing of the ground floor is entered through a pair of glazed façade doors into a "Lobby" (98.3 m², ≈3.58 × 31.26 m). Just inside stands a 3.0 m "Tisch_Empfang" counter with two swivel chairs behind it; further along are a 2 m sofa with a side table, two groups of two armchairs ("Sofa-02") with glass tables, and at the far end a second 3.0 m "Tisch_Empfang" with four bar stools. What role is this lobby designed to play, and which function of a typical office entrance area is not provided?',
         answer='It is laid out as the office entrance area that links the public and the working areas: the counter facing the doors is the information point and visitor registration (staff seated behind it), the sofa and armchair groups form the waiting zone, and the counter with stools at the end works as a stand-up bar / informal meeting point, adding to the first impression that Neufert calls decisive for corporate identity. What is missing is access control: the lobby opens directly, through ordinary doors, onto the WCs and the Working Space, and no gate, barrier or separate controlled zone is modelled between visitors and the workplaces.',
         evidence=['Façade doors 2S7nIm7pvBthAHaPVMoDmb/…Dmd and 0N9CSx_ib7HQ7izEW$Ow$4/…$6 ("TU Fassade - 1-flg-Drehflügel"), y ≈ −11.2…−6.5 m, into the Lobby spaces 1 and 24.',
                   'IfcFurniture "Tisch_Empfang" 3.0 × 0.42 m at y −10.19…−7.19 m with two "Drehstuhl-01" behind it; "Sofa-08 2000 x 800" + "Tisch-04" (y ≈ −13.5…−11.5); 2 × 2 "Sofa-02" with "Tisch-02 Glas" (y ≈ −17.5…−15.3); second "Tisch_Empfang" across the lobby at y ≈ −19.9 with four "Hocker-06" (per wing, mirrored).',
                   'Lobby doors 0.885 m "Drehflügel 1-flg - Stahlzarge" lead directly to WC (3 per wing) and Working Space.'],
         hidden_knowledge='Office entrance area: link between public and work areas with lobby, access control, information, visitor registration and waiting zone; first impression/corporate identity.',
         basis=[C['g4_entrance'], C['g4_entrance_ci']],
         rubric=['Maps the counter to information/visitor registration', 'Maps the sofas to the waiting zone', 'Identifies missing access control (lobby opens straight onto WCs and work areas)']),
    dict(project='digital_hub', derived_from=[], pairing='supplement', question_type='intent',
         question='On the ground floor the Cafeteria (114.5 m²) and the Küche (35.9 m²) sit at the west end of the "Eingangsbereich / Flur" that visitors enter through the glazed façade doors. Two double doors (1.635 m) open from the cafeteria straight onto the entrance hall, one of them at the junction with the kitchen, and the west WCs are a few metres along the same hall. Why is the cafeteria placed here, and does the arrangement of kitchen, dining room and toilets follow catering practice?',
         answer='The cafeteria is placed in the public entrance zone, directly off the entrance hall and in front of the office floors, i.e. outside any access-controlled part of the building. Neufert recommends exactly this for office canteens: near the reception and outside the access control, so that outside visitors (e.g. guests of the adjacent Veranstaltungsraum) can use it. The catering layout is also right in principle: the kitchen adjoins the dining room with a direct double-door connection, so the servery can sit between preparation and dining, and the toilets (WC Damen/Herren West) are grouped close by off the same hall. The weak point is that the kitchen–cafeteria connection shares a door node with the entrance hall, so service traffic and visitor traffic cross there.',
         evidence=['Space 1-2 Cafeteria: 114.452 m², x 7.13–27.93, y 7.12–12.63 m; 1-3 Küche: 35.927 m², x 7.13–13.88, y 12.78–18.10 m; 1-1 Eingangsbereich / Flur 383.6 m².',
                   'IfcDoor 03fYK2KZb9bQXMSPptFYV5 "ML - 1635 x 2135" (DOUBLE_DOOR) between Cafeteria, Eingangsbereich and Küche; 11eI7IJI9EJgsn80j11Erx (same type) Cafeteria–Eingangsbereich; 03fYK2KZb9bQXMSPptFYPu Küche–Eingangsbereich.',
                   'Façade doors 0ehNcYPbH3JQicvZQLHOvk/…$q ("TU Fassade") into the Eingangsbereich; 1-15/1-16 WC Damen/Herren West at x 21.1–26.6 off the hall; 1-12 Veranstaltungsraum 76.5 m².'],
         hidden_knowledge='Office canteens near reception and outside access control so visitors can use them; kitchen, side rooms and toilets grouped around the dining room; servery between preparation and dining.',
         basis=[C['g4_canteen'], C['g4_rest_group'], C['g4_servery']],
         rubric=['Explains the location as public zone / outside access control for visitors', 'Checks kitchen directly adjoins the dining room (servery between)', 'Notes toilets grouped nearby', 'Flags the shared door node between service and visitor traffic (optional)']),
    dict(project='digital_hub', derived_from=[], pairing='supplement', question_type='compliance',
         question='The sixteen "Gruppenbüro" rooms (≈37 m² each) and the two open workspaces line the long façades; each is about 5.4–5.5 m deep, with one 6.0 m × 1.5 m window per 7.0 m bay. The VR/AR LAB (74 m²) at the east end is 6.75 × 10.98 m with windows only in its south wall and the southern 4 m of its east wall. Judge the rooms against the usual limit for group rooms.',
         answer='Group rooms should keep the workplace surroundings within about 7.5 m of a window. All group offices and open workspaces are only 5.4–5.5 m deep, so every point is within ≈5.5 m of the façade windows, 2 m inside the limit (and inside the ≈7.0 m daylight depth). At ≈37 m² they also suit the small teams (4–16 workstations) that group offices are meant for. The VR/AR LAB is different: its north-west corner is ≈11 m from the south windows and ≈9.4 m from the nearest east window, so if it were used as a group workspace its rear third would lie beyond 7.5 m; as a lab that depends on artificial light (VR/AR) this is acceptable, but it should not be counted as a group office.',
         evidence=['Spaces 1-4…1-10, 2-4…2-20 Gruppenbüro: 36.7–37.7 m², 6.80–6.85 × 5.40–5.50 m; 1-7/2-7 Open Workspace 20.85 × 5.4 m.',
                   'IfcWindow "FE 3 tlg … 6000 x 1500" on the long façades, one per 7.0 m bay; "FE 2 tlg … 4000 x 1500" in the end walls at y 7.5–11.5 and 22.1–26.1 m.',
                   'Space 1-11 VR/AR LAB: 74.08 m², x 63.12–69.88, y 7.12–18.10 m; windows x 63.5–69.5 (south) and x 69.88, y 7.5–11.5 (east).'],
         hidden_knowledge='Group rooms: workplace surroundings max. 7.5 m to a window; group offices ≈4–16 workstations; daylight usable to ≈7.00 m depth.',
         basis=[C['g4_group_rooms'], C['g4_group_window'], C['g4_group_4_16'], C['g4_daylight7']],
         rubric=['Uses 5.4–5.5 m depth vs 7.5 m → compliant', 'Computes the VR/AR lab distances (≈9.4–11 m) → beyond 7.5 m', 'Distinguishes the lab from a group office']),
    dict(project='fantasy_office_building_3', derived_from=[], pairing='supplement', question_type='compliance',
         question='On every office floor the offices open onto two corridors ("Corridor east" and "Corridor west"), each 21.28 m long and only 1.51–1.73 m wide. Do these corridors have to meet the requirements for escape routes? Use the floor areas of the model to decide.',
         answer='Probably not. Neufert notes that for combined use units of less than 400 m², the corridors are not subject to escape-route requirements. Each office floor of this building is small: the modelled spaces total 358.0 m² (EG), 299.3 m² (OG1), 355.9 m² (OG2), 356.0 m² (OG3) and 244.6 m² (OG4), including the two staircase cores and lift shafts (≈32.7 m²), so the usable area per floor is only ≈212–325 m². If each floor is let or used as one unit, it stays below 400 m², and the corridors are ordinary circulation, not necessary corridors; the escape routes are the two staircase cores. The assumption to state is that a floor is not merged with another floor into one larger unit.',
         evidence=['Spaces 018/118/218/318/418 Corridor east (1.51–1.66 × 21.28 m) and 019/119/219/319/419 Corridor west (1.58–1.73 × 21.28 m).',
                   'Σ IfcSpace area per storey: EG 358.01, OG1 299.30, OK OG2 355.90, OK OG3 355.97, OK OG4 244.55 m².',
                   'Staircase core (west) 13.87 m², Staircase core (east) 14.43 m², Elevator shafts 2 × 2.21 m² per floor.'],
         hidden_knowledge='Corridors within combined use units < 400 m² are not subject to escape-route requirements.',
         basis=[C['g4_unit400']],
         rubric=['Sums the floor areas (all < 400 m²)', 'Applies the 400 m² use-unit rule', 'States the assumption that each floor is one unit; escape via staircase cores']),

    # ============================================================ hotels and catering
    dict(project='fantasy_hotel_1', derived_from=[], pairing='supplement', question_type='diagnosis',
         question='The "hotel" model contains, on two floors, living rooms, master bedrooms, two "Room Name" rooms, four sanitary rooms, three staircase spaces and one KITCHEN (≈4.4 × 2.5 m) furnished with a small round dining table, four chairs, a worktop and a TV. Which areas that every hotel needs are missing, and what does that say about what has been modelled?',
         answer='The model has no lobby or reception, no catering area connected to a lobby, no administration, staff or service areas, only guest-room-type spaces and stairs. Neufert names the hotel lobby and reception as the central nerve centre between the parts of the operation, with catering attached to it, plus administration, a separately accessed staff area and a service area with kitchens and stores; even the lowest DEHOGA category requires a reception as a separate area. The single KITCHEN is a domestic-size room with a family dining table, not a hotel kitchen or restaurant. So what is modelled is only a guest-room (or apartment) wing; as a hotel it is incomplete, and the missing reception would have to be in another building or not exist at all.',
         evidence=['26 IfcSpace: LIVING ROOM 100, 101, 103, 114, 115, 124–126; MASTER BEDROOM 106, 107, 110, 112, 118, 120, 121, 123; Room Name 104, 105; BATHROOM 108, 109; BATH 116; WASH BASIN 117; STAIRCASE 111, 113, 119; KITCHEN 102.',
                   'KITCHEN 102 ≈4.36 × 2.53 m: "M_Table-Dining Round w Chairs", 4 "M_Chair-Breuer", one "Work_Surface-Rectangular", one overhead cabinet, a flat-screen TV.',
                   'No space named lobby, reception, restaurant, office, staff or store.'],
         hidden_knowledge='Essential hotel areas: lobby and reception as nerve centre, catering connected to the lobby, administration, staff area, guest rooms, service area; reception is required even at 1 star.',
         basis=[C['g4_hotel_areas'], C['g4_reception_1star']],
         rubric=['Lists missing lobby/reception, catering, administration/staff/service areas', 'Identifies the KITCHEN as domestic, not a hotel kitchen', 'Concludes the model is only a guest-room/apartment wing']),

    # ============================================================ parking
    dict(project='digital_hub', derived_from=[], pairing='supplement', question_type='derivation',
         question='Each of the 26 bays (2.50 × 5.00 m, two facing rows, 9.55 m aisle between them) has a bow-shaped "Anfahrschutz Rohr:1000 x 700" (≈1.2 m wide, 0.20 m deep, 0.77 m high) standing inside the bay near its rear end; in the south row a charging station ("E-Ladestation") stands behind each bow. The bows are 0.49 m (south row) and 0.23 m (north row) in from the rear bay line. How much clear bay length is left in front of the bows compared with the regulation parking-space size, and is the aisle still wide enough for 90° parking if each car takes that full length?',
         answer='Yes, thanks to the wide aisle. Neufert notes (in the petrol-station section) that state regulations set the parking space size at 2.50 × 5.00 m (12.50 m²); the modelled bays match this on paper. In front of the bows only 5.00 − 0.49 − 0.20 ≈ 4.31 m (south row) and 5.00 − 0.23 − 0.20 ≈ 4.57 m (north row) remain, i.e. 0.69 m and 0.43 m less than a 5.00 m bay. A car that needs the full 5.00 m therefore stands that far into the aisle, leaving 9.55 − 0.69 − 0.43 ≈ 8.4 m, still well above the 5.50 m access that the book\'s 90° parking example shows with 2.50 m bays. Put the other way, the same rows with full 5.00 m clear bays would need only (5.00 + 0.69) + 5.50 + (5.00 + 0.43) ≈ 16.6 m of depth instead of the 19.55 m modelled; the bows and chargers simply consume part of the surplus aisle.',
         evidence=['26 IfcBuildingElementProxy "Parkplatz - 01 90:2500 x 5000": south row y 7.17–12.17 m, north row y 21.72–26.72 m; aisle 12.17–21.72 m = 9.55 m.',
                   '26 "Anfahrschutz Rohr:1000 x 700": 1.20 × 0.20 m, z −0.20…+0.57 m; south row y 7.66–7.86, north row y 26.29–26.49 m, centred in each bay.',
                   '13 "E-Ladestation - 03:Typ1" (0.43 × 0.27 × 1.30 m) at y 7.36–7.63 m, between the south-row bows and the rear bay line.', 'Original answer #144/#145: 26 spaces, 13 chargers, 26 Anfahrschutz.'],
         hidden_knowledge='Parking space size set by state regulations (quoted for petrol stations): 2.50 × 5.00 m = 12.50 m²; the book\'s 90° parking example: 5.50 m access with 2.50 m bays.',
         basis=[C['g4_bay_size'], C['g4_aisle90']],
         rubric=['Computes clear lengths ≈4.31 m and ≈4.57 m (0.69 / 0.43 m short of 5.00 m)', 'Remaining aisle ≈8.4 m ≥ the 5.50 m of the 90° parking example → still works', 'Notes the surplus aisle absorbs the lost bay depth (≈16.6 m vs 19.55 m, optional)']),
]

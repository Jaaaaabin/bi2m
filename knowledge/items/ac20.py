# ac20: KIT "AC20-Institute-Var-2" office/institute building (ArchiCAD 20, IFC4).
# Keller -3.0 / EG 0.0 / 1.OG 3.0 / 2.OG 6.0 / DG 9.0 m; 82 spaces; space boundaries present.

C['off_height'] = cite('page_0255', 'Ceiling height 2.75 m according to Vst regulation (enables the later installation of raised floor and deeper suspended ceilings).')
C['off_sedentary'] = cite('page_0255', 'For predominantly sedentary activities, the reduction of the ceiling height by 25 cm is possible, but min. 2.50 m clear.')
C['off_corridor_h'] = cite('page_0255', 'Corridors and sanitary facilities are permitted to be 2.30 m high (this can be exploited for installation runs).')
C['off_toilets'] = cite('page_0250', 'A good ratio is one toilet unit per 50–80 workstations. Space requirement ~0.6–0.8 m² per workstation.')
C['conf_seat'] = cite('page_0250', 'A conference area requires about 2.5 m^2 per seat (without subsidiary areas).')
C['conf_entrance'] = cite('page_0250', 'Conference areas should be directly accessible from the entrance area.')
C['grid_150'] = cite('page_0252', 'Workstation depth 2.20 m (80 cm desk, 1 m movement area, 40 cm shelf behind). With 10 cm wall thickness, this gives 4.40 m clear room space.')
C['grid_150_double'] = cite('page_0252', 'This is the economical module dimension for single-room offices consisting mainly of double workstations.')
C['grid_modules'] = cite('page_0252', 'The modular dimensions, which have proved successful in recent years, are 1.50 m for single-room offices and 1.35 m for office types based on the combi principle.')
C['grid_depth'] = cite('page_0252', 'The usual depth of buildings with central corridors is 12–13 m.')
C['daylight_7m'] = cite('page_0253', 'Daylight can mostly be exploited into a room depth of about 7.00 m.')
C['work_view'] = cite('page_0109', 'The total width of all visual connections to the outside must be at least 1/10 of the total width of all walls, according to workplace guidelines')
C['work_sill'] = cite('page_0109', 'Possible visual connection to the outside should be at eye level (window sill heights of 0.85 –1.25 m)')
C['escape_window'] = cite('page_0109', 'If the window serves as an escape route, it must have a clear opening of at least 0.9 × 1.2 m and a sill height of max. 1.2 m above floor level.')
C['revolving_traffic'] = cite('page_0022', 'Because revolving doors can cope with relatively little through traffic, the door leaves can be folded at peak times and pushed to the side.')
C['revolving_extra'] = cite('page_0127', 'Revolving door with additional emergency exits')
C['door_clear_h'] = cite('page_0125', 'clear opening height of internal doors\nminimum\t210 cm')
C['bf_public'] = cite('page_0037', 'This requirement applies notably to cultural, educational, sport, leisure and health facilities, offices, administration buildings and courts, sales and catering establishments, parking, garages and toilets.')
C['bf_no_steps'] = cite('page_0034', 'All levels of buildings designed in accordance with the principles of accessibility must be accessible without steps, i.e. using a lift or a ramp.')
C['stair_office'] = cite('page_0133', 'Stairs in offices or emergency stairs should, in contrast, make it possible to change level quickly.')
C['stair_outside'] = cite('page_0133', 'For outside stairs, low steps are preferable, with dimensions of 12 × 41 to 16 × 30 cm.')

ITEMS += [
    # ------------------------------------------------------------------ ac20 (paired, ordered by id)
    dict(project='ac20', derived_from=[54], question_type='derivation',
         question='Every storey of the institute is 3.00 m floor-to-floor and every floor slab is 30 cm thick, with no raised floor or suspended ceiling modelled. What clear height does that leave in the offices, how does it compare with the standard office ceiling height, and what floor-to-floor height would the standard have needed with the same slab?',
         answer='3.00 − 0.30 = 2.70 m clear, which is exactly the FinishCeilingHeight stored on the office spaces. The standard office ceiling height is 2.75 m, so the offices are 5 cm short; they are acceptable only under the allowance for predominantly sedentary work (reduction by up to 25 cm, but at least 2.50 m clear), leaving 0.20 m above that minimum. Reaching 2.75 m with a 0.30 m slab would need a floor-to-floor height of 3.05 m. Because the 2.75 m rule exists to leave room for a later raised floor or deeper suspended ceiling, the 3.00 m section leaves at most about 20 cm for such retrofits before the offices drop below 2.50 m.',
         evidence=['IfcBuildingStorey elevations: Keller −3.0, Erdgeschoss 0.0, 1. Obergeschoss 3.0, 2. Obergeschoss 6.0, Dachgeschoss 9.0 m (3.00 m each).',
                   'Floor slabs Decke-001 / Decke-002: 0.30 m thick (e.g. z −0.30 to 0.00, 2.70 to 3.00, 5.70 to 6.00).',
                   'Office spaces (e.g. 101 Buero Meier, 201 Buero Obermueller): BaseQuantities.FinishCeilingHeight 2.70 m; no IfcCovering in the model.'],
         hidden_knowledge='Office ceiling height 2.75 m (Vst), reducible by 25 cm to min. 2.50 m for sedentary work; the 2.75 m reserves space for raised floors/suspended ceilings.',
         basis=[C['off_height'], C['off_sedentary']],
         rubric=['Computes 2.70 m clear (3.00 − 0.30)', 'Compares with 2.75 m and invokes the sedentary reduction to ≥ 2.50 m', 'Gives 3.05 m as the floor-to-floor needed', 'Notes ≈0.20 m reserve for raised floor/suspended ceiling (optional)']),
    dict(project='ac20', derived_from=[57], question_type='diagnosis',
         question='The two widest doors in the model are Tür-019 (2.0 m) and Tür-018 (1.8 m). Tür-019 is the only door leading outside. What is wrong with relying on it as the building\'s exit, and can the wide Tür-018 make up for it?',
         answer='Tür-019 is a revolving door (IFC Tür - Drehtür, operation REVOLVING, 1.90 m clear). Revolving doors are not permitted at emergency exits because they can block in danger, and they handle relatively little through traffic; since no other door in the model leads outside, the institute has no compliant final exit. Its 1.90 m clear width does not help: the problem is the door type, not the size. Since the revolving door cannot itself be the emergency exit, a separate emergency exit is needed, e.g. a hinged swing door beside it in the entrance façade (as in Neufert\'s illustration of a revolving door with additional emergency exits), or a second external exit elsewhere. Tür-018 cannot make up for it: although it is a 1.80 m double door (1.70 m clear), it is an internal door between the stair hall and the corridors on every floor and does not lead outside.',
         evidence=['Tür-019 (GlobalId 18PQUIFELEARLM4c0brquf): "IFC Tür - Drehtür", OperationType REVOLVING, 2.00 × 2.10 m, Durchgangslichte Breite 1.90 m; bounds only Flur EG Eingang (external).',
                   'All other 76 doors connect two internal spaces (space boundaries / ArchiCAD Von Raum–zu Raum).',
                   'Tür-018 (one per storey, Keller–2.OG): "IFC Doppeltür - Eine Öffnungsrichtung" / "- Zwei Öffnungsrichtungen" (Keller), 1.80 m, clear 1.70 m, between the stair hall and the corridors; connects two internal spaces.'],
         hidden_knowledge='Revolving (and sliding) doors are not permissible at emergency exits; revolving doors cope with relatively little through traffic; Neufert illustrates revolving doors combined with additional emergency exits.',
         basis=[C['no_sliding_exit'], C['revolving_traffic'], C['revolving_extra']],
         rubric=['Identifies Tür-019 as a revolving door that cannot serve as an emergency exit', 'Notes it is the only external door, so there is no compliant exit', 'Tür-018 is internal and cannot serve; an additional emergency exit is needed (swing door beside Tür-019 or a second external exit)']),
    dict(project='ac20', derived_from=[58], question_type='compliance',
         question='The narrowest door in the building is the 1.00 m single-leaf type used for every office, lab and WC. Would a wheelchair user fit through these doors, and which width figure must the check use?',
         answer='Yes, with no margin. Neufert requires a clear passage width of at least 0.90 m for doors in accessible public buildings; an office/institute building is among the publicly accessible types in its parts serving the public, and for the internal offices and labs the same figure is the benchmark by analogy. The 1.00 m is the nominal/structural opening; the model\'s own clear passage width (Durchgangslichte Breite, "Größe Ausgang") is 0.90 × 2.05 m, which meets 0.90 m exactly. The check has to use the clear width, not the 1.00 m overall width. Read literally, the clear height of 2.05 m is 5 cm below the 2.10 m minimum clear opening height Neufert gives for internal doors; the 2.10 m figure is met only by the nominal height.',
         evidence=['67 doors "IFC Tür - Eine Öffnunsgrichtung": OverallWidth 1.00 m, OverallHeight 2.10 m.',
                   'AC_Equantity: Durchgangslichte Breite 0.90 m, Durchgangslichte Höhe 2.05 m; ArchiCADProperties "Größe Ausgang" 0,90x2,05, "Nominale B x H" 1,00x2,10 (e.g. Tür-014, GlobalId 3qloCPnZDEQBom1ZjBlwJP).'],
         hidden_knowledge='Accessible public buildings (offices included, in their public parts): door clear passage width ≥ 0.90 m; nominal size ≠ clear width; clear opening height of internal doors min. 2.10 m.',
         basis=[C['bf_door'], C['bf_public'], C['door_clear_h'], C['door_frame']],
         rubric=['Uses the 0.90 m clear width rather than 1.00 m', 'Verdict: passes exactly (zero margin)', 'Notes 2.05 m clear height vs 2.10 m (optional)']),
    dict(project='ac20', derived_from=[60], question_type='compliance',
         question='The widest window type (1.00 × 1.50 m, sill 0.90 m) is the standard office window; a single office such as 111 Buero Maier (≈2.8 × 4.4 m) has two of them and the basement Seminarraum (≈11.6 × 11.4 m) has sixteen. Do these rooms meet the workplace rules for view to the outside?',
         answer='Yes. For workrooms, the total width of visual connections must be at least 1/10 of the total width of all walls. Buero Maier: walls 2 × (2.8 + 4.4) = 14.4 m → at least 1.44 m needed, 2 × 1.00 = 2.00 m provided. Seminarraum: 2 × (11.6 + 11.4) = 46.0 m → 4.60 m needed, 16 × 1.00 = 16.0 m provided. The 0.90 m sill also lies inside the recommended 0.85–1.25 m eye-level band for a view out, though only 5 cm above its lower end.',
         evidence=['"IFC Fenster - ein Panel" 1.00 × 1.50 m, ArchiCAD Brüstungshöhe 0.90 m (196 of 206 windows).',
                   '111 Buero Maier: 11.95 m², geometry bounding box ≈2.8 × 4.4 m, 2 windows (space boundaries).',
                   '006 Seminarraum: 128.27 m², geometry bounding box ≈11.6 × 11.4 m, 16 windows.'],
         hidden_knowledge='Workplace guidelines: total width of visual connections ≥ 1/10 of total wall width; the view out should be at eye level (sill heights 0.85–1.25 m).',
         basis=[C['work_view'], C['work_sill']],
         rubric=['Computes 1.44 m required vs 2.00 m for the office', 'Computes 4.60 m vs 16.0 m for the seminar room', 'Checks 0.90 m sill within the recommended 0.85–1.25 m']),
    dict(project='ac20', derived_from=[61], question_type='compliance',
         question='The narrowest windows (0.90 m wide, 1.50 m high, sill 0.90 m, 7 cm frames) close the ends of the long corridors on every floor above the basement. The building has a single stair. Could these windows serve as escape windows?',
         answer='No. An escape window needs a clear opening of at least 0.90 × 1.20 m with a sill no higher than 1.20 m. The sill (0.90 m) and the height (1.50 − 2 × 0.07 ≈ 1.36 m) would pass, but 0.90 m is the overall width, so with 7 cm frames the clear width is only about 0.76 m. Even the 1.00 m office windows give only about 0.86 m. As modelled, no window type reaches the 0.90 m clear width, so none of them can serve as an emergency escape route.',
         evidence=['"IFC Fenster - ein Panel" 0.90 × 1.50 m, sill 0.90 m: one each in Flur West/Ost on Erdgeschoss, 1. and 2. Obergeschoss (6 windows); 3 further 0.90 × 2.00 m (sill 0.10 m) in Flur EG Eingang.',
                   'Window frame width (Rahmen-Breite) 0.07 m, sash frame 0.05 m.', 'Four IfcStair (Treppe-KG/EG/1-OG/2-OG), all in the one central stair hall.'],
         hidden_knowledge='Escape windows: clear opening ≥ 0.9 × 1.2 m, sill ≤ 1.2 m; overall size ≠ clear opening.',
         basis=[C['escape_window']],
         rubric=['States the 0.9 × 1.2 m clear opening and ≤ 1.2 m sill rule', 'Deducts the frames → ≈0.76 m < 0.90 m', 'Verdict: cannot serve as escape windows']),
    dict(project='ac20', derived_from=[77], question_type='derivation',
         question='The ground floor has two toilet rooms, 112 WC Herren and 113 WC Damen. Using an office-planning ratio of sanitary area per workstation, how many workstations do they cover, and how does that compare with the workplaces furnished on the ground floor?',
         answer='Offices need about 0.6–0.8 m² of sanitary area per workstation. The two WCs total 2 × 12.38 = 24.75 m², enough for about 31 (24.75 / 0.8) to 41 (24.75 / 0.6) workstations. The ground floor is furnished for about 30 workplaces (30 chairs in the eleven offices and two labs), so the provision just covers it, at the lower end of the ratio. The number of toilet units (one per 50–80 workstations) cannot be checked because the model contains no sanitary fixtures.',
         evidence=['112 WC Herren and 113 WC Damen, Erdgeschoss: 12.377 m² each.',
                   'Chairs (Kubus-Einrichtung-2) by ground-floor space: 8 single offices × 1, Buero Studenten I 6, II 6, III 5, Labor I 3, Labor II 2 = 30.',
                   'No IfcSanitaryTerminal in the model (original ifc-bench answer #76).'],
         hidden_knowledge='Office toilets: ≈0.6–0.8 m² per workstation; one toilet unit per 50–80 workstations.',
         basis=[C['off_toilets']],
         rubric=['Sums 24.75 m²', 'Derives ≈31–41 workstations', 'Compares with ≈30 furnished workplaces', 'Notes fixtures are not modelled (optional)']),
    dict(project='ac20', derived_from=[81], question_type='diagnosis',
         question='According to the space data, every room in the building, including the two attic rooms Dachboden-1 and Dachboden-2, has a ceiling height of 2.70 m. Which rooms does that height suit, and what is wrong with the attic figure?',
         answer='For the offices, labs and seminar room, 2.70 m is below the 2.75 m office ceiling height (Vst regulation) but above the 2.50 m minimum allowed for predominantly sedentary work. Corridors and WCs are permitted to be as low as 2.30 m, so they have 0.40 m to spare, enough for installation runs. The attic value is wrong: Dachboden-1 and -2 (71.08 m² each) carry FinishCeilingHeight 2.70 m, but their geometry runs only from +9.00 m to at most +10.64 m under the curved roof, a peak clear height of about 1.64 m. The 2.70 m is a default value, and these rooms are unusable as workrooms.',
         evidence=['All 82 IfcSpace: BaseQuantities.FinishCeilingHeight 2.70 m.',
                   '402 Dachboden-1, 403 Dachboden-2: 71.078 m², space geometry z 9.00 → 10.64 m (bbox height 1.64 m); roof slabs Dach-001 lowest edge ≈8.78 m.',
                   'Storey height 3.00 m, slab 0.30 m.'],
         hidden_knowledge='Office buildings: ceiling height 2.75 m (Vst), min. 2.50 m for predominantly sedentary work; corridors and sanitary rooms may be 2.30 m.',
         basis=[C['off_height'], C['off_sedentary'], C['off_corridor_h']],
         rubric=['Offices: 2.70 < 2.75 but ≥ 2.50 (sedentary)', 'Corridors/WCs only need 2.30 m', 'Flags attic spaces: geometry ≈1.64 m vs 2.70 m attribute']),

    # ------------------------------------------------------------------ ac20 (supplementary)
    dict(project='ac20', derived_from=[54], pairing='supplement', question_type='diagnosis',
         question='The central stair climbs each 3.00 m storey in three flights around two quarter landings, with 22 risers of about 13.6 cm and treads of about 35 cm (read from the stair geometry; the IfcStair has no riser properties). Is this a good stair for an office building?',
         answer='Formally it is fine. The stride is 2 × 13.6 + 35 ≈ 62 cm, inside 59–65 cm. The runs of 8, 7 and 7 risers are within 3–18 steps, as required between landings for a storey height ≥ 2.75 m. At 1.50 m wide it exceeds the 1.00 m minimum usable width German standards set for legally essential stairs in residential buildings (for public buildings Neufert sizes stair width by evacuation time, so this is only a benchmark). But 13.6/35 is a very shallow, slow stair, inside the 12 × 41 to 16 × 30 cm range Neufert recommends for outside stairs. Office stairs should let people change level quickly; a 17/29 stair would need only 18 risers (3.00 / 0.17).',
         evidence=['Treppe-EG mesh: tread surfaces every 0.136 m from 0.00 to 3.00 m (22 risers), tread depth 0.35 m; landings at +1.09 m and +2.05 m (≈1.5 × 1.5 m); flight width 1.50 m (x 18.3–19.8).',
                   'Identical stairs Treppe-KG, Treppe-1-OG, Treppe-2-OG; storey height 3.00 m.'],
         hidden_knowledge='2r + t = 59–65 cm; 3–18 steps per run; landings at storey height ≥ 2.75 m; legally essential stairs 1.00 m (German standards, residential; public buildings by evacuation time); outside stairs 12/41–16/30; office stairs should be quick; ideal 17/29.',
         basis=[C['stride'], C['run_len'], C['landing'], C['essential'], C['stair_public'], C['stair_outside'], C['stair_office']],
         rubric=['Computes 2r + t ≈ 62 cm (within range)', 'Runs ≤ 18 and landings present', 'Recognises 13.6/35 as an outdoor-type shallow stair, not a quick office stair']),
    dict(project='ac20', derived_from=[], pairing='supplement', question_type='intent',
         question='The cellular offices on the upper floors are 4.40 m deep and either 2.80 m or 5.80 m wide between 20 cm partitions, on both sides of a 2.0 m central corridor. What planning grid and workstation layout does this geometry point to?',
         answer='It is a 1.50 m office grid. Partition axes fall every 3.00 m (2.80 + 0.20 = 2 modules; 5.80 + 0.20 = 4 modules), and the 4.40 m room depth is exactly the clear room dimension Neufert gives for the 1.50 m module, the economical module for single-room offices consisting mainly of double workstations: workstation depth 2.20 m (80 cm desk, 1 m movement area, 40 cm shelf behind), which with 10 cm wall thickness gives 4.40 m clear room space. The rooms therefore point to cellular offices laid out mainly for double workstations. With 0.30 m walls the building depth is 4.40 + 0.30 + 2.00 + 0.30 + 4.40 + 2 × 0.30 = 12.0 m, inside the usual 12–13 m for central-corridor buildings. At 4.40 m every desk is well within the ≈7 m depth that daylight reaches.',
         evidence=['1. Obergeschoss spaces: 205 Buero Schmitt II x 24.1–26.9 m, 204 Buero Oberschmitt 18.1–23.9 m, 203 12.1–17.9 m … (partitions centred on multiples of 3.0 m); all offices 4.40 m deep (y 2.3–6.7 and 9.3–13.7).',
                   'Corridors Flur 1.OG West/Ost y 7.0–9.0 m (2.0 m); internal walls Kalksandstein 200 mm, external walls 300 mm.'],
         hidden_knowledge='1.50 m module: economical for single-room offices with mainly double workstations; workstation depth 2.20 m, with 10 cm wall thickness → 4.40 m clear room space; central-corridor building depth 12–13 m; daylight to ≈7 m depth.',
         basis=[C['grid_modules'], C['grid_150_double'], C['grid_150'], C['grid_depth'], C['daylight_7m']],
         rubric=['Identifies the 1.50 m grid (3.0 m axes)', 'Links the 4.40 m depth to the 1.50 m-module double-workstation office (2.20 m workstation depth, 10 cm wall → 4.40 m clear)', 'Building depth ≈12 m within 12–13 m']),
    dict(project='ac20', derived_from=[], pairing='supplement', question_type='diagnosis',
         question='Besprechungsraum I in the basement (23.9 m²) is furnished with 16 chairs, and the Seminarraum next door (128.3 m²) with 22. Are these rooms sized sensibly for their seating, and is their location where conference areas would normally be placed?',
         answer='Besprechungsraum I is overfilled. At about 2.5 m² per conference seat, 23.9 m² suits about 9–10 seats, not 16 (16 seats would need ≈40 m²); Besprechungsraum II (24.75 m², also 16 chairs) has the same problem. The Seminarraum is generous: 128.3 / 2.5 ≈ 51 seats possible against 22 furnished. Location is also off: conference areas should be directly reachable from the entrance, but both rooms are in the Keller, reached only via the stair. The model has no lift, so if the building is to be accessible (a building designed to accessibility principles must have all levels reachable without steps, by lift or ramp), these rooms are not.',
         evidence=['001 Besprechungsraum I 23.901 m², 002 Besprechungsraum II 24.754 m² (Keller): 6 tables + 16 chairs each (Kubus-Einrichtung-1/-2).',
                   '006 Seminarraum 128.273 m²: 10 tables + 22 chairs.', 'No IfcTransportElement and no lift space in the model.'],
         hidden_knowledge='Conference area ≈2.5 m² per seat; conference areas should be directly accessible from the entrance; in buildings designed to accessibility principles all levels must be reachable without steps (lift or ramp).',
         basis=[C['conf_seat'], C['conf_entrance'], C['bf_no_steps']],
         rubric=['Computes ≈9–10 seats for 23.9 m² vs 16 chairs', 'Seminarraum ≈51 seats vs 22', 'Flags basement location / no step-free access (no lift)']),
]

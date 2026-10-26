# fantasy_office_building_2 — TUM student office model (Revit 2025, IFC4, Munich).
# Only three IfcBuildingStorey are exported (3rd Floor +11.10, 4th Floor +14.80, 5th Floor +18.50 = roof level),
# but the geometry holds floor slabs at 0.00 / +3.70 / +7.40 / +11.10 / +14.80 m and the Revit levels
# "Groundfloor", "1st Floor", "2nd Floor" survive in element properties (railing/stair Base Level).
# Everything below +11.10 m is contained in the "3rd Floor" storey.
C['office_ceiling'] = cite('page_0255', 'Ceiling height 2.75 m according to Vst regulation (enables the later installation of raised floor and deeper suspended ceilings).')
C['office_sedentary'] = cite('page_0255', 'For predominantly sedentary activities, the reduction of the ceiling height by 25 cm is possible, but min. 2.50 m clear.')
C['office_corr'] = cite('page_0255', 'Corridors and sanitary facilities are permitted to be 2.30 m high')
C['workroom_glass'] = cite('page_0109', 'For workrooms more than 3.5 m high, the glass area of the window must be at least 30% of the outside wall area')
C['view_width'] = cite('page_0109', 'The total width of all visual connections to the outside must be at least 1/10 of the total width of all walls, according to workplace guidelines')
C['view_sill'] = cite('page_0109', 'Possible visual connection to the outside should be at eye level (window sill heights of 0.85 –1.25 m)')
C['ws_total'] = cite('page_0250', 'The total space requirement per workstation varies between 23 and 45 m^2, depending on organisational and status requirements.')
C['tea_kitchen'] = cite('page_0250', 'Tea kitchens should be as near to the workstations as possible and connected with communication zones. For every approx. 50–100 workplaces, one ~10 m² kitchen.')
C['office_wc'] = cite('page_0250', 'A good ratio is one toilet unit per 50–80 workstations.')
C['conference'] = cite('page_0250', 'A conference area requires about 2.5 m^2 per seat (without subsidiary areas).')
C['ws_depth'] = cite('page_0252', 'Workstation depth 2.20 m (80 cm desk, 1 m movement area, 40 cm shelf behind). With 10 cm wall thickness, this gives 4.40 m clear room space.')
C['double_ws'] = cite('page_0252', 'This is the economical module dimension for single-room offices consisting mainly of double workstations.')
C['guard_work'] = cite('page_0134', 'drop <12 m, h = 1.00 m for workplaces')
C['ws_move'] = cite('page_0248', 'There should be a free movement area of at least 1.5 m² at the workstation.')

ITEMS += [
    dict(project='fantasy_office_building_2', derived_from=[410], question_type='diagnosis',
         question='The storey list gives the 4th Floor at +14.80 m, where the model places benches, planters and two external railings of type "Vertikale Stäbe mit Handlauf" along the open edges. The railings\' IFC Height is 1.219 m. Treating the open terrace edge like a balcony edge, what guard height would it need, and does the railing actually provide it?',
         answer='About 1.10 m. Neufert gives guard-rail heights for galleries, mezzanines, balconies and theatre circles; a roof terrace is not named, so the rule is applied here by analogy to a balcony. The terrace floor is 14.80 m above the ground-floor slab (0.00 m), and for drops of more than 12 m the guard height is 1.10 m. The railing does not provide it. Its Revit "Railing Height" is 1.00 m and its geometry ends at +15.80 m, i.e. 1.00 m above the +14.80 m floor; the IFC Height of 1.2192 m is exactly 4 ft, the exporter\'s imperial default, not the modelled height. Measured against that value the guard is about 0.10 m too low. The same railing type is adequate lower down: at +7.40 m (railing over the Big Meeting Room) and along the gallery at +3.70 m (a gallery, so directly within the rule\'s scope) the drop is below 12 m, where Neufert gives 0.90 m, or 1.00 m for workplaces; the 1.00 m railing meets even the workplace value.',
         evidence=['IfcRailing 1PR80QZsPFIAuUfLBR9VbU (…:2531645, Length 40.74 m) and 3huwo$A1DDawqzKsrq0pRo (…:2549713, Length 39.0 m): Base Level "4th Floor", IsExternal true, "Railing Height" 1.00 m, "Height" 1.2192 m; geometry z 14.89–15.80 m.',
                   'Slab "Floor:STB 200:2530111" top +14.80 m; ground slab "Floor:STB 200:2527032" top 0.00 m; 8 "Bank-01" benches and 4 "Pflanztrog" planters stand at +14.80 m (another 8 benches on the +7.40 m terrace).',
                   'Railing 3huwo$A1DDawqzKsrq0pM_ (…:2548893) Base Level "2nd Floor", z 7.49–8.40 m; gallery railings 2534028/2534347 Base Level "1st Floor", z 3.79–4.70 m.',
                   'Original answer #410: storeys 3rd 11.10, 4th 14.80, 5th 18.50 m.'],
         hidden_knowledge='Guards on galleries, mezzanines, balconies (here applied by analogy to a roof terrace), compulsory from 1 m drop; 0.90 m below 12 m (1.00 m for workplaces), 1.10 m above 12 m; 1.2192 m = 4 ft is a software default.',
         basis=[C['guard'], C['guard_low'], C['guard_work'], C['guard_high']],
         rubric=['Drop 14.80 m > 12 m → 1.10 m (balcony rule applied by analogy to the terrace)', 'Reads the real height as 1.00 m (Railing Height / geometry), not 1.219 m', 'Verdict: ≈0.10 m below that value', 'Lower railings (+7.40, +3.70) only need 0.90 m (1.00 m for workplaces) (optional)']),
    dict(project='fantasy_office_building_2', derived_from=[410], question_type='derivation',
         question='The exported storeys are 3.70 m apart (+11.10, +14.80, +18.50 m), and the floor slabs are 200 mm thick. Derive the clear room height of the offices and compare it with the standard ceiling heights for office buildings. Does the room height trigger any extra window requirement for workrooms?',
         answer='Clear height = 3.70 − 0.20 = 3.50 m, which matches the spaces\' Qto Height of 3.50 m. Neufert gives a ceiling height of 2.75 m for office buildings according to the Vst regulation (reducible by 25 cm for predominantly sedentary work, but min. 2.50 m clear; corridors and sanitary rooms are permitted at 2.30 m), so the offices exceed that figure by 0.75 m, room enough for a later raised floor or suspended ceiling, the very reason the 2.75 m is given. The extra rule that workrooms more than 3.5 m high need glazing of at least 30 % of the outside wall area is not triggered, because 3.50 m is not more than 3.5 m. The same 3.70 m rhythm holds below the exported storeys (slabs at 0.00, +3.70 and +7.40 m).',
         evidence=['Storeys: 3rd Floor +11.10, 4th Floor +14.80, 5th Floor +18.50 m.', 'Five IfcSlab "Floor:STB 200" (0.20 m) with tops at 0.00, 3.70, 7.40, 11.10, 14.80 m.',
                   'All office spaces: Qto_SpaceBaseQuantities.Height 3.50 m (e.g. Office 13, 1R_yUA_T1FjvEL3YlI1fnb).'],
         hidden_knowledge='Office ceiling height 2.75 m according to Vst regulation (min 2.50 m clear for predominantly sedentary work, 2.30 m permitted for corridors/sanitary); workrooms > 3.5 m high need ≥ 30 % glazing of the outside wall.',
         basis=[C['office_ceiling'], C['office_sedentary'], C['office_corr'], C['workroom_glass']],
         rubric=['Derives 3.50 m clear height', 'Compares with 2.75 m (+0.75 m)', 'Notes 3.50 m does not exceed 3.5 m → 30 % rule not triggered']),
    dict(project='fantasy_office_building_2', derived_from=[413], question_type='derivation',
         question='The model contains 13 offices (Office 1–13, about 14.6–14.9 m² each), each furnished with one desk. Relate the total area of all modelled spaces to the number of workstations, and judge the result against the typical total space requirement per workstation.',
         answer='The 27 IfcSpaces add up to 716.06 m²; with 13 desks that is 716.06 / 13 ≈ 55.1 m² per workstation. Neufert gives 23–45 m² per workstation in total, so the building is about 10 m² per workstation above even the generous end, and the 4th-floor common rooms and WCs (no spaces modelled) are not yet counted. The offices themselves are small; the surplus lies in the eight 33.8 m² common rooms, the 53.6 m² entrance hall, the 91.1 m² gallery balcony and the 59.9 m² meeting room. With two desks per office (26 workstations) the figure would fall to ≈27.5 m², inside the range.',
         evidence=['27 IfcSpace, Σ Qto NetFloorArea = 716.06 m²; Offices 1–13: 14.625 m² (×9) and 14.925 m² (×4).',
                   '13 IfcFurniture "Schreibtisch-Kombination-01:Typ1", one per office.', 'Common Room 1–8: 33.775 m² each; Entrance Hall 53.585 m²; Gallery Balcony 91.053 m²; Big Meeting Room 59.874 m².',
                   'No IfcSpace at +14.80 m although WC fixtures, kitchenettes and doors exist there.', 'Original answer #413: 13 offices (4 + 3 + 3 + 3 by floor).'],
         hidden_knowledge='Total space requirement per workstation 23–45 m².',
         basis=[C['ws_total']],
         rubric=['Computes ≈55 m² per workstation', 'Compares with 23–45 m² → above range', 'Identifies the common/circulation areas as the surplus (or the two-desk scenario)']),
    dict(project='fantasy_office_building_2', derived_from=[415], question_type='derivation',
         question='Office 13 contains one desk combination and one shelf (Regal-01 1500 × 600 × 2500). Using the standard workstation depth for single-room offices, could the room take a second workstation, and is the movement area at the existing desk adequate?',
         answer='Yes to both. Office 13 is ≈4.98 m wide along the façade and 3.00 m deep. Neufert\'s workstation depth is 2.20 m (80 cm desk, 1 m movement area, 40 cm shelf), and for a single-room office with a double workstation in the 1.50 m module (with a 10 cm wall) this gives 4.40 m clear room space, i.e. two workstations facing the side walls; 4.98 m leaves ≈0.58 m to spare, which is the double-workstation single office Neufert\'s 1.50 m module is built around. Of the 14.93 m², the desk combination takes ≈2.5 m² (1.75 × 1.42 m) and the shelf 0.90 m² (1.50 × 0.60 m), leaving about 11.5 m² unfurnished, far more than the free movement area of at least 1.5 m² that a workstation should have.',
         evidence=['Space 24 "Office 13" (1R_yUA_T1FjvEL3YlI1fnb): NetFloorArea 14.925 m², geometry ≈3.00 × 4.98 m, two façade windows on the 4.98 m side.',
                   'IfcFurniture 3zLgZj6qn7ZfXBVD2gvfbw "Schreibtisch-Kombination-01:Typ1:2589494": ≈1.75 × 1.42 m (geometry).', 'IfcFurniture 3zLgZj6qn7ZfXBVD2gvfbs "Regal-01:1500 x 600 x 2500:2589498": 1.50 × 0.60 m.', 'Original answer #415: the desk combination and the shelf.'],
         hidden_knowledge='1.50 m module for single-room offices with mainly double workstations: workstation depth 2.20 m (desk 0.80 + movement 1.00 + shelf 0.40), with 10 cm wall → 4.40 m clear room space; free movement area of at least 1.5 m² per workstation (should).',
         basis=[C['ws_depth'], C['double_ws'], C['ws_move']],
         rubric=['Uses 2 × 2.20 = 4.40 m vs ≈4.98 m', 'Concludes a second workstation fits', 'Checks the ≥ 1.5 m² movement area (≈11.5 m² free)']),
    # ------------------------------------------------------------------ supplements
    dict(project='fantasy_office_building_2', derived_from=[415], pairing='supplement', question_type='compliance',
         question='Office 13 is lit by two "FE 2 tlg - waagrecht geteilt 1100 x 1850" windows in its façade wall, starting about 0.37 m above the floor. Does the office meet the workplace guidance on visual connection to the outside?',
         answer='Yes. The visual connections must total at least 1/10 of the total width of all walls. The room\'s walls total 2 × (3.00 + 4.98) ≈ 15.96 m, so ≈1.60 m of window width is needed; the two windows give 2 × 1.10 = 2.20 m. They run from ≈0.37 m to ≈2.25 m above the floor, so the view out at eye level that the guidance recommends (it gives sill heights of 0.85–1.25 m as a should) is provided: that band lies within the glazing, even though the sill itself is lower than the quoted sill heights.',
         evidence=['Office 13 geometry ≈3.00 × 4.98 m, floor +11.10 m.', 'IfcWindow 0MHrdAmTX4nBC1_XZqueqy (…:2529992) and 0MHrdAmTX4nBC1_XZqueqz (…:2529993): OverallWidth 1.10 m, geometry z 11.47–13.35 m.'],
         hidden_knowledge='Workplace guidelines: total width of visual connections must be ≥ 1/10 of total wall width; the view out should be at eye level (sill heights 0.85–1.25 m).',
         basis=[C['view_width'], C['view_sill']],
         rubric=['Computes ≈1.60 m required vs 2.20 m provided', 'Checks the eye-level band against the window height range']),
    dict(project='fantasy_office_building_2', derived_from=[413], pairing='supplement', question_type='intent',
         question='Every floor has two common rooms with a kitchenette and an armchair group, and two WC rooms with two toilets each. Measured against the usual provision ratios for 13 workstations, what does this level of provision tell you about the designer\'s intent?',
         answer='By the ratios it is far more than needed: one ~10 m² tea kitchen per 50–100 workplaces and one toilet per 50–80 workstations would mean a single kitchen and a single toilet for 13 desks, whereas the model has 10 kitchenettes and 20 WCs. The kitchens are clearly not sized by headcount. Neufert also asks that tea kitchens be close to the workstations and connected with communication zones, which is what the 33.8 m² common rooms (kitchenette plus 4 armchairs and table on every floor) do: they are meant as per-floor social and meeting zones, and the generous WC provision suggests the building is planned for more occupants than the 13 modelled desks.',
         evidence=['10 IfcFurniture "Küchenzeile-02 Kombination" (Common Rooms 1–8 and two on the +14.80 m level) with 17 "Tisch-Sofa-Kombination-02:4 Sessel und 1 Tisch".',
                   '20 IfcFlowTerminal "WC 03:WC" (2 per WC room, 10 rooms), 10 "Waschbecken m. Griffen barrierefrei", 10 "Waschbecken 05".', '13 "Schreibtisch-Kombination-01" desks; Common Room 33.775 m² each.'],
         hidden_knowledge='One ~10 m² tea kitchen per 50–100 workplaces, close to workstations and linked to communication zones; one toilet per 50–80 workstations.',
         basis=[C['tea_kitchen'], C['office_wc']],
         rubric=['Computes required ≈1 kitchen and ≈1 toilet vs 10 and 20', 'Interprets common rooms as communication zones', 'Infers social intent / higher planned occupancy']),
    dict(project='fantasy_office_building_2', derived_from=[413], pairing='supplement', question_type='compliance',
         question='The Big Meeting Room (59.9 m²) holds a conference table-and-chair set for 16 people. Is the room large enough for that set by the usual area per conference seat, and how many seats could it hold at most?',
         answer='Yes. A conference area needs about 2.5 m² per seat, so 16 seats need ≈40 m², well within 59.9 m². At 2.5 m² per seat the room could take about 59.9 / 2.5 ≈ 23 seats (excluding the subsidiary rooms that Neufert adds on top). An identical 16-seat set stands at +11.10 m in the same position, i.e. a second meeting room on the 3rd floor that has no IfcSpace.',
         evidence=['Space 10 "Big Meeting Room" (3zLgZj6qn7ZfXBVD2gvfY_): NetFloorArea 59.874 m², geometry ≈15.0 × 4.0 m, floor +3.70 m.',
                   'IfcFurniture 3huwo$A1DDawqzKsrq0pwx "Tisch-Stuhl-Kombination-08 Konferenz:2000 x 1000 x 750 - 16 Stühle" at +3.70 m; same type 3huwo$A1DDawqzKsrq0o7W at +11.10 m (same plan position, no IfcSpace).'],
         hidden_knowledge='Conference areas need ≈2.5 m² per seat (without subsidiary areas).',
         basis=[C['conference']],
         rubric=['16 × 2.5 = 40 m² ≤ 59.9 m²', 'Capacity ≈23–24 seats', 'Notes the second set without a space (optional)']),
    dict(project='fantasy_office_building_2', derived_from=[410], pairing='supplement', question_type='diagnosis',
         question='Each 3.70 m storey is served by three kinds of stair: straight cast-in-place flights, cast-in-place spiral stairs, and a steel-and-timber assembled stair with two runs. Which of them could serve as the building\'s legally essential stair by the standard geometric stair rules, and why do the others fail?',
         answer='Only the assembled stair. It climbs in two runs of 10 risers of ≈19.5 cm with ≈24.5 cm treads and landings between: 2r + t ≈ 2 × 19.5 + 24.5 = 63.5 cm (inside 59–65 cm), 10 steps per run (≤ 18) and width 1.00 m (meets the 1.00 m minimum usable width that German standards, as Neufert cites them for residential buildings, set for legally essential stairs; applied here by analogy, since for workplaces the health-and-safety rules govern), although 19.5/24.5 is steeper than 17/28. The straight and spiral cast-in-place stairs take the whole 3.70 m in one run of 19 risers of ≈19.5 cm with 20 cm treads: 19 steps exceed the 18-step maximum per run, there is no landing although the storey height is ≥ 2.75 m, and 2r + t ≈ 58.9 cm is just below 59 cm because the 20 cm tread is very short.',
         evidence=['IfcStair 0WaQTzLw53AhnhP0vcVNHR "Assembled Stair:Stair:2588205" (one per floor): two IfcStairFlight of 10 risers × 0.1952 m, tread 0.2445 m, Actual Run Width 1.00 m; landing slabs "Landing 1/2".',
                   'IfcStair 0GcgtZmYP67vXxQb6KyQhK "Cast-In-Place Stair:2521121" (STRAIGHT_RUN_STAIR) and 2ozJvhRSHCDRvaJs1EcWau "…:2579308" (SPIRAL_STAIR): 19 risers × 0.1947 m, tread 0.200 m, one flight, run height 3.70 m, width 1.00 m.',
                   'Storey height 3.70 m (slabs at 0.00/3.70/7.40/11.10/14.80 m).'],
         hidden_knowledge='Stride 59–65 cm; ≤ 18 steps per run; landing at storey height ≥ 2.75 m; legally essential stairs min. usable width 1.00 m, 17/28 (German standards, residential context, applied by analogy to this office).',
         basis=[C['stride'], C['run_len'], C['landing'], C['essential']],
         rubric=['Assembled stair passes (63.5 cm, 10 steps, landings, 1.00 m)', 'Single-flight stairs fail: 19 > 18 steps and no landing', 'Computes ≈58.9 cm for the 20 cm tread stairs']),
]

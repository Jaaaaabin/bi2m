# x_g1: building physics & environment (daylight, sun/orientation, ventilation, window geometry,
# thermal envelope, acoustics). All items are supplements; each new knowledge point is listed in
# knowledge/x_g1.json.

# --- orientation of dwelling rooms (residential chapter)
C['g1_bed_orient'] = cite('page_0169', 'These would normally be aligned to east or southeast (parents) or south to west (children) and separated from the living room in another part of the home.', 'page_0169_intent_003')
C['g1_dining_orient'] = cite('page_0166', 'Dining areas are normally oriented to the south or west.', 'page_0166_intent_013')
C['g1_kitchen_orient'] = cite('page_0161', 'The location of the kitchen is ideally on the northeast or northwest', 'page_0161_intent_004')
# --- bathroom orientation / ventilation, windowless kitchens
C['g1_bath_north'] = cite('page_0172', 'The bathroom should be oriented to the north, and if possible have natural ventilation and lighting (otherwise provide effective mechanical ventilation according to DIN 18017-3).', 'page_0172_intent_003')
C['g1_kitchen_nowin'] = cite('page_0161', 'Kitchens and kitchenettes without windows are generally undesirable and only permissible if effective ventilation is guaranteed.', 'page_0161_intent_022')
# --- windows (p.97)
C['g1_glass_13'] = cite('page_0109', 'For rooms with dimensions corresponding to those of residential rooms, the minimum height of the glass area is 1.3 m.')
C['g1_workroom_crit'] = cite('page_0109', 'In order to optimise the energy balance, the criteria for workrooms can be applied.')
# --- daylight: view out, depth of the working area
C['g1_width_65'] = cite('page_0507', 'The minimum window width as a percentage, before finishings, should not be less than 65% of the room width.')
C['g1_work_depth'] = cite('page_0278', 'The distance of the working area from the window should be twice as long as the clear window height')
# --- orientation of office / workplace buildings
C['g1_axis_ew'] = cite('page_0253', 'According to Rosenauer, 90% of all office buildings in the USA have a main axis E/W, because the deeply penetrating morning and evening sun is a disturbance.')
C['g1_south_blinds'] = cite('page_0253', 'Sun from the south can be shaded more easily with sun blinds.')
C['g1_axis_ns'] = cite('page_0253', 'According to Joedicke (→ refs), the main axis in the N/S alignment is to ensure sunlight through all rooms.')
C['g1_north_rooms'] = cite('page_0253', 'North-facing rooms are acceptable only for layouts without a corridor.')
C['g1_two_sided'] = cite('page_0278', 'Multi-storey buildings with windows on one side should face northeast, and, with windows on both sides facing north and south, they should be oriented east–west.')
# --- sun shading by compass direction, projection of shading elements
C['g1_shade_dir'] = cite('page_0512', 'On north sides, direct sunshine can only be expected in the mornings in June and July and simple internal systems are sufficient. If the alignment is largely west or east, movable systems should shade the low sun.')
C['g1_shade_south'] = cite('page_0512', 'South windows need effective shading above all in the early year and autumn, with low sun. In the high summer, slight roof overhangs are sufficient to avoid direct sunshine.')
C['g1_shadow_angles'] = cite('page_0512', "21 June (summer solstice), midday \\( \\alpha' = 63^\\circ, \\alpha = 27^\\circ \\); 1 May and 31 July, midday \\( \\alpha' = 50^\\circ, \\alpha = 40^\\circ \\); 21 March and 21 September (equinoxes) midday \\( \\alpha' = 40^\\circ, \\alpha = 50^\\circ \\).")
C['g1_projection'] = cite('page_0512', 'Projection A = tan shadow angle \\( \\alpha \times \\) window height H;')
C['g1_projection_min'] = cite('page_0512', 'but min. projection A = (tan shadow angle \\( \\alpha \times \\) window height H) – wall thickness D')
# --- thermal envelope
C['g1_av'] = cite('page_0486', 'Depending on the ratio of heat-transmitting area A to heated building volumes V_e (A/V_e ratio), the maximum permissible annual primary energy demand will be determined according to EnEV 2007, according to the envelope area process.')
# --- acoustics
C['g1_party_400'] = cite('page_0490', 'for this reason, party walls between flats or houses should always weigh at least 400 kg/m².')
C['g1_party_2skin'] = cite('page_0491', 'The mass per unit area of the individual layers with plaster must be at least 150 kg/m^2, and the thickness of the separating joint must be at least 30 mm. With a thickness of the separating joint (layer spacing) of more than 50 mm, the mass of each skin can be 100 kg/m^2. The joint cavity is to be filled with gapless full-surface fibre insulating boards')
C['g1_vol_person'] = cite('page_0495', 'Guideline values are 4 m³/person for speech and 10 m³/person for (concert) music. If the volume is too small, this allows too little reverberation.')
C['g1_services_noise'] = cite('page_0492', 'Noisy elements of services (water pipes, waste pipes, gas riser pipes, waste disposal units, lifts) may not be installed in the walls of rooms where quiet is required (living rooms, bedrooms).')
C['g1_lift_shaft'] = cite('page_0493', 'Lifts should be installed in separate shafts (joints filled with >3 cm mineral fibre)')

ITEMS += [
    # ------------------------------------------------------------------ fzk_house
    dict(project='fzk_house', derived_from=[], pairing='supplement', question_type='diagnosis',
         question='The model\'s true north is not project +Y: the context\'s TrueNorth is (0.766, 0.643) in plan coordinates. Using the window positions, which compass directions do the kitchen, the bedroom and the bathroom face, and how well does the ground-floor layout follow the usual orientation of these rooms in a house?',
         answer='Rotating the plan by the TrueNorth vector, the +X façade faces about 40° (NE), −Y about 130° (SE), −X about 220° (SW) and +Y about 310° (NW). The bathroom (Bad) has its only window in the NW façade, so it lies on the north side as recommended. The kitchen (Küche) is the opposite of the recommendation: its two windows face SW and SE, i.e. it occupies the south corner, whereas a kitchen is ideally on the northeast or northwest side. The bedroom (Schlafzimmer) has windows to NE and NW, i.e. the north corner; a parents\' bedroom is normally aligned east to southeast, so it gets only some early-morning summer sun through the NE window. The living room (Wohnen, windows SE and NE, terrace door SE) takes the east corner, which is fine. In effect kitchen and bedroom sit in each other\'s usual corners; the south-corner kitchen (16.3 m²) would only make sense if it is used mainly as the dining room, since dining areas are normally oriented south or west.',
         evidence=['IfcGeometricRepresentationContext (Model/Plan) TrueNorth DirectionRatios (0.766044, 0.642788) → project +X ≈ 40°, −Y ≈ 130°, −X ≈ 220°, +Y ≈ 310° (clockwise from north).',
                   'Küche (17JZcMFrf5tOftUTidA0d3, x 0.30–4.70, y 0.30–4.01): EG-Fenster-7 (0B1RwEzzP3CfME5NR$Vqh5) in the −X wall and EG-Fenster-4 (25nJxEpYf8LRDJNkMUVO0m) in the −Y wall.',
                   'Schlafzimmer (347jFE2yX7IhCEIALmupEH, x 7.65–11.70, y 4.25–9.70): EG-Fenster-8 (13aSY79zb8fP4HApEJ0z_e) in the +X wall, EG-Fenster-3 (1DiYqhfzH9xxuJdVHwXCNa) in the +Y wall.',
                   'Bad (0e_hbkIQ5DMQlIJ$2V3j_m): EG-Fenster-2 (2Q9w7oRXP249jBobEMVqlZ) in the +Y wall only.',
                   'Wohnen: EG-Fenster-5 (−Y wall), EG-Fenster-9 (+X wall), Terrassentuer at x 5.0–7.0 in the −Y wall.'],
         hidden_knowledge='Dwelling rooms: kitchen ideally NE or NW, parents\' bedroom normally E–SE (children S–W), dining normally S or W, bathroom should face north; orientation must be read through IFC TrueNorth.',
         basis=[C['g1_kitchen_orient'], C['g1_bed_orient'], C['g1_dining_orient'], C['g1_bath_north']],
         rubric=['Converts the facades with TrueNorth (≈40/130/220/310°)', 'Bathroom on the NW (north) side: complies', 'Kitchen in the S corner (SW+SE): contradicts NE/NW', 'Bedroom NE/NW instead of E/SE; notes kitchen and bedroom are effectively swapped (optional)']),

    dict(project='fzk_house', derived_from=[], pairing='supplement', question_type='compliance',
         question='The home office "Buero" (12.6 m²) is lit by two "IFC Fenster - zwei Panele - Vertikal" windows, structural opening 2.00 × 1.20 m, sill 0.80 m, with 7 cm linings and 5 cm sash frames. Treating the Buero as a workroom of ordinary room size, are the windows tall enough?',
         answer='No. Neufert\'s window rules for workrooms give a minimum glass height of 1.3 m for rooms with the dimensions of residential rooms, which is what the Buero is. The structural opening is only 1.20 m high; after the 7 cm lining and 5 cm sash frame top and bottom the glass is only about 1.20 − 2 × (0.07 + 0.05) ≈ 0.96 m high, about 0.34 m short. Even the raw opening would miss 1.3 m by 0.10 m. With the window head at 2.00 m and the ceiling at 2.50 m there is room to fix this: an opening of about 1.55 m (e.g. 0.80–2.35 m) would give 1.3 m of glass. The 0.80 m sill is also 5 cm below the 0.85–1.25 m band in which a workroom\'s view out should lie (eye level), a recommendation rather than a hard limit.',
         evidence=['Buero (2RSCzLOBz4FAK$_wE8VckM): NetFloorArea 12.595 m², clear height 2.50 m.',
                   'EG-Fenster-1 (1TAI4ouKX4Xx4lBDZIu5qM) and EG-Fenster-6 (1srAI$R4T8ihLXSNHmUSET): OverallWidth 2.00 m, OverallHeight 1.20 m; ArchiCAD Brüstungshöhe 0.80 m, Sturzhöhe 2.00 m.',
                   'IfcWindowLiningProperties LiningThickness 0.07 m; IfcWindowPanelProperties FrameThickness 0.05 m (two side-hung panels).'],
         hidden_knowledge='Workrooms of residential-room size: glass area at least 1.3 m high; the view out should be at eye level (sills 0.85–1.25 m).',
         basis=[C['g1_glass_13'], C['g1_workroom_crit'], cite('page_0109', 'Possible visual connection to the outside should be at eye level (window sill heights of 0.85 –1.25 m)')],
         rubric=['States the 1.3 m minimum glass height for workrooms of residential-room size', 'Derives ≈0.96 m glass height (or at least notes 1.20 m < 1.3 m)', 'Verdict: not compliant', 'Notes a taller opening fits below the 2.50 m ceiling or that the 0.80 m sill is just below the recommended eye-level band (optional)']),

    dict(project='fzk_house', derived_from=[], pairing='supplement', question_type='derivation',
         question='The house is a 12.0 × 10.0 m box on a 0.20 m base slab, with 0.30 m external walls rising to +3.37 m at the eaves and a symmetrical 30° gable roof over the 10 m span; the attic Galerie is heated. Which single geometric ratio of the whole building does the energy-saving regulation use to set its permissible annual primary energy demand, and what is its value here?',
         answer='The ratio of heat-transmitting envelope area A to heated building volume Ve (A/Ve). Using external dimensions from the underside of the base slab (−0.20 m): the roof rises 5.0 × tan 30° ≈ 2.89 m from eaves (+3.37 m) to ridge (≈ +6.26 m). Volume Ve ≈ 12 × 10 × 3.57 + ½ × 10 × 2.89 × 12 ≈ 428 + 173 ≈ 602 m³. Envelope A ≈ base slab 120 m² + eaves walls 2 × 12 × 3.57 ≈ 86 m² + gable walls 2 × (10 × 3.57 + ½ × 10 × 2.89) ≈ 100 m² + roof 2 × 12 × 5.77 ≈ 139 m², i.e. ≈ 445 m². A/Ve ≈ 445 / 602 ≈ 0.74 m⁻¹. This is a high value, typical of a small detached house: every cubic metre of heated volume has a lot of envelope, so the envelope-area method allows it a correspondingly higher specific demand, but its heat losses per m³ are large; a more compact form would lower the ratio.',
         evidence=['Bodenplatte (1pPHnf7cXCpPsNEnQf8_6B): 12.0 × 10.0 m, GrossArea 120 m², z −0.20 to 0.00 m.',
                   'External walls Wand-Ext-ERDG-1…4 / Wand-Ext-OG-2, -4: 0.30 m Leichtbeton on the 0–12 × 0–10 m outline; eaves walls top at +3.37 m; gable walls Wand-Ext-OG-1, -3 up to +6.09 m.',
                   'Roof slabs Dach-1, Dach-2 (0.20 m), pitch 30°, ridge along y = 5.0 m; ridge beam "First" top +6.09 m, roof slab top at ridge +6.32 m.',
                   'Galerie (attic, 107.16 m² gross) is a habitable space inside the envelope.'],
         hidden_knowledge='EnEV sets the maximum annual primary energy demand as a function of the A/Ve ratio (envelope area / heated volume).',
         basis=[C['g1_av']],
         rubric=['Names the A/Ve ratio as the governing parameter', 'Volume ≈ 600 m³ and envelope ≈ 440–450 m² with stated assumptions', 'A/Ve ≈ 0.74 m⁻¹ (±0.05)', 'Interprets the high ratio as a non-compact building (optional)']),



    # ------------------------------------------------------------------ fantasy_residential_building_1
    dict(project='fantasy_residential_building_1', derived_from=[], pairing='supplement', question_type='compliance',
         question='Each flat has a bathroom (13.37 m², walk-in shower and basins) at one end and a separate toilet (4.33 m², wall-hung WC and basin) at the other. Check both kinds of sanitary room against the usual design guidance on their orientation, daylight and ventilation (true north is project +Y). Which comply, and what should be added?',
         answer='The bathrooms comply. Each has one "Single-leaf Turn-Tilt window with Sublight" (1.22 × 1.55 m, sill ≈0.76 m) in the +Y façade, i.e. facing north, so the bathroom is oriented to the north and has natural light and natural ventilation, as recommended. The toilets do not: they have no window at all, because they sit at the south (entrance) end of the flat next to the wardrobe, so they get neither daylight nor natural ventilation. Applying the bathroom guidance to these separate WCs by analogy (natural light and ventilation where possible, otherwise effective mechanical ventilation), they must be given effective mechanical ventilation instead. Placing the toilet against the north façade as well (or giving it a window in an external wall) would avoid this; as planned, the layout trades the toilet\'s daylight for its position near the flat entrance.',
         evidence=['Geometric context TrueNorth (0, 1) → +Y = north.',
                   'Bathroom spaces 9 / 18 (13.37 m², y 7.98–10.45) on each floor; windows 0eNSff11H9VhE9adIdTgas, 0eNSff11H9VhE9adIdTgar (GF), 0RgKgXPa5AqeGvHba2KWCl, 0RgKgXPa5AqeGvHba2KW3$ (FF), 01fbTcJgz1b8Z$wgfmHMhW, 01fbTcJgz1b8Z$wgfmHMhd (SF): type "Windows_Opening-Hinge_S9000_Single-leaf-Turn-Tilt-window-with-Sublight", 1.22 × 1.55 m, at y ≈ 10.4–10.8 (north façade).',
                   'Toilet spaces 4 / 13 (4.33 m², y −17.35 to −15.60): no IfcWindow; wall-hung WC and basin proxies.'],
         hidden_knowledge='Bathrooms should face north and if possible have natural light/ventilation, otherwise effective mechanical ventilation (DIN 18017-3); applied by analogy to the separate WC.',
         basis=[C['g1_bath_north']],
         rubric=['Bathroom windows face north → orientation and natural light/ventilation comply', 'Toilets have no window (south entrance end) → no daylight/natural ventilation', 'Concludes (by analogy with the bathroom rule) the toilets need effective mechanical ventilation (or a window on an external wall)']),

    dict(project='fantasy_residential_building_1', derived_from=[], pairing='supplement', question_type='intent',
         question='The lift of each half of the building (door type "TU SF 2 - Lift Zentral") stands inside the stairwell at the south end, and the flats are arranged wardrobe/toilet – kitchen-dining – living room – bedroom – bathroom from south to north. In the bathrooms the shower, basins and taps are all fixed to the north external wall. Explain what this arrangement achieves acoustically.',
         answer='It keeps noisy building services away from the quiet rooms. Lifts, water and waste pipes may not be installed in the walls of rooms that need quiet, such as living rooms and bedrooms. Here the lift doors (around y −20.5 to −19.1) are inside Stairwell 1/2 (y −22.1 to −17.5), and the flat is entered through the wardrobe and toilet zone (y −17.35 to −13.08). The nearest living room starts about 13 m further north (y −5.75) and the bedroom about 20 m away (y 1.23), so no lift-shaft wall touches a quiet room. In the bathrooms the plumbing sits on the north external wall (y ≈ 10.45), not on the partition shared with the bedroom (y ≈ 7.9), so supply and waste pipes do not run in a bedroom wall. The model does not show a separate lift shaft or its acoustic joint (Neufert asks for separate shafts with >3 cm mineral-fibre joints), so that part cannot be verified.',
         evidence=['Lift doors 3yt5iHkuT7cwFfSmaBrXHK (x −10.02 to −9.50, y −20.52 to −19.11) and 3yt5iHkuT7cwFfSmaBrWe6 (x 3.47–3.99): "TU SF 2 - Lift Zentral:DL - 705 x 2100", in Stairwell 1 (x −12.71 to −7.31, y −22.10 to −17.50) and Stairwell 2.',
                   'West ground-floor flat: Wardrobe y −17.35 to −13.08, Toilet −17.35 to −15.60, Kitchen and Dining −12.93 to −5.75, Living room −5.75 to 1.08, Bedroom 1.23–7.83, Bathroom 7.98–10.45.',
                   'Bathroom fittings: basin (y 9.94–10.45), faucets (y 10.28–10.47), shower set (y 10.07–10.53) on the north wall; no fittings on the bedroom partition.',
                   'No IfcTransportElement or lift-shaft space in the model.'],
         hidden_knowledge='Noisy services (lifts, water and waste pipes) must not be built into walls of living rooms and bedrooms; lifts in separate shafts with mineral-fibre joints.',
         basis=[C['g1_services_noise'], C['g1_lift_shaft']],
         rubric=['Identifies the acoustic intent (noisy services away from quiet rooms)', 'Uses positions: lift in stairwell, buffer zone, living/bedroom far away', 'Notes plumbing on the external wall, not the bedroom wall', 'Notes the separate shaft/joint cannot be verified (optional)']),

    # ------------------------------------------------------------------ ac20
    dict(project='ac20', derived_from=[], pairing='supplement', question_type='intent',
         question='This office building (true north = project +Y) is a slab about 42 m long and 12 m deep with a central corridor; 198 of its 206 windows are in the two long façades, roughly half facing north and half facing south. Why is this a defensible orientation for an office building, what argument from standard office design guidance speaks against it, and what sun protection does each long façade need?',
         answer='The long axis runs east–west. Neufert notes that orientation is variously judged: according to Rosenauer, 90 % of office buildings in the USA have an E/W main axis because deep-reaching morning and evening sun is a disturbance, while sun from the south is easier to shade with blinds; and the book\'s industrial-building chapter says multi-storey buildings with windows on both sides facing north and south should be oriented east–west. The counter-argument (Joedicke) is that a north–south main axis lets sunlight reach every room, and that north-facing rooms are acceptable only in layouts without a corridor. ac20 has exactly such a corridor layout (Flur EG Ost/West between the two rows), so the north row of offices (Buero Maier, Meyer, Mayer, Meyr, Mayr, Obermeier, Studenten III …) never gets direct sun. Sun protection: on the north façade, direct sun comes only on June/July mornings, so simple internal blinds are enough. The south façade needs effective, preferably external, shading mainly in spring and autumn when the sun is low; in high summer a slight overhang would do.',
         evidence=['IfcGeometricRepresentationContext TrueNorth (0, 1).',
                   'Room extent x 0.3–41.7 m; south rooms y 2.3–6.7, corridor (Flur EG Ost/West) y 7.0–9.0, north rooms y 9.3–13.7.',
                   'Windows: 102 in the south façade (Fenster-002 ×88, -003 ×12, -012, -013), 96 in the north façade (Fenster-004 ×48, -005 ×48), 8 in the east/west ends.',
                   'North-row rooms on Erdgeschoss: Buero Maier, Meyer, Mayer, Meyr, Mayr, Obermeier, Studenten III, WC Damen, WC Herren.'],
         hidden_knowledge='Office orientation is disputed: Rosenauer (90 % of US office buildings E/W axis; morning/evening sun disturbing, south sun easy to shade) vs Joedicke (N/S axis for sun in all rooms; north rooms only without corridor); industrial chapter: N+S windows → E–W orientation; shading by compass direction.',
         basis=[C['g1_axis_ew'], C['g1_south_blinds'], C['g1_two_sided'], C['g1_axis_ns'], C['g1_north_rooms'], C['g1_shade_dir'], C['g1_shade_south']],
         rubric=['Reads the E–W main axis with N/S façades from TrueNorth', 'Justifies it (Rosenauer: low morning/evening sun disturbing, south easy to shade; N+S windows → E–W)', 'Gives the counter-argument (Joedicke): north rooms acceptable only without a corridor, so the north row here gets no sun', 'North: simple internal shading; south: effective shading for low spring/autumn sun']),

    dict(project='ac20', derived_from=[], pairing='supplement', question_type='derivation',
         question='The basement Besprechungsraum I (23.90 m²) and Besprechungsraum II (24.75 m²) are each furnished with 16 stools, the Seminarraum (128.27 m²) with 22; all three have a 2.70 m ceiling. Judge the room volumes per person for speech use, and say which room is at risk of too little and which of too much reverberation.',
         answer='Speech rooms need about 4 m³ per person; too small a volume gives too little reverberation. Besprechungsraum I: 23.90 × 2.70 ≈ 64.5 m³ / 16 ≈ 4.0 m³ per person, exactly at the guideline. Besprechungsraum II: 66.8 m³ / 16 ≈ 4.2 m³. Both are acceptable, but neither could seat more people. Seminarraum: 128.27 × 2.70 ≈ 346 m³ / 22 ≈ 15.7 m³ per person, almost four times the speech value and above even the 10 m³ per person given for concert music, so the risk is too much reverberation, not too little. Volume-wise the Seminarraum would suit about 128.27 × 2.70 / 4 ≈ 87 people for speech; with only 22 seats it has far more volume than its occupancy needs, so either the room is planned for a much larger audience or its volume is out of proportion for speech.',
         evidence=['001 Besprechungsraum I: NetFloorArea 23.901 m², FinishCeilingHeight 2.70 m; 16 × Kubus-Einrichtung-2 (0.30 × 0.30 × 0.50 m stools), 6 × Kubus-Einrichtung-1 tables.',
                   '002 Besprechungsraum II: 24.754 m², 2.70 m; 16 stools.',
                   '006 Seminarraum: 128.273 m², 2.70 m; 22 stools, 10 tables.'],
         hidden_knowledge='Room volume per person: ≈4 m³/person for speech, 10 m³/person for (concert) music; too small a volume gives too little reverberation.',
         basis=[C['g1_vol_person']],
         rubric=['Computes ≈4.0 and ≈4.2 m³/person for the meeting rooms and judges them just adequate (no spare capacity)', 'Computes ≈15.7 m³/person for the Seminarraum, above even the 10 m³/person music value', 'Concludes: meeting rooms at the lower limit, Seminarraum at risk of too much reverberation (≈87 people would match 4 m³/person)']),

    # ------------------------------------------------------------------ fantasy_office_building_2
    dict(project='fantasy_office_building_2', derived_from=[], pairing='supplement', question_type='diagnosis',
         question='All thirteen offices (Office 1–13, about 3.0 m deep) have their two "FE 2 tlg - waagrecht geteilt 1100 x 1850" windows in the same façade, while the common rooms have French windows in another. Taking the model\'s true north at face value, which way do the offices face, and what does the usual design guidance on office orientation and sun protection imply for them?',
         answer='The offices face west: their windows sit in the façade at x ≈ 13.2–13.5 m, the −X side, and TrueNorth is +Y. The building\'s long axis runs north–south (spaces span ≈ 20 × 36 m), the arrangement Joedicke favours because it brings sun into all rooms. But for offices it brings exactly the deep-reaching low evening sun that, according to Rosenauer, is the reason 90 % of US office buildings have an east–west axis. On a largely west (or east) façade the low sun should be shaded with movable systems such as external blinds or louvres. The windows run from 0.37 m above the floor with 1.66 m of clear height, so the low afternoon sun reaches deep into the 3 m rooms and the desks. Only the common rooms\' French windows face south, where shading is easier.',
         evidence=['TrueNorth (≈0, 1) → +Y north.',
                   '26 windows "FE 2 tlg - waagrecht geteilt:1100 x 1850" at x 13.23–13.51 (façade facing −X), two per Office 1–13 (e.g. Office 1: 0GcgtZmYP67vXxQb6KyQ4k, 0GcgtZmYP67vXxQb6KyQRy); sill ≈0.37 m, head ≈2.25 m; Rahmenlichte Höhe 1.66 m; Isolierverglasung 3-fach.',
                   'Offices x 13.51–16.51 (3.0 m deep); building spaces x 13.5–33.3, y 5.7–41.5 m.',
                   '20 French windows "FE TÜR 2 tlg - DrehKipp mit Stulp:2000 x 2250" face −Y (south), serving Common Rooms.'],
         hidden_knowledge='Rosenauer: morning/evening sun is disturbing in offices (hence 90 % of US office buildings have an E–W main axis); Joedicke: N–S axis gives sun to all rooms; on west/east façades movable systems should shade the low sun.',
         basis=[C['g1_axis_ew'], C['g1_axis_ns'], C['g1_shade_dir']],
         rubric=['Determines that the offices face west', 'Links west orientation to disturbing low evening sun (reason for E–W axes)', 'Recommends movable (external) shading for the west façade', 'Mentions the N–S axis / sun-in-all-rooms argument or the low sill (optional)']),

    dict(project='fantasy_office_building_2', derived_from=[], pairing='supplement', question_type='compliance',
         question='Office 1 (14.6 m²) is about 3.0 m deep and 4.88 m wide along its façade, and has two windows with a structural width of 1.10 m each (clear frame width 0.92 m). Is the total window width enough for the occupant\'s view out?',
         answer='No. The window width, measured before finishings, should be at least 65 % of the room width. 0.65 × 4.88 ≈ 3.17 m would be needed; the two windows give 2 × 1.10 = 2.20 m, i.e. about 45 % (≈38 % on the clear frame width of 2 × 0.92 m). About 1 m of window width is missing. The shallow 3 m room depth helps the daylight but does not replace the missing width for the view out; a third window or wider units would be needed.',
         evidence=['Office 1 (1QIaKYlmj5M8nldkqeS3Wz): NetFloorArea 14.625 m², bounding box 3.0 × 4.88 × 3.5 m (façade side 4.88 m).',
                   'Windows 0GcgtZmYP67vXxQb6KyQ4k and 0GcgtZmYP67vXxQb6KyQRy, "FE 2 tlg - waagrecht geteilt:1100 x 1850", each 1.10 m wide; Rahmenlichte Breite 0.92 m.'],
         hidden_knowledge='View out (DIN 5034 as reported by Neufert): window width before finishings ≥ 65 % of room width.',
         basis=[C['g1_width_65']],
         rubric=['States the 65 % of room width criterion', 'Computes 2.20 / 4.88 ≈ 45 % (needed ≈3.17 m)', 'Verdict: not compliant']),

    # ------------------------------------------------------------------ digital_hub
    dict(project='digital_hub', derived_from=[], pairing='supplement', question_type='derivation',
         question='Gruppenbüro 8 on E01 (37.0 m², 6.85 m wide, 5.40 m deep) is lit only by one north-facing "FE 3 tlg - DK-Fix im Rahmen-DK-2:6000 x 1500" window: sill 0.95 m and head 2.45 m above the E01 level, clear frame height 1.31 m. What distance of the working area from the window does the usual lighting guideline for side-lit workrooms give for this window, and how much of the room lies beyond that distance?',
         answer='The guideline (given in the book\'s industrial-buildings chapter) is that the distance of the working area from the window should be about twice the clear window height: 2 × 1.31 m ≈ 2.6 m (≈2.9 m if the 1.45 m structural opening height is used). Reading this as the depth the window serves well, a 5.40 m deep room leaves the rear ≈2.8 m (≈2.5 m) beyond it, i.e. about 6.85 × 2.8 ≈ 19 m², roughly half of the 37 m² floor. The room is well within the ≈7 m depth up to which daylight can generally be used, but desks should be placed in the front half, or the window head raised towards the ≈3.5 m ceiling, to light the full depth (a clear height of about 2.7 m would be needed).',
         evidence=['Gruppenbüro 8 (space 2-5): NetFloorArea 36.99 m², bounding box 6.85 × 5.40 × 3.5 m.',
                   'Window 03iwAedpj2TfaeVhYaw$xW, "FE 3 tlg - DK-Fix im Rahmen-DK-2:6000 x 1500", in the +Y (north) façade: Rohbauhöhe 1.50 m, AL Höhe 1.45 m, Rahmenlichte Höhe 1.31 m, Schwelle/Brüstung 0.95 m, Sturzhöhe 2.45 m; Glasflaeche 6.75 m².',
                   'TrueNorth (0, 1).'],
         hidden_knowledge='Industrial-building lighting guideline: distance of the working area from the window should be twice the clear window height; office chapter: daylight is mostly usable to about 7 m room depth.',
         basis=[C['g1_work_depth'], cite('page_0253', 'Daylight can mostly be exploited into a room depth of about 7.00 m.')],
         rubric=['Applies the guideline distance of 2 × clear window height (≈2.6 m)', 'Finds ≈2.8 m (≈half the room) beyond that distance', 'Suggests desk placement or a taller window (optional)']),

    dict(project='digital_hub', derived_from=[], pairing='supplement', question_type='derivation',
         question='Gruppenbüro 15 on E01 has a 6.0 m wide "DK-Fix" window in the south façade (structural height 1.50 m) in a 0.25 m wall with 0.16 m external build-up; the site lies at about 48° N. How deep a fixed horizontal projection above the window would keep out the midday sun on 21 June, on 1 May/31 July and at the equinoxes, and what does the result say about the shading the south offices need?',
         answer='Projection A = tan(shadow angle α) × window height H, reduced by the wall thickness D that already shades: A_min = tan α × H − D. With H = 1.50 m and D ≈ 0.41 m: 21 June (α = 27°): 0.51 × 1.50 ≈ 0.76 m, minus 0.41 ≈ 0.35 m. 1 May / 31 July (α = 40°): 0.84 × 1.50 ≈ 1.26 m, minus 0.41 ≈ 0.85 m. Equinoxes (α = 50°): 1.19 × 1.50 ≈ 1.79 m, minus 0.41 ≈ 1.38 m. A small fixed overhang (≈0.4–0.8 m) is enough in high summer, but the low spring and autumn sun would need an overhang of almost 1.4 m. As Neufert notes, south windows need effective shading above all in spring and autumn, so the south offices need movable external shading (e.g. blinds) rather than relying on a fixed projection.',
         evidence=['Window 03iwAedpj2TfaeVhYaw$eR (Gruppenbüro 15, space 2-19), "FE 3 tlg - DK-Fix im Rahmen-DK-2:6000 x 1500" in the −Y (south) façade: Rohbauhöhe 1.50 m, Wandstärke 0.25 m, Wandaufbau Aussen 0.16 m; Gesamtenergiedurchlassgrad 0.41.',
                   'TrueNorth (0, 1); IfcSite RefLatitude 48° 8′ N.'],
         hidden_knowledge='Shading projection A = tan α × H (min. tan α × H − D); midday shadow angles for a south wall below 50° N: 27° (21 June), 40° (1 May/31 July), 50° (equinoxes); south windows need shading mainly for low spring/autumn sun.',
         basis=[C['g1_projection'], C['g1_projection_min'], C['g1_shadow_angles'], C['g1_shade_south']],
         rubric=['Uses A = tan α × H (and subtracts D)', 'Values ≈0.35 / 0.85 / 1.38 m (or ≈0.76 / 1.26 / 1.79 m without D)', 'Concludes fixed overhang suffices only in summer; movable shading needed for spring/autumn']),

    dict(project='digital_hub', derived_from=[], pairing='supplement', question_type='compliance',
         question='Konferenzraum 1 on E01 (21.9 m², 5.40 m deep, 4.05 m along the façade) has a single window, "FE 1 tlg - DrehKipp:2000 x 1500", 2.0 m wide, in the west façade. Does it give enough view out, and how wide would the window have to be?',
         answer='No. The window width, measured before finishings, should be at least 65 % of the room width: 0.65 × 4.05 ≈ 2.63 m, but the window is 2.0 m wide, ≈49 %, so about 0.63 m of width is missing. A window of at least ≈2.65 m (or a second unit) would be needed along the 4.05 m façade. Konferenzraum 2 (3.94 m façade, same 2.0 m window, ≈51 %, needs ≈2.56 m) has the same shortfall.',
         evidence=['Konferenzraum 1 (space 2-3): NetFloorArea 21.87 m², bounding box 5.40 × 4.05 × 3.5 m (x 7.12–12.53, y 16.87–20.92).',
                   'Window 0mm00kOGjAr9AVy6ECzdYH "FE 1 tlg - DrehKipp:2000 x 1500" at x 6.85–7.12, y 17.17–19.17 (west façade); Teiligkeit "einteilig"; Rahmenlichte Höhe 1.31 m.',
                   'Konferenzraum 2: 3.94 m façade, window 3m8kFc6d50JBEsXmSlfXeP (same type).'],
         hidden_knowledge='View out: window width before finishings ≥ 65 % of room width.',
         basis=[C['g1_width_65']],
         rubric=['Computes 2.0 / 4.05 ≈ 49 % < 65 % (needs ≈2.63 m)', 'Verdict: view-out not compliant', 'Notes Konferenzraum 2 has the same shortfall (≈51 %, optional)']),

    # ------------------------------------------------------------------ fantasy_hotel_1
    dict(project='fantasy_hotel_1', derived_from=[], pairing='supplement', question_type='diagnosis',
         question='Ground-floor MASTER BEDROOM 107 (≈3.73 × 6.0 m) is lit by four "Windows_Sgl_Plain:910x910mm" units in its 6.0 m west wall, sill 1.20 m, head 2.11 m. What is wrong with these windows by the usual window design guidance? Consider the glass height and the total window width.',
         answer='Both fall short. Height: each window is only 0.91 m high overall, so the glass is less than 0.91 m high. Neufert\'s workroom rules give a minimum glass height of 1.3 m for rooms of residential size, and the book notes that the workroom criteria can also be applied to dwellings (applied here by analogy); with the head at 2.11 m this would need a sill near 0.8 m instead of 1.20 m. Width: 4 × 0.91 = 3.64 m against 0.65 × 6.0 = 3.90 m, i.e. about 61 %, just under the 65 % of room width wanted for a view out.',
         evidence=['MASTER BEDROOM 107 (0MyMB1s_P4Zh6OoNQiQeMZ): bounding box x −15.96 to −12.23, y −7.04 to −1.04 (3.73 × 6.0 m), height 3.05 m.',
                   'Windows 3fgrIy5C52Nh3glL4d4CzJ, 3fgrIy5C52Nh3glL4d4C_z, 3fgrIy5C52Nh3glL4d4CyH, 3fgrIy5C52Nh3glL4d4Cp7: "Windows_Sgl_Plain:910x910mm", 0.91 × 0.91 m, z 1.20–2.11 m, in the west wall (x ≈ −16.2).',
                   'Pset_WindowCommon IsExternal true.'],
         hidden_knowledge='Workroom rule: glass at least 1.3 m high in rooms of residential size (the book says workroom criteria can be applied to dwellings); window width ≥ 65 % of room width.',
         basis=[C['g1_glass_13'], C['g1_workroom_crit'], C['g1_width_65']],
         rubric=['Glass height < 0.91 m vs 1.3 m', 'Notes a lower sill (≈0.8 m with the 2.11 m head) would be needed', 'Width 3.64 m ≈61 % vs 65 % (3.90 m)']),
]

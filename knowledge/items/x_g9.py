# x_g9 — expansion group 9: missing early-design topics.
# New knowledge points: landing width >= stair width (stair cores); DIN 277 built volumes
# (gross built volume per storey height, net built volume = net floor area x clear height).
# Candidate topics evaluated but not added (no verbatim rule or no testable model): fire brigade
# access/rescue areas, full-storey definition, storey-height build-up, basement habitable rooms /
# light wells, human circulation widths, entrances/canopies, high-rise fire service lift (> 30 m).
# All items are supplements (pairing='supplement').

C['g9_landing_width'] = cite('page_0133', 'Landing width \\( \\geq \\) stair width.')
C['g9_gross_volume'] = cite('page_0075', 'The gross built volume is the sum of the floor areas of all levels multiplied by the relevant height (measured between top of floor covering and top of floor covering of the next level')
C['g9_net_volume'] = cite('page_0075', 'The net built volume is the net floor area multiplied by the relevant clear ceiling height.')

ITEMS += [
    # ------------------------------------------------------------ landing width vs. flight width
    dict(project='digital_hub', derived_from=[], pairing='supplement', question_type='diagnosis',
         question='The two precast half-turn stairs on the ground floor of the DigitalHub (Fertigbetontreppe:Treppe:2421059 in the west '
                  'stairwell and :2423903 in the east stairwell, E00_OKRD to E01_OKRD) each have two straight runs and one intermediate '
                  'landing slab. Judging from the model geometry, is the intermediate landing adequately sized for these flights? '
                  'Compare with the assembled half-turn stair Zusammengebaute Treppe:Treppe:2424673 on the same floor.',
         answer='Yes, by the rules the book states. Landings are mandatory here, since the storey height is 3.90 m '
                '(E00 −0.15 m to E01 +3.75 m, 22 risers × 0.177 m), i.e. ≥2.75 m. The book\'s caption asks only that the landing width be '
                '≥ the stair width: the landing slab spans 2.80 m across both runs (each ≈1.30 m wide, geometry bounding box, together '
                'x 14.13–16.93 m), so it is wider than either flight. The landing-length rule (n × stride + 1 tread = '
                '2 × 0.177 + 0.27 = 0.624 m stride, + 0.27 = ≈0.89 m for n = 1) is also met by the ≈1.24 m depth (bbox 2.80 × 1.24 m). '
                'What the model does show is that this depth in the direction of travel is ≈6 cm less than the flight width (and smaller '
                'still if the ≈0.12 m by which the run bounding boxes reach into the landing were taken off). The caption does not '
                'say that the depth must equal the flight width, so this is not a breach of the stated rule; reading "width" as that '
                'depth would be an interpretation beyond the text. The assembled stair :2424673 (runs ≈1.30 m, landing ≈1.33 m deep, bbox '
                '1.33 × 2.80 m) is the more generous design.',
         evidence=['IfcStair Fertigbetontreppe:Treppe:2421059 (0YVU7tDBX86u6UVVsSmdwD) and :2423903 (3LF03GdXv2GhSTK1xTZzXh), HALF_TURN_STAIR, '
                   'storey E00_OKRD, 22 risers, RiserHeight 0.177 m, TreadLength 0.27 m',
                   'IfcStairFlight Run 1 / Run 2 geometry bbox width 1.30 m (e.g. x 14.13–15.43 and 15.63–16.93 m)',
                   'IfcSlab LANDING "Landing 1" geometry bbox 2.80 × 1.24 m (y 14.12–15.36 m); Run 1 bbox starts at y 15.20 m',
                   'IfcBuildingStorey E00_OKRD −0.15 m, E01_OKRD +3.75 m',
                   'IfcStair Zusammengebaute Treppe:Treppe:2424673: runs 1.30 m wide, LANDING bbox 1.33 × 2.80 m'],
         hidden_knowledge='Caption: landing width ≥ stair width (no separate depth rule for the turning landing); stairs with landings are required in legally essential stairways with storey height ≥2.75 m; landing length = n × stride + 1 tread.',
         basis=[C['g9_landing_width'], C['landing'], cite('page_0132', 'landing length = \\( n \\) times length of stride + 1 depth of tread')],
         rubric=['Reads flight width ≈1.30 m and landing 2.80 × 1.24 m from the geometry',
                 'Applies landing width ≥ stair width to the 2.80 m landing width (met) and the landing-length rule (≈0.89 m ≤ 1.24 m)',
                 'Notes landings are required because the storey height 3.90 m ≥ 2.75 m',
                 'Observes the ≈1.24 m depth is slightly below the flight width but that the book states no depth rule (does not call it a breach); optionally contrasts with :2424673']),

    dict(project='fantasy_office_building_3', derived_from=[444], pairing='supplement', question_type='compliance',
         question='Both stair cores of fantasy_office_building_3 contain half-turn stairs with one intermediate landing per storey '
                  '(west: Betonfertigteil-Treppe, e.g. :687453 on OG1; east: Ortbetontreppe, e.g. :688549 on OG1). Using the storey '
                  'elevations and the stair geometry, are the intermediate landings dimensioned correctly for these flights?',
         answer='Yes. The storey height is 3.70 m (OG1 3.70 m to OK OG2 7.40 m; 21 risers × 0.176 m), which is '
                '≥2.75 m, so landings are required. The book\'s caption asks that the landing width be ≥ the stair width: the flights are '
                '≈1.20 m wide (geometry bounding box) and the landings span ≈2.59 m (west, bbox 2.59 × 1.23 m) and ≈2.64 m (east, bbox '
                '2.64 × 1.24 m) across both runs, so the rule is met with a wide margin. The landing length also covers one stride plus one '
                'tread: 2 × 0.176 + 0.27 = 0.62 m + 0.27 m ≈ 0.89 m (east: 2 × 0.176 + 0.283 + 0.283 ≈ 0.92 m), both < 1.23 m. The '
                'landing depth in the direction of travel (≈1.23–1.24 m) also just exceeds the flight width, by 3–4 cm, though the caption '
                'states no rule for that depth.',
         evidence=['IfcBuildingStorey OG1 3.70 m, OK OG2 7.40 m (original answer 444)',
                   'IfcStair Betonfertigteil-Treppe:Treppe:687453 (3xSk0LgvD4W95QoeT91raN), HALF_TURN_STAIR, 21 risers, 0.176 m / tread 0.27 m; '
                   'runs bbox width 1.20 m; LANDING bbox 2.59 × 1.23 m',
                   'IfcStair Ortbetontreppe:Treppe:688549 (3xSk0LgvD4W95QoeT91wNl), HALF_TURN_STAIR, 21 risers, 0.176 m / tread 0.283 m; '
                   'runs bbox width 1.20 m; LANDING bbox 2.64 × 1.24 m'],
         hidden_knowledge='Stairs with landings are required in legally essential stairways with storey height ≥2.75 m; caption: landing width ≥ stair width (no separate depth rule); landing length = n × stride + 1 tread.',
         basis=[C['g9_landing_width'], C['landing'], cite('page_0132', 'landing length = \\( n \\) times length of stride + 1 depth of tread')],
         rubric=['Identifies the storey height 3.70 m ≥ 2.75 m, so landings are mandatory',
                 'Compares the landing width ≈2.59–2.64 m with the flight width ≈1.20 m and states landing ≥ stair width is met',
                 'Notes the depth ≈1.23–1.24 m also exceeds 1.20 m but that the book gives no explicit depth rule (optional)',
                 'Optionally checks the landing length ≈0.89–0.92 m < 1.23 m']),

    # ------------------------------------------------------------ DIN 277 built volume
    dict(project='digital_hub', derived_from=[152], pairing='supplement', question_type='derivation',
         question='For an early cost estimate, the cost planner needs the net built volume of the DigitalHub basement level B01_OKRD '
                  '(all twelve spaces, technical rooms, stores, corridor and both stairwells). Compute it from the model and say why '
                  'simply multiplying the basement floor area by the storey height would give the wrong figure.',
         answer='≈1,683 m³. The net built volume is the net floor area of each room times its clear ceiling height: the ten rooms with '
                '3.00 m clear height (RLT-Raum 206.37, Flur-UG 105.04, Heizzentrale 53.97, five × 26.49, Putzmittel and BMZ 10.34 m² each '
                '= 518.52 m²) give 1,555.6 m³; the two stairwells (19.79 m² each, 3.22 m) give 127.4 m³. Total net floor area 558.1 m², '
                'net volume ≈1,683 m³. Multiplying by the storey height (B01 −3.37 m to E00 −0.15 m = 3.22 m) gives ≈1,797 m³, which '
                'mixes the net floor area with a floor-to-floor height. The floor-to-floor height belongs to the gross built volume, which '
                'multiplies the gross (outside-dimension) floor area by the height from top of floor covering to top of floor covering. '
                'The Qto Height of the spaces is taken here as the clear height.',
         evidence=['B01_OKRD spaces, Qto_SpaceBaseQuantities.NetFloorArea / Height: 0-10 RLT-Raum 206.371 m² / 3.0 m; 0-1 Flur - UG 105.04 / 3.0; '
                   '0-5 Heizzentrale 53.969 / 3.0; 0-3, 0-4, 0-6, 0-7, 0-8 26.494 / 3.0 each; 0-2 Putzmittel 10.335 / 3.0; 0-9 BMZ 10.335 / 3.0; '
                   '0-11 and 0-12 Treppenhaus Ost/West - UG 19.79 / 3.22 each',
                   'IfcBuildingStorey B01_OKRD −3.37 m, E00_OKRD −0.15 m'],
         hidden_knowledge='DIN 277: net built volume = net floor area × clear ceiling height; gross built volume = gross floor area × floor-to-floor height (top of floor covering to top of floor covering).',
         basis=[C['g9_net_volume'], C['g9_gross_volume']],
         rubric=['Multiplies each space\'s net floor area by its own clear height (not one height for all)',
                 'Arrives at ≈1,680 m³ (net floor area ≈558 m²)',
                 'Explains that floor-to-floor height (3.22 m) belongs to the gross volume with gross floor area, giving ≈1,797 m³ if misapplied']),
]

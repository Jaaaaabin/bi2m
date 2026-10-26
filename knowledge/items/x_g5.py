# x_g5 — expansion group 5: building envelope and thermal insulation (early design stage).
# New knowledge points: single-leaf vs. insulated wall build-ups, cavity walls, concrete external walls,
# rear-ventilated skins, R/U-value arithmetic, thermal bridges at junctions, flat-roof falls, flat-roof
# types (warm / upside-down), vapour-barrier position, slopes for green roofs,
# pitched-roof insulation and ventilation. All items are supplements; see knowledge/x_g5.json.
# The book's text gives no tabulated U-value limits or λ values, so no item checks a numeric EnEV limit;
# U/R values used below are the ones stored in the IFC models.

# ---------------------------------------------------------------- external wall build-ups
C['g5_single_leaf'] = cite('page_0087', 'Single-leaf external walls → ① – ② are unproblematic regarding building physics, but on account of the high thermal insulation requirements can only be built with materials with high thermal insulation value (e.g. aerated blocks) and special thermally insulated mortars and plasters.')
C['g5_add_insul'] = cite('page_0087', 'Single-leaf walls with additional insulation layers → ③ – ⑥ (external, internal insulation → Building physics, p. 471 ff.) are therefore a common alternative.')
C['g5_render'] = cite('page_0485', 'On the external side of the insulating layers, there is a risk of cracking due to heat build-up and substrate with poor shear strength, so mineral render reinforced with mesh is used here (or plastic modified render).')
C['g5_cavity'] = cite('page_0087', 'Cavity walls consist of an inner load-bearing wall and an outer non-load-bearing weather protection facing (minimum thickness 90 mm). They can be built with an air gap, with air gap and thermal insulation, with cavity-filling insulation and with intermediate plaster layer')
C['g5_cavity_gap'] = cite('page_0087', 'The width of the air gap should be min. 40 mm (max. 150 mm).')
C['g5_concrete'] = cite('page_0090', 'Solid concrete walls can be used as external walls only with an additional thermal insulation layer. This can be as an external thermal insulation system → ① or as a multi-leaf construction (analogous to p. 75) with core insulation and possibly back-ventilation.')
C['g5_concrete_2layer'] = cite('page_0090', 'Two-layer reinforced concrete walls → ① with core insulation are used particularly as large-format external wall elements.')
C['g5_rearvent'] = cite('page_0485', 'The rear ventilation of the skin removes the vapour barrier effect of the relatively vapour-sealed outer layers. The width of the air gap with panel-like external skin amounts to min. 20 mm, or for brickwork outer skin min. 40 mm.')
# ---------------------------------------------------------------- U-value arithmetic, thermal bridges
C['g5_R'] = cite('page_0483', 'Thermal resistance R, unit m^2K/W [m^2hK/kcal] is a property of a layer: R = d/λ (d = layer thickness in m).')
C['g5_U'] = cite('page_0483', 'Overall resistance 1/U, unit m^2K/W [m^2hK/kcal], is the sum of the resistances of a building element to the transmission of heat (thermal resistances and surface resistances): 1/U = R_{si} + R + R_{se}')
C['g5_airfilm'] = cite('page_0484', 'The surface air film cannot exceed a certain proportion X of the overall resistance 1/U')
C['g5_bridge'] = cite('page_0485', 'Thermal bridges are parts of building elements with low thermal insulation compared with surrounding areas.')
C['g5_connections'] = cite('page_0486', 'Good thermal insulation includes not only highly insulated building components, but also the appropriate connections between the building elements.')
C['g5_bridge_worse'] = cite('page_0486', 'Thus it should be borne in mind that this thermal bridging effect can have considerably worse consequences with highly insulated elements than with building elements with less thermal insulation.')
# ---------------------------------------------------------------- flat roofs
C['g5_flat_slope'] = cite('page_0103', 'Flat roofs are defined as roofs with a slope of up to 5%. Flat roofs without slope are possible as a special construction in exceptional cases. Flat roofs should generally have a minimum slope of 2%.')
C['g5_flat_5'] = cite('page_0103', 'it is recommended to construct flat roofs with a minimum slope of 5% (3°).')
C['g5_warm_roof'] = cite('page_0104', "Non-ventilated, single-layer construction ('warm roof'), in which the load-bearing structure, vapour barrier, thermal insulation and waterproofing (including intermediate layers) form a composite element.")
C['g5_upside_down'] = cite('page_0104', "or an 'upside-down roof' → 8 (waterproofing and vapour barrier are applied as one layer directly onto the load-bearing construction and the closed-cell insulation is loosely laid on top and secured with a gravel layer)")
C['g5_green_slope'] = cite('page_0106', 'The pitch of gabled roofs should not exceed 25° and flat roofs should have a maximum slope of 2–3%.')
# ---------------------------------------------------------------- vapour barrier
C['g5_vb_warm'] = cite('page_0484', 'If there is a vapour barrier on the outside, then the entire vapour pressure gradient occurs there and the result is condensation → 8; if this is to be avoided, then a vapour barrier must be installed on the warm side')
C['g5_vb_extra'] = cite('page_0485', "More recent building ('warm roof', 'warm façade') features an external vapour barrier layer (e.g. waterproofing) and, on account of this, an additional internal vapour barrier.")
C['g5_vb_roof'] = cite('page_0102', 'The vapour barrier is under the thermal insulation to prevent condensation inside the roof construction.')
# ---------------------------------------------------------------- pitched roofs
C['g5_pitched_insul'] = cite('page_0102', 'Thermal insulation is generally in the form of mineral wool roll material and is installed between and under the rafters or as prefabricated insulation elements, sometimes with interlocking, vapour barrier on the room side and battens fixed to the rafters')
C['g5_vent_gap'] = cite('page_0102', 'ventilated roof construction has an additional ventilation gap between underlay and thermal insulation, to remove spray and condensate.')
C['g5_vent_pref'] = cite('page_0102', 'Ventilated roofs require additional rafter depth and work properly only with a correctly installed vapour barrier and functioning roof ventilation. Therefore the building industry commonly prefers unventilated roof construction.')

ITEMS += [
    # ============================================================ cavity walls


    # ============================================================ single-leaf wall, U-value arithmetic
    dict(project='fzk_house', derived_from=[], pairing='supplement', question_type='derivation',
         question='The eight external walls of the house are a single 300 mm layer of "Leichtbeton 102890359" (lightweight concrete), no separate insulation, with Pset ThermalTransmittance 0.4 W/m²K. Is a single-leaf external wall without an insulation layer a reasonable design choice here, and what thermal conductivity must the lightweight concrete have for the stated U-value to hold?',
         answer='It is reasonable only because the wall material itself must be highly insulating. With 1/U = R_si + R + R_se and R = d/λ: 1/U = 1/0.4 = 2.5 m²K/W, so the 300 mm layer must provide R = 2.5 − (R_si + R_se), i.e. at most 2.5 m²K/W. Hence λ = d/R ≥ 0.30/2.5 = 0.12 W/mK, and since the thin surface air films supply only a small part of 1/U, λ must be only slightly above 0.12 W/mK. That is an insulating lightweight masonry value (the kind of material Neufert names, e.g. aerated blocks), not ordinary structural concrete. Neufert notes that, because of today\'s high insulation requirements, single-leaf external walls can only be built in such high-insulation materials (with special insulating mortars and plasters); the common alternative is a single leaf with an added insulation layer.',
         evidence=['8 IfcWall "Leichtbeton 102890359 300" (Wand-Ext-ERDG-1…4, Wand-Ext-OG-1…4), e.g. 3rPX_Juz59peXXY6wDJl18; IfcMaterialLayerSet: one layer Leichtbeton 102890359, 0.30 m.',
                   'Pset_WallCommon ThermalTransmittance = 0.4 on these walls.',
                   'Arithmetic: 1/0.4 = 2.5 m²K/W; 0.30/2.5 = 0.12 W/mK.'],
         hidden_knowledge='Single-leaf external walls only in highly insulating materials (e.g. aerated blocks); R = d/λ, 1/U = R_si + R + R_se.',
         basis=[C['g5_single_leaf'], C['g5_R'], C['g5_U']],
         rubric=['Computes 1/U = 2.5 m²K/W', 'Derives λ ≥ 0.12 W/mK (≈ 0.12 after small surface resistances)', 'States single-leaf walls can only be built in a highly insulating material such as aerated blocks, the common alternative being an added insulation layer']),

    dict(project='fzk_house', derived_from=[], pairing='supplement', question_type='diagnosis',
         question='The house uses the same material "Leichtbeton 102890359" for its 300 mm external walls (ThermalTransmittance 0.4 W/m²K) and its 240 mm internal walls (ThermalTransmittance 1.5 W/m²K). Can both U-values be right for the same homogeneous material? Show the check.',
         answer='No, they are inconsistent. With R = d/λ, the same material at 240 mm has R240 = 0.8 × R300. The internal wall gives 1/U = 1/1.5 ≈ 0.67 m²K/W, so R240 ≤ 0.67 and R300 = R240/0.8 ≤ 0.83 m²K/W. For the external wall 1/U = 1/0.4 = 2.5 m²K/W = R_si + R300 + R_se, the surface resistances would then have to supply ≥ 2.5 − 0.83 ≈ 1.67 m²K/W, i.e. about two-thirds of the overall resistance — impossible for thin surface air films, whose share of 1/U is necessarily limited. Either the 0.4 value is a design target attached to the external type, or the 1.5 value is a placeholder; the model\'s U-values cannot be used to check the envelope without correcting one of them.',
         evidence=['5 IfcWall "Leichtbeton 102890359 240" (Wand-Int-ERDG-1…5), e.g. 2XPyKWY018sA1ygZKgQPtU: single layer 0.24 m, ThermalTransmittance 1.5.',
                   '8 IfcWall "Leichtbeton 102890359 300" (Wand-Ext-*), e.g. 3rPX_Juz59peXXY6wDJl18: single layer 0.30 m, ThermalTransmittance 0.4.',
                   'Arithmetic: 0.24/0.30 = 0.8; 1/1.5 = 0.667; 0.667/0.8 = 0.833; 2.5 − 0.833 = 1.667 m²K/W (67 % of 2.5).'],
         hidden_knowledge='R = d/λ scales with thickness for one material; 1/U = R_si + R + R_se; the surface air film can only be a limited share of 1/U.',
         basis=[C['g5_R'], C['g5_U'], C['g5_airfilm']],
         rubric=['Uses R ∝ d for the same λ (R240 = 0.8 R300)', 'Derives R300 ≤ ≈0.83 m²K/W from the internal wall', 'Shows the external U = 0.4 would need ≈1.67 m²K/W of surface resistance → inconsistent']),

    # ============================================================ concrete external walls
    dict(project='fantasy_residential_building_1', derived_from=[], pairing='supplement', question_type='compliance',
         question='The perimeter walls of the apartment building (e.g. the west and east end walls and the north wall on all three floors) are "STB 30.0 - Sichtbeton 1": 300 mm exposed in-situ concrete, single material, flagged IsExternal. Is this acceptable as a heated building\'s external wall, and how could the exposed-concrete appearance be kept?',
         answer='No. The walls are a single 300 mm layer of fair-faced reinforced concrete with no insulation layer, and solid concrete walls may be used as external walls only with an additional thermal insulation layer — either an external insulation system or a multi-leaf build-up with core insulation (possibly back-ventilated). An external insulation system would hide the Sichtbeton; to keep the exposed concrete outside, the façade would become a two-layer reinforced-concrete wall with core insulation (an inner structural leaf, insulation, outer concrete facing), a build-up Neufert names for large-format external wall elements. The 500 mm base slab also carries no insulation layer in the model.',
         evidence=['24 IfcWall "Basiswand:STB 30.0 - Sichtbeton 1" (Pset_WallCommon IsExternal = True), material "StB - Sichtbeton (1)" only, e.g. 1tiTc0GsT6r8z9SnpAsGsL (x −13.01…−12.71, y −22.1…10.75, First Floor), 1C2465LnHARBtzuYAQtmwF (x 6.69…6.99, Ground Floor), 1B8zheoLv0avhNvrhkAR_h (y 10.45…10.75, Ground Floor).',
                   'Thickness 0.30 m from geometry (e.g. x −13.01 → −12.71); no insulation layer or lining on these walls.',
                   'IfcSlab "Bodenplatte:STB 50cm" 0ZTMLRs0fFLvIOWq5uTbRO, single material Beton C 25/30, z −0.5…0.'],
         hidden_knowledge='Solid concrete external walls need an additional insulation layer (ETICS or multi-leaf with core insulation); two-layer RC walls with core insulation as large-format façade elements.',
         basis=[C['g5_concrete'], C['g5_concrete_2layer']],
         rubric=['Notes the walls are single-layer 300 mm concrete with no insulation', 'Verdict: not acceptable without added insulation', 'Proposes two-layer RC with core insulation (or names ETICS and its loss of exposed concrete)']),

    dict(project='fantasy_office_building_1', derived_from=[], pairing='supplement', question_type='intent',
         question='The office building\'s solid external walls are "STB 25.0 WD 12.0" and "STB 20.0 WD 12.0". Read their layer order from the model and explain what kind of external wall construction this is, why the designer added the 120 mm layer, and what the outer surface of such a wall needs.',
         answer='Both are single-leaf reinforced-concrete walls with an external thermal insulation system (ETICS): the layer list starts on the outside with 120 mm hard insulation ("Wärmedämmung - Hart"), then 250 mm (or 200 mm) in-situ concrete, and in the 200 mm type a 50 mm gypsum lining on the room side (total 370 mm). The insulation is required because solid concrete may serve as an external wall only with an additional insulation layer — single-leaf walls with added (external or internal) insulation are the usual alternative to monolithic high-insulation masonry. Placing it outside keeps the concrete on the warm side. The insulation face is not left exposed: on the external side of insulation layers there is a risk of cracking (heat build-up, substrate with poor shear strength), so a mesh-reinforced mineral (or plastic-modified) render is used there.',
         evidence=['6 IfcWall "Basiswand:STB 25.0 WD 12.0" (e.g. 1BjNOqpyX8MBF4NmZ4FzfT) and 8 IfcWall "Basiswand:STB 20.0 WD 12.0" (e.g. 1BjNOqpyX8MBF4NmZ4FziJ), all on EG, Pset_WallCommon IsExternal = True.',
                   'Qto_WallBaseQuantities layers (in order): Wärmedämmung - Hart 0.12; StB - Ortbeton 0.25 (resp. 0.20); MW - Gipskarton 0.05 (20.0 type only); Width 0.37 m for the 20.0 type.'],
         hidden_knowledge='Concrete external walls only with added insulation (ETICS or core insulation); single-leaf + additional insulation is a standard alternative; render on external insulation is mesh-reinforced mineral (or plastic-modified) render because of the cracking risk.',
         basis=[C['g5_concrete'], C['g5_add_insul'], C['g5_render']],
         rubric=['Identifies external insulation (ETICS) on a concrete leaf from the layer order', 'Explains concrete external walls need added insulation', 'Mentions mesh-reinforced render on the insulation']),

    # ============================================================ rear-ventilated façade, insulation continuity
    dict(project='digital_hub', derived_from=[], pairing='supplement', question_type='compliance',
         question='The building\'s façade is modelled as an inner leaf "Leichtbetonmauerwerk 250" plus a separate outer wall element "WD 200 + Luft 40 + Bekleidung 12" (fibre-cement panels). What kind of external wall is this, and is the cladding\'s cavity dimensioned correctly?',
         answer='It is a single-leaf masonry wall with external insulation behind a rear-ventilated cladding: 250 mm lightweight-concrete masonry, 200 mm mineral wool (Rockwool Fixrock 033), a 40 mm air layer, and 12 mm fibre-cement panels (outer element 252 mm, wall 502 mm in total, U of the outer element 0.151 W/m²K, R 6.63 m²K/W). For a panel-like external skin the ventilation gap must be at least 20 mm (40 mm would be needed only for a brickwork skin); 40 mm gives twice the minimum, so the rear ventilation works and removes the vapour-barrier effect of the fairly vapour-tight panels.',
         evidence=['4 IfcWall "Basiswand:WD 200 + Luft 40 + Bekleidung 12" (e.g. 12bPoIwbv0tBGfPfnvCUc2), height 0–8.15 m around the whole perimeter (x 6.62–70.38, y 6.62–26.98); Pset_WallCommon IsExternal = True, ThermalTransmittance 0.1508; Beschreibung "LB 250 + WD 200 + Luft 40 + Bekleidung 12".',
                   'Qto layers: Faserzementplatte (Equitone - natura) 0.012; Luftschicht 0.04; Steinwolle (Rockwool Fixrock033 VS) 0.20; Width 0.252; Thermischer Widerstand (R) 6.629.',
                   '10 IfcWall "Basiswand:Leichtbetonmauerwerk 250" directly inside the cladding element (e.g. 12bPoIwbv0tBGfPfnvCUq4, y 6.87–7.12).'],
         hidden_knowledge='Rear-ventilated skin: air gap ≥ 20 mm for panel cladding, ≥ 40 mm for brickwork; single-leaf walls with additional external insulation.',
         basis=[C['g5_rearvent'], C['g5_add_insul']],
         rubric=['Classifies as masonry + external insulation + rear-ventilated cladding', 'Applies the ≥ 20 mm panel rule (not the 40 mm brick rule)', 'Verdict: 40 mm complies (2× minimum)']),

    dict(project='digital_hub', derived_from=[], pairing='supplement', question_type='intent',
         question='Below the façade cladding the model continues the insulation with separate elements: "WD hart 200" walls around the plinth (−0.82 to 0.00 m) and around the basement (−3.67 to −0.37 m), and "WD 200 hart" slabs under the basement base slab and under the ground floor outside the basement. What is the designer trying to achieve with these elements, and what would happen if they were omitted?',
         answer='They keep a continuous 200 mm insulation envelope around the heated volume: façade insulation (200 mm mineral wool) runs down to ground level, the plinth and the reinforced-concrete basement walls get 200 mm hard (pressure-resistant) insulation on the outside, and the 300 mm base slab and the ground floor over the unexcavated part sit on 200 mm hard insulation. Good thermal insulation needs not only well-insulated components but proper connections between them. Without these pieces the bare concrete basement walls and slabs (concrete external parts need added insulation anyway) would be thermal bridges — areas with much lower insulation than the 200 mm-insulated surroundings, with heat loss and cold, condensation-prone inner surfaces. In a highly insulated envelope like this one (U ≈ 0.13–0.15 W/m²K), such bridges have proportionally worse consequences.',
         evidence=['IfcWall "Basiswand:WD hart 200" (U 0.135): plinth ring z −0.82…0.00 (e.g. 3POx7FYsP3ahzOj_4LrJA4, y 6.67–6.87, x 6.88–70.33); basement ring z −3.67…−0.37 (e.g. 0CWDnGbzX4Sf1BesL9Tj9B, x 13.83–63.18, y 13.62–13.82).',
                   'IfcSlab "Geschossdecke:WD 200 hart" 0CWDnGbzX4Sf1BesL9TjTl (z −3.87…−3.67, under base slab) and 0CWDnGbzX4Sf1BesL9TjKx (z −0.57…−0.37, x 7.37–69.62, y 7.37–26.23).',
                   'IfcSlab "Bodenplatte:STB 300" 23Np8uMAvEN9H6Ds49deXD, z −3.67…−3.37 (U 1.357 on its own).',
                   'Façade element "WD 200 + Luft 40 + Bekleidung 12" from z 0.00 to 8.15 (U 0.151); roof "Flachdachaufbau begrünt 320" U 0.128.'],
         hidden_knowledge='Thermal bridges = parts with low insulation compared with surroundings; good insulation needs proper connections; worse effect in highly insulated envelopes; concrete external elements need added insulation.',
         basis=[C['g5_bridge'], C['g5_connections'], C['g5_bridge_worse'], C['g5_concrete']],
         rubric=['Explains the elements form a continuous insulation wrap (façade → plinth → basement → slabs)', 'Names thermal bridges / junction losses as what is avoided', 'Notes bare concrete basement elements would need insulation anyway', 'Mentions the higher impact in a highly insulated envelope (optional)']),

    # ============================================================ flat roofs
    dict(project='fantasy_office_building_3', derived_from=[], pairing='supplement', question_type='compliance',
         question='The four roof areas over the top offices are slabs "Basisdach:Titanzink - Eindeckung" (timber boarding + bitumen, titanium-zinc covering), modelled with PitchAngle 0. Would standard design guidance accept this roof geometry and build-up for a heated office building at concept stage?',
         answer='No, on two counts. (1) Fall: the roof is exactly flat (0°, 0 %). Flat roofs should have at least 2 % slope, and because of flatness tolerances and deflection Neufert recommends ≥ 5 % (3°); a roof with no fall is only an exceptional special construction — and a metal sheet covering is normally laid on a pitch. (2) Thermal envelope: the 80 mm package contains only timber boarding and bitumen, no insulation and no vapour barrier, so it is neither a warm roof (structure, vapour barrier, insulation and waterproofing as one composite) nor a cold roof. Across the ≈ 2 × 160 m² + 2 × 64 m² = 448 m² of roof (bounding boxes) the model shows no thermal insulation at all.',
         evidence=['4 IfcSlab (PredefinedType ROOF) "Basisdach:Titanzink - Eindeckung": 2rKnuImKDBFhDP_XLXucUH and 2e6qd952zBGAsBt5_H2E$A (5.0 × 32.0 m, z 18.50–18.58), 2e6qd952zBGAsBt5_H2EsL and 2e6qd952zBGAsBt5_H2EoY (16.0 × 4.0 m, z 14.55–14.63).',
                   'Pset_SlabCommon PitchAngle = 0.0, IsExternal = True; upward faces horizontal (0°); thickness 0.08 m.',
                   'IfcMaterialConstituentSet: Holz - Verschalung, Bitumen (no insulation constituent).',
                   'Plan areas from bounding boxes: 5.0 × 32.0 = 160 m² (×2), 16.0 × 4.0 = 64 m² (×2); Σ 448 m².'],
         hidden_knowledge='Flat roofs ≥ 2 % fall (recommended ≥ 5 % / 3°), zero-fall roofs only exceptionally; a warm roof is a composite of structure, vapour barrier, insulation and waterproofing.',
         basis=[C['g5_flat_slope'], C['g5_flat_5'], C['g5_warm_roof']],
         rubric=['Reads PitchAngle 0 and compares with ≥ 2 % (5 % recommended)', 'Notes zero-fall is exceptional only', 'Notes missing insulation / vapour barrier in the roof build-up']),

    dict(project='fantasy_office_building_2', derived_from=[], pairing='supplement', question_type='diagnosis',
         question='The flat part of the top roof is "Basic Roof:Flachdachaufbau begrünt 320" (a green roof, U 0.128 W/m²K), modelled perfectly level. Its constituents, listed outside to inside as in the model\'s other types, are greening, fleece, hard insulation, bitumen membrane. What flat-roof type is this, and what is wrong with the way it is modelled for a planted roof?',
         answer='With the insulation above the bitumen waterproofing, it is an upside-down (inverted) roof: waterproofing (doubling as vapour barrier) directly on the structure, insulation loosely laid on top — which must therefore be closed-cell, pressure-resistant insulation, consistent with "Dämmung - hart" — and the planting acting as ballast instead of gravel. The problem is the fall: the roof is modelled at 0°. Planted flat roofs should have a maximum slope of 2–3 %, and flat roofs in general at least 2 % (recommended 5 %), zero-fall being only an exceptional special construction. So the roof needs a fall of about 2 % (≈ 1.1°) — enough to drain, but not more than 3 % so the growing layer does not dry out.',
         evidence=['IfcRoof 3IUIR8A5v9Ge7poU5yykfA "Basic Roof:Flachdachaufbau begrünt 320" on 5th Floor, bbox x 13.22–33.26, y 5.42–41.46, z 18.27–18.42; all upward faces horizontal (0°).',
                   'Pset_RoofCommon IsExternal = True, ThermalTransmittance 0.1279; Thermal Resistance (R) 7.82.',
                   'IfcMaterialConstituentSet order: Dachdeckung - Begrünung; Dachdeckung - Flies; Dämmung - hart; Dachdeckung - Bitumenbahn.',
                   'Arithmetic: atan(0.02) ≈ 1.15°.'],
         hidden_knowledge='Upside-down roof: waterproofing/vapour barrier on the structure, closed-cell insulation laid on top; planted flat roofs max. 2–3 % slope; flat roofs ≥ 2 %.',
         basis=[C['g5_upside_down'], C['g5_green_slope'], C['g5_flat_slope']],
         rubric=['Identifies an upside-down (inverted) roof from insulation above the membrane', 'Notes the insulation must be closed-cell/hard', 'Flags 0° fall; target ≈ 2 % (≤ 3 % for green roofs)']),


    dict(project='samuel_macalister_sample_house', derived_from=[], pairing='supplement', question_type='diagnosis',
         question='The flat roof over part of the house is "Basic Roof:Warm Roof - Timber", modelled with PitchAngle 0. Check its layer sequence and its fall: is the build-up right, and where would the required fall come from?',
         answer='The layer sequence is correct: asphalt 20 mm and felt (waterproofing), 50 mm rigid insulation, a vapour retarder, 18 mm chipboard deck, 50 mm firrings and 200 mm timber joists (338 mm). Structure, vapour barrier, insulation and waterproofing form the composite of a non-ventilated warm roof, and the vapour retarder lies on the warm side directly under the insulation, where a vapour barrier has to be to avoid condensation behind the vapour-tight waterproofing (the book places it under the insulation in pitched roofs for the same reason). The geometry, however, is modelled with 0° (PitchAngle 0, top at +2.54 m throughout), while flat roofs should have at least 2 % fall (5 % recommended). The 50 mm firring layer is where the fall belongs (tapered firrings on the joists); over the ≈ 13 m long roof 2 % needs ≈ 0.26 m, so 50 mm firrings alone would give only ≈ 0.4 % unless the joists are also laid to falls.',
         evidence=['IfcSlab 0LKJKCHUL1kBtnlFXddz6a (IfcRoof 0LKJKCHUL1kBtnlFfddz6a) "Basic Roof:Warm Roof - Timber", storey Ceiling, bbox x −12.14…−0.24, y −26.70…−13.67, z 2.20–2.54; Pset_SlabCommon PitchAngle 0.0; upward faces 0° (70.8 m²).',
                   'IfcMaterialLayerSet (mm): Roofing - Asphalt 20; Roofing - Felt 0; Insulation / Thermal Barriers - Rigid insulation 50; Vapour / Moisture Barriers - Vapour Retarder 0; Wood - Sheathing - Chipboard 18; Wood - Firring 50; Structure - Timber Joist/Rafter Layer 200 (Σ 338).',
                   'Arithmetic: −13.67 − (−26.70) = 13.03 m; 0.02 × 13.03 ≈ 0.26 m; 0.05/13.03 ≈ 0.4 %.'],
         hidden_knowledge='Warm roof composite with vapour barrier on the warm side under the insulation; flat roofs ≥ 2 % fall (5 % recommended).',
         basis=[C['g5_warm_roof'], C['g5_vb_warm'], C['g5_vb_roof'], C['g5_flat_slope'], C['g5_flat_5']],
         rubric=['Recognises a correct warm roof with vapour retarder under the insulation', 'Flags the 0° geometry vs ≥ 2 % fall', 'Points to the firrings (or joists to falls) as the source of fall, with the ≈ 0.26 m figure (optional)']),

    # ============================================================ pitched roofs
    dict(project='fzk_house', derived_from=[], pairing='supplement', question_type='diagnosis',
         question='The FZK house has a 30° gable roof over a habitable 74.5 m² attic room, but the roof is modelled only as two 200 mm "Solid" slabs (ThermalTransmittance 0.3). For a habitable attic under a pitched roof, where would the thermal insulation and the vapour barrier normally go, and should the roof be built as a ventilated or an unventilated construction?',
         answer='The insulation (usually mineral wool) goes between and under the rafters, with the vapour barrier on the room side and battens fixed to the rafters. An unventilated construction is the usual choice: a ventilated roof needs extra rafter depth and only works with a correctly installed vapour barrier and functioning roof ventilation, so the industry commonly prefers unventilated roofs. None of these layers is modelled: the roof is a single homogeneous 200 mm slab with a stored U-value of 0.3, so the build-up has to be added before the envelope can be checked.',
         evidence=['IfcSlab Dach-1 07Enbsqm9C7AQC9iyBwfSD and Dach-2 2IxUUNUVPB6Ob$eicCfP2N, top faces 30°; type "Solid 397409098 200", one material layer, ThermalTransmittance 0.3.',
                   'IfcSpace 7 on Dachgeschoss (+2.7 m), area 74.509 m² (habitable attic room).'],
         hidden_knowledge='Pitched-roof insulation between/under the rafters with a room-side vapour barrier; unventilated roofs are generally preferred because ventilated ones need deeper rafters and a perfect vapour barrier plus working ventilation.',
         basis=[C['g5_pitched_insul'], C['g5_vent_pref']],
         rubric=['Insulation between/under rafters', 'Vapour barrier on the room (warm) side', 'Unventilated construction preferred, with the reason', 'Notes the model lacks the layer build-up']),

    dict(project='fantasy_office_building_2', derived_from=[], pairing='supplement', question_type='diagnosis',
         question='The two 12° pitched roof areas are "Basic Roof:Ziegeldach 360" (U 0.110 W/m²K). Their constituents, outside to inside, are: roof tiles, air layer, timber, soft insulation, air layer, timber. Is this a ventilated or a non-ventilated pitched-roof construction, and what layer does it then rely on that the model does not show?',
         answer='Non-ventilated. The air layer directly under the tiles is the covering\'s batten space, which both roof types have; a ventilated roof would need an additional ventilation gap between the underlay (here the outer timber boarding) and the insulation, and there is none — the insulation lies directly under the boarding. The second air layer is on the room side of the insulation, behind the inner timber lining, i.e. a service void, not a ventilation path. This unventilated build-up is the one the industry prefers (ventilated roofs need extra rafter depth and work only with a correct vapour barrier and functioning ventilation), but it depends on an airtight vapour barrier on the room side under the insulation, sealed at all joints and penetrations — no such constituent is in the model.',
         evidence=['IfcRoof 3a$5BMVQv4e9TNrjRqPBXW and 1ShjT4WB13Uw9ASipZ2PRh "Basic Roof:Ziegeldach 360" on 5th Floor; Dimensions Slope 0.2127 (≈ 12.0°), Thickness 0.36, Area 90.16 m² each; ThermalTransmittance 0.1095, R 9.13.',
                   'IfcMaterialConstituentSet order: Dachdeckung - Ziegeldach; Luftschicht; Dachdeckung - Holz; Dämmung - weich; Luftschicht; Dachdeckung - Holz.'],
         hidden_knowledge='Ventilated pitched roofs have an extra ventilation gap between underlay and insulation; unventilated roofs are preferred but need a room-side vapour barrier under the insulation.',
         basis=[C['g5_vent_gap'], C['g5_vent_pref'], C['g5_vb_roof']],
         rubric=['Classifies as non-ventilated (no gap between underlay and insulation)', 'Interprets the inner air layer as a room-side void, not ventilation', 'Names the missing room-side vapour barrier']),
]

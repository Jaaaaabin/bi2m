"""Instances of the rules on model 0204 of data/model_ifc4_0001-0370 (anonymised IFC4, Revit 25 export).

The facts come from the graph runs/graphs/ifc4_0204.json (rules/extract_graph.py) plus a few numbers computed from the
mesh (space areas = volume / height, slab areas). Verdicts: pass | fail | mixed | unknown | not_applicable.
`unknown` = the context is met but the IFC lacks what the requirement needs (e.g. FireRating).

.venv/bin/python rules/build_instances_0204.py
"""
import json, os
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'instances_ifc4_0204.jsonl')
M = 'ifc4_0204'

# ── shared facts (all from the graph unless stated) ─────────────────────────────────────────
STOREYS = {'Level -1': -3.1, 'Level 0': 0.0, 'Level 1': 3.1, 'Level 2': 6.2, 'Level 3': 9.3, 'Level 4 (roof)': 12.4}
BUILDING = {'IfcBuilding': '17TzSGhx1CmfOinWf9tG7t (unnamed, Pset_BuildingCommon.NumberOfStoreys = 6)',
            'IfcSite': '17TzSGhx1CmfOinWf9tG7q, RefLatitude 48°08′20″ N, RefLongitude 11°34′48″ E (Munich), RefElevation 0.0, TrueNorth = +Y',
            'footprint_m': '54.4 × 51.4 (slab bbox), floor slab area ≈ 2444 m² (volume / 0.20)',
            'usage': 'office (inferred from room names: 15 Office + 5 Outer office + 2 Open-plan office + 9 Conference + 4 Tea kitchen per floor; no model card)',
            'spaces': 'IfcSpace only on Level 1–3 (53 each); Level 0 (entrance, canteen) and Level -1 (basement) have no IfcSpace'}
WS = {'Level 1': 75, 'Level 2': 66, 'Level 3': 66}  # Furniture_Desk count inside office-type spaces (derived: contains)

I = []
def inst(rid, ctx, derived, met, verdict, expl, ev):
    I.append(dict(iid=f'I0204-{len(I) + 1:02d}', rid=rid, model=M, context_instance=ctx, derived=derived, condition_met=met,
                  verdict=verdict, explanation=expl, evidence=ev))


# ───────────── Site & Building ─────────────
inst('R01', {**BUILDING, 'storeys': STOREYS, 'uppermost_occupied_storey': 'Level 3 (53 spaces incl. offices)'},
     {'H_top_m': 9.3, 'roof_top_m': 15.0}, False, 'not_applicable',
     '最高有人停留楼层 Level 3 楼面 9.3 m ≤ 22 m，屋面顶 15.0 m 也在 22 m 以下，不是高层建筑。高层相关规则（R52、R53、R60–R62、R64、R94、R103）一并不适用。',
     ['IfcBuildingStorey Level 3 Elevation=9.3', 'IfcSlab 329wVB92v7LvgBS$H3YgMN (roof) bbox z 12.2–15.0', 'IfcSite.RefElevation=0.0'])

inst('R13', {**BUILDING, 'plot_boundary': '模型里没有地块边界（IfcSite 只有经纬度，无几何）'},
     {'H_wall_m': 'Level 0 地坪 0.0 → 屋面顶 15.0，H ≈ 15.0', 'required_setback_general_m': '0.4 × 15.0 = 6.0', 'required_setback_commercial_m': '0.2 × 15.0 = 3.0 → 取 3.0'},
     True, 'unknown', '能算出所需退距（一般地区 6.0 m、商业区 3.0 m），但 IFC 没有地块边界，d 无法求，判定留空——正是规则 notes 预言的情况。',
     ['IfcSite 17TzSGhx1CmfOinWf9tG7q 无 IfcRelAggregates 几何、无 Pset_SiteCommon.TotalArea', 'external walls Basic Wall:MW 36.5 height 2.9–3.1 per storey'])

inst('R14', {'building.usage': 'office', 'TrueNorth': '(0, 1) → 模型 +Y = 北', 'offices_by_facade': {'west x=-13 (Office ×5)': 'W', 'north y=+10.75 (Office ×5)': 'N', 'east x=+41 (Office ×4)': 'E', 'south y=-40 (Conference ×8, curtain wall)': 'S'}},
     {'axis': '54.4 × 51.4 m，近似方形，无明显长轴', 'has_corridor': 'true：600 m² 的环形 Hall 是走廊式交通，围着两个核心大开间'},
     True, 'fail', '北立面有 5 间单人办公室（y = 5.72–10.57，窗朝 +Y = 北）。书中“北向房间只在无走廊平面中可接受”，而本平面以环形 Hall 作走廊，所以这 5 间按规则不合适；南立面全部给了会议室（幕墙），正好与“南向易遮阳”相反。',
     ['IfcGeometricRepresentationContext.TrueNorth = (6e-17, 1.0)', 'IfcSpace 0Cf3vwOoj5UOMjVSWR4C4X Office bbox y 5.72–10.57, window Windows_Concept_Sash 1810x1210 at y=10.8', 'IfcSpace Hall 0Cf3vwOoj5UOMjVSWR4C67 (599 m²)'])

inst('R15', {'building.usage': 'office', 'is_high_rise': False, 'plan (Level 1)': '外圈：单间办公 + 会议室 + 卫生间 + 楼梯间（沿四个立面）；中间：3.2 m 宽环形 Hall；核心：两个 258 / 274 m² 的 Open-plan office（无窗）'},
     {'layout': '既不是单排/双排/三排——外圈一排房间 + 环廊 + 内核大开间，相当于“三排且中部用于工位”', 'room_depth_m': '外圈单间 3.3–5.0；核心开间 17.3–18.4', 'building_depth_m': 51.4},
     True, 'fail', '书中中部大区只适合高层且用作服务核心（竖向交通比例高）；这里 9.3 m 的四层楼把中部 530 m² 用作无窗的工位区，不符合“中部服务区只对高层合适”，也不是书中推荐给行政办公的双排。',
     ['IfcSpace Open-plan office 0Cf3vwOoj5UOMjVSWR4C4K bbox x -3.74…14.62, y -14.75…2.54 (全部在外墙 3 m 以内之外)，opensTo 无 IfcWindow', 'Hall 宽度：west 3.18 m, north 3.18, east 3.17, south 6.89 (space bbox 差)'])

inst('R16', {'building.usage': 'office', 'facade_grid': '南立面幕墙 Curtain Wall:Raster 1.5 x 3.0m（1.5 m 竖梃）；北/东/西立面砌体墙，每间办公室一扇 1.81 m 窗', 'partition_grid': '北立面办公室 x 起点 10.53, 14.54, 18.55, 22.56, 26.57 → 开间 4.01 m；西立面办公室 y 间距 5.13 m（= 轴网 U 间距）'},
     {'module_m': '4.0（北）/ 5.13（西、东）', 'structural_grid_m': 'V: 4.0 ×3, 5.25 ×8；U: 5.12–5.13 ×8', 'partition_meets_window': '砌体立面：隔墙落在窗间墙上（窗 1.81 居中于 4.0 开间）；幕墙立面上是会议室，开间 5.5–9.7 m 不是 1.5 的整倍数'},
     True, 'mixed', '砌体立面上隔墙都接在窗间墙上（must 满足）；但装修模数 4.0 / 5.13 m 与书中 1.50 / 1.35 m 无关，南立面会议室开间也与 1.5 m 幕墙栅格不对齐（should 不满足）。',
     ['IfcGrid 1eRexCEkCEkvyyokOUrlKP V axes x = -13.01, -9.01, -5.01, -1.01, 4.24, 9.49 … 40.99', 'IfcCurtainWall 0ruFImLAb9LfetxTnYmgTV "Raster 1.5 x 3.0m"', 'IfcSpace Office 0Cf3vwOoj5UOMjVSWR4C4X/4Y x 10.53–14.36 / 14.54–18.37'])

inst('R17', {'building.usage': 'office', 'plan_type': '不是中廊式（见 R15）'}, {'building_depth_m': 51.4}, False, 'not_applicable',
     '规则针对中廊式办公楼的 12–13 m 进深；本楼是 51 m 进深的环廊 + 核心大开间，不属于该类型。', ['slab bbox 54.4 × 51.4'])

inst('R18', {'building.usage': 'office', 'n_ws': WS, 'floor_area_per_storey_m2': {'Level 1 spaces total': 2272, 'Level 3': 2321}},
     {'gross_area_per_ws_m2': {'Level 1': round(2272 / 75, 1), 'Level 2': round(2272 / 66, 1), 'Level 3': round(2321 / 66, 1)}, 'direct_ws_area_m2': {'Level 1': 12.3, 'Level 2': 14.0, 'Level 3': 14.3}},
     True, 'pass', '每工位 30–35 m² 总面积、12–14 m² 直接工位面积，都落在书中 23–45 / 11–15 的区间内。注意 Hall 本身 600 m²（26% 的楼层面积）是交通面积，拉高了总值。',
     ['Furniture_Desk count per storey via derived contains edges: 75 / 66 / 66', 'space areas = mesh volume / 2.75'])

inst('R19', {'building.usage': 'office', 'L_building_m': 54.4, 'd_boundary': 'unknown (no plot)'},
     {'L > 40': True, 'fire_walls': '无：425 面 IfcWall 都没有 Pset_WallCommon.FireRating；材料为 MW 17.5 / MW 24 / MW 36.5 砖墙和 GK 10 石膏板'},
     True, 'unknown', '建筑长 54.4 m > 40 m，按规则必须有一道防火墙分区；模型里没有任何墙带 FireRating，也看不出贯通到屋面的 F 90 A 墙，无法判定——这是学生模型典型的缺失。',
     ['IfcWall props keys: IsExternal, LoadBearing, Reference only', 'slab bbox x -13.2…41.2 (54.4 m)'])

inst('R20', {'building.usage': 'office', 'storeys_above_ground': 4, 'class': '未知（无 FireRating、无建筑等级）'},
     {'loadbearing_elements': 'MW 24 cm 砖墙 ×145 (LoadBearing=True), STB d=30 混凝土柱 ×48, STB 20 楼板'}, True, 'unknown',
     '承重构件材料（砖、混凝土）本身是不燃的，但模型没有耐火等级，规则要求的 F 90 / 阻燃判定做不了。',
     ['IfcWall 2mLzcJrvn1oQkXVPlODKcG Basic Wall:MW 24cm LoadBearing=True', 'IfcColumn STB Stütze - rund:STB d=30_loadbearing ×48'])

inst('R21', {'external_walls': 'Basic Wall:MW 36.5 ×16 (Level -1…2), material "MW - Ziegel, verputzt"', 'curtain_walls': 'Level 1–3 南立面 + Level 3 全周 Curtain Wall（材料未给）', 'roof': 'Floor:STB 20.0 - roof (Beton C 20/25)'},
     {'external_wall_material_class': '砖 + 抹灰 → 不燃', 'facade_cladding': '无饰面层/保温层（单层墙）', 'roof_covering': '混凝土板，覆盖层未建模'}, True, 'pass',
     '砌体外墙和混凝土屋面都是不燃材料，满足外墙不燃、屋面硬屋面的要求；幕墙材料未建模，按玻璃+金属也不燃。无外墙饰面层，故饰面难燃的要求不触发。',
     ['IfcWall 20yioNqezEKwcckzHyn2BX Basic Wall:MW 36.5 IsExternal=True material MW - Ziegel, verputzt', 'IfcSlab 329wVB92v7LvgBS$H3YgMN material Beton - C 20/25'])

inst('R47', {'slabs': 'Floor:STB 20.0 ×4 (0.20 m solid RC, Beton C 20/25)', 'grid': 'U 5.12–5.13 m, V 4.0 / 5.25 m'},
     {'span_m': '5.13 / 5.25（柱网）', 'slab_type': 'solid RC 20 cm'}, True, 'pass', '实心钢筋混凝土板跨 5.1–5.25 m，在书中实心板 2.5–5.5 m 的范围内。',
     ['IfcSlab 2nhEwnQ65A$gVm19oF6B3_ Floor:STB 20.0 thk 0.2', 'IfcGrid U spacing 5.12…5.13'])

inst('R48', {**BUILDING}, {'GFZ_numerator_m2': '4 个完整地上楼层 × ≈2444 = 9776（地下室不计）', 'plot_area': 'unknown'}, True, 'unknown',
     '按规则口径能算出容积率的分子（≈ 9776 m²），但没有地块面积，GFZ、GRZ 都算不出。', ['floor slab areas 2444–2455 m² (mesh volume / 0.2)'])

inst('R49', {'spaces (Level 1)': {'Office/Outer/Open-plan': 22, 'Conference': 9, 'Tea kitchen': 4, 'Bathroom': 8, 'Storage': 4, 'Stairs': 5, 'Hall': 1}},
     {'NF usable (m²)': '办公 925 + 会议 391 + 茶水 95 + 卫生 122 + 储藏 48 = 1581', 'VF traffic (m²)': 'Hall 599 + Stairs 92 = 691', 'TF technical (m²)': '0（无设备用房、无管井）', 'rentable': '≈ NF 1581（楼梯、Hall 不计）'},
     True, 'pass', '53 个房间都能按名称落入 DIN 277 的三类；本层没有设备面积，是学生模型常见的缺项（没有机房、管井）。交通面积占 30%，偏高。',
     ['space areas from mesh; names Office / Conference / Tea kitchen / Bathroom / Storage / Stairs / Hall'])

inst('R50', {'storeys': STOREYS, 'slab_area_m2': 2444}, {'BRI_m3': '2444 × 3.1 × 5 层（含地下室）≈ 37 900', 'NRI_m3': 'Level 1–3: 2272 × 2.75 × 3 ≈ 18 700（Level 0/-1 无房间）'}, True, 'pass',
     '层高 3.1 m（楼面面层顶到上层楼面面层顶）直接由 Elevation 差得到，毛体积可算；净体积只能算有 IfcSpace 的三层。',
     ['IfcBuildingStorey Elevation -3.1 / 0 / 3.1 / 6.2 / 9.3 / 12.4'])

# ───────────── Storey ─────────────
STAIR = {'IfcStair': '20 个 HALF_TURN_STAIR（5 个楼梯间 × 4 个层间），每个 2 段 IfcStairFlight + 1 个 IfcSlab LANDING + 2 个 IfcRailing',
         'Pset_StairFlightCommon': 'RiserHeight 0.1937, TreadLength 0.27, NumberOfRiser 8 / run (16 per storey), NosingLength 0.03'}
inst('R03', STAIR, {'r_cm': 19.37, 't_cm': 27.0, '2r+t_cm': 65.7, 'pitch_deg': 35.7}, True, 'fail',
     '2r + t = 65.7 cm，刚好超出 59–65 cm 的上限 0.7 cm；坡度 35.7° 也比最省力的 30° 陡。原因是 3.1 m 层高被分成 16 级（19.4 cm）而踏面只给了 27 cm。',
     ['IfcStair 22FAsQIwT60AUDe0twn$X0 Pset_StairCommon.RiserHeight=0.1937 TreadLength=0.27', '16 × 0.1937 = 3.10 = storey height'])

inst('R04', {**STAIR, 'storey_h_m': 3.1}, {'n_riser_per_run': 8, 'landing': 'IfcSlab "Monolithic Landing" 每梯 1 个', 'landing_width_vs_flight': '平台 1.545 × 3.571 对 1.5 m 梯段；1.045 × 2.19 对 1.0 m 梯段'}, True, 'pass',
     '层高 3.1 ≥ 2.75 m，确有休息平台；每段 8 级在 3–18 之间；平台宽度与梯段宽相同（1.5 / 1.3 / 1.0）。',
     ['IfcSlab Cast-In-Place Stair:Stair:491267 Landing 1 size 1.545 × 3.571', 'IfcStairFlight Run 1 NumberOfRiser=8'])

inst('R05', {**STAIR, 'building.public_access': 'office → 视为公众可达', 'flight_widths_m': {'1.5': '2 个楼梯间 (491267, 492899, 761129, 761164, 761382 …)', '1.3': '1 个楼梯间 (493197, 761199 …)', '1.0': '2 个楼梯间 (493681, 494608, 761228, 761262 …)'}},
     {'w_min_m': 1.0, 'r/t': '19.4/27', 'n_rail_per_stair': 2, 'rail_height_m': 1.2192}, True, 'mixed',
     '五个楼梯间宽度 1.5 / 1.3 / 1.0 m 都 ≥ 1.00 m（两个只刚好达标）；每个楼梯 2 道栏杆（内外侧）满足两侧扶手；但踏步比 19.4/27 比 17/28 陡，见 R25。',
     ['IfcStairFlight Cast-In-Place Stair:Stair:493681 Run 1 size 1.935 × 1.0', 'IfcRailing 22FAsQIwT60AUDe0twnm9R Pset_RailingCommon.Height=1.2192'])

inst('R06', {'railings': 'IfcRailing Railing:Stahl (4) - Vertikal ×40, Pset_RailingCommon.Height = 1.2192', 'drop_m': '楼梯间内坠落高度 ≤ 3.1 m/层，总高 15 m < 12 m 仅在顶部楼梯超出'}, {'h_rail_m': 1.22, 'required_m': '0.90（< 12 m）/ 1.00（工作场所）'}, True, 'pass',
     '栏杆高 1.22 m（4 ft，Revit 默认）高于 0.90 / 1.00 m 的要求；即使按 > 12 m 的 1.10 m 也满足。', ['IfcRailing Pset_RailingCommon.Height=1.2192 (all 40)'])

inst('R22', {'storeys': 'Level 1–3 各 53 个房间，一个使用单元', 'stairs': '5 个楼梯间，每层各有 IfcSpace "Stairs"（10.5–29 m²）', 'exits': 'Level 0 两个外门：旋转门 2.4 m + 双扇门 1.81 m'},
     {'n_escape_routes_per_storey': 5, 'independent': '5 个楼梯间分布在四角 + 南侧中部'}, True, 'pass',
     '每层有 5 条经封闭楼梯间的独立疏散路线，远多于 2 条；楼梯间彼此距离 30–40 m。', ['IfcSpace Stairs 0Cf3vwOoj5UOMjVSWR4BwQ / Bw7 / Bw0 / BwD / BwE (Level 1)', 'stairs centres (-9.9,-22.7) (-3.1,8.2) (38.4,8.2) (38.3,-24.3) (19.8,-22.5)'])

inst('R23', {'building.usage': 'office', 'doors to Hall from office/conference (Level 1)': 48, 'stair_spaces': 5},
     {'d_walk_max_m': 24.4, 'd_walk_median_m': 16.2, 'stair_spacing_m': '约 30–42 m（相邻楼梯间中心距）', 'n_over_35': 0}, True, 'pass',
     '从每扇办公/会议室门到最近楼梯间的曼哈顿距离最大 24.4 m，远小于 35 m；楼梯间间距与书中“端部 30 m、彼此 60 m”的经验一致。房间内部到门的距离未计（单间 ≤ 5 m，大开间最多约 12 m，仍 < 35）。',
     ['derived: door bbox centre → nearest Stairs-space centre (|dx|+|dy|)'])

inst('R24', {'stairs': '每个楼梯都在名为 Stairs 的 IfcSpace 内', 'stair_doors (Level 1)': '2.01 m 双扇金属门 ×4 (Stairs↔Hall), 1.0 m 单扇门 ×6 (Stairs↔Storage / Conference / Hall)', 'exit_at_ground': 'Level 0 没有 IfcSpace，无法核对楼梯间到室外出口'},
     {'enclosed': True, 'exit_width_vs_stair_width': '门 2.01 / 1.0 m vs 梯段 1.5 / 1.3 / 1.0'}, True, 'mixed',
     '主楼梯都在封闭的楼梯间内，有门隔开（满足）；但有 3 个楼梯间从 Storage 进入、1 个经会议室进入，不是直接的疏散走道；门的防火/自闭属性没有建模。',
     ['IfcDoor 0nGWV7aUj0IR6cvT_6f$lU Simple door - 2 sides - metal 2.01 opensTo Stairs, Hall', 'IfcDoor simple_door_1door_var2 1.0 opensTo Storage, Stairs ×3'])

inst('R25', STAIR, {'w_m': '1.0–1.5', 'r_cm': 19.37, 't_cm': 27}, True, 'fail',
     '踢面 19.37 cm 超过必要楼梯 r ≤ 19 cm 的限值（0.37 cm），踏面 27 ≥ 26 满足，宽度 ≥ 100 满足。把每层 16 级改成 17 级（18.2 cm）即可。',
     ['Pset_StairFlightCommon.RiserHeight=0.1937 on all 40 flights'])

inst('R26', {'building.usage': 'office', 'stairs': STAIR['IfcStair'], 'grand_stair': '无（所有楼梯都是封闭楼梯间内的双跑梯）'}, {'r/t': '19.4/27, 35.7°', 'nosing_m': 0.03}, True, 'mixed',
     '双跑梯、有平台，便于快速通行；但 3 cm 的踏步突缘（NosingLength 0.03）与无障碍建筑“不得有突缘”的要求相抵触。', ['Pset_StairFlightCommon.NosingLength=0.03 (15 flights), 0.0 (STB 12.0 basement stairs)'])

inst('R27', {'building.public_access': 'office', 'entrance': 'Level 0 = 0.0 = IfcSite.RefElevation（无台阶）', 'lifts': '17 个 IfcBuildingElementProxy "M_Electric Lift- wall based 2100 x 1100mm"（6 组：3+3+3+3+3+2），Level -1/0 各 17 扇 1.16 m 电梯门'},
     {'step_free_entrance': True, 'all_storeys_by_lift': '电梯门只建在 Level -1 和 Level 0；Level 1–3 没有电梯门，轿厢实体只放在 Level 1'}, True, 'mixed',
     '入口无台阶、有电梯，原则上各层可无台阶到达；但电梯在 Level 1–3 没有任何门或井道，说明电梯只是“摆了个符号”，不能证明各层可达。',
     ['IfcBuildingElementProxy 3_cOKxIPX2YAr1dOe577AN M_Electric Lift- wall based (Level 1, xyz -6.83,-16.08,3.1)', 'IfcDoor 2hkbLK$WHF6ACzlr$c5tWk TU SF 2 - Lift Zentral 1.16 m (Level 0)'])

inst('R28', {'lifts': '17 × 2.1 × 1.1 m 轿厢（proxy 尺寸）', 'lift_doors': 'Level 0: 1.16 m 宽，位于 Hall 环廊侧', 'waiting_area': 'Level 0 无 IfcSpace，门前为开放大厅'}, {'car_w×d_m': '1.1 × 2.1 ≥ 1.10 × 1.40', 'movement_area': '门前为 ≥ 3 m 宽大厅，不与楼梯重叠'}, True, 'pass',
     '轿厢 1.1 × 2.1 m 满足 1.10 × 1.40；电梯门前是开放大厅，1.5 × 1.5 m 的活动区没有障碍；电梯组紧挨楼梯间，符合“与主楼梯组合布置”。',
     ['proxy name "2100 x 1100mm"', 'lift door bbox e.g. [-7.1,-20.4]…[-6.5,-18.5] next to Stairs space at (-9.9,-22.7)'])

inst('R29', {'ramps': '无 IfcRamp', 'level_changes': '入口 0.0 = 地坪'}, {}, False, 'not_applicable', '入口无高差，不需要坡道；模型里也没有坡道。', ['IfcRamp count 0'])

inst('R02', {'building.usage': 'office', 'IfcSpace': '159 个，Level 1–3', 'storey_h_m': 3.1, 'slab_thk_m': 0.2},
     {'h_space_m': 2.75, 'h_slab_to_slab_clear_m': 2.9}, True, 'pass',
     '所有房间的 IfcSpace 高度都是 2.75 m，正好等于 Vst 规定的 2.75（和 fantasy_office_building_1 一样，Revit 房间高度被设成这个值）；按楼板算的净高 2.9 m 也满足。',
     ['IfcSpace size_m[2] = 2.75 for all 159 spaces', 'Elevation 差 3.1 − slab 0.2 = 2.9'])

inst('R57', {'building.public_access': 'office', 'stairs_spaces': 'Stairs 房间 3.68 × 4.82 … 5.88 × 4.70 m，内含 2.9 × 2.2 … 3.4 × 3.6 m 的楼梯'}, {'free_depth_in_front_of_flight_m': '≈ 1.1–2.5（房间长减楼梯长）'}, True, 'mixed',
     '宽梯段（1.5 m）所在楼梯间前方剩余约 2.5 m，满足 1.50 m；1.0 m 梯段的楼梯间 4.9 × 4.8 内楼梯 2.9 × 2.2，剩余 ≈ 2.0 m 也够；但 3.68 m 长的楼梯间（Bw7）里 3.4 m 长的楼梯只剩约 0.3 m，不满足。',
     ['IfcSpace Stairs 0Cf3vwOoj5UOMjVSWR4Bw7 size 3.682 × 4.823', 'IfcStair 22FAsQIwT60AUDe0twn$X0 size 3.435 × 3.571'])

# ───────────── Zone ─────────────
inst('R11', {'building.usage': 'office', 'n_ws_per_storey': WS, 'bathrooms_per_storey': '8 个 Bathroom（13.9–22.1 m²），成对布置（4 对）', 'fixtures': '每间 1 个 Plumbing_Fixtures_Counter_Top_w-Sinks（1800 mm，3 盆）；没有 IfcSanitaryTerminal / WC 便器'},
     {'n_emp': '≈ 75 / 层', 'separate_m_f': '成对布置 → 推断男女分设', 'd_to_wc_max_m': '< 40（同层）', 'anteroom+cubicles': '每层 7 扇 0.585 m 的 Bathroom-only 门 = 隔间门；入口门 0.585 / 0.81 m'}, True, 'mixed',
     '厕所数量、分布、距离都满足（每层 8 间对 75 人远超书中比例）；结构上也有前室 + 隔间；但便器没有建模，n_wc / n_basin ≥ 1/5 无法核；隔间门 58.5 cm 过窄。',
     ['IfcSpace Bathroom 0Cf3vwOoj5UOMjVSWR4BZn / Bob (5.0 × 2.99 / 2.83, 相邻)', 'IfcFurniture Plumbing_Fixtures_Counter_Top_w-Sinks:1800x600x850mm ×21', 'IfcDoor 3956de_ov29AluAtiLorzT 0.585 m'])

inst('R30', {'unit': '每层一个使用单元 ≈ 2272 m²', 'corridor': 'Hall 599 m²，环形，宽 3.2 m（南侧 6.9 m）', 'side_walls': 'Basic Wall:MW 17.5（砖 17.5 cm 抹灰）/ GK 10.0 int（石膏板）'},
     {'unit.area ≥ 400': True, 'wall_fire_rating': 'FireRating 缺；砖墙 17.5 cm 通常 ≥ F 90，石膏板 10 cm 取决于构造', 'glazing_sill_m': '走廊侧无窗'}, True, 'mixed',
     '单元 ≥ 400 m²，Hall 是必要走廊；砖侧墙按材料足以达到 F 30，但有 93 面 GK 10 石膏板隔墙（部分在 Hall 侧）没有耐火数据。',
     ['IfcWall 2mLzcJrvn1oQkXVPlODKTE Basic Wall:MW 17.5', 'IfcWall 3956de_ov29AluAtiLorUz Basic Wall:GK 10.0 int constituents Gipskarton / Wärmedämmung / Gipskarton'])

inst('R31', {'units': '单租户（无 IfcZone，房间名无租户区分）'}, {}, False, 'not_applicable', '整层是一个使用单元，没有单元之间的分隔墙。', ['IfcZone count 0'])

inst('R32', {'bathrooms': '每层 8 间，隔间门 0.585 m ×7/层（Bathroom↔Bathroom）', 'fixtures': '只有洗手台（1800 mm 三盆）'},
     {'n_wc_per_unit': 'unknown（无便器）', 'n_basin': 3, 'urinal_visibility': 'unknown'}, True, 'unknown', '前室 + 隔间的结构在，但便器、小便器都没有建模，比例与视线要求无法判定。', ['IfcSanitaryTerminal count 0'])

inst('R33', {'building.usage': 'office', 'n_ws': WS, 'tea_kitchens_per_storey': '4 间，17.8 / 19.7 / 26.0 / 31.4 m²，含水槽台、柜、圆桌'}, {'ws_per_tea_kitchen': '≈ 19', 'area_each_m2': '18–31'}, True, 'pass',
     '每 19 个工位就有一间 18–31 m² 的茶水间，远超书中“每 50–100 工位约 10 m²”；分散在四个角，靠近工位。', ['IfcSpace Tea kitchen 0Cf3vwOoj5UOMjVSWR4Bvq (5.9 × 3.0)', 'Casework_Counter_Top_Corner_w-Sink ×9'])

inst('R34', {'per_storey': 'Storage ×4（8–19 m²），无名为 cleaning / Putzraum 的房间', 'central': 'Level 0/-1 无 IfcSpace'}, {'cleaning_room_per_storey': 'unknown（Storage 可能兼用）'}, True, 'unknown',
     '每层有 4 间储藏室，但没有一间标为保洁间（无拖把池/给水），中央垃圾房和物业用房在没有房间的地下室/底层无从判断。', ['IfcSpace Storage ×12'])

inst('R35', {'entrance (Level 0)': '旋转门 2.4 m + 双扇门 1.81 m，Level 0 无 IfcSpace', 'level_0_furniture': 'Stuhl-01 ×126, 6 人桌 ×21（餐厅），沙发组 ×5，圆桌 ×5；Cook Top ×15, Refrigerator ×12（厨房）', 'conference': '9 间会议室全在 Level 1–3'},
     {'canteen_near_entrance': True, 'conference_from_entrance': '需上一层', 'wheelchair_parking': 'unknown'}, True, 'mixed',
     '底层是入口 + 126 座餐厅 + 厨房，餐厅在门禁之外、靠近入口（满足）；会议区不在入口层，访客须上楼；轮椅停放位无法判断。',
     ['IfcDoor 07ayvKkmjF_vBCLJOpy$dk M_Door-Exterior-Revolving 2400 x 2100', 'IfcFurniture Stuhl-01:Typ1 ×126 on Level 0', 'IfcBuildingElementProxy M_Cook Top-2 Unit ×15'])

inst('R65', {'corridor': 'Hall 环廊，一圈周长约 150 m，单个 IfcSpace', 'doors_in_corridor': '无把 Hall 分段的门', 'stair_doors': '2.01 m 金属双扇门 / 1.0 m 单扇门，无 SelfClosing / SmokeStop 属性'},
     {'L_corridor_m': '≈ 150（环形）', 'segment_doors': 0}, True, 'fail', '150 m 的环廊没有任何分段门，远超 30 m；楼梯间门也没有自闭、防烟的属性。', ['IfcSpace Hall 599 m² bbox 47.5 × 40.3', 'Pset_DoorCommon only IsExternal / Reference'])

inst('R70', {'building.usage': 'office', 'perimeter': '外圈单间 16–20 m²（1–3 工位）', 'core': '中部两个 258 / 274 m² 的 Open-plan office（各 18 工位）', 'partitions': 'MW 17.5 砖墙 / GK 10 石膏板，无玻璃'},
     {'office.type': 'cellular + open-plan 混合，不是 combi'}, False, 'not_applicable', '外圈小单间 + 深核心区的骨架像组合式办公，但核心区放的是工位而非共用设施，隔墙也是实墙，所以不按 combi 规则判。', ['IfcWall type names: MW 17.5, MW 24cm, GK 10.0 int (no glass)'])

inst('R72', {'building.public_access': 'office', 'corridor': 'Hall 环廊，宽 3.17–3.18 m（南侧 6.9 m）'}, {'L_m': '≈ 150', 'passing_place': '整条走廊 ≥ 1.8 m 宽'}, True, 'pass',
     '走廊长 > 15 m，但全程 3.2 m 宽，任何位置都能供两辆轮椅会车。', ['Hall width = open-plan bbox − outer-office bbox: 3.18 / 3.18 / 3.17 / 6.89'])

inst('R87', {'building.usage': 'office', 'corridor': 'Hall（疏散通道）', 'furniture_in_hall (Level 1)': 'Table-chair-combination-01 (4 Sessel und 1 Tisch) ×2; Level 2/3 另有 Plumbing counter ×2'},
     {'furniture_in_escape_route': 2}, True, 'fail', 'Hall 是唯一的疏散走道，里面放了两组沙发+茶几（Level 2、3 还有洗手台）；按规则疏散通道内不得放家具。',
     ['derived contains: Hall 0Cf3vwOoj5UOMjVSWR4C67 ⊃ IfcFurniture 2QE2nhPBzBsBMKMEk0rCVA Table-chair-combination-01'])

# ───────────── Space ─────────────
inst('R09', {'building.usage': 'office', 'office rooms (Level 1)': {'Office': '15 间 16.4–38.4 m², 1–3 桌', 'Outer office': '5 间 11.8–40.7 m², 1–2 桌', 'Open-plan office': '2 间 257.7 / 274.2 m², 各 18 桌'}, 'n_ws': 75},
     {'direct_area_per_ws_m2': {'Office 单人': '16.5–18.6', 'Office 双/三人': '6.2–9.3', 'Open-plan': '14.3–15.2', 'Level 1 平均': 12.3}}, True, 'mixed',
     '平均 12.3 m²/工位落在 11–15 内；但分布两极：单人办公室 16–19 m² 偏大，而 3.8 × 4.9 m 的办公室里放 3 张桌（6.2 m²/人）过挤。',
     ['IfcSpace Office 0Cf3vwOoj5UOMjVSWR4C4X 18.6 m² contains Furniture_Desk ×3', 'Open-plan 0Cf3vwOoj5UOMjVSWR4C4K 257.7 m² contains Furniture_Desk ×18'])

inst('R10', {'building.usage': 'office', 'rooms': {'perimeter offices': '进深 3.3–5.0 m（有窗）', 'Outer office': '2.4 × 4.9 m，内部无窗', 'Open-plan office': '17.3 / 18.4 m 深，内部无窗', 'Conference (south)': '幕墙立面'}},
     {'d_max_daylit_m': 5.0, 'rooms_without_daylight': '2 Open-plan (36 工位) + 5 Outer office (6 工位) 每层'}, True, 'fail',
     '外圈办公室进深 ≤ 5 m 可自然采光；但每层 36 + 6 个工位在没有任何窗的内部房间里，完全靠人工照明。', ['opensTo: Open-plan office / Outer office 没有 IfcWindow', 'Office 窗 Windows_Concept_Sash 1810x1210 ×1/间'])

inst('R12', {'conference rooms (Level 1)': '9 间，22.8–92.6 m²，椅子 7–15 把'}, {'a_seat_m2': [3.4, 6.2, 4.3, 3.5, 3.0, 2.9, 3.7, 3.3, 3.4]}, True, 'pass',
     '每座 2.9–6.2 m²，都不低于 2.5 m²；92.6 m² 只放 15 把椅子的那间明显偏大（6.2 m²/座）。', ['IfcSpace Conference 0Cf3vwOoj5UOMjVSWR4Buo 92.6 m² contains Chair ×15 + Furniture_Table_Conference'])

inst('R36', {'building.usage': 'office', 'Open-plan office': '2 间 × 18 工位，17.3–18.4 m 深，四周被 Hall 包围，无外墙', 'group rooms': 'Office 3 桌间 = 3 工位'},
     {'n_ws': 18, 'd_to_window_max_m': '> 20（房间本身无窗，最近外墙隔着 Hall 和外圈房间）'}, True, 'fail',
     '18 工位属于组团办公的规模（4–16 略超），但工位到窗的距离远超 7.5 m——房间根本没有窗；按书中说法只有 ≥ 100 工位的大开间才可以完全依赖人工照明通风。',
     ['IfcSpace Open-plan office 0Cf3vwOoj5UOMjVSWR4C4K bbox -3.74…14.62 × -14.75…2.54; 外墙在 x=-13.2 / y=10.9'])

inst('R37', {'desks': 'Furniture_Desk 1830 × 915 ×150, 1905 × 815 ×45, 1525 × 762 ×12 (Student)'}, {'desk_w×d_cm': '183 × 92 / 191 × 82 / 153 × 76', 'free_area_per_ws': '单人间 ≥ 10 m² 空余；3 桌间约 2 m²/人'}, True, 'pass',
     '桌面 183 × 92 和 191 × 82 cm 都超过 120 × 80（屏幕工作）；153 × 76 的学生桌略小于 80 cm 深但宽度足够。活动面积每人 ≥ 1.5 m² 在所有房间都能满足。',
     ['IfcFurniture 0nGWV7aUj0IR6cvT_6f$Fm Furniture_Desk:1830x915x762mm'])

inst('R38', {'workrooms (Level 1)': {'Office ×14 有窗': '1 扇 1.81 × 1.21，窗台 0.9 m', 'Office ×1 (西南角)': '无窗', 'Outer office ×5': '无窗', 'Open-plan ×2': '无窗', 'Conference ×8 南侧': '幕墙（未作 IfcWindow）'}},
     {'window_width_over_wall_widths': '1.81 / (3.33 + 4.95) × 2 = 0.11', 'sill_m': 0.9, 'h_clear_m': 2.75}, True, 'mixed',
     '有窗的办公室：窗宽 1.81 m 占全部墙宽 16.6 m 的 11% ≥ 1/10，窗台 0.9 m 在视平线范围，净高 < 3.5 m 不触发 30% 条款——满足；但每层 8 个工作间（含两个大开间）完全无窗，违反“对外视线”的前提。',
     ['IfcWindow 0_5VnUY6L6cAJIW4T9UYqA 1810x1210, bbox z_min − Elevation = 0.9', 'Outer office 0Cf3vwOoj5UOMjVSWR4BxO opensTo 无窗'])

inst('R39', {'offices with window (Level 1)': '14 间，立面宽 3.7–4.95 m，窗宽 1.81 m；一间 8.3 m 宽的大办公室窗 1.81 m'}, {'window_width_ratio': '0.37–0.49（大办公室 0.22）', 'd_work_to_window_m': '≈ 2 × 1.21 = 2.4 推荐；实际桌子距窗 1–3 m'}, True, 'fail',
     '所有办公室的窗宽只占房间宽度的 37–49%，低于 65% 的要求；8.3 m 宽的办公室只有一扇窗（22%）。', ['Office 0Cf3vwOoj5UOMjVSWR4C4X width 3.833, window 1.81 → 0.47', 'Office (x -12.83…-6.92, y -36.70…-28.43) width 8.275, window 1.81 → 0.22'])

inst('R40', {'archive': '无名为 archive / Registratur 的房间；Storage ×4/层'}, {}, False, 'not_applicable', '模型没有档案室。', ['IfcSpace names'])
inst('R41', {'server room': '无'}, {}, False, 'not_applicable', '模型没有机房。', ['IfcSpace names'])

inst('R71', {'building.public_access': 'office', 'smallest rooms': 'Outer office 2.41 × 4.92 m，Storage 2.37 × 3.45 m，Bathroom 2.9 × 4.9', 'corridor': 'Hall 3.2 m 宽'}, {'turning_1.5×1.5_fits': '所有房间净宽 ≥ 2.37 m → 几何上放得下；家具后不保证', 'corridor_w_m': 3.2}, True, 'pass',
     '走廊 3.2 m ≥ 1.5 m；最窄的房间也有 2.37 m 净宽，1.5 × 1.5 的转身空间在几何上都放得下。', ['IfcSpace Outer office 0Cf3vwOoj5UOMjVSWR4BxO 2.408 × 4.918'])

inst('R83', {'rooms': '会议室 22.8–92.6 m²，h 2.75，7–15 座'}, {'V_per_person_m3': '22.8×2.75/7 = 9.0 … 92.6×2.75/15 = 17.0'}, True, 'pass',
     '每人 9–17 m³，高于讲话用厅 4 m³/人 的参考值（会议室按讲话算）。', ['Conference 0Cf3vwOoj5UOMjVSWR4Buo 92.6 m² × 2.75 / 15 chairs'])

inst('R88', {'building.usage': 'office', 'Open-plan office': '2 间，17.3 × 17.3 / 18.4 × 17.3 m'}, {'depth_m': '17.3–18.4', 'daylight': '无'}, True, 'mixed',
     '进深 17–18 m 略小于书中大空间办公典型的 20–30 m，但因为房间完全在内部，设备（通风、照明）成本的后果与书中描述一样成立。', ['Open-plan office size_m [18.36, 17.293] / [17.792, 17.293]'])

# ───────────── Element ─────────────
inst('R07', {'doors': {'office / conference 单扇': '1.0 m × 2.26–2.36 (M_Door 900 x 2200 ×54, simple_door ×66)', 'conference 双扇': '1.885 / 2.01 m', 'Bathroom 入口': '0.585 m ×14/层 + 0.81 m ×2/层', 'Bathroom 隔间': '0.585 m ×7/层', 'entrance': '旋转门 2.415 m + 双扇 1.81 m, 无台阶'}},
     {'h_clear_min_m': 2.11, 'w_clear_office_m': '≈ 0.9（OverallWidth 1.0 减框）', 'w_bathroom_entry_m': 0.585}, True, 'fail',
     '门高 ≥ 2.11 m 全部满足，办公室门净宽约 0.9 m 满足，入口无台阶且 1.81 m 双扇门满足；但每层 14 扇卫生间入口门只有 0.585 m（连 0.81 m 的也不够 0.90），无障碍不达标。',
     ['IfcDoor 3956de_ov29AluAtiLorzT Simple door - 1 side:68.5 x 2.26 OverallWidth=0.585 opensTo Bathroom, Hall', 'IfcDoor 0M1WK7UVP6_vWKl4OG5BoE M_Door 900 x 2200 OverallWidth=1.0', 'IfcDoor 12X206Tp141e7Q_D92prd4 Doors_ExtDbl_Flush 1.81 IsExternal'])

inst('R08', {'external_walls': 'Basic Wall:MW 36.5 ×16, material "MW - Ziegel, verputzt"（单层砖墙）', 'concrete_external_walls': '无（混凝土只用于柱、楼板、地下室楼梯）'}, {}, False, 'not_applicable',
     '外墙是砌体不是混凝土，规则不触发；单层砌体外墙的保温问题由 R95 处理。', ['IfcWall 20yioNqezEKwcckzHyn2BX material single: MW - Ziegel, verputzt'])

inst('R95', {'wall.IsExternal': 'Basic Wall:MW 36.5 ×16（Level -1…2）', 'layers': '单层："MW - Ziegel, verputzt"，无保温层、无空气层', 'Level 3': '全周幕墙'},
     {'single_leaf': True, 'material_high_insulation': 'unknown：材料名只说“砖、抹灰”，36.5 cm 是传统保温砖墙的厚度'}, True, 'mixed',
     '条件成立（单层外墙）；36.5 cm 砖墙是德国单层保温砌体的典型厚度，但材料名没有标明加气/多孔砖，也没有专用保温砂浆，无法确认“高保温材料”这一要求；没有附加保温层这一替代做法。',
     ['IfcWall 20yioNqezEKwcckzHyn2BX size 54.4 × 0.365 × 2.9', 'IfcMaterial "MW - Ziegel, verputzt"'])

inst('R42', {'door_widths_m': {'1.0': 135, '1.16 (lift)': 34, '0.585': 84, '0.81': 18, '1.3': 12, '1.885': 27, '2.01': 18, '1.81 / 2.415 ext': 2}}, {'multiples_of_125mm': '1000 ✓, 1250→1300 ✗, 810 ✗, 585 ✗, 1885 ✗'}, True, 'fail',
     '只有 1.0 m 的门洞是标准模数；0.585、0.81、1.3、1.885 都不是 125 mm 的整数倍，也不是 DIN 18100 的标准洞口。', ['IfcDoor OverallWidth distribution'])

inst('R43', {'exits (Level 0)': '旋转门 2.415 m（M_Door-Exterior-Revolving）+ 双扇平开门 1.81 m（Doors_ExtDbl_Flush）', 'occupants': '≈ 75 × 3 层 + 126 座餐厅 ≈ 350'}, {'usable_exit_width_m': '1.81（旋转门不计）', 'required_m': '350 / 150 × 1.0 ≈ 2.3'}, True, 'fail',
     '旋转门不能算紧急出口，只剩一扇 1.81 m 的双扇门，低于约 350 人所需的 2.3 m；且只有一个可用出口。地下室楼梯是否另有出口无法判断（Level -1 无房间、无外门）。',
     ['IfcDoor 07ayvKkmjF_vBCLJOpy$dk Revolving IsExternal=True', 'IfcDoor 12X206Tp141e7Q_D92prd4 ExtDbl 1810 IsExternal=True', 'IsExternal doors total = 2'])

inst('R44', {'windows': 'Windows_Concept_Sash / Plain_Sgl ×62，Fenstertür ×6；无 Pset_WindowCommon.ThermalTransmittance / 玻璃层'}, {'glazing': 'unknown'}, True, 'unknown', '窗的玻璃构造和 U 值都没有建模。', ['Pset_WindowCommon absent'])

inst('R45', {'roof': 'Floor:STB 20.0 - roof, bbox z 12.2–15.0（2.8 m 厚的“板”），材料 Beton C 20/25', 'pitch': 'Pset_SlabCommon.PitchAngle 缺'}, {'slope': 'unknown', 'vapour_barrier': '无材料层'}, True, 'unknown',
     '屋面被建成一块 2.8 m 厚的混凝土板，没有坡度和构造层信息，排水坡度和隔汽层都判不了。', ['IfcSlab 329wVB92v7LvgBS$H3YgMN size 54.3 × 51.4 × 2.8'])

inst('R46', {'partitions': 'GK 10.0 int ×93（Gipskarton / Wärmedämmung - Hart / Gipskarton），MW 17.5 ×171', 'raised_floor / ceiling': '未建模（房间高 2.75 vs 结构净高 2.9 → 隐含 15 cm 吊顶或面层）'}, {'partition_to_slab': '墙高 3.1 = 层高 → 隔墙到结构楼板'}, True, 'pass',
     '隔墙高度等于层高 3.1 m，说明隔墙延续到结构楼板，满足“隔墙在竖向延续”；石膏板墙的隔声构造无数据。', ['IfcWall 3956de_ov29AluAtiLorUz GK 10.0 int height 3.1'])

inst('R98', {'external elements': 'MW 36.5 砖墙，STB 20 屋面板', 'material λ': '无 Pset_MaterialThermal', 'ThermalTransmittance': '只有 1 扇门有'}, {'U': 'unknown'}, True, 'unknown', '没有导热系数，U 值算不出，也没有可核对的 ThermalTransmittance。', ['Pset_DoorCommon.ThermalTransmittance on 1 door only'])

inst('R102', {'grid': 'V 4.0 ×3 + 5.25 ×8；U 7.2, 2.8, 5.12–5.13 ×8', 'wall_thicknesses_cm': '17.5 / 24 / 36.5（砖标志尺寸）'}, {'grid_mod_100mm': '4000 ✓, 5250 ✗, 5125 ✗', 'wall_nominal': '24 = 25 − 1 灰缝, 36.5 = 37.5 − 1 → 符合砖模数'}, True, 'mixed',
     '墙厚 24 / 36.5 cm 正是书中“模数 25 cm 减 1 cm 灰缝 = 标志尺寸 24 cm”的做法；但柱网 5.25 / 5.125 m 不是 100 mm 模数的整倍数（5125 更像 1/8 英尺制的残留）。',
     ['IfcGrid 1eRexCEkCEkvyyokOUrlKP axis spacing', 'IfcWall type names MW 17.5 / MW 24cm / MW 36.5'])

# ───────────── groups that do not apply (one summary instance each) ─────────────
NA_RES = ['R51', 'R54', 'R55', 'R56', 'R58', 'R59', 'R63', 'R66', 'R67', 'R68', 'R69', 'R73', 'R74', 'R75', 'R76', 'R77', 'R78', 'R79', 'R80', 'R81', 'R82', 'R91', 'R92', 'R101']
for rid in NA_RES:
    inst(rid, {'building.usage': 'office（房间名：Office / Conference / Tea kitchen / Open-plan office；无住宅房间）'}, {}, False, 'not_applicable',
         '住宅规则；本楼没有住宅单元、卧室、户门或分户墙。' if rid != 'R82' else '卫生间类型判定需要 IfcSanitaryTerminal；本模型只有洗手台家具、没有便器/淋浴/浴缸。',
         ['IfcSpace names (Level 1–3)', 'IfcZone count 0'] if rid != 'R82' else ['IfcSanitaryTerminal count 0'])
for rid in ['R52', 'R53', 'R60', 'R61', 'R62', 'R64', 'R94', 'R103']:
    inst(rid, {'building.is_high_rise': False, 'H_top_m': 9.3}, {}, False, 'not_applicable', '高层规则；最高有人停留楼层 9.3 m < 22 m（见 R01）。', ['IfcBuildingStorey Level 3 Elevation=9.3'])
for rid, why in [('R84', '餐饮厨房在 Level 0（Cook Top ×15, Refrigerator ×12），但 Level 0 没有 IfcSpace，员工数未知；休息室无从判断。'),
                 ('R85', '不是高校建筑。'), ('R86', '不是高校建筑。'), ('R89', '桌子的朝向可从 ObjectPlacement 读出，但屏幕家具没有建模；本轮未做。'),
                 ('R90', '没有收发室。'), ('R93', '每层有 5 条楼梯疏散路线，不需要把窗当第二疏散路线。'), ('R96', '外墙是单层砖墙，不是夹心墙。'), ('R97', '外墙没有背通风外挂层。'),
                 ('R99', '屋面无种植层。'), ('R100', '平屋面（混凝土板），不是坡屋面。')]:
    inst(rid, {'note': why}, {}, False, 'not_applicable' if rid not in ('R84', 'R89') else 'unknown', why, ['see facts above'])


def main():
    ids = [i['iid'] for i in I]
    assert len(ids) == len(set(ids))
    rids = {json.loads(l)['rid'] for fn in ('rules_pilot.jsonl', 'rules_office.jsonl', 'rules_general.jsonl') for l in open(os.path.join(HERE, fn), encoding='utf-8')}
    missing = sorted(rids - {i['rid'] for i in I}, key=lambda r: int(r[1:]))
    with open(OUT, 'w', encoding='utf-8') as fh:
        for i in I:
            fh.write(json.dumps(i, ensure_ascii=False) + '\n')
    from collections import Counter
    print(f'{len(I)} instances → {OUT}', dict(Counter(i["verdict"] for i in I)))
    print('rules without instance:', missing)


if __name__ == '__main__':
    main()

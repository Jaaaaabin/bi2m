"""Office rules: Neufert knowledge rewritten as context → requirement rules (no IFC mapping yet).

Every quote is checked verbatim against embeddings.sqlite before the file is written; the build fails on a mismatch.
Scope: what a student office BIM model at early design stage (like fantasy_office_building_1) would touch.

python3 rules/build_rules_office.py
"""
import json, os, re, sqlite3, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..')
OUT = os.path.join(HERE, 'rules_office.jsonl')

def q(page, quote):
    return {'book_page': str(int(page[-4:]) - 12), 'page': page, 'quote': quote}

R = []
def rule(rid, title, level, modality, entity, match, derive, condition, requirement, params, basis, ifc_needed, notes='', frm=(), priority=2, chapter=''):
    R.append(dict(rid=rid, **{'from': list(frm)}, level=level, modality=modality, title=title, priority=priority, chapter=chapter,
                  context=dict(entity=entity, match=match, derive=derive), condition=condition, requirement=requirement, params=params,
                  basis=basis, ifc_needed=ifc_needed, notes=notes))

# ───────────────────────── Site & Building ─────────────────────────
rule('R13', '退距深度按墙高计算', 'Site & Building', 'must', 'IfcBuilding / IfcSite',
     {'building.external_wall': '任一外墙', 'site.plot_boundary': '地块边界已知'},
     {'H': '墙高：室外地面至墙顶或墙与屋面覆盖层交线，垂直于墙面量；坡度 ≤ 70° 的屋面高度按 1/3 计入，≥ 70° 全部计入',
      'd': '外墙到地块边界的垂直距离', 'zone': '用地性质（一般 / 商业或工业）'},
     'always (within context)',
     '一般地区 d ≥ 0.4 × H 且 ≥ 3 m；商业、工业区 d ≥ 0.2 × H 且 ≥ 3 m；建筑等级 1、2 且地上不超过三层时 3 m 即可；退距须在本地块内（可延伸到公共道路、绿地、水域的中线）',
     {'factor_general': 0.4, 'factor_commercial': 0.2, 'min_m': 3, 'roof_share_below_70deg': '1/3'},
     [q('page_0076', 'According to the model building regulations (MBO), it is 0.4 × H, but at least 3 m (0.2 × H, min. 3 m for commercial and industrial areas). In front of the outside walls of building classes 1 and 2 with not more than three overground storeys, 3 m depth is also sufficient.'),
      q('page_0076', 'Wall height means the dimension from ground level to upper extent of the wall or to the intersection of the wall with the roof covering'),
      q('page_0076', 'The height of roofs with a pitch of ≤70° is included to one third, ≥70° fully with the wall height'),
      q('page_0076', 'Setback areas must be on the plot itself')],
     ['IfcSite 地块边界（IFC 里通常没有，学生模型多半缺）', 'IfcWall IsExternal + 几何高度', 'IfcRoof 坡度', 'IfcSite.RefElevation'],
     '学生模型一般没有地块边界，只能算出 H 和所需退距，判定留空。', frm=['K05'], priority=3, chapter='Basics · Building regulations')

rule('R14', '办公楼朝向与北向房间', 'Site & Building', 'should', 'IfcBuilding / IfcSpace',
     {'building.usage': 'office', 'space.function': 'office / working space', 'space.window_orientation': '房间采光面朝向（需 IfcSite TrueNorth）'},
     {'axis': '建筑长轴方向', 'has_corridor': '平面是否为走廊式（单排 / 双排）'},
     'space.window_orientation = N',
     '北向办公室只在无走廊式平面中可接受；长轴东西向可避免早晚低角度阳光干扰、南向易用遮阳（美国 90% 的办公楼如此），按 Joedicke 则长轴南北向以保证所有房间都有日照',
     {'north_rooms_ok_only_if': 'layout without corridor', 'main_axis_usa': 'E/W'},
     [q('page_0253', 'North-facing rooms are acceptable only for layouts without a corridor.'),
      q('page_0253', 'According to Rosenauer, 90% of all office buildings in the USA have a main axis E/W, because the deeply penetrating morning and evening sun is a disturbance. Sun from the south can be shaded more easily with sun blinds.')],
     ['IfcSite.TrueNorth / RefLatitude', 'IfcSpace 几何与外墙面', '平面类型（推断）'],
     '书中两种朝向说法并存（Rosenauer 东西 / Joedicke 南北），只有“北向房间仅限无走廊平面”是明确的判定句。', frm=[], priority=1, chapter='Office buildings · Access')

rule('R15', '单排、双排、三排平面与建筑类型', 'Site & Building', 'should', 'IfcBuilding',
     {'building.usage': 'office'},
     {'layout': '按每层房间相对走廊/核心的排数判断：single-row / two-row / three-row（中部暗区设服务核心）', 'is_high_rise': 'R01 的结果', 'room_depth': '办公室进深'},
     'always (within context)',
     '双排是行政办公楼的标准解，单间和小办公室都能自然采光；单排不经济、不生态，只有办公室很深时可接受；三排（中部大服务区）通常只对高层合适',
     {'standard': 'two-row', 'single_row': 'only with deep office rooms', 'three_row': 'high-rise only'},
     [q('page_0253', 'Two-row layouts have mostly been used for administration buildings until now; single rooms and small offices are possible with daylight'),
      q('page_0253', 'Single-row layouts are unecological, and only acceptable with deep office rooms (daylight?)'),
      q('page_0253', 'Single-row layout is normally uneconomical'),
      q('page_0253', 'A large supply zone at the centre of the building is normally practical only for high-rise buildings (greater proportion of vertical transport).')],
     ['IfcSpace 平面布置（推断排数）', 'IfcBuildingStorey.Elevation（高层判定）'],
     'fantasy_office_building_1 是两条办公长条夹一个中庭，不属于三种之一；规则要允许 “atrium” 作为第四种结果。', frm=['K133'], priority=2, chapter='Office buildings · Access')

rule('R16', '网格模数：装修网格 = 立面网格，1.50 / 1.35 m', 'Site & Building', 'must/should', 'IfcGrid / IfcCurtainWall / IfcWall',
     {'building.usage': 'office'},
     {'facade_module': '立面竖梃间距（IfcCurtainWall / IfcWindow 轴距）', 'fitout_module': '隔墙可接驳位置的间距', 'office_type': 'single-room / combi'},
     'always (within context)',
     '装修（隔墙）网格必须与立面网格一致，隔墙才能接到窗上（must）；结构网格可以与装修网格错开；模数宜取单间办公 1.50 m、组合办公 1.35 m（should）；1.50 m 模数下工位进深 2.20 m（桌 0.80 + 活动 1.00 + 后柜 0.40），含 10 cm 墙厚得 4.40 m 净房间；1.35 m 模数下 3.80 m 开间（约 18 m²）能布置所有常见工位',
     {'module_single_m': 1.5, 'module_combi_m': 1.35, 'workstation_depth_m': 2.2, 'room_clear_1_50_m': 4.4, 'room_width_1_35_m': 3.8},
     [q('page_0252', 'The fitting out and façade grids must be the same in order to enable the partitions to connect to the windows.'),
      q('page_0252', 'The structural grid can be offset against the fitting out grid. This reduces the problem of connecting the partitions to columns, but loses space in the rooms, which contain columns.'),
      q('page_0252', 'The modular dimensions, which have proved successful in recent years, are 1.50 m for single-room offices and 1.35 m for office types based on the combi principle.'),
      q('page_0252', 'Workstation depth 2.20 m (80 cm desk, 1 m movement area, 40 cm shelf behind). With 10 cm wall thickness, this gives 4.40 m clear room space.'),
      q('page_0252', 'Room widths of 3.80 m (~18 m^2 usable area) enable:')],
     ['IfcGrid（模型里常没有）', 'IfcCurtainWall 竖梃 IfcMember 的间距', 'IfcWall 隔墙端点与竖梃位置'],
     'fantasy_office_building_1 的幕墙类型叫 “Fassade:Raster 1.5 x 3.0m”，模数 1.50 可直接从类型名读出。', frm=['K131', 'K132', 'K115'], priority=3, chapter='Office buildings · Grid')

rule('R17', '中廊式办公楼的建筑进深', 'Site & Building', 'typical', 'IfcBuilding',
     {'building.usage': 'office', 'layout': 'two-row with central corridor'},
     {'depth': '建筑进深（垂直于走廊方向的外墙间距）', 'module': '网格模数'},
     'always (within context)',
     '中廊式办公楼通常进深 12–13 m；网格 1.35 m 配进深 13.40 m 对组合办公经济、对单间办公则房间过深；网格 1.50 m 配进深 12.50 m 对单间或组合办公都经济，但公共区窄、靠窗工位少 10%',
     {'depth_m': [12, 13], 'combi': {'module': 1.35, 'depth': 13.4}, 'single': {'module': 1.5, 'depth': 12.5}},
     [q('page_0252', 'The usual depth of buildings with central corridors is 12–13 m.'),
      q('page_0252', 'Grid module 1.35 m, building depth 13.40 m, an economical form of building for combi-offices, but for single offices this produces deep and badly proportioned rooms.'),
      q('page_0252', 'Grid module 1.50 m, building depth 12.50 m, an economical form of building for single offices or for combi-offices; this provides a narrow communal zone and 10% fewer workstations at the window than with ②.')],
     ['IfcSlab / IfcWall 外轮廓', '平面类型（推断）'],
     '', frm=['K116', 'K132'], priority=2, chapter='Office buildings · Grid')

rule('R18', '每工位的附属面积与总面积', 'Site & Building', 'typical', 'IfcBuilding',
     {'building.usage': 'office'},
     {'n_ws': '全楼工位数（办公桌数）', 'a_by_function': '各功能房间净面积之和 / n_ws：卫生、会议、档案、储藏、餐饮、入口、收发、机房、交通'},
     'n_ws ≥ 1',
     '每工位平均毛面积参考：直接工位 11–15（均 13）、附加 1.5–4.2；卫生 0.6–0.8、会议/培训 0.3–1.0、档案 0.4–1.0、储藏 0.4–1.5、餐饮/茶水 0.6–1.6、入口 0.2–0.7、收发 0.3–0.5、机房 0.5–1.5；结构 1.9–3.8、设备 2.4–4.6、交通 2.2–6.0；合计每工位 23–45 m²',
     {'workstation': [11, 15], 'sanitary': [0.6, 0.8], 'conference': [0.3, 1.0], 'archive': [0.4, 1.0], 'stores': [0.4, 1.5], 'canteen_tea': [0.6, 1.6], 'entrance': [0.2, 0.7], 'post': [0.3, 0.5], 'server': [0.5, 1.5], 'construction': [1.9, 3.8], 'services': [2.4, 4.6], 'traffic': [2.2, 6.0], 'total': [23, 45]},
     [q('page_0250', 'Workstation | Immediate workstation | 11–15 | 13 | 15.5'),
      q('page_0250', 'Subsidiary areas | Sanitary facilities | 0.6–0.8 | 0.7'),
      q('page_0250', ' | Conference/training | 0.3–1.0 | 0.6'),
      q('page_0250', ' | Archive | 0.4–1.0 | 0.6'),
      q('page_0250', ' | Canteen, cafeteria, tea kitchen | 0.6–1.6 | 1.1 | 9.0'),
      q('page_0250', ' | Entrance area | 0.2–0.7 | 0.4'),
      q('page_0250', 'Building | Construction area | 1.9–3.8 | 3.0 | 10.5'),
      q('page_0250', ' | Traffic area | 2.2–6.0 | 4.5'),
      q('page_0250', ' | Stores | 0.4–1.5 | 0.6 | '), q('page_0250', ' | Post room | 0.3–0.5 | 0.4 | '), q('page_0250', ' | Server room | 0.5–1.5 | 1.0 | '), q('page_0250', ' | Building services | 2.4–4.6 | 3.0 | '),
      q('page_0250', 'The total space requirement per workstation varies between 23 and 45 m^2, depending on organisational and status requirements.')],
     ['IfcSpace.LongName 分功能汇总 NetFloorArea', 'IfcFurniture 桌子计数'],
     '与 R09 的区别：R09 是单个房间口径，这里是整栋楼口径。', frm=['K141', 'K113'], priority=2, chapter='Office buildings · Additional areas')

rule('R19', '防火分区 ≤ 40 m 与防火墙', 'Site & Building', 'must', 'IfcBuilding / IfcWall',
     {'building.any': True},
     {'L': '建筑最大连续长度', 'd_boundary': '外墙到地块边界距离', 'compartment_walls': '标为防火墙的 IfcWall（FireRating ≥ F 90, 不燃）'},
     'L > 40 m 或 d_boundary < 2.50 m',
     '须设防火墙把建筑划成不超过 40 m 的防火分区；距地块边界 < 2.50 m 的外墙须为防火墙；防火墙须 F 90 A（防火、受火稳定、不燃），从基础连续到屋面以上 ≥ 30 cm（软屋面和工业建筑 ≥ 50 cm）；防火墙上原则上不开口，建筑内部的防火墙可开口但须自闭防火门 T 90',
     {'compartment_max_m': 40, 'boundary_min_m': 2.5, 'rating': 'F 90A', 'above_roof_cm': 30, 'door': 'T 90'},
     [q('page_0525', 'According to the MBO, fire compartment walls are to be constructed in the following locations: the external walls of buildings, when the wall is less than 2.50 m from the plot boundary; between terraced buildings on the same plot boundary; and to sub-divide larger buildings into fire compartments of not more than 40 m.'),
      q('page_0525', 'Fire compartment walls must be fireproof, structurally stable when exposed to fire and consist of non-combustible materials (F 90A). They must normally extend continuously from the foundations to min. 30 cm above the roof (min. 50 cm for a soft roof covering and in industrial buildings) or be capped with a projecting slab'),
      q('page_0525', 'Openings in fire compartment walls are generally impermissible. They can be allowed through fire compartment walls within buildings and then have to be provided with fireproof self-closing doors (T 90 door or gate)')],
     ['IfcBuilding 外轮廓长度', 'Pset_WallCommon.FireRating / Combustible', 'IfcDoor FireRating', 'IfcZone 防火分区（模型都没有）'],
     'fantasy_office_building_1 长 32 m < 40 m，不触发；学生模型 FireRating 几乎都为空。', frm=['K42'], priority=3, chapter='Fire protection')

rule('R20', '建筑等级决定承重构件与楼板的耐火要求', 'Site & Building', 'must', 'IfcWall / IfcColumn / IfcSlab',
     {'building.class': '建筑等级 1–5（住宅超过两套或使用面积 ≥ 400 m² → 等级 3–5；等级 1、2 ≤ 三层地上）', 'element.load_bearing': 'Pset_*Common.LoadBearing = True'},
     {'rating': 'Pset_*Common.FireRating', 'is_basement': '构件所在楼层低于室外地面'},
     'always (within context)',
     '承重及支撑墙、柱：等级 5 防火（fireproof）、等级 4 高度阻燃、等级 1–2 阻燃；地下室内须防火（等级 1–2 阻燃）；楼板须防火或至少阻燃，地下室顶板须防火；有耐火要求的楼板不得开洞，必须开洞时须用同等耐火的防火封堵',
     {'class5': 'fireproof', 'class4': 'highly fire-retarding', 'class1_2': 'fire-retarding', 'basement': 'fireproof', 'slab': 'fireproof or at least fire-retarding', 'slab_over_cellar': 'fireproof'},
     [q('page_0526', 'Load-bearing and bracing walls and columns must be constructed fireproof in buildings of class 5, highly fire-retarding in buildings of class 4 and fire-retarding in buildings of classes 1 and 2'),
      q('page_0526', 'In cellars, they have to be constructed fireproof and, in buildings of classes 1 and 2, fire-retarding.'),
      q('page_0527', 'Ceilings must be fireproof, or at least fire-retarding, and slabs over cellars must be fireproof. Openings in ceilings and floor slabs for which a fire resistance duration is necessary are prohibited. If openings are required, they must be fitted with fire protection closures (doors, etc.) constructed with a fire resistance duration corresponding to that of the slab.'),
      q('page_0076', 'In front of the outside walls of building classes 1 and 2 with not more than three overground storeys, 3 m depth is also sufficient.')],
     ['Pset_WallCommon / Pset_ColumnCommon / Pset_SlabCommon: LoadBearing, FireRating', '建筑等级（IFC 无，按层数与面积推断）'],
     '建筑等级的完整定义书里没有，只有零散线索；对 5 层、1257 m² 的办公楼按等级 4/5 处理。', frm=['K70'], priority=3, chapter='Fire protection')

rule('R21', '外墙、外墙饰面与屋面覆盖的燃烧性能', 'Site & Building', 'must', 'IfcWall / IfcCovering / IfcRoof',
     {'wall.is_external': 'Pset_WallCommon.IsExternal = True', 'building.class': '建筑等级'},
     {'combustibility': '材料燃烧等级（Pset_*Common.Combustible 或材料类别）', 'roof_covering': '屋面覆盖层材料'},
     'always (within context)',
     '非承重外墙及承重外墙的非承重部分须用不燃（至少阻燃）材料（等级 1–3 除外）；外墙饰面含保温层和支撑构造须难燃（等级 1、2 若能防止向邻房蔓延可用普通可燃）；屋面一般须为“硬屋面”，抗飞火和辐射热',
     {'ext_wall_nonloadbearing': 'non-combustible (at least fire-retarding), except classes 1–3', 'cladding_incl_insulation': 'flame-resistant', 'roof': 'hard covering'},
     [q('page_0526', 'Non-load-bearing external walls and non-load-bearing parts of load-bearing external walls are (except for buildings of building classes 1–3) to be constructed of non-combustible (at least fire-retarding) materials. External wall claddings, including insulation and support construction, have to be made of flame-resistant materials.'),
      q('page_0527', "The roofing must generally consist of 'hard covering' and be resistant against airborne spread of fire and radiated heat.")],
     ['IfcMaterial / Pset_*Common.Combustible', 'IfcRoof 材料层'],
     '幕墙是“非承重外墙”，这条对 fantasy_office_building_1 的 38 片幕墙直接适用。', frm=['K73'], priority=2, chapter='Fire protection')

# ───────────────────────── Storey ─────────────────────────
rule('R22', '每层每个使用单元两条独立疏散路线', 'Storey', 'must', 'IfcBuildingStorey / IfcZone',
     {'unit.has_occupied_room': '单元内至少一个有人员停留的房间'},
     {'n_routes': '通往室外的独立疏散路线数', 'first_via_stair': '第一条是否经必要楼梯（间）', 'second': '第二条经第二部必要楼梯，或消防队救援设备可达的位置', 'safety_stairwell': '是否为烟火不能侵入的安全楼梯间'},
     'always (within context)',
     '每层须有至少两条通往室外的独立疏散路线；单元不在地面层时第一条须经必要楼梯（必要时在自己的楼梯间内），第二条经第二部必要楼梯或消防队救援设备可达的位置；若经安全楼梯间疏散则不需要第二条',
     {'routes_min': 2, 'exception': 'safety stairwell'},
     [q('page_0523', 'Residential or commercial units with at least one occupied room must have at least two independent escape routes leading to the open air on each storey.'),
      q('page_0523', 'the first escape route must be via a legally essential staircase, if required in its own (legally essential) stairwell, and the second escape route via a second essential staircase or a single unified location which is accessible with the rescue equipment of the local fire brigade'),
      q('page_0523', "A second escape route is not required if escape is via a safety stairwell")],
     ['IfcStair 每层数量与位置', 'IfcZone 使用单元（无则按整层）', 'IfcWindow 可作救援开口'],
     'fantasy_office_building_1 每层 2–4 部楼梯，第一个条件易判；“救援设备可达”要看窗。', frm=['K39'], priority=3, chapter='Fire protection')

rule('R23', '疏散距离按建筑类型：办公 ≤ 35 m，楼梯间距 30 / 60 m', 'Storey', 'must', 'IfcBuildingStorey / IfcStair / IfcSpace',
     {'building.type': 'office = “buildings without special status, according to LBO”'},
     {'d_max': '每个居室内任一点到最近必要楼梯间或室外出口的步行距离', 'stair_spacing': '楼梯间彼此间距', 'end_spacing': '楼梯到建筑端部距离'},
     'always (within context)',
     '普通建筑（含办公）任一点到楼梯间 ≤ 35 m；高层 25 m；学校、商店、封闭/地下车库、人员密集场所、医院 30 m；实践中楼梯间距建筑端部约 30 m、彼此约 60 m；多部楼梯时布置使疏散路线最短；卫生间、楼梯间、电梯井等固定点按法规最大间距布置',
     {'office_m': 35, 'high_rise_m': 25, 'schools_shops_garages_assembly_hospitals_m': 30, 'end_spacing_m': 30, 'stair_spacing_m': 60},
     [q('page_0133', 'Every location in inhabited rooms and basements must be \\( \\leq 35 \\) m from the stairwell of at least one legally essential stairway or exit. If a number of stairways are necessary, then they should be arranged so that the escape route is as short as possible.'),
      q('page_0133', '- high-rise buildings | 25 m'),
      q('page_0133', '- buildings without special status, according to LBO | 35 m'),
      q('page_0253', 'According to MBO 2002, every point in an occupied room must be \\( \\leq 35 \\) m from a staircase. This in practice leads to a spacing of the staircases from the end of the building of 30 m and from each other of 60 m'),
      q('page_0253', 'Fixed points are sanitary facilities, stairwells, lift shafts etc., situated at maximum spacings defined in the building regulations')],
     ['IfcSpace 几何', 'IfcStair 位置', '步行路径（几何推导）'],
     '', frm=['K38', 'K134'], priority=3, chapter='Stairs · Regulations / Office buildings · Access')

rule('R24', '必要楼梯：封闭楼梯间、出口宽度、楼梯间开门', 'Storey', 'must', 'IfcStair / IfcSpace / IfcDoor',
     {'stair.role': 'main / legally essential'},
     {'enclosed': '楼梯是否位于连续封闭的楼梯间（IfcSpace 包围 + 墙）', 'exit_to_open_air': '楼梯间出口是否直通室外或经无火荷载前室', 'doors_into_stairwell': '开向楼梯间的门是否占用梯段宽度'},
     'always (within context)',
     '所有主楼梯须设在连续封闭的楼梯间内，连同通道和通向室外的出口能安全用于疏散；出口宽度与梯段宽度对应（原文 “Exit width should be ≤ stair width”）；开向楼梯间的门不得遮挡梯段宽度',
     {'enclosed': True},
     [q('page_0133', 'All main staircases must be enclosed in a continuous stairwell, which is designed and arranged so that, including its access routes and exit to the open air, it can safely be used for escape. Exit width should be \\( \\leq \\) stair width.'),
      q('page_0132', 'Doors opening into the stairwell must not obstruct the stair width.')],
     ['IfcStair 与包围它的 IfcSpace / IfcWall（需 IfcRelSpaceBoundary 或几何）', 'IfcDoor 开启方向与位置', 'IfcDoor 位置'],
     'fantasy_office_building_1 的楼梯都开敞在大厅/办公区里，没有楼梯间——这是对学生模型最常见的判定。', frm=['K43'], priority=3, chapter='Stairs · Regulations')

rule('R25', '必要楼梯的尺寸限值（非住宅）', 'Storey', 'must', 'IfcStair / IfcStairFlight',
     {'building.type': 'other buildings（非住宅）', 'stair.role': 'legally essential / non-essential'},
     {'w': '可用梯段宽度', 'r': 'Pset_StairFlightCommon.RiserHeight', 't': 'Pset_StairFlightCommon.TreadLength', 'storey_h': '层高', 'n_riser': 'NumberOfRiser'},
     'always (within context)',
     '必要楼梯：w ≥ 100 cm，r ≤ 19 cm，t ≥ 26 cm；非必要（附加）楼梯：w ≥ 50 cm，21/21；常规楼梯 17/29，必要楼梯每 ≤ 18 步设平台；层高 3.00 m 对应两跑 18 步 r = 16.66 cm',
     {'essential': {'width_cm': 100, 'riser_max_cm': 19, 'tread_min_cm': 26}, 'non_essential': {'width_cm': 50, 'riser_cm': 21, 'tread_cm': 21}, 'normal': '17/29', 'steps_per_run_max': 18},
     [q('page_0133', 'Row | Type of building | Type of stairs | Usable stair width (min) | Stair riser (R)^2 | Stair tread (T)^3'),
      q('page_0133', '4 | other buildings | legally essential stairs | 100 | 19 | 26'),
      q('page_0133', '5 | all buildings | non-essential (additional) stairs | 50 | 21 | 21'),
      q('page_0132', 'Normal stairs 17/29, landing after max. 18 steps for legally essential stairs.'),
      q('page_0132', '3000 | 18 | 166.6 | 17 | 176.4')],
     ['Pset_StairFlightCommon RiserHeight / TreadLength / NumberOfRiser', '梯段宽度（几何）'],
     '比 R05 的 17/28 更适合办公楼：这张表按建筑类型给出限值，办公楼属 “other buildings”。fantasy 的 r = 20 cm 超过 19。', frm=['K11', 'K09'], priority=3, chapter='Stairs · Regulations')

rule('R26', '办公与疏散楼梯应便于快速通行；气派楼梯的平台豁免', 'Storey', 'should', 'IfcStair',
     {'building.usage': 'office', 'stair.role': 'office stair / emergency stair / prestigious stair'},
     {'storey_h': '层高', 'has_landing': '是否有休息平台', 'is_prestigious': '是否为门厅内的气派楼梯'},
     'always (within context)',
     '办公楼楼梯和疏散楼梯应便于快速上下（区别于宜用低踏步的室外楼梯）；气派楼梯可在层高 ≤ 4 m 时不设平台，平台要求对其放宽；无障碍建筑的楼梯踏步不得有突缘',
     {'prestige_no_landing_up_to_m': 4.0, 'nosing_in_accessible_buildings': 'not allowed'},
     [q('page_0133', 'Stairs in offices or emergency stairs should, in contrast, make it possible to change level quickly.'),
      q('page_0132', 'Prestigious-style stairs can climb up to a 4 m storey height without a landing.'),
      q('page_0132', 'For stairs intended to be prestigious the requirement to provide landings is mitigated.'),
      q('page_0134', 'For stairs in buildings subject to disability-friendly building rules, steps may have no nosing!')],
     ['IfcStair 所在 IfcSpace（门厅 → 气派楼梯）', 'IfcBuildingStorey.Elevation', 'Pset_StairFlightCommon.NosingLength'],
     'fantasy_office_building_1 大厅里的 Ortbetontreppe 可按气派楼梯看，但层高 4.8 > 4 m，豁免不成立；NosingLength = 0.03 也违反无突缘。', frm=['K13', 'K10'], priority=2, chapter='Stairs')

rule('R27', '无台阶通达所有楼层（公众可达建筑）', 'Storey', 'must', 'IfcBuilding / IfcBuildingStorey / IfcTransportElement / IfcRamp',
     {'building.public_access': '办公、行政建筑属 MBO §50(2) 的公众可达建筑'},
     {'levels': '所有 IfcBuildingStorey', 'step_free_access': '每层是否可经电梯或坡道到达', 'has_lift': 'IfcTransportElement ELEVATOR 存在且服务各层'},
     'always (within context)',
     '公众可达建筑面向公众的部分须能供残障人士、老人和带小孩者无需帮助进出使用；按无障碍原则设计的建筑所有楼层须无台阶可达（电梯或坡道）',
     {'applies_to': 'offices, administration buildings', 'means': 'lift or ramp'},
     [q('page_0037', 'Buildings which are publicly accessible, must in their parts serving the general public be capable of being accessed and used, according to their purpose, by disabled people, old people and people with small children, without outside help. This requirement applies notably to cultural, educational, sport, leisure and health facilities, offices, administration buildings and courts, sales and catering establishments, parking, garages and toilets.'),
      q('page_0034', 'All levels of buildings designed in accordance with the principles of accessibility must be accessible without steps, i.e. using a lift or a ramp.')],
     ['IfcTransportElement（电梯）', 'IfcRamp', 'IfcBuildingStorey'],
     'fantasy_office_building_1 五层没有任何 IfcTransportElement，直接 fail。', frm=['K27'], priority=3, chapter='Accessible building')

rule('R28', '无障碍电梯：轿厢与门前活动区', 'Storey', 'must', 'IfcTransportElement / IfcSpace',
     {'building.public_access': True, 'element': 'IfcTransportElement ELEVATOR'},
     {'car_w': '轿厢净宽', 'car_d': '轿厢净深', 'area_front': '梯门前活动区', 'overlap': '是否与其他交通路线/活动区重叠', 'with_stair': '电梯是否与主楼梯间组合'},
     'always (within context)',
     '轿厢净宽 ≥ 1.10 m、净深 ≥ 1.40 m；门前活动区不小于轿厢地面面积且 ≥ 1.50 × 1.50 m，不得与其他交通路线和活动区重叠；电梯组通常与主楼梯间组合布置',
     {'car_min_m': [1.1, 1.4], 'front_min_m': [1.5, 1.5]},
     [q('page_0034', 'Cars of lifts must have a min. clear width of 1.10 m and a clear depth of 1.40 m. The movement area in front of the doors must be as large as the floor area of the car, but min. 1.50 m wide and 1.50 m deep'),
      q('page_0034', 'This area must not overlap with other traffic routes and movement areas.'),
      q('page_0143', 'Lift sets normally form part of the main stairwell.')],
     ['IfcTransportElement 几何', '梯门前 IfcSpace 几何', 'IfcStair 位置'],
     '', frm=['K30', 'K18'], priority=2, chapter='Accessible building / Lifts')

rule('R29', '无障碍坡道', 'Storey', 'must', 'IfcRamp / IfcRailing',
     {'building.public_access': True, 'element': 'IfcRamp'},
     {'slope': '坡度', 'w': '净宽', 'L': '坡段长度', 'landings': '起止及中间平台', 'handrails': '两侧扶手', 'kerb': '10 cm 轮挡'},
     'always (within context)',
     '坡度 ≤ 6%；净宽 ≥ 1.20 m；超过 6 m 须设 ≥ 1.50 m 长的中间平台；起止处设平台；两侧扶手（高 85 cm，直径 3–4.5 cm）及 10 cm 轮挡；坡道延长线上不得有向下台阶',
     {'slope_max': 0.06, 'width_min_m': 1.2, 'landing_every_m': 6, 'landing_len_m': 1.5, 'handrail_h_m': 0.85, 'kerb_cm': 10},
     [q('page_0034', 'May have a maximum slope of 6% → 3. If ramps are longer than 6 m, an intermediate landing of min. 1.50 m length is required. The ramp and the intermediate landing are both to be provided with 10 cm high wheel kerbs and handrails (diameter 3–4.5 cm) at a height of 85 cm. The clear ramp width must be min. 1.20 m.'),
      q('page_0034', 'There must be no stairs down in the extension of the ramp.'),
      q('page_0037', 'Ramps may not have a slope of more than 6%, must be at least 1.20 m wide and have a fixed handrail with a safe grip on both sides. A landing is to be provided at the start and end of the ramp and also an intermediate landing every 6 m. The landings must have a length of at least 1.50 m.')],
     ['IfcRamp / IfcRampFlight 几何', 'IfcRailing'],
     '9 个模型都没有 IfcRamp；规则仍保留，因为入口有高差时就会触发。', frm=['K16'], priority=2, chapter='Accessible building')

# ───────────────────────── Zone ─────────────────────────
rule('R30', '使用单元 ≥ 400 m² 时走廊为必要走廊：侧墙 F 30', 'Zone', 'must', 'IfcZone / IfcSpace / IfcWall',
     {'unit.area': '使用单元面积', 'space.function': 'corridor'},
     {'is_essential_corridor': 'unit.area ≥ 400 m² 且走廊是居室到楼梯间/室外的疏散路线', 'wall_rating': '走廊侧墙 FireRating', 'glazing_sill': '侧墙上采光玻璃下沿高度'},
     'unit.area ≥ 400 m²',
     '走廊受疏散路线规定约束：侧墙须阻燃 F 30；侧墙上的采光开口可用 G 级玻璃但下沿须 ≥ 1.80 m 离地；使用单元 < 400 m² 时走廊不受疏散路线要求',
     {'unit_threshold_m2': 400, 'wall_rating': 'F 30', 'glazing_lower_edge_m': 1.8},
     [q('page_0253', 'For combined use units of less than 400 m², the corridors are not subject to the requirements for escape routes.'),
      q('page_0528', 'A typical area of application for G-glazing is the openings for lighting installed in corridor walls, which have to be constructed fire-retarding (F 30) as the side walls of escape routes. The lower edge of the glass must in this case be at least 1.80 m above floor level, so that in case of fire the corridor remains usable in the radiation shadow.')],
     ['IfcZone 使用单元面积', 'IfcSpace corridor', 'Pset_WallCommon.FireRating', 'IfcWindow 内窗位置'],
     '', frm=['K127', 'K44'], priority=3, chapter='Office buildings · Access / Fire protection')

rule('R31', '单元之间的分隔墙', 'Zone', 'must', 'IfcZone / IfcWall',
     {'wall.between_units': '墙两侧属于不同的使用单元（租户）或单元与其他用途房间'},
     {'rating': 'Pset_WallCommon.FireRating', 'storey_structure_rating': '该层承重构件耐火等级（R20）', 'extends_to_slab': '墙是否砌到结构楼板（非仅到吊顶）', 'openings': '墙上开口的门'},
     'always (within context)',
     '分隔墙耐火时间须与该层承重构件相当；须一直到结构楼板（屋顶空间内到屋面覆层）；开口限于使用所需的大小和数量，并用至少阻燃、密闭、自闭的构件封闭',
     {'rating': '= load-bearing components of the storey', 'top': 'structural slab', 'door': 'at least fire-retarding, sealed, self-closing'},
     [q('page_0526', 'The fire resistance duration of separating walls between residential or commercial units (or units and rooms used otherwise) must correspond to the quality of the load-bearing components of the storey. These must extend to the structural slab (in roof spaces up to the roof cladding). Openings are limited to the size and number required for their use and must be closed by components which are at least fire-retarding, sealed and self-closing.')],
     ['IfcZone', 'IfcWall 顶标高 vs IfcSlab 底标高', 'Pset_WallCommon.FireRating', 'Pset_DoorCommon.FireRating / SelfClosing'],
     '出租办公（可逆办公楼）里每个租户单元都是一个 zone。', frm=['K72'], priority=2, chapter='Fire protection')

rule('R32', '工作场所厕所的布置细则', 'Zone', 'must', 'IfcSpace (WC) / IfcSanitaryTerminal / IfcDoor',
     {'building.usage': 'workplace / office', 'space.function': 'WC / sanitary facility'},
     {'n_wc': '一个厕所单元内的 WC 隔间数', 'n_urinal': '小便器数', 'urinal_visible_from_entrance': '从入口是否直接看到小便器', 'n_basin': '前室洗手盆数', 'wc_accessible': '是否有轮椅厕所', 'door_swing': '厕所门开启方向'},
     'always (within context)',
     '厕所单元 = 带洗手盆的前室（每 5 个 WC ≥ 1 个洗手盆）+ 完全分隔的 WC 间；一个单元不超过 10 个 WC 隔间和 10 个小便器；小便器不得从入口直接可见；隔间可上锁，轻质隔断高 ≥ 1.90 m、底部留 10–15 cm；所有卫生设施中至少一个轮椅厕所（并标识）；厕所、淋浴、更衣室的门须向外开',
     {'basin_per_wc': '1/5', 'cubicles_max': 10, 'urinals_max': 10, 'partition_h_m': 1.9, 'gap_cm': [10, 15], 'wheelchair_wc_min': 1, 'door': 'outward'},
     [q('page_0282', 'Toilet facilities consist of a lobby with washbasins (at least one washbasin per five WCs) and a completely separate room with at least one WC'),
      q('page_0282', 'Toilet cubicles must be lockable and, if light partitions (incompletely separated WC cubicles) are used, the partition should have a height of at least 1.90 m, and at the bottom a gap of 10–15 cm. Urinals must be placed so as not to be visible from the entrance. Toilet facilities should not contain more than 10 WC cubicles and 10 urinals.'),
      q('page_0034', 'At least one toilet must be provided for wheelchair users in all sanitary facilities.'),
      q('page_0034', 'Doors to toilets, showers and changing rooms must open outward.'),
      q('page_0037', 'One toilet must also be suitable and accessible for wheelchair users; this is to be indicated by a sign.')],
     ['IfcSpace WC 与前室的划分', 'IfcFlowTerminal / IfcSanitaryTerminal 类型与位置', 'IfcDoor 开启方向（几何/OperationType）'],
     '补 R11：R11 管数量与距离，这条管布置。', frm=['K120', 'K29'], priority=3, chapter='Industry · Subsidiary rooms / Accessible building')

rule('R33', '茶水间：每 50–100 工位一间 ~10 m²', 'Zone', 'typical', 'IfcSpace',
     {'building.usage': 'office'},
     {'n_ws': '工位数', 'n_kitchen': '茶水间数', 'a_kitchen': '茶水间面积', 'd_to_ws': '到工位距离'},
     'n_ws ≥ 50',
     '每约 50–100 个工位设一间约 10 m² 的茶水间，尽量靠近工位并与交流区相连',
     {'ws_per_kitchen': [50, 100], 'area_m2': 10},
     [q('page_0250', 'Tea kitchens should be as near to the workstations as possible and connected with communication zones. For every approx. 50–100 workplaces, one ~10 m² kitchen.')],
     ['IfcSpace.LongName = tea kitchen / pantry', 'IfcFurniture 桌子计数'],
     '', frm=['K119'], priority=1, chapter='Office buildings · Additional areas')

rule('R34', '每层保洁间；中央垃圾房与物业用房', 'Zone', 'should', 'IfcBuildingStorey / IfcSpace',
     {'building.usage': 'office'},
     {'cleaner_room_per_storey': '每个 IfcBuildingStorey 内是否有保洁间', 'waste_room': '中央垃圾房', 'caretaker': '物业休息、储藏、工作间是否居中'},
     'always (within context)',
     '每层应设保洁间（存放清洁设备，最好有给水和拖把池）；设中央垃圾房；物业管理员的休息室、储藏室和工作间应位于中心位置',
     {'cleaner_room': 'one per floor'},
     [q('page_0250', 'A cleaner’s room should be provided on every floor, as a store for cleaning equipment and ideally with water supply and bucket sink. A central waste room, possibly enclosed waste collection rooms with separate collection containers and shredders. The caretaker should have a rest room, store and workshop in a central location.')],
     ['IfcSpace.LongName 分楼层'],
     '学生模型几乎都没有这些房间，是典型的 diagnosis 题。', frm=['K122'], priority=2, chapter='Office buildings · Additional areas')

rule('R35', '入口区及其相邻关系：会议区、餐厅、轮椅停放', 'Zone', 'should', 'IfcSpace (entrance / lobby)',
     {'building.usage': 'office'},
     {'entrance_functions': '门厅、门禁、问询、访客登记、等候', 'conference_adjacent': '会议区是否从入口区直达', 'canteen_position': '餐厅是否靠近接待且在门禁之外', 'wheelchair_parking': '入口区是否有轮椅停放位'},
     'always (within context)',
     '入口区连接公共区与工作区，含门厅、门禁、问询、访客登记和等候区；会议区应从入口区直达；食堂/自助餐厅靠近接待处并在门禁之外，访客可用；按无障碍要求在入口区为轮椅使用者设停放位',
     {},
     [q('page_0250', 'Connection between public and working areas. The important functions are lobby, access control, information, visitor registration and waiting zone.'),
      q('page_0250', 'Conference areas should be directly accessible from the entrance area.'),
      q('page_0250', 'Location near the reception and outside the access control allows outside visitors in.'),
      q('page_0034', 'A wheelchair parking place for each wheelchair user is to be included in the design, preferably in the entrance area.')],
     ['IfcSpace 邻接（IfcRelSpaceBoundary 或几何）', 'IfcSpace.LongName'],
     'fantasy_office_building_1 的会议室在 OG1，不与 EG 大厅直接相连。', frm=['K124', 'K118', 'K125'], priority=2, chapter='Office buildings · Additional areas')

# ───────────────────────── Space ─────────────────────────
rule('R36', '组团办公 4–16 工位、距窗 ≤ 7.5 m；大开间依赖人工照明', 'Space', 'should', 'IfcSpace',
     {'building.usage': 'office', 'space.function': 'working space / group office / open-plan'},
     {'n_ws': '房间内工位数', 'd_window_max': '房间内任一工位到最近外窗的距离'},
     'n_ws ≥ 4',
     '组团办公室约 4–16 个工位，供一个团队使用；工位周围到窗距离最大 7.5 m（可不用全空调，开窗 + 辅助通风即可）；≥ 100 工位的大开间只有靠人工照明和通风才可能',
     {'group_office_ws': [4, 16], 'd_window_max_m': 7.5, 'open_plan_ws': 100},
     [q('page_0251', 'The experience with the open-plan layout led to the development of group offices with approx. 4–16 workstations; each office is used by a single team or department.'),
      q('page_0245', 'via the size of the workplace surroundings (max. 7.5 m to a window)'),
      q('page_0251', 'Large-scale office landscapes with 100 or more workstations are made possible by artificial lighting and ventilation')],
     ['IfcFurniture 桌子与 IfcSpace 的包含关系', 'IfcWindow / IfcCurtainWall 位置'],
     '', frm=['K117', 'K126'], priority=2, chapter='Office buildings · Room typology')

rule('R37', '工位的桌面与活动面积', 'Space', 'should', 'IfcFurniture / IfcSpace',
     {'furniture.kind': 'desk / workstation'},
     {'desk_w_d': '桌面尺寸', 'free_area': '工位处自由活动面积', 'overlap': '各类面积是否重叠且不影响功能'},
     'always (within context)',
     '桌面 ≥ 120 × 80 cm（以屏幕工作为主）、专业人员 ≥ 200 × 80 cm；每工位 ≥ 1.5 m² 自由活动面积；标准不再规定固定尺寸，但要求足够的工作面和活动面，各类面积可重叠，只要不限制功能',
     {'desk_min_cm': [120, 80], 'desk_specialist_cm': [200, 80], 'movement_m2': 1.5},
     [q('page_0248', 'The desktop working area should be at least 120 × 80 cm (few documents, predominantly screen work; for specialist employees, at least 200 × 80 cm)'),
      q('page_0248', 'There should be a free movement area of at least 1.5 m² at the workstation.'),
      q('page_0247', 'The assignments of various areas are differentiated by the standard; however, they can overlap if this results in no limitation of the function.')],
     ['IfcFurniture 几何（桌面）', '桌子周围的空地（几何）'],
     '', frm=['K114', 'K140'], priority=1, chapter='Office buildings · Computer workstations')

rule('R38', '工作间的窗面积', 'Space', 'must', 'IfcSpace / IfcWindow / IfcCurtainWall',
     {'building.usage': 'workplace / office', 'space.function': 'workroom / office'},
     {'sum_window_width': '所有对外视线窗的宽度之和', 'sum_wall_width': '所有墙宽之和（周长）', 'sill_h': '窗台高', 'room_h': '房间净高', 'glass_area': '窗玻璃面积', 'ext_wall_area': '外墙面积', 'floor_area': '地面面积'},
     'always (within context)',
     '对外视线窗总宽 ≥ 全部墙宽之和的 1/10；视线宜在视平线（窗台 0.85–1.25 m）；净高 > 3.5 m 的工作间玻璃面积 ≥ 外墙面积 30%；与住宅房间尺寸相当的房间玻璃最小高度 1.3 m；近似值：≤ 600 m² 的房间窗面积约为地面面积 1/10，精细作业 1/5',
     {'width_ratio': '1/10 of total wall width', 'sill_m': [0.85, 1.25], 'tall_room_glass': '≥ 30% of external wall area if h > 3.5 m', 'glass_min_h_m': 1.3, 'area_ratio': '1/10 floor area (≤ 600 m²), 1/5 for fine work'},
     [q('page_0109', 'The total width of all visual connections to the outside must be at least 1/10 of the total width of all walls, according to workplace guidelines'),
      q('page_0109', 'Possible visual connection to the outside should be at eye level (window sill heights of 0.85 –1.25 m)'),
      q('page_0109', 'For workrooms more than 3.5 m high, the glass area of the window must be at least 30% of the outside wall area'),
      q('page_0109', 'For rooms with dimensions corresponding to those of residential rooms, the minimum height of the glass area is 1.3 m.'),
      q('page_0278', 'Approx. figures for window areas: 1/10 of the floor area for rooms up to 600 m² (Workplace Guidelines 7/1 → p. 263); for fine work, provide 1/5 of the floor area.')],
     ['IfcWindow OverallWidth/Height、窗台高（几何）', 'IfcCurtainWall 玻璃面板面积', 'Qto_SpaceBaseQuantities NetFloorArea / NetPerimeter'],
     '幕墙房间玻璃面积远超 30%，这条主要筛出只有小窗的办公室。', frm=['K48'], priority=3, chapter='Windows · Requirements / Industry')

rule('R39', '窗与工作区：视野宽度与进深', 'Space', 'should', 'IfcSpace / IfcWindow',
     {'space.function': 'office / workroom', 'space.has_external_window': True},
     {'window_width': '窗宽（毛洞口）', 'room_width': '房间沿窗方向宽度', 'h_clear_window': '窗净高', 'd_work': '工作区到窗距离'},
     'always (within context)',
     '窗宽不应小于房间宽度的 65%（保证向外视野）；工作区到窗的距离宜为窗净高的 2 倍；自然采光大约能用到 7 m 进深',
     {'window_width_ratio': 0.65, 'work_distance': '2 × clear window height', 'daylight_depth_m': 7.0},
     [q('page_0507', 'The minimum window width as a percentage, before finishings, should not be less than 65% of the room width.'),
      q('page_0278', 'The distance of the working area from the window should be twice as long as the clear window height'),
      q('page_0253', 'Daylight can mostly be exploited into a room depth of about 7.00 m.')],
     ['IfcWindow 尺寸与所在墙', 'IfcSpace 几何', 'IfcFurniture 桌子位置'],
     'R10 讲建筑层面的采光进深，这条讲单个房间的窗与工位关系。', frm=['K52', 'K53', 'K116'], priority=2, chapter='Daylight / Industry')

rule('R40', '档案室：楼面荷载与位置', 'Space', 'must', 'IfcSpace / IfcSlab',
     {'building.usage': 'office', 'space.function': 'archive'},
     {'floor_load': '所在楼板设计荷载（Pset_SlabCommon / 结构属性）', 'mobile_units': '是否用密集架', 'length_per_ws': '纸质档案长度 / 工位'},
     'always (within context)',
     '档案室应按提高的楼面荷载 7.5–12.5 kN/m²（密集架）设计；纯纸质档案每工位很快占到 10–20 m；档案系统面积 = 家具面积 + 通道面积（½ L × W + 0.5 m），应设在中心位置',
     {'floor_load_kn_m2': [7.5, 12.5], 'paper_per_ws_m': [10, 20]},
     [q('page_0250', 'Archive rooms should be designed for an increased floor loading of 7.5–12.5 kN/m² (for mobile units)'),
      q('page_0250', 'purely paper archives rapidly take up 10–20 m per workstation'),
      q('page_0249', 'L × W (filing furniture) = space for furniture\n+ ½ L × W + 0.5 m = passage space')],
     ['IfcSpace.LongName = archive', '楼板荷载属性（结构模型才有）'],
     '', frm=['K123', 'K143'], priority=1, chapter='Office buildings · Additional areas / Archives')

rule('R41', '机房 / 服务器机房的空间要求', 'Space', 'should', 'IfcSpace',
     {'building.usage': 'office', 'space.function': 'server room / data centre'},
     {'raised_floor_h': '架空地板高度（层高 − 净高 − 板厚推得）', 'air_conditioned': '是否空调', 'backup_separated': '备份系统是否在独立防火区'},
     'always (within context)',
     '机房须 70 cm 架空地板（大量管线）、空调；门禁尤其重要；备份系统尽可能与数据中心分开设在防火分隔区域内',
     {'raised_floor_cm': 70},
     [q('page_0250', 'These rooms should have a 70 cm raised floor on account of the large amount of installation, and should be air-conditioned. Access control is particularly important. Back-up systems should if possible be separated from the data centre in fire-protected areas.')],
     ['IfcSpace.LongName', 'IfcSpace 底标高 vs 楼板顶（架空高度）'],
     '70 cm 架空影响层高，是早期设计就要定的。', frm=['K145'], priority=1, chapter='Office buildings · Additional areas')

# ───────────────────────── Element ─────────────────────────
rule('R42', '门洞模数与净宽折减', 'Element', 'should', 'IfcDoor / IfcOpeningElement',
     {'door.any': True},
     {'opening_w_h': '墙洞口尺寸（IfcOpeningElement 或 OverallWidth/Height）', 'clear_w': '净通行宽度 = 洞口 − 门框构造'},
     'always (within context)',
     '门洞口尺寸用标准模数（如 875 × 2000）；例外尺寸须为 125 mm 的整数倍；按 DIN 18100 表，875 mm 洞口的净开启宽度只有 841 mm，1000 mm 洞口才有 966 mm——无障碍要求 ≥ 0.90 m 净宽时洞口至少 1000 mm',
     {'module_mm': 125, 'opening_875_clear_mm': 841, 'opening_1000_clear_mm': 966},
     [q('page_0126', 'Dimensions of wall openings for doors → 1 are standard modular dimensions. If, in exceptional cases, different dimensions are required then their modular dimensions should be whole multiples of 125 mm (100 mm according to British Standards). A wall opening with 875 mm width and 2000 mm height (modular dimensions) can be described as: wall opening DIN 18100 – 875 × 2000.'),
      q('page_0126', '4 | 875 | 2000 | 860 | 1985 | 834 | 1972 | 841 | 1983'),
      q('page_0126', '5 | 1000 | 2000 | 985 | 1985 | 959 | 1972 | 966 | 1983')],
     ['IfcDoor.OverallWidth/OverallHeight', 'IfcOpeningElement 尺寸'],
     'fantasy 的内门 0.885 既不是 125 的倍数，按表净宽也到不了 0.90。', frm=['K26', 'K23'], priority=2, chapter='Doors · Construction details')

rule('R43', '紧急出口的门型与宽度', 'Element', 'must', 'IfcDoor',
     {'door.on_escape_route': '门在疏散路线上 / 是出口', 'n_people': '使用该出口的人数'},
     {'type': 'IfcDoor OperationType（推拉 / 旋转 / 平开）', 'w': '出口宽度'},
     'always (within context)',
     '紧急出口不得用推拉门和旋转门；出口宽度每 150 人 1.0 m（餐饮章节给出）',
     {'forbidden': ['sliding', 'revolving'], 'width_per_150_persons_m': 1.0},
     [q('page_0125', 'Sliding doors and revolving doors are not permissible at emergency exits, which they can block in circumstances of danger.'),
      q('page_0187', 'Emergency exits 1.0 m wide per 150 people using them.')],
     ['IfcDoor OperationType / 类型名', '人数（按工位数）'],
     'fantasy 的入口是平开玻璃门，type 合规；1.0 m/150 人来自餐饮章节，对办公只作参考。', frm=['K24', 'K41'], priority=2, chapter='Doors / Catering')

rule('R44', '采暖房间外窗至少双层/中空玻璃', 'Element', 'must', 'IfcWindow / IfcCurtainWall',
     {'window.is_external': 'IsExternal = True', 'space.heated': '采暖房间'},
     {'glazing': '玻璃构造（IfcMaterial / 类型名：Isolierverglasung / double glazing）'},
     'always (within context)',
     '采暖房间的外窗和落地窗至少用中空或双层玻璃；新建筑窗的 U 值按 EnEV 随整栋楼计算',
     {'glazing_min': 'insulating or double glazing'},
     [q('page_0111', 'External windows and French windows of heated rooms must be constructed with at least insulating or double glazing.')],
     ['IfcWindow / IfcPlate 材料（fantasy 里有 “Glas - Isolierverglasung klar”）'],
     '', frm=[], priority=2, chapter='Windows · Thermal')

rule('R45', '平屋面坡度与隔汽层位置', 'Element', 'should/must', 'IfcRoof / IfcSlab',
     {'roof.is_flat': '坡度 ≤ 5%'},
     {'slope': '屋面坡度', 'vapour_barrier_side': '隔汽层在保温层的暖侧还是冷侧'},
     'always (within context)',
     '平屋面一般至少 2% 坡度（推荐 5% / 3°）；无坡平屋面只作例外特殊构造；隔汽层须设在暖侧，否则冷凝',
     {'slope_min': 0.02, 'slope_recommended': 0.05, 'vapour_barrier': 'warm side'},
     [q('page_0103', 'Flat roofs are defined as roofs with a slope of up to 5%. Flat roofs without slope are possible as a special construction in exceptional cases. Flat roofs should generally have a minimum slope of 2%.'),
      q('page_0103', 'it is recommended to construct flat roofs with a minimum slope of 5% (3°).'),
      q('page_0484', 'If there is a vapour barrier on the outside, then the entire vapour pressure gradient occurs there and the result is condensation → 8; if this is to be avoided, then a vapour barrier must be installed on the warm side')],
     ['IfcRoof / IfcSlab ROOF 几何坡度', '材料层（IfcMaterialLayerSet）'],
     'fantasy 的四块屋面板都是水平的 Basisdach:Stb 20, insulated（Revit 平屋面一般不建坡度）。', frm=['K63', 'K65'], priority=2, chapter='Roofs / Building physics')

rule('R46', '隔墙与吊顶/架空地板、立面竖梃的连接', 'Element', 'must/should', 'IfcWall / IfcCovering / IfcCurtainWall',
     {'wall.is_partition': '非承重轻质隔墙', 'has_raised_floor_or_suspended_ceiling': '房间有架空地板或吊顶'},
     {'partition_continues': '隔墙是否延续到结构楼板/顶板', 'ceiling_floor_insulated': '吊顶/架空地板本身是否隔声', 'mullion_width': '模数线上的立面竖梃宽度'},
     'always (within context)',
     '有架空地板和吊顶时，隔墙要么在竖向延续（穿过吊顶和架空地板），要么这些构件本身隔声；位于模数网格上的立面竖梃应足够宽以连接隔墙；轻质隔墙节点要特别注意隔声，玻璃隔墙要与用户商定隔声等级',
     {},
     [q('page_0252', 'With raised access floors and suspended ceilings, either vertical continuation of any possible partitions is to be provided or these elements are to be sound-insulating in themselves'),
      q('page_0252', 'Vertical profiles in the façade, which lie on the modular grid, should be wide enough to connect a partition.'),
      q('page_0252', 'The junctions of light partitions demand particular attention to noise reduction. When glass partitions are specified, the required degree of sound proofing should be discussed with the user!')],
     ['IfcWall 顶标高 vs IfcSlab 底 / IfcCovering CEILING', 'IfcMember 竖梃宽度'],
     'fantasy：空间净高 2.75、层高 4.8 → 有 1.64 m 吊顶/架空区，GK 10 隔墙是否到板底可从几何判。', frm=['K148', 'K147'], priority=2, chapter='Office buildings · Grid')

rule('R47', '办公楼楼板跨度与荷载', 'Element', 'typical', 'IfcSlab / IfcColumn / IfcBeam',
     {'building.usage': 'office', 'structure': '钢或钢筋混凝土框架'},
     {'span': '柱/主梁间距', 'slab_type': '实心板 / 肋形板 / 预应力', 'load': '设计活荷载'},
     'always (within context)',
     '实心钢筋混凝土板跨 2.5–5.5 m，肋形板 5.0–7.5 m，主梁间距最大 12.5 m；预应力板可跨 25 m、厚仅 0.75 m；双排办公楼荷载假定：正常 5 kN/m² 另加 2 kN/m² 面层（8 cm 地面线槽）；书中算例为 6.50 m 跨钢筋混凝土板',
     {'solid_rc_span_m': [2.5, 5.5], 'ribbed_span_m': [5.0, 7.5], 'main_beam_max_m': 12.5, 'live_load_kn_m2': 5, 'screed_kn_m2': 2, 'example_span_m': 6.5},
     [q('page_0257', 'Solid reinforced concrete slabs span 2.5–5.5 m, ribbed slabs 5.0–7.5 m, both with a maximum 12.5 m between main beams. Pre-stressed concrete can span up to 25 m with only 0.75 m structural depth'),
      q('page_0255', 'normal 5 KN/m², additional 2 KN/m² for screed (8 cm for floor duct and supply connections)'),
      q('page_0255', 'Constructive scope for decision-making via the example of a reinforced concrete slab with 6.50 m span.')],
     ['IfcColumn 位置 → 柱距', 'IfcSlab 类型 / 厚度', 'IfcBeam'],
     'fantasy 的柱距 5.0–6.3 m，在实心板范围内偏上。跨度段落出自高层章节但是通用框架构造。', frm=[], priority=1, chapter='Office buildings · Construction / High-rise · Construction')

# ───────────────────────── verify & write ─────────────────────────
con = sqlite3.connect(os.path.join(ROOT, 'data', 'neufert', 'embeddings.sqlite'))
by_page = {}
for pg, c in con.execute('select page, content from embeddings'):
    by_page.setdefault(pg, []).append(c)
ws = lambda s: re.sub(r'\s+', ' ', s).strip()
bad = []
for r in R:
    for b in r['basis']:
        cands = by_page.get(b['page'], [])
        if any(b['quote'] in c for c in cands):
            continue
        status = 'ws_only' if any(ws(b['quote']) in ws(c) for c in cands) else ('other_page' if any(b['quote'] in c for lst in by_page.values() for c in lst) else 'MISSING')
        bad.append((r['rid'], status, b['page'], b['quote'][:100]))
for x in bad:
    print('%-4s %-10s %s | %r' % x)
nq = sum(len(r['basis']) for r in R)
if bad:
    sys.exit('%d of %d quotes not exact — fix before writing' % (len(bad), nq))
ids = [r['rid'] for r in R]
assert len(ids) == len(set(ids)), 'duplicate rid'
with open(OUT, 'w', encoding='utf-8') as f:
    for r in R:
        f.write(json.dumps(r, ensure_ascii=False) + '\n')
print('wrote %s: %d rules, %d quotes, all exact' % (os.path.relpath(OUT, ROOT), len(R), nq))

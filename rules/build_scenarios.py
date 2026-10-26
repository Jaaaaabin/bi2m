"""Scenario augmentation for the active rules.

A rule from the book says "in situation X, element Y must be designed as Z". The scenario makes that explicit as graph
roles: which element's parameter is being decided (target), which neighbouring elements it has to read (context
elements, with the parameters read and the relation that connects them), and how they compose into one situation.
The book quotes stay on the rule itself (basis); this file only adds the scenario layer.

Writes rules/scenarios.jsonl (one line per rule) — the site shows it inside each rule card.

.venv/bin/python rules/build_scenarios.py
"""
import json, os
HERE = os.path.dirname(os.path.abspath(__file__))

S = []
def sc(rid, target, decides, ctx, relations, scenario, scenario_en):
    """target: entity whose parameter is decided; decides: that parameter; ctx: [(entity, role, parameters read)];
    relations: graph edges that connect target and context; scenario: the situation in words."""
    S.append(dict(rid=rid, target=dict(entity=target, decides=decides),
                  context=[dict(entity=e, role=r, reads=p) for e, r, p in ctx], relations=relations,
                  scenario=scenario, scenario_en=scenario_en))

# ───────────── Storey & stairs ─────────────
sc('R02', 'IfcSpace (office / meeting room)', '房间净高 h_clear（Qto Height，或层高 − 楼板 − 吊顶）',
   [('IfcBuildingStorey ×2', '本层与上一层', 'Elevation 差 = 层高'), ('IfcSlab', '上方楼板', '厚度'), ('IfcCovering (ceiling)', '吊顶 / 架空地板', '厚度，常缺'), ('IfcBuilding', '建筑用途', 'office（model card）')],
   ['space partOf storey', 'storey ABOVE storey', 'slab containedIn upper storey'],
   '办公楼里的一个房间要定净高：它看自己所在层和上一层的标高差、上方楼板的厚度、是否预留吊顶和架空地板，剩下的净空必须 ≥ 2.75 m（坐姿房间 2.50，走廊卫生间 2.30）。',
   'An office room decides its clear height from the elevation difference to the storey above, the slab thickness and any ceiling / raised-floor allowance; what remains must be ≥ 2.75 m (2.50 seated rooms, 2.30 corridors).')

sc('R03', 'IfcStairFlight', '踢面 r 与踏面 t（Pset_StairFlightCommon.RiserHeight / TreadLength）',
   [('IfcBuildingStorey ×2', '梯段连接的两层', 'Elevation 差 → 总升高'), ('IfcStair', '所属楼梯', '梯段数、是否有平台'), ('IfcStairFlight (sibling)', '同一楼梯的其他梯段', 'r/t 是否一致')],
   ['flight partOf stair', 'stair SERVES storey'],
   '一段楼梯要定踢面和踏面：总升高由两层标高差给定，分成 n 级后 r = 升高 / n，再选 t 使 2r + t 落在 59–65 cm；同一楼梯各段应一致。新手常只做前一步（r 由层高除出来），不做后一步。',
   'A flight decides riser and tread: the rise is fixed by the two storey elevations, r = rise / n, and t is chosen so that 2r + t lands in 59–65 cm, consistently across the stair\'s flights.')

sc('R04', 'IfcStair', '每段级数 n_riser 与休息平台（IfcSlab LANDING）的有无及宽度',
   [('IfcBuildingStorey ×2', '所连两层', '层高 ≥ 2.75 时须设平台'), ('IfcStairFlight', '各梯段', 'NumberOfRiser ≤ 18，宽度'), ('IfcSlab (LANDING)', '平台', '宽度 ≥ 梯段宽')],
   ['stair SERVES storey', 'flight partOf stair', 'landing partOf stair'],
   '一部楼梯按层高决定要不要平台、分几段：层高 ≥ 2.75 m 必须有平台，每段 3–18 级，平台宽度不小于梯段宽。',
   'A stair decides from the storey height whether it needs a landing and how many flights: ≥ 2.75 m requires a landing, 3–18 risers per flight, landing at least as wide as the flight.')

sc('R05', 'IfcStairFlight', '梯段可用宽度 w（几何或 Qto）',
   [('IfcStair', '所属楼梯', '是否必要楼梯（连接各层、通向出口）'), ('IfcBuilding', '建筑类型', '住宅 / 非住宅；高层住宅 1.25'), ('IfcBuildingStorey ×2', '所连两层', '升高 → 踏步比')],
   ['flight partOf stair', 'stair SERVES storey'],
   '必要楼梯的梯段按建筑类型定宽度和踏步比：w ≥ 1.00 m、17/28；高层住宅 1.25 m。',
   'An essential stair flight takes its width and ratio from the building type: w ≥ 1.00 m, 17/28; 1.25 m in high-rise housing.')

sc('R06', 'IfcRailing', '栏杆高度（Pset_RailingCommon.Height 或几何）',
   [('IfcBuildingStorey', '栏杆所在层', 'Elevation'), ('IfcBuildingStorey / IfcSlab', '下方最近的可落地面', 'Elevation → 坠落高度 drop'), ('IfcBuilding', '是否工作场所', 'office → 1.00')],
   ['railing containedIn storey', 'storey ABOVE storey'],
   '一根栏杆要定高度，先算它保护的坠落高度（本层到下方楼面）：< 12 m 用 0.90，> 12 m 用 1.10，工作场所 1.00。',
   'A railing takes its height from the drop it guards (its storey to the floor below): 0.90 under 12 m, 1.10 above, 1.00 at workplaces.')

sc('R22', 'IfcBuildingStorey', '本层的独立疏散路线数（IfcStair 数与位置）',
   [('IfcStair', '连接本层与下层 / 出口的楼梯', 'SERVES 本层，位置'), ('IfcSpace (stairwell)', '楼梯间', '是否封闭'), ('IfcDoor IsExternal', '地面层出口', '位置')],
   ['stair SERVES storey', 'stair containedIn stairwell space', 'door opensTo space'],
   '每个楼层数一数能到达室外的独立路线：至少两部楼梯、互相不经过同一空间；若只有一条，第二条要靠消防救援位置或安全楼梯间。',
   'Each storey counts independent routes to the open air: at least two stairs not sharing a space; otherwise a rescue position or a safety stairwell must stand in.')

sc('R23', 'IfcSpace (any occupied room)', '到最近楼梯间的步行距离 d_walk',
   [('IfcDoor', '房间的门', '位置'), ('IfcSpace (corridor / hall)', '经过的交通空间', '路径'), ('IfcSpace (stairwell) / IfcStair', '最近的楼梯间', '位置'), ('IfcBuilding', '建筑类型', 'office 35 m / high-rise 25 m / school 30 m')],
   ['door opensTo room', 'door opensTo corridor', 'stair containedIn stairwell', 'stairwell partOf same storey'],
   '每个使用房间沿门 → 走廊 → 楼梯间量步行距离，上限按建筑类型取 35 / 30 / 25 m；楼梯间之间的距离也由此落到 30 / 60 m。',
   'Each occupied room measures door → corridor → stairwell; the limit is 35 / 30 / 25 m by building type, which in turn spaces stairwells 30 / 60 m apart.')

sc('R24', 'IfcStair (main / essential)', '是否位于封闭楼梯间（IfcSpace）内，楼梯间的门与出口宽度',
   [('IfcSpace (stairwell)', '包围楼梯的房间', '是否存在、是否只含楼梯'), ('IfcDoor', '楼梯间的门', '宽度 ≤ 梯段宽、防火自闭'), ('IfcSpace (hall / corridor)', '门另一侧的空间', '类型')],
   ['stair containedIn stairwell', 'door opensTo stairwell + corridor'],
   '主楼梯看自己有没有被一个楼梯间房间包起来、门通向哪里：须连续封闭，出口宽度与梯段宽对应，门自闭防烟。开敞在大厅里的楼梯不满足。',
   'A main stair checks whether a stairwell room encloses it and where its doors lead: continuously enclosed, exit width matching the flight, self-closing doors. An open stair in a hall fails.')

sc('R25', 'IfcStairFlight (non-residential)', 'r ≤ 19、t ≥ 26、w ≥ 1.00 的限值',
   [('IfcBuilding', '建筑用途', '非住宅'), ('IfcStair', '是否必要楼梯', '连接各层且通出口'), ('IfcBuildingStorey ×2', '两层标高', '升高')],
   ['flight partOf stair', 'stair SERVES storey'],
   '非住宅的必要楼梯梯段按硬限值自检：踢面不超过 19、踏面不少于 26、宽不少于 100 cm；附加楼梯才可以 50 cm、21/21。',
   'A non-residential essential flight checks the hard limits: r ≤ 19, t ≥ 26, w ≥ 100 cm; only additional stairs may be 50 cm, 21/21.')

sc('R26', 'IfcStair (office)', '踏步比取向（便于快速通行）、气派楼梯的平台豁免',
   [('IfcBuilding', '办公用途', 'office'), ('IfcBuildingStorey', '层高', '≤ 4 m 时气派楼梯可免平台'), ('IfcStairFlight', '梯段', 'r/t、突缘')],
   ['stair SERVES storey', 'flight partOf stair'],
   '办公楼和疏散楼梯选踏步比时偏向快速上下（区别于室外楼梯的低踏步）；层高 ≤ 4 m 的气派楼梯可以不设平台；无障碍建筑不得有踏步突缘。',
   'Office and escape stairs choose their ratio for quick walking; a grand stair may omit the landing up to 4 m storey height; no nosings in accessible buildings.')

sc('R27', 'IfcBuildingStorey (every storey)', '无台阶可达：由 IfcTransportElement / IfcRamp 提供',
   [('IfcBuilding', '公众可达建筑', 'office, school…'), ('IfcTransportElement', '电梯', 'SERVES 哪些层'), ('IfcRamp', '坡道', '连接的层'), ('IfcSite', '室外地坪', 'RefElevation vs 入口层')],
   ['lift SERVES storey', 'ramp SERVES storey', 'entrance door opensTo storey'],
   '公众可达建筑的每一层都要能不经台阶到达：入口层与室外地坪齐平或有坡道，其余各层由电梯服务；没有电梯的多层公共建筑直接不满足。',
   'Every storey of a public building must be reachable without steps: the entrance level flush with the ground or ramped, the other storeys served by a lift; a multi-storey public building without a lift fails.')

sc('R56', 'IfcStair (additional / non-essential)', '允许的最小宽度 0.50 与 21/21',
   [('IfcStair (others)', '同层其他楼梯', '是否已有必要楼梯通出口'), ('IfcSpace / IfcZone', '楼梯所在的户或房间', '是否只在一户内部'), ('IfcStairFlight', '梯段', 'w, r/t')],
   ['stair SERVES storey', 'stair containedIn space', 'space inZone'],
   '一部楼梯先看自己是不是法定必要楼梯：如果本层另有通向出口的必要楼梯、而它只在一户或一个房间内部，它就是附加楼梯，可以窄到 0.50、21/21；否则按必要楼梯 1.00、17/28。',
   'A stair first decides whether it is essential: if another essential stair already leads out and this one stays inside one flat or room, it is additional and may be 0.50 wide, 21/21; otherwise 1.00, 17/28 applies.')

sc('R57', 'IfcStair (start / end)', '梯段起止处前方的活动区深度',
   [('IfcBuilding', '公众可达', '无障碍要求'), ('IfcSpace', '楼梯起止处所在的房间 / 走廊', '净尺寸'), ('IfcFurniture / IfcWall', '前方的障碍物', '位置'), ('IfcStairFlight', '首级踏步', '踏面不计入')],
   ['stair containedIn space', 'space contains furniture', 'wall boundedBy space'],
   '无障碍建筑里每段楼梯的起步和到达处，前方要空出 ≥ 1.50 m 宽的活动区，不算首级踏面；看的是楼梯所在房间的净尺寸和前方有没有墙或家具。',
   'In an accessible building each flight needs a ≥ 1.50 m movement area at its start and end, excluding the first tread; it reads the enclosing room and any wall or furniture in front.')

sc('R58', 'IfcBuilding (residential)', '是否必须设电梯（IfcTransportElement）',
   [('IfcBuildingStorey', '完整楼层', '地上、含居住房间的层数 > 5'), ('IfcTransportElement / lift space', '电梯', '是否存在'), ('IfcZone / 户门', '每梯户数', '一梯两户为常见')],
   ['storey containedIn building', 'lift SERVES storey', 'flat inZone'],
   '住宅数完整楼层：超过 5 层就必须有电梯；交通组织以一梯两户最常见。',
   'A residential building counts its full storeys: more than five requires a lift; two flats per stair is the usual arrangement.')

# ───────────── Site & Building, layout ─────────────
sc('R14', 'IfcSpace (office room)', '朝向可接受性（北向房间是否允许）',
   [('IfcSite / context', 'TrueNorth', '方向'), ('IfcWall IsExternal / IfcWindow', '房间的采光面', '法线方向'), ('IfcSpace (corridor)', '平面是否走廊式', '有无走廊')],
   ['window opensTo room', 'window fillsOpeningIn external wall', 'corridor adjacent rooms'],
   '一间办公室看自己的窗朝哪、平面是不是走廊式：北向房间只在无走廊平面里可接受；长轴东西向避免早晚低角度阳光。',
   'An office room reads its window orientation and whether the plan is corridor-type: north-facing rooms only without a corridor; E/W main axis avoids low sun.')

sc('R15', 'IfcBuilding (office)', '平面类型：单排 / 双排 / 三排（中部服务核）',
   [('IfcSpace (corridor / hall)', '交通空间', '位置与两侧'), ('IfcSpace (rooms)', '房间', '相对走廊 / 核心的排数'), ('IfcBuildingStorey', '层数 / 高度', '三排只适合高层'), ('IfcSpace', '房间进深', '单排只在深房间时可接受')],
   ['room opensTo corridor', 'room on_facade', 'storey elevations'],
   '整栋办公楼按房间相对走廊的排列判断平面类型：双排是标准解；单排不经济，只在房间很深时可接受；中部大服务区只对高层合适。',
   'An office building reads how rooms line up against the corridor: double-row is the standard; single-row only with deep rooms; a central service zone only for high-rise.')

sc('R16', 'IfcWall (partition) / IfcGrid', '装修网格模数（1.50 / 1.35）与隔墙落点',
   [('IfcCurtainWall / IfcWindow', '立面网格', '竖梃 / 窗间墙间距'), ('IfcGrid', '结构网格', '可与装修网格错开'), ('IfcSpace (office)', '办公室类型', '单间 → 1.50，组合 → 1.35'), ('IfcColumn', '柱', '落在房间内的损失')],
   ['partition fillsOpeningIn / meets facade', 'grid axes spacing', 'room width = n × module'],
   '定隔墙网格时看立面：隔墙必须接到窗间墙或竖梃上，所以装修网格 = 立面网格，模数按办公类型取 1.50 或 1.35；结构网格可以错开。',
   'Partitions read the façade: they must meet a pier or mullion, so fit-out grid = façade grid, with 1.50 or 1.35 by office type; the structural grid may be offset.')

sc('R17', 'IfcBuilding (corridor-type office)', '建筑进深 12–13 m（与模数配合）',
   [('IfcSpace (corridor)', '中廊', '存在、位置'), ('IfcSpace (rooms both sides)', '两侧房间', '进深'), ('IfcGrid', '模数', '1.35 → 13.40，1.50 → 12.50')],
   ['corridor adjacent rooms', 'external walls bound rooms', 'grid spacing'],
   '中廊式办公楼的总进深由两侧房间进深 + 走廊宽度得出，通常 12–13 m，并与模数配套（1.35 m → 13.40，1.50 m → 12.50）。',
   'A corridor-type office derives its depth from room depth on both sides plus corridor width, typically 12–13 m, matched to the module (1.35 → 13.40, 1.50 → 12.50).')

sc('R18', 'IfcBuilding (office)', '每工位总面积与各类附属面积',
   [('IfcFurniture (desk)', '工位', '数量 n_ws'), ('IfcSpace', '各类房间', '面积按用途分：卫生、会议、档案、储藏、茶水、入口、设备、交通'), ('IfcWall / IfcColumn', '结构面积', '平面面积')],
   ['space contains desk', 'space partOf storey', 'space classified by name'],
   '整栋楼把所有房间面积按用途分类，除以工位数：直接工位 11–15、各附属项各有区间，总计 23–45 m²/工位。',
   'The whole building sorts room areas by use and divides by workstations: 11–15 direct, each ancillary item in its range, 23–45 m² per workstation in total.')

sc('R19', 'IfcBuilding', '是否需要防火墙 / 分区（IfcWall FireRating F 90 A）',
   [('IfcWall IsExternal', '外轮廓', '建筑长度 L'), ('IfcSite', '地块边界', '外墙到边界 < 2.50 m'), ('IfcWall (fire wall)', '防火墙', '从基础到屋面以上 ≥ 30 cm，FireRating'), ('IfcRoof / IfcSlab', '屋面', '防火墙是否穿出')],
   ['external walls → extent', 'fire wall spans storeys', 'wall FireRating'],
   '楼一旦超过 40 m 长（或外墙离地块边界不到 2.5 m），就要有一道 F 90 A 的防火墙把平面切成 ≤ 40 m 的分区，并从基础连续到屋面以上。',
   'Once a building exceeds 40 m (or stands within 2.5 m of the boundary) an F 90 A fire wall must split it into ≤ 40 m compartments, continuous from foundation to above the roof.')

sc('R20', 'IfcWall (LoadBearing) / IfcColumn / IfcSlab', '耐火要求（fireproof / highly fire-retarding / fire-retarding）',
   [('IfcBuilding', '建筑等级', 'class 1–5（由高度和用途定）'), ('IfcBuildingStorey', '是否地下室', 'Elevation < 0'), ('IfcSlab', '楼板', '是否开洞、地下室顶板')],
   ['element containedIn storey', 'storey elevation', 'building class (external)'],
   '承重墙、柱、楼板按建筑等级和所在层定耐火：等级 5 防火、4 高度阻燃、1–2 阻燃；地下室内防火；地下室顶板防火；有耐火要求的板不得开洞。',
   'Load-bearing walls, columns and slabs take their fire resistance from the building class and storey: class 5 fireproof, 4 highly retarding, 1–2 retarding; cellars fireproof; no openings in rated slabs.')

sc('R21', 'IfcWall IsExternal / IfcCovering (cladding) / IfcRoof', '燃烧性能（不燃 / 难燃）',
   [('IfcBuilding', '建筑等级', '1–3 可放宽'), ('IfcMaterial', '材料层', '砖 / 混凝土 / 木 / 保温'), ('IfcBuilding (neighbour)', '邻房', '是否能防止蔓延')],
   ['wall hasMaterial layers', 'covering on wall'],
   '外墙、外墙饰面（含保温与支撑）和屋面覆盖按材料判燃烧性能：外墙不燃（至少阻燃），饰面难燃，屋面为硬屋面；低等级建筑有放宽。',
   'External walls, claddings (with insulation and supports) and roof coverings are judged by material: non-combustible walls, hardly flammable claddings, hard roofing; relaxed for low classes.')

sc('R30', 'IfcSpace (corridor)', '走廊是否为必要走廊 → 侧墙 F 30、采光开口下沿 ≥ 1.80',
   [('IfcZone / 使用单元', '走廊所属单元', '面积 ≥ 400 m²'), ('IfcWall', '走廊侧墙', 'FireRating、材料'), ('IfcWindow (internal)', '侧墙上的采光窗', '下沿高度、玻璃等级')],
   ['corridor inZone', 'wall boundedBy corridor', 'window fillsOpeningIn wall'],
   '一条走廊看自己所在使用单元有多大：≥ 400 m² 时它受疏散路线规定约束，侧墙须 F 30，侧墙上的采光玻璃下沿 ≥ 1.80 m；小单元内的走廊不受约束。',
   'A corridor reads the size of its use unit: at ≥ 400 m² it falls under escape-route rules, side walls F 30, glazing sills ≥ 1.80 m; corridors in small units are exempt.')

sc('R47', 'IfcSlab (floor)', '板跨与板型（实心 / 肋形 / 预应力）、设计荷载',
   [('IfcColumn / IfcWall LoadBearing', '支承', '间距 = 跨度'), ('IfcGrid', '柱网', '轴距'), ('IfcBuilding', '办公用途', '荷载 5 kN/m²、档案室更高')],
   ['slab supported by columns / walls', 'grid spacing'],
   '楼板按柱网或承重墙间距选板型：实心板 2.5–5.5 m、肋形板 5–7.5 m、预应力可到 25 m；办公荷载 5 kN/m²。',
   'A slab picks its type from the column or wall spacing: solid 2.5–5.5 m, ribbed 5–7.5 m, prestressed up to 25 m; office load 5 kN/m².')

sc('R102', 'IfcWall / IfcGrid', '标志尺寸与模数（M = 100，3M / 6M / 12M）',
   [('IfcGrid', '轴网', '轴距是否为模数倍数'), ('IfcWall', '墙', '厚度 = 模数 − 灰缝（24 / 36.5）'), ('IfcMaterial', '砌体', '砖模数 25 cm')],
   ['grid spacing', 'wall thickness from material layers'],
   '墙厚和轴距对照模数系统：砖墙 24 = 25 − 1 灰缝、36.5 = 37.5 − 1；轴距应为 100 mm（或 300 / 600 / 1200）的倍数。',
   'Wall thicknesses and grid spacings are checked against the modular system: brick 24 = 25 − 1 joint, 36.5 = 37.5 − 1; grid spacings in multiples of 100 (or 300 / 600 / 1200) mm.')

# ───────────── Space ─────────────
sc('R09', 'IfcSpace (office room)', '每工位面积 a_ws = 房间面积 / 工位数',
   [('IfcFurniture (desk)', '房间内的桌子', '数量 n_ws'), ('IfcFurniture (chair / cabinet)', '其他家具', '区分工位与配套'), ('IfcSpace', '房间本身', '净面积')],
   ['space contains desk', 'space Qto area'],
   '一间办公室数自己的桌子、算面积：直接工位 11–15 m²（均 13）；双三人间常过挤，单人间常过大。',
   'An office room counts its desks against its area: 11–15 m² per workstation (mean 13); shared rooms tend to be too tight, single rooms too generous.')

sc('R10', 'IfcSpace (office room)', '进深 d 与采光方式（自然 / 人工）',
   [('IfcWall IsExternal / IfcCurtainWall', '采光立面', '房间哪一边贴外墙'), ('IfcWindow', '窗', '有无'), ('IfcSpace (corridor)', '走廊', '中廊式整体 12–13 m')],
   ['room on_facade', 'window opensTo room', 'room adjacent corridor'],
   '一间房间量自己从采光面到对面墙的进深：≲ 7 m 才能主要靠自然采光；完全没有外墙的内部房间只能人工照明。',
   'A room measures its depth from the daylight face: ≲ 7 m for daylight; an interior room without an external wall is artificially lit only.')

sc('R11', 'IfcBuildingStorey / IfcZone (workplace unit)', '厕所数量、男女分设、到厕所距离',
   [('IfcFurniture (desk)', '工位', '人数 n_emp'), ('IfcSpace (WC)', '厕所房间', '数量、成对与否、位置'), ('IfcSanitaryTerminal', '便器 / 洗手盆', 'n_wc, n_basin'), ('IfcSpace (anteroom)', '前室', '是否存在')],
   ['space contains desk', 'wc partOf storey', 'wc contains sanitary'],
   '每层按工位数定厕所：> 5 人分男女，每个工位到厕所 ≤ 100 m 或一层楼，前室带洗手盆（每 5 个 WC 一个）加完全分隔的隔间。',
   'Each storey sizes its toilets from the headcount: separate M/F above 5, ≤ 100 m or one storey to a toilet, an anteroom with basins (1 per 5 WCs) plus fully separated cubicles.')

sc('R12', 'IfcSpace (conference)', '每座面积 a_seat',
   [('IfcFurniture (chair)', '座椅', '数量 n_seat'), ('IfcFurniture (table)', '会议桌', '尺寸'), ('IfcSpace (storage / pantry)', '附属空间', '面积 ≈ 会议面积 / 3')],
   ['space contains chair', 'space contains table'],
   '会议室数椅子算面积：约 2.5 m²/座，储藏备餐等附属空间另加约 1/3。',
   'A conference room counts chairs against area: about 2.5 m² per seat, with ancillary storage and pantry adding about a third.')

sc('R32', 'IfcSpace (toilet unit)', '前室 + 隔间的组织、便器上限、小便器视线',
   [('IfcSanitaryTerminal (WC)', '隔间便器', '≤ 10 个 / 单元'), ('IfcSanitaryTerminal (urinal)', '小便器', '≤ 10，不得从入口直视'), ('IfcSanitaryTerminal (basin)', '洗手盆', '前室内'), ('IfcDoor', '入口门', '位置 → 视线')],
   ['unit contains sanitary', 'door opensTo unit'],
   '一个厕所单元按便器数和门的位置自检：前室带洗手盆，隔间完全分隔，一个单元不超过 10 个 WC 和 10 个小便器，小便器不能从入口直接看见。',
   'A toilet unit checks itself by fixtures and door position: anteroom with basins, fully separated cubicles, ≤ 10 WCs and 10 urinals per unit, urinals not visible from the entrance.')

sc('R33', 'IfcBuildingStorey / IfcZone (office unit)', '茶水间数量与面积',
   [('IfcFurniture (desk)', '工位', 'n_ws ≥ 50'), ('IfcSpace (tea kitchen)', '茶水间', '数量、面积 ≈ 10 m²、位置'), ('IfcSpace (communication area)', '交流区', '相邻')],
   ['space contains desk', 'tea kitchen partOf storey', 'tea kitchen adjacent communication'],
   '一个办公单元按工位数配茶水间：每 50–100 个工位一间约 10 m²，靠近工位并与交流区相连。',
   'An office unit provides tea kitchens by headcount: one ~10 m² per 50–100 workstations, near the desks and linked to a communication area.')

sc('R34', 'IfcBuildingStorey', '保洁间的有无；中央垃圾房与物业用房的位置',
   [('IfcSpace (cleaning)', '保洁间', '每层一间，带给水 / 拖把池'), ('IfcSpace (refuse)', '中央垃圾房', '存在'), ('IfcSpace (caretaker)', '物业用房', '位置居中')],
   ['space partOf storey', 'space classified by name'],
   '每层检查有没有保洁间（最好有给水和拖把池）；整栋楼要有中央垃圾房，物业用房放在中心位置。',
   'Each storey checks for a cleaner\'s room (ideally with water); the building needs a central refuse room and centrally placed caretaker\'s rooms.')

sc('R35', 'IfcSpace (entrance zone)', '入口区的组成与相邻关系',
   [('IfcDoor IsExternal', '主入口', '位置'), ('IfcSpace (reception / waiting)', '门厅、问询、等候', '存在'), ('IfcSpace (conference)', '会议区', '从入口直达'), ('IfcSpace (canteen)', '餐厅', '靠近接待、门禁外'), ('IfcSpace (wheelchair parking)', '轮椅停放', '存在')],
   ['door opensTo entrance space', 'entrance adjacent conference / canteen'],
   '入口层围绕主入口组织：门厅、门禁、问询、等候；会议区从入口直达；餐厅靠近接待且在门禁之外；按无障碍要求留轮椅停放位。',
   'The entrance level is organised around the main door: foyer, access control, reception, waiting; conference reachable directly; canteen near reception outside access control; wheelchair parking.')

sc('R36', 'IfcSpace (group office)', '工位数 4–16、到窗距离 ≤ 7.5 m、是否可自然通风',
   [('IfcFurniture (desk)', '工位', 'n_ws'), ('IfcWindow / IfcWall IsExternal', '窗', '工位到窗的距离'), ('IfcSpace (open plan)', '大开间', '≥ 100 工位才可全人工')],
   ['space contains desk', 'window opensTo space', 'desk bbox → window distance'],
   '组团办公室数工位、量到窗距离：4–16 个工位供一个团队，任一工位距窗 ≤ 7.5 m 就可以开窗通风不用全空调；≥ 100 工位的大开间才靠人工照明通风。',
   'A group office counts desks and measures to the window: 4–16 workstations for one team, every desk ≤ 7.5 m from a window to get by without full air-conditioning; only ≥ 100-desk open plans rely on artificial light.')

sc('R37', 'IfcFurniture (desk)', '桌面尺寸与每工位活动面积',
   [('IfcSpace', '所在房间', '净面积'), ('IfcFurniture (other)', '同室家具', '占用面积'), ('工作类型', '屏幕 / 专业人员', 'external')],
   ['space contains desk', 'space contains furniture'],
   '每张桌子对照用途：屏幕工作 ≥ 120 × 80、专业人员 ≥ 200 × 80；房间面积减去家具后每工位 ≥ 1.5 m² 活动面积。',
   'Each desk is checked against its use: ≥ 120 × 80 for screen work, ≥ 200 × 80 for professionals; room area minus furniture must leave ≥ 1.5 m² free per workstation.')

sc('R38', 'IfcSpace (workroom)', '窗面积与视线：窗总宽 ≥ 墙宽 / 10、窗台 0.85–1.25、净高 > 3.5 时玻璃 ≥ 30% 外墙',
   [('IfcWindow', '房间的窗', '宽、高、窗台'), ('IfcWall', '所有墙', '宽度之和'), ('IfcWall IsExternal', '外墙', '面积'), ('IfcSpace', '房间', '净高')],
   ['window opensTo room', 'wall boundedBy room', 'window fillsOpeningIn external wall'],
   '一个工作间把窗宽加起来和全部墙宽比：≥ 1/10；窗台在视平线（0.85–1.25）；房间高于 3.5 m 时玻璃面积 ≥ 外墙面积的 30%。',
   'A workroom sums its window widths against all wall widths: ≥ 1/10; sills at eye level (0.85–1.25); above 3.5 m clear height, glazing ≥ 30 % of the external wall.')

sc('R39', 'IfcSpace (office)', '窗宽 / 房间宽 ≥ 0.65；工作区距窗 ≈ 2 × 窗净高',
   [('IfcWindow', '房间的窗', '总宽、净高'), ('IfcWall IsExternal', '采光面', '房间沿立面的宽度'), ('IfcFurniture (desk)', '工作区', '到窗距离')],
   ['window opensTo room', 'window on facade wall', 'space contains desk'],
   '一间办公室把窗宽和自己沿立面的宽度比，不应低于 65%；桌子离窗大约两倍窗净高，自然采光约到 7 m。',
   'An office compares window width to its façade width (≥ 65 %); desks sit about twice the window height from the window, daylight reaching ~7 m.')

sc('R66', 'IfcZone (flat)', '居住面积的计算结果',
   [('IfcSpace', '户内各房间', '净面积、净高（≥ 2 全算，1–2 半算）'), ('IfcSpace (balcony)', '阳台 / 露台', '面积 × 25–50%'), ('IfcRoof', '坡顶', '净高变化'), ('IfcWall / IfcCovering', '饰面', '从饰面表面量')],
   ['space inZone', 'space partOf storey', 'balcony IsExternal'],
   '一户把各房间按净高分段算面积：≥ 2 m 全算、1–2 m 算一半、阳台算 25–50%，从饰面表面量净尺寸。',
   'A flat adds up its rooms by clear height: full above 2 m, half between 1 and 2, balconies at 25–50 %, measured between finished surfaces.')

sc('R67', 'IfcZone (flat)', '房间分组：起居区 / 睡眠区是否各自成片',
   [('IfcSpace (living / kitchen / dining)', '起居组', '相互连通'), ('IfcSpace (bedroom / bath)', '睡眠组', '相互连通'), ('IfcDoor', '房间之间的门', '连通关系'), ('IfcSpace (central corridor)', '中廊', '替代方案')],
   ['space inZone', 'door opensTo two spaces'],
   '一户把房间按功能分两组，看每组是否连成一片：起居（起居室、厨房、就餐）一片，睡眠（卧室、卫生间）一片；中廊式则沿两侧立面排房间、每间独立进入。',
   'A flat groups its rooms and checks each group is contiguous: living (living, kitchen, dining) and sleeping (bedrooms, bath); a central-corridor plan instead lines rooms along both façades, each entered separately.')

sc('R68', 'IfcZone (flat)', '是否具备厨房、储藏间、独立卫生间',
   [('IfcSpace (kitchen)', '厨房 / 小厨房', '存在，或含灶台水槽的家具'), ('IfcSpace (storage)', '储藏间', '存在、够大'), ('IfcSpace (bathroom)', '卫生间', '含浴缸 / 淋浴 + 便器'), ('IfcSanitaryTerminal', '洁具', '类型')],
   ['space inZone', 'space contains sanitary / cook'],
   '每一户逐项核对最低配置：至少一个厨房或小厨房、一个足够大的储藏间、一个独立的卫生间（浴缸或淋浴 + 厕所）。',
   'Each flat checks its minimum equipment: at least one kitchen or kitchenette, a sufficiently large storeroom, and a separate bathroom (bath or shower plus WC).')

sc('R69', 'IfcSpace (storage in flat)', '储藏面积 ≥ 1 m²、净宽 75 cm 或 2% 户面积',
   [('IfcZone (flat)', '所属户', '户面积 → 2%'), ('IfcFurniture (wardrobe)', '壁柜', '可计入'), ('IfcDoor', '储藏间门', '外开')],
   ['storage inZone', 'zone area'],
   '户内储藏空间对照户面积：至少 1 m²、净宽 75 cm；大户按 2% 配，可分散；门宜外开。',
   'Storage in a flat is checked against the flat area: ≥ 1 m² with 75 cm clear width, 2 % in larger flats, may be split; doors opening outwards.')

sc('R71', 'IfcSpace (any room / corridor)', '轮椅转身位 1.50 × 1.50；走廊宽 ≥ 1.50',
   [('IfcBuilding', '公众可达', '无障碍要求'), ('IfcFurniture', '房间内家具', '剩余净空'), ('IfcSpace (corridor)', '走廊', '净宽'), ('IfcTransportElement', '电梯门前', '活动区不得重叠')],
   ['space contains furniture', 'corridor width from geometry', 'lift door opensTo corridor'],
   '公众可达建筑里每个房间在扣掉家具后要放得下 1.50 × 1.50 的转身位；走廊和主通道 ≥ 1.50 宽；活动区可以重叠，电梯门前除外。',
   'In a public building every room must fit a 1.50 × 1.50 turning space after furniture; corridors ≥ 1.50 wide; movement areas may overlap except in front of lift doors.')

sc('R72', 'IfcSpace (corridor > 15 m)', '是否有 1.80 × 1.80 的会车位',
   [('IfcBuilding', '公众可达', '无障碍要求'), ('IfcSpace (corridor)', '走廊本身', '长度 > 15 m、各处净宽'), ('IfcWall', '侧墙', '局部退让')],
   ['corridor geometry', 'wall boundedBy corridor'],
   '走廊超过 15 m 就要在某处留出 1.80 × 1.80 的会车位；全程 ≥ 1.80 宽的走廊自然满足。',
   'A corridor over 15 m must provide a 1.80 × 1.80 passing place somewhere; a corridor ≥ 1.80 wide throughout satisfies it.')

sc('R75', 'IfcSpace (rooms of accessible flat)', '活动区宽 ≥ 1.20：家具旁、床侧、墙间、通道',
   [('IfcZone (accessible flat)', '无障碍户', 'R63 指定'), ('IfcFurniture', '家具 / 床', '侧向接近的边'), ('IfcWall', '对面的墙', '净距'), ('IfcSpace (corridor in flat)', '户内通道', '宽度')],
   ['space inZone', 'space contains furniture', 'furniture bbox → wall distance'],
   '无障碍户里每件轮椅要侧向接近的家具旁、非轮椅使用者的床侧、墙与墙之间和户内通道都要量出 ≥ 1.20 m。',
   'In an accessible flat, beside every piece of furniture approached sideways, along the bed, between walls and in internal passages ≥ 1.20 m must be measured.')

sc('R76', 'IfcSpace (habitable room)', '面积 ≥ 8 m²、净高 ≥ 2.40、窗面积 ≥ 1/8',
   [('IfcWindow', '房间的窗', '面积之和'), ('IfcBuildingStorey / IfcSlab', '层高、楼板', '净高'), ('IfcZone (flat)', '所属户', '用途 residential')],
   ['window opensTo room', 'room partOf storey', 'room inZone'],
   '住宅里每个居室自检三项：面积 8 m²、净高 2.40、窗面积为房间面积的 1/8，外加朝向与通风。',
   'Each habitable room in a dwelling checks three things: 8 m², 2.40 clear, window area 1/8 of the floor, plus orientation and ventilation.')

sc('R82', 'IfcSpace (sanitary room)', '卫生间类型（客用 WC / 淋浴间 / 浴室 / 完整浴室）',
   [('IfcSanitaryTerminal', '房间内的洁具', 'WC / basin / shower / bath 的组合')],
   ['space contains sanitary'],
   '一个卫生间按它装的洁具归类：WC + 盆 = 客用 WC；淋浴 + 盆 = 淋浴间；浴缸 + 盆 + WC = 浴室；四样全有 = 完整浴室。',
   'A sanitary room is typed by its fixtures: WC + basin = guest WC; shower + basin = shower room; bath + basin + WC = bathroom; all four = full bathroom.')

sc('R87', 'IfcSpace (corridor / escape route)', '通道内不得放家具；共用设施放到使用房间',
   [('IfcFurniture', '走廊里的家具', '数量'), ('IfcSpace (office)', '单间办公室', '共用设施占的靠窗面积'), ('IfcSpace (shared room)', '专用共用设施间', '是否存在')],
   ['corridor contains furniture', 'office contains shared equipment'],
   '走廊是疏散通道，先数里面有没有家具（不允许）；共用的复印、储物只能进使用房间占靠窗面积，或专门设一间。',
   'A corridor is an escape route: first count furniture in it (none allowed); shared copiers and storage must go into occupied rooms or a dedicated room.')

sc('R89', 'IfcFurniture (screen workstation)', '视线方向平行于窗立面与灯带',
   [('IfcWindow / IfcWall IsExternal', '窗立面', '方向'), ('IfcLightFixture', '灯带', '方向'), ('IfcFurniture (desk)', '桌子', 'ObjectPlacement 朝向')],
   ['desk containedIn space', 'window opensTo space', 'desk placement axis vs facade normal'],
   '每个屏幕工位看自己朝向和窗、灯带的关系：视线应与窗立面及灯带平行，屏幕尽量落在两者之间。',
   'Each screen workstation compares its facing with the window façade and light bands: view parallel to both, screen between them.')

# ───────────── Element ─────────────
sc('R07', 'IfcDoor', '净高 ≥ 2.10；无障碍净宽 ≥ 0.90；入口无台阶',
   [('IfcBuilding', '公众可达', '无障碍要求'), ('IfcSpace ×2', '门两侧的房间', '内门 / 入口 / 卫生间门'), ('IfcSite / IfcBuildingStorey', '入口层与地坪', '有无台阶')],
   ['door opensTo spaces', 'door IsExternal', 'entrance storey vs site elevation'],
   '每扇门看自己连接哪两个空间和建筑类型：内门净高 ≥ 2.10；公众可达建筑的门净宽 ≥ 0.90（包括卫生间门）；至少一个入口 ≥ 0.90 且无台阶。',
   'Each door reads the two spaces it joins and the building type: internal doors ≥ 2.10 high; in public buildings ≥ 0.90 clear (bathroom doors included); at least one step-free entrance ≥ 0.90.')

sc('R08', 'IfcWall IsExternal (concrete)', '是否附加保温层（外保温或夹心）',
   [('IfcMaterial layers', '墙的材料层', '混凝土 + 保温 / 空气层'), ('IfcSpace', '内侧房间', '采暖 → 需要保温')],
   ['wall hasMaterial layers', 'wall boundedBy heated space'],
   '混凝土外墙看自己的材料层：必须有保温层——外保温系统，或带夹心保温（可背通风）的多叶构造。',
   'A concrete external wall reads its own layers: an insulation layer is mandatory, as ETICS or as a multi-leaf wall with core insulation.')

sc('R42', 'IfcDoor', '洞口模数（875 / 1000 / 1125…）与净宽折减',
   [('IfcOpeningElement / IfcWall', '洞口与墙', '洞口尺寸'), ('IfcDoor', '门扇', 'OverallWidth → 净开启宽度（841 for 875）')],
   ['door fillsOpeningIn wall'],
   '每扇门的洞口应是标准模数或 125 mm 的倍数；标志宽度减去门框后才是净宽（875 洞口只有 841 净宽），和无障碍 0.90 比的是净宽。',
   'Each door opening should be a standard module or a multiple of 125 mm; the clear width is the nominal minus the frame (875 → 841), and it is the clear width that meets the 0.90 test.')

sc('R43', 'IfcDoor IsExternal (emergency exit)', '门型（不得推拉 / 旋转）、总出口宽度 1.0 m / 150 人',
   [('IfcFurniture (seats / desks)', '人数', 'n_people'), ('IfcDoor (other exits)', '其他外门', '可用宽度之和'), ('IfcSpace', '出口所在的门厅', '位置')],
   ['door opensTo entrance space', 'spaces contain seats / desks'],
   '紧急出口按建筑总人数算所需宽度（每 150 人 1.0 m），旋转门和推拉门不算；看剩下的平开门够不够。',
   'Emergency exits are sized by headcount (1.0 m per 150 people); revolving and sliding doors do not count; the remaining swing doors must add up.')

sc('R44', 'IfcWindow (external, heated room)', '玻璃构造（≥ 双层 / 中空）与 U 值',
   [('IfcSpace', '内侧房间', '是否采暖'), ('IfcWall IsExternal', '所在外墙', '外窗'), ('Pset_WindowCommon', '窗', 'ThermalTransmittance')],
   ['window opensTo heated room', 'window fillsOpeningIn external wall'],
   '采暖房间的外窗和落地窗至少用中空或双层玻璃；U 值按 EnEV 随整栋楼核算。',
   'External windows of heated rooms need at least double or insulating glazing; U-values are checked for the whole building under EnEV.')

sc('R45', 'IfcRoof / IfcSlab (flat roof)', '排水坡度 ≥ 2%（推荐 5%）、隔汽层在暖侧',
   [('IfcMaterial layers', '屋面构造层', '隔汽层相对保温层的位置'), ('IfcSpace', '下方房间', '暖侧'), ('IfcSlab', '结构层', 'PitchAngle')],
   ['roof hasMaterial layers', 'roof above heated space'],
   '平屋面看自己的坡度和构造层顺序：至少 2% 坡度（无坡只作例外）；隔汽层必须在保温层的暖侧，否则冷凝。',
   'A flat roof reads its slope and layer order: at least 2 % fall; the vapour barrier on the warm side of the insulation, else condensation.')

sc('R46', 'IfcWall (partition)', '竖向延续（穿吊顶 / 架空地板）、与立面竖梃的连接、隔声节点',
   [('IfcCovering (ceiling / raised floor)', '吊顶与架空地板', '是否存在、是否自身隔声'), ('IfcCurtainWall / IfcMember (mullion)', '立面竖梃', '位于模数网格上、宽度'), ('IfcSpace ×2', '两侧房间', '隔声要求')],
   ['partition meets ceiling / floor', 'partition meets mullion', 'partition boundedBy rooms'],
   '一面隔墙看上下和两端：有吊顶或架空地板时要么穿过去到结构，要么那些构件自己隔声；端部要接到足够宽、落在模数上的立面竖梃；轻质墙和玻璃墙的隔声要与用户商定。',
   'A partition checks above, below and at its ends: through ceiling and raised floor to the structure unless those insulate; ends on a mullion wide enough and on the module; acoustics of light and glass walls agreed with the user.')

sc('R65', 'IfcSpace (corridor) / IfcDoor', '> 30 m 的走廊分段门；楼梯间门自闭防烟',
   [('IfcSpace (corridor)', '走廊', '长度'), ('IfcDoor', '分段门 / 楼梯间门', 'SelfClosing、SmokeStop'), ('IfcSpace (stairwell)', '楼梯间', '门的另一侧'), ('IfcSpace (cellar / shop / workshop)', '通向楼梯的特殊房间', 'T 30')],
   ['door opensTo corridor + stairwell', 'corridor length'],
   '走廊超过 30 m 就要有自闭防烟门分段；凡是楼梯间与疏散走廊之间的门都要自闭防烟；地下室、商店、车间通向楼梯的门还要 T 30。',
   'Corridors over 30 m get self-closing smoke-stop doors; every door between stairwell and escape corridor must be self-closing and smoke-proof; cellars, shops and workshops need T 30 to the stair.')

sc('R98', 'IfcWall / IfcRoof / IfcSlab (external)', 'U 值 = 1 / (R_si + Σ d/λ + R_se)',
   [('IfcMaterialLayer', '各材料层', '厚度 d、导热系数 λ'), ('Pset_*Common', '构件', 'ThermalTransmittance 应与计算一致')],
   ['element hasMaterial layers', 'material thermal properties'],
   '外围护构件把每层 d/λ 加起来，加上内外表面热阻，取倒数得 U；Pset 里填的 ThermalTransmittance 应与之自洽。',
   'An envelope element sums d/λ over its layers plus the surface resistances and inverts the total; the ThermalTransmittance in its Pset should agree.')

sc('R100', 'IfcRoof (pitched)', '保温位置（椽间 / 椽下）、隔汽层室内侧、通风与否',
   [('IfcMaterial layers', '屋面构造层', '保温、隔汽、空气层顺序'), ('IfcBeam / rafter', '椽', '高度是否容纳通风层'), ('IfcSpace', '下方房间', '暖侧')],
   ['roof hasMaterial layers', 'roof above heated space'],
   '坡屋面看构造层顺序：保温在椽间和椽下，隔汽层在室内侧；通风屋面要更高的椽并且隔汽与通风都可靠，所以多采用非通风构造。',
   'A pitched roof reads its layer order: insulation between and below the rafters, vapour barrier on the room side; ventilated roofs need deeper rafters and reliable detailing, hence unventilated is preferred.')


# ───────────── rules activated by the either-side criterion (2026-10-23) ─────────────
sc('R01', 'IfcBuilding', '是否为高层（最高有人停留楼层 > 22 m）',
   [('IfcBuildingStorey', '最高有人停留的楼层', 'Elevation'), ('IfcSite', '室外地坪', 'RefElevation'), ('IfcSpace', '该层是否有人停留', '房间存在')],
   ['storey containedIn building', 'space partOf storey'],
   '整栋楼看最高一个有人停留楼层的楼面离室外地坪多高：超过 22 m 就是高层，疏散楼梯、消防电梯、防火槛墙一整套要求随之生效。',
   'The building reads the elevation of its highest occupied storey above ground: over 22 m it is high-rise and the whole set of high-rise requirements applies.')
sc('R13', 'IfcBuilding / IfcSite', '退距深度 d（到地块边界）',
   [('IfcWall IsExternal', '外墙', '高度 H（地坪到墙顶 / 屋面交线）'), ('IfcRoof', '屋面', '坡度（≤ 70° 计 1/3）'), ('IfcSite', '地块边界与用地性质', '边界几何、一般 / 商业区')],
   ['wall containedIn building', 'site aggregates building'],
   '每面外墙按自己的高度算所需退距：一般地区 0.4 × H 且 ≥ 3 m，商业区 0.2 × H；再和到地块边界的距离比。IFC 里通常没有地块边界，只能算出"所需"。',
   'Each external wall derives its required setback from its height (0.4 × H, min 3 m; 0.2 × H commercial) and compares it with the distance to the plot boundary, which IFC usually lacks.')
sc('R31', 'IfcWall (between use units)', '分隔墙的耐火时间与连续性、开口的封闭',
   [('IfcZone ×2', '墙两侧的使用单元', '是否属于不同单元'), ('IfcWall LoadBearing / IfcColumn', '同层承重构件', '耐火时间 → 分隔墙取同值'), ('IfcSlab / IfcRoof', '上方结构板 / 屋面', '墙须到达'), ('IfcDoor', '墙上的开口', '数量、自闭阻燃')],
   ['wall boundedBy spaces in different zones', 'wall reaches slab', 'door fillsOpeningIn wall'],
   '一面墙如果两侧是不同的使用单元，它就是分隔墙：耐火时间与本层承重构件相当、一直到结构板，墙上开口只能是使用所需的，且自闭阻燃。',
   'A wall between two use units is a separating wall: fire resistance like the storey\'s structure, continuous to the slab, openings only as needed and self-closing fire-retardant.')
sc('R48', 'IfcBuilding / IfcSite', '容积率 GFZ 与建筑密度 GRZ 的分子',
   [('IfcBuildingStorey', '完整楼层', '外轮廓面积之和'), ('IfcSpace (balcony / loggia / terrace)', '不计入的部分', '面积'), ('IfcSite', '地块', '面积（分母，IFC 常缺）'), ('IfcSpace (garage / parking)', '建成面积的组成', '面积')],
   ['storey containedIn building', 'space partOf storey', 'site aggregates building'],
   '整栋楼把完整楼层的外轮廓面积加起来（不算阳台、凉廊、露台）得容积率分子；建成面积要把车库、停车位和地下设施算进去；再除以地块面积。',
   'The building sums the external areas of its full storeys (no balconies, loggias, terraces) for the FAR numerator, counts garages and underground facilities for the coverage ratio, and divides by the plot area.')
sc('R49', 'IfcSpace (every room)', 'DIN 277 类别：使用 / 设备 / 交通面积；可出租面积',
   [('IfcSpace', '房间本身', '名称 / 用途、净面积'), ('IfcWall / IfcColumn', '围合构件', '结构面积'), ('IfcSpace (stair / lift / shaft / plant)', '不可出租的部分', '面积')],
   ['space partOf storey', 'wall boundedBy space'],
   '每个房间按用途归入使用面积、设备面积或交通面积之一；毛面积减结构面积得净面积；楼梯、电梯、管井、设备间不算可出租面积。',
   'Every room is classed as usable, technical or circulation area; gross minus structural area gives net area; stairs, lifts, shafts and plant rooms are not lettable.')
sc('R50', 'IfcBuilding', '总建筑体积 BRI 与净体积 NRI',
   [('IfcBuildingStorey ×n', '各层', 'Elevation 差 = 楼面面层顶到上层楼面面层顶'), ('IfcSlab', '楼板', '面积'), ('IfcSpace', '房间', '净面积 × 净高')],
   ['storey containedIn building', 'space partOf storey'],
   '整栋楼把每层楼面面积乘以层高（面层顶到面层顶）累加得毛体积；净体积用各房间净面积乘净高。',
   'The building multiplies each storey\'s floor area by its height (finish to finish) for the gross volume; net volume is room net area times clear height.')
sc('R51', 'IfcBuilding (terrace house)', '进深 ≤ 12 m、面宽 4–8 m、暗区的用途',
   [('IfcWall IsExternal', '两个采光立面', '间距 = 进深'), ('IfcWall (party wall)', '分户墙', '间距 = 面宽'), ('IfcSpace (stair / storage / dining)', '中部暗区的房间', '位置')],
   ['external walls → depth', 'party walls → width', 'space partOf storey'],
   '联排住宅只有两个立面能采光：进深控制在 12 m 内、面宽 4–8 m，中部必然是暗区，楼梯、辅助房间和就餐区就放在那里。',
   'A terrace house has only two daylight façades: depth within 12 m, width 4–8 m, with stairs, ancillary rooms and dining in the inevitably dark middle zone.')
sc('R54', 'IfcStairFlight (house with ≤ 2 flats)', 'w ≥ 0.80、17/28',
   [('IfcZone / 户门', '住宅的户数', '≤ 2'), ('IfcStair', '是否必要楼梯', '连接各层'), ('IfcBuildingStorey', '两层标高', '升高')],
   ['flat inZone', 'flight partOf stair', 'stair SERVES storey'],
   '不超过两户的住宅，必要楼梯的梯段可以放宽到 0.80 m 宽、17/28；多于两户或非住宅就回到 1.00 m。',
   'In a house with at most two flats the essential stair may be 0.80 wide at 17/28; beyond two flats or outside housing it is 1.00.')
sc('R59', 'IfcBuilding (residential, one flat per floor, no lift)', '层数 ≤ 4',
   [('IfcZone / 户门', '每层户数', '= 1'), ('IfcTransportElement', '电梯', '不存在'), ('IfcBuildingStorey', '楼层数', '≤ 4')],
   ['flat inZone', 'storey containedIn building', 'lift SERVES storey'],
   '一梯一户又没有电梯的住宅，一般只做到四层；交通面积占比高，书里称之为"叠摞的联排 / 城市别墅"。',
   'A residential building with one flat per floor and no lift is generally limited to four storeys; its access area ratio is high.')
sc('R63', 'IfcBuilding (residential, > 2 flats)', '一层住户无障碍可达，户内关键房间轮椅可用',
   [('IfcZone', '户', '数量 > 2'), ('IfcTransportElement / IfcRamp / 入口', '到该层的路径', '无台阶'), ('IfcSpace (living / bed / WC / bath / kitchen)', '该层各户的房间', '活动区尺寸')],
   ['flat inZone', 'lift SERVES storey', 'space inZone'],
   '超过两户的住宅至少要有一层的住户能无台阶到达，这些户的起居室、卧室、一个厕所、一个浴室和厨房要能供轮椅使用。',
   'A building with more than two flats needs one storey whose flats are reached step-free and whose living rooms, bedrooms, one WC, one bathroom and kitchen are wheelchair-usable.')
sc('R70', 'IfcZone (office unit, combi type)', '单间 + 玻璃隔墙 + 中部联系区的组织',
   [('IfcSpace (small single offices)', '外圈小单间', '面积、沿外墙'), ('IfcSpace (connection zone)', '中部联系区', '较深、不靠外墙'), ('IfcWall (partition)', '单间与联系区之间的墙', '材料 = 玻璃'), ('IfcFurniture (shared)', '共用设施', '位于联系区')],
   ['office on_facade', 'partition boundedBy office + zone', 'zone contains shared furniture'],
   '组合式办公的判定看三样：外圈很小的单人间、中部较深的联系区、两者之间是玻璃隔墙，共用设施放在联系区。',
   'A combi-office is recognised by three things: very small cellular offices on the façade, a deep central connection zone, glass partitions between them, shared infrastructure in the zone.')
sc('R77', 'IfcSpace (balcony / terrace)', '面积（7 / 9 m²）与连接的房间',
   [('IfcZone (flat)', '所属户', '人数（external）'), ('IfcDoor', '通向阳台的门', '另一侧是哪个房间'), ('IfcSpace (living / dining / bedroom)', '相连房间', '类型')],
   ['balcony inZone', 'door opensTo balcony + room'],
   '阳台按户内人数定面积（3–4 人 7 m²，5–6 人 9 m²），并通过门与起居、工作或就餐空间相连；有多个户外空间时才接卧室厨房。',
   'A balcony is sized by household (7 m² for 3–4, 9 m² for 5–6) and opens from living, working or dining rooms; bedrooms and kitchens only when there are several.')
sc('R80', 'IfcBuildingStorey (detached house)', '每层是否有门直通户外空间',
   [('IfcDoor IsExternal', '本层的外门', '存在'), ('IfcSpace (terrace / garden / courtyard / roof garden)', '户外空间', '类型'), ('IfcBuilding', '建筑类型', 'detached house（external）')],
   ['door containedIn storey', 'door opensTo external space'],
   '独立住宅的每一层都应有直接通往花园、露台、内院或屋顶花园的门。',
   'Every storey of a detached house should open directly onto a garden, terrace, courtyard or roof garden.')
sc('R81', 'IfcDoor (flat entrance, recessed)', '凹口宽 ≥ 1.25（最好 1.50）、深 ≈ 1.00',
   [('IfcWall IsExternal', '门两侧的外墙', '退让形成的凹口尺寸'), ('IfcSpace (entrance hall)', '门内的门厅', '位置')],
   ['door fillsOpeningIn wall', 'door opensTo hall'],
   '入户门前若做凹口，宽至少 1.25 m（最好 1.50）、深约 1.00 m，让两个人能有遮蔽地在门前等候。',
   'An entrance recess should be at least 1.25 m wide (better 1.50) and about 1.00 m deep so two people can wait sheltered.')
sc('R83', 'IfcSpace (hall / conference / auditorium)', '每人容积 V / 座位数',
   [('IfcFurniture (chair / seat)', '座位', '数量'), ('IfcSpace', '房间', '净面积 × 净高 = 容积'), ('用途', '讲话 / 音乐', 'external')],
   ['space contains chair', 'space Qto volume'],
   '厅室把自己的容积除以座位数：讲话用 4 m³/人，音乐 10 m³/人；容积太小混响不足。',
   'A hall divides its volume by its seats: 4 m³ per person for speech, 10 for music; too little volume gives too little reverberation.')
sc('R84', 'IfcSpace (restaurant kitchen staff area)', '员工 > 10 时的休息室',
   [('IfcSpace (kitchen)', '餐饮厨房', '面积 / 设备数 → 员工数估计'), ('IfcSpace (rest / break room)', '休息室', '存在'), ('IfcSpace (canteen)', '餐厅', '相邻')],
   ['space partOf storey', 'kitchen adjacent canteen'],
   '餐饮厨房的员工区按人数看：超过 10 人必须有休息室。人数 IFC 里没有，只能从厨房规模估。',
   'A restaurant kitchen needs a rest room once staff exceed 10; headcount is not in IFC and has to be estimated from the kitchen size.')
sc('R85', 'IfcSpace (seminar room)', '每生面积 1.9–2.0 m²；单侧通风时进深 ≤ 2.5 × 净高',
   [('IfcFurniture (chair / table)', '座位', '数量'), ('IfcWall IsExternal / IfcWindow', '通风外墙', '只有一面'), ('IfcSpace', '房间', '进深、净高')],
   ['space contains chair', 'window opensTo space', 'space on_facade'],
   '研讨室按座位数算面积（1.9–2.0 m²/人）；如果只靠一面外墙自然通风，进深不超过净高的 2.5 倍。',
   'A seminar room is sized at 1.9–2.0 m² per student; with natural ventilation from one external wall only, depth ≤ 2.5 × clear height.')
sc('R91', 'IfcDoor (residential)', '按角色的净开启宽度：房门 80、浴 WC 70、户门 ≥ 90、大门 ≤ 115',
   [('IfcSpace ×2', '门两侧的房间', '类型决定门的角色'), ('IfcDoor', '门', 'OverallWidth / Height')],
   ['door opensTo spaces', 'door IsExternal'],
   '住宅里每扇门先看自己连接哪两个房间来确定角色，再对照：房门约 80，浴室 WC 约 70，户门至少 90，入户大门最大 115；净高至少 210。',
   'Each door in a dwelling reads the two rooms it joins to find its role, then checks: room doors ~80, bath/WC ~70, flat entrance ≥ 90, front door ≤ 115; height ≥ 210.')
sc('R93', 'IfcWindow (escape window)', '净开口 ≥ 0.9 × 1.2、窗台 ≤ 1.2',
   [('IfcSpace', '所在房间', '是否只有一条楼梯路线'), ('IfcStair', '本层楼梯', '数量 < 2'), ('IfcWindow', '窗', 'OverallWidth / Height、窗台高度'), ('IfcBuildingStorey', '楼层', '离地高度')],
   ['window opensTo room', 'stair SERVES storey', 'window bbox − storey elevation'],
   '一个房间若没有第二条楼梯路线，它的外窗就要能当疏散口：净开口至少 0.9 × 1.2 m，窗台不高于 1.2 m。',
   'A room without a second stair route needs an escape window: clear opening ≥ 0.9 × 1.2 m, sill ≤ 1.2 m.')
sc('R95', 'IfcWall IsExternal (single-leaf masonry)', '材料是否高保温；或附加保温层',
   [('IfcMaterialLayer', '墙的材料层', '层数 = 1、材料名（加气 / 多孔砖）、灰浆'), ('IfcCovering / 保温层', '附加保温', '存在、内 / 外侧')],
   ['wall hasMaterial layers'],
   '单层外墙看自己的材料：要么是高保温砌块配保温砂浆，要么必须加一层内保温或外保温。',
   'A single-leaf external wall reads its material: either highly insulating blocks with insulating mortar, or an added internal / external insulation layer.')
sc('R96', 'IfcWall IsExternal (cavity wall)', '外叶 ≥ 90 mm、空气层 40–150 mm',
   [('IfcMaterialLayer (outer leaf)', '外叶', '厚度'), ('IfcMaterialLayer (air / insulation)', '空腔', '宽度、是否填保温'), ('IfcMaterialLayer (inner leaf)', '内承重叶', '厚度')],
   ['wall hasMaterial layers'],
   '夹心墙逐层核对：外叶至少 90 mm，空气层在 40–150 mm 之间，可以空、可以加保温、可以满填。',
   'A cavity wall checks layer by layer: outer leaf ≥ 90 mm, air gap 40–150 mm, empty, partly or fully insulated.')
sc('R99', 'IfcRoof (green roof)', '坡度：坡屋面 ≤ 25°、平屋面 ≤ 2–3%',
   [('IfcMaterialLayer', '屋面构造层', '含种植 / 基质层'), ('IfcRoof / IfcSlab', '屋面', 'PitchAngle')],
   ['roof hasMaterial layers'],
   '种植屋面看坡度：坡屋面不超过 25°，平屋面不超过 2–3%。',
   'A green roof checks its pitch: ≤ 25° on pitched roofs, ≤ 2–3 % on flat roofs.')
sc('R101', 'IfcWall (party wall)', '面密度 ≥ 400 kg/m²、R′w 53 dB',
   [('IfcZone ×2', '墙两侧的户', '不同户'), ('IfcMaterialLayer', '材料层', '厚度 × 密度'), ('Pset_WallCommon', '墙', 'AcousticRating')],
   ['wall boundedBy spaces in different zones', 'wall hasMaterial layers'],
   '一面墙如果两侧是不同的户，它就是分户墙：面密度至少 400 kg/m²，空气声隔声达 53 dB。',
   'A wall between two flats is a party wall: surface mass ≥ 400 kg/m² and airborne sound insulation 53 dB.')


# ───────────── forced active by the user (2026-10-23) ─────────────
sc('R55', 'IfcStair (spiral)', '外径 ≥ 190 cm、可用宽度 80 cm',
   [('IfcStair (others in the house)', '同一住宅内的其他楼梯', '是否存在 → 是否唯一连接楼梯'), ('IfcBuildingStorey ×2', '所连两层', '升高'), ('IfcSpace', '楼梯所在房间', '是否开敞空间 / 通向夹层')],
   ['stair SERVES storey', 'stair containedIn space', 'stair PredefinedType = SPIRAL_STAIR'],
   '一部螺旋楼梯先看自己是不是住宅里唯一的连接楼梯：是的话外径至少 190 cm、可用宽度 80 cm；踏步处处都重要的地方不该用它，它更适合通向夹层或立在开敞空间里。',
   'A spiral stair first checks whether it is the sole connecting stair in the house: then ≥ 190 cm diameter and 80 cm usable width; it does not belong where every centimetre of tread counts.')
sc('R78', 'IfcSpace (entrance hall of a flat)', '是否直接通向厨房、WC 和楼梯',
   [('IfcDoor (flat entrance)', '户门', '门内第一个房间 = 门厅'), ('IfcDoor', '门厅的其他门', '另一侧的房间类型'), ('IfcSpace (kitchen / WC / stair)', '应直达的房间', '是否与门厅共享一扇门')],
   ['entrance door opensTo hall', 'door opensTo hall + kitchen / WC / stair'],
   '一户的门厅（户门进来的第一个房间）数自己的门通向哪里：厨房、WC 和楼梯这三个最常用的公共部分应该都能从门厅直接进入。',
   'The entrance hall of a flat (the first room behind the flat door) reads where its doors lead: kitchen, WC and stair should all open directly off it.')
sc('R79', 'IfcSpace (internal corridor of a flat)', '净宽 ≥ 1.00 m；柜子做嵌入式',
   [('IfcZone (flat)', '所属户', '户内'), ('IfcWall', '走道两侧的墙', '净距'), ('IfcFurniture (cupboard)', '走道里的柜子', '是否占用宽度')],
   ['corridor inZone', 'wall boundedBy corridor', 'corridor contains furniture'],
   '户内走道量两墙之间的净宽：至少 1.00 m 才能两人错身；这个宽度放不下柜子，柜子要做成嵌入式。',
   'An internal corridor measures the clear width between its walls: ≥ 1.00 m so two people can pass; cupboards do not fit in it and should be built in.')


def main():
    rules, status = {}, {}
    for fn in ('rules_pilot.jsonl', 'rules_office.jsonl', 'rules_general.jsonl'):
        for l in open(os.path.join(HERE, fn), encoding='utf-8'):
            r = json.loads(l); rules[r['rid']] = r
    sp = os.path.join(HERE, '_status.json')
    if os.path.exists(sp):
        status = {k: v['status'] for k, v in json.load(open(sp, encoding='utf-8'))['rules'].items()}
    ids = [s['rid'] for s in S]
    assert len(ids) == len(set(ids)), 'duplicate rid'
    unknown = [i for i in ids if i not in rules]; assert not unknown, unknown
    active = sorted([r for r, st in status.items() if st == 'active'], key=lambda r: int(r[1:]))
    missing = [r for r in active if r not in ids]
    S.sort(key=lambda s: int(s['rid'][1:]))
    with open(os.path.join(HERE, 'scenarios.jsonl'), 'w', encoding='utf-8') as fh:
        for s in S:
            fh.write(json.dumps(s, ensure_ascii=False) + '\n')
    print(f'{len(S)} scenarios → rules/scenarios.jsonl; active rules without scenario: {missing}')


if __name__ == '__main__':
    main()

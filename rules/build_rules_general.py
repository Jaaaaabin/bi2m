"""General rules: the remaining knowledge points (residential, accessibility, high-rise, envelope, area measurement …)
rewritten as context → requirement rules. Complements rules_pilot (R01–R12) and rules_office (R13–R47).

Quotes come from the knowledge points themselves (knowledge/knowledge_probes.jsonl, already verbatim) via kq(kid), plus a few
extra sentences via q(page, quote); every quote is re-checked against data/neufert/embeddings.sqlite before writing.

Context representation (the part that is hard when the book speaks abstractly):
  context.entity        the graph node type(s) the rule attaches to
  context.match         preconditions, as graph predicates (node.attr = value) with a Chinese gloss
  context.derive        variables the extractor must compute before the rule can fire
  context.grounding     for every abstract concept in match/condition: how it is read off the graph, or 'external' if the
                        model cannot tell (then it must come from the model card / brief and the instance says so)
  context.concreteness  direct   – IFC attribute or Pset as is
                        derived  – computed from geometry / relations by the extractor
                        external – needs information no IFC carries (plot boundary, number of occupants, tenancy …)

.venv/bin/python rules/build_rules_general.py
"""
import json, os, sqlite3, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..')
OUT = os.path.join(HERE, 'rules_general.jsonl')
K = {p['kid']: p for p in (json.loads(l) for l in open(os.path.join(ROOT, 'knowledge', 'knowledge_probes.jsonl'), encoding='utf-8'))}


def q(page, quote):
    return {'book_page': str(int(page[-4:]) - 12), 'page': page, 'quote': quote}


def kq(*kids):
    """all basis quotes of the given knowledge points (deduplicated, order kept)"""
    seen, out = set(), []
    for kid in kids:
        for b in K[kid]['basis']:
            key = (b['page'], b['quote'])
            if key not in seen:
                seen.add(key)
                out.append({'book_page': b.get('book_page') or str(int(b['page'][-4:]) - 12), 'page': b['page'], 'quote': b['quote']})
    return out


R = []
def rule(rid, title, level, modality, entity, match, derive, condition, requirement, params, basis, ifc_needed,
         grounding, concreteness, notes='', frm=(), priority=2, chapter=''):
    assert concreteness in ('direct', 'derived', 'external')
    R.append(dict(rid=rid, **{'from': list(frm)}, level=level, modality=modality, title=title, priority=priority, chapter=chapter,
                  context=dict(entity=entity, match=match, derive=derive, grounding=grounding, concreteness=concreteness),
                  condition=condition, requirement=requirement, params=params, basis=basis, ifc_needed=ifc_needed, notes=notes))


# ───────────────────────── Site & Building ─────────────────────────
rule('R48', '容积率与建筑密度的计量口径', 'Site & Building', 'must', 'IfcSite / IfcBuilding',
     {'site.plot_area': '地块面积已知', 'building.storeys': '各层外轮廓面积可量'},
     {'GFZ': '容积率 = Σ(完整楼层外轮廓面积) / 地块面积；不计附属面积、阳台、凉廊、露台和允许建在退距内的构筑物',
      'GRZ': '建筑密度 = 建成面积 / 地块面积；建成面积含建筑平面、车库、停车位及其通道、附属面积和地下设施'},
     'always (within context)',
     '报规划法指标时按上述口径计量：容积率只算完整楼层的外轮廓面积，阳台、凉廊、露台不计入；建筑密度把车库、停车位和地下设施都算进建成面积',
     {'GFZ_counts': 'full storeys, external dimensions', 'GFZ_excludes': ['subsidiary areas', 'balconies', 'loggias', 'terraces', 'structures in setback areas'],
      'GRZ_includes': ['building plan area', 'garages', 'parking places and access', 'subsidiary areas', 'underground facilities']},
     kq('K06') + [q('page_0075', 'the plot coverage ratio determines the permissible ratio of built area on the plot (plan area of building including garages, parking places and their access, subsidiary areas... and underground facilities beneath the plot)')],
     ['IfcSite 地块面积（Pset_SiteCommon.TotalArea 或地块几何，学生模型多缺）', 'IfcBuildingStorey 外轮廓（由外墙几何推）', 'IfcSpace 的阳台/露台识别'],
     {'full storey': '地上、层高正常的 IfcBuildingStorey；地下室和阁楼按当地法规另判，抽取器先全部列出由人决定', 'plot area': 'external：IFC 几乎不带地块边界，须从 model_card / 红线图来',
      'balcony / loggia / terrace': 'IfcSpace 名称或 Pset_SpaceCommon 分类，或 IsExternal 的楼板'},
     'external', '这是计量规则：它不判对错，而是规定“GFZ、GRZ 怎么从模型算出来”；有了地块面积才能和当地允许值比较。', frm=['K06'], priority=2, chapter='Basics · Building regulations')

rule('R49', 'DIN 277 面积分类与可出租面积', 'Site & Building', 'must', 'IfcBuilding / IfcSpace',
     {'space.any': '每个 IfcSpace 都要归类'},
     {'BGF': '毛面积：各层外轮廓面积之和（不含可用屋面）', 'KGF': '结构面积：墙、柱、烟道、不可进入管井、门洞等所有围合构件的平面面积之和',
      'NGF': '净面积 = BGF − KGF，再分为 NF 使用面积 / TF 设备面积 / VF 交通面积', 'rentable': '可出租面积：按 GIF 指南，由专用面积与共用面积组成，楼梯、电梯、紧急出口、设备间和管井不计'},
     'always (within context)',
     '每个房间必须落入 DIN 277 的三类之一：使用面积（服务于建筑用途）、设备面积（设备用房、可进入的管井）或交通面积（楼梯间、走廊、电梯井、疏散阳台）；向租户报面积时楼梯、电梯、管井不算可出租面积',
     {'classes': ['usable area', 'technical function area', 'traffic area'], 'rentable_excludes': ['stairs', 'lifts', 'emergency exits', 'plant rooms', 'shafts']},
     kq('K79') + [q('page_0075', 'The gross floor area is the sum of the plan area of all levels (without usable roof areas), measured between the external dimensions of the surrounding building elements at floor height.'),
                 q('page_0075', 'The leased space is calculated from two types of area:')],
     ['IfcSpace 名称 / LongName / Pset_SpaceCommon.Category', 'Qto_SpaceBaseQuantities.NetFloorArea', 'IfcWall/IfcColumn 平面面积'],
     {'usable / technical / traffic': 'derived：按 IfcSpace 名称关键词（office, meeting → NF；plant, shaft → TF；corridor, stair, lift, lobby → VF）分类，无名房间留给人判',
      'rentable': 'derived：NF + 分摊的共用面积，减去楼梯、电梯、管井所在的 IfcSpace'},
     'derived', '分类规则：作用是给每个房间打上 NF/TF/VF 标签，后面的每工位面积、可出租面积都靠它。', frm=['K79'], priority=2, chapter='Basics · Building regulations')

rule('R50', 'DIN 277 建筑体积的量法', 'Site & Building', 'must', 'IfcBuilding / IfcBuildingStorey',
     {'building.storeys': '≥ 1 个 IfcBuildingStorey'},
     {'BRI': '总建筑体积 = Σ 各层楼面面积 × 该层高度；高度自本层地面面层顶量至上一层地面面层顶', 'NRI': '净建筑体积 = Σ 净面积 × 相应室内净高'},
     'always (within context)',
     '报建筑体积时，毛体积按“楼面面层顶到上层楼面面层顶”的层高乘楼面面积累加；净体积用净面积乘室内净高',
     {'BRI_height': 'top of floor covering → top of next floor covering', 'NRI_height': 'clear room height'},
     kq('K80'),
     ['IfcBuildingStorey.Elevation（层高差）', 'IfcSlab 厚度 / Qto_SpaceBaseQuantities.Height（净高）', '各层楼面面积'],
     {'storey height': 'direct：相邻 IfcBuildingStorey.Elevation 之差', 'clear height': 'direct：Qto_SpaceBaseQuantities.Height，否则层高 − 楼板厚（derived）'},
     'direct', '计量规则，和 R48/R49 配套。', frm=['K80'], priority=1, chapter='Basics · Building regulations')

rule('R51', '联排住宅的进深与面宽', 'Site & Building', 'should', 'IfcBuilding',
     {'building.usage': 'residential', 'building.form': 'terrace / row house（只有两个立面能直接采光）'},
     {'depth': '两条采光立面之间的建筑进深', 'width': '单元面宽（分户墙间距）'},
     'building.form = terrace house',
     '经济进深不超过 12 m、面宽 4–8 m；中部必然出现采光差的暗区，用来放楼梯、辅助房间（常含就餐区）——设计时就把这些功能放在中部',
     {'depth_max_m': 12, 'width_m': [4, 8], 'dark_middle_zone': ['stairs', 'subsidiary rooms', 'dining']},
     kq('K92'),
     ['IfcBuilding 外轮廓 / 外墙 IsExternal', '分户墙（IfcWall 位置）', 'model_card 建筑类型'],
     {'terrace house': 'external / derived：model_card 说明，或从“只有两个相对立面有窗、两侧为分户墙”推出', 'depth / width': 'derived：外墙几何'},
     'derived', '', frm=['K92'], priority=2, chapter='Housing · Building types')

rule('R52', '高层建筑分级与各级要求', 'Site & Building', 'must', 'IfcBuilding',
     {'building.is_high_rise': 'R01 判定为高层（最高有人停留楼层 > 22 m）'},
     {'H_fire': '最高有人停留楼层地面距消防车停放面的高度', 'group': 'I: 22–30 m；II: 30–60 m；III: 60–200 m；IV: > 200 m'},
     'H_fire > 22',
     'I 级：适用高层建筑规定；II 级：至少 1 部消防电梯；III 级：结构重要构件 F 120，可要求多部消防电梯；IV 级：审批机关可提出进一步要求',
     {'I': [22, 30], 'II': [30, 60], 'III': [60, 200], 'IV': '>200', 'II_req': '≥1 fire service lift', 'III_req': 'structural elements F 120'},
     [q('page_0258', 'High-rise group | Height above fire service parking area | Special requirements\nI | 22–30 m | high-rise regulations apply\nII | 30–60 m | at least 1 fire service lift\nIII | 60–200 m | elements of structural significance must be F 120 and many fire service lifts can be required\nIV | over 200 m | the approval authority can place further requirements')],
     ['IfcBuildingStorey.Elevation', 'IfcSite.RefElevation（消防车停放面近似取室外地坪）', 'IfcTransportElement（消防电梯）', '构件 FireRating'],
     {'height above fire service parking area': 'derived：最高有人停留的 IfcBuildingStorey.Elevation − 室外地坪；停放面本身 external', 'fire service lift': 'direct：IfcTransportElement + Pset_TransportElementCommon.FireExit / 名称含 fire/Feuerwehr'},
     'derived', '', frm=['K152'], priority=3, chapter='High-rise buildings')

rule('R53', '高层建筑的用途限制', 'Site & Building', 'must', 'IfcBuilding',
     {'building.is_high_rise': 'R01 判定为高层', 'building.usage': '学校 / 医院 / 养老院'},
     {}, 'building.is_high_rise AND building.usage IN {school, hospital, home for elderly}',
     '不允许：按德国现行法规，高层建筑不得用作学校、医院或养老院——这类用途必须改为非高层体量',
     {'forbidden_uses': ['school', 'hospital', 'home for elderly people']},
     kq('K153'),
     ['IfcBuildingStorey.Elevation', 'model_card 用途 / IfcBuilding Pset_BuildingCommon.OccupancyType'],
     {'usage': 'external：Pset_BuildingCommon.OccupancyType 极少填写，实际靠 model_card；也可从房间名（classroom, ward, patient room）推（derived）'},
     'external', '', frm=['K153'], priority=2, chapter='High-rise buildings')

# ───────────────────────── Storey ─────────────────────────
rule('R54', '不超过两户的住宅楼梯', 'Storey', 'must', 'IfcStair / IfcStairFlight',
     {'building.usage': 'residential', 'building.flats': '≤ 2 户', 'stair.essential': '法定必要楼梯'},
     {'w': '梯段可用宽度', 'r/t': '踢面 / 踏面（cm）'},
     'building.flats ≤ 2 AND stair.essential',
     '可用宽度 ≥ 0.80 m，踏步比 17/28；（对比：其他必要楼梯 1.00 m、17/28，高层住宅 1.25 m）',
     {'width_min_m': 0.80, 'riser_tread_cm': '17/28', 'other_essential_m': 1.00, 'high_rise_flats_m': 1.25},
     kq('K12') + [q('page_0132', 'but legally essential stairs 1.00 m, 17/28, high-rise flats 1.25 m width')],
     ['IfcStairFlight 宽度（几何）', 'Pset_StairFlightCommon.RiserHeight / TreadLength', '户数（IfcZone 或 model_card）'],
     {'number of flats': 'external / derived：IfcZone 分户，或按“每户一个厨房”的房间名数', 'legally essential stair': 'derived：连接各层且通往出口的楼梯视为必要楼梯；明显的户内附加楼梯视为非必要（见 R56）'},
     'derived', '', frm=['K12'], priority=2, chapter='Stairs')

rule('R55', '螺旋楼梯作为户内唯一楼梯', 'Storey', 'must', 'IfcStair',
     {'stair.shape': '螺旋 / 圆形（IfcStair.PredefinedType = SPIRAL_STAIR 或平面为圆）', 'stair.role': '住宅内唯一的连接楼梯'},
     {'D': '外径', 'w': '可用行走宽度'},
     'stair.shape = spiral AND stair.role = sole connecting stair inside house',
     '外径 ≥ 190 cm、可用宽度 80 cm；踏步处处都重要的地方不宜用螺旋楼梯，它更适合通往夹层、看台或立在开敞空间里',
     {'diameter_min_cm': 190, 'usable_width_cm': 80},
     kq('K14') + [q('page_0136', 'Although spiral staircases appear generous, they should not be installed where every last centimetre of tread is important.')],
     ['IfcStair.PredefinedType', 'IfcStair 几何（bbox 近似外径）', '同户其他楼梯的存在（sole 判定）'],
     {'spiral': 'direct：PredefinedType = SPIRAL_STAIR；否则 derived：bbox 近似正方且梯段弯曲', 'sole connecting stair': 'derived：该户/该住宅内没有其他连接同两层的 IfcStair'},
     'derived', '', frm=['K14'], priority=1, chapter='Stairs')

rule('R56', '非法定必要楼梯的最小尺寸', 'Storey', 'must', 'IfcStair / IfcStairFlight',
     {'stair.essential': 'false：不是法规意义上的必要楼梯（不作为疏散路线）'},
     {'w': '可用宽度', 'r/t': '踏步比'},
     'NOT stair.essential',
     '可用宽度可低至 0.50 m、踏步比 21/21——前提是它不承担疏散功能；一旦它是某层唯一的下楼路线，就按必要楼梯 1.00 m、17/28',
     {'width_min_m': 0.50, 'riser_tread_cm': '21/21'},
     kq('K19'),
     ['IfcStair 连接关系（serves 哪些层）', 'Pset_StairFlightCommon', '同层其他楼梯'],
     {'legally essential': 'derived：若某层除此楼梯外还有 ≥1 条通向出口的楼梯，且本楼梯只在一户/一房间内部，则视为非必要'},
     'derived', '', frm=['K19'], priority=1, chapter='Stairs')

rule('R57', '无障碍建筑楼梯起止处的活动区', 'Storey', 'must', 'IfcStair / IfcSpace',
     {'building.public_access': '公众可达 / 无障碍要求的建筑', 'stair.any': '每段楼梯的起步与到达处'},
     {'w_move': '楼梯起步 / 到达处前方活动区宽度（不计首级踏面）'},
     'building.public_access',
     '上下楼梯旁的活动区宽度至少 1.50 m；首级踏步的踏面不计入活动区',
     {'movement_area_width_min_m': 1.50, 'first_tread_excluded': True},
     kq('K32') + [q('page_0034', 'min. 1.50 m wide ...\nin corridors, main routes and next to stairs up and down.')],
     ['IfcStairFlight 端点位置', '相邻 IfcSpace 净尺寸 / 家具 bbox'],
     {'public access': 'external：model_card；办公楼默认视为公众可达（R07 的 K27 范围）', 'movement area': 'derived：梯段端点前方、与踏步同宽的矩形内无墙无家具的深度'},
     'derived', '', frm=['K32'], priority=2, chapter='Accessibility')

rule('R58', '住宅超过五个完整楼层须设电梯', 'Storey', 'must', 'IfcBuilding / IfcTransportElement',
     {'building.usage': 'residential'},
     {'n_full_storeys': '完整楼层数（地上、可住）', 'has_lift': '是否有 IfcTransportElement(ELEVATOR) 或电梯井'},
     'n_full_storeys > 5',
     '必须设电梯；一梯两户是最常见、品质与经济性平衡的交通组织',
     {'storeys_threshold': 5, 'typical_flats_per_stair': 2},
     kq('K83') + [q('page_0154', 'Two flats per floor is the most common access method, with balanced advantages of residential quality and value for money.')],
     ['IfcBuildingStorey 数量与标高', 'IfcTransportElement / 名为 lift、elevator、Aufzug 的 IfcSpace'],
     {'full floor': 'derived：地上且含居住房间的 IfcBuildingStorey', 'lift': 'direct：IfcTransportElement；否则 derived：竖向贯通的小面积 IfcSpace 名含 lift/elevator'},
     'derived', '', frm=['K83'], priority=2, chapter='Housing · Access')

rule('R59', '一梯一户无电梯时限四层', 'Storey', 'typical', 'IfcBuilding / IfcStair',
     {'building.usage': 'residential', 'access.flats_per_floor': '每层每梯 1 户', 'has_lift': 'false'},
     {'n_storeys': '楼层数'},
     'access.flats_per_floor = 1 AND NOT has_lift',
     '一般限四层；这种“叠摞的联排 / 城市别墅”交通面积占比高、不经济',
     {'storeys_max_without_lift': 4},
     kq('K91'),
     ['IfcStair 与各层户数（IfcZone / 户门数）', 'IfcTransportElement'],
     {'flats per floor per stair': 'derived：每层由同一楼梯间到达的户门（IfcDoor 名含 entrance/Wohnungstür）数，或 IfcZone 数'},
     'derived', '', frm=['K91'], priority=1, chapter='Housing · Access')

rule('R60', '消防电梯（高度超过 30 m）', 'Storey', 'must', 'IfcBuilding / IfcTransportElement',
     {'building.H_fire': '> 30 m（R52 II 级及以上）'},
     {'n_fire_lifts': '独立井道内的消防电梯数', 'coverage': '从消防电梯出发，使用房间各点的最大半径'},
     'H_fire > 30',
     '至少一部位于独立井道内的消防电梯，从它出发 50 m 半径内须能到达任何使用房间的每一点；须设带消火栓的前室，大小应能把担架运进电梯；通道至少 T 30',
     {'height_threshold_m': 30, 'radius_max_m': 50, 'min_fire_lifts': 1, 'lobby': 'with hydrant, stretcher-sized', 'access_fire_rating': 'T 30'},
     kq('K149') + [q('page_0258', 'It must have an anteroom with a hydrant, which is large enough to enable the transport of stretchers to the lift. Access routes must be at least T 30 fire-retarding.')],
     ['IfcTransportElement + 井道', '各层 IfcSpace 几何（半径覆盖）', '前室 IfcSpace', 'IfcDoor.FireRating'],
     {'fire service lift': 'direct/derived：名称或 Pset；否则任何独立井道电梯都算候选并标“未确认”', 'radius 50 m': 'derived：电梯门中心到各使用房间最远点的平面距离'},
     'derived', '', frm=['K149'], priority=3, chapter='High-rise buildings')

rule('R61', '高层疏散楼梯的梯井、排烟与出口', 'Storey', 'must', 'IfcStair / IfcSpace',
     {'building.is_high_rise': 'true', 'stair.essential': '疏散楼梯'},
     {'wellhole': '梯井宽度（两梯段之间净距）', 'smoke_outlet_area': '楼梯间顶部排烟口面积', 'exit': '楼梯间出口通向何处'},
     'building.is_high_rise',
     '梯井 ≥ 0.80 m（避免在梯段上铺水带）；最高处设排烟口，面积为楼梯间楼面的 5% 且 ≥ 1 m²；出口直通室外或经无火灾荷载的门厅；每段梯段行走宽度 ≥ 1.25 m',
     {'wellhole_min_m': 0.80, 'smoke_outlet': '5% of floor area, ≥ 1 m²', 'exit': 'directly to open air or via lobby without fire load', 'walking_width_min_m': 1.25},
     kq('K150') + [q('page_0258', 'The exit must be directly into the open air or through a lobby without any fire load.'), q('page_0258', 'Their walking width must be at least 1.25 m.')],
     ['IfcStairFlight 几何（梯井 = 两段间距）', '楼梯间 IfcSpace 面积与顶部开口 / IfcWindow', '楼梯间出口 IfcDoor 与 IsExternal'],
     {'wellhole': 'derived：同一楼梯两平行梯段 bbox 的净距', 'smoke outlet': 'direct：楼梯间顶层 IfcWindow / IfcOpening，常缺', 'exit': 'derived：楼梯间 IfcDoor.IsExternal 或经由的 IfcSpace 类型'},
     'derived', '', frm=['K150'], priority=3, chapter='High-rise buildings')

rule('R62', '高层电梯分组', 'Storey', 'should', 'IfcBuilding / IfcTransportElement',
     {'building.is_high_rise': 'true'},
     {'n_storeys': '层数', 'n_lifts': '电梯部数'},
     'always (within context)',
     '约 25 层以下通常只设一组电梯、所有电梯服务所有楼层；需要超过 6 部电梯时分成两组',
     {'one_group_up_to_storeys': 25, 'split_above_lifts': 6},
     kq('K151'),
     ['IfcBuildingStorey 数', 'IfcTransportElement 数与 serves 关系'],
     {'lift group': 'derived：按 serves 的楼层集合分组'},
     'derived', '', frm=['K151'], priority=1, chapter='High-rise buildings')

# ───────────────────────── Zone ─────────────────────────
rule('R63', '超过两户的住宅须有一层无障碍', 'Zone', 'must', 'IfcZone (flat) / IfcSpace',
     {'building.usage': 'residential', 'building.flats': '> 2 户'},
     {'accessible_floor': '是否存在一层，其各户可无障碍到达', 'wheelchair_rooms': '这些户内的起居室、卧室、一个厕所、一个浴室、厨房是否轮椅可用'},
     'building.flats > 2',
     '至少一层的住户须无障碍可达；这些户内的起居室、卧室、一个厕所、一个浴室和厨房须可供轮椅使用（活动区按 R65 / R66）',
     {'flats_threshold': 2, 'rooms_wheelchair': ['living rooms', 'bedrooms', 'one toilet', 'one bathroom', 'kitchen']},
     kq('K34'),
     ['IfcZone / 户门', '入口与该层之间有无台阶（IfcStair, IfcRamp, IfcTransportElement）', 'IfcSpace 名称 + 活动区几何'],
     {'flat': 'derived：IfcZone，或由户门划分的房间组', 'accessible': 'derived：从室外入口到该层无台阶（R07 的逻辑）'},
     'derived', '', frm=['K34'], priority=2, chapter='Accessibility · Housing')

rule('R64', '高层建筑疏散走道', 'Zone', 'must', 'IfcSpace (corridor) / IfcDoor',
     {'building.is_high_rise': 'true', 'space.role': '走廊 / 疏散路线'},
     {'w': '走道净宽', 'd_walk': '使用房间任一点到楼梯间的步行距离', 'L_corridor': '走廊长度', 'directions': '走廊可向几个方向疏散'},
     'building.is_high_rise',
     '疏散通道宽 ≥ 1.25 m，宜双向通往各楼梯间；任一点步行距离 ≤ 25 m；双向走廊 ≤ 40 m，每 20 m 设防烟自闭门；单向尽端走廊 ≤ 10 m（有第二疏散路线如疏散阳台时 ≤ 20 m）',
     {'width_min_m': 1.25, 'walk_max_m': 25, 'two_way_corridor_max_m': 40, 'smoke_door_every_m': 20, 'dead_end_max_m': 10, 'dead_end_with_2nd_route_m': 20},
     kq('K45'),
     ['走廊 IfcSpace 几何', '楼梯间位置', 'IfcDoor Pset_DoorCommon.SmokeStop / SelfClosing'],
     {'corridor': 'derived：细长、连接多个房间门的 IfcSpace（名含 corridor/Flur 或长宽比 > 3 且 opensTo ≥ 3 扇门）', 'walking distance': 'derived：房间最远角到最近楼梯间门的折线距离'},
     'derived', '', frm=['K45'], priority=3, chapter='High-rise buildings')

rule('R65', '长疏散走廊分段与楼梯间门', 'Zone', 'must', 'IfcSpace (corridor) / IfcDoor',
     {'space.role': '法定必要的疏散走廊', 'door.between': '楼梯间与走廊之间的门'},
     {'L_corridor': '走廊长度', 'door.self_closing': '自闭', 'door.smoke_proof': '防烟'},
     'L_corridor > 30 OR door connects stair and corridor',
     '超过 30 m 的必要疏散走廊须用自闭、防烟的门分段；楼梯与疏散走廊之间的门也须自闭、防烟；地下室、空置屋顶空间、车间、商店通向楼梯的门须自闭、防烟并至少阻火（如 T 30）',
     {'segment_every_m': 30, 'door_props': ['self-closing', 'smoke-proof'], 'cellar_shop_to_stair': 'T 30'},
     kq('K47') + [q('page_0529', 'Cellars, unoccupied roof spaces, workshops, shops, etc. must have self-closing, smoke-proof and fire-retardant closures (e.g. T 30 door) into the stairs.')],
     ['走廊 IfcSpace 长度', 'IfcDoor Pset_DoorCommon.SelfClosing / SmokeStop / FireRating', 'opensTo 关系（门两侧是哪两个房间）'],
     {'legally essential corridor': 'derived：从使用房间到楼梯间必经的走廊', 'door between stair and corridor': 'derived：opensTo 同时指向楼梯间空间和走廊空间的 IfcDoor'},
     'derived', '', frm=['K47'], priority=3, chapter='Fire protection')

rule('R66', '住宅居住面积的计算方法', 'Zone', 'must', 'IfcZone (flat) / IfcSpace',
     {'building.usage': 'residential', 'zone.flat': '一套住宅'},
     {'A_full': '净高 ≥ 2 m 部分的地面面积', 'A_half': '净高 ≥ 1 m 且 < 2 m 部分的面积', 'A_balcony': '阳台、凉廊、露台面积', 'measure': '按构件间净空，从饰面表面量起'},
     'always (within context)',
     '居住面积 = A_full + 0.5 × A_half + (25–50%) × A_balcony；房间面积按构件之间的净空间量，从饰面层表面起算；地下室、车库、办公室不计',
     {'clear_height_full_m': 2.0, 'clear_height_half_m': [1.0, 2.0], 'balcony_share': [0.25, 0.5], 'measure_from': 'face of cladding'},
     kq('K76', 'K77', 'K78'),
     ['IfcSpace Qto_SpaceBaseQuantities.NetFloorArea / Height', '坡顶下净高变化（IfcRoof 几何）', '阳台 IfcSpace'],
     {'flat': 'derived：IfcZone 或户门划分', 'part of room below 2 m': 'derived：坡屋面下按净高剖切，学生模型一般只能整间处理', 'balcony': 'derived：IsExternal 或名称'},
     'derived', '计量规则，三个知识点合并；它决定“房间面积”在后续所有住宅规则里怎么算。', frm=['K76', 'K77', 'K78'], priority=2, chapter='Housing · Area')

rule('R67', '户内分组：起居区与睡眠区', 'Zone', 'typical', 'IfcZone (flat) / IfcSpace',
     {'building.usage': 'residential', 'zone.flat': '一套住宅', 'plan.type': '分组式平面'},
     {'living_group': '起居室、厨房、就餐区', 'sleeping_group': '卧室、卫生间', 'adjacency': '两组各自是否连成一片'},
     'plan.type = grouped plan',
     '把户内房间分成两个组团：起居区（起居室、厨房、就餐）和睡眠区（卧室、卫生间）；中廊式平面则沿两侧立面排房间、每间都能独立进入',
     {'groups': {'living': ['living room', 'kitchen', 'dining'], 'sleeping': ['bedrooms', 'bathrooms']}},
     kq('K85'),
     ['IfcSpace 名称', 'opensTo / 相邻关系'],
     {'grouped plan': 'derived：按房间名归到两组后检查组内连通；无法判断时规则只输出分组建议'},
     'derived', '', frm=['K85'], priority=1, chapter='Housing · Layout')

rule('R68', '每套住宅的最低配置：厨房、储藏间、卫生间', 'Zone', 'must', 'IfcZone (flat) / IfcSpace',
     {'building.usage': 'residential', 'zone.flat': '一套住宅'},
     {'has_kitchen': '是否有厨房或小厨房', 'has_storeroom': '是否有足够大的储藏间', 'has_bathroom': '是否有含浴缸/淋浴和厕所的独立房间'},
     'always (within context)',
     '每户至少一个厨房或小厨房、一个足够大的储藏间、一个卫生间（独立房间，含浴缸/淋浴和厕所）；大户型宜浴厕分设或加客用 WC',
     {'kitchen_min': 1, 'storeroom_min': 1, 'bathroom_min': 1, 'bathroom_def': 'independent room with bath/shower and toilet'},
     kq('K94', 'K103'),
     ['IfcSpace 名称 / LongName', 'IfcSanitaryTerminal 类型（bath, shower, WC）', 'contains 关系'],
     {'flat': 'derived：IfcZone 或户门划分', 'kitchen': 'direct：名称 kitchen/Küche，或 derived：contains 灶台/水槽家具', 'bathroom': 'derived：contains WC 且 contains bath 或 shower'},
     'derived', '', frm=['K94', 'K103'], priority=2, chapter='Housing · Layout')

rule('R69', '户内储藏空间', 'Zone', 'should', 'IfcZone (flat) / IfcSpace',
     {'building.usage': 'residential', 'zone.flat': '一套住宅'},
     {'A_store': '储藏空间面积（可分散）', 'w_store': '储藏间净宽', 'A_flat': '户面积'},
     'always (within context)',
     '储藏空间 ≥ 1 m²、净宽 75 cm；较大住宅按户面积的 2% 设置（可分成多处）；储藏间门宜外开',
     {'area_min_m2': 1, 'clear_width_cm': 75, 'large_flat_share': 0.02},
     kq('K107'),
     ['IfcSpace 名称 storage/Abstellraum', 'Qto_SpaceBaseQuantities', '户面积（R66）'],
     {'storage space': 'direct：名称；derived：壁柜家具（IfcFurniture 类型含 wardrobe/closet）也算', 'larger flat': 'external：书中未给阈值，由人定'},
     'derived', '', frm=['K107'], priority=1, chapter='Housing · Layout')

rule('R70', '组合式办公（combi-office）的组织', 'Zone', 'typical', 'IfcZone (office unit) / IfcSpace',
     {'building.usage': 'office', 'office.type': 'combi-office（R24 分类结果）'},
     {'cells': '沿外墙的很小单间办公', 'core_zone': '较深的中部联系区', 'partition': '单间与联系区之间的隔墙材料'},
     'office.type = combi',
     '很小的单间办公室用玻璃隔墙与较深的联系区分开，共用设施（复印、茶水、会议）放在联系区内；每人有专注工作的单间，中部共用区促进交流',
     {'partition_to_core': 'glass', 'shared_infrastructure_in': 'connection zone'},
     kq('K135') + [q('page_0251', 'Each employee is provided with an individual workstation for concentrated work and a jointly used room in the central zone, with its glass partitions, encourage communication')],
     ['IfcSpace 布置', 'IfcWall 材料（玻璃）', 'contains 共用设施家具'],
     {'combi-office': 'derived：外圈一圈小单间（每间 1 工位、面积 8–12 m²）+ 中部大 IfcSpace，且隔墙材料含 glass', 'connection zone': 'derived：中部不靠外墙的大 IfcSpace'},
     'derived', '', frm=['K135'], priority=1, chapter='Office buildings · Types')

# ───────────────────────── Space ─────────────────────────
rule('R71', '轮椅转身空间与无障碍走廊宽度', 'Space', 'should', 'IfcSpace',
     {'building.public_access': '公众可达 / 无障碍要求', 'space.any': '每个房间；走廊和门厅'},
     {'turn': '房间内最大内切 1.50 × 1.50 m 方块是否放得下', 'w_corridor': '走廊 / 主通道净宽'},
     'building.public_access',
     '每个房间宜提供至少 1.50 m 深 × 1.50 m 宽的转身空间；走廊、主通道、楼梯上下处 ≥ 1.50 m 宽；活动区尺寸 0.90–1.80 m 可以互相重叠，电梯门前除外',
     {'turning_m': [1.5, 1.5], 'corridor_width_min_m': 1.5, 'no_overlap_in_front_of': 'lift doors'},
     kq('K28') + [q('page_0033', 'The dimensions of the movement area are 0.90–1.80 m and may overlap – except in front of lift doors.')],
     ['IfcSpace 几何', 'contains 家具 bbox', '走廊识别'],
     {'turning space': 'derived：房间净轮廓减家具后最大内切正方形', 'corridor': 'derived：见 R64 的识别方法'},
     'derived', '', frm=['K28'], priority=2, chapter='Accessibility')

rule('R72', '长走廊的轮椅会车位', 'Space', 'must', 'IfcSpace (corridor)',
     {'building.public_access': '无障碍要求', 'space.role': '走廊 / 通道'},
     {'L': '走廊长度', 'passing': '是否存在 ≥ 1.80 × 1.80 m 的会车位'},
     'L > 15',
     '须设宽、深均 ≥ 1.80 m 的两轮椅会车位',
     {'length_threshold_m': 15, 'passing_place_m': [1.8, 1.8]},
     kq('K33'),
     ['走廊 IfcSpace 几何'],
     {'corridor': 'derived：见 R64', 'passing place': 'derived：走廊轮廓内任一处宽度 ≥ 1.80 m 且长 ≥ 1.80 m'},
     'derived', '', frm=['K33'], priority=2, chapter='Accessibility')

rule('R73', '无障碍住宅的卫浴活动区', 'Space', 'must', 'IfcSpace (bathroom) / IfcSanitaryTerminal',
     {'zone.flat.accessible': '无障碍住宅（R63 指定的那一层）', 'space.function': 'bathroom / WC'},
     {'wc_side': 'WC 一侧的活动区宽 × 深', 'wc_other_side': 'WC 另一侧到墙或家具的距离', 'front_areas': '淋浴区、WC、洗手台前的活动区'},
     'always (within context)',
     'WC 一侧活动区 ≥ 95 cm 宽 × 70 cm 深，另一侧到墙或家具 ≥ 30 cm；浴室须设轮椅可用的淋浴；淋浴区及 WC、洗手台前须有 ≥ 1.50 × 1.50 m 活动区',
     {'wc_side_cm': [95, 70], 'wc_other_side_min_cm': 30, 'front_movement_m': [1.5, 1.5], 'shower': 'wheelchair accessible'},
     kq('K35') + [q('page_0035', 'min. 1.50 m wide and min. 1.50 m deep...\na turning place in every room (excepting small rooms, which the wheelchair user can use by moving backwards and forwards), the shower → ① + ④, in front of the WC and vanity unit → ② – ④')],
     ['IfcSanitaryTerminal 位置与类型', '卫生间 IfcSpace 几何'],
     {'accessible flat': 'derived：R63', 'WC / shower / basin': 'direct：IfcSanitaryTerminal.PredefinedType 或类型名'},
     'derived', '', frm=['K35'], priority=2, chapter='Accessibility · Housing')

rule('R74', '轮椅住宅的起居室最小面积与宽度', 'Space', 'should', 'IfcSpace (living room)',
     {'zone.flat.accessible': '轮椅使用者住宅', 'space.function': 'living room with eating area', 'flat.occupants': '人数'},
     {'A': '起居室（含就餐区）面积', 'w': '房间宽度'},
     'always (within context)',
     '1 人 22 m²、2–4 人 24 m²、5 人 26 m²、6 人 28 m²；1–2 人户最小房间宽度 3.75 m',
     {'area_m2': {'1': 22, '2-4': 24, '5': 26, '6': 28}, 'width_min_m_1_2_persons': 3.75},
     kq('K36'),
     ['IfcSpace 面积 / 尺寸', '户型人数（external）'],
     {'occupants': 'external：由卧室数推（derived）或 model_card', 'living room with eating area': 'direct：名称 living/Wohnen；就餐区可能是同一 IfcSpace'},
     'external', '', frm=['K36'], priority=1, chapter='Accessibility · Housing')

rule('R75', '无障碍住宅的户内活动区宽度 1.20 m', 'Space', 'must', 'IfcSpace / IfcFurniture',
     {'zone.flat.accessible': '无障碍住宅', 'space.any': '户内所有房间与通道'},
     {'w_beside_furniture': '轮椅侧向接近的家具旁宽度', 'w_bed_side': '非轮椅使用者床的进入侧宽度', 'w_wall_to_wall': '户内墙与墙之间', 'w_passage': '户内通道'},
     'always (within context)',
     '以下活动区须至少 1.20 m 宽：轮椅侧向接近的家具旁、非轮椅使用者床的进入侧、户内墙与墙之间、操作设备旁、坡道护轮缘之间以及户内通道',
     {'width_min_m': 1.2},
     kq('K37'),
     ['contains 家具 bbox', 'IfcSpace 几何', '户内走道'],
     {'movement area': 'derived：家具 bbox 到最近墙或其他家具的净距'},
     'derived', '', frm=['K37'], priority=2, chapter='Accessibility · Housing')

rule('R76', '居室的最低要求', 'Space', 'must', 'IfcSpace (habitable room)',
     {'building.usage': 'residential', 'space.function': '居室（起居室、卧室、儿童房等有人长期停留的房间）'},
     {'A': '地面面积', 'h': '净高', 'A_window': '窗面积', 'ratio': 'A_window / A'},
     'always (within context)',
     '面积 ≥ 8 m²、净高 ≥ 2.40 m、窗面积 ≥ 房间面积的 1/8，并满足朝向与通风要求',
     {'area_min_m2': 8, 'clear_height_min_m': 2.40, 'window_to_floor_ratio_min': '1/8'},
     kq('K74'),
     ['Qto_SpaceBaseQuantities.NetFloorArea / Height', 'IfcWindow OverallWidth × OverallHeight + opensTo'],
     {'habitable room': 'derived：名称 living/bed/child/Zimmer；不含 kitchen、bath、corridor、storage', 'window of the room': 'derived：opensTo 指向该房间的 IfcWindow'},
     'derived', '', frm=['K74'], priority=3, chapter='Housing · Rooms')

rule('R77', '阳台面积与户外空间的连接', 'Space', 'typical', 'IfcSpace (balcony / terrace)',
     {'building.usage': 'residential', 'space.function': 'balcony / loggia / terrace', 'flat.occupants': '人数'},
     {'A': '阳台面积', 'connected_to': '阳台从哪个房间进入'},
     'always (within context)',
     '3–4 人约 7 m²，5–6 人约 9 m²；户外空间一般与起居、工作、就餐空间相连，有多个户外空间时也可接卧室、厨房',
     {'area_m2': {'3-4 persons': 7, '5-6 persons': 9}, 'connect_to': ['living', 'working', 'dining'], 'additional_ok': ['bedroom', 'kitchen']},
     kq('K81', 'K82'),
     ['阳台 IfcSpace / IsExternal 楼板', 'opensTo（阳台门连接哪个房间）', '人数（external）'],
     {'balcony': 'derived：IsExternal 或名称', 'connected to': 'derived：IfcDoor opensTo 同时指向阳台和某房间'},
     'derived', '', frm=['K81', 'K82'], priority=1, chapter='Housing · Rooms')

rule('R78', '门厅直达厨房、WC 和楼梯', 'Space', 'should', 'IfcSpace (entrance hall)',
     {'building.usage': 'residential', 'space.function': 'entrance hall / Diele'},
     {'direct_to_kitchen': '门厅与厨房之间有门', 'direct_to_wc': '门厅与 WC 之间有门', 'direct_to_stair': '门厅通楼梯'},
     'always (within context)',
     '厨房、WC 和楼梯应能从门厅直接到达',
     {'must_adjoin': ['kitchen', 'WC', 'staircase']},
     kq('K87'),
     ['IfcSpace 名称', 'opensTo 关系'],
     {'entrance hall': 'derived：户门 opensTo 的第一个室内 IfcSpace', 'directly accessible': 'derived：两房间共享一扇 IfcDoor（opensTo 两端）'},
     'derived', '', frm=['K87'], priority=2, chapter='Housing · Layout')

rule('R79', '户内走道宽度', 'Space', 'typical', 'IfcSpace (internal corridor)',
     {'building.usage': 'residential', 'space.role': '户内走道'},
     {'w': '走道净宽', 'cupboards': '走道内是否放柜子'},
     'always (within context)',
     '最小宽度 1 m（两人可错身）；这个宽度放不下柜子，柜子宜做嵌入式',
     {'width_min_m': 1.0, 'cupboards': 'built-in'},
     kq('K89'),
     ['走道 IfcSpace 几何', 'contains 家具'],
     {'internal corridor': 'derived：户内细长 IfcSpace'},
     'derived', '', frm=['K89'], priority=1, chapter='Housing · Layout')

rule('R80', '独立住宅每层直通户外', 'Space', 'typical', 'IfcBuildingStorey / IfcSpace',
     {'building.usage': 'residential', 'building.form': 'detached house'},
     {'storey.has_outdoor_access': '每层是否有门通向花园、露台、内院或屋顶花园'},
     'building.form = detached house',
     '从每一层都可直接通往私有或半公共的户外空间（花园、露台、内院、屋顶花园）',
     {'every_storey': True, 'outdoor_types': ['garden', 'terrace', 'inner courtyard', 'roof garden']},
     kq('K90'),
     ['IfcDoor IsExternal + containedIn 楼层', '露台 IfcSpace'],
     {'detached house': 'external：model_card', 'outdoor access': 'derived：该层存在 IsExternal 的 IfcDoor，或通向 IsExternal 空间的门'},
     'derived', '', frm=['K90'], priority=1, chapter='Housing · Building types')

rule('R81', '入户凹口尺寸', 'Space', 'should', 'IfcDoor (entrance) / IfcSpace',
     {'building.usage': 'residential', 'door.role': '户门 / 入户门', 'recess': '门前为凹入式'},
     {'w': '凹口宽', 'd': '凹口深'},
     'door.role = entrance AND recess',
     '凹口宽 ≥ 1.25 m（最好 1.50 m）、深约 1.00 m，使两人能舒适且有遮蔽地在门前等候',
     {'width_min_m': 1.25, 'width_better_m': 1.5, 'depth_m': 1.0},
     kq('K93'),
     ['IfcDoor IsExternal / 户门', '门前外墙几何'],
     {'entrance recess': 'derived：户门两侧外墙向内退的空腔尺寸'},
     'derived', '', frm=['K93'], priority=1, chapter='Housing · Access')

rule('R82', '卫生间类型的判定', 'Space', 'typical', 'IfcSpace (bathroom) / IfcSanitaryTerminal',
     {'space.function': 'sanitary room'},
     {'fixtures': '房间内的洁具集合', 'type': 'guest WC / shower room / bathroom / full bathroom'},
     'always (within context)',
     'WC + 洗手盆 = （客用）WC；淋浴 + 洗手盆 = 淋浴间；浴缸 + 洗手盆 + WC = 浴室；浴缸 + 淋浴 + 洗手盆 + WC = 完整浴室',
     {'guest_wc': ['WC', 'washbasin'], 'shower_room': ['shower', 'basin'], 'bathroom': ['bath', 'washbasin', 'WC'], 'full_bathroom': ['bath', 'shower', 'washbasin', 'WC']},
     kq('K109'),
     ['IfcSanitaryTerminal.PredefinedType / 类型名', 'contains 关系'],
     {'fixtures': 'direct：PredefinedType ∈ {BATH, SHOWER, WASHHANDBASIN, TOILETPAN}；类型名里的 WC/Dusche/Badewanne 也算（derived）'},
     'direct', '分类规则：给卫生间打类型标签，R68 的“卫生间”判定依赖它。', frm=['K109'], priority=1, chapter='Housing · Rooms')

rule('R83', '厅室的每人容积（声学）', 'Space', 'typical', 'IfcSpace (hall / auditorium)',
     {'space.function': '讲演厅、会议厅、音乐厅', 'space.occupants': '座位数'},
     {'V': '房间容积', 'V_per_person': 'V / 座位数'},
     'always (within context)',
     '讲话用厅约 4 m³/人，（音乐会）音乐 10 m³/人；容积过小则混响不足',
     {'speech_m3_per_person': 4, 'music_m3_per_person': 10},
     kq('K121'),
     ['Qto_SpaceBaseQuantities.NetVolume', '座位数（contains 座椅家具数，或 external）'],
     {'occupants': 'derived：contains 的座椅 IfcFurniture 数；否则 external'},
     'derived', '', frm=['K121'], priority=1, chapter='Acoustics')

rule('R84', '餐饮厨房员工超过 10 人须设休息室', 'Space', 'must', 'IfcSpace (restaurant kitchen)',
     {'space.function': 'restaurant / canteen kitchen', 'kitchen.staff': '员工数'},
     {'has_rest_room': '员工区内是否有休息室'},
     'kitchen.staff > 10',
     '须设休息室（劳动场所规定）',
     {'staff_threshold': 10},
     kq('K128'),
     ['IfcSpace 名称 kitchen / rest / break', '员工数（external）'],
     {'staff': 'external：model_card 或按厨房面积估', 'rest room': 'direct：名称 rest/break/Pause'},
     'external', '', frm=['K128'], priority=1, chapter='Restaurants · Kitchens')

rule('R85', '研讨室的规模与进深', 'Space', 'should', 'IfcSpace (seminar room)',
     {'building.usage': 'university / education', 'space.function': 'seminar room'},
     {'seats': '座位数', 'A_per_student': '面积 / 座位数', 'depth': '房间进深', 'h': '净高', 'ventilation': '是否只靠一面外墙自然通风'},
     'always (within context)',
     '常用规模 20、40、50、60 座，每名学生 1.90–2.00 m²；只靠一面外墙自然通风时，进深不超过净高的 2.5 倍',
     {'sizes_seats': [20, 40, 50, 60], 'area_per_student_m2': [1.9, 2.0], 'depth_max_over_clear_height': 2.5},
     kq('K129'),
     ['Qto_SpaceBaseQuantities', 'IfcWindow / 外墙 opensTo', '座椅家具数'],
     {'single-sided natural ventilation': 'derived：房间只有一面墙 IsExternal 且带可开启窗', 'seats': 'derived：contains 座椅数或 external'},
     'derived', '', frm=['K129'], priority=1, chapter='Universities')

rule('R86', '高校教研人员办公室面积', 'Space', 'typical', 'IfcSpace (office)',
     {'building.usage': 'university', 'space.function': 'office', 'space.occupant_role': '教授 / 科研助理 / 助理 / 秘书'},
     {'A': '房间面积'},
     'always (within context)',
     '教授 20–24 m²，科研助理 15 m²，助理 20 m²，秘书 15 m²（两人合用 20 m²）',
     {'professor_m2': [20, 24], 'scientific_assistant_m2': 15, 'assistant_m2': 20, 'secretary_m2': 15, 'secretary_double_m2': 20},
     kq('K130'),
     ['Qto_SpaceBaseQuantities.NetFloorArea', '房间用途（external）'],
     {'occupant role': 'external：房间名偶尔带 Prof./Sekretariat，否则由 model_card'},
     'external', '', frm=['K130'], priority=1, chapter='Universities')

rule('R87', '单间办公的走廊是疏散通道，不得放家具', 'Space', 'must', 'IfcSpace (corridor) / IfcFurniture',
     {'building.usage': 'office', 'space.role': '走廊 / 疏散通道'},
     {'furniture_in_corridor': 'contains 的家具（复印机、柜子、共用设施）', 'window_area_used': '共用设施占用的靠窗面积'},
     'always (within context)',
     '疏散通道内不允许放置家具；因此单间办公的共用设施只能放在使用房间里，占用昂贵的靠窗面积——设计时要为共用设施预留专门房间或区域',
     {'furniture_in_escape_route': 'none'},
     kq('K136') + [q('page_0251', 'Single-room offices: Single and double rooms are arranged in rows along a mostly artificially lit corridor.')],
     ['走廊 IfcSpace', 'contains 家具 bbox'],
     {'escape route': 'derived：走廊 IfcSpace（见 R64）', 'furniture in corridor': 'derived：bbox 中心落在走廊内的 IfcFurniture'},
     'derived', '', frm=['K136'], priority=2, chapter='Office buildings · Types')

rule('R88', '大空间办公的进深', 'Space', 'typical', 'IfcSpace (open-plan office)',
     {'building.usage': 'office', 'office.type': 'open-plan（R24 分类）'},
     {'depth': '房间进深（采光面到对面墙）'},
     'office.type = open-plan',
     '大空间办公的典型进深 20–30 m，适合协同工作的大群体和专注度要求低的常规工作；这种进深导致建筑设备成本高、改造适应性有限——学生模型里 20–30 m 进深的无分隔楼层应被识别为大空间办公，并随之触发全空调（R47）和 R30 的进深限制',
     {'depth_m': [20, 30], 'consequence': ['high building services cost', 'limited adaptability']},
     kq('K137') + [q('page_0245', 'are suitable for large groups of employees who are predominantly engaged in shared work and for routine activities with a low concentration threshold.')],
     ['IfcSpace 几何（进深）', '外墙 IsExternal'],
     {'open-plan': 'derived：单个 IfcSpace 面积 > 400 m² 且含 ≥ 20 工位家具', 'depth': 'derived：垂直于采光立面的尺寸'},
     'derived', '', frm=['K137'], priority=1, chapter='Office buildings · Types')

rule('R89', '屏幕工位的视线方向', 'Space', 'should', 'IfcFurniture (desk) / IfcWindow',
     {'building.usage': 'office', 'furniture.type': '屏幕工位（desk + screen）'},
     {'view_dir': '工位视线方向', 'facade_dir': '窗立面方向', 'light_band_dir': '灯带方向'},
     'always (within context)',
     '屏幕工位的视线应与窗立面及灯带平行，屏幕尽量位于两者之间',
     {'view_parallel_to': ['window façade', 'light bands'], 'screen_between': True},
     kq('K142'),
     ['IfcFurniture 放置方向（ObjectPlacement）', '外墙 / IfcWindow 方向', 'IfcLightFixture'],
     {'view direction': 'derived：桌子的局部 Y 轴（ObjectPlacement）；屏幕家具常缺', 'window façade': 'derived：房间 IsExternal 墙的方向'},
     'derived', '', frm=['K142'], priority=1, chapter='Office buildings · Workplace')

rule('R90', '收发室面积', 'Space', 'typical', 'IfcSpace (mail room)',
     {'building.usage': 'office', 'space.function': 'mail room / Poststelle', 'building.workplaces': '工位总数'},
     {'A': '收发室面积', 'A_per_workplace': 'A / 工位数'},
     'always (within context)',
     '约每工位 0.3–0.5 m²；打包台、分拣台要足够大以便高峰时快速分发',
     {'area_per_workplace_m2': [0.3, 0.5]},
     kq('K144'),
     ['IfcSpace 名称', '工位数（R16 的推导）'],
     {'workplaces': 'derived：R16 的工位计数'},
     'derived', '', frm=['K144'], priority=1, chapter='Office buildings · Ancillary')

# ───────────────────────── Element ─────────────────────────
rule('R91', '住宅门的净开启宽度', 'Element', 'typical', 'IfcDoor',
     {'building.usage': 'residential', 'door.role': '房门 / 浴室 WC 门 / 户门 / 入户大门'},
     {'w_clear': '净开启宽度（OverallWidth 减框）'},
     'always (within context)',
     '房门约 80 cm，浴室/WC 门约 70 cm，户门 ≥ 90 cm，入户大门最大 115 cm；任何门最小通行净宽 55 cm；内门净高最低 210 cm、更好 210–225 cm',
     {'room_door_cm': 80, 'bath_wc_cm': 70, 'flat_entrance_min_cm': 90, 'front_door_max_cm': 115, 'absolute_min_cm': 55, 'height_min_cm': 210},
     kq('K22') + [q('page_0125', 'Minimum clear width for walking through is 55 cm.'), q('page_0125', 'clear opening height of internal doors\nminimum\t210 cm\nbetter\t210-225 cm')],
     ['IfcDoor.OverallWidth / OverallHeight', 'opensTo（门两侧房间决定门的角色）', 'IsExternal'],
     {'door role': 'derived：opensTo 两端房间类型（bath/WC → 浴室门；室外或楼梯间 ↔ 户内 → 户门）'},
     'derived', '', frm=['K22'], priority=2, chapter='Doors')

rule('R92', '电梯到达的住户户门', 'Element', 'must', 'IfcDoor (flat entrance)',
     {'building.usage': 'residential', 'door.role': '户门', 'access.by_lift': '该户所在层由电梯到达'},
     {'w_clear': '净开启宽度', 'h': '门高'},
     'access.by_lift',
     '净开启宽度 90 cm（轮椅通行），门高宜 ≥ 2.10 m',
     {'clear_width_cm': 90, 'height_min_m': 2.10},
     kq('K25'),
     ['IfcDoor.OverallWidth / OverallHeight', 'IfcTransportElement serves 楼层'],
     {'accessed by lift': 'derived：户门所在 IfcBuildingStorey 在某电梯的 serves 集合内', 'flat entrance door': 'derived：见 R91'},
     'derived', '', frm=['K25'], priority=2, chapter='Doors')

rule('R93', '作为疏散路线的窗', 'Element', 'must', 'IfcWindow',
     {'window.role': '作为第二疏散路线的窗（房间没有第二条楼梯时）'},
     {'w_clear × h_clear': '净开口', 'sill': '窗台距楼面高度'},
     'window.role = escape route',
     '净开口 ≥ 0.9 × 1.2 m，窗台高 ≤ 1.2 m',
     {'clear_opening_m': [0.9, 1.2], 'sill_max_m': 1.2},
     kq('K40'),
     ['IfcWindow OverallWidth / OverallHeight', '窗底标高 − 楼面标高（bbox）', 'R08 两条疏散路线的判定'],
     {'escape route window': 'derived：R08 判定只有一条楼梯路线的房间里，朝外的 IfcWindow；是否被指定为疏散窗 external', 'sill height': 'derived：bbox.z_min − storey.elevation'},
     'derived', '', frm=['K40'], priority=2, chapter='Fire protection')

rule('R94', '高层建筑立面的层间防火', 'Element', 'must', 'IfcWall / IfcCurtainWall / IfcSlab',
     {'building.is_high_rise': 'true', 'facade.any': '每层外墙'},
     {'parapet_h': '窗槛墙高度（上层窗底到下层窗顶）', 'parapet_rating': '槛墙耐火等级', 'projection': '层间外挑水平构件的出挑长度'},
     'building.is_high_rise',
     '每层须有高 ≥ 1 m 的 W 90 A 防火窗槛墙，或外挑 ≥ 1.5 m 的 W 90 A 水平构件；全玻璃（含双层）幕墙须特别审批并用喷淋等措施防止火势窜层',
     {'parapet_min_m': 1.0, 'parapet_rating': 'W 90 A', 'projection_alt_m': 1.5, 'all_glass_facade': 'special approval + sprinklers'},
     kq('K46') + [q('page_0258', 'All-glass façades (also double façades) are permitted only with special approvals if particular protection measures (area sprinklers, mist extinguishing systems) can prevent the spread of fire to the next storey')],
     ['IfcWindow / IfcCurtainWall 竖向位置（bbox）', 'IfcWall.FireRating', 'IfcSlab 外挑'],
     {'parapet height': 'derived：同一立面上下两层窗 bbox 的 z 间距', 'W 90 A': 'direct：Pset_WallCommon.FireRating（常缺）'},
     'derived', '', frm=['K46'], priority=3, chapter='High-rise buildings')

rule('R95', '单层外墙：高保温材料或附加保温层', 'Element', 'should', 'IfcWall (external)',
     {'wall.IsExternal': 'true', 'wall.layers': '单层砌体（无独立保温层、无空气层）'},
     {'material': '砌体材料', 'has_insulation_layer': '是否有附加保温层（内/外）'},
     'wall.layers = single leaf',
     '单层外墙只能用高保温材料（如加气砌块）配专用保温砂浆和抹灰；否则就做单层墙加附加保温层（外保温或内保温），保温层外侧用网格增强的矿物抹灰防裂',
     {'single_leaf_material': 'aerated blocks + thermally insulating mortar/plaster', 'alternative': 'single leaf + external/internal insulation layer'},
     kq('K57'),
     ['IfcMaterialLayerSet（层数、材料名）', 'Pset_WallCommon.IsExternal'],
     {'single leaf': 'direct：IfcMaterialLayerSet 只有一层结构层（抹灰不算）', 'high insulation material': 'derived：材料名含 aerated/Porenbeton/Ytong/Leichtbeton'},
     'direct', '', frm=['K57'], priority=2, chapter='Walls · Envelope')

rule('R96', '夹心墙的外叶与空气层', 'Element', 'should', 'IfcWall (external, cavity)',
     {'wall.IsExternal': 'true', 'wall.layers': '内承重叶 + 外叶（夹心墙）'},
     {'t_outer': '外叶厚度', 't_air': '空气层宽度'},
     'wall.layers = cavity wall',
     '外叶最小 90 mm；空气层 ≥ 40 mm、≤ 150 mm；可做空气层、空气层加保温、满填保温或中间抹灰层',
     {'outer_leaf_min_mm': 90, 'air_gap_mm': [40, 150]},
     kq('K58'),
     ['IfcMaterialLayerSet 各层厚度与 IsVentilated / 材料名'],
     {'cavity wall': 'direct：IfcMaterialLayerSet 含两层砌体且中间有 air/Luft 层或保温层', 'air gap': 'direct：IfcMaterialLayer.IsVentilated 或材料名 air'},
     'direct', '', frm=['K58'], priority=2, chapter='Walls · Envelope')

rule('R97', '背通风外挂层的空气间层', 'Element', 'must', 'IfcWall / IfcCovering (ventilated cladding)',
     {'wall.IsExternal': 'true', 'wall.cladding': '背通风外挂层（板材或砖砌外叶）'},
     {'t_air': '空气间层宽度', 'skin_type': 'panel / brickwork'},
     'wall.cladding = rear-ventilated',
     '板材类外挂层后的空气间层 ≥ 20 mm，砖砌外叶 ≥ 40 mm；背通风消除较不透汽外层的隔汽效应',
     {'air_gap_panel_min_mm': 20, 'air_gap_brick_min_mm': 40},
     kq('K60'),
     ['IfcMaterialLayerSet（air 层厚度、IsVentilated）', 'IfcCovering CLADDING'],
     {'rear-ventilated skin': 'direct：IfcMaterialLayer.IsVentilated = TRUE，或外侧为 IfcCovering 且与墙之间有空隙（derived）'},
     'direct', '', frm=['K60'], priority=2, chapter='Walls · Envelope')

rule('R98', '热阻与传热系数的计算', 'Element', 'must', 'IfcWall / IfcRoof / IfcSlab (external)',
     {'element.IsExternal': 'true', 'element.layers': '材料层厚度与导热系数已知'},
     {'R_i': '每层 d/λ（d 以 m 计）', '1/U': 'R_si + Σ R_i + R_se', 'U': '其倒数'},
     'always (within context)',
     '每层热阻 R = d/λ；总热阻 1/U = R_si + R + R_se，U 为其倒数——Pset_WallCommon.ThermalTransmittance 应与按层计算的 U 一致',
     {'R': 'd / λ', 'one_over_U': 'R_si + R + R_se'},
     kq('K61'),
     ['IfcMaterialLayerSet 厚度', 'IfcMaterialProperties Pset_MaterialThermal.ThermalConductivity', 'Pset_WallCommon.ThermalTransmittance'],
     {'λ of each layer': 'direct：Pset_MaterialThermal，学生模型多缺 → 按材料名查表（external）'},
     'direct', '计量规则，用来校验 ThermalTransmittance 是否自洽。', frm=['K61'], priority=1, chapter='Building physics')

rule('R99', '种植屋面的坡度', 'Element', 'should', 'IfcRoof / IfcSlab (roof)',
     {'roof.green': '种植屋面（材料层含 substrate / vegetation / Gründach）'},
     {'pitch': '屋面坡度'},
     'roof.green',
     '坡屋面坡度不超过 25°，平屋面坡度最大 2–3%',
     {'pitched_max_deg': 25, 'flat_max_percent': [2, 3]},
     kq('K66'),
     ['IfcRoof / IfcSlab 材料层', 'Pset_RoofCommon / 几何坡度'],
     {'green roof': 'direct：材料层名含 substrate/vegetation/Gründach/green', 'pitch': 'derived：屋面几何'},
     'derived', '', frm=['K66'], priority=1, chapter='Roofs')

rule('R100', '坡屋面保温的位置与通风构造', 'Element', 'typical', 'IfcRoof (pitched)',
     {'roof.pitched': 'true', 'roof.insulated': '椽间 / 椽下有保温'},
     {'vapour_barrier_side': '隔汽层位置（室内侧）', 'ventilated': '挂瓦垫层与保温之间是否有通风层'},
     'roof.pitched',
     '保温（一般矿棉）铺在椽间和椽下，室内侧设隔汽层；通风屋面需更大椽高且只有隔汽层和通风都可靠时才有效，因此业内多采用非通风构造',
     {'insulation': 'between and below rafters', 'vapour_barrier': 'room side', 'preferred': 'unventilated'},
     kq('K67'),
     ['IfcRoof / IfcSlab 材料层顺序', 'IfcMaterialLayer.IsVentilated'],
     {'ventilated roof': 'direct：材料层含 air/Luft 且 IsVentilated', 'vapour barrier': 'direct：材料名含 vapour/Dampfsperre（与 R42 同）'},
     'direct', '', frm=['K67'], priority=1, chapter='Roofs')

rule('R101', '分户墙的面密度', 'Element', 'should', 'IfcWall (party wall)',
     {'building.usage': 'residential', 'wall.role': '分户墙（两户之间 / 两栋之间）'},
     {'m_wall': '面密度 kg/m²（Σ 厚度 × 密度）', 'Rw': 'Pset_WallCommon.AcousticRating'},
     'wall.role = party wall',
     '分户墙面密度始终 ≥ 400 kg/m²（弯曲刚度大、10–160 kg/m² 的板材是最有效的侧向传声路径，所以分户墙要重）；多层住宅分户墙的空气声隔声 R\'w 须达 53 dB',
     {'single_min_kg_m2': 400, 'airborne_Rw_dB': 53},
     kq('K68') + [q('page_0490', 'residential units, party walls | 53 | ')],
     ['IfcWall 两侧房间所属户（IfcZone）', 'IfcMaterialLayerSet 厚度 + Pset_MaterialCommon.MassDensity', 'Pset_WallCommon.AcousticRating'],
     {'party wall': 'derived：墙两侧的 IfcSpace 属于不同 IfcZone/户', 'surface mass': 'derived：Σ 层厚 × 密度，密度缺时按材料名查表（external）'},
     'derived', '', frm=['K68'], priority=2, chapter='Walls · Acoustics')

rule('R102', '模数协调与标志尺寸', 'Element', 'typical', 'IfcGrid / IfcWall',
     {'project.modular': '采用模数协调的项目'},
     {'grid_spacing': '轴网间距', 'nominal_dims': '构件标志尺寸'},
     'always (within context)',
     '基本模数 M = 100 mm，扩大模数 3M / 6M / 12M；非模数补充尺寸 25、50、75 mm 用于配件和搭接；构件标志尺寸 = 模数尺寸 ∓ 灰缝/面层（砖：模数 25 cm − 1 cm 灰缝 = 24 cm；现浇混凝土墙 25 cm）',
     {'M_mm': 100, 'multi_modules_mm': [300, 600, 1200], 'supplementary_mm': [25, 50, 75]},
     kq('K69') + [q('page_0047', 'There are also standardised non-modular supplementary dimensions l = 25 mm, 50 mm and 75 mm for fitting elements or overlapping connections → 11.')],
     ['IfcGrid 轴线间距', 'IfcWall 厚度 / 长度'],
     {'modular': 'derived：轴网间距和墙厚是否为 100 mm 的倍数'},
     'derived', '', frm=['K69'], priority=1, chapter='Basics · Dimensions')

rule('R103', '高层外窗的清洁方式', 'Element', 'must', 'IfcWindow / IfcCurtainWall',
     {'building.is_high_rise': 'true', 'window.cleanable_from_inside': 'false（固定扇、幕墙）'},
     {'cleaning': '清洁方式 / 设备（擦窗机、吊篮）'},
     'NOT window.cleanable_from_inside',
     '须由受过训练的人员使用合适设备从室外清洁——屋顶须为擦窗设备预留位置',
     {'cleaning': 'from outside, trained personnel, suitable apparatus'},
     kq('K154'),
     ['IfcWindow.OperationType（FIXEDCASEMENT 不可内开）', 'IfcCurtainWall'],
     {'cleanable from inside': 'direct：IfcWindow.PartitioningType / OperationType 含可开启扇；幕墙视为不可'},
     'direct', '', frm=['K154'], priority=1, chapter='High-rise buildings')


# ───────────────────────── verify + write ─────────────────────────
def main():
    db = sqlite3.connect(os.path.join(ROOT, 'data', 'neufert', 'embeddings.sqlite'))
    bad, n = [], 0
    for r in R:
        for b in r['basis']:
            n += 1
            rows = [c for (c,) in db.execute('select content from embeddings where page=?', (b['page'],))]
            if not any(b['quote'] in c for c in rows):
                bad.append((r['rid'], b['page'], b['quote'][:80]))
    if bad:
        for x in bad:
            print('NOT VERBATIM:', x)
        sys.exit(1)
    ids = [r['rid'] for r in R]
    assert len(ids) == len(set(ids))
    with open(OUT, 'w', encoding='utf-8') as fh:
        for r in R:
            fh.write(json.dumps(r, ensure_ascii=False) + '\n')
    print(f'{len(R)} rules, {n} quotes all verbatim → {OUT}')


if __name__ == '__main__':
    main()

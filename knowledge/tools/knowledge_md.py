"""Write hard_qa/KNOWLEDGE.md: the Neufert knowledge points behind the advanced QA.

Distinct quotes in hard_qa.jsonl are grouped by hand into knowledge points (K) below, keyed by
the start of each quote. Pages, page ids, intent ids and the questions using each point are
computed from the data. Run from the project root:
    python3 knowledge/tools/knowledge_md.py
"""
import collections, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
QA = os.path.join(HERE, '..', 'hard_qa.jsonl')
OUT = os.path.join(HERE, '..', 'KNOWLEDGE.md')

# (topic, title, summary, [quote prefixes])
K = [
    ('楼梯', '舒适步距公式', '踏步高 r 与踏面宽 t 应满足 2r + t = 59–65 cm（成人步距）。', ['In order to determine a suitable pitch']),
    ('楼梯', '最佳坡度与踏步比', '最省力的是 30° 坡度、踏步比 17/29。', ["the best use of 'climbing effort'"]),
    ('楼梯', '每段梯段步数', '必要楼梯每段 3–18 步；18 步上限是“应当”性规定。', ['Length of runs on legally essential stairs', "The 18-step rule is a 'should'"]),
    ('楼梯', '休息平台', '层高 ≥ 2.75 m 的必要楼梯必须设休息平台；平台长度 = n × 步距 + 1 个踏面。', ['Stairs with landings are required', 'landing length = ']),
    ('楼梯', '必要楼梯宽度与踏步比', '必要楼梯（法定疏散楼梯）宽 1.00 m、踏步比 17/28。', ['legally essential stairs 1.00 m', 'Stair width in public buildings is calculated']),
    ('楼梯', '两户以下住宅的楼梯', '不超过两户的住宅，楼梯可用宽度 ≥ 0.80 m、踏步比 17/28。', ['residential buildings with no more than two flats']),
    ('楼梯', '室外楼梯与办公楼梯的取向', '室外楼梯宜用低踏步（12×41 至 16×30 cm）；办公楼梯和疏散楼梯应便于快速通行。', ['For outside stairs, low steps', 'Stairs in offices or emergency stairs']),
    ('楼梯', '螺旋楼梯', '螺旋楼梯作为住宅内唯一的连接楼梯，直径 ≥ 190 cm、可用宽度 80 cm。', ['Spiral staircases are permissible from 190 cm']),
    ('护栏', '护栏高度', '高差 ≥ 1 m 必须设护栏：坠落高度 < 12 m 为 0.90 m，> 12 m 为 1.10 m，工作场所为 1.00 m。', ['Galleries, mezzanines, balconies', 'drop <12 m, h = 0.90 m', 'drop <12 m, h = 1.00 m', 'drop >12 m, h = 1.10 m']),
    ('门', '洞口尺寸 ≠ 净通行宽度', '门的结构洞口/外形尺寸和净通行宽度不同，要扣除门框等构造厚度。', ['difference between structural opening']),
    ('门', '住宅门的常规宽度', '房门约 80 cm，浴室/WC 门约 70 cm，户门 ≥ 90 cm，入户大门最宽约 115 cm。', ['room doors      approx. 80 cm', 'bath, WC        approx. 70 cm', 'entrance doors\n    to flats']),
    ('门', '内门净高', '内门净开启高度最小 2.10 m。', ['clear opening height of internal doors']),
    ('门', '紧急出口的门型', '紧急出口不得使用推拉门或旋转门；旋转门需另设紧急出口。', ['Sliding doors and revolving doors are not permissible', 'Revolving door with additional emergency exits', 'Because revolving doors can cope']),
    ('门', '电梯入户的户门', '经电梯到达的住户，户门净宽 90 cm（轮椅通行），高度 ≥ 2.10 m。', ['front doors of flats which are accessed by lifts']),
    ('无障碍', '无障碍门净宽', '无障碍门净通行宽度 ≥ 0.90 m；无障碍入口净宽 ≥ 0.90 m 且无台阶。', ['Clear passage width of doors', 'must be accessible through an entrance']),
    ('无障碍', '无障碍的适用范围与无台阶通达', '按无障碍原则设计的建筑各层须无台阶可达（电梯或坡道）；适用于办公、文教、医疗、餐饮、停车、厕所等。', ['All levels of buildings designed', 'This requirement applies notably']),
    ('无障碍', '轮椅活动空间', '每个房间应有至少 1.50 × 1.50 m 的转身空间；走廊和门厅宽 ≥ 1.50 m。', ['A depth and width of at least 1.50 m', 'Corridors and entrance halls must be at least 1.50 m']),
    ('无障碍', '无障碍卫生间', '每处卫生设施至少一个轮椅厕位；厕所、淋浴、更衣间的门须向外开。', ['At least one toilet must be provided for wheelchair', 'Doors to toilets, showers and changing rooms']),
    ('无障碍', '无障碍电梯', '电梯轿厢净宽 ≥ 1.10 m、净深 ≥ 1.40 m；门前活动区 ≥ 1.50 × 1.50 m。', ['Cars of lifts must have', 'The movement area in front of the doors']),
    ('无障碍', '轮椅停车位', '轮椅使用者的车位，车辆长边旁需留活动区。', ['min. 1.50 m deep ...\nin front of therapy facilities']),
    ('疏散', '疏散距离', '居室和地下室内任一点到必要楼梯或出口 ≤ 35 m。', ['Every location in inhabited rooms']),
    ('疏散', '两条独立疏散路线', '有居室的单元每层须有两条独立疏散路线；第二条可以是第二部必要楼梯，或消防救援设备可达的位置。', ['Residential or commercial units with at least one occupied room', 'the second escape route via']),
    ('疏散', '疏散窗', '作为疏散路线的窗，净开口 ≥ 0.9 × 1.2 m，窗台高 ≤ 1.2 m。', ['If the window serves as an escape route']),
    ('疏散', '出口宽度（按人数）', '紧急出口宽度每 150 人 1.0 m（餐饮章节）。', ['Emergency exits 1.0 m wide per 150']),
    ('疏散', '高层建筑', '最高使用楼层一侧高出地面 > 22 m 为高层；高层需两部位于不同防火分区、宽 ≥ 1.25 m 的疏散楼梯。', ['High-rise buildings are those', 'High-rise buildings up to 60 m high: at least two emergency stairs']),
    ('居室与采光', '居室最低要求', '居室最小面积 8 m²、净高 2.40 m，窗面积为房间面积的 1/8。', ['minimum requirements for floor area (8 m^2)']),
    ('居室与采光', '厨房作为居室', '厨房作为居室时净高 ≥ 2.40 m，窗面积 ≥ 净地面面积的 1/8。', ['As a habitable room, the kitchen']),
    ('居室与采光', '居住面积计算', '净高 ≥ 2 m 的部分全额计入，1–2 m 计一半；地下室、车库、办公室等不计。', ['Floor areas are included in the calculation', 'but not subsidiary rooms']),
    ('居室与采光', '工作间的窗', '工作间视线窗总宽 ≥ 墙宽的 1/10，窗台高 0.85–1.25 m；高 > 3.5 m 的工作间玻璃 ≥ 外墙面积 30%；采光窗面积为地面面积的 1/10（≤ 600 m²）。', ['The total width of all visual connections', 'Possible visual connection to the outside', 'For workrooms more than 3.5 m high', '1/10 of the floor area for rooms up to 600']),
    ('住宅·厨房', '厨房宽度与操作空间', '双排厨房最小宽 2.70 m（绝对最小 2.40 m）；两排台面间活动区 1.50 m（最小 1.20 m）。', ['this results in a minimum kitchen width', 'A movement area of 1.50 m (min. 1.20 m)']),
    ('住宅·厨房', '厨房面积与类型', '带就餐区的厨房约 10 m² 起；L 形、连通客厅和走廊的布置约 14 m²。', ['Kitchens with dining areas can be planned', 'A good arrangement is an L shape']),
    ('住宅·厨房', '开放式厨房', '开放式厨房需良好通风和排烟，以免油烟影响起居和就餐区。', ['Open kitchens require good ventilation']),
    ('住宅·厨房', '厨房位置', '厨房宜紧邻入口区（购物、倒垃圾路线短）。', ['in the immediate vicinity of the entrance area']),
    ('住宅·卧室与卫浴', '卧室最小面积', '父母房/双人卧室约 13 m²，单人卧室约 8 m²，宽敞的双人卧室 16.5 m²。', ['bedrooms with minimal space of approx. 13', 'approx. 8 m² (single room)', 'a generous twin bedroom of 16.5']),
    ('住宅·卧室与卫浴', '卫生间', '每户至少一个卫生间（含浴缸/淋浴和厕所的独立房间）；大户型宜浴厕分设或加客用 WC；卫生间通常紧邻卧室。', ['according to building regulations, belongs to the minimum', 'A bathroom is defined as', 'In larger houses, bath and WC', 'The bathroom is normally next to the bedroom']),
    ('住宅·卧室与卫浴', '没有洗衣间时', '没有洗衣间时，卫生间须预留洗衣机、烘干机和洗衣篮的位置与接口。', ['If there is no laundry room']),
    ('住宅·卧室与卫浴', '洗衣间', '洗衣间需 1.20 m 宽的工作台；最好朝东北、紧邻或便于通往厨房；独立住宅应直通花园晾晒。', ['A worktop of 1.20 m width', 'These rooms are best placed to the northeast', 'In detached houses, direct access should be provided to the garden']),
    ('住宅·户外与组织', '阳台计入居住面积', '阳台、凉廊和露台按面积的 25–50% 计入居住面积。', ['Balconies, loggias and terraces are a part']),
    ('住宅·户外与组织', '阳台面积', '3–4 人阳台约 7 m²，5–6 人约 9 m²。', ['A = 7.0 m^2 balcony', 'B = 9.0 m^2 balcony']),
    ('住宅·户外与组织', '户外空间的连接', '户外空间一般与起居、工作和就餐空间相连；有多个户外空间时也可接卧室、厨房。', ['They generally have a spatial relationship', 'with more than one open area']),
    ('住宅·户外与组织', '电梯与每层户数', '超过五个完整楼层的住宅须设电梯；一梯两户是最常见的交通组织方式。', ['Lifts are required for residential buildings', 'Two flats per floor is the most common']),
    ('住宅·户外与组织', '私宅停车', '私宅可减少停车面积；车棚比车库更经济，建筑物理上也更有利。', ['A reduction in the parking area', 'In addition to garages, roofed-over parking']),
    ('酒店', '酒店星级与客房面积', '德国酒店分级：1 星单/双人间 8/12 m²（带洗手盆），2 星 12/16 m²（70% 客房带卫生间），3 星 14/18 m²（全部带卫生间），4 星 16/22 m²，5 星 18/26 m²。', ['1 Star (Tourist)', '2 Stars (Standard)', '3 Stars (Comfort)', '4 Stars (First Class)', '5 Stars (Luxury)']),
    ('酒店', '汽车旅馆', '汽车旅馆客房 4×4 至 5×5 m、带卫生间；多为单层分散布置；停车位尽量靠近客房。', ['Room sizes 4 × 4 m', 'In contrast to city hotels, motels', 'The access road normally leads to the registration']),
    ('酒店', '餐厅', '餐厅通道净宽 ≥ 0.80 m、门 0.90 m；就餐区净高：≤ 50 m² 为 2.50 m，> 50 m² 为 2.75 m，> 100 m² ≥ 3.00 m。', ['Minimum clear width of aisles in restaurants', 'The ceiling heights of dining areas']),
    ('办公', '办公室净高', '办公室净高 2.75 m；以坐姿工作为主时可降 25 cm，但最低 2.50 m；走廊和卫生间允许 2.30 m；> 100 m² 的工作间建议 3.00 m。', ['Ceiling height 2.75 m according to Vst', 'For predominantly sedentary activities', 'Corridors and sanitary facilities are permitted', 'guideline 3.00 m for working rooms']),
    ('办公', '每工位总面积', '每个工位的总面积需求 23–45 m²，视组织和职级而定。', ['The total space requirement per workstation']),
    ('办公', '工位尺寸', '桌面 ≥ 120 × 80 cm；每个工位 ≥ 1.5 m² 的自由活动区。', ['The desktop working area should be', 'There should be a free movement area']),
    ('办公', '办公室进深、开间与模数', '工位进深 2.20 m（桌 80 + 活动 100 + 后柜 40），房间净深 4.40 m；单间办公室模数 1.50 m、组合办公 1.35 m；开间 3.80 m（约 18 m²）可放两个进深 0.90 m 的电脑工位。', ['Workstation depth 2.20 m', 'The modular dimensions', 'This is the economical module dimension', 'Room widths of 3.80 m', 'two computer workstations with a depth']),
    ('办公', '建筑进深与采光深度', '中廊式办公楼通常进深 12–13 m；自然采光大约能利用到 7.00 m 的房间进深。', ['The usual depth of buildings with central corridors', 'Daylight can mostly be exploited']),
    ('办公', '办公室类型', '单间办公室适合独立或专注工作；组团办公约 4–16 个工位；100 个以上工位的大开间依赖人工照明和通风；提倡单间与组团混合。', ['Single-room offices are suitable', 'The experience with the open-plan layout', 'Large-scale office landscapes', 'the requirement for a mixed provision']),
    ('办公', '会议区', '会议区每座约 2.5 m²（不含附属空间），储藏和备餐等附属空间约为会议面积的 1/3；会议区应从入口区直达。', ['A conference area requires about 2.5', 'store rooms and a pantry for catering', 'Conference areas should be directly accessible']),
    ('办公', '办公卫生间与茶水间配置', '每 50–80 个工位一个厕所单元，每工位约 0.6–0.8 m²；每 50–100 个工位一个约 10 m² 的茶水间，并尽量靠近工位。', ['A good ratio is one toilet unit', 'For every approx. 50–100 workplaces', 'Tea kitchens should be as near']),
    ('办公', '工作场所厕所（劳动场所规定）', '员工超过 5 人须分设男女厕所；距每个工位 ≤ 100 m 或不超过一层；厕所由带洗手盆的前室（每 5 个 WC 至少 1 个洗手盆）和独立的 WC 间组成。', ['If there are more than five employees', 'These are to be provided at a distance', 'Toilet facilities consist of a lobby', 'at least one washbasin per five WCs']),
    ('停车', '车位与通道尺寸', '车位 2.50 × 5.00 m = 12.5 m²；90° 停车通道宽 5.50 m；车库条例要求车位宽 ≥ 2.30 m，FGSV 建议公共车位 ≥ 2.50 m。', ['90° parking, access 5.50 m wide', 'Parking space size (2.50', 'The Garage (multi-storey car park) Regulations', 'The Research Company for Roads and Traffic']),
]


EXTRA_CITES = []   # (page_id, quote, chapter) cited directly by knowledge points, not through a hard-QA item


def load_extra():
    """knowledge/<group>.json: list of {topic, title, summary, prefixes} appended after the built-in K list."""
    import glob
    for path in sorted(glob.glob(os.path.join(HERE, '..', 'knowledge', 'x_*.json'))):
        for e in json.load(open(path, encoding='utf-8')):
            # knowledge-only points bring their own citations: "cites": [[page_id, verbatim quote], ...]
            for pg, q in e.get('cites', []):
                EXTRA_CITES.append((pg, q, e.get('chapter', '')))
            K.append((e['topic'], e['title'], e['summary'], e.get('prefixes') or [q for _, q in e['cites']]))
            if 'priority' in e and e['title'] not in TIER:
                TIER[e['title']] = (e.get('lod', '200–300'), int(e['priority']), e.get('decision', ''))
    # knowledge/_extra_cites.json: [[page_id, verbatim quote, chapter], ...] — citations for built-in points whose
    # hard-QA items were removed (e.g. with the 4351 / duplex models); they add no new point.
    xp = os.path.join(HERE, '..', 'knowledge', '_extra_cites.json')
    if os.path.exists(xp):
        for pg, q, ch in json.load(open(xp, encoding='utf-8')):
            EXTRA_CITES.append((pg, q, ch))


# Canonical topic taxonomy: order of sections, and how raw topic labels / titles map onto it.
TOPICS = ['场地与体量', '楼梯、坡道、电梯与护栏', '门', '无障碍', '疏散与防火', '采光、日照、通风与窗', '围护结构与保温', '墙体与构造',
          '居室标准与面积计算', '住宅·户型组织与入户', '住宅·厨房与就餐', '住宅·卧室、卫浴与储藏',
          '办公', '高层建筑', '酒店与餐饮']
# Topics dropped from the knowledge list (their quotes stay in hard_qa.jsonl).
EXCLUDED_TOPICS = {'酒店与餐饮'}
# Coarse-to-fine levels after the BOT zone hierarchy (bot:Site/Building > bot:Storey > bot:Zone > bot:Space > bot:Element),
# assigned per knowledge point in knowledge/_levels.json together with the IFC entities the point is about and the
# extra IFC data needed to check it (relations, property sets, layers, ...).
LV = json.load(open(os.path.join(HERE, '..', 'knowledge', '_levels.json'), encoding='utf-8'))
LEVELS = [l['id'] for l in LV['levels']]
NEEDS = LV['needs']
TOPIC_OF_LABEL = {
    '楼梯': '楼梯、坡道、电梯与护栏', '楼梯·坡道·电梯': '楼梯、坡道、电梯与护栏', '护栏': '楼梯、坡道、电梯与护栏',
    '门': '门', '无障碍': '无障碍', '疏散': '疏散与防火', '疏散与防火': '疏散与防火',
    '采光与日照': '采光、日照、通风与窗', '窗': '采光、日照、通风与窗', '通风': '采光、日照、通风与窗', '建筑物理': '办公', '围护结构与保温': '围护结构与保温', '墙体与构造': '墙体与构造',
    '居室与采光': '居室标准与面积计算', '居室标准与面积计算': '居室标准与面积计算', '场地与体量': '场地与体量',
    '住宅·户型组织与入户': '住宅·户型组织与入户', '疏散与防火': '疏散与防火', '采光、日照、通风与窗': '采光、日照、通风与窗',
    '楼梯、坡道、电梯与护栏': '楼梯、坡道、电梯与护栏', '酒店与餐饮': '酒店与餐饮', '住宅·户型组织': '住宅·户型组织与入户', '住宅·入户与走道': '住宅·户型组织与入户',
    '住宅·户外与组织': '住宅·户型组织与入户', '住宅·厨房': '住宅·厨房与就餐', '住宅·卧室与卫浴': '住宅·卧室、卫浴与储藏',
    '住宅·卫浴': '住宅·卧室、卫浴与储藏', '住宅·储藏与家具': '住宅·卧室、卫浴与储藏',
    '办公': '办公', '高层建筑': '高层建筑', '酒店': '酒店与餐饮', '酒店与餐饮': '酒店与餐饮', '停车': '场地与体量', '结构与模数': '结构与模数',
}
TOPIC_OF_TITLE = {
    '工作间的窗': '采光、日照、通风与窗', '阳台计入居住面积': '居室标准与面积计算',
    '就餐区的朝向与连接': '住宅·厨房与就餐', '餐桌尺寸与就餐人数': '住宅·厨房与就餐', '储藏与食品间靠近厨房': '住宅·厨房与就餐',
    '分户墙隔声': '墙体与构造', '模数协调与标志尺寸': '墙体与构造', '设备噪声与安静房间': '住宅·户型组织与入户', '厅室的每人容积': '办公', '车位与通道尺寸': '场地与体量', '私宅停车': '场地与体量', '高层建筑': '场地与体量', '体形系数 A/Ve': '场地与体量',
}

# Early-design relevance, keyed by title: (minimum LOD needed to check it, priority 3/2/1, decision it drives)
# 3 = core for LOD 200-300 early design; 2 = important; 1 = secondary / detail / beyond LOD 300.
TIER = {
    '舒适步距公式': ('300', 3, '交通核'), '最佳坡度与踏步比': ('300', 2, ''), '每段梯段步数': ('200–300', 3, '交通核'),
    '休息平台': ('200–300', 3, '交通核'), '必要楼梯宽度与踏步比': ('200–300', 3, '交通核'), '两户以下住宅的楼梯': ('300', 3, '交通核'),
    '室外楼梯与办公楼梯的取向': ('300', 1, ''), '螺旋楼梯': ('300', 2, ''), '护栏高度': ('300', 3, '安全'),
    '无障碍坡道': ('200–300', 3, '无障碍'), '公共建筑楼梯两侧扶手': ('350', 1, ''), '电梯候梯区': ('200', 2, ''),
    '非必要楼梯': ('300', 1, ''), '洞口尺寸 ≠ 净通行宽度': ('300', 2, ''), '住宅门的常规宽度': ('300', 2, ''),
    '内门净高': ('300', 2, ''), '紧急出口的门型': ('300', 2, ''), '电梯入户的户门': ('300', 2, ''),
    '无障碍门净宽': ('300', 3, '无障碍'), '无障碍的适用范围与无台阶通达': ('200', 3, '无障碍'), '轮椅活动空间': ('200', 3, '无障碍'),
    '无障碍卫生间': ('200–300', 2, ''), '无障碍电梯': ('200', 3, '无障碍'), '轮椅停车位': ('200', 1, ''),
    '楼梯起止处活动区': ('200', 2, ''), '长走廊轮椅会车位': ('200', 2, ''), '多户住宅的无障碍楼层': ('200', 2, ''),
    '无障碍住宅卫浴': ('350', 2, ''), '轮椅住宅的起居室': ('200', 2, ''),
    '疏散距离': ('200', 3, '疏散'), '两条独立疏散路线': ('200', 3, '疏散'), '疏散窗': ('300', 2, ''),
    '出口宽度（按人数）': ('200', 2, ''), '高层建筑': ('100–200', 3, '体量'), '防火分区与防火墙': ('200', 3, '疏散'),
    '主楼梯须设在连续封闭的楼梯间': ('200', 3, '疏散'), '疏散走廊侧墙 F 30': ('300', 2, ''),
    '工作间的窗': ('200–300', 3, '立面与采光'), '厨房朝向': ('200', 1, ''), '无窗厨房': ('200', 2, ''),
    '玻璃面最小高度 1.3 m': ('300', 1, ''), '视野：窗宽不小于房间宽 65%': ('300', 1, ''), '工作区距窗不超过 2 倍窗净高': ('200–300', 2, ''),
    '办公与工作建筑的朝向': ('100', 2, ''), '按朝向选择遮阳': ('200', 2, ''), '遮阳挑檐的出挑计算': ('300', 1, ''),
    '体形系数 A/Ve': ('100–200', 3, '体量'), '厅室的每人容积': ('200', 1, ''), '设备噪声与安静房间': ('200', 2, ''),
    '单层外墙与附加保温层': ('300', 3, '构造选型'), '夹心墙（双叶墙）的外叶与空气层': ('300', 2, ''), '混凝土外墙必须附加保温': ('300', 3, '构造选型'),
    '背通风外挂层的空气间层': ('350', 1, ''), '热阻与传热系数计算': ('300', 3, '构造选型'), '热桥与构件连接': ('350', 2, ''),
    '平屋面排水坡度': ('300', 2, ''), '平屋面构造：暖屋面与倒置屋面': ('300', 2, ''), '隔汽层设在暖侧': ('350', 1, ''),
    '种植屋面的坡度': ('300', 1, ''), '坡屋面保温位置与通风构造': ('300–350', 2, ''),
    '分户墙隔声': ('300', 3, '构造选型'), '模数协调与标志尺寸': ('200–300', 2, ''), '建筑等级与承重墙耐火': ('200', 3, '构造选型'),
    '地下室墙体与楼板耐火': ('300', 2, ''), '住宅/商业单元之间的分隔墙': ('300', 3, '构造选型'), '外墙及外墙饰面的燃烧性能': ('300', 2, ''),
    '居室最低要求': ('200', 3, '房间尺寸'), '厨房作为居室': ('200', 3, '房间尺寸'), '居住面积计算': ('200', 3, '面积核算'),
    '阳台计入居住面积': ('200', 2, ''), '阳台面积': ('200', 2, ''), '户外空间的连接': ('200', 2, ''),
    '电梯与每层户数': ('100–200', 3, '体量'), '分组式平面与房间独立可达': ('200', 3, '户型布局'), '卧室朝向与位置': ('200', 2, ''),
    '门厅直达厨房、WC 和楼梯': ('200', 2, ''), '防风门斗': ('200', 1, ''), '户内走道宽度': ('200', 2, ''), '独立住宅每层通往户外': ('200', 1, ''),
    '厨房宽度与操作空间': ('200', 3, '房间尺寸'), '厨房面积与类型': ('200', 2, ''), '开放式厨房': ('200', 1, ''), '厨房位置': ('200', 1, ''),
    '就餐区的朝向与连接': ('200', 2, ''), '餐桌尺寸与就餐人数': ('350', 1, ''), '储藏与食品间靠近厨房': ('200', 1, ''),
    '卧室最小面积': ('200', 3, '房间尺寸'), '卫生间': ('200', 3, '户型布局'), '没有洗衣间时': ('200', 2, ''), '洗衣间': ('200', 1, ''),
    '衣柜的位置与通风': ('200', 1, ''), '户内储藏空间': ('200', 2, ''), '卫生间朝向、采光与通风': ('200', 2, ''), '卫生间类型': ('300', 1, ''),
    '卫浴与厨房共用管井': ('200', 2, ''), '婴儿车与自行车公共储藏间': ('200', 2, ''),
    '办公室净高': ('200', 3, '体量'), '每工位总面积': ('100–200', 3, '面积核算'), '工位尺寸': ('350', 1, ''),
    '办公室进深、开间与模数': ('200', 3, '平面进深'), '建筑进深与采光深度': ('100–200', 3, '平面进深'), '办公室类型': ('200', 2, ''),
    '会议区': ('200', 2, ''), '办公卫生间与茶水间配置': ('200', 2, ''), '工作场所厕所（劳动场所规定）': ('200', 2, ''),
    '保洁间与物业用房': ('200', 1, ''), '档案室': ('200', 1, ''), '办公楼入口区': ('200', 1, ''), '员工餐厅位置': ('200', 1, ''),
    '组团办公室到窗距离': ('200', 2, ''), '小型使用单元内的走廊': ('200', 2, ''),
    '酒店星级与客房面积': ('200', 3, '房间尺寸'), '汽车旅馆': ('200', 1, ''), '餐厅': ('200', 2, ''), '酒店基本功能区': ('100–200', 2, ''),
    '餐厅与厨房、卫生间的组织': ('200', 1, ''), '私宅停车': ('100', 1, ''), '车位与通道尺寸': ('100–200', 2, ''),
}
STARS = {3: '★★★', 2: '★★', 1: '★'}


def normalise():
    out = []
    for i, (topic, title, summary, pres) in enumerate(K):
        t = TOPIC_OF_TITLE.get(title) or TOPIC_OF_LABEL.get(topic)
        if t not in TOPICS: sys.exit(f'no canonical topic for {topic} / {title}')
        out.append((TOPICS.index(t), i, (t, title, summary, pres)))
    K[:] = [k for _, _, k in sorted(out)]


def apply_overrides():
    """knowledge/_overrides.json: {original title: {"title": ..., "summary": ...}} from the source check."""
    path = os.path.join(HERE, '..', 'knowledge', '_overrides.json')
    if not os.path.exists(path):
        return
    ov = json.load(open(path, encoding='utf-8'))
    for i, (topic, title, summary, pres) in enumerate(K):
        o = ov.get(title)
        if not o:
            continue
        new_title = o.get('title') or title
        if new_title != title and title in TIER:
            TIER[new_title] = TIER[title]
        K[i] = (topic, new_title, o.get('summary') or summary, pres)
    unknown = set(ov) - {t for _, t, _, _ in K} - {k for k, o in ov.items() if o.get('title')}
    if unknown: sys.exit('overrides for unknown titles: ' + ', '.join(sorted(unknown)))


def probe_basis(p, pb, quotes):
    """The point's own quotes the probe cites, then quotes of other points the probe names by their start
    (a probe may need a sentence that belongs to a neighbouring point, e.g. a category table row)."""
    own = [q for q in p['quotes'] if any(q.startswith(b[:60]) or b in q for b in pb['basis'])]
    other = [q for q in quotes if q not in p['quotes'] and any(q.startswith(b[:60]) for b in pb['basis'] if len(b) >= 15)]
    return own + other


def main():
    load_extra()
    normalise()
    apply_overrides()
    rows = [json.loads(l) for l in open(QA, encoding='utf-8')]
    quotes = {}  # quote -> dict
    for r in rows:
        for b in r['basis']:
            q = b['quote'].strip()
            e = quotes.setdefault(q, dict(book_page=b['book_page'], page=b['page'] if 'page' in b else None, chapter=b['chapter'], intents=set(), hids=set()))
            if b.get('intent_id'): e['intents'].add(b['intent_id'])
            e['hids'].add(r['hid'])
    if EXTRA_CITES:   # same strict rule as build_hard_qa.cite(): verbatim substring of the page text in embeddings.sqlite
        import sqlite3
        con = sqlite3.connect(os.path.join(HERE, '..', '..', 'data', 'neufert', 'embeddings.sqlite'))
        for pg, q, ch in EXTRA_CITES:
            if not any(q in c for (c,) in con.execute('select content from embeddings where page=?', (pg,))):
                sys.exit(f'QUOTE NOT EXACT on {pg}: {q!r}')
            quotes.setdefault(q, dict(book_page=str(int(pg[5:]) - 12), page=pg, chapter=ch, intents=set(), hids=set()))
    assigned = {}
    for i, (_, _, _, prefixes) in enumerate(K):
        for pre in prefixes:
            hits = [q for q in quotes if q.startswith(pre)]
            if not hits: sys.exit(f'K{i + 1:02d}: no quote starts with {pre!r}')
            for q in hits:
                if q in assigned and assigned[q] != i: sys.exit(f'quote assigned twice: {q[:60]}')
                assigned[q] = i
    missing = [q for q in quotes if q not in assigned]
    if missing: sys.exit('unassigned quotes:\n' + '\n'.join(q[:100] for q in missing))

    proj_short = {'fantasy_residential_building_1': 'frb1', 'fantasy_office_building_1': 'office1', 'fantasy_office_building_2': 'office2',
                  'fantasy_office_building_3': 'office3', 'fantasy_hotel_1': 'hotel1', 'samuel_macalister_sample_house': 'samuel'}
    def short(h):
        p, n = h[2:].rsplit('-', 1)
        return f'{proj_short.get(p, p)}-{n}'

    points = []
    for i, (topic, title, summary, _) in enumerate(K):
        qs = [q for q, k in assigned.items() if k == i]
        hids = set().union(*(quotes[q]['hids'] for q in qs))
        pages = sorted({int(quotes[q]['book_page']) for q in qs})
        points.append(dict(kid=f'K{i + 1:02d}', topic=topic, title=title, summary=summary, quotes=sorted(qs, key=lambda q: int(quotes[q]['book_page'])),
                           pages=pages, chapters=sorted({quotes[q]['chapter'] for q in qs}), intents=sorted(set().union(*(quotes[q]['intents'] for q in qs))),
                           hids=sorted(hids)))
    points = [p for p in points if p['topic'] not in EXCLUDED_TOPICS]
    topic_rank = {t: i for i, t in enumerate(TOPICS)}
    for p in points:
        e = LV['points'].get(p['kid'])
        if not e or e['title'] != p['title']: sys.exit(f"knowledge/_levels.json: no entry for {p['kid']} {p['title']} (or its title changed)")
        p.update(level=e['level'], ifc=e['ifc'], needs=e['needs'])
        known = [NEEDS[n]['models'] for n in p['needs'] if NEEDS[n]['models'] is not None]
        p['models'] = sorted(set.intersection(*map(set, known))) if known else None   # None = no entity-level restriction
    points.sort(key=lambda p: (LEVELS.index(p['level']), topic_rank.get(p['topic'], 99), int(p['kid'][1:])))   # ids stay as assigned
    # scope review (knowledge/_scope.json, labelled on the website): only points labelled "in" stay; "unsure" and "out" are archived
    sp = os.path.join(HERE, '..', 'knowledge', '_scope.json')
    scope = json.load(open(sp, encoding='utf-8')) if os.path.exists(sp) else {}
    for p in points:
        e = scope.get(p['kid'], {})
        p['scope'] = e.get('label', '') if e.get('title') == p['title'] else ''
    archived = [p for p in points if p['scope'] in ('unsure', 'out')]
    points = [p for p in points if p['scope'] not in ('unsure', 'out')]
    proj_of = {r['hid']: r['project'] for r in rows}
    import glob as _glob
    probes = {}
    for f in sorted(_glob.glob(os.path.join(HERE, '..', 'probes', 'probes_*.json'))):
        for pr_ in json.load(open(f, encoding='utf-8')):
            probes[pr_['title']] = pr_
    no_probe = [p['title'] for p in points if p['title'] not in probes]
    if probes and no_probe: print('WARNING: no probe for', no_probe)

    L = []
    L.append('# Neufert 知识点清单（进阶题）\n')
    L.append(f'由 `tools/knowledge_md.py` 从 `hard_qa.jsonl` 生成。{len(rows)} 道进阶题共引用 {len(quotes)} 条不同的 Neufert 原文，'
             f'其中 **{len(points)} 个知识点**收入本清单（另有 {len(archived)} 个经范围核对后归档，列在文末），分属 {len(LEVELS)} 个层级、{len(dict.fromkeys(p["topic"] for p in points))} 个主题。\n')
    L.append('- **页码**是书页码（`data/neufert/dataset` 所解析的 Neufert 英文版正文页码）；括号里的 `page_XXXX` 是 `data/neufert/dataset/pages.jsonl` 里的页面 id（= 书页码 + 12）。')
    L.append('- **intent** 是 `runs/intent_pilot_residential/intents.jsonl` 里对应的条目；只有住宅章节有。')
    L.append('- **用到的题**里，题号是进阶题 id 的缩写（如 `fzk_house-04` = `H-fzk_house-04`）。')
    L.append('- 每条原文都已和 `embeddings.sqlite` 中的 Neufert 文本逐字（含空白）核对一致；含换行、制表符或连续空格的原文以代码块原样展示。\n')

    L.append('- **层级**按 BOT 的空间层次从粗到细：Site & Building → Storey → Zone → Space → Element，并标出对应的 IFC 实体。知识点编号是固定 id，不随排序变化。')
    if EXCLUDED_TOPICS: L.append(f"- 已移出清单的主题：{'、'.join(sorted(EXCLUDED_TOPICS))}（相关进阶题仍保留在 `hard_qa.jsonl`）。")
    L.append('')
    L.append('## 层级\n')
    L.append('| 层级 | 含义 | BOT | IFC 实体 | 知识点数 |')
    L.append('|---|---|---|---|---|')
    for l in LV['levels']:
        L.append(f"| {l['id']} | {l['desc']} | `{l['bot']}` | {l['ifc']} | {sum(p['level'] == l['id'] for p in points)} |")
    L.append('')
    L.append('层级按知识点逐个归类，所以同一个主题可能出现在几个层级下。Storey 层除了层数、层高、净高，还收了连接各层的楼梯、坡道、电梯和护栏；'
             '这些在 IFC 里是构件（`IfcStair` 等），不是 `IfcBuildingStorey` 的属性。\n')
    L.append('### 检查时需要的 IFC 数据\n')
    L.append('除了实体本身的尺寸，很多知识点还要用到实体之间的关系或实体上的属性。下表是每类数据在 IFC 里的表达，以及 9 个模型里哪些有。\n')
    L.append('| 需要 | IFC 表达 | 知识点数 | 有这类数据的模型 | 说明 |')
    L.append('|---|---|---|---|---|')
    for k, n in NEEDS.items():
        cnt = sum(k in p['needs'] for p in points)
        ms = '未逐个核对' if n['models'] is None else (f"{len(n['models'])}/9" + ('：' + '、'.join(n['models']) if 0 < len(n['models']) < 9 else ''))
        L.append(f"| {n['label']} | `{n['ifc']}` | {cnt} | {ms} | {n['note']} |")
    L.append('')
    nz = [p for p in points if p['models'] is not None and not p['models']]
    L.append(f"按上表，有 **{len(nz)} 个知识点**所需的数据在 9 个模型里都没有（主要是房间分组和电梯/坡道）：{'、'.join(p['kid'] for p in nz)}。\n")
    L.append('## 总览\n')
    missing_tier = [p['title'] for p in points if p['title'] not in TIER]
    if missing_tier: sys.exit('no TIER entry for: ' + ', '.join(missing_tier))
    L.append('| 知识点 | 层级 | 主题 | 内容 | IFC 实体 | 需要 | LOD | 优先级 | 页码 | 题数 |')
    L.append('|---|---|---|---|---|---|---|---|---|---|')
    for p in points:
        lod, pr, _ = TIER[p['title']]
        L.append(f"| {p['kid']} | {p['level']} | {p['topic']} | {p['title']} | {', '.join(p['ifc'])} | {'、'.join(NEEDS[n]['label'] for n in p['needs']) or '—'} | {lod} | {STARS[pr]} | {', '.join('p.' + str(x) for x in p['pages'])} | {len(p['hids'])} |")
    L.append('')

    core = [p for p in points if TIER[p['title']][1] == 3]
    L.append(f'## 早期设计（LOD 200–300）核心知识点：{len(core)} 个\n')
    L.append('★★★ = 直接左右早期设计决策（体量、交通核、房间尺寸、构造选型）或是法规硬门槛，且在 LOD 200–300 的模型上可检查。'
             '★★ = 重要但影响面较小或与核心点重叠。★ = 细部、建议性或超出 LOD 300。\n')
    order = ['体量', '平面进深', '面积核算', '交通核', '疏散', '无障碍', '安全', '户型布局', '房间尺寸', '立面与采光', '构造选型']
    L.append('| 决策 | 核心知识点 |')
    L.append('|---|---|')
    for d in order:
        ks = [p for p in core if TIER[p['title']][2] == d]
        if ks: L.append(f"| {d} | {'；'.join(p['kid'] + ' ' + p['title'] for p in ks)} |")
    stats = collections.Counter(TIER[p['title']][1] for p in points)
    L.append(f"\n优先级分布：★★★ {stats[3]} · ★★ {stats[2]} · ★ {stats[1]}；"
             f"★★★ 知识点共被 {len(set().union(*(set(p['hids']) for p in core)))} 道题使用。\n")

    by_topic = collections.Counter()
    for p in points: by_topic[p['topic']] += len(p['hids'])
    L.append('### 按主题\n')
    L.append('| 主题 | 知识点数 | 涉及题数（按知识点累计） |')
    L.append('|---|---|---|')
    for t in dict.fromkeys(p['topic'] for p in points):
        L.append(f"| {t} | {sum(p['topic'] == t for p in points)} | {by_topic[t]} |")
    L.append('')

    L.append('### 按页码\n')
    page_k = collections.defaultdict(list)
    page_ch = {}
    for p in points:
        for q in p['quotes']:
            bp = int(quotes[q]['book_page'])
            if p['kid'] not in page_k[bp]: page_k[bp].append(p['kid'])
            page_ch[bp] = quotes[q]['chapter']
    L.append('| 页码 | 章节 | 知识点 |')
    L.append('|---|---|---|')
    for bp in sorted(page_k):
        L.append(f"| p.{bp} (page_{bp + 12:04d}) | {page_ch[bp]} | {', '.join(page_k[bp])} |")
    L.append('')

    cur = cur_lv = None
    for p in points:
        if p['level'] != cur_lv:
            cur_lv = p['level']; cur = None; L.append(f"# {cur_lv}\n"); L.append(f"{next(l['desc'] for l in LV['levels'] if l['id'] == cur_lv)}\n")
        if p['topic'] != cur:
            cur = p['topic']; L.append(f'## {cur}\n')
        L.append(f"### {p['kid']} {p['title']}\n")
        lod, pr, dec = TIER[p['title']]
        L.append(f"{p['summary']}\n")
        L.append(f"- **早期设计**：{STARS[pr]} · LOD {lod}" + (f" · 决定{dec}" if dec else ''))
        L.append(f"- **IFC**：{'、'.join('`' + x + '`' for x in p['ifc'])}"
                 + (f" · 还需要：{'；'.join(NEEDS[n]['label'] + '（`' + NEEDS[n]['ifc'] + '`）' for n in p['needs'])}" if p['needs'] else ''))
        L.append(f"- **页码**：{', '.join(f'p.{x} (page_{x + 12:04d})' for x in p['pages'])} · {' / '.join(p['chapters'])}")
        if p['intents']: L.append(f"- **intent**：{', '.join('`' + x + '`' for x in p['intents'])}")
        projs = collections.Counter(proj_of[h] for h in p['hids'])
        L.append(f"- **用到的题**（{len(p['hids'])} 道，{len(projs)} 个模型）：{', '.join('`' + short(h) + '`' for h in p['hids'])}")
        pb = probes.get(p['title'])
        if pb:
            L.append(f"- **知识探针题**（{ {'must': '须', 'should': '宜', 'typical': '一般'}.get(pb['modality'], pb['modality'])} · {pb['difficulty']}）：{pb['question']}")
            L.append(f"  - 标准答案：{pb['answer']}")
            L.append('  - 选项：' + '；'.join(('**' + chr(65 + i) + '. ' + o + '** ✓') if i == pb['mcq']['correct'] else (chr(65 + i) + '. ' + o) for i, o in enumerate(pb['mcq']['options'])))
        L.append('- **原文**：')
        for q in p['quotes']:
            if '\n' in q or '\t' in q or '  ' in q:
                # keep the source layout exactly: code block preserves line breaks, tabs and runs of spaces
                L.append(f"  - p.{quotes[q]['book_page']}（原文含换行/制表符，按原样）：")
                L.append('')
                L.append('    ```text')
                L.extend('    ' + line for line in q.split('\n'))
                L.append('    ```')
            else:
                L.append(f"  - p.{quotes[q]['book_page']}：“{q}”")
        L.append('')

    if archived:
        SC = {'unsure': '待定', 'out': '不在范围'}
        L.append(f'# 已归档：{len(archived)} 个\n')
        L.append('范围核对时标为“待定”或“不在范围”的知识点。它们不进入上面的清单和 `knowledge_probes.jsonl`，探针题保存在 `knowledge_probes_archived.jsonl`。'
                 '要恢复某一条，把 `knowledge/_scope.json` 里它的 label 改成 `in` 再重新生成。\n')
        L.append('| 知识点 | 标注 | 层级 | 主题 | 内容 | 优先级 | 页码 |')
        L.append('|---|---|---|---|---|---|---|')
        for p in archived:
            L.append(f"| {p['kid']} | {SC[p['scope']]} | {p['level']} | {p['topic']} | {p['title']} | {STARS[TIER[p['title']][1]]} | {', '.join('p.' + str(x) for x in p['pages'])} |")
        L.append('')
    open(OUT, 'w', encoding='utf-8').write('\n'.join(L))
    if probes:
      for fname, plist in (('knowledge_probes.jsonl', points), ('knowledge_probes_archived.jsonl', archived)):
        with open(os.path.join(HERE, '..', fname), 'w', encoding='utf-8') as f:
            for p in plist:
                pb = probes.get(p['title'])
                if not pb: continue
                lod, pr, dec = TIER[p['title']]
                f.write(json.dumps(dict(kid=p['kid'], scope=p['scope'], level=p['level'], ifc=p['ifc'], needs=p['needs'], models=p['models'], topic=p['topic'], title=p['title'], summary=p['summary'], lod=lod, priority=pr,
                                        question=pb['question'], answer=pb['answer'], accept=pb.get('accept', []), mcq=pb['mcq'],
                                        rubric=pb['rubric'], modality=pb['modality'], difficulty=pb['difficulty'],
                                        basis=[dict(book_page=quotes[q]['book_page'], page=quotes[q]['page'], quote=q) for q in probe_basis(p, pb, quotes)],
                                        hard_qa=p['hids']), ensure_ascii=False) + '\n')
    print(f'{len(archived)} archived;', end=' ')
    print(f'{len(points)} knowledge points from {len(quotes)} quotes -> {OUT}')


if __name__ == '__main__':
    main()

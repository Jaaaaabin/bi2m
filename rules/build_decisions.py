"""Design-decision topics = the unit of the ground truth ("did the author apply this knowledge?").

Tiered by how tricky the decision is for a novice BIM author at early design:
  core        early-design elements / contexts that anyone can model but that carry a lot of rules a novice does not
              know (stairs, escape routes, daylight depth, lifts, toilets, corridors, clear height, workplace density …)
  secondary   detailing or weak-signal topics (railings, door modules, wall / roof build-up, acoustics)
  convention  measurement conventions, not design decisions
Each topic groups rules as evidence and states: why it is tricky, the signals that show the knowledge was applied,
and the software defaults that merely look like it. Coverage counts come from runs/scan370/matches.jsonl.

.venv/bin/python rules/build_decisions.py
"""
import json, os, collections
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..')

D = []
def topic(did, tier, title, title_en, question, question_en, why, why_en, rules, signals, defaults, note=''):
    D.append(dict(did=did, tier=tier, title=title, title_en=title_en, question=question, question_en=question_en, why_tricky=why, why_tricky_en=why_en,
                  rules=rules, signals=signals, defaults=defaults, note=note))

# ───────────────────────── core: tricky early-design decisions ─────────────────────────
topic('T01', 'core', '楼梯几何', 'Stair geometry',
      '踢面 / 踏面、每段几级、要不要平台、梯段多宽——按用途不同全都不一样。',
      'Riser / tread, risers per flight, landings, flight width: all depend on the building type.',
      '新手会画出一部能走的楼梯，但踢面是层高除出来的（19.37 cm），踏面随手 25，一段 20 级不设平台；书里的 2r+t = 59–65、每段 ≤ 18 级、必要楼梯 r ≤ 19 / t ≥ 26 / w ≥ 1.00、住宅 17/28、非必要 21/21，一条都不知道。',
      'A novice gets a walkable stair, but the riser is storey height ÷ n (19.37 cm), the tread is 25 by habit, 20 risers without a landing; 2r+t = 59–65, ≤ 18 risers per flight, r ≤ 19 / t ≥ 26 / w ≥ 1.00 for essential stairs, 17/28 for dwellings are all unknown to them.',
      ['R03', 'R04', 'R05', 'R25', 'R26', 'R54', 'R55', 'R56'],
      ['r/t = 17/28、17/29 或 18/27 整，全楼一致', '2r + t 在 59–65 内', '梯段宽 1.00 / 1.25 m 整', '每段 ≤ 18 级并有平台'],
      ['Revit 按层高自动均分踢面（19.37 等奇数值），踏面默认 250–280', 'ArchiCAD 默认 17 × 29——命中书值但可能是默认'],
      '370 个里 347 个有数据；2r+t 超限 192 个、踢面 > 19 cm 213 个——最常被忽略的知识。')

topic('T02', 'core', '疏散路线与楼梯布置', 'Escape routes & stair placement',
      '每层几部楼梯、放在哪、楼梯间要不要封闭、最远的房间离楼梯多远、长走廊要不要分段。',
      'How many stairs per storey, where, enclosed or not, maximum travel distance, subdividing long corridors.',
      '新手把楼梯放在大厅中间一部了事；书里要求每个使用单元两条独立路线、办公 ≤ 35 m / 高层 25 m、楼梯间间距约 30 / 60 m、主楼梯须在封闭楼梯间内、走廊 > 30 m 要用防烟门分段、疏散通道内不许放家具。',
      'A novice drops one open stair in the hall; the book wants two independent routes per use unit, ≤ 35 m travel (25 m high-rise), stairs about 30 / 60 m apart, main stairs in enclosed stairwells, corridors over 30 m subdivided, no furniture in escape routes.',
      ['R22', 'R23', 'R24', 'R61', 'R64', 'R65', 'R87', 'R93'],
      ['楼梯间是独立 IfcSpace，有门与大厅隔开', '楼梯分布在平面两端，间距 30–60 m', '≥ 2 部楼梯且任一房间 ≤ 35 m'],
      ['防烟门 / 自闭属性几乎没人填（SelfClosing、SmokeStop 全缺）——判不了分段'],
      '两条路线 354 个 pass，但封闭楼梯间只有 106 个 pass、254 个 fail：楼梯“有”但“不对”。')

topic('T03', 'core', '进深与采光', 'Building depth & daylight',
      '房间能做多深、楼能做多厚还靠自然采光；窗要开多宽；大开间放在哪。',
      'How deep a room and a building can be and still be daylit; window width; where open-plan zones go.',
      '新手把平面做成 50 m 见方、中间放工位；书里说自然采光约 7 m 进深、中廊式整体 12–13 m、窗宽 ≥ 65% 房间宽、组团工位距窗 ≤ 7.5 m、≥ 100 工位的大开间才可以全靠人工照明。',
      'A novice draws a 50 m square plate with desks in the middle; the book gives ~7 m daylight depth, 12–13 m for corridor-type buildings, window width ≥ 65 % of room width, ≤ 7.5 m to a window for group rooms.',
      ['R10', 'R17', 'R38', 'R39', 'R88', 'R89', 'R103'],
      ['房间进深 ≤ 7 m 且一致', '建筑进深 12.5 / 13.4 m（对应 1.50 / 1.35 模数）', '窗宽比 ≥ 0.65', '没有无窗的工作间'],
      ['Revit 默认窗 1.2 × 1.2 / 0.9 × 1.2，一间一扇——窗宽比 0.3–0.5 多半是默认窗的结果'],
      '0204 的核心大开间无窗、外圈窗宽比 0.47，是典型的“没用知识”；全数据集窗宽比 fail 119 / 207。')

topic('T04', 'core', '平面类型与网格模数', 'Layout type & grid module',
      '单排、双排、还是大开间；轴网取多少；隔墙能不能接到窗上；柱子落在哪。',
      'Single-row, double-row or open plan; the grid module; whether partitions meet the mullions; where columns fall.',
      '新手先画 6 × 6 或 7.5 m 柱网再往里塞房间；书里是先定装修模数 1.50（单间）或 1.35（组合）、立面网格必须等于装修网格、再由模数反推进深 12.5 / 13.4，结构网格可以错开。',
      'A novice starts with a 6 × 6 or 7.5 m column grid and fills rooms in; the book starts from the fit-out module 1.50 (cellular) or 1.35 (combi), makes the façade grid equal to it, derives the depth, and lets the structural grid be offset.',
      ['R14', 'R15', 'R16', 'R47', 'R51', 'R70', 'R102'],
      ['轴网是 1.35 / 1.50 的整倍数', '房间开间 = n × 模数（2.70、4.05、3.00、4.50）', '隔墙落在窗间墙或竖梃上', '双排布置（走廊两侧都有采光房间）'],
      ['5 / 6 / 7.5 / 8.1 m 柱网是教学习惯，与书无关', '墙厚 24 / 36.5 是德国砖模数的肌肉记忆，不等于查了书'],
      '模数一致性 R102 pass 212 / fail 157；平面类型 R15 还没机械化判定。')

topic('T05', 'core', '电梯与无台阶到达', 'Lifts & step-free access',
      '几层以上必须有电梯、公共建筑是否要无台阶到达每层、电梯放哪、轿厢多大。',
      'When a lift is mandatory, step-free access to every storey in public buildings, where lifts go, car size.',
      '新手要么不放电梯，要么放一个方块；书里：住宅 > 5 个完整楼层必须有电梯，公众可达建筑所有楼层须无台阶可达，轿厢 ≥ 1.10 × 1.40，门前 1.50 × 1.50 不得与通道重叠，电梯组与主楼梯间组合布置。',
      'A novice either omits lifts or drops a box; the book: lifts mandatory above 5 full storeys in housing, step-free access to all storeys in public buildings, car ≥ 1.10 × 1.40, a 1.50 × 1.50 area in front, lifts grouped with the main stair.',
      ['R27', 'R28', 'R58', 'R60', 'R62'],
      ['IfcTransportElement 或名为 lift 的竖向房间贯通各层', '电梯紧贴楼梯间', '轿厢 1.10 × 1.40 / 1.10 × 2.10'],
      ['电梯常是 Proxy 或只有门（0204：17 扇电梯门，楼上没有井道）'],
      '255 个多层公共建筑里 201 个没有任何电梯——数据集里最大面积的空白。')

topic('T06', 'core', '层高与净高', 'Storey & clear height',
      '层高定多少才能在扣掉楼板、吊顶、架空地板后还剩够净高。',
      'Which storey height leaves enough clear height after slab, ceiling void and raised floor.',
      '新手层高 3.0 m、板 0.2 m 就以为够了；书里办公净高 ≥ 2.75（坐姿房间 2.50、走廊卫生间 2.30），住宅居室 2.40，而且要预留架空地板和吊顶，所以层高常要 3.4–3.75。',
      'A novice takes 3.0 m storeys with a 0.2 m slab; the book asks ≥ 2.75 clear in offices (2.50 seated rooms, 2.30 corridors), 2.40 in dwellings, plus room for raised floors and ceilings, so storeys of 3.4–3.75.',
      ['R02'],
      ['IfcSpace 高度 = 2.75 / 2.50 / 2.30 / 2.40 整', '层高 − 板厚 − 吊顶 恰好 ≥ 2.75'],
      ['Revit 房间高度默认 = 层高或 2.4384 (8 ft)', 'ArchiCAD 默认层高 3.00'],
      '2.75 的精确值在 0204 和 fantasy_office_building_1 都出现，信号最清楚；220 个有房间的模型里 188 pass。')

topic('T07', 'core', '卫生间与后勤配置', 'Sanitary & ancillary provision',
      '每层几个厕所、按多少人配、男女怎么分、前室隔间怎么组织；茶水间、保洁间、餐厅放哪。',
      'Toilets per storey by headcount, gender split, anteroom + cubicles; tea kitchens, cleaner\'s rooms, canteen.',
      '新手每层画一个 WC；书里按人数定：> 5 人分设男女、每工位到厕所 ≤ 100 m 或一层、前室 + 隔间、每 5 个 WC 一个洗手盆、每 50–100 工位一间茶水间、每层保洁间、餐厅在门禁外靠入口。',
      'A novice draws one WC per floor; the book sizes by headcount: separate M/F above 5 staff, ≤ 100 m or one storey to a toilet, anteroom + cubicles, 1 basin per 5 WCs, a tea kitchen per 50–100 workstations, a cleaner\'s room per storey, the canteen outside access control.',
      ['R11', 'R32', 'R33', 'R34', 'R35', 'R82', 'R84', 'R90'],
      ['厕所成对（男/女）布置在核心筒旁', '厕所数与工位数成比例', '茶水间数 ≈ 工位 / 50–100', '餐厅在入口层'],
      ['洁具几乎无人建模（IfcSanitaryTerminal ≈ 0），只能按房间名数'],
      '依赖房间命名；R11 在 167 个办公模型上 122 pass，R33 茶水间 38 fail / 63。')

topic('T08', 'core', '走廊、门与无障碍尺寸', 'Corridors, doors & accessibility',
      '走廊多宽、门多宽多高、轮椅转身和会车位、坡道坡度——公共建筑一律按无障碍算。',
      'Corridor width, door width and height, turning and passing places, ramp slope: public buildings count as accessible.',
      '新手走廊 1.2 m、门 0.8 m；书里公众可达建筑走廊 ≥ 1.50、> 15 m 设 1.80 × 1.80 会车位、门净宽 ≥ 0.90、内门净高 ≥ 2.10、每个房间 1.50 × 1.50 转身位、坡道 ≤ 6%。',
      'A novice uses 1.2 m corridors and 0.8 m doors; the book: ≥ 1.50 corridors in public buildings, 1.80 × 1.80 passing places beyond 15 m, ≥ 0.90 clear door width, ≥ 2.10 door height, a 1.50 × 1.50 turning space per room, ramps ≤ 6 %.',
      ['R07', 'R29', 'R57', 'R63', 'R71', 'R72', 'R73', 'R74', 'R75'],
      ['走廊 1.50 / 1.80 m 整', '所有内门 ≥ 0.90（含卫生间）', '坡道 6% 且 ≤ 6 m 一段'],
      ['Revit 默认门 900 × 2100 ——看着 pass 其实是默认', '走廊宽度常由轴网决定（1.2 / 1.5 / 2.0）'],
      '门 R07 fail 147 / 369，多半是卫生间门 0.6–0.8；走廊宽度 R71 pass 195 / 256。')

topic('T09', 'core', '工位密度与办公室类型', 'Workplace density & office type',
      '一个工位给多少面积、单间 / 组团 / 大开间怎么分、会议室每座多大。',
      'Area per workstation, cellular / group / open-plan mix, area per conference seat.',
      '新手按桌子能塞几张算；书里直接工位 11–15 m²、整栋楼每工位 23–45 m²、组团 4–16 工位、会议 2.5 m²/座、桌面 ≥ 1.20 × 0.80。',
      'A novice fits as many desks as the room takes; the book gives 11–15 m² per workstation, 23–45 m² gross per workstation, group rooms of 4–16, 2.5 m² per conference seat, desks ≥ 1.20 × 0.80.',
      ['R09', 'R12', 'R18', 'R36', 'R37', 'R40', 'R41', 'R83', 'R85', 'R86'],
      ['单人间 ≈ 12–13 m²、双人间 ≈ 18–20 m²（模数间）', '会议 2.5 m²/座', '组团 ≤ 16 工位'],
      ['Revit 默认桌 1830 × 915 (6 × 3 ft)；"Chair - Desk" 族名会被误数'],
      '需要家具；R09 在 130 个模型上 pass 24 / fail 68（多数过密或过松）。')

topic('T10', 'core', '住宅户型基本配置', 'Dwelling layout essentials',
      '每户必须有什么房间、居室最小多大多高、阳台多大、门厅要通哪里、户门多宽。',
      'What every flat must contain, habitable-room minimums, balcony size, hall adjacencies, flat entrance door.',
      '新手画几个卧室一个客厅就算一户；书里每户必有厨房 + 储藏 + 独立卫生间，居室 ≥ 8 m² / 净高 2.40 / 窗 1/8，储藏 ≥ 1 m² 或 2%，门厅直达厨房、WC、楼梯，户门 ≥ 0.90，户内走道 1.00。',
      'A novice draws bedrooms and a living room; the book requires kitchen + storage + a separate bathroom per flat, habitable rooms ≥ 8 m² / 2.40 clear / window 1/8, storage ≥ 1 m² or 2 %, hall giving onto kitchen, WC and stair, flat door ≥ 0.90, internal corridors 1.00.',
      ['R59', 'R67', 'R68', 'R69', 'R76', 'R77', 'R78', 'R79', 'R80', 'R81', 'R91', 'R92'],
      ['每户都有 storage / Abstellraum', '居室 ≥ 8 m²、2.40', '阳台 7 / 9 m²', '户内走道 1.00 整'],
      ['住宅模型多无 IfcZone，户的边界要从户门推'],
      '97 个住宅模型里 R68（厨房+储藏+卫生间）只有 24 个 pass，几乎都是缺储藏间。')

topic('T11', 'core', '高层门槛与防火分区', 'High-rise threshold & fire compartments',
      '最高楼层一过 22 m 规则全变；楼长超过 40 m 要不要防火墙；承重构件要什么耐火等级。',
      'Above 22 m every rule changes; buildings over 40 m need a fire wall; fire resistance of load-bearing elements.',
      '新手不知道 22 m 是一道门槛（两部 1.25 m 楼梯、消防电梯、25 m 疏散距离、层间防火槛墙），也不知道 40 m 要分防火分区；这两条在早期体量阶段就决定了方案能不能成立。',
      'A novice does not know 22 m is a threshold (two 1.25 m stairs, fire lift, 25 m travel, spandrels) nor that 40 m length needs compartments; both are decided at the massing stage.',
      ['R01', 'R19', 'R20', 'R21', 'R30', 'R31', 'R52', 'R53', 'R94'],
      ['最高楼层标高刻意停在 21.x m', '有贯通到屋面、把平面切成 ≤ 40 m 段的墙', 'FireRating 填了值'],
      ['FireRating 在 365 / 370 个模型里为空；地块、用途 IFC 里没有'],
      '门槛型知识：数据集里只有 1 个高层，防火等级几乎不可见——GT 大多为 unknown，但作为“知不知道门槛”的题目很有价值。')

# ───────────────────────── secondary: detailing or weak signal ─────────────────────────
topic('S01', 'secondary', '栏杆与护栏', 'Railings & guards', '栏杆多高（按坠落高度分档）。', 'Railing height by drop height.',
      '细节层面；几乎总是软件默认值。', 'Detailing; almost always a software default.',
      ['R06'], ['0.90 / 1.00 / 1.10 整'], ['Revit 1.2192 (4 ft)、ArchiCAD 0.90'], '')
topic('S02', 'secondary', '门洞模数与出口门型', 'Door modules & exit door types', '门洞是不是标准模数；紧急出口不用旋转门。', 'Modular door openings; no revolving doors at exits.',
      '施工层面的讲究，早期设计不会考虑。', 'Construction-level detail, not an early-design concern.',
      ['R42', 'R43'], ['洞口 875 / 1000 / 1125', '旋转门旁有平开门'], ['族名里的 900 × 2100'], '')
topic('S03', 'secondary', '外墙构造与玻璃', 'External wall build-up & glazing', '单层 / 夹心 / 混凝土加保温；U 值；外窗玻璃。', 'Single-leaf / cavity / concrete + insulation; U-value; glazing.',
      '材料层只有 1/3 的模型有；属于深化设计。', 'Only a third of the models carry material layers; detailed design.',
      ['R08', 'R44', 'R95', 'R96', 'R97', 'R98'], ['独立保温层 12–20 cm', '36.5 单层保温砖'], ['Generic 200 mm 墙无材料层'], '')
topic('S04', 'secondary', '屋面构造', 'Roof build-up', '排水坡度、隔汽层、坡屋面保温、种植。', 'Drainage slope, vapour barrier, pitched-roof insulation, green roof.',
      '构造层面；PitchAngle 多为空。', 'Construction level; PitchAngle mostly empty.',
      ['R45', 'R99', 'R100'], ['2% / 5% 坡度'], ['Revit 屋面 0°'], '')
topic('S05', 'secondary', '隔墙与隔声', 'Partitions & acoustics', '隔墙到板还是到吊顶；分户墙面密度。', 'Partitions to slab or ceiling; party-wall mass.',
      '信号弱，IFC 无隔声数据。', 'Weak signal, no acoustic data in IFC.',
      ['R46', 'R101'], ['隔墙高 = 层高'], ['墙高默认 = 层高'], '')

# ───────────────────────── conventions ─────────────────────────
topic('C01', 'convention', '面积、体积与退距的计量口径', 'Measurement conventions',
      '容积率、DIN 277、建筑体积、居住面积、退距按什么口径算——不是设计决策。',
      'How FAR, DIN 277 areas, volume, living area and setbacks are measured: not a design decision.',
      '给其他主题提供“量”的定义。', 'Provides the quantities other topics use.',
      ['R13', 'R48', 'R49', 'R50', 'R66'], [], ['IFC 无地块；无 Qto 时面积为包围盒近似'], '')


def main():
    rules = {}
    for fn in ('rules_pilot.jsonl', 'rules_office.jsonl', 'rules_general.jsonl'):
        for l in open(os.path.join(HERE, fn), encoding='utf-8'):
            r = json.loads(l); rules[r['rid']] = r
    assigned = collections.Counter(r for t in D for r in t['rules'])
    missing = sorted(set(rules) - set(assigned), key=lambda r: int(r[1:]))
    dup = [r for r, c in assigned.items() if c > 1]
    assert not missing and not dup, (missing, dup)
    sp = os.path.join(HERE, 'scan370_summary.json')
    stats = {s['rid']: s for s in json.load(open(sp, encoding='utf-8'))['rules']} if os.path.exists(sp) else {}
    mp = os.path.join(ROOT, 'runs', 'scan370', 'matches.jsonl')
    rows = [json.loads(l) for l in open(mp, encoding='utf-8')] if os.path.exists(mp) else []
    for t in D:
        c = collections.Counter()
        for m in rows:
            xs = [m['rules'].get(r, {}) for r in t['rules']]
            if any(x.get('context') for x in xs): c['context'] += 1
            if any(x.get('context') and x.get('condition') for x in xs): c['fires'] += 1
            vs = [x.get('verdict') for x in xs if x.get('verdict')]
            if any(v == 'pass' for v in vs): c['any_pass'] += 1
            if any(v == 'fail' for v in vs): c['any_fail'] += 1
            if vs and all(v in ('unknown', 'mixed') for v in vs): c['only_unknown'] += 1
        t['coverage'] = dict(n_models=len(rows), **c)
        t['rule_titles'] = {r: rules[r]['title'] for r in t['rules']}
        t['rule_stats'] = {r: {k: stats[r][k] for k in ('fires', 'pass', 'fail', 'unknown')} for r in t['rules'] if r in stats}
        t['levels'] = sorted({rules[r]['level'] for r in t['rules']})
    out = os.path.join(HERE, 'decisions.json')
    json.dump(dict(n_rules=len(rules), n_topics=len(D), tiers={'core': '核心：早期设计里讲究多的决策', 'secondary': '次要：细节或信号弱', 'convention': '计量口径'}, topics=D),
              open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'{len(D)} topics covering {sum(len(t["rules"]) for t in D)} rules → {out}')
    for t in D:
        print(f"  {t['did']} {t['tier']:10} {t['title']:14} rules={len(t['rules']):2} ctx={t['coverage'].get('context',0):3} fires={t['coverage'].get('fires',0):3} pass={t['coverage'].get('any_pass',0):3} fail={t['coverage'].get('any_fail',0):3}")


if __name__ == '__main__':
    main()

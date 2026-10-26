"""Concrete IF for every active rule.

The generated rules carried an IF like "always (within context)" with the preconditions hidden in context.match. Here each
active rule gets an explicit, ordered list of the conditions the book's knowledge actually requires before the THEN
applies: the building situation, the target element, its relation to neighbouring elements, and the trigger threshold.
Every item names the element or parameter it is read from, so the IF can be matched on the graph.

Writes rules/if_concrete.jsonl: {rid, if: [..zh..], if_en: [..], then: short restatement}. The site shows this list in
place of the old one-line condition (the old text stays available as "原 IF").

.venv/bin/python rules/build_if.py
"""
import json, os
HERE = os.path.dirname(os.path.abspath(__file__))

OUT = []
def IF(rid, zh, en, then=''):
    OUT.append(dict(rid=rid, **{'if': zh, 'if_en': en}, then=then))

# ───────────── Storey / stairs ─────────────
IF('R02', ['建筑用途 = 办公（model card 或房间名）', '目标 = 一个 IfcSpace，功能是办公室或会议室（有人长时间坐着工作）', '它所在层与上一层都有 IfcBuildingStorey.Elevation（能算层高）', '上方楼板（IfcSlab）厚度已知，吊顶 / 架空地板若有也计入'],
    ['building use = office', 'target = an IfcSpace used as office or meeting room (people work seated for long periods)', 'its storey and the storey above both have an Elevation (storey height computable)', 'the slab above has a thickness; ceiling / raised floor counted if present'],
    '净高 ≥ 2.75 m（走廊、卫生间可 2.30）')

IF('R03', ['目标 = 一段 IfcStairFlight', '它属于一部连接两个 IfcBuildingStorey 的 IfcStair（升高 = 两层标高差）', 'Pset_StairFlightCommon 里有 RiserHeight 和 TreadLength（或能从几何量出）', '楼梯是室内楼梯（Pset_StairCommon.IsExternal = false）'],
    ['target = an IfcStairFlight', 'it belongs to an IfcStair connecting two storeys (rise = elevation difference)', 'RiserHeight and TreadLength are in the Pset or measurable', 'the stair is internal (IsExternal = false)'],
    '2r + t 在 59–65 cm 内')

IF('R04', ['目标 = 一部 IfcStair', '它连接的两个 IfcBuildingStorey 标高差 ≥ 2.75 m', '它是法定必要楼梯（连接各层并通向出口，不是户内附加楼梯）', '每段 IfcStairFlight 的 NumberOfRiser 已知'],
    ['target = an IfcStair', 'the two storeys it connects differ by ≥ 2.75 m', 'it is a legally essential stair (connects storeys and leads to an exit, not an additional stair inside a flat)', 'NumberOfRiser of each flight is known'],
    '须设休息平台；每段 3–18 级；平台宽 ≥ 梯段宽')

IF('R05', ['目标 = 一段 IfcStairFlight 的宽度', '所属 IfcStair 是法定必要楼梯（连接各层并通向出口）', '建筑类型已知（高层住宅 → 1.25 m）', '梯段宽度可从几何或 Qto 量出'],
    ['target = width of an IfcStairFlight', 'the stair is legally essential', 'building type known (high-rise housing → 1.25 m)', 'flight width measurable'],
    'w ≥ 1.00 m，17/28')

IF('R06', ['目标 = 一根 IfcRailing', '它保护的坠落高度已知：所在层标高 − 下方最近楼面标高 ≥ 1 m', '是否工作场所已知（办公等 → 1.00 m 档）'],
    ['target = an IfcRailing', 'the drop it guards is known: its storey elevation minus the nearest floor below ≥ 1 m', 'whether it is a workplace is known (office etc. → the 1.00 m band)'],
    'drop < 12 m → 0.90；> 12 m → 1.10；工作场所 → 1.00')

IF('R22', ['目标 = 一个 IfcBuildingStorey（地上，有人使用）', '该层的使用单元不在地面层（标高 > 地坪）', '该层有 IfcSpace（有人使用）', '连接该层与出口的 IfcStair 及其所在的楼梯间 IfcSpace 可识别'],
    ['target = an above-ground, occupied IfcBuildingStorey', 'the use unit is not at ground level', 'the storey has occupied IfcSpaces', 'the stairs linking it to the exit and their stairwell spaces are identifiable'],
    '≥ 2 条互不经过同一空间的疏散路线（第二条可为消防救援位置）')

IF('R23', ['建筑用途已知（办公 → 35 m；高层 → 25 m；学校、商店、车库、医院 → 30 m）', '目标 = 一个有人使用的 IfcSpace', '它的 IfcDoor 通向走廊 / 大厅（opensTo），走廊通向楼梯间', '楼梯间（含 IfcStair 的 IfcSpace）在同一层可定位'],
    ['building use known (office → 35 m; high-rise → 25 m; school, shop, garage, hospital → 30 m)', 'target = an occupied IfcSpace', 'its IfcDoor opens to a corridor / hall which opens to a stairwell', 'the stairwell on the same storey is locatable'],
    '房间任一点到楼梯间的步行距离 ≤ 35 / 30 / 25 m')

IF('R24', ['目标 = 一部主楼梯（必要楼梯）IfcStair', '建筑多于一层（有上层使用单元）', '能判断楼梯是否被一个 IfcSpace（楼梯间）包围、该空间是否有门与大厅 / 走廊隔开', '楼梯间出口 IfcDoor 的宽度已知'],
    ['target = a main (essential) IfcStair', 'the building has more than one storey', 'it can be determined whether a stairwell IfcSpace encloses the stair and has doors to the hall / corridor', 'the exit door width is known'],
    '须在连续封闭的楼梯间内；出口宽度与梯段宽对应')

IF('R25', ['建筑用途 ≠ 住宅', '目标 = 一段 IfcStairFlight，所属楼梯是必要楼梯', 'RiserHeight、TreadLength、宽度已知'],
    ['building use ≠ residential', 'target = an IfcStairFlight of an essential stair', 'riser, tread and width known'],
    'r ≤ 19 cm，t ≥ 26 cm，w ≥ 100 cm（附加楼梯 50 cm、21/21）')

IF('R26', ['建筑用途 = 办公，或该楼梯是疏散楼梯', '目标 = 一部 IfcStair 的踏步比取向', '若是气派楼梯：所连两层标高差 ≤ 4 m 才可免平台', '若建筑按无障碍设计：踏步不得有突缘（NosingLength = 0）'],
    ['building use = office, or the stair is an escape stair', 'target = the riser/tread choice of an IfcStair', 'for a grand stair: storey height ≤ 4 m to omit the landing', 'in an accessible building: no nosings (NosingLength = 0)'],
    '按快速通行选踏步比；气派楼梯 ≤ 4 m 免平台；无障碍无突缘')

IF('R27', ['建筑是公众可达类型（办公、学校、医院、商业、文化…）', '建筑有 ≥ 2 个地上 IfcBuildingStorey', '入口层标高与 IfcSite.RefElevation 的差已知（有无台阶）', '是否存在 IfcTransportElement（电梯）或 IfcRamp 及其服务的楼层已知'],
    ['the building is publicly accessible', 'it has ≥ 2 above-ground storeys', 'the difference between entrance level and site elevation is known (steps or not)', 'presence of lifts / ramps and the storeys they serve is known'],
    '所有楼层须无台阶可达（电梯或坡道）；入口无台阶')

IF('R56', ['目标 = 一部 IfcStair', '同层已有另一部必要楼梯通向出口', '该楼梯只在一户 / 一个房间内部（containedIn 的 IfcSpace 不是公共交通空间）', '→ 它才算"非法定必要"楼梯'],
    ['target = an IfcStair', 'another essential stair on the same storey already leads to the exit', 'this stair stays inside one flat / room (its containing IfcSpace is not public circulation)', '→ only then it counts as non-essential'],
    '可窄到 0.50 m、21/21；否则按必要楼梯 1.00、17/28')

IF('R57', ['建筑按无障碍要求设计（公众可达）', '目标 = 一段 IfcStairFlight 的起步处和到达处', '梯段端点前方的 IfcSpace 净尺寸可量（扣除 IfcWall、IfcFurniture）', '首级踏步的踏面不计入'],
    ['the building is designed accessible (public)', 'target = the start and end of an IfcStairFlight', 'the clear space in front of the flight end is measurable (minus walls and furniture)', 'the first tread is excluded'],
    '前方活动区 ≥ 1.50 m 宽')

IF('R58', ['建筑用途 = 住宅', '完整楼层数（地上、含居住房间的 IfcBuildingStorey）> 5', '是否存在 IfcTransportElement / 名为 lift 的竖向房间已知'],
    ['building use = residential', 'number of full storeys (above ground, with habitable rooms) > 5', 'presence of a lift (IfcTransportElement or lift space) known'],
    '必须设电梯')

IF('R55', ['目标 = 一部 IfcStair，PredefinedType = SPIRAL_STAIR 或平面为圆 / 方螺旋', '它在住宅内', '同一住宅内没有其他连接同两层的 IfcStair（它是唯一连接楼梯）'],
    ['target = an IfcStair that is spiral (PredefinedType or plan)', 'it is inside a house', 'no other stair in the house connects the same two storeys (it is the sole connecting stair)'],
    '外径 ≥ 190 cm，可用宽度 80 cm')

# ───────────── Site & Building / layout ─────────────
IF('R01', ['目标 = IfcBuilding', '最高一个有人停留的 IfcBuildingStorey（含 IfcSpace）标高已知', '室外地坪标高已知（IfcSite.RefElevation 或入口层）', '两者之差 > 22 m'],
    ['target = IfcBuilding', 'elevation of the highest occupied storey (with IfcSpaces) known', 'ground level known (IfcSite.RefElevation or entrance storey)', 'difference > 22 m'],
    '属高层：≤ 60 m 时两部 ≥ 1.25 m 疏散楼梯分设两个防火分区')

IF('R13', ['目标 = 每面 IfcWall IsExternal = true', '墙高 H 可量：室外地坪到墙顶 / 墙与屋面交线（坡度 ≤ 70° 的屋面计 1/3）', '用地性质已知（一般 / 商业工业）', '地块边界几何已知（IfcSite，通常缺）'],
    ['target = every external IfcWall', 'wall height H measurable (ground to top / roof intersection; roofs ≤ 70° count one third)', 'zoning known (general / commercial-industrial)', 'plot boundary geometry known (IfcSite, usually missing)'],
    'd ≥ 0.4 × H 且 ≥ 3 m（商业区 0.2 × H）')

IF('R14', ['建筑用途 = 办公', '目标 = 一个办公室 IfcSpace', 'TrueNorth 已知，房间的窗（IfcWindow opensTo）所在外墙法线朝北', '平面是否走廊式可判（有无走廊 IfcSpace 连接房间）'],
    ['building use = office', 'target = an office IfcSpace', 'TrueNorth known and the wall carrying the room\'s window faces north', 'whether the plan is corridor-type is decidable'],
    '北向办公室只在无走廊平面中可接受')

IF('R15', ['建筑用途 = 办公', '目标 = IfcBuilding 的平面类型', '每层的交通空间（走廊 / 大厅 IfcSpace）和两侧房间可识别', '是否高层已知（三排只对高层合适）'],
    ['building use = office', 'target = the building\'s layout type', 'circulation spaces and the rooms on either side identifiable per storey', 'high-rise status known'],
    '双排为标准；单排仅房间很深时；三排仅高层')

IF('R16', ['建筑用途 = 办公', '目标 = 隔墙 IfcWall 的落点与装修网格模数', '立面网格已知：IfcCurtainWall 竖梃间距或 IfcWindow 窗间墙间距', '办公类型已知（单间 → 1.50，组合 → 1.35）'],
    ['building use = office', 'target = partition positions and the fit-out module', 'façade grid known: mullion spacing or window pier spacing', 'office type known (cellular → 1.50, combi → 1.35)'],
    '装修网格 = 立面网格；隔墙接到竖梃 / 窗间墙；模数 1.50 或 1.35')

IF('R17', ['建筑用途 = 办公', '平面是中廊式：存在走廊 IfcSpace，两侧都有房间', '目标 = 建筑进深（两侧外墙间距）', '模数已知（1.35 / 1.50）'],
    ['building use = office', 'the plan is corridor-type: a corridor IfcSpace with rooms on both sides', 'target = building depth (between the two external walls)', 'module known'],
    '进深 12–13 m：1.35 m → 13.40，1.50 m → 12.50')

IF('R18', ['建筑用途 = 办公', '工位数 n_ws ≥ 1（IfcFurniture 桌子）', '各 IfcSpace 的面积已知并能按用途分类（卫生、会议、档案、储藏、茶水、入口、设备、交通）', '结构面积（IfcWall / IfcColumn 平面面积）可算'],
    ['building use = office', 'n_ws ≥ 1 (desks)', 'room areas known and classifiable by use', 'structural area computable'],
    '每工位 23–45 m² 总面积，各项在表中区间内')

IF('R19', ['目标 = IfcBuilding', '建筑长度 L（外墙外轮廓）> 40 m，或任一外墙到地块边界 < 2.50 m', '墙的 FireRating（Pset_WallCommon）可读'],
    ['target = IfcBuilding', 'building length L > 40 m, or any external wall within 2.50 m of the boundary', 'wall FireRating readable'],
    '设 F 90 A 防火墙分成 ≤ 40 m 分区，从基础到屋面以上 ≥ 30 cm')

IF('R20', ['目标 = IfcWall LoadBearing = true、IfcColumn、IfcSlab', '建筑等级已知（1–5，由高度与用途定）', '构件所在 IfcBuildingStorey 是否地下室已知', 'FireRating 可读'],
    ['target = load-bearing walls, columns, slabs', 'building class known (1–5)', 'whether the element\'s storey is a cellar known', 'FireRating readable'],
    '等级 5 防火、4 高度阻燃、1–2 阻燃；地下室防火；楼板防火或阻燃')

IF('R21', ['目标 = IfcWall IsExternal、外墙饰面 IfcCovering、屋面 IfcRoof', '材料层（IfcMaterialLayer）可读，能判燃烧性能', '建筑等级已知（1–3 放宽）'],
    ['target = external walls, claddings, roof', 'material layers readable', 'building class known (1–3 relaxed)'],
    '外墙不燃（至少阻燃）；饰面难燃；屋面硬屋面')

IF('R30', ['目标 = 一条走廊 IfcSpace', '它所属的使用单元（IfcZone 或整层）面积 ≥ 400 m²', '走廊侧墙 IfcWall 及其 FireRating 可读', '侧墙上的内窗 IfcWindow 下沿高度可量'],
    ['target = a corridor IfcSpace', 'its use unit (IfcZone or storey) ≥ 400 m²', 'side walls and their FireRating readable', 'sill height of internal windows in those walls measurable'],
    '侧墙 F 30；侧墙采光开口下沿 ≥ 1.80 m')

IF('R31', ['目标 = 一面 IfcWall', '墙两侧的 IfcSpace 属于不同的使用单元（IfcZone）', '本层承重构件的耐火时间已知', '墙是否到达上方 IfcSlab / IfcRoof 可判；墙上 IfcDoor 的自闭 / 耐火属性可读'],
    ['target = an IfcWall', 'the spaces on its two sides belong to different use units', 'fire resistance of the storey\'s structure known', 'whether the wall reaches the slab / roof decidable; door properties readable'],
    '耐火 = 本层承重构件；到结构板；开口最少且自闭阻燃')

IF('R47', ['建筑用途 = 办公', '目标 = 一块楼板 IfcSlab', '支承间距已知（IfcColumn / 承重墙间距或 IfcGrid 轴距）', '板型可判（实心 / 肋形 / 预应力）'],
    ['building use = office', 'target = an IfcSlab', 'support spacing known (columns / bearing walls / grid)', 'slab type decidable'],
    '实心 2.5–5.5 m，肋形 5–7.5 m，预应力到 25 m；荷载 5 kN/m²')

IF('R48', ['目标 = IfcBuilding 的容积率 / 建筑密度分子', '各完整楼层外轮廓面积可算', '阳台、凉廊、露台 IfcSpace 可识别并剔除', '车库、停车位、地下设施面积可识别', '地块面积已知（IfcSite，通常缺）'],
    ['target = FAR / coverage numerators', 'external area of each full storey computable', 'balconies, loggias, terraces identifiable and excluded', 'garages, parking, underground facilities identifiable', 'plot area known (usually missing)'],
    '按口径计量后与允许值比')

IF('R49', ['目标 = 每个 IfcSpace', '房间用途可从名称 / Pset 判断', '围合构件（IfcWall、IfcColumn）平面面积可算', '楼梯、电梯、管井、设备间可识别'],
    ['target = every IfcSpace', 'room use decidable from name / Pset', 'structural area computable', 'stairs, lifts, shafts, plant rooms identifiable'],
    '归入 NF / TF / VF；可出租面积不含楼梯电梯管井')

IF('R50', ['目标 = IfcBuilding 的体积', '≥ 2 个 IfcBuildingStorey 有标高（层高 = 面层顶到面层顶）', '各层楼面面积可算；房间净面积与净高可算'],
    ['target = building volume', '≥ 2 storeys with elevations', 'floor areas and room net area × clear height computable'],
    'BRI = Σ 楼面面积 × 层高；NRI = Σ 净面积 × 净高')

IF('R51', ['建筑用途 = 住宅', '建筑形式 = 联排（只有两个相对立面能开窗，两侧为分户墙）', '目标 = 建筑进深与面宽'],
    ['building use = residential', 'form = terrace house (only two opposite façades can have windows, party walls on the sides)', 'target = depth and width'],
    '进深 ≤ 12 m，面宽 4–8 m，中部放楼梯 / 辅助房间')

IF('R70', ['建筑用途 = 办公', '外圈有很小的单人办公室 IfcSpace（沿外墙，≈ 8–12 m²）', '中部有较深的、不靠外墙的联系区 IfcSpace', '单间与联系区之间的 IfcWall 材料为玻璃'],
    ['building use = office', 'very small single offices along the façade', 'a deep central connection zone not on the façade', 'glass partitions between them'],
    '= 组合式办公：共用设施放在联系区')

IF('R102', ['目标 = IfcWall 厚度与 IfcGrid 轴距', '材料层总厚度或几何厚度可读', '轴线坐标可读'],
    ['target = wall thicknesses and grid spacings', 'thickness readable', 'axis coordinates readable'],
    '砖墙 24 / 36.5（模数 − 灰缝）；轴距为 100 / 300 / 600 / 1200 的倍数')

# ───────────── Space ─────────────
IF('R09', ['建筑用途 = 办公', '目标 = 一间办公室 IfcSpace', '房间里有 ≥ 1 张桌子（IfcFurniture desk，contains）', '房间净面积已知'],
    ['building use = office', 'target = an office IfcSpace', 'it contains ≥ 1 desk', 'net area known'],
    '直接工位 11–15 m²/工位（均 13）')

IF('R10', ['建筑用途 = 办公', '目标 = 一个工作房间 IfcSpace，它有采光面（IfcWindow opensTo 或贴外墙 / 幕墙）', '从采光面到对面墙的进深可量'],
    ['building use = office', 'target = a workroom with a daylight face (window or on the façade)', 'depth from the daylight face measurable'],
    '进深 ≲ 7 m 的部分能靠天光；中廊式整体 12–13 m')

IF('R11', ['建筑用途 = 办公 / 工作场所', '目标 = 一层或一个使用单元', '工位数 > 5（IfcFurniture 桌子）', '厕所 IfcSpace 及其洁具（IfcSanitaryTerminal）可识别；工位到厕所的距离可量'],
    ['building use = office / workplace', 'target = a storey or use unit', 'workstations > 5', 'toilet rooms and fixtures identifiable; distance desk → toilet measurable'],
    '男女分设；≤ 100 m 或一层；前室 + 隔间；每 5 WC 一洗手盆')

IF('R12', ['目标 = 一间会议室 IfcSpace', '房间里有座椅（IfcFurniture chair，contains）≥ 1', '房间净面积已知'],
    ['target = a conference IfcSpace', 'it contains ≥ 1 chair', 'net area known'],
    '≈ 2.5 m²/座；附属空间 ≈ 1/3')

IF('R32', ['建筑是工作场所', '目标 = 一个厕所单元（前室 + 隔间的 IfcSpace 组）', '便器、小便器、洗手盆（IfcSanitaryTerminal）及入口 IfcDoor 位置可读'],
    ['the building is a workplace', 'target = a toilet unit (anteroom + cubicles)', 'WCs, urinals, basins and the entrance door position readable'],
    '≤ 10 WC + 10 小便器 / 单元；小便器不从入口可见；每 5 WC 一洗手盆')

IF('R33', ['建筑用途 = 办公', '目标 = 一个办公单元（层 / IfcZone）', '工位数 ≥ 50', '茶水间 IfcSpace 可识别'],
    ['building use = office', 'target = an office unit (storey / zone)', 'workstations ≥ 50', 'tea kitchens identifiable'],
    '每 50–100 工位一间 ≈ 10 m² 茶水间，靠近工位')

IF('R34', ['建筑用途 = 办公', '目标 = 每个 IfcBuildingStorey', '保洁间 / 垃圾房 / 物业用房 IfcSpace 可由名称识别'],
    ['building use = office', 'target = every storey', 'cleaner\'s / refuse / caretaker rooms identifiable by name'],
    '每层保洁间；中央垃圾房；物业用房居中')

IF('R35', ['建筑用途 = 办公', '目标 = 入口层（含 IfcDoor IsExternal 主入口的 IfcBuildingStorey）', '门厅、会议区、餐厅、接待等 IfcSpace 可识别并能判相邻（opensTo）'],
    ['building use = office', 'target = the entrance storey', 'foyer, conference, canteen, reception spaces identifiable with adjacencies'],
    '会议区从入口直达；餐厅靠接待、门禁外；轮椅停放位')

IF('R36', ['建筑用途 = 办公', '目标 = 一间有 ≥ 4 张桌子的办公室 IfcSpace（组团）', '房间的窗 / 外墙位置可定位，工位到窗的距离可量'],
    ['building use = office', 'target = an office with ≥ 4 desks (group room)', 'window / façade position locatable, desk → window distance measurable'],
    '4–16 工位；任一工位距窗 ≤ 7.5 m')

IF('R37', ['目标 = 一张桌子 IfcFurniture（工位）', '桌面尺寸可从几何读', '所在 IfcSpace 的净面积与其他家具占用面积可算', '工作类型已知（屏幕 / 专业人员）'],
    ['target = a desk', 'desk size readable', 'room area and other furniture area computable', 'work type known'],
    '桌面 ≥ 120 × 80（专业 200 × 80）；每工位 ≥ 1.5 m² 活动面积')

IF('R38', ['目标 = 一个工作间 IfcSpace（办公 / 会议 / 教室）', '房间的 IfcWindow（opensTo）宽高与窗台高可读', '房间所有 IfcWall 的宽度之和可算', '净高已知（> 3.5 m 触发 30% 条款）'],
    ['target = a workroom (office / meeting / classroom)', 'its windows\' width, height and sill readable', 'sum of all wall widths computable', 'clear height known (> 3.5 m triggers the 30 % clause)'],
    '窗宽 ≥ 墙宽 / 10；窗台 0.85–1.25；> 3.5 m 时玻璃 ≥ 30% 外墙')

IF('R39', ['建筑用途 = 办公', '目标 = 一间办公室 IfcSpace，有 IfcWindow', '房间沿采光立面的宽度可量', '工位（桌子）到窗的距离可量'],
    ['building use = office', 'target = an office with windows', 'room width along the façade measurable', 'desk → window distance measurable'],
    '窗宽 ≥ 65% 房间宽；工作区距窗 ≈ 2 × 窗净高')

IF('R59', ['建筑用途 = 住宅', '每层每梯 1 户（IfcZone 或户门数）', '无电梯（无 IfcTransportElement / lift 空间）', '目标 = 楼层数'],
    ['building use = residential', 'one flat per floor per stair', 'no lift', 'target = number of storeys'],
    '一般限 4 层')

IF('R63', ['建筑用途 = 住宅', '户数 > 2（IfcZone 或户门）', '目标 = 其中一层的住户及其起居室、卧室、一个厕所、一个浴室、厨房', '从入口到该层的路径可判有无台阶（电梯 / 坡道）'],
    ['building use = residential', 'more than 2 flats', 'target = the flats of one storey and their key rooms', 'step-free path from the entrance decidable'],
    '一层无障碍可达；关键房间轮椅可用')

IF('R66', ['建筑用途 = 住宅', '目标 = 一户（IfcZone 或户门划分的房间组）的居住面积', '各房间净面积与净高可读', '阳台 / 露台 IfcSpace 可识别'],
    ['building use = residential', 'target = the living area of one flat', 'room net areas and clear heights readable', 'balconies identifiable'],
    '≥ 2 m 全算，1–2 m 半算，阳台 25–50%，净尺寸')

IF('R67', ['建筑用途 = 住宅', '目标 = 一户的房间组织', '房间功能可由名称判（起居 / 厨房 / 就餐 vs 卧室 / 卫生间）', '房间之间的连通（IfcDoor opensTo）可读'],
    ['building use = residential', 'target = the room organisation of one flat', 'room functions decidable by name', 'door connectivity readable'],
    '起居组与睡眠组各自成片；或中廊式每间独立进入')

IF('R68', ['建筑用途 = 住宅', '目标 = 一户（IfcZone 或户门划分）', '厨房、储藏间、卫生间 IfcSpace 可由名称或家具 / 洁具识别'],
    ['building use = residential', 'target = one flat', 'kitchen, storage and bathroom identifiable by name or fixtures'],
    '每户 ≥ 1 厨房 + 1 储藏间 + 1 独立卫生间')

IF('R69', ['建筑用途 = 住宅', '目标 = 一户内的储藏空间 IfcSpace（或壁柜）', '储藏面积、净宽与户面积可算'],
    ['building use = residential', 'target = storage space in one flat', 'storage area, clear width and flat area computable'],
    '≥ 1 m²、净宽 75 cm；大户 2%')

IF('R71', ['建筑是公众可达类型（无障碍要求）', '目标 = 每个 IfcSpace 和每条走廊', '房间扣除 IfcFurniture 后的净空可算', '走廊净宽可量；电梯门前区域可定位'],
    ['the building is publicly accessible', 'target = every room and corridor', 'free space after furniture computable', 'corridor width measurable; lift door zones locatable'],
    '每间 1.50 × 1.50 转身位；走廊 ≥ 1.50；电梯门前不重叠')

IF('R72', ['建筑是公众可达类型', '目标 = 一条走廊 IfcSpace，长度 > 15 m', '走廊各处净宽可量'],
    ['the building is publicly accessible', 'target = a corridor longer than 15 m', 'clear width along it measurable'],
    '设 1.80 × 1.80 会车位')

IF('R75', ['建筑用途 = 住宅且该户为无障碍户（R63）', '目标 = 户内每个房间和通道', '家具 IfcFurniture 的位置与墙的净距可量'],
    ['residential and the flat is the accessible one', 'target = every room and passage in the flat', 'furniture positions and clearances to walls measurable'],
    '家具旁、床侧、墙间、通道 ≥ 1.20 m')

IF('R76', ['建筑用途 = 住宅', '目标 = 一个居室 IfcSpace（起居、卧室、儿童房）', '面积、净高可读；房间的 IfcWindow 面积可算'],
    ['building use = residential', 'target = a habitable room', 'area, clear height readable; window area computable'],
    '≥ 8 m²；≥ 2.40；窗 ≥ 1/8')

IF('R77', ['建筑用途 = 住宅', '目标 = 一个阳台 / 露台 IfcSpace', '户内人数已知（external）', '通向阳台的 IfcDoor 另一侧房间可读'],
    ['building use = residential', 'target = a balcony / terrace', 'household size known', 'the room its door opens from readable'],
    '3–4 人 7 m²，5–6 人 9 m²；接起居 / 就餐')

IF('R78', ['建筑用途 = 住宅', '目标 = 一户的门厅（户门 IfcDoor 内第一个 IfcSpace）', '门厅各 IfcDoor 另一侧房间类型可读'],
    ['building use = residential', 'target = the flat\'s entrance hall', 'rooms behind each hall door readable'],
    '厨房、WC、楼梯从门厅直达')

IF('R79', ['建筑用途 = 住宅', '目标 = 户内走道 IfcSpace', '两侧 IfcWall 净距可量；走道内 IfcFurniture 可识别'],
    ['building use = residential', 'target = an internal corridor of a flat', 'wall clearance measurable; furniture in it identifiable'],
    '≥ 1.00 m；柜子嵌入式')

IF('R80', ['建筑用途 = 住宅，形式 = 独立住宅', '目标 = 每个 IfcBuildingStorey', '该层 IfcDoor IsExternal 及其通向的户外 IfcSpace（花园、露台、内院、屋顶花园）可识别'],
    ['residential, detached house', 'target = every storey', 'external doors of that storey and the outdoor space they open to identifiable'],
    '每层直通户外空间')

IF('R81', ['建筑用途 = 住宅', '目标 = 入户门 IfcDoor，门前为凹口（两侧外墙退让）', '凹口宽、深可量'],
    ['building use = residential', 'target = a flat entrance door set in a recess', 'recess width and depth measurable'],
    '宽 ≥ 1.25（最好 1.50），深 ≈ 1.00')

IF('R82', ['目标 = 一个卫生间 IfcSpace', '房间内 IfcSanitaryTerminal 的类型（WC / basin / shower / bath）可读'],
    ['target = a sanitary room', 'fixture types readable'],
    '按洁具组合归类：客用 WC / 淋浴间 / 浴室 / 完整浴室')

IF('R83', ['目标 = 一个讲演厅 / 会议厅 / 音乐厅 IfcSpace', '座位数已知（IfcFurniture 座椅 contains）', '容积 = 净面积 × 净高可算', '用途（讲话 / 音乐）已知'],
    ['target = a hall / auditorium / conference room', 'seats known', 'volume computable', 'use (speech / music) known'],
    '讲话 4 m³/人；音乐 10 m³/人')

IF('R84', ['目标 = 餐饮厨房的员工区（IfcSpace kitchen + 相邻员工房间）', '员工数 > 10（external，或按厨房规模估）', '休息室 IfcSpace 可识别'],
    ['target = the staff area of a restaurant kitchen', 'staff > 10', 'rest room identifiable'],
    '须设休息室')

IF('R85', ['建筑用途 = 高校 / 教育', '目标 = 一间研讨室 IfcSpace', '座位数（IfcFurniture）、面积、进深、净高可读', '是否只有一面外墙通风可判（IfcWindow / 外墙）'],
    ['education', 'target = a seminar room', 'seats, area, depth, clear height readable', 'single-sided ventilation decidable'],
    '1.9–2.0 m²/生；单侧通风时进深 ≤ 2.5 × 净高')

IF('R87', ['建筑用途 = 办公', '目标 = 走廊 / 疏散通道 IfcSpace', '通道内的 IfcFurniture（contains）可识别'],
    ['building use = office', 'target = a corridor / escape route', 'furniture inside it identifiable'],
    '通道内不得放家具；共用设施进使用房间或专用房间')

IF('R89', ['目标 = 一个屏幕工位 IfcFurniture（桌子）', '桌子的朝向（ObjectPlacement）可读', '房间窗立面方向与灯带方向可读'],
    ['target = a screen workstation (desk)', 'desk orientation readable', 'window façade and light-band directions readable'],
    '视线平行于窗立面与灯带，屏幕在两者之间')

IF('R91', ['建筑用途 = 住宅', '目标 = 一扇 IfcDoor', '门两侧 IfcSpace 的类型可读（→ 房门 / 浴室 WC 门 / 户门 / 入户大门）', 'OverallWidth / Height 可读'],
    ['building use = residential', 'target = an IfcDoor', 'the rooms on both sides readable (→ door role)', 'width / height readable'],
    '房门 80、浴 WC 70、户门 ≥ 90、大门 ≤ 115；高 ≥ 210')

IF('R93', ['目标 = 一个有人使用的 IfcSpace，它所在层只有一条楼梯路线（IfcStair < 2）', '该房间有外窗 IfcWindow，宽、高与窗台高可读'],
    ['target = an occupied room whose storey has only one stair route', 'it has an external window with readable size and sill'],
    '窗净开口 ≥ 0.9 × 1.2 m，窗台 ≤ 1.2 m')

# ───────────── Element ─────────────
IF('R07', ['目标 = 一扇 IfcDoor', '是否内门 / 外门可读（IsExternal），两侧 IfcSpace 可读', '建筑是公众可达类型 → 净宽条款生效', '入口层与地坪高差可判（无台阶）'],
    ['target = an IfcDoor', 'internal / external and the two rooms readable', 'the building is publicly accessible → the clear-width clause applies', 'entrance step-free decidable'],
    '内门净高 ≥ 2.10；公众可达门净宽 ≥ 0.90；一个入口 ≥ 0.90 且无台阶')

IF('R08', ['目标 = 一面 IfcWall IsExternal = true', '材料层中有混凝土（IfcMaterialLayer 名含 Beton / concrete / STB）', '内侧房间为采暖房间'],
    ['target = an external wall', 'a concrete layer in its materials', 'the room inside is heated'],
    '必须有保温层（外保温或夹心）')

IF('R42', ['目标 = 一扇 IfcDoor 及其洞口', 'OverallWidth（标志宽度）可读', '门框厚度 / 净开启宽度可读或按 DIN 18100 表推'],
    ['target = a door and its opening', 'nominal width readable', 'frame / clear opening readable or taken from DIN 18100'],
    '洞口为标准模数或 125 mm 倍数；用净宽比 0.90')

IF('R43', ['目标 = 作为紧急出口的 IfcDoor IsExternal', '建筑总人数可估（座椅 / 桌子数）', '门型可读（旋转 / 推拉 / 平开）', '其他外门的宽度之和可算'],
    ['target = an external door used as an emergency exit', 'headcount estimable', 'door type readable', 'sum of other exit widths computable'],
    '不得旋转 / 推拉；总宽 ≥ 1.0 m / 150 人')

IF('R44', ['目标 = 一扇 IfcWindow，装在 IsExternal 墙上', '内侧 IfcSpace 为采暖房间', '玻璃层数 / U 值（Pset_WindowCommon）可读'],
    ['target = a window in an external wall', 'the room inside is heated', 'glazing / U-value readable'],
    '至少中空或双层玻璃；U 按 EnEV')

IF('R45', ['目标 = 一个平屋面（IfcRoof FLAT_ROOF 或屋面 IfcSlab，坡度 < 10°）', '坡度（PitchAngle 或几何）可读', '构造层顺序（IfcMaterialLayer：保温、隔汽）可读'],
    ['target = a flat roof', 'slope readable', 'layer order readable'],
    '坡度 ≥ 2%（推荐 5%）；隔汽层在暖侧')

IF('R46', ['目标 = 一面内隔墙 IfcWall（IsExternal = false，LoadBearing = false）', '两侧房间有无吊顶 / 架空地板（IfcCovering）可判', '墙端是否接到立面竖梃（IfcCurtainWall / IfcMember）可判', '两侧房间的隔声要求已知'],
    ['target = an internal non-load-bearing partition', 'ceiling / raised floor presence decidable', 'whether the end meets a mullion decidable', 'acoustic requirement of the rooms known'],
    '穿吊顶 / 架空地板到结构，或那些构件自身隔声；端部接竖梃')

IF('R65', ['目标 = 一条疏散走廊 IfcSpace 或楼梯间的 IfcDoor', '走廊长度 > 30 m，或该门一侧是楼梯间 IfcSpace、另一侧是走廊', '门的 SelfClosing / SmokeStop / FireRating 可读'],
    ['target = an escape corridor or a stairwell door', 'corridor > 30 m, or the door joins a stairwell and a corridor', 'door properties readable'],
    '分段门与楼梯间门自闭防烟；地下室 / 商店 / 车间通楼梯 T 30')

IF('R95', ['目标 = 一面 IfcWall IsExternal = true', '材料层只有一层砌体（无独立保温层、无空气层）', '材料名可读（加气 / 多孔 / 普通砖）'],
    ['target = an external wall', 'a single masonry layer (no separate insulation, no cavity)', 'material name readable'],
    '高保温砌块 + 保温砂浆；否则加内 / 外保温层')

IF('R96', ['目标 = 一面 IfcWall IsExternal = true', '材料层 = 内叶砌体 + 空气层 / 保温 + 外叶砌体（夹心墙）', '各层厚度可读'],
    ['target = an external wall', 'layers = inner leaf + cavity / insulation + outer leaf', 'layer thicknesses readable'],
    '外叶 ≥ 90 mm；空气层 40–150 mm')

IF('R98', ['目标 = 一个外围护构件（IfcWall / IfcRoof / IfcSlab，IsExternal）', '各材料层厚度 d 可读；导热系数 λ 可读（Pset_MaterialThermal，常缺）', 'Pset 里的 ThermalTransmittance 可读'],
    ['target = an envelope element', 'layer thicknesses readable; conductivities readable (often missing)', 'ThermalTransmittance in the Pset readable'],
    '1/U = R_si + Σ d/λ + R_se；与 Pset 值一致')

IF('R99', ['目标 = 一个屋面 IfcRoof / IfcSlab', '构造层含种植 / 基质层（材料名）', '坡度可读'],
    ['target = a roof', 'a vegetation / substrate layer in its materials', 'slope readable'],
    '坡屋面 ≤ 25°；平屋面 ≤ 2–3%')

IF('R100', ['目标 = 一个坡屋面 IfcRoof（PredefinedType 坡屋面类型或坡度 > 10°）', '构造层顺序可读（保温、隔汽、空气层）', '椽 / 梁高度可读'],
    ['target = a pitched roof', 'layer order readable', 'rafter depth readable'],
    '保温在椽间 / 椽下，隔汽层室内侧；通风屋面需更高椽')

IF('R101', ['建筑用途 = 住宅', '目标 = 一面 IfcWall，两侧 IfcSpace 属于不同的户（IfcZone）', '材料层厚度与密度可读，或 AcousticRating 可读'],
    ['building use = residential', 'target = a wall whose two sides belong to different flats', 'layer thickness × density or AcousticRating readable'],
    '面密度 ≥ 400 kg/m²；R′w 53 dB')


def main():
    rules, status = {}, {}
    for fn in ('rules_pilot.jsonl', 'rules_office.jsonl', 'rules_general.jsonl'):
        for l in open(os.path.join(HERE, fn), encoding='utf-8'):
            r = json.loads(l); rules[r['rid']] = r
    sp = os.path.join(HERE, '_status.json')
    if os.path.exists(sp):
        status = {k: v['status'] for k, v in json.load(open(sp, encoding='utf-8'))['rules'].items()}
    ids = [o['rid'] for o in OUT]
    assert len(ids) == len(set(ids)), 'duplicate'
    bad = [i for i in ids if i not in rules]; assert not bad, bad
    active = [r for r, st in status.items() if st == 'active']
    missing = sorted([r for r in active if r not in ids], key=lambda r: int(r[1:]))
    OUT.sort(key=lambda o: int(o['rid'][1:]))
    with open(os.path.join(HERE, 'if_concrete.jsonl'), 'w', encoding='utf-8') as fh:
        for o in OUT:
            fh.write(json.dumps(o, ensure_ascii=False) + '\n')
    print(f'{len(OUT)} concrete IFs → rules/if_concrete.jsonl; active rules without one: {missing}')


if __name__ == '__main__':
    main()

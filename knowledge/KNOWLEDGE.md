# Neufert 知识点清单（进阶题）

由 `tools/knowledge_md.py` 从 `hard_qa.jsonl` 生成。174 道进阶题共引用 350 条不同的 Neufert 原文，其中 **122 个知识点**收入本清单（另有 32 个经范围核对后归档，列在文末），分属 5 个层级、13 个主题。

- **页码**是书页码（`data/neufert/dataset` 所解析的 Neufert 英文版正文页码）；括号里的 `page_XXXX` 是 `data/neufert/dataset/pages.jsonl` 里的页面 id（= 书页码 + 12）。
- **intent** 是 `runs/intent_pilot_residential/intents.jsonl` 里对应的条目；只有住宅章节有。
- **用到的题**里，题号是进阶题 id 的缩写（如 `fzk_house-04` = `H-fzk_house-04`）。
- 每条原文都已和 `embeddings.sqlite` 中的 Neufert 文本逐字（含空白）核对一致；含换行、制表符或连续空格的原文以代码块原样展示。

- **层级**按 BOT 的空间层次从粗到细：Site & Building → Storey → Zone → Space → Element，并标出对应的 IFC 实体。知识点编号是固定 id，不随排序变化。
- 已移出清单的主题：酒店与餐饮（相关进阶题仍保留在 `hard_qa.jsonl`）。

## 层级

| 层级 | 含义 | BOT | IFC 实体 | 知识点数 |
|---|---|---|---|---|
| Site & Building | 场地与建筑：整栋楼层面的宏观规则（体量、退距、面积与体积核算、建筑进深） | `bot:Site, bot:Building` | IfcSite, IfcBuilding | 15 |
| Storey | 楼层与竖向：层数、层高、净高，以及连接各层的楼梯、坡道、电梯、护栏 | `bot:Storey` | IfcBuildingStorey；竖向交通在 IFC 里是构件：IfcStair, IfcStairFlight, IfcRamp, IfcRailing, IfcTransportElement | 25 |
| Zone | 分区：一组房间构成的单元（一套住宅、防火分区、疏散路线、办公使用单元） | `bot:Zone` | IfcZone（IFC4 另有 IfcSpatialZone） | 16 |
| Space | 空间：单个房间的大小、朝向、布局与相邻关系 | `bot:Space` | IfcSpace | 40 |
| Element | 构件：门、窗、墙、屋面及其构造层和性能 | `bot:Element` | IfcElement 的子类：IfcDoor, IfcWindow, IfcWall, IfcSlab, IfcRoof, IfcCovering … | 26 |

层级按知识点逐个归类，所以同一个主题可能出现在几个层级下。Storey 层除了层数、层高、净高，还收了连接各层的楼梯、坡道、电梯和护栏；这些在 IFC 里是构件（`IfcStair` 等），不是 `IfcBuildingStorey` 的属性。

### 检查时需要的 IFC 数据

除了实体本身的尺寸，很多知识点还要用到实体之间的关系或实体上的属性。下表是每类数据在 IFC 里的表达，以及 9 个模型里哪些有。

| 需要 | IFC 表达 | 知识点数 | 有这类数据的模型 | 说明 |
|---|---|---|---|---|
| 相邻/围合 | `IfcRelSpaceBoundary` | 20 | 2/9：ac20、fzk_house | 没有时只能从几何推断 |
| 房间分组 | `IfcZone / IfcSpatialZone` | 16 | 0/9 | 9 个模型都没有；“哪几间是一户”只能推断 |
| 朝向 | `IfcGeometricRepresentationContext.TrueNorth` | 0 | 9/9 | 7 个模型的值是默认的正上方为北，只有 fzk_house 和 samuel 是旋转过的值 |
| 洞口 | `IfcOpeningElement + IfcRelFillsElement` | 1 | 9/9 |  |
| 家具/洁具 | `IfcFurnishingElement / IfcFurniture / IfcSanitaryTerminal / IfcFlowTerminal` | 13 | 7/9：ac20、fantasy_hotel_1、fantasy_office_building_1、fantasy_office_building_2、fantasy_office_building_3、fantasy_residential_building_1、samuel_macalister_sample_house |  |
| 构造层 | `IfcMaterialLayerSet` | 11 | 3/9：ac20、fzk_house、samuel_macalister_sample_house |  |
| 电梯/坡道 | `IfcTransportElement / IfcRamp` | 8 | 0/9 | 9 个模型都没有 |
| 性能属性 | `Pset_*Common（FireRating, ThermalTransmittance, AcousticRating, IsExternal …）` | 14 | 未逐个核对 | 文件里出现 FireRating 的有 fantasy_hotel_1、fantasy_office_building_2、fantasy_office_building_3、fzk_house；出现 ThermalTransmittance 的有 digital_hub、fantasy_hotel_1、fantasy_office_building_2、fantasy_residential_building_1、fzk_house、samuel；出现 AcousticRating 的只有 fzk_house。只统计了属性名，未核对是否填了值 |
| 用途/人数 | `IfcSpace.Name / LongName, Pset_SpaceOccupancyRequirements, 建筑类型` | 63 | 未逐个核对 | 依赖房间命名，各模型质量不一，未逐个核对 |
| 场地 | `IfcSite 的地块边界与场地几何` | 2 | 未逐个核对 | 未核对各模型的场地几何 |

按上表，有 **23 个知识点**所需的数据在 9 个模型里都没有（主要是房间分组和电梯/坡道）：K16、K18、K27、K30、K83、K91、K149、K151、K34、K39、K42、K76、K77、K78、K85、K94、K103、K107、K127、K135、K25、K68、K72。

## 总览

| 知识点 | 层级 | 主题 | 内容 | IFC 实体 | 需要 | LOD | 优先级 | 页码 | 题数 |
|---|---|---|---|---|---|---|---|---|---|
| K01 | Site & Building | 场地与体量 | 高层建筑 | IfcBuilding, IfcBuildingStorey | — | 100–200 | ★★★ | p.244, p.246 | 4 |
| K05 | Site & Building | 场地与体量 | 退距（Abstandsfläche） | IfcSite, IfcBuilding | 场地 | 100–200 | ★★★ | p.64 | 5 |
| K06 | Site & Building | 场地与体量 | 建筑密度与容积率 | IfcSite, IfcBuilding | 场地 | 100–200 | ★★ | p.63 | 2 |
| K79 | Site & Building | 居室标准与面积计算 | DIN 277 面积分类与可出租面积 | IfcBuilding, IfcSpace | 用途/人数 | 200 | ★★★ | p.63 | 2 |
| K80 | Site & Building | 居室标准与面积计算 | DIN 277 建筑体积（总体积与净体积） | IfcBuilding, IfcBuildingStorey | — | 200 | ★★ | p.63 | 1 |
| K92 | Site & Building | 住宅·户型组织与入户 | 联排住宅进深 ≤12 m、面宽 4–8 m | IfcBuilding | 用途/人数 | 100–200 | ★★★ | p.144 | 0 |
| K116 | Site & Building | 办公 | 建筑进深与采光深度 | IfcBuilding | 用途/人数 | 100–200 | ★★★ | p.240, p.241 | 5 |
| K131 | Site & Building | 办公 | 装修网格与立面网格一致 | IfcGrid, IfcWall, IfcWindow | — | 200 | ★★★ | p.240 | 0 |
| K132 | Site & Building | 办公 | 网格模数与建筑进深的搭配 | IfcGrid, IfcBuilding | 用途/人数 | 200 | ★★★ | p.240 | 0 |
| K133 | Site & Building | 办公 | 单排、双排与三排布局 | IfcBuilding, IfcSpace | 用途/人数 | 100–200 | ★★★ | p.241 | 0 |
| K139 | Site & Building | 办公 | 可逆办公楼（出租办公） | IfcBuilding | 用途/人数 | 100–200 | ★ | p.239 | 0 |
| K141 | Site & Building | 办公 | 每工位面积指标（直接工位与交通面积） | IfcBuilding, IfcSpace | 用途/人数 | 100–200 | ★★★ | p.238 | 0 |
| K146 | Site & Building | 办公 | 全空调对建筑体积的影响 | IfcBuilding | 用途/人数 | 100–200 | ★★ | p.242 | 0 |
| K152 | Site & Building | 高层建筑 | 高层建筑的分级 | IfcBuilding, IfcBuildingStorey | — | 100 | ★★ | p.246 | 0 |
| K153 | Site & Building | 高层建筑 | 高层建筑的用途限制 | IfcBuilding | 用途/人数 | 100 | ★ | p.244 | 0 |
| K07 | Storey | 楼梯、坡道、电梯与护栏 | 舒适步距公式 | IfcStairFlight | 性能属性 | 300 | ★★★ | p.121 | 12 |
| K08 | Storey | 楼梯、坡道、电梯与护栏 | 最佳坡度与踏步比 | IfcStairFlight | 性能属性 | 300 | ★★ | p.121 | 3 |
| K09 | Storey | 楼梯、坡道、电梯与护栏 | 每段梯段步数 | IfcStairFlight | 性能属性 | 200–300 | ★★★ | p.120 | 11 |
| K10 | Storey | 楼梯、坡道、电梯与护栏 | 休息平台 | IfcStair, IfcStairFlight, IfcBuildingStorey | — | 200–300 | ★★★ | p.120, p.121 | 12 |
| K11 | Storey | 楼梯、坡道、电梯与护栏 | 必要楼梯宽度与踏步比 | IfcStair, IfcStairFlight | 用途/人数 | 200–300 | ★★★ | p.120 | 7 |
| K12 | Storey | 楼梯、坡道、电梯与护栏 | 两户以下住宅的楼梯 | IfcStair, IfcStairFlight | 用途/人数 | 300 | ★★★ | p.120 | 1 |
| K13 | Storey | 楼梯、坡道、电梯与护栏 | 室外楼梯与办公楼梯的取向 | IfcStair | 用途/人数 | 300 | ★ | p.121 | 1 |
| K14 | Storey | 楼梯、坡道、电梯与护栏 | 螺旋楼梯 | IfcStair | — | 300 | ★★ | p.124 | 1 |
| K15 | Storey | 楼梯、坡道、电梯与护栏 | 楼座、夹层、阳台的护栏高度 | IfcRailing | — | 300 | ★★★ | p.122 | 5 |
| K16 | Storey | 楼梯、坡道、电梯与护栏 | 无障碍坡道 | IfcRamp, IfcRailing | 电梯/坡道 | 200–300 | ★★★ | p.22, p.25 | 1 |
| K17 | Storey | 楼梯、坡道、电梯与护栏 | 公共建筑楼梯两侧扶手 | IfcStair, IfcRailing | 用途/人数 | 350 | ★ | p.25 | 0 |
| K18 | Storey | 楼梯、坡道、电梯与护栏 | 电梯候梯区 | IfcTransportElement, IfcSpace | 电梯/坡道 | 200 | ★★ | p.22, p.128, p.130 | 2 |
| K19 | Storey | 楼梯、坡道、电梯与护栏 | 非必要楼梯 | IfcStair, IfcStairFlight | 用途/人数 | 300 | ★ | p.120 | 1 |
| K20 | Storey | 楼梯、坡道、电梯与护栏 | 休息平台宽度不小于梯段宽度 | IfcStairFlight, IfcSlab | — | 300 | ★★★ | p.121 | 2 |
| K27 | Storey | 无障碍 | 无障碍：无台阶通达与公众可达建筑的适用范围 | IfcBuildingStorey, IfcTransportElement, IfcRamp | 电梯/坡道、用途/人数 | 200 | ★★★ | p.22, p.25 | 9 |
| K30 | Storey | 无障碍 | 无障碍电梯 | IfcTransportElement, IfcSpace | 电梯/坡道 | 200 | ★★★ | p.22 | 3 |
| K32 | Storey | 无障碍 | 楼梯起止处活动区 | IfcStair, IfcSpace | — | 200 | ★★ | p.22 | 1 |
| K43 | Storey | 疏散与防火 | 主楼梯须设在连续封闭的楼梯间 | IfcStair, IfcSpace | 相邻/围合 | 200 | ★★★ | p.121 | 2 |
| K83 | Storey | 住宅·户型组织与入户 | 电梯与每层户数 | IfcBuildingStorey, IfcTransportElement | 电梯/坡道、房间分组 | 100–200 | ★★★ | p.142 | 2 |
| K91 | Storey | 住宅·户型组织与入户 | 一梯一户限四层（无电梯）；一梯三户 | IfcBuildingStorey, IfcStair | 房间分组 | 100–200 | ★★★ | p.142 | 1 |
| K112 | Storey | 办公 | 办公楼室内净高 | IfcBuildingStorey, IfcSpace | 用途/人数 | 200 | ★★★ | p.243, p.266 | 5 |
| K134 | Storey | 办公 | 楼梯间的间距（30 m / 60 m） | IfcStair, IfcSpace | 相邻/围合 | 100–200 | ★★★ | p.241 | 0 |
| K149 | Storey | 高层建筑 | 消防电梯（高度超过 30 m） | IfcTransportElement, IfcBuilding | 电梯/坡道 | 100–200 | ★★★ | p.246 | 0 |
| K150 | Storey | 高层建筑 | 高层疏散楼梯的梯井、排烟与出口 | IfcStair, IfcSpace | 用途/人数 | 200–300 | ★★ | p.246 | 0 |
| K151 | Storey | 高层建筑 | 高层电梯分组 | IfcTransportElement, IfcBuildingStorey | 电梯/坡道 | 100–200 | ★★ | p.246 | 0 |
| K34 | Zone | 无障碍 | 多户住宅的无障碍楼层 | IfcZone, IfcSpace | 房间分组、用途/人数 | 200 | ★★ | p.25 | 2 |
| K38 | Zone | 疏散与防火 | 疏散距离 | IfcSpace, IfcStair, IfcDoor | 相邻/围合 | 200 | ★★★ | p.121 | 0 |
| K39 | Zone | 疏散与防火 | 两条独立疏散路线 | IfcZone, IfcStair | 房间分组、相邻/围合 | 200 | ★★★ | p.511 | 0 |
| K42 | Zone | 疏散与防火 | 防火分区与防火墙 | IfcZone, IfcWall | 房间分组、性能属性 | 200 | ★★★ | p.513 | 2 |
| K45 | Zone | 疏散与防火 | 高层建筑的疏散走道 | IfcSpace, IfcDoor | 相邻/围合、用途/人数 | 200 | ★★★ | p.246 | 1 |
| K47 | Zone | 疏散与防火 | 长疏散走廊分段与楼梯间的封闭 | IfcSpace, IfcDoor | 相邻/围合、性能属性 | 200–300 | ★★ | p.517 | 1 |
| K76 | Zone | 居室标准与面积计算 | 居住面积计算 | IfcZone, IfcSpace | 房间分组、用途/人数 | 200 | ★★★ | p.63 | 2 |
| K77 | Zone | 居室标准与面积计算 | 阳台计入居住面积 | IfcZone, IfcSpace | 房间分组、用途/人数 | 200 | ★★ | p.155 | 3 |
| K78 | Zone | 居室标准与面积计算 | 住宅面积的计入范围与净尺寸量法 | IfcZone, IfcSpace | 房间分组 | 200–300 | ★★★ | p.136 | 1 |
| K85 | Zone | 住宅·户型组织与入户 | 分组式平面与中廊式平面 | IfcZone, IfcSpace | 房间分组、相邻/围合、用途/人数 | 200 | ★★★ | p.145 | 1 |
| K94 | Zone | 住宅·户型组织与入户 | 每户必备厨房与储藏间 | IfcZone, IfcSpace | 房间分组、用途/人数 | 200 | ★★★ | p.149, p.162 | 1 |
| K103 | Zone | 住宅·卧室、卫浴与储藏 | 卫生间 | IfcZone, IfcSpace | 房间分组、用途/人数、家具/洁具 | 200 | ★★★ | p.160 | 5 |
| K107 | Zone | 住宅·卧室、卫浴与储藏 | 户内储藏空间 | IfcZone, IfcSpace | 房间分组、用途/人数 | 200 | ★★ | p.162 | 1 |
| K127 | Zone | 办公 | 小型使用单元内的走廊 | IfcZone, IfcSpace | 房间分组、用途/人数 | 200 | ★★ | p.241 | 1 |
| K135 | Zone | 办公 | 组合式办公（combi-office） | IfcZone, IfcSpace | 房间分组、用途/人数 | 200 | ★★ | p.234, p.239 | 0 |
| K138 | Zone | 办公 | 非固定工位办公的面积节省 | IfcSpace, IfcFurnishingElement | 用途/人数、家具/洁具 | 200 | ★ | p.239 | 0 |
| K28 | Space | 无障碍 | 轮椅活动空间 | IfcSpace | 用途/人数 | 200 | ★★★ | p.21, p.25 | 4 |
| K29 | Space | 无障碍 | 无障碍卫生间 | IfcSpace, IfcSanitaryTerminal, IfcDoor | 家具/洁具、用途/人数 | 200–300 | ★★ | p.22 | 1 |
| K33 | Space | 无障碍 | 长走廊轮椅会车位 | IfcSpace | 用途/人数 | 200 | ★★ | p.22 | 2 |
| K35 | Space | 无障碍 | 无障碍住宅卫浴 | IfcSpace, IfcSanitaryTerminal | 家具/洁具 | 350 | ★★ | p.23 | 1 |
| K36 | Space | 无障碍 | 轮椅住宅的起居室 | IfcSpace | 用途/人数 | 200 | ★★ | p.24 | 1 |
| K37 | Space | 无障碍 | 无障碍住宅的户内活动区宽度 | IfcSpace, IfcFurnishingElement | 家具/洁具 | 200 | ★★ | p.23 | 1 |
| K48 | Space | 采光、日照、通风与窗 | 工作间的窗 | IfcSpace, IfcWindow | 相邻/围合、用途/人数 | 200–300 | ★★★ | p.97, p.266 | 4 |
| K52 | Space | 采光、日照、通风与窗 | 视野：窗宽不小于房间宽 65% | IfcSpace, IfcWindow | 相邻/围合 | 300 | ★ | p.495 | 4 |
| K53 | Space | 采光、日照、通风与窗 | 工作区距窗约为 2 倍窗净高 | IfcSpace, IfcWindow | 相邻/围合 | 200–300 | ★★ | p.266 | 1 |
| K74 | Space | 居室标准与面积计算 | 居室最低要求 | IfcSpace, IfcWindow | 相邻/围合 | 200 | ★★★ | p.167 | 7 |
| K81 | Space | 住宅·户型组织与入户 | 阳台面积 | IfcSpace | 用途/人数 | 200 | ★★ | p.155 | 3 |
| K82 | Space | 住宅·户型组织与入户 | 户外空间的连接 | IfcSpace | 相邻/围合、用途/人数 | 200 | ★★ | p.155 | 2 |
| K87 | Space | 住宅·户型组织与入户 | 门厅直达厨房、WC 和楼梯 | IfcSpace | 相邻/围合、用途/人数 | 200 | ★★ | p.147 | 1 |
| K89 | Space | 住宅·户型组织与入户 | 户内走道宽度 | IfcSpace | 用途/人数 | 200 | ★★ | p.148 | 1 |
| K90 | Space | 住宅·户型组织与入户 | 独立住宅每层通往户外 | IfcSpace, IfcBuildingStorey | 相邻/围合 | 200 | ★ | p.139 | 1 |
| K93 | Space | 住宅·户型组织与入户 | 入户凹口尺寸 | IfcSpace, IfcDoor | — | 200–300 | ★★ | p.146 | 0 |
| K109 | Space | 住宅·卧室、卫浴与储藏 | 卫生间类型 | IfcSpace, IfcSanitaryTerminal | 家具/洁具 | 300 | ★ | p.161 | 1 |
| K113 | Space | 办公 | 每工位总面积 | IfcSpace | 用途/人数 | 100–200 | ★★★ | p.238 | 1 |
| K114 | Space | 办公 | 工位尺寸 | IfcSpace, IfcFurnishingElement | 家具/洁具 | 350 | ★ | p.236 | 3 |
| K115 | Space | 办公 | 办公室进深、开间与模数 | IfcSpace | 用途/人数 | 200 | ★★★ | p.240 | 3 |
| K117 | Space | 办公 | 办公室类型 | IfcSpace | 用途/人数 | 200 | ★★ | p.232, p.233, p.239 | 5 |
| K118 | Space | 办公 | 会议区 | IfcSpace | 相邻/围合、用途/人数 | 200 | ★★ | p.238 | 6 |
| K119 | Space | 办公 | 办公卫生间与茶水间配置 | IfcSpace | 用途/人数 | 200 | ★★ | p.238 | 6 |
| K120 | Space | 办公 | 工作场所厕所（劳动场所规定） | IfcSpace, IfcSanitaryTerminal | 相邻/围合、用途/人数、家具/洁具 | 200 | ★★ | p.270 | 3 |
| K121 | Space | 办公 | 厅室的每人容积 | IfcSpace | 用途/人数 | 200 | ★ | p.483 | 1 |
| K122 | Space | 办公 | 保洁间与物业用房 | IfcSpace, IfcBuildingStorey | 用途/人数 | 200 | ★ | p.238 | 2 |
| K123 | Space | 办公 | 档案室 | IfcSpace | 用途/人数 | 200 | ★ | p.237, p.238 | 1 |
| K124 | Space | 办公 | 办公楼入口区 | IfcSpace | 相邻/围合、用途/人数 | 200 | ★ | p.238 | 1 |
| K125 | Space | 办公 | 员工餐厅位置 | IfcSpace | 相邻/围合、用途/人数 | 200 | ★ | p.238 | 1 |
| K126 | Space | 办公 | 组团办公室到窗距离 | IfcSpace, IfcWindow | 相邻/围合、家具/洁具 | 200 | ★★ | p.233 | 1 |
| K128 | Space | 办公 | 餐饮厨房员工休息室 | IfcSpace | 用途/人数 | 200 | ★★ | p.180 | 2 |
| K129 | Space | 办公 | 研讨室的规模与进深 | IfcSpace | 用途/人数 | 200 | ★★★ | p.202 | 2 |
| K130 | Space | 办公 | 高校教研人员办公室面积 | IfcSpace | 用途/人数 | 200 | ★★ | p.202 | 1 |
| K136 | Space | 办公 | 单间办公：疏散通道内不得放家具 | IfcSpace, IfcFurnishingElement | 家具/洁具、用途/人数 | 200 | ★★ | p.239 | 0 |
| K137 | Space | 办公 | 大空间办公的进深 | IfcSpace | 用途/人数 | 100–200 | ★★ | p.233 | 0 |
| K140 | Space | 办公 | 工位面积的构成 | IfcSpace, IfcFurnishingElement | 家具/洁具 | 300 | ★★ | p.235 | 0 |
| K142 | Space | 办公 | 屏幕工位与窗的关系 | IfcSpace, IfcFurnishingElement, IfcWindow | 家具/洁具、相邻/围合 | 300 | ★★ | p.236 | 0 |
| K143 | Space | 办公 | 档案存放的面积与位置 | IfcSpace, IfcFurnishingElement | 家具/洁具、用途/人数 | 200–300 | ★ | p.237 | 0 |
| K144 | Space | 办公 | 收发室 | IfcSpace | 用途/人数 | 200 | ★ | p.238 | 0 |
| K145 | Space | 办公 | 数据中心与服务器机房 | IfcSpace | 用途/人数 | 200–300 | ★ | p.238 | 0 |
| K22 | Element | 门 | 住宅门的常规宽度 | IfcDoor | 用途/人数 | 300 | ★★ | p.113 | 5 |
| K23 | Element | 门 | 内门净高 | IfcDoor | — | 300 | ★★ | p.113 | 3 |
| K24 | Element | 门 | 紧急出口的门型 | IfcDoor | 性能属性、用途/人数 | 300 | ★★ | p.10, p.113, p.115 | 3 |
| K25 | Element | 门 | 电梯入户的户门 | IfcDoor, IfcTransportElement | 电梯/坡道、用途/人数 | 300 | ★★ | p.146 | 2 |
| K26 | Element | 无障碍 | 无障碍门净宽 | IfcDoor | 用途/人数 | 300 | ★★★ | p.22, p.25 | 10 |
| K40 | Element | 疏散与防火 | 疏散窗 | IfcWindow | 洞口 | 300 | ★★ | p.97 | 2 |
| K41 | Element | 疏散与防火 | 出口宽度（按人数） | IfcDoor | 用途/人数 | 200 | ★★ | p.175 | 0 |
| K44 | Element | 疏散与防火 | 疏散走廊侧墙 F 30 | IfcWall, IfcWindow | 性能属性、用途/人数 | 300 | ★★ | p.514, p.516 | 1 |
| K46 | Element | 疏散与防火 | 高层建筑立面的层间防火 | IfcWall, IfcCurtainWall, IfcSlab | 性能属性 | 200–300 | ★★ | p.246 | 1 |
| K57 | Element | 围护结构与保温 | 单层外墙与附加保温层 | IfcWall | 构造层 | 300 | ★★★ | p.75, p.473 | 6 |
| K58 | Element | 围护结构与保温 | 夹心墙（双叶墙）的外叶与空气层 | IfcWall | 构造层 | 300 | ★★ | p.75 | 0 |
| K59 | Element | 围护结构与保温 | 混凝土外墙必须附加保温 | IfcWall | 构造层 | 300 | ★★★ | p.78 | 4 |
| K60 | Element | 围护结构与保温 | 背通风外挂层的空气间层 | IfcWall, IfcCovering | 构造层 | 350 | ★ | p.473 | 1 |
| K61 | Element | 围护结构与保温 | 热阻与传热系数计算 | IfcWall, IfcRoof, IfcSlab | 构造层、性能属性 | 300 | ★★★ | p.471, p.472 | 2 |
| K63 | Element | 围护结构与保温 | 平屋面排水坡度 | IfcRoof, IfcSlab | — | 300 | ★★ | p.91 | 3 |
| K65 | Element | 围护结构与保温 | 隔汽层设在暖侧 | IfcRoof, IfcWall | 构造层 | 350 | ★ | p.90, p.472, p.473 | 2 |
| K66 | Element | 围护结构与保温 | 种植屋面的坡度 | IfcRoof, IfcSlab | 构造层 | 300 | ★ | p.94 | 1 |
| K67 | Element | 围护结构与保温 | 坡屋面保温位置与通风构造 | IfcRoof | 构造层 | 300–350 | ★★ | p.90 | 2 |
| K68 | Element | 墙体与构造 | 分户墙隔声 | IfcWall | 性能属性、构造层、房间分组 | 300 | ★★★ | p.478, p.479 | 0 |
| K69 | Element | 墙体与构造 | 模数协调与标志尺寸 | IfcWall, IfcGrid | — | 200–300 | ★★ | p.34, p.35 | 1 |
| K70 | Element | 墙体与构造 | 建筑等级与承重墙耐火 | IfcWall, IfcColumn | 性能属性、用途/人数 | 200 | ★★★ | p.464, p.514 | 3 |
| K72 | Element | 墙体与构造 | 住宅/商业单元之间的分隔墙 | IfcWall | 性能属性、房间分组 | 300 | ★★★ | p.514 | 1 |
| K73 | Element | 墙体与构造 | 外墙及外墙饰面的燃烧性能 | IfcWall, IfcCovering | 性能属性、构造层 | 300 | ★★ | p.514 | 1 |
| K147 | Element | 办公 | 立面竖梃与隔墙的连接 | IfcCurtainWall, IfcMember, IfcWall | — | 300 | ★★ | p.240 | 0 |
| K148 | Element | 办公 | 轻质隔墙的隔声与上下延续 | IfcWall, IfcCovering | 性能属性、构造层 | 300 | ★★ | p.240 | 0 |
| K154 | Element | 高层建筑 | 高层外窗的清洁 | IfcWindow, IfcCurtainWall | — | 300 | ★ | p.246 | 0 |

## 早期设计（LOD 200–300）核心知识点：47 个

★★★ = 直接左右早期设计决策（体量、交通核、房间尺寸、构造选型）或是法规硬门槛，且在 LOD 200–300 的模型上可检查。★★ = 重要但影响面较小或与核心点重叠。★ = 细部、建议性或超出 LOD 300。

| 决策 | 核心知识点 |
|---|---|
| 体量 | K01 高层建筑；K05 退距（Abstandsfläche）；K133 单排、双排与三排布局；K83 电梯与每层户数；K112 办公楼室内净高 |
| 平面进深 | K92 联排住宅进深 ≤12 m、面宽 4–8 m；K116 建筑进深与采光深度；K131 装修网格与立面网格一致；K132 网格模数与建筑进深的搭配；K115 办公室进深、开间与模数 |
| 面积核算 | K79 DIN 277 面积分类与可出租面积；K141 每工位面积指标（直接工位与交通面积）；K76 居住面积计算；K78 住宅面积的计入范围与净尺寸量法；K113 每工位总面积 |
| 交通核 | K07 舒适步距公式；K09 每段梯段步数；K10 休息平台；K11 必要楼梯宽度与踏步比；K12 两户以下住宅的楼梯；K20 休息平台宽度不小于梯段宽度；K91 一梯一户限四层（无电梯）；一梯三户；K134 楼梯间的间距（30 m / 60 m）；K149 消防电梯（高度超过 30 m） |
| 疏散 | K43 主楼梯须设在连续封闭的楼梯间；K38 疏散距离；K39 两条独立疏散路线；K42 防火分区与防火墙；K45 高层建筑的疏散走道 |
| 无障碍 | K16 无障碍坡道；K27 无障碍：无台阶通达与公众可达建筑的适用范围；K30 无障碍电梯；K28 轮椅活动空间；K26 无障碍门净宽 |
| 安全 | K15 楼座、夹层、阳台的护栏高度 |
| 户型布局 | K85 分组式平面与中廊式平面；K94 每户必备厨房与储藏间；K103 卫生间 |
| 房间尺寸 | K74 居室最低要求；K129 研讨室的规模与进深 |
| 立面与采光 | K48 工作间的窗 |
| 构造选型 | K57 单层外墙与附加保温层；K59 混凝土外墙必须附加保温；K61 热阻与传热系数计算；K68 分户墙隔声；K70 建筑等级与承重墙耐火；K72 住宅/商业单元之间的分隔墙 |

优先级分布：★★★ 47 · ★★ 53 · ★ 22；★★★ 知识点共被 100 道题使用。

### 按主题

| 主题 | 知识点数 | 涉及题数（按知识点累计） |
|---|---|---|
| 场地与体量 | 3 | 11 |
| 居室标准与面积计算 | 6 | 16 |
| 住宅·户型组织与入户 | 11 | 13 |
| 办公 | 37 | 50 |
| 高层建筑 | 6 | 0 |
| 楼梯、坡道、电梯与护栏 | 14 | 59 |
| 无障碍 | 11 | 35 |
| 疏散与防火 | 10 | 10 |
| 住宅·卧室、卫浴与储藏 | 3 | 7 |
| 采光、日照、通风与窗 | 3 | 9 |
| 门 | 4 | 13 |
| 围护结构与保温 | 9 | 21 |
| 墙体与构造 | 5 | 6 |

### 按页码

| 页码 | 章节 | 知识点 |
|---|---|---|
| p.10 (page_0022) | Basics | K24 |
| p.21 (page_0033) | Basics | K28 |
| p.22 (page_0034) | Basics | K16, K18, K27, K30, K32, K29, K33, K26 |
| p.23 (page_0035) | Basics | K35, K37 |
| p.24 (page_0036) | Basics | K36 |
| p.25 (page_0037) | Basics | K16, K17, K27, K34, K28, K26 |
| p.34 (page_0046) | Basics | K69 |
| p.35 (page_0047) | Basics | K69 |
| p.63 (page_0075) | Design process | K06, K79, K80, K76 |
| p.64 (page_0076) | Design process | K05 |
| p.75 (page_0087) | Building components | K57, K58 |
| p.78 (page_0090) | Building components | K59 |
| p.90 (page_0102) | Building components | K65, K67 |
| p.91 (page_0103) | Building components | K63 |
| p.94 (page_0106) | Building components | K66 |
| p.97 (page_0109) | Building components | K48, K40 |
| p.113 (page_0125) | Building components | K22, K23, K24 |
| p.115 (page_0127) | Building components | K24 |
| p.120 (page_0132) | Building components | K09, K10, K11, K12, K19 |
| p.121 (page_0133) | Building components | K07, K08, K10, K13, K20, K43, K38 |
| p.122 (page_0134) | Building components | K15 |
| p.124 (page_0136) | Building components | K14 |
| p.128 (page_0140) | Building components | K18 |
| p.130 (page_0142) | Building components | K18 |
| p.136 (page_0148) | Residential buildings | K78 |
| p.139 (page_0151) | Residential buildings | K90 |
| p.142 (page_0154) | Residential buildings | K83, K91 |
| p.144 (page_0156) | Residential buildings | K92 |
| p.145 (page_0157) | Residential buildings | K85 |
| p.146 (page_0158) | Residential buildings | K93, K25 |
| p.147 (page_0159) | Residential buildings | K87 |
| p.148 (page_0160) | Residential buildings | K89 |
| p.149 (page_0161) | Residential buildings | K94 |
| p.155 (page_0167) | Residential buildings | K77, K81, K82 |
| p.160 (page_0172) | Residential buildings | K103 |
| p.161 (page_0173) | Residential buildings | K109 |
| p.162 (page_0174) | Residential buildings | K94, K107 |
| p.167 (page_0179) | Accommodation | K74 |
| p.175 (page_0187) | Accommodation | K41 |
| p.180 (page_0192) | Accommodation | K128 |
| p.202 (page_0214) | Education and research | K129, K130 |
| p.232 (page_0244) | Administration and offices | K117 |
| p.233 (page_0245) | Administration and offices | K117, K126, K137 |
| p.234 (page_0246) | Administration and offices | K135 |
| p.235 (page_0247) | Administration and offices | K140 |
| p.236 (page_0248) | Administration and offices | K114, K142 |
| p.237 (page_0249) | Administration and offices | K123, K143 |
| p.238 (page_0250) | Administration and offices | K141, K113, K118, K119, K122, K123, K124, K125, K144, K145 |
| p.239 (page_0251) | Administration and offices | K139, K135, K138, K117, K136 |
| p.240 (page_0252) | Administration and offices | K116, K131, K132, K115, K147, K148 |
| p.241 (page_0253) | Administration and offices | K116, K133, K134, K127 |
| p.242 (page_0254) | Administration and offices | K146 |
| p.243 (page_0255) | Administration and offices | K112 |
| p.244 (page_0256) | Administration and offices | K01, K153 |
| p.246 (page_0258) | Administration and offices | K01, K152, K149, K150, K151, K45, K46, K154 |
| p.266 (page_0278) | Industry and trade | K112, K48, K53 |
| p.270 (page_0282) | Industry and trade | K120 |
| p.464 (page_0476) | Agriculture | K70 |
| p.471 (page_0483) | Building services | K61 |
| p.472 (page_0484) | Building services | K61, K65 |
| p.473 (page_0485) | Building services | K57, K60, K65 |
| p.478 (page_0490) | Building services | K68 |
| p.479 (page_0491) | Building services | K68 |
| p.483 (page_0495) | Building services | K121 |
| p.495 (page_0507) | Building services | K52 |
| p.511 (page_0523) | Building services | K39 |
| p.513 (page_0525) | Building services | K42 |
| p.514 (page_0526) | Building services | K44, K70, K72, K73 |
| p.516 (page_0528) | Building services | K44 |
| p.517 (page_0529) | Building services | K47 |

# Site & Building

场地与建筑：整栋楼层面的宏观规则（体量、退距、面积与体积核算、建筑进深）

## 场地与体量

### K01 高层建筑

高层建筑指供人长期停留、最高楼层在建筑一侧高出地面 > 22 m 的建筑；高度 ≤ 60 m 的高层须至少设两部相对布置、位于两个不同防火分区的疏散楼梯，其通行宽度须 ≥ 1.25 m（例外情况下可批准仅设一部安全楼梯）。

- **早期设计**：★★★ · LOD 100–200 · 决定体量
- **IFC**：`IfcBuilding`、`IfcBuildingStorey`
- **页码**：p.244 (page_0256), p.246 (page_0258) · Administration and offices
- **用到的题**（4 道，2 个模型）：`office1-02`, `office1-14`, `office3-02`, `office3-14`
- **知识探针题**（须 · recall）：According to the German high-rise building regulations: (a) above what height of the uppermost floor (on one side of the building, above ground level) does a building intended for long-term human occupation count as a high-rise building, and (b) what minimum walking width must each of the emergency stairs have in a high-rise building up to 60 m high?
  - 标准答案：(a) more than 22 m; (b) at least 1.25 m
  - 选项：A. > 22 m; 1.00 m；B. > 25 m; 1.50 m；**C. > 22 m; 1.25 m** ✓；D. > 30 m; 1.25 m
- **原文**：
  - p.244：“High-rise buildings are those intended for long-term human occupation whose upper-most floor on one side of the building is more than 22 m above ground level.”
  - p.246：“High-rise buildings up to 60 m high: at least two emergency stairs must be available, which must be located opposite in two separate fire compartments. Their walking width must be at least 1.25 m.”

### K05 退距（Abstandsfläche）

按示范建筑条例（MBO），退距深度为 0.4 H 且不小于 3 m（商业区和工业区为 0.2 H，不小于 3 m）；建筑等级 1 和 2、地上不超过三层的建筑外墙前，3 m 深度即足够；各州 LBO 规定不同并有其他例外。墙高 H 自地面量至墙顶或墙与屋面覆盖层交线，垂直于墙面测量；坡度 ≤ 70° 的屋面高度按 1/3 计入、≥ 70° 全部计入。退距须位于本地块内（也可延伸至公共交通、绿地或水域的中线，或延伸至依公法确定不可建造的其他地块）。檐口、挑檐等外墙突出构件若占墙宽合计 < 1/3、外挑 ≤ 1.50 m 且距对面地界 ≥ 2 m，则不计入退距。

- **早期设计**：★★★ · LOD 100–200 · 决定体量
- **IFC**：`IfcSite`、`IfcBuilding` · 还需要：场地（`IfcSite 的地块边界与场地几何`）
- **页码**：p.64 (page_0076) · Design process
- **用到的题**（5 道，4 个模型）：`ac20-19`, `office1-12`, `office1-13`, `frb1-20`, `fzk_house-29`
- **知识探针题**（须 · recall）：According to the German model building regulations (MBO), what is the general rule for the required depth of the setback area (Abstandsfläche) in front of an external wall of height H, in general areas (i.e. not commercial or industrial areas)?
  - 标准答案：0.4 × H, but at least 3 m
  - 选项：A. 0.2 × H, but at least 3 m；B. 1.0 × H, but at least 2.5 m；C. 0.5 × H, but at least 3 m；**D. 0.4 × H, but at least 3 m** ✓
- **原文**：
  - p.64：“The depth of setback areas differs in the various state building regulations (LBO)). According to the model building regulations (MBO), it is 0.4 × H, but at least 3 m (0.2 × H, min. 3 m for commercial and industrial areas). In front of the outside walls of building classes 1 and 2 with not more than three overground storeys, 3 m depth is also sufficient.”
  - p.64：“The depth of the setback area is measured according to wall height → ④ – ⑥. This is measured at right angles to the wall. Wall height means the dimension from ground level to upper extent of the wall or to the intersection of the wall with the roof covering → ④. The height of roofs with a pitch of ≤70° is included to one third, ≥70° fully with the wall height → ⑤.”
  - p.64（原文含换行/制表符，按原样）：

    ```text
    Building elements projecting from the outside wall (cornices, roof overhang) are not considered in the measurement of setback areas → ⑧. Projections remain unconsidered if they:
    – take up altogether less than one third of the width of the outside wall
    – project by a max. 1.50 m in front of the outside wall
    – stay at least 2 m distant from the opposing plot boundary
    ```
  - p.64：“Setback areas are the spaces between buildings and their plot boundaries.”
  - p.64：“Setback areas must be on the plot itself”
  - p.64：“According to the model building regulations (MBO), it is 0.4 × H, but at least 3 m (0.2 × H, min. 3 m for commercial and industrial areas).”
  - p.64：“Wall height means the dimension from ground level to upper extent of the wall or to the intersection of the wall with the roof covering”
  - p.64：“The height of roofs with a pitch of ≤70° is included to one third, ≥70° fully with the wall height”
  - p.64：“They may also lie on public traffic, green and water areas, but only to their centre.”
  - p.64：“In front of the outside walls of building classes 1 and 2 with not more than three overground storeys, 3 m depth is also sufficient.”

### K06 建筑密度与容积率

土地利用条例规定的规划法建设用途度量参数：建筑密度（plot coverage ratio）为可允许的建成面积占地块面积之比，建成面积包括建筑平面面积及车库、停车位及其通道、附属面积和地块下方的地下设施；容积率（floor-area ratio）为可允许的楼层面积（所有完整楼层外轮廓尺寸，不含附属面积、阳台、凉廊、露台及允许建在退距内的构筑物）与地块面积之比。

- **早期设计**：★★ · LOD 100–200
- **IFC**：`IfcSite`、`IfcBuilding` · 还需要：场地（`IfcSite 的地块边界与场地几何`）
- **页码**：p.63 (page_0075) · Design process
- **用到的题**（2 道，2 个模型）：`ac20-20`, `fzk_house-29`
- **知识探针题**（须 · recall）：Under the German land use regulation (measures of building use in planning law), the floor-area ratio (GFZ) is the permissible ratio of storey area to plot area. How is the storey area determined, and are balconies, loggias and terraces included?
  - 标准答案：External dimensions of all full storeys; balconies, loggias and terraces (and subsidiary areas, structures permissible in setback areas) are excluded
  - 选项：A. Net internal floor area of all storeys, including balconies and loggias；**B. External dimensions of all full storeys, excluding balconies, loggias and terraces** ✓；C. External dimensions of all storeys including basements, balconies and terraces；D. Ground-floor footprint only, including garages and their access
- **原文**：
  - p.63：“the plot coverage ratio determines the permissible ratio of built area on the plot (plan area of building including garages, parking places and their access, subsidiary areas... and underground facilities beneath the plot)”
  - p.63：“the floor-area ratio (determines the permissible ratio of storey area (external dimensions of all full floors, without subsidiary areas..., balconies, loggias, terraces and structures which are permissible inside setback areas) to the plot area.”

## 居室标准与面积计算

### K79 DIN 277 面积分类与可出租面积

毛面积按外轮廓计算，结构面积是墙柱所占面积，净面积是构件之间的面积，再分为使用、技术和交通面积；可出租面积（GIF）不含楼梯、电梯、紧急出口、设备间和管井。

- **早期设计**：★★★ · LOD 200 · 决定面积核算
- **IFC**：`IfcBuilding`、`IfcSpace` · 还需要：用途/人数（`IfcSpace.Name / LongName, Pset_SpaceOccupancyRequirements, 建筑类型`）
- **页码**：p.63 (page_0075) · Design process
- **用到的题**（2 道，2 个模型）：`digital_hub-21`, `fzk_house-28`
- **知识探针题**（一般 · recall）：According to DIN 277, the net floor area is the sum of which three area categories?
  - 标准答案：Usable area, technical function area and traffic (circulation) area
  - 选项：**A. Usable area, technical function area and traffic area** ✓；B. Usable area, constructional area and traffic area；C. Gross area, constructional area and usable area；D. Letting area, communal area and traffic area
- **原文**：
  - p.63：“The gross floor area is the sum of the plan area of all levels (without usable roof areas), measured between the external dimensions of the surrounding building elements at floor height.”
  - p.63：“The constructional floor area is the sum of the plan area of all surrounding building elements (walls, columns, pillars, chimneys, non-accessible shafts, door openings, niches, apertures) measured between the external dimensions at floor height.”
  - p.63：“The net floor area is the usable floor area between the building elements (without door and window openings, cut-outs and niches) measured at floor level.”
  - p.63：“The net floor area is the sum of the usable area (area which serves the building’s intended purpose), the technical function area (rooms for building services, such as utility connection room, accessible shafts, etc.) and the traffic area (e.g. stairwells, corridors, lift shafts, escape balconies etc.).”
  - p.63：“The following do not belong to the letting area: stairs, lifts, emergency exits, escape balconies, services rooms, shafts, protection rooms, areas of columns, pillars and separate walls, areas with a clear ceiling height of 1.50 m or less.”
  - p.63：“2. Areas with communal right of use, individually listed as: rooms for communal use (WCs/bathrooms, staff rooms, etc.) and communal traffic areas (entrance halls, corridors, etc.).”

### K80 DIN 277 建筑体积（总体积与净体积）

按 DIN 277，总建筑体积为各层楼面面积乘以相应高度（自本层地面面层顶量至上层地面面层顶），净建筑体积为净面积乘以相应的室内净高。

- **早期设计**：★★ · LOD 200
- **IFC**：`IfcBuilding`、`IfcBuildingStorey`
- **页码**：p.63 (page_0075) · Design process
- **用到的题**（1 道，1 个模型）：`digital_hub-25`
- **知识探针题**（一般 · recall）：According to DIN 277, the gross built volume is the sum of the floor areas of all levels multiplied by the relevant height. Between which surfaces is that height measured?
  - 标准答案：From the top of the floor covering to the top of the floor covering of the next level
  - 选项：A. From the top of the floor covering to the underside of the ceiling；B. From the top of the structural slab to the underside of the suspended ceiling；C. From the underside of one structural slab to the underside of the next；**D. From the top of the floor covering to the top of the floor covering of the next level** ✓
- **原文**：
  - p.63：“The gross built volume is the sum of the floor areas of all levels multiplied by the relevant height (measured between top of floor covering and top of floor covering of the next level”
  - p.63：“The net built volume is the net floor area multiplied by the relevant clear ceiling height.”

## 住宅·户型组织与入户

### K92 联排住宅进深 ≤12 m、面宽 4–8 m

联排住宅只能从两个立面直接采光，经济进深不超过 12 m、面宽 4–8 m，中部不可避免地形成布置楼梯、辅助房间（常含就餐区）的暗区。

- **早期设计**：★★★ · LOD 100–200 · 决定平面进深
- **IFC**：`IfcBuilding` · 还需要：用途/人数（`IfcSpace.Name / LongName, Pset_SpaceOccupancyRequirements, 建筑类型`）
- **页码**：p.144 (page_0156) · Residential buildings
- **用到的题**（0 道，0 个模型）：
- **知识探针题**（一般 · recall）：In German (DIN-based) design practice: Terraced (row) houses can receive direct daylight only from two façades. What economic building depth (maximum) and what range of house widths typically apply to row houses, which make a badly lit middle zone (stairs, subsidiary rooms) unavoidable?
  - 标准答案：Depth up to 12 m; width 4–8 m
  - 选项：A. Depth up to 10 m; width 5–7 m；**B. Depth up to 12 m; width 4–8 m** ✓；C. Depth up to 15 m; width 6–10 m；D. Depth up to 12 m; width 8–12 m
- **原文**：
  - p.144：“Building in a row restricts the possibilities for direct lighting to two façades so that, with economic building depths of up to 12 m and widths between 4 and 8 m, the existence of a badly lit or dark middle zone containing the stairs, subsidiary rooms and often also the dining area becomes unavoidable.”

## 办公

### K116 建筑进深与采光深度

中廊式办公楼通常进深 12–13 m；自然采光大约能利用到 7.00 m 的房间进深。

- **早期设计**：★★★ · LOD 100–200 · 决定平面进深
- **IFC**：`IfcBuilding` · 还需要：用途/人数（`IfcSpace.Name / LongName, Pset_SpaceOccupancyRequirements, 建筑类型`）
- **页码**：p.240 (page_0252), p.241 (page_0253) · Administration and offices
- **用到的题**（5 道，4 个模型）：`ac20-09`, `digital_hub-08`, `digital_hub-16`, `office1-03`, `office3-04`
- **知识探针题**（一般 · recall）：In German (DIN-based) design practice: What is the usual building depth of office buildings with central corridors, and to about what room depth can daylight mostly be exploited?
  - 标准答案：12–13 m building depth; daylight to about 7.00 m room depth
  - 选项：A. 15–18 m; about 7.50 m；B. 10–11 m; about 5.00 m；C. 12–13 m; about 10.00 m；**D. 12–13 m; about 7.00 m** ✓
- **原文**：
  - p.240：“The usual depth of buildings with central corridors is 12–13 m.”
  - p.241：“Daylight can mostly be exploited into a room depth of about 7.00 m.”

### K131 装修网格与立面网格一致

装修（隔墙）网格与立面网格必须一致，隔墙才能接到窗上；结构网格可以与装修网格错开，这样减少隔墙与柱的连接问题，但有柱的房间会损失面积。因各类构件寿命不同，应选用可适应调整的模数。

- **早期设计**：★★★ · LOD 200 · 决定平面进深
- **IFC**：`IfcGrid`、`IfcWall`、`IfcWindow`
- **页码**：p.240 (page_0252) · Administration and offices
- **用到的题**（0 道，0 个模型）：
- **知识探针题**（须 · recall）：In German (DIN-based) office design practice: Which two planning grids of an office building must coincide so that partitions can connect to the windows, and which grid may be offset against them?
  - 标准答案：The fit-out (partition) grid and the façade grid must be the same; the structural grid can be offset against the fit-out grid
  - 选项：A. All three grids must always coincide；**B. Fit-out grid and façade grid must coincide; the structural grid may be offset** ✓；C. Structural grid and fit-out grid must coincide; the façade grid may be offset；D. Structural grid and façade grid must coincide; the fit-out grid may be offset
- **原文**：
  - p.240：“The fitting out and façade grids must be the same in order to enable the partitions to connect to the windows.”
  - p.240：“The structural grid can be offset against the fitting out grid. This reduces the problem of connecting the partitions to columns, but loses space in the rooms, which contain columns.”
  - p.240：“Because of the different lifecycles of the building elements, an adaptable module dimension should be chosen.”

### K132 网格模数与建筑进深的搭配

网格 1.35 m、建筑进深 13.40 m 是组合式办公的经济形式，但用于单间办公时房间过深、比例差；网格 1.50 m、建筑进深 12.50 m 对单间办公或组合式办公都经济，但公共区较窄，靠窗工位比前者少 10%。

- **早期设计**：★★★ · LOD 200 · 决定平面进深
- **IFC**：`IfcGrid`、`IfcBuilding` · 还需要：用途/人数（`IfcSpace.Name / LongName, Pset_SpaceOccupancyRequirements, 建筑类型`）
- **页码**：p.240 (page_0252) · Administration and offices
- **用到的题**（0 道，0 个模型）：
- **知识探针题**（宜 · recall）：In German (DIN-based) office design practice: What building depth goes with a 1.35 m grid module as the economical form for combi-offices, and what building depth goes with a 1.50 m grid module (economical for single offices or combi-offices)?
  - 标准答案：13.40 m with the 1.35 m module; 12.50 m with the 1.50 m module
  - 选项：A. 12.50 m and 13.40 m；**B. 13.40 m and 12.50 m** ✓；C. 15.00 m and 12.00 m；D. 11.00 m and 13.40 m
- **原文**：
  - p.240：“Grid module 1.35 m, building depth 13.40 m, an economical form of building for combi-offices, but for single offices this produces deep and badly proportioned rooms.”
  - p.240：“Grid module 1.50 m, building depth 12.50 m, an economical form of building for single offices or for combi-offices; this provides a narrow communal zone and 10% fewer workstations at the window than with ②.”

### K133 单排、双排与三排布局

单排布局不经济、不生态，只有办公室很深时才可接受；双排布局是行政办公楼至今最常用的形式，单间和小办公室都能有自然采光；三排布局（中部设大的服务核心区）通常只对高层建筑合适，其中部可用采光井自然采光。

- **早期设计**：★★★ · LOD 100–200 · 决定体量
- **IFC**：`IfcBuilding`、`IfcSpace` · 还需要：用途/人数（`IfcSpace.Name / LongName, Pset_SpaceOccupancyRequirements, 建筑类型`）
- **页码**：p.241 (page_0253) · Administration and offices
- **用到的题**（0 道，0 个模型）：
- **知识探针题**（宜 · recall）：In German (DIN-based) office design practice: Among single-row, two-row and three-row office layouts, which is described as normally practical only for high-rise buildings, and why?
  - 标准答案：The three-row layout with a large supply zone at the centre of the building, because of the greater proportion of vertical transport in high-rise buildings
  - 选项：A. The layout without corridor, because it saves circulation area；B. The two-row layout, because the cores sit in well-lit zones；**C. The three-row layout, because of the greater proportion of vertical transport** ✓；D. The single-row layout, because it gives every room daylight
- **原文**：
  - p.241：“Single-row layouts are unecological, and only acceptable with deep office rooms (daylight?)”
  - p.241：“Two-row layouts have mostly been used for administration buildings until now; single rooms and small offices are possible with daylight”
  - p.241：“A large supply zone at the centre of the building is normally practical only for high-rise buildings (greater proportion of vertical transport).”
  - p.241：“Lightwells can illuminate the centre of three-row buildings naturally”

### K139 可逆办公楼（出租办公）

可逆办公（Revibüro）其实不是一种办公室类型，而是一种建筑形式；适应性越高设备成本越高，办公室大小和组织上须接受折中；主要适合出租给尚未确定的租户。

- **早期设计**：★ · LOD 100–200
- **IFC**：`IfcBuilding` · 还需要：用途/人数（`IfcSpace.Name / LongName, Pset_SpaceOccupancyRequirements, 建筑类型`）
- **页码**：p.239 (page_0251) · Administration and offices
- **用到的题**（0 道，0 个模型）：
- **知识探针题**（descriptive · recall）：In German (DIN-based) office design practice: For what kind of occupier is a 'reversible office' building (Revibüro) mainly suitable?
  - 标准答案：Offices for renting to tenants who are not yet known
  - 选项：A. Public authorities with archive duties；B. A single owner-occupier with fixed staff numbers；**C. Offices let to tenants who are not yet known** ✓；D. Call centres with shift work
- **原文**：
  - p.239：“The cost of equipment rises with increasing adaptability and compromises have to be accepted concerning office sizes and organisation.”
  - p.239：“This type of building is mainly suitable for offices for renting to tenants who are not yet known”

### K141 每工位面积指标（直接工位与交通面积）

每个工位的平均毛面积指标：直接工位面积 11–15 m²（平均 13 m²），附加面积（洽谈、存放）1.5–4.2 m²（平均 2.5 m²），交通面积 2.2–6.0 m²（平均 4.5 m²）。

- **早期设计**：★★★ · LOD 100–200 · 决定面积核算
- **IFC**：`IfcBuilding`、`IfcSpace` · 还需要：用途/人数（`IfcSpace.Name / LongName, Pset_SpaceOccupancyRequirements, 建筑类型`）
- **页码**：p.238 (page_0250) · Administration and offices
- **用到的题**（0 道，0 个模型）：
- **知识探针题**（宜 · recall）：In German (DIN-based) office design practice: In the average gross space requirement per office workstation, what range (and average) is given for (a) the immediate workstation and (b) the traffic area?
  - 标准答案：(a) 11–15 m², average 13 m²; (b) 2.2–6.0 m², average 4.5 m²
  - 选项：A. 11–15 m² (avg. 13); 6.0–10.0 m² (avg. 8)；**B. 11–15 m² (avg. 13); 2.2–6.0 m² (avg. 4.5)** ✓；C. 8–10 m² (avg. 9); 1.0–2.0 m² (avg. 1.5)；D. 15–20 m² (avg. 18); 2.2–6.0 m² (avg. 4.5)
- **原文**：
  - p.238：“Workstation | Immediate workstation | 11–15 | 13 | 15.5”
  - p.238：“Additional area (consulting, storage) | 1.5–4.2 | 2.5”
  - p.238：“Traffic area | 2.2–6.0 | 4.5”

### K146 全空调对建筑体积的影响

全空调建筑的总建筑体积和总建造成本是无空调建筑的 1.3–1.5 倍。

- **早期设计**：★★ · LOD 100–200 · 决定体量
- **IFC**：`IfcBuilding` · 还需要：用途/人数（`IfcSpace.Name / LongName, Pset_SpaceOccupancyRequirements, 建筑类型`）
- **页码**：p.242 (page_0254) · Administration and offices
- **用到的题**（0 道，0 个模型）：
- **知识探针题**（descriptive · recall）：In German (DIN-based) office design practice: By what factor are the gross built volume and the total construction costs of a fully air-conditioned office building higher than for a building without air conditioning?
  - 标准答案：1.3–1.5 times
  - 选项：A. 2–3 times；B. 1.05–1.1 times；**C. 1.3–1.5 times** ✓；D. 1.8–2.0 times
- **原文**：
  - p.242：“The gross built volume and the total construction costs for air-conditioned buildings are 1.3–1.5 times higher than for buildings without air conditioning”

## 高层建筑

### K152 高层建筑的分级

高层建筑按距消防车停放面的高度分级：I 级 22–30 m，适用高层建筑规定；II 级 30–60 m，至少 1 部消防电梯；III 级 60–200 m，结构重要构件须为 F 120，并可要求多部消防电梯；IV 级 200 m 以上，审批机关可提出进一步要求。

- **早期设计**：★★ · LOD 100 · 决定体量
- **IFC**：`IfcBuilding`、`IfcBuildingStorey`
- **页码**：p.246 (page_0258) · Administration and offices
- **用到的题**（0 道，0 个模型）：
- **知识探针题**（须 · recall）：In the German classification of high-rise buildings by height above the fire service parking area, what height range is group II and what special requirement applies to it, and what must elements of structural significance achieve in group III (60–200 m)?
  - 标准答案：Group II: 30–60 m, at least 1 fire service lift; group III: elements of structural significance must be F 120
  - 选项：A. 22–30 m, sprinklers; F 90；B. 60–100 m, at least 1 fire service lift; F 120；**C. 30–60 m, at least 1 fire service lift; F 120** ✓；D. 30–60 m, two safety stairs; F 180
- **原文**：
  - p.246：“I | 22–30 m | high-rise regulations apply”
  - p.246：“II | 30–60 m | at least 1 fire service lift”
  - p.246：“III | 60–200 m | elements of structural significance must be F 120 and many fire service lifts can be required”
  - p.246：“IV | over 200 m | the approval authority can place further requirements”

### K153 高层建筑的用途限制

在德国，按现行法规高层建筑不得用作学校、医院或养老院。

- **早期设计**：★ · LOD 100
- **IFC**：`IfcBuilding` · 还需要：用途/人数（`IfcSpace.Name / LongName, Pset_SpaceOccupancyRequirements, 建筑类型`）
- **页码**：p.244 (page_0256) · Administration and offices
- **用到的题**（0 道，0 个模型）：
- **知识探针题**（须 · recall）：In Germany, which uses are ruled out for high-rise buildings by the applicable regulations?
  - 标准答案：Schools, hospitals and homes for elderly people
  - 选项：**A. Schools, hospitals and homes for elderly people** ✓；B. Car parks, laboratories and archives；C. Shops, restaurants and cinemas；D. Hotels, apartments and offices
- **原文**：
  - p.244：“In Germany, use as schools, hospitals or homes for elderly people is ruled out by the applicable regulations.”

# Storey

楼层与竖向：层数、层高、净高，以及连接各层的楼梯、坡道、电梯、护栏

## 楼梯、坡道、电梯与护栏

### K07 舒适步距公式

踏步高 r 与踏面宽 t 应满足 2r + t = 59–65 cm（成人步距）。

- **早期设计**：★★★ · LOD 300 · 决定交通核
- **IFC**：`IfcStairFlight` · 还需要：性能属性（`Pset_*Common（FireRating, ThermalTransmittance, AcousticRating, IsExternal …）`）
- **页码**：p.121 (page_0133) · Building components
- **用到的题**（12 道，9 个模型）：`ac20-08`, `digital_hub-07`, `hotel1-02`, `hotel1-03`, `office1-01`, `office2-08`, `office2-11`, `office3-01`, `frb1-02`, `fzk_house-04`, `samuel-01`, `samuel-02`
- **知识探针题**（宜 · recall）：In German (DIN-based) design practice: For a comfortable stair with the lowest energy requirement, a standard design rule combines riser height r and tread depth t, based on the stride length of an adult. Within what range should 2r + t lie?
  - 标准答案：59–65 cm
  - 选项：A. 54–58 cm；B. 66–72 cm；**C. 59–65 cm** ✓；D. 45–50 cm
- **原文**：
  - p.121：“In order to determine a suitable pitch with the lowest energy requirement, this formula applies: 2 r + t = 59–65 cm.”

### K08 最佳坡度与踏步比

最省力的是 30° 坡度、踏步比 17/29。

- **早期设计**：★★ · LOD 300
- **IFC**：`IfcStairFlight` · 还需要：性能属性（`Pset_*Common（FireRating, ThermalTransmittance, AcousticRating, IsExternal …）`）
- **页码**：p.121 (page_0133) · Building components
- **用到的题**（3 道，3 个模型）：`hotel1-02`, `fzk_house-04`, `samuel-02`
- **知识探针题**（一般 · recall）：In German (DIN-based) design practice: From a physiological point of view, at what stair pitch and what riser-to-tread ratio (r/t, in cm) is 'climbing effort' generally considered to be used best?
  - 标准答案：30° pitch, riser/tread 17/29
  - 选项：**A. 30°, 17/29** ✓；B. 35°, 19/26；C. 25°, 15/32；D. 40°, 20/24
- **原文**：
  - p.121：“the best use of 'climbing effort' is at a stair pitch of 30° and a ratio of riser (r) to tread (t) of 17/29.”

### K09 每段梯段步数

必要楼梯每段 3–18 步；18 步上限是“应当”性规定。

- **早期设计**：★★★ · LOD 200–300 · 决定交通核
- **IFC**：`IfcStairFlight` · 还需要：性能属性（`Pset_*Common（FireRating, ThermalTransmittance, AcousticRating, IsExternal …）`）
- **页码**：p.120 (page_0132) · Building components
- **用到的题**（11 道，9 个模型）：`ac20-08`, `digital_hub-07`, `hotel1-02`, `hotel1-03`, `office1-01`, `office2-08`, `office3-01`, `frb1-02`, `fzk_house-04`, `samuel-01`, `samuel-02`
- **知识探针题**（宜 · recall）：Under German stair rules, what is the permitted range for the number of steps in one run (flight) of a legally essential stair (one required as a fire escape route)?
  - 标准答案：At least 3 and at most 18 steps per run (the 18-step limit is a 'should' rule)
  - 选项：A. 2 to 20 steps；B. 3 to 15 steps；C. 4 to 16 steps；**D. 3 to 18 steps** ✓
- **原文**：
  - p.120：“Length of runs on legally essential stairs is \( \geq 3 \) steps up to \( \leq 18 \) steps”
  - p.120：“The 18-step rule is a 'should' regulation.”

### K10 休息平台

层高 ≥ 2.75 m 的必要楼梯必须设休息平台；平台长度 = n × 步距 + 1 个踏面。

- **早期设计**：★★★ · LOD 200–300 · 决定交通核
- **IFC**：`IfcStair`、`IfcStairFlight`、`IfcBuildingStorey`
- **页码**：p.120 (page_0132), p.121 (page_0133) · Building components
- **用到的题**（12 道，9 个模型）：`ac20-08`, `digital_hub-07`, `digital_hub-24`, `hotel1-02`, `hotel1-03`, `office1-01`, `office2-08`, `office3-01`, `office3-15`, `frb1-02`, `fzk_house-04`, `samuel-01`
- **知识探针题**（须 · recall）：Under German stair rules, from what storey height onwards must a legally essential stairway be provided with a landing (i.e. not be a single uninterrupted flight)?
  - 标准答案：Storey height ≥ 2.75 m
  - 选项：A. ≥ 2.50 m；**B. ≥ 2.75 m** ✓；C. ≥ 3.00 m；D. ≥ 3.50 m
- **原文**：
  - p.120：“landing length = \( n \) times length of stride + 1 depth of tread”
  - p.121：“Stairs with landings are required in legally essential stairways with a storey height of \( \geq 2.75 \) m.”

### K11 必要楼梯宽度与踏步比

按德国标准（住宅建筑），法定必要楼梯（作为疏散路线）的可用梯宽至少 1.00 m、踏步比 17/28；对比：不超过两户的住宅楼梯可用宽度至少 0.80 m（17/28），非必要楼梯 0.50 m（21/21），高层住宅 1.25 m。

- **早期设计**：★★★ · LOD 200–300 · 决定交通核
- **IFC**：`IfcStair`、`IfcStairFlight` · 还需要：用途/人数（`IfcSpace.Name / LongName, Pset_SpaceOccupancyRequirements, 建筑类型`）
- **页码**：p.120 (page_0132) · Building components
- **用到的题**（7 道，7 个模型）：`ac20-08`, `digital_hub-07`, `hotel1-03`, `office1-01`, `office2-08`, `office3-01`, `frb1-02`
- **知识探针题**（须 · recall）：According to German standards, what minimum usable stair width and riser/tread ratio apply to legally essential stairs (fire escape routes) in residential buildings that are neither houses with at most two flats nor high-rise flats?
  - 标准答案：1.00 m usable width, riser/tread 17/28
  - 选项：A. 0.80 m, 17/28；B. 1.25 m, 17/29；C. 0.90 m, 18/26；**D. 1.00 m, 17/28** ✓
- **原文**：
  - p.120：“legally essential stairs 1.00 m, 17/28”
  - p.120：“Stair width in public buildings is calculated according to the required evacuation time”

### K12 两户以下住宅的楼梯

按德国标准，不超过两户的住宅，楼梯须满足可用宽度至少 0.80 m、踏步比（踢面/踏面）17/28；（同段：非法定必要楼梯可为 0.50 m、21/21，其他法定必要楼梯 1.00 m、17/28，高层住宅 1.25 m）。

- **早期设计**：★★★ · LOD 300 · 决定交通核
- **IFC**：`IfcStair`、`IfcStairFlight` · 还需要：用途/人数（`IfcSpace.Name / LongName, Pset_SpaceOccupancyRequirements, 建筑类型`）
- **页码**：p.120 (page_0132) · Building components
- **用到的题**（1 道，1 个模型）：`samuel-01`
- **知识探针题**（须 · recall）：According to German standards, what minimum usable stair width and riser/tread ratio must stairs have in residential buildings with no more than two flats?
  - 标准答案：0.80 m usable width, riser/tread 17/28
  - 选项：**A. 0.80 m, 17/28** ✓；B. 1.00 m, 17/28；C. 0.50 m, 21/21；D. 0.90 m, 17/29
- **原文**：
  - p.120：“residential buildings with no more than two flats must have a usable stair width min. 0.80 m, 17/28 riser to tread ratio”

### K13 室外楼梯与办公楼梯的取向

室外楼梯宜用低踏步（12×41 至 16×30 cm）；办公楼梯和疏散楼梯应便于快速通行。

- **早期设计**：★ · LOD 300
- **IFC**：`IfcStair` · 还需要：用途/人数（`IfcSpace.Name / LongName, Pset_SpaceOccupancyRequirements, 建筑类型`）
- **页码**：p.121 (page_0133) · Building components
- **用到的题**（1 道，1 个模型）：`ac20-08`
- **知识探针题**（宜 · recall）：In German (DIN-based) design practice: Low steps are generally recommended for outside stairs. What range of step dimensions (riser × tread) is considered preferable for outside stairs?
  - 标准答案：From 12 × 41 cm to 16 × 30 cm
  - 选项：A. 15 × 35 cm to 17 × 29 cm；**B. 12 × 41 cm to 16 × 30 cm** ✓；C. 10 × 45 cm to 14 × 38 cm；D. 16 × 30 cm to 18 × 26 cm
- **原文**：
  - p.121：“For outside stairs, low steps are preferable, with dimensions of 12 × 41 to 16 × 30 cm.”
  - p.121：“Stairs in offices or emergency stairs should, in contrast, make it possible to change level quickly.”

### K14 螺旋楼梯

螺旋楼梯作为住宅内唯一的连接楼梯，直径 ≥ 190 cm、可用宽度 80 cm。

- **早期设计**：★★ · LOD 300
- **IFC**：`IfcStair`
- **页码**：p.124 (page_0136) · Building components
- **用到的题**（1 道，1 个模型）：`fzk_house-04`
- **知识探针题**（须 · recall）：In German (DIN-based) stair design guidance, what minimum diameter must a spiral staircase have to be permissible as the sole connecting stair inside a house, and what usable walking width is associated with it?
  - 标准答案：Diameter from 190 cm, with 80 cm usable walking width
  - 选项：A. 140 cm, 60 cm；B. 160 cm, 70 cm；**C. 190 cm, 80 cm** ✓；D. 220 cm, 90 cm
- **原文**：
  - p.124：“Spiral staircases are permissible from 190 cm in diameter as the sole connecting stairs inside houses with 80 cm usable walking width”

### K15 楼座、夹层、阳台的护栏高度

楼座、夹层、阳台及剧院楼座看台须设护栏（高 h），高差 ≥ 1 m 起强制：坠落高度 < 12 m 时 h = 0.90 m；坠落高度 > 12 m 时 h = 1.10 m；工作场所坠落高度 < 12 m 时 h = 1.00 m，且楼梯井宽至少 20 cm 时，坠落高度超过 12 m 也为 1.00 m（同一正文条目所述）。

- **早期设计**：★★★ · LOD 300 · 决定安全
- **IFC**：`IfcRailing`
- **页码**：p.122 (page_0134) · Building components
- **用到的题**（5 道，4 个模型）：`office2-01`, `frb1-03`, `fzk_house-12`, `samuel-07`, `samuel-13`
- **知识探针题**（须 · recall）：Under German (DIN-based) building guidance, galleries, mezzanines and balconies must have a protective guard rail once the height difference reaches a certain value. For a non-workplace building, what guard rail height h is required (a) for a drop of less than 12 m and (b) for a drop of more than 12 m?
  - 标准答案：(a) 0.90 m; (b) 1.10 m
  - 选项：**A. 0.90 m / 1.10 m** ✓；B. 1.00 m / 1.20 m；C. 0.80 m / 1.00 m；D. 1.10 m / 1.30 m
- **原文**：
  - p.122：“Galleries, mezzanines, balconies and circle seating in theatres must have a protective guard rail (height h), compulsory from 1 m height difference:”
  - p.122：“drop <12 m, h = 0.90 m”
  - p.122：“drop <12 m, h = 1.00 m for workplaces”
  - p.122：“drop >12 m, h = 1.10 m”

### K16 无障碍坡道

坡道坡度 ≤ 6%、净宽 ≥ 1.20 m、两侧设扶手；起点、终点及每 6 m 设长度 ≥ 1.50 m 的平台（坡道长于 6 m 须设中间平台）。

- **早期设计**：★★★ · LOD 200–300 · 决定无障碍
- **IFC**：`IfcRamp`、`IfcRailing` · 还需要：电梯/坡道（`IfcTransportElement / IfcRamp`）
- **页码**：p.22 (page_0034), p.25 (page_0037) · Basics
- **用到的题**（1 道，1 个模型）：`samuel-17`
- **知识探针题**（须 · recall）：For barrier-free design under German regulations, what are (a) the maximum slope of a ramp, (b) its minimum clear width, and (c) the ramp length beyond which an intermediate landing is required?
  - 标准答案：(a) 6%; (b) 1.20 m; (c) 6 m
  - 选项：A. 8%; 1.20 m; 10 m；B. 6%; 0.90 m; 10 m；C. 5%; 1.50 m; 6 m；**D. 6%; 1.20 m; 6 m** ✓
- **原文**：
  - p.22：“If ramps are longer than 6 m, an intermediate landing of min. 1.50 m length is required.”
  - p.22：“The clear ramp width must be min. 1.20 m.”
  - p.25：“Ramps may not have a slope of more than 6%, must be at least 1.20 m wide and have a fixed handrail with a safe grip on both sides.”
  - p.25：“A landing is to be provided at the start and end of the ramp and also an intermediate landing every 6 m. The landings must have a length of at least 1.50 m.”

### K17 公共建筑楼梯两侧扶手

按 MBO §50，公众可达建筑的楼梯须两侧设扶手，扶手应在休息平台和窗洞处连续，并延伸过最后一级踏步。

- **早期设计**：★ · LOD 350
- **IFC**：`IfcStair`、`IfcRailing` · 还需要：用途/人数（`IfcSpace.Name / LongName, Pset_SpaceOccupancyRequirements, 建筑类型`）
- **页码**：p.25 (page_0037) · Basics
- **用到的题**（0 道，0 个模型）：
- **知识探针题**（须 · recall）：Under the German model building regulations (MBO) provisions for publicly accessible buildings, on how many sides must stairs have handrails, and how must the handrails run at landings, window openings and the last step?
  - 标准答案：On both sides, continued past landings and window openings and past the last steps
  - 选项：A. One side; continued past landings, window openings and the last steps；B. Both sides; interrupted at landings and window openings, ending at the last step；**C. Both sides; continued past landings, window openings and the last steps** ✓；D. Both sides; interrupted at window openings, ending flush with the last step
- **原文**：
  - p.25：“Stairs must have handrails on both sides, which are to be continued past landings and window openings and past the last steps.”

### K18 电梯候梯区

候梯（排队）空间不得占用楼梯；单台电梯前候梯区自井道门墙至对面墙的最小可用进深（沿轿厢进深方向量）应等于轿厢进深，最小可用面积应等于轿厢进深 × 井道宽度；无障碍电梯门前活动区不得与其他交通路线和活动区重叠。

- **早期设计**：★★ · LOD 200
- **IFC**：`IfcTransportElement`、`IfcSpace` · 还需要：电梯/坡道（`IfcTransportElement / IfcRamp`）
- **页码**：p.22 (page_0034), p.128 (page_0140), p.130 (page_0142) · Basics / Building components
- **用到的题**（2 道，2 个模型）：`digital_hub-11`, `office3-09`
- **知识探针题**（宜 · recall）：According to German (DIN-based) lift planning guidance, what minimum usable depth should the waiting area in front of a single lift have, measured between the shaft door wall and the opposite wall in the direction of the car depth?
  - 标准答案：Equal to the lift car depth
  - 选项：A. Equal to the lift car width；B. Twice the lift car depth；**C. Equal to the lift car depth** ✓；D. 1.20 m regardless of car size
- **原文**：
  - p.22：“This area must not overlap with other traffic routes and movement areas.”
  - p.128：“Provide sufficient space for waiting and queuing → p. 130 which must not infringe on stairs.”
  - p.130：“minimum usable depth between shaft door wall and opposing wall, measured in the direction of the depth of the car, should equal the car depth”

### K19 非必要楼梯

按德国标准（书中在“不超过两户的住宅”一句中列出）：建筑法规不视为必要楼梯（不作为法定疏散路线）的楼梯，可用宽度（最小）0.50 m，踏步比 21/21；相比之下必要楼梯为 1.00 m、17/28。

- **早期设计**：★ · LOD 300
- **IFC**：`IfcStair`、`IfcStairFlight` · 还需要：用途/人数（`IfcSpace.Name / LongName, Pset_SpaceOccupancyRequirements, 建筑类型`）
- **页码**：p.120 (page_0132) · Building components
- **用到的题**（1 道，1 个模型）：`office2-11`
- **知识探针题**（须 · recall）：According to German standards, what minimum usable width and riser/tread ratio apply to stairs that building regulations do not deem legally essential (i.e. not fire escape routes)?
  - 标准答案：0.50 m usable width, riser/tread 21/21
  - 选项：**A. 0.50 m, 21/21** ✓；B. 0.60 m, 20/23；C. 0.80 m, 17/28；D. 0.50 m, 19/25
- **原文**：
  - p.120：“stairs not deemed by building regulations to be legally essential (as fire escape routes) 0.50 m, 21/21”

### K20 休息平台宽度不小于梯段宽度

楼梯休息平台宽度不小于楼梯宽度；（同一图注）层高 ≥ 2.75 m 的法定必要楼梯须设休息平台。

- **早期设计**：★★★ · LOD 300 · 决定交通核
- **IFC**：`IfcStairFlight`、`IfcSlab`
- **页码**：p.121 (page_0133) · Building components
- **用到的题**（2 道，2 个模型）：`digital_hub-24`, `office3-15`
- **知识探针题**（须 · recall）：In German stair design rules, how must the width of a stair landing relate to the stair (flight) width?
  - 标准答案：Landing width must be at least equal to the stair width (landing width ≥ stair width)
  - 选项：A. At least 1.5 times the stair width；**B. At least equal to the stair width** ✓；C. May be up to 20% narrower than the stair；D. At least the stair width plus 0.30 m
- **原文**：
  - p.121：“Landing width \( \geq \) stair width.”

## 无障碍

### K27 无障碍：无台阶通达与公众可达建筑的适用范围

按无障碍原则设计的建筑，所有楼层须无台阶可达（即通过电梯或坡道）。另按 MBO §50，公众可达建筑面向公众的部分须能供残障人士、老人和带小孩的人无需他人帮助按用途进出使用，尤其适用于文化、教育、体育、休闲和医疗设施，办公、行政建筑和法院，商业和餐饮场所，停车场、车库和厕所。

- **早期设计**：★★★ · LOD 200 · 决定无障碍
- **IFC**：`IfcBuildingStorey`、`IfcTransportElement`、`IfcRamp` · 还需要：电梯/坡道（`IfcTransportElement / IfcRamp`）；用途/人数（`IfcSpace.Name / LongName, Pset_SpaceOccupancyRequirements, 建筑类型`）
- **页码**：p.22 (page_0034), p.25 (page_0037) · Basics
- **用到的题**（9 道，4 个模型）：`ac20-03`, `ac20-10`, `ac20-13`, `digital_hub-01`, `digital_hub-03`, `digital_hub-05`, `office1-06`, `office1-09`, `office3-10`
- **知识探针题**（须 · recall）：For buildings designed in accordance with the principles of accessibility (barrier-free design per German guidance), how must the building's levels be reachable?
  - 标准答案：All levels must be accessible without steps, i.e. by lift or ramp
  - 选项：A. Only the entrance level needs step-free access；**B. All levels must be accessible without steps (lift or ramp)** ✓；C. Upper levels may be reached by stairs with handrails on both sides；D. Upper levels must be reachable by a stair lift
- **原文**：
  - p.22：“All levels of buildings designed in accordance with the principles of accessibility must be accessible without steps, i.e. using a lift or a ramp.”
  - p.25：“This requirement applies notably to cultural, educational, sport, leisure and health facilities, offices, administration buildings and courts, sales and catering establishments, parking, garages and toilets.”
  - p.25：“This requirement applies notably to cultural, educational, sport, leisure and health facilities, offices, administration buildings and courts”

### K30 无障碍电梯

无障碍建筑中，电梯轿厢净宽须 ≥ 1.10 m、净深 ≥ 1.40 m；门前活动区须至少与轿厢地面面积相同，且不小于 1.50 m 宽 × 1.50 m 深，并不得与其他交通路线和活动区重叠。

- **早期设计**：★★★ · LOD 200 · 决定无障碍
- **IFC**：`IfcTransportElement`、`IfcSpace` · 还需要：电梯/坡道（`IfcTransportElement / IfcRamp`）
- **页码**：p.22 (page_0034) · Basics
- **用到的题**（3 道，2 个模型）：`digital_hub-05`, `digital_hub-11`, `office3-09`
- **知识探针题**（须 · recall）：In barrier-free design per German guidance, what minimum clear internal dimensions (width × depth) must a lift car have?
  - 标准答案：1.10 m wide × 1.40 m deep
  - 选项：A. 1.00 m × 1.25 m；B. 0.90 m × 1.20 m；C. 1.10 m × 2.10 m；**D. 1.10 m × 1.40 m** ✓
- **原文**：
  - p.22：“Cars of lifts must have a min. clear width of 1.10 m and a clear depth of 1.40 m.”
  - p.22：“The movement area in front of the doors must be as large as the floor area of the car, but min. 1.50 m wide and 1.50 m deep”

### K32 楼梯起止处活动区

无障碍公共建筑中，上下楼梯旁的活动区宽度至少 1.50 m，首级踏步的踏面不计入活动区。

- **早期设计**：★★ · LOD 200
- **IFC**：`IfcStair`、`IfcSpace`
- **页码**：p.22 (page_0034) · Basics
- **用到的题**（1 道，1 个模型）：`digital_hub-11`
- **知识探针题**（须 · recall）：In barrier-free design per German guidance, what minimum width must the movement area next to the top and bottom of stairs have, and is the tread of the first step counted as part of it?
  - 标准答案：Min. 1.50 m wide; the tread of the first step is not included
  - 选项：A. 1.20 m; first tread counted；**B. 1.50 m; first tread not counted** ✓；C. 1.80 m; first tread not counted；D. 1.50 m; first tread counted
- **原文**：
  - p.22：“The movement area next to the stairs going up and down must be min. 1.50 m wide; the tread of the first step is not to be included in the calculation of the movement area”

## 疏散与防火

### K43 主楼梯须设在连续封闭的楼梯间

主楼梯须设在连续封闭的楼梯间内，连同其通道和通向室外的出口都须能安全用于疏散。

- **早期设计**：★★★ · LOD 200 · 决定疏散
- **IFC**：`IfcStair`、`IfcSpace` · 还需要：相邻/围合（`IfcRelSpaceBoundary`）
- **页码**：p.121 (page_0133) · Building components
- **用到的题**（2 道，2 个模型）：`digital_hub-13`, `hotel1-12`
- **知识探针题**（须 · recall）：Under German building regulations for stairs, how must all main staircases be enclosed?
  - 标准答案：In a continuous (enclosed) stairwell which, including its access routes and exit to the open air, can safely be used for escape
  - 选项：A. In a stairwell enclosed only above the ground floor, opening freely into the entrance hall；**B. In a continuous stairwell that, with its access routes and exit to the open air, can safely be used for escape** ✓；C. In a stairwell enclosed on the lowest storeys only, the upper flights may be open galleries；D. No enclosure is needed if the whole building is fitted with a sprinkler system
- **原文**：
  - p.121：“All main staircases must be enclosed in a continuous stairwell, which is designed and arranged so that, including its access routes and exit to the open air, it can safely be used for escape.”

## 住宅·户型组织与入户

### K83 电梯与每层户数

超过五个完整楼层的住宅须设电梯；一梯两户是最常见的交通组织方式。

- **早期设计**：★★★ · LOD 100–200 · 决定体量
- **IFC**：`IfcBuildingStorey`、`IfcTransportElement` · 还需要：电梯/坡道（`IfcTransportElement / IfcRamp`）；房间分组（`IfcZone / IfcSpatialZone`）
- **页码**：p.142 (page_0154) · Residential buildings
- **intent**：`page_0154_intent_006`, `page_0154_intent_009`
- **用到的题**（2 道，1 个模型）：`frb1-06`, `frb1-21`
- **知识探针题**（须 · recall）：Under German building regulations, residential buildings with more than how many full floors require lifts?
  - 标准答案：More than five full floors
  - 选项：A. More than three；B. More than four；C. More than six；**D. More than five** ✓
- **原文**：
  - p.142：“Lifts are required for residential buildings of more than five full floors”
  - p.142：“Two flats per floor is the most common access method, with balanced advantages of residential quality and value for money.”

### K91 一梯一户限四层（无电梯）；一梯三户

一梯一户交通面积占比高、较不经济（“叠摞的联排”/城市别墅），不设电梯时一般限四层；一梯三户兼顾居住品质与经济性。

- **早期设计**：★★★ · LOD 100–200 · 决定交通核
- **IFC**：`IfcBuildingStorey`、`IfcStair` · 还需要：房间分组（`IfcZone / IfcSpatialZone`）
- **页码**：p.142 (page_0154) · Residential buildings
- **intent**：`page_0154_intent_001`, `page_0154_intent_008`
- **用到的题**（1 道，1 个模型）：`frb1-21`
- **知识探针题**（一般 · recall）：In German (DIN-based) design practice: Among the access types for multi-storey apartment buildings, the type with access to only one flat on each floor (sometimes marketed as 'town villas') is generally limited to how many floors when no lift is provided?
  - 标准答案：4 floors
  - 选项：A. 3 floors；B. 5 floors；**C. 4 floors** ✓；D. 6 floors
- **原文**：
  - p.142：“There is access to only one flat on each floor. This is relatively uneconomic due to the high proportion of the total floor area taken up for access, but can often give the feeling of living in a 'stacked terrace'. The flats are also marketed as town villas. There is a general limitation to four floors without a lift.”
  - p.142：“Three flats per floor offers a favourable combination of residential quality and value for money.”

## 办公

### K112 办公楼室内净高

办公楼（按 Vst 规定）室内净高 2.75 m（便于日后加设架空地板和较深吊顶）；以坐姿工作为主时可降低 25 cm，但净高不低于 2.50 m；走廊和卫生设施允许为 2.30 m。（另：工业与工商建筑一章给出面积大于 100 m² 的工作间净高参考值 3.00 m。）

- **早期设计**：★★★ · LOD 200 · 决定体量
- **IFC**：`IfcBuildingStorey`、`IfcSpace` · 还需要：用途/人数（`IfcSpace.Name / LongName, Pset_SpaceOccupancyRequirements, 建筑类型`）
- **页码**：p.243 (page_0255), p.266 (page_0278) · Administration and offices / Industry and trade
- **用到的题**（5 道，4 个模型）：`ac20-01`, `ac20-07`, `digital_hub-02`, `office2-02`, `office3-02`
- **知识探针题**（须 · recall）：For office buildings, under the German Vst workplace regulation on room heights: what ceiling height is given for office rooms, what minimum clear height remains if the height is reduced for predominantly sedentary activities, and what height is permitted for corridors and sanitary facilities?
  - 标准答案：2.75 m; min. 2.50 m clear; 2.30 m
  - 选项：**A. 2.75 m; min. 2.50 m; 2.30 m** ✓；B. 3.00 m; min. 2.75 m; 2.50 m；C. 2.50 m; min. 2.40 m; 2.20 m；D. 2.75 m; min. 2.50 m; 2.10 m
- **原文**：
  - p.243：“Ceiling height 2.75 m according to Vst regulation (enables the later installation of raised floor and deeper suspended ceilings).”
  - p.243：“For predominantly sedentary activities, the reduction of the ceiling height by 25 cm is possible, but min. 2.50 m clear.”
  - p.243：“Corridors and sanitary facilities are permitted to be 2.30 m high (this can be exploited for installation runs).”
  - p.243：“Corridors and sanitary facilities are permitted to be 2.30 m high”
  - p.266：“guideline 3.00 m for working rooms larger than 100 m^2).”

### K134 楼梯间的间距（30 m / 60 m）

按 MBO 2002，使用房间内任一点到楼梯的距离须 ≤ 35 m；实践中由此得出楼梯间距建筑端部约 30 m、楼梯间彼此间距约 60 m（须注意各州 LBO 的不同规定）。卫生间、楼梯间、电梯井等固定点按建筑法规规定的最大间距布置。

- **早期设计**：★★★ · LOD 100–200 · 决定交通核
- **IFC**：`IfcStair`、`IfcSpace` · 还需要：相邻/围合（`IfcRelSpaceBoundary`）
- **页码**：p.241 (page_0253) · Administration and offices
- **用到的题**（0 道，0 个模型）：
- **知识探针题**（须 · recall）：Under the German model building code (MBO 2002), every point in an occupied room must be within 35 m of a staircase. In office buildings, what spacing of the staircases does this lead to in practice (a) from the end of the building and (b) from each other?
  - 标准答案：(a) about 30 m from the end of the building; (b) about 60 m from each other
  - 选项：A. 25 m; 50 m；B. 35 m; 70 m；**C. 30 m; 60 m** ✓；D. 20 m; 40 m
- **原文**：
  - p.241：“According to MBO 2002, every point in an occupied room must be \( \leq 35 \) m from a staircase.”
  - p.241：“This in practice leads to a spacing of the staircases from the end of the building of 30 m and from each other of 60 m”
  - p.241：“Fixed points are sanitary facilities, stairwells, lift shafts etc., situated at maximum spacings defined in the building regulations”

## 高层建筑

### K149 消防电梯（高度超过 30 m）

高度超过 30 m 的高层建筑须至少设一部位于独立井道内的消防电梯，从它出发在 50 m 半径内须能到达使用房间的每一点；须设带消火栓的前室，其大小应能把担架运进电梯；通道须至少为 T 30 阻火。

- **早期设计**：★★★ · LOD 100–200 · 决定交通核
- **IFC**：`IfcTransportElement`、`IfcBuilding` · 还需要：电梯/坡道（`IfcTransportElement / IfcRamp`）
- **页码**：p.246 (page_0258) · Administration and offices
- **用到的题**（0 道，0 个模型）：
- **知识探针题**（须 · recall）：Under the German high-rise building guideline: above what building height is at least one fire service lift in its own shaft required, and within what radius must it reach every point of an occupied room?
  - 标准答案：More than 30 m; within a radius of 50 m
  - 选项：**A. > 30 m; 50 m** ✓；B. > 22 m; 35 m；C. > 30 m; 25 m；D. > 60 m; 50 m
- **原文**：
  - p.246：“In high-rise buildings more than 30 m high, there must be at least one fire service lift in its own shaft, from where every point of an occupied room can be reached within a radius of 50 m.”
  - p.246：“It must have an anteroom with a hydrant, which is large enough to enable the transport of stretchers to the lift. Access routes must be at least T 30 fire-retarding.”

### K150 高层疏散楼梯的梯井、排烟与出口

高层建筑疏散楼梯的梯井须至少 0.80 m 宽（避免在楼梯上铺设水带）；最高处须设排烟口（楼面面积的 5%，但不小于 1 m²）；出口须直通室外，或经过无火灾荷载的门厅。

- **早期设计**：★★ · LOD 200–300 · 决定疏散
- **IFC**：`IfcStair`、`IfcSpace` · 还需要：用途/人数（`IfcSpace.Name / LongName, Pset_SpaceOccupancyRequirements, 建筑类型`）
- **页码**：p.246 (page_0258) · Administration and offices
- **用到的题**（0 道，0 个模型）：
- **知识探针题**（须 · recall）：Under the German high-rise building guideline: what minimum width must the wellhole of an emergency stair have, and what size of smoke outlet is required at its highest point?
  - 标准答案：Wellhole min. 0.80 m wide; smoke outlet 5% of the floor area but at least 1 m²
  - 选项：A. 0.20 m; 5% of the floor area, min. 1 m²；B. 1.25 m; 10% of the floor area, min. 2 m²；C. 0.80 m; 1% of the floor area, min. 0.5 m²；**D. 0.80 m; 5% of the floor area, min. 1 m²** ✓
- **原文**：
  - p.246：“The wellhole must be min. 0.80 m wide in order to avoid having to lay hoses on the stairs.”
  - p.246：“Smoke outlets must be provided at their highest point (5% of the floor area but min. 1 m^2).”
  - p.246：“The exit must be directly into the open air or through a lobby without any fire load.”

### K151 高层电梯分组

约 25 层以下通常设一组电梯，所有电梯服务所有楼层；需要超过 6 部电梯时应分成两组。

- **早期设计**：★★ · LOD 100–200 · 决定交通核
- **IFC**：`IfcTransportElement`、`IfcBuildingStorey` · 还需要：电梯/坡道（`IfcTransportElement / IfcRamp`）
- **页码**：p.246 (page_0258) · Administration and offices
- **用到的题**（0 道，0 个模型）：
- **知识探针题**（宜 · recall）：In high-rise building design practice: up to about how many storeys is one group of lifts serving all floors usual, and above how many lifts should they be divided into two groups?
  - 标准答案：Up to about 25 storeys; more than 6 lifts
  - 选项：**A. About 25 storeys; more than 6 lifts** ✓；B. About 40 storeys; more than 8 lifts；C. About 10 storeys; more than 3 lifts；D. About 25 storeys; more than 12 lifts
- **原文**：
  - p.246：“Up to about 25 storeys, it is usual to provide one group of lifts with all lifts serving all floors. If more than 6 lifts are necessary, they should be divided into two groups.”

# Zone

分区：一组房间构成的单元（一套住宅、防火分区、疏散路线、办公使用单元）

## 无障碍

### K34 多户住宅的无障碍楼层

超过两户的住宅，须有一层的住户无障碍可达，其起居室、卧室、一个厕所、一个浴室和厨房须可供轮椅使用。

- **早期设计**：★★ · LOD 200
- **IFC**：`IfcZone`、`IfcSpace` · 还需要：房间分组（`IfcZone / IfcSpatialZone`）；用途/人数（`IfcSpace.Name / LongName, Pset_SpaceOccupancyRequirements, 建筑类型`）
- **页码**：p.25 (page_0037) · Basics
- **用到的题**（2 道，1 个模型）：`frb1-07`, `frb1-17`
- **知识探针题**（须 · recall）：Under the German model building regulations (MBO), what accessibility requirement applies to residential buildings with more than two flats?
  - 标准答案：The flats on one floor must be accessible (barrier-free); in them living rooms, bedrooms, one toilet, one bathroom and the kitchen must be wheelchair accessible
  - 选项：A. All flats on every floor must be accessible, with every room wheelchair-usable；B. At least 10% of the flats must be accessible, with every room wheelchair-usable；**C. Flats on one floor must be accessible, with living rooms, bedrooms, a WC, a bathroom and the kitchen wheelchair-usable** ✓；D. Flats on one floor must have a step-free entrance, but no room inside need be wheelchair-usable
- **原文**：
  - p.25：“In buildings with more than two flats, the flats on one floor must be accessible.”
  - p.25：“In buildings with more than two flats, the flats on one floor must be accessible. In these flats, the living rooms and bedrooms, one toilet, one bathroom and the kitchen or kitchenette must be accessible with a wheelchair.”

## 疏散与防火

### K38 疏散距离

居室和地下室内任一点到必要楼梯或出口 ≤ 35 m。

- **早期设计**：★★★ · LOD 200 · 决定疏散
- **IFC**：`IfcSpace`、`IfcStair`、`IfcDoor` · 还需要：相邻/围合（`IfcRelSpaceBoundary`）
- **页码**：p.121 (page_0133) · Building components
- **用到的题**（0 道，0 个模型）：
- **知识探针题**（须 · recall）：Under the German building rules for normal (non-high-rise) buildings, what is the maximum distance from every location in inhabited rooms and basements to the stairwell of at least one legally essential stairway or to an exit?
  - 标准答案：35 m
  - 选项：**A. 35 m** ✓；B. 25 m；C. 40 m；D. 50 m
- **原文**：
  - p.121：“Every location in inhabited rooms and basements must be \( \leq 35 \) m from the stairwell of at least one legally essential stairway or exit.”

### K39 两条独立疏散路线

含至少一个居室的住宅或商业单元，每层须有至少两条通往室外的独立疏散路线；单元不在地面层时，第一条须经必要楼梯，第二条可经第二部必要楼梯或消防队救援设备可达的位置；经烟火无法侵入的安全楼梯间疏散时不需要第二疏散路线。

- **早期设计**：★★★ · LOD 200 · 决定疏散
- **IFC**：`IfcZone`、`IfcStair` · 还需要：房间分组（`IfcZone / IfcSpatialZone`）；相邻/围合（`IfcRelSpaceBoundary`）
- **页码**：p.511 (page_0523) · Building services
- **用到的题**（0 道，0 个模型）：
- **知识探针题**（须 · recall）：Under German building regulations, how many independent escape routes to the open air must a residential or commercial unit with at least one occupied room have on each storey, and if the unit is not at ground level, what may the second escape route be?
  - 标准答案：At least two; the second may be a second essential staircase or a location reachable with the fire brigade's rescue equipment
  - 选项：A. One; a second is required only for units more than 22 m above ground；**B. At least two; the second via a second essential stair or a point reachable by fire brigade rescue equipment** ✓；C. At least two; both must run via separate legally essential staircases in their own stairwells；D. At least two; the second must be an external escape stair fixed to the façade
- **原文**：
  - p.511：“Residential or commercial units with at least one occupied room must have at least two independent escape routes leading to the open air on each storey.”
  - p.511：“the second escape route via a second essential staircase or a single unified location which is accessible with the rescue equipment of the local fire brigade”

### K42 防火分区与防火墙

按 MBO，较大建筑须用防火墙划分为不超过 40 m 的防火分区；防火墙须防火、受火时结构稳定并由不燃材料构成（F 90 A）。防火墙上开口原则上不允许，建筑内部的防火墙可例外允许开口，但须设自闭式防火门（T 90 门或闸门）。

- **早期设计**：★★★ · LOD 200 · 决定疏散
- **IFC**：`IfcZone`、`IfcWall` · 还需要：房间分组（`IfcZone / IfcSpatialZone`）；性能属性（`Pset_*Common（FireRating, ThermalTransmittance, AcousticRating, IsExternal …）`）
- **页码**：p.513 (page_0525) · Building services
- **用到的题**（2 道，2 个模型）：`ac20-14`, `digital_hub-12`
- **知识探针题**（须 · recall）：Under the German model building regulations (MBO), into fire compartments of what maximum length must larger buildings be sub-divided by fire compartment walls, and what fire resistance classification must these walls have?
  - 标准答案：Max. 40 m; F 90-A (fire-resistant, non-combustible)
  - 选项：A. 40 m; F 30；B. 60 m; F 90-B；C. 30 m; F 120-A；**D. 40 m; F 90-A** ✓
- **原文**：
  - p.513：“to sub-divide larger buildings into fire compartments of not more than 40 m.”
  - p.513：“Fire compartment walls must be fireproof, structurally stable when exposed to fire and consist of non-combustible materials (F 90A).”
  - p.513：“Openings in fire compartment walls are generally impermissible. They can be allowed through fire compartment walls within buildings and then have to be provided with fireproof self-closing doors (T 90 door or gate)”

### K45 高层建筑的疏散走道

高层建筑疏散通道宽 ≥ 1.25 m，宜双向通往楼梯；房间任一点步行距离 ≤ 25 m；双向走廊 ≤ 40 m，每 20 m 设防烟自闭门；单向尽端走廊 ≤ 10 m（另有第二疏散路线时 ≤ 20 m）。

- **早期设计**：★★★ · LOD 200 · 决定疏散
- **IFC**：`IfcSpace`、`IfcDoor` · 还需要：相邻/围合（`IfcRelSpaceBoundary`）；用途/人数（`IfcSpace.Name / LongName, Pset_SpaceOccupancyRequirements, 建筑类型`）
- **页码**：p.246 (page_0258) · Administration and offices
- **用到的题**（1 道，1 个模型）：`office3-14`
- **知识探针题**（须 · recall）：For escape routes in high-rise buildings under German regulations, what are (a) the minimum width of escape routes, (b) the maximum walking distance from any point in an occupied room, and (c) the maximum length of a branch corridor with only one escape direction when no second escape route is available?
  - 标准答案：(a) 1.25 m; (b) 25 m; (c) 10 m
  - 选项：A. 1.20 m; 35 m; 15 m；B. 1.25 m; 35 m; 20 m；C. 1.50 m; 30 m; 10 m；**D. 1.25 m; 25 m; 10 m** ✓
- **原文**：
  - p.246：“Escape routes are min. 1.25 m wide and should if possible lead in two directions, to each staircase. The maximum walking distance from each point of an occupied room may not exceed 25 m. Corridors with two escape directions may be max. 40 m long. After 20 m, a smoke-proof self-closing door must be installed. Branch corridors with only one escape direction may be max. 10 m long. If a second escape route (e.g. an escape balcony) is available, max. 20 m.”

### K47 长疏散走廊分段与楼梯间的封闭

长度超过 30 m 的必要疏散走廊须用自闭、防烟的门分段；楼梯与作为疏散路线的走廊之间的门也须自闭、防烟。

- **早期设计**：★★ · LOD 200–300
- **IFC**：`IfcSpace`、`IfcDoor` · 还需要：相邻/围合（`IfcRelSpaceBoundary`）；性能属性（`Pset_*Common（FireRating, ThermalTransmittance, AcousticRating, IsExternal …）`）
- **页码**：p.517 (page_0529) · Building services
- **用到的题**（1 道，1 个模型）：`ac20-21`
- **知识探针题**（须 · recall）：Under German building regulations (general rule, not the high-rise guideline), legally essential escape-route corridors longer than what length must be divided by self-closing, smoke-proof closures?
  - 标准答案：30 m
  - 选项：**A. 30 m** ✓；B. 15 m；C. 50 m；D. 60 m
- **原文**：
  - p.517：“Closures between stairways and corridors legally essential as escape routes and also for the division of legally essential corridors more than 30 m long must be self-closing and smoke-proof”

## 居室标准与面积计算

### K76 居住面积计算

净高 ≥ 2 m 的部分全额计入，1–2 m 计一半；地下室、车库、办公室等不计。

- **早期设计**：★★★ · LOD 200 · 决定面积核算
- **IFC**：`IfcZone`、`IfcSpace` · 还需要：房间分组（`IfcZone / IfcSpatialZone`）；用途/人数（`IfcSpace.Name / LongName, Pset_SpaceOccupancyRequirements, 建筑类型`）
- **页码**：p.63 (page_0075) · Design process
- **用到的题**（2 道，1 个模型）：`fzk_house-02`, `fzk_house-11`
- **知识探针题**（须 · recall）：Under the German housing area regulation for calculating residential living area, which clear-ceiling-height thresholds decide whether a floor area is counted in full or by half?
  - 标准答案：Clear height ≥ 2 m: counted in full; ≥ 1 m and < 2 m: counted by half
  - 选项：A. Full from 2.30 m; half between 1.50 m and 2.30 m；B. Full from 2.40 m; half between 1.50 m and 2.40 m；**C. Full from 2 m; half between 1 m and 2 m** ✓；D. Full from 2 m; half between 1.50 m and 2 m
- **原文**：
  - p.63：“Floor areas are included in the calculation either completely (for rooms and parts of rooms with a clear ceiling height of at least 2 m), or a half (for rooms and parts of rooms with a clear ceiling height of at least 1 m and less than 2 m)”
  - p.63：“but not subsidiary rooms (cellars, garages etc:), offices and rooms which do not comply with the building regulations”

### K77 阳台计入居住面积

阳台、凉廊和露台属于居住面积的一部分，一般按其面积的 25–50% 计入。

- **早期设计**：★★ · LOD 200
- **IFC**：`IfcZone`、`IfcSpace` · 还需要：房间分组（`IfcZone / IfcSpatialZone`）；用途/人数（`IfcSpace.Name / LongName, Pset_SpaceOccupancyRequirements, 建筑类型`）
- **页码**：p.155 (page_0167) · Residential buildings
- **intent**：`page_0167_intent_010`
- **用到的题**（3 道，2 个模型）：`frb1-04`, `samuel-11`, `samuel-12`
- **知识探针题**（一般 · recall）：In German housing area calculation, balconies, loggias and terraces are normally counted toward living area at what proportion of their area?
  - 标准答案：25–50%
  - 选项：**A. 25–50%** ✓；B. 0% (not counted)；C. 100%；D. 50–75%
- **原文**：
  - p.155：“Balconies, loggias and terraces are a part of the living areas, for which they are normally calculated as 25–50%”

### K78 住宅面积的计入范围与净尺寸量法

（按 2003 年《住宅面积计算条例》，用于住房建设补贴法）住宅面积包括专属于该户的所有房间的地面面积；房间面积按构件之间的净空间确定，从构件饰面层表面量起，可在建成房间内实测，或按合适的施工图计算。

- **早期设计**：★★★ · LOD 200–300 · 决定面积核算
- **IFC**：`IfcZone`、`IfcSpace` · 还需要：房间分组（`IfcZone / IfcSpatialZone`）
- **页码**：p.136 (page_0148) · Residential buildings
- **intent**：`page_0148_intent_001`, `page_0148_intent_002`
- **用到的题**（1 道，1 个模型）：`fzk_house-27`
- **知识探针题**（须 · recall）：Under the German housing area regulation (2003), from which reference surface is a room's floor area measured?
  - 标准答案：Clear dimensions between building components, measured from the face of the components' cladding (finished surface)
  - 选项：A. From the wall centre lines；B. From the unfinished structural faces of the walls；**C. Clear dimensions from the face of the building components' cladding** ✓；D. From the external faces of the enclosing walls
- **原文**：
  - p.136：“The area of a house or flat includes the floor area of all rooms which belong exclusively to the house”
  - p.136：“The floor area of a room is determined from the clearance space between building components and starts from the face of the cladding of the building component”

## 住宅·户型组织与入户

### K85 分组式平面与中廊式平面

分组式平面（20 世纪初出现）将户内分为两个房间组：起居区（起居室、厨房和就餐区）和睡眠区（卧室和卫生间）。中廊式平面（19 世纪末城市公寓的典型平面）沿两侧立面布置房间，所有房间都可独立进入和使用。

- **早期设计**：★★★ · LOD 200 · 决定户型布局
- **IFC**：`IfcZone`、`IfcSpace` · 还需要：房间分组（`IfcZone / IfcSpatialZone`）；相邻/围合（`IfcRelSpaceBoundary`）；用途/人数（`IfcSpace.Name / LongName, Pset_SpaceOccupancyRequirements, 建筑类型`）
- **页码**：p.145 (page_0157) · Residential buildings
- **intent**：`page_0157_intent_006`, `page_0157_intent_019`
- **用到的题**（1 道，1 个模型）：`frb1-11`
- **知识探针题**（一般 · recall）：In German (DIN-based) design practice: In the grouped room floor plan for apartments (developed in the early 20th century), into which two room groups is the dwelling divided, and which rooms belong to each?
  - 标准答案：Living area (living room, kitchen, dining) and sleeping area (bedrooms, bathrooms)
  - 选项：A. Day area (living room, bedrooms) and service area (kitchen, bathrooms)；B. Living area (living room, dining, bathrooms) and sleeping area (bedrooms, kitchen)；**C. Living area (living room, kitchen, dining) and sleeping area (bedrooms, bathrooms)** ✓；D. Public area (entrance, living) and private area (all other rooms) along a central corridor
- **原文**：
  - p.145：“the separation of areas inside the apartment into two 'room groups': the living areas (living room, kitchen and dining area) and the sleeping area (bedrooms and bathrooms)”
  - p.145：“All rooms can be accessed and used separately.”

### K94 每户必备厨房与储藏间

按建筑法规，每套住宅（独户住宅或公寓）至少要有一个厨房或小厨房，并须配备足够大的储藏间。

- **早期设计**：★★★ · LOD 200 · 决定户型布局
- **IFC**：`IfcZone`、`IfcSpace` · 还需要：房间分组（`IfcZone / IfcSpatialZone`）；用途/人数（`IfcSpace.Name / LongName, Pset_SpaceOccupancyRequirements, 建筑类型`）
- **页码**：p.149 (page_0161), p.162 (page_0174) · Residential buildings
- **intent**：`page_0161_intent_028`, `page_0174_intent_012`
- **用到的题**（1 道，1 个模型）：`fzk_house-30`
- **知识探针题**（须 · recall）：According to the German building regulations, apart from the bathroom, which two rooms belong to the mandatory provision of every house or flat?
  - 标准答案：At least one kitchen (or kitchenette) and a sufficiently large storeroom
  - 选项：**A. A kitchen or kitchenette, and a sufficiently large storeroom** ✓；B. A kitchen, and a separate dining room of adequate size；C. A storeroom, and a separate laundry/utility room；D. A kitchenette, and a separate guest WC with washbasin
- **原文**：
  - p.149：“According to the building regulations, every house or flat must have at least one kitchen or kitchenette for cooking.”
  - p.162：“The building regulations require that every flat or house be provided with a sufficiently large storeroom.”

## 住宅·卧室、卫浴与储藏

### K103 卫生间

每户至少一个卫生间（含浴缸/淋浴和厕所的独立房间）；大户型宜浴厕分设或加客用 WC；卫生间通常紧邻卧室。

- **早期设计**：★★★ · LOD 200 · 决定户型布局
- **IFC**：`IfcZone`、`IfcSpace` · 还需要：房间分组（`IfcZone / IfcSpatialZone`）；用途/人数（`IfcSpace.Name / LongName, Pset_SpaceOccupancyRequirements, 建筑类型`）；家具/洁具（`IfcFurnishingElement / IfcFurniture / IfcSanitaryTerminal / IfcFlowTerminal`）
- **页码**：p.160 (page_0172) · Residential buildings
- **intent**：`page_0172_intent_001`, `page_0172_intent_002`, `page_0172_intent_007`
- **用到的题**（5 道，3 个模型）：`frb1-15`, `fzk_house-10`, `fzk_house-19`, `fzk_house-30`, `samuel-10`
- **知识探针题**（须 · recall）：Under German building regulations, a bathroom belongs to the minimum equipment of every flat or house. How is such a 'bathroom' defined?
  - 标准答案：An independent room with bath or shower and toilet
  - 选项：**A. An independent room with bath or shower and toilet** ✓；B. A room with WC and washbasin only；C. A room with bath, shower, washbasin and WC；D. A shower and washbasin in a niche of the bedroom
- **原文**：
  - p.160：“according to building regulations, belongs to the minimum equipment of a flat or house.”
  - p.160：“A bathroom is defined as an independent room with bath/shower and toilet”
  - p.160：“In larger houses, bath and WC should be in separate rooms, or an additional WC (guest WC) should be provided.”
  - p.160：“The bathroom is normally next to the bedroom”

### K107 户内储藏空间

户内储藏空间至少 1 m²、净宽 75 cm；较大住宅按建筑面积的 2% 设置（可分散成多处）；储藏间门宜外开以节省空间。

- **早期设计**：★★ · LOD 200
- **IFC**：`IfcZone`、`IfcSpace` · 还需要：房间分组（`IfcZone / IfcSpatialZone`）；用途/人数（`IfcSpace.Name / LongName, Pset_SpaceOccupancyRequirements, 建筑类型`）
- **页码**：p.162 (page_0174) · Residential buildings
- **intent**：`page_0174_intent_001`, `page_0174_intent_013`, `page_0174_intent_015`
- **用到的题**（1 道，1 个模型）：`samuel-16`
- **知识探针题**（宜 · recall）：In German (DIN-based) housing planning guidance, in addition to cellar and attic storage, what storage space should be provided within a flat: minimum area, minimum clear width, and the share of floor area for larger flats?
  - 标准答案：≥ 1 m² with 75 cm clear width; in larger flats 2% of the floor area
  - 选项：A. ≥ 2 m² with 60 cm clear width; 1% of floor area；B. ≥ 1.5 m² with 90 cm clear width; 2% of floor area；C. ≥ 1 m² with 60 cm clear width; 5% of floor area；**D. ≥ 1 m² with 75 cm clear width; 2% of floor area** ✓
- **原文**：
  - p.162：“storage space should therefore be provided within a flat of \( \geq 1 \ \mathrm{m}^2 \) with a clear width of 75 cm”
  - p.162：“In larger flats, 2% of the floor area should be provided as storage space (split into many small areas is also acceptable).”
  - p.162：“Doors to storerooms should open outward for reasons of space.”

## 办公

### K127 小型使用单元内的走廊

组合使用单元面积小于 400 m² 时，其内部走廊不受疏散通道要求的约束。

- **早期设计**：★★ · LOD 200
- **IFC**：`IfcZone`、`IfcSpace` · 还需要：房间分组（`IfcZone / IfcSpatialZone`）；用途/人数（`IfcSpace.Name / LongName, Pset_SpaceOccupancyRequirements, 建筑类型`）
- **页码**：p.241 (page_0253) · Administration and offices
- **用到的题**（1 道，1 个模型）：`office3-11`
- **知识探针题**（须 · recall）：Under German building regulations for office access systems: below what floor area of a combined use unit are the corridors inside it not subject to the requirements for escape routes?
  - 标准答案：400 m²
  - 选项：A. 200 m²；**B. 400 m²** ✓；C. 600 m²；D. 1000 m²
- **原文**：
  - p.241：“For combined use units of less than 400 m², the corridors are not subject to the requirements for escape routes.”

### K135 组合式办公（combi-office）

组合式办公：很小的单间办公室用玻璃隔墙与较深的联系区分开，共用设施设在联系区内；每人有一个专注工作的独立工位，中部共用区促进交流。特别适合工作地点可随日程变化的独立、高素质工作。

- **早期设计**：★★ · LOD 200 · 决定户型布局
- **IFC**：`IfcZone`、`IfcSpace` · 还需要：房间分组（`IfcZone / IfcSpatialZone`）；用途/人数（`IfcSpace.Name / LongName, Pset_SpaceOccupancyRequirements, 建筑类型`）
- **页码**：p.234 (page_0246), p.239 (page_0251) · Administration and offices
- **用到的题**（0 道，0 个模型）：
- **知识探针题**（宜 · recall）：In German (DIN-based) office design practice: In a combi-office, how are the individual offices separated from the central connection zone, and what is located in that zone?
  - 标准答案：Very small single offices are separated by glass walls from the deep connection zone, which holds the communally used infrastructure
  - 选项：A. By a corridor wall with doors only; the archive；**B. By glass walls; the communally used infrastructure** ✓；C. By movable screens; the individual workstations；D. By solid fire walls; the escape stairs
- **原文**：
  - p.234：“It is particularly suitable for independent, highly qualified work where the workplace can change with the daily programme.”
  - p.239：“Combi-office: Very small single offices are separated by glass walls from the deep connection zone, in which communally used infrastructure is located.”

### K138 非固定工位办公的面积节省

非固定工位（hot desk / business club）办公：员工的个人区域只限于一个可移动的桌柜单元；结合远程办公或外勤比例高时，比固定工位办公可节省 20–50%。

- **早期设计**：★ · LOD 200
- **IFC**：`IfcSpace`、`IfcFurnishingElement` · 还需要：用途/人数（`IfcSpace.Name / LongName, Pset_SpaceOccupancyRequirements, 建筑类型`）；家具/洁具（`IfcFurnishingElement / IfcFurniture / IfcSanitaryTerminal / IfcFlowTerminal`）
- **页码**：p.239 (page_0251) · Administration and offices
- **用到的题**（0 道，0 个模型）：
- **知识探针题**（descriptive · recall）：In German (DIN-based) office design practice: In a 'hot desk' office (business club) combined with teleworking or many travelling staff, what space savings are possible compared with personalised offices?
  - 标准答案：20–50%
  - 选项：**A. 20–50%** ✓；B. 5–10%；C. 10–15%；D. 60–80%
- **原文**：
  - p.239：“The personal area of the employee is limited to a mobile desk/cupboard unit.”
  - p.239：“Combined with teleworking or with a high proportion of travelling representatives, savings of 20–50% are possible compared with personalised offices”

# Space

空间：单个房间的大小、朝向、布局与相邻关系

## 无障碍

### K28 轮椅活动空间

轮椅转身：每个房间宜提供至少 1.50 m 深 × 1.50 m 宽的转身空间。对于公众可达建筑（第(2)条所指，如文化、教育、办公、餐饮等建筑），走廊和门厅宽度须 ≥ 1.50 m。

- **早期设计**：★★★ · LOD 200 · 决定无障碍
- **IFC**：`IfcSpace` · 还需要：用途/人数（`IfcSpace.Name / LongName, Pset_SpaceOccupancyRequirements, 建筑类型`）
- **页码**：p.21 (page_0033), p.25 (page_0037) · Basics
- **用到的题**（4 道，3 个模型）：`ac20-13`, `office3-10`, `fzk_house-07`, `fzk_house-18`
- **知识探针题**（宜 · recall）：In barrier-free design per German guidance, what minimum turning space (depth × width) for a wheelchair should be provided in every room?
  - 标准答案：1.50 m × 1.50 m
  - 选项：A. 1.20 m × 1.20 m；B. 1.80 m × 1.80 m；**C. 1.50 m × 1.50 m** ✓；D. 1.40 m × 1.70 m
- **原文**：
  - p.21：“A depth and width of at least 1.50 m should be provided in every room for turning.”
  - p.25：“Corridors and entrance halls must be at least 1.50 m wide.”

### K29 无障碍卫生间

无障碍公共建筑中，所有卫生设施内须至少设一个供轮椅使用者使用的厕所（坐高宜为 48 cm）；厕所、淋浴间和更衣间的门须向外开。

- **早期设计**：★★ · LOD 200–300
- **IFC**：`IfcSpace`、`IfcSanitaryTerminal`、`IfcDoor` · 还需要：家具/洁具（`IfcFurnishingElement / IfcFurniture / IfcSanitaryTerminal / IfcFlowTerminal`）；用途/人数（`IfcSpace.Name / LongName, Pset_SpaceOccupancyRequirements, 建筑类型`）
- **页码**：p.22 (page_0034) · Basics
- **用到的题**（1 道，1 个模型）：`digital_hub-03`
- **知识探针题**（须 · recall）：In barrier-free public buildings per German guidance, (a) how many wheelchair-accessible toilets must be provided in sanitary facilities, and (b) in which direction must doors to toilets, showers and changing rooms open?
  - 标准答案：(a) At least one wheelchair-accessible toilet in all sanitary facilities; (b) outward
  - 选项：**A. At least one in all sanitary facilities; doors open outward** ✓；B. At least one in all sanitary facilities; doors open inward；C. One per building; sliding doors only；D. Two in each sanitary facility; doors open outward
- **原文**：
  - p.22：“At least one toilet must be provided for wheelchair users in all sanitary facilities.”
  - p.22：“Doors to toilets, showers and changing rooms must open outward.”

### K33 长走廊轮椅会车位

长于 15 m 的走廊和通道须设宽、深均 ≥ 1.80 m 的两轮椅会车位。

- **早期设计**：★★ · LOD 200
- **IFC**：`IfcSpace` · 还需要：用途/人数（`IfcSpace.Name / LongName, Pset_SpaceOccupancyRequirements, 建筑类型`）
- **页码**：p.22 (page_0034) · Basics
- **用到的题**（2 道，2 个模型）：`ac20-13`, `office3-10`
- **知识探针题**（须 · recall）：In barrier-free design per German guidance, beyond what corridor length must a passing place for two wheelchair users be provided, and what minimum size (width and depth) must it have?
  - 标准答案：Corridors longer than 15 m; passing place at least 1.80 m × 1.80 m
  - 选项：A. > 20 m; 1.50 m × 1.50 m；**B. > 15 m; 1.80 m × 1.80 m** ✓；C. > 10 m; 2.00 m × 2.00 m；D. > 15 m; 1.50 m × 1.50 m
- **原文**：
  - p.22：“Corridors and routes longer than 15 m must have a passing place for two wheelchair users of at least 1.80 m width and depth.”

### K35 无障碍住宅卫浴

WC 一侧须留宽 ≥ 95 cm、深 ≥ 70 cm 的活动区，另一侧距墙或家具 ≥ 30 cm；浴室须设轮椅可用的淋浴，淋浴区及 WC、洗手台前须有 ≥ 1.50 × 1.50 m 活动区。

- **早期设计**：★★ · LOD 350
- **IFC**：`IfcSpace`、`IfcSanitaryTerminal` · 还需要：家具/洁具（`IfcFurnishingElement / IfcFurniture / IfcSanitaryTerminal / IfcFlowTerminal`）
- **页码**：p.23 (page_0035) · Basics
- **用到的题**（1 道，1 个模型）：`frb1-17`
- **知识探针题**（须 · recall）：In wheelchair-accessible dwellings per German guidance, what minimum movement area (width × depth) is required to one side of the WC, and what minimum distance is required from the other side of the WC to the wall or furniture?
  - 标准答案：95 cm wide × 70 cm deep on one side; min. 30 cm on the other side
  - 选项：A. 90 × 70 cm; 20 cm；B. 120 × 70 cm; 30 cm；C. 80 × 60 cm; 25 cm；**D. 95 × 70 cm; 30 cm** ✓
- **原文**：
  - p.23：“The movement area to the right or left of the WC must be at least 95 cm wide and 70 cm deep. From one side of the WC towards the wall, or furniture, there must be a distance of min. 30 cm”
  - p.23：“The bathroom is to be provided with a wheelchair-accessible shower.”
  - p.23（原文含换行/制表符，按原样）：

    ```text
    min. 1.50 m wide and min. 1.50 m deep...
    a turning place in every room (excepting small rooms, which the wheelchair user can use by moving backwards and forwards), the shower → ① + ④, in front of the WC and vanity unit
    ```

### K36 轮椅住宅的起居室

含就餐区的起居室最小面积：1 人 22 m²、2–4 人 24 m²、5 人 26 m²、6 人 28 m²；1–2 人户最小房间宽度 3.75 m。

- **早期设计**：★★ · LOD 200
- **IFC**：`IfcSpace` · 还需要：用途/人数（`IfcSpace.Name / LongName, Pset_SpaceOccupancyRequirements, 建筑类型`）
- **页码**：p.24 (page_0036) · Basics
- **用到的题**（1 道，1 个模型）：`fzk_house-21`
- **知识探针题**（宜 · recall）：In wheelchair-accessible dwellings per German guidance, what should be the minimum floor area of a living room with an eating area in a flat for one person and in a flat for 2–4 people, and what minimum room width applies for a 1–2 person household?
  - 标准答案：22 m² (1 person); 24 m² (2–4 people); min. width 3.75 m
  - 选项：A. 20 m²; 24 m²; 3.50 m；**B. 22 m²; 24 m²; 3.75 m** ✓；C. 24 m²; 26 m²; 4.00 m；D. 18 m²; 22 m²; 3.60 m
- **原文**：
  - p.24：“For a living room with an eating area, the minimum floor area should be: in a flat for one person 22 m², for 2–4 people 24 m², for five people 26 m² and for six people 28 m²; minimum room width 3.75 m (1–2 person household).”

### K37 无障碍住宅的户内活动区宽度

（无障碍住宅）以下活动区须至少 1.20 m 宽：轮椅使用者侧向接近的家具旁、非轮椅使用者床的进入侧、户内墙与墙之间、操作设备旁、坡道两侧护轮缘之间以及户内通道。

- **早期设计**：★★ · LOD 200
- **IFC**：`IfcSpace`、`IfcFurnishingElement` · 还需要：家具/洁具（`IfcFurnishingElement / IfcFurniture / IfcSanitaryTerminal / IfcFlowTerminal`）
- **页码**：p.23 (page_0035) · Basics
- **用到的题**（1 道，1 个模型）：`fzk_house-07`
- **知识探针题**（须 · recall）：In wheelchair-accessible dwellings per German guidance, what minimum width must the movement area have between walls within the dwelling and along routes within the house?
  - 标准答案：1.20 m
  - 选项：A. 0.90 m；B. 1.50 m；**C. 1.20 m** ✓；D. 1.00 m
- **原文**：
  - p.23（原文含换行/制表符，按原样）：

    ```text
    min. 1.20 m wide…
    along furniture which the wheelchair user approaches from the side, along the access side of a non-wheelchair user’s bed → 9, between walls within the dwelling
    ```

## 采光、日照、通风与窗

### K48 工作间的窗

工作间（按工作场所指南）：所有对外视线窗的总宽度须至少为全部墙宽总和的 1/10；对外视线宜在视平线高度（窗台高 0.85–1.25 m）；高度超过 3.5 m 的工作间，窗玻璃面积须至少为外墙面积的 30%。工业建筑中窗面积的近似值：面积不超过 600 m² 的房间约为地面面积的 1/10，精细作业约 1/5。

- **早期设计**：★★★ · LOD 200–300 · 决定立面与采光
- **IFC**：`IfcSpace`、`IfcWindow` · 还需要：相邻/围合（`IfcRelSpaceBoundary`）；用途/人数（`IfcSpace.Name / LongName, Pset_SpaceOccupancyRequirements, 建筑类型`）
- **页码**：p.97 (page_0109), p.266 (page_0278) · Building components / Industry and trade
- **用到的题**（4 道，3 个模型）：`ac20-04`, `office2-02`, `office2-05`, `fzk_house-15`
- **知识探针题**（须 · recall）：According to the German workplace guidelines, the total width of all visual connections to the outside (windows) in a workroom must be at least what fraction of the total width of all its walls?
  - 标准答案：1/10
  - 选项：A. 1/8；B. 1/5；C. 1/6；**D. 1/10** ✓
- **原文**：
  - p.97：“The total width of all visual connections to the outside must be at least 1/10 of the total width of all walls, according to workplace guidelines”
  - p.97：“Possible visual connection to the outside should be at eye level (window sill heights of 0.85 –1.25 m)”
  - p.97：“For workrooms more than 3.5 m high, the glass area of the window must be at least 30% of the outside wall area”
  - p.266：“1/10 of the floor area for rooms up to 600 m² (Workplace Guidelines 7/1 → p.”

### K52 视野：窗宽不小于房间宽 65%

为保证向外的视野，窗宽（按毛洞口尺寸）不应小于房间宽度的 65%。

- **早期设计**：★ · LOD 300
- **IFC**：`IfcSpace`、`IfcWindow` · 还需要：相邻/围合（`IfcRelSpaceBoundary`）
- **页码**：p.495 (page_0507) · Building services
- **用到的题**（4 道，4 个模型）：`digital_hub-10`, `hotel1-10`, `office2-10`, `fzk_house-08`
- **知识探针题**（宜 · recall）：In German (DIN-based) design practice: To ensure an adequate view out, the window width (structural opening, before finishings) should not be less than what percentage of the room width?
  - 标准答案：65%
  - 选项：**A. 65%** ✓；B. 50%；C. 80%；D. 40%
- **原文**：
  - p.495：“The minimum window width as a percentage, before finishings, should not be less than 65% of the room width.”

### K53 工作区距窗约为 2 倍窗净高

（工业建筑）侧窗采光时，工作区到窗的距离宜为窗净高的 2 倍。

- **早期设计**：★★ · LOD 200–300
- **IFC**：`IfcSpace`、`IfcWindow` · 还需要：相邻/围合（`IfcRelSpaceBoundary`）
- **页码**：p.266 (page_0278) · Industry and trade
- **用到的题**（1 道，1 个模型）：`digital_hub-08`
- **知识探针题**（宜 · recall）：In German (DIN-based) design practice: In side-lit industrial/work buildings, the distance of the working area from the window should be what multiple of the clear window height?
  - 标准答案：Twice the clear window height
  - 选项：A. Equal to the clear window height；B. 1.5 times；**C. Twice** ✓；D. 3 times
- **原文**：
  - p.266：“The distance of the working area from the window should be twice as long as the clear window height”

## 居室标准与面积计算

### K74 居室最低要求

居室最小面积 8 m²、净高 2.40 m，窗面积为房间面积的 1/8。

- **早期设计**：★★★ · LOD 200 · 决定房间尺寸
- **IFC**：`IfcSpace`、`IfcWindow` · 还需要：相邻/围合（`IfcRelSpaceBoundary`）
- **页码**：p.167 (page_0179) · Accommodation
- **用到的题**（7 道，3 个模型）：`hotel1-04`, `hotel1-05`, `fzk_house-01`, `fzk_house-03`, `fzk_house-09`, `samuel-03`, `samuel-07`
- **知识探针题**（须 · recall）：Under German building regulations, what are the minimum floor area, minimum ceiling height, and minimum window area (relative to room area) of a residential (habitable) room?
  - 标准答案：8 m²; 2.40 m; window area 1/8 of room area
  - 选项：A. 10 m²; 2.50 m; 1/6；**B. 8 m²; 2.40 m; 1/8** ✓；C. 8 m²; 2.20 m; 1/12；D. 6 m²; 2.40 m; 1/8
- **原文**：
  - p.167：“minimum requirements for floor area (8 m^2), ceiling height (2.40 m), orientation, ventilation and lighting (window area 1/8 of the room area)”

## 住宅·户型组织与入户

### K81 阳台面积

3–4 人阳台约 7 m²，5–6 人约 9 m²。

- **早期设计**：★★ · LOD 200
- **IFC**：`IfcSpace` · 还需要：用途/人数（`IfcSpace.Name / LongName, Pset_SpaceOccupancyRequirements, 建筑类型`）
- **页码**：p.155 (page_0167) · Residential buildings
- **intent**：`page_0167_intent_016`, `page_0167_intent_017`
- **用到的题**（3 道，2 个模型）：`frb1-04`, `samuel-11`, `samuel-12`
- **知识探针题**（一般 · recall）：In German (DIN-based) design practice: In housing design, approximately what balcony area is appropriate for a household of 5–6 people?
  - 标准答案：9 m²
  - 选项：A. 5 m²；**B. 9 m²** ✓；C. 7 m²；D. 12 m²
- **原文**：
  - p.155：“A = 7.0 m^2 balcony for 3–4 people”
  - p.155：“B = 9.0 m^2 balcony for 5–6 people”

### K82 户外空间的连接

户外空间一般与起居、工作和就餐空间相连；有多个户外空间时也可接卧室、厨房。

- **早期设计**：★★ · LOD 200
- **IFC**：`IfcSpace` · 还需要：相邻/围合（`IfcRelSpaceBoundary`）；用途/人数（`IfcSpace.Name / LongName, Pset_SpaceOccupancyRequirements, 建筑类型`）
- **页码**：p.155 (page_0167) · Residential buildings
- **intent**：`page_0167_intent_001`, `page_0167_intent_002`
- **用到的题**（2 道，1 个模型）：`samuel-11`, `samuel-12`
- **知识探针题**（一般 · recall）：In German (DIN-based) design practice: With which rooms of a dwelling should open-air areas (balconies, loggias, terraces) generally have a spatial relationship?
  - 标准答案：Living and working areas and dining rooms (with several open areas, also bedrooms, kitchens etc.)
  - 选项：A. Bathrooms and utility rooms；**B. Living and working areas and dining rooms** ✓；C. Entrance hall and staircase；D. Bedrooms only
- **原文**：
  - p.155：“They generally have a spatial relationship to living and working areas and dining rooms”
  - p.155：“with more than one open area, this can also include bedrooms, kitchens etc.”

### K87 门厅直达厨房、WC 和楼梯

厨房、WC 和楼梯这几个最重要的公共部分应能从门厅直接到达。

- **早期设计**：★★ · LOD 200
- **IFC**：`IfcSpace` · 还需要：相邻/围合（`IfcRelSpaceBoundary`）；用途/人数（`IfcSpace.Name / LongName, Pset_SpaceOccupancyRequirements, 建筑类型`）
- **页码**：p.147 (page_0159) · Residential buildings
- **intent**：`page_0159_intent_004`
- **用到的题**（1 道，1 个模型）：`frb1-13`
- **知识探针题**（宜 · recall）：In German (DIN-based) design practice: In a house, which of the most important communal areas should be directly accessible from the entrance hall?
  - 标准答案：Kitchen, WC and staircase
  - 选项：A. Living room, bedroom and bathroom；**B. Kitchen, WC and staircase** ✓；C. Dining room, study and terrace；D. Bathroom, utility room and cellar
- **原文**：
  - p.147：“The most important communal areas like the kitchen, WC and staircase should be directly accessible from the entrance hall.”

### K89 户内走道宽度

书中示例假定户内走道最小宽度为 1 m，可供两人错身；但这一宽度放不下柜子，柜子最好做成嵌入式。

- **早期设计**：★★ · LOD 200
- **IFC**：`IfcSpace` · 还需要：用途/人数（`IfcSpace.Name / LongName, Pset_SpaceOccupancyRequirements, 建筑类型`）
- **页码**：p.148 (page_0160) · Residential buildings
- **intent**：`page_0160_intent_002`, `page_0160_intent_003`
- **用到的题**（1 道，1 个模型）：`fzk_house-18`
- **知识探针题**（一般 · recall）：In German (DIN-based) planning examples of corridor layouts inside a dwelling, what minimum corridor width is assumed, one that allows two people to pass?
  - 标准答案：1 m
  - 选项：A. 0.70 m；B. 0.80 m；**C. 1.00 m** ✓；D. 1.50 m
- **原文**：
  - p.148：“The examples assume a minimum corridor width of 1 m, which allows two people to pass.”
  - p.148：“This width does not, however, permit the siting of cupboards, which would be better built-in”

### K90 独立住宅每层通往户外

独立住宅（自住住宅的原型）从每一层都可直接通往其他私有或半公共的户外空间（如花园、露台、内院或屋顶花园）。

- **早期设计**：★ · LOD 200
- **IFC**：`IfcSpace`、`IfcBuildingStorey` · 还需要：相邻/围合（`IfcRelSpaceBoundary`）
- **页码**：p.139 (page_0151) · Residential buildings
- **intent**：`page_0151_intent_011`
- **用到的题**（1 道，1 个模型）：`fzk_house-20`
- **知识探针题**（一般 · recall）：In German (DIN-based) design practice: A detached, owner-occupied house on its own plot typically has direct access to private or semi-public open spaces (garden, terrace, courtyard, roof garden) from which storeys?
  - 标准答案：From each storey
  - 选项：A. Only from the ground floor；**B. From each storey** ✓；C. From the ground floor and the top floor；D. Only from the main living level
- **原文**：
  - p.139：“It has direct access from each storey to further private or semi-public open spaces (e.g. garden, terrace, inner courtyard or roof garden)”

### K93 入户凹口尺寸

入户门前的凹口宽至少 1.25 m（最好 1.50 m）、深约 1.00 m，使两人能舒适且有遮蔽地在门前等候。

- **早期设计**：★★ · LOD 200–300
- **IFC**：`IfcSpace`、`IfcDoor`
- **页码**：p.146 (page_0158) · Residential buildings
- **用到的题**（0 道，0 个模型）：
- **知识探针题**（宜 · recall）：In German (DIN-based) design practice: How large should the entrance recess in front of a house or flat door be (minimum width, preferred width, approximate depth) so that two people can wait comfortably and sheltered in front of the door?
  - 标准答案：At least 1.25 m wide (better 1.50 m), approx. 1.00 m deep
  - 选项：A. At least 1.00 m wide (better 1.25 m), approx. 0.80 m deep；B. At least 1.50 m wide (better 2.00 m), approx. 1.50 m deep；C. At least 0.90 m wide (better 1.20 m), approx. 1.00 m deep；**D. At least 1.25 m wide (better 1.50 m), approx. 1.00 m deep** ✓
- **原文**：
  - p.146：“Entrance recesses should be at least 1.25 m (better 1.50 m) wide and approx. 1.00 m deep, so that two people can wait comfortably and protected in front of the door”

## 住宅·卧室、卫浴与储藏

### K109 卫生间类型

卫生间分四类：（客用）WC＝WC＋洗手盆；淋浴间＝淋浴＋洗手盆；浴室＝浴缸＋洗手盆＋WC；完整浴室＝浴缸＋淋浴＋洗手盆＋WC。

- **早期设计**：★ · LOD 300
- **IFC**：`IfcSpace`、`IfcSanitaryTerminal` · 还需要：家具/洁具（`IfcFurnishingElement / IfcFurniture / IfcSanitaryTerminal / IfcFlowTerminal`）
- **页码**：p.161 (page_0173) · Residential buildings
- **intent**：`page_0173_intent_019`
- **用到的题**（1 道，1 个模型）：`frb1-15`
- **知识探针题**（一般 · recall）：In German (DIN-based) design practice: Residential bathrooms are commonly divided into four basic categories: (guest) WC, shower room, bathroom and full bathroom. Which fittings does a 'full bathroom' contain?
  - 标准答案：Bath, shower, washbasin and WC
  - 选项：A. Bath, washbasin and WC；**B. Bath, shower, washbasin and WC** ✓；C. Shower, washbasin and WC；D. Bath, shower, two washbasins, WC and bidet
- **原文**：
  - p.161：“The basic bathroom categories are: (guest) WCs with WC and washbasin → 3 - 4, shower rooms with shower and basin → 5 - 6, bathrooms with bath, washbasin and WC → 7 - 8, full bathrooms with bath, shower, washbasin and WC → 10.”

## 办公

### K113 每工位总面积

每个工位的总面积需求 23–45 m²，视组织和职级而定。

- **早期设计**：★★★ · LOD 100–200 · 决定面积核算
- **IFC**：`IfcSpace` · 还需要：用途/人数（`IfcSpace.Name / LongName, Pset_SpaceOccupancyRequirements, 建筑类型`）
- **页码**：p.238 (page_0250) · Administration and offices
- **用到的题**（1 道，1 个模型）：`office2-03`
- **知识探针题**（一般 · recall）：In German (DIN-based) design practice: Within what range does the total space requirement per office workstation (including subsidiary and additional areas) typically vary, depending on organisational and status requirements?
  - 标准答案：23–45 m² per workstation
  - 选项：A. 8–12 m²；B. 12–20 m²；**C. 23–45 m²** ✓；D. 50–70 m²
- **原文**：
  - p.238：“The total space requirement per workstation varies between 23 and 45 m^2, depending on organisational and status requirements.”

### K114 工位尺寸

桌面工作面积宜不小于 120 × 80 cm（文件少、以屏幕工作为主的情况；专业人员至少 200 × 80 cm）；每个工位宜有不小于 1.5 m² 的自由活动面积。

- **早期设计**：★ · LOD 350
- **IFC**：`IfcSpace`、`IfcFurnishingElement` · 还需要：家具/洁具（`IfcFurnishingElement / IfcFurniture / IfcSanitaryTerminal / IfcFlowTerminal`）
- **页码**：p.236 (page_0248) · Administration and offices
- **用到的题**（3 道，3 个模型）：`office1-04`, `office2-04`, `office3-04`
- **知识探针题**（宜 · recall）：In German (DIN-based) design practice: For an office workstation with few documents and predominantly screen work, what is the guideline minimum desktop working area and the minimum free movement area at the workstation?
  - 标准答案：Desktop at least 120 × 80 cm; free movement area at least 1.5 m²
  - 选项：**A. Desktop 120 × 80 cm; movement area 1.5 m²** ✓；B. Desktop 160 × 80 cm; movement area 1.0 m²；C. Desktop 200 × 80 cm; movement area 1.5 m²；D. Desktop 120 × 60 cm; movement area 2.0 m²
- **原文**：
  - p.236：“The desktop working area should be at least 120 × 80 cm (few documents, predominantly screen work; for specialist employees, at least 200 × 80 cm)”
  - p.236：“There should be a free movement area of at least 1.5 m² at the workstation.”

### K115 办公室进深、开间与模数

1.50 m 模数是以双工位为主的单间办公室的经济模数：工位进深 2.20 m（桌 80 cm + 活动区 1 m + 后柜 40 cm），计 10 cm 墙厚得 4.40 m 净房间尺寸。近年行之有效的模数为单间办公室 1.50 m、组合办公 1.35 m；在 1.35 m 模数下，3.80 m 开间（约 18 m² 使用面积）可布置两个进深 0.90 m 的电脑工位（事故保险机构建议值）等多种工位。

- **早期设计**：★★★ · LOD 200 · 决定平面进深
- **IFC**：`IfcSpace` · 还需要：用途/人数（`IfcSpace.Name / LongName, Pset_SpaceOccupancyRequirements, 建筑类型`）
- **页码**：p.240 (page_0252) · Administration and offices
- **用到的题**（3 道，3 个模型）：`ac20-09`, `office2-04`, `office3-06`
- **知识探针题**（一般 · recall）：In German (DIN-based) design practice: In office planning, which grid module dimensions have proved successful in recent years for (a) single-room offices and (b) office types based on the combi principle?
  - 标准答案：1.50 m for single-room offices; 1.35 m for combi-offices
  - 选项：A. 1.35 m single-room; 1.50 m combi；**B. 1.50 m single-room; 1.35 m combi** ✓；C. 1.20 m single-room; 1.25 m combi；D. 1.875 m single-room; 1.50 m combi
- **原文**：
  - p.240：“Workstation depth 2.20 m (80 cm desk, 1 m movement area, 40 cm shelf behind). With 10 cm wall thickness, this gives 4.40 m clear room space.”
  - p.240：“The modular dimensions, which have proved successful in recent years, are 1.50 m for single-room offices and 1.35 m for office types based on the combi principle.”
  - p.240：“This is the economical module dimension for single-room offices consisting mainly of double workstations.”
  - p.240：“Room widths of 3.80 m (~18 m^2 usable area) enable:”
  - p.240：“two computer workstations with a depth of 0.90 m, as recommended by accident insurance companies”

### K117 办公室类型

单间办公室适合独立或专注工作；组团办公约 4–16 个工位；100 个以上工位的大开间依赖人工照明和通风；提倡单间与组团混合。

- **早期设计**：★★ · LOD 200
- **IFC**：`IfcSpace` · 还需要：用途/人数（`IfcSpace.Name / LongName, Pset_SpaceOccupancyRequirements, 建筑类型`）
- **页码**：p.232 (page_0244), p.233 (page_0245), p.239 (page_0251) · Administration and offices
- **用到的题**（5 道，3 个模型）：`digital_hub-06`, `digital_hub-16`, `office1-03`, `office3-03`, `office3-06`
- **知识探针题**（一般 · recall）：In German (DIN-based) design practice: Approximately how many workstations does a group office have, and how many workstations characterise the large-scale open-plan office landscapes made possible by artificial lighting and ventilation?
  - 标准答案：Group office approx. 4–16 workstations; open-plan 100 or more
  - 选项：A. Group office 2–6; open-plan 50 or more；B. Group office 10–30; open-plan 200 or more；**C. Group office 4–16; open-plan 100 or more** ✓；D. Group office 4–16; open-plan 50 or more
- **原文**：
  - p.232：“the requirement for a mixed provision of single and group rooms”
  - p.233：“Single-room offices are suitable for independent or concentrated work, as a single-person room or for a few people in very small groups who need to exchange information constantly.”
  - p.239：“The experience with the open-plan layout led to the development of group offices with approx. 4–16 workstations”
  - p.239：“The experience with the open-plan layout led to the development of group offices with approx. 4–16 workstations; each office is used by a single team or department.”
  - p.239：“Large-scale office landscapes with 100 or more workstations are made possible by artificial lighting and ventilation”

### K118 会议区

会议区每座约 2.5 m²（不含附属空间），储藏和备餐等附属空间约为会议面积的 1/3；会议区应从入口区直达。

- **早期设计**：★★ · LOD 200
- **IFC**：`IfcSpace` · 还需要：相邻/围合（`IfcRelSpaceBoundary`）；用途/人数（`IfcSpace.Name / LongName, Pset_SpaceOccupancyRequirements, 建筑类型`）
- **页码**：p.238 (page_0250) · Administration and offices
- **用到的题**（6 道，5 个模型）：`ac20-10`, `digital_hub-06`, `office1-05`, `office1-06`, `office2-07`, `office3-07`
- **知识探针题**（一般 · recall）：In German (DIN-based) design practice: In an office building, about how much floor area does a conference area require per seat (excluding subsidiary areas), and what proportion of the conference area do the subsidiary rooms (store rooms, catering pantry) require?
  - 标准答案：About 2.5 m² per seat; subsidiary rooms about 1/3 of the conference area
  - 选项：A. About 1.5 m² per seat; about 1/4；**B. About 2.5 m² per seat; about 1/3** ✓；C. About 5.0 m² per seat; about 1/5；D. About 4.0 m² per seat; about 1/2
- **原文**：
  - p.238：“A conference area requires about 2.5 m^2 per seat (without subsidiary areas).”
  - p.238：“store rooms and a pantry for catering (these subsidiary rooms require about 1/3 of the conference area)”
  - p.238：“Conference areas should be directly accessible from the entrance area.”

### K119 办公卫生间与茶水间配置

每 50–80 个工位一个厕所单元，每工位约 0.6–0.8 m²；每 50–100 个工位一个约 10 m² 的茶水间，并尽量靠近工位。

- **早期设计**：★★ · LOD 200
- **IFC**：`IfcSpace` · 还需要：用途/人数（`IfcSpace.Name / LongName, Pset_SpaceOccupancyRequirements, 建筑类型`）
- **页码**：p.238 (page_0250) · Administration and offices
- **用到的题**（6 道，5 个模型）：`ac20-06`, `digital_hub-06`, `office1-08`, `office2-06`, `office3-05`, `office3-07`
- **知识探针题**（一般 · recall）：In German (DIN-based) design practice: For office buildings, what ratio of toilet units to workstations is considered good, and how large a tea kitchen should be provided per how many workplaces?
  - 标准答案：One toilet unit per 50–80 workstations; one ~10 m² tea kitchen per approx. 50–100 workplaces
  - 选项：A. 1 toilet unit per 20–30; one 6 m² kitchen per 30–50；B. 1 toilet unit per 50–80; one 20 m² kitchen per 200；C. 1 toilet unit per 100–150; one 10 m² kitchen per 50–100；**D. 1 toilet unit per 50–80; one 10 m² kitchen per 50–100** ✓
- **原文**：
  - p.238：“A good ratio is one toilet unit per 50–80 workstations. Space requirement ~0.6–0.8 m² per workstation.”
  - p.238：“A good ratio is one toilet unit per 50–80 workstations.”
  - p.238：“For every approx. 50–100 workplaces, one ~10 m² kitchen.”
  - p.238：“Tea kitchens should be as near to the workstations as possible and connected with communication zones. For every approx. 50–100 workplaces, one ~10 m² kitchen.”

### K120 工作场所厕所（劳动场所规定）

（工作场所）厕所距每个工位不超过 100 m，或最远不超过一层楼高（无自动扶梯时）；员工超过 5 人须分设男女厕所，且宜仅供员工使用；厕所由带洗手盆的前室（每 5 个 WC 至少 1 个洗手盆）和完全分隔、至少含一个 WC 的房间组成。

- **早期设计**：★★ · LOD 200
- **IFC**：`IfcSpace`、`IfcSanitaryTerminal` · 还需要：相邻/围合（`IfcRelSpaceBoundary`）；用途/人数（`IfcSpace.Name / LongName, Pset_SpaceOccupancyRequirements, 建筑类型`）；家具/洁具（`IfcFurnishingElement / IfcFurniture / IfcSanitaryTerminal / IfcFlowTerminal`）
- **页码**：p.270 (page_0282) · Industry and trade
- **用到的题**（3 道，2 个模型）：`office1-07`, `office1-08`, `office3-05`
- **知识探针题**（须 · recall）：Under the German Workplace Regulations: (a) what is the maximum distance from each workstation to the toilets, (b) above how many employees must separate toilets for women and men be provided, and (c) what is the minimum number of washbasins in the toilet lobby relative to WCs?
  - 标准答案：(a) not more than 100 m (or one storey height); (b) more than 5 employees; (c) at least one washbasin per 5 WCs
  - 选项：A. 50 m; more than 10; 1 per 3 WCs；B. 100 m; more than 10; 1 per 5 WCs；**C. 100 m; more than 5; 1 per 5 WCs** ✓；D. 150 m; more than 5; 1 per 10 WCs
- **原文**：
  - p.270：“If there are more than five employees, separate toilets must be provided for women and men and these should be available exclusively to employees.”
  - p.270：“If there are more than five employees, separate toilets must be provided for women and men”
  - p.270：“These are to be provided at a distance from each workstation of not more than 100 m or, at the farthest, one storey height”
  - p.270：“Toilet facilities consist of a lobby with washbasins (at least one washbasin per five WCs) and a completely separate room with at least one WC (unless the facilities contain only one toilet and have no direct access to a work, social, changing, wash or sanitary room).”
  - p.270：“Toilet facilities consist of a lobby with washbasins (at least one washbasin per five WCs) and a completely separate room with at least one WC”
  - p.270：“at least one washbasin per five WCs”

### K121 厅室的每人容积

声学所需容积的参考值：讲话 4 m³/人，（音乐会）音乐 10 m³/人；容积过小则混响不足。

- **早期设计**：★ · LOD 200
- **IFC**：`IfcSpace` · 还需要：用途/人数（`IfcSpace.Name / LongName, Pset_SpaceOccupancyRequirements, 建筑类型`）
- **页码**：p.483 (page_0495) · Building services
- **用到的题**（1 道，1 个模型）：`ac20-12`
- **知识探针题**（一般 · recall）：In German (DIN-based) design practice: For good room acoustics, what are the guideline room volumes per person for rooms used for speech and for (concert) music?
  - 标准答案：4 m³/person for speech; 10 m³/person for music
  - 选项：**A. 4 m³ for speech; 10 m³ for music** ✓；B. 2 m³ for speech; 5 m³ for music；C. 6 m³ for speech; 12 m³ for music；D. 10 m³ for speech; 4 m³ for music
- **原文**：
  - p.483：“Guideline values are 4 m³/person for speech and 10 m³/person for (concert) music. If the volume is too small, this allows too little reverberation.”

### K122 保洁间与物业用房

办公楼每层应设一间保洁间（存放清洁设备，最好有给水和拖把池）；物业管理员需要位于中心位置的休息室、储藏室和工作间。

- **早期设计**：★ · LOD 200
- **IFC**：`IfcSpace`、`IfcBuildingStorey` · 还需要：用途/人数（`IfcSpace.Name / LongName, Pset_SpaceOccupancyRequirements, 建筑类型`）
- **页码**：p.238 (page_0250) · Administration and offices
- **用到的题**（2 道，2 个模型）：`ac20-15`, `digital_hub-14`
- **知识探针题**（宜 · recall）：In German (DIN-based) design practice: In an office building, how frequently should cleaner's rooms be provided, and with what fittings ideally?
  - 标准答案：One on every floor, ideally with water supply and bucket sink
  - 选项：A. One central cleaner's room per building, with a washing machine；B. One on every second floor, with a floor drain；**C. One on every floor, ideally with water supply and bucket sink** ✓；D. One per 1000 m² of floor area, without water supply
- **原文**：
  - p.238：“A cleaner’s room should be provided on every floor, as a store for cleaning equipment and ideally with water supply and bucket sink.”
  - p.238：“The caretaker should have a rest room, store and workshop in a central location.”

### K123 档案室

文件室须干燥，因此阁楼和地下室不宜；文件区宜采用净高约 2.10 m（2 层普通办公 = 3 层文件存放；有利的窗中线高度为 2.25–2.50 m）；档案室宜按 7.5–12.5 kN/m² 的较高楼面荷载设计（针对移动式密集架）。

- **早期设计**：★ · LOD 200
- **IFC**：`IfcSpace` · 还需要：用途/人数（`IfcSpace.Name / LongName, Pset_SpaceOccupancyRequirements, 建筑类型`）
- **页码**：p.237 (page_0249), p.238 (page_0250) · Administration and offices
- **用到的题**（1 道，1 个模型）：`ac20-16`
- **知识探针题**（宜 · recall）：In German (DIN-based) design practice: For office filing (records) rooms, what is the guideline ceiling clearance height for filing areas (such that two storeys of normal office space equal three storeys of filing), and what increased floor loading should archive rooms with mobile shelving units be designed for?
  - 标准答案：Clearance height 2.10 m; floor loading 7.5–12.5 kN/m²
  - 选项：A. 2.25–2.50 m; 5.0 kN/m²；**B. 2.10 m; 7.5–12.5 kN/m²** ✓；C. 2.10 m; 5.0 kN/m²；D. 2.40 m; 15–20 kN/m²
- **原文**：
  - p.237：“The rooms must be dry, so attic and cellar are inadvisable.”
  - p.237：“ceiling clearance height 2.10 m (2 storeys of normal office space = 3 storeys of filing)”
  - p.238：“Archive rooms should be designed for an increased floor loading of 7.5–12.5 kN/m² (for mobile units)”

### K124 办公楼入口区

入口区连接公共区与工作区，主要功能为门厅、门禁、问询、访客登记和等候区，是企业形象的第一印象。

- **早期设计**：★ · LOD 200
- **IFC**：`IfcSpace` · 还需要：相邻/围合（`IfcRelSpaceBoundary`）；用途/人数（`IfcSpace.Name / LongName, Pset_SpaceOccupancyRequirements, 建筑类型`）
- **页码**：p.238 (page_0250) · Administration and offices
- **用到的题**（1 道，1 个模型）：`office1-10`
- **知识探针题**（一般 · recall）：In German (DIN-based) design practice: Which main functions does the entrance area of an office building (the connection between public and working areas) typically contain?
  - 标准答案：Lobby, access control, information, visitor registration and waiting zone
  - 选项：**A. Lobby, access control, information, visitor registration and waiting zone** ✓；B. Lobby, canteen, mail room, archive and central copy room；C. Reception, conference rooms, tea kitchen, cloakroom and toilets；D. Lobby, open-plan workstations, copy room, archive and mail room
- **原文**：
  - p.238：“Connection between public and working areas. The important functions are lobby, access control, information, visitor registration and waiting zone.”
  - p.238：“Important area for the company’s corporate identity – the first impression is decisive!”

### K125 员工餐厅位置

办公楼食堂/自助餐厅宜靠近接待处并位于门禁之外，以便外来访客使用。

- **早期设计**：★ · LOD 200
- **IFC**：`IfcSpace` · 还需要：相邻/围合（`IfcRelSpaceBoundary`）；用途/人数（`IfcSpace.Name / LongName, Pset_SpaceOccupancyRequirements, 建筑类型`）
- **页码**：p.238 (page_0250) · Administration and offices
- **用到的题**（1 道，1 个模型）：`digital_hub-15`
- **知识探针题**（宜 · recall）：In German (DIN-based) design practice: Where should a canteen or cafeteria in an office building be located so that outside visitors can also use it?
  - 标准答案：Near the reception and outside the access control
  - 选项：A. On the top floor, inside the access-controlled zone；**B. Near the reception and outside the access control** ✓；C. In the basement next to the delivery yard；D. At the centre of the office floors, inside the access control
- **原文**：
  - p.238：“Location near the reception and outside the access control allows outside visitors in.”

### K126 组团办公室到窗距离

组团办公室（小型开敞办公）适合需要持续交流的工作组，工位周边到窗的距离最大 7.5 m。

- **早期设计**：★★ · LOD 200
- **IFC**：`IfcSpace`、`IfcWindow` · 还需要：相邻/围合（`IfcRelSpaceBoundary`）；家具/洁具（`IfcFurnishingElement / IfcFurniture / IfcSanitaryTerminal / IfcFlowTerminal`）
- **页码**：p.233 (page_0245) · Administration and offices
- **用到的题**（1 道，1 个模型）：`digital_hub-16`
- **知识探针题**（宜 · recall）：In German (DIN-based) design practice: Group rooms (smaller open-plan offices for work groups with constant information exchange) limit the size of the workplace surroundings. What is the guideline maximum distance from a workplace to a window for them?
  - 标准答案：max. 7.5 m
  - 选项：A. 6.0 m；**B. 7.5 m** ✓；C. 10.0 m；D. 12.5 m
- **原文**：
  - p.233：“Group rooms (smaller open-plan) are suitable for work groups with constant information exchange.”
  - p.233：“via the size of the workplace surroundings (max. 7.5 m to a window)”

### K128 餐饮厨房员工休息室

餐饮厨房的员工区中，员工超过 10 人时须设休息室（依据劳动场所规定）。

- **早期设计**：★★ · LOD 200
- **IFC**：`IfcSpace` · 还需要：用途/人数（`IfcSpace.Name / LongName, Pset_SpaceOccupancyRequirements, 建筑类型`）
- **页码**：p.180 (page_0192) · Accommodation
- **用到的题**（2 道，2 个模型）：`ac20-22`, `digital_hub-22`
- **知识探针题**（须 · recall）：For the staff area of a commercial (catering) kitchen, above what number of employees do the workplace regulations require a rest/break room?
  - 标准答案：More than 10 employees
  - 选项：A. More than 5 employees；B. More than 20 employees；**C. More than 10 employees** ✓；D. More than 50 employees
- **原文**：
  - p.180：“For more than 10 employees, a rest/break room is necessary (workplace regulations).”

### K129 研讨室的规模与进深

高校研讨室常用规模为 20、40、50、60 座，每名学生约 1.90–2.00 m²；仅靠一面外墙自然通风时，房间进深不超过净高的 2.5 倍。

- **早期设计**：★★★ · LOD 200 · 决定房间尺寸
- **IFC**：`IfcSpace` · 还需要：用途/人数（`IfcSpace.Name / LongName, Pset_SpaceOccupancyRequirements, 建筑类型`）
- **页码**：p.202 (page_0214) · Education and research
- **用到的题**（2 道，2 个模型）：`ac20-23`, `digital_hub-23`
- **知识探针题**（宜 · recall）：In German (DIN-based) design practice: For university seminar rooms, what is the guideline floor area per student, and if the room has free ventilation from only one external wall, what is the maximum room depth?
  - 标准答案：1.90–2.00 m² per student; depth not exceeding 2.5 × clear ceiling height
  - 选项：A. 1.20–1.50 m² per student; depth ≤ 2.5 × clear height；**B. 1.90–2.00 m² per student; depth ≤ 2.5 × clear height** ✓；C. 1.90–2.00 m² per student; depth ≤ 3.5 × clear height；D. 2.50–3.00 m² per student; depth ≤ 2.0 × clear height
- **原文**：
  - p.202：“Seminar rooms, usual sizes: 20, 40, 50, 60 seats; mobile double tables, width 1.20 m, depth 0.60 m, space required per student 1.90–2.00 m.”
  - p.202：“If there is free ventilation from only one external wall, the depth of the room should not exceed 2.5 × clear ceiling height.”

### K130 高校教研人员办公室面积

高校教研人员办公室面积参考值：教授 20–24 m²，科研助理 15 m²，助理 20 m²，秘书 15 m²（两人合用 20 m²）。

- **早期设计**：★★ · LOD 200
- **IFC**：`IfcSpace` · 还需要：用途/人数（`IfcSpace.Name / LongName, Pset_SpaceOccupancyRequirements, 建筑类型`）
- **页码**：p.202 (page_0214) · Education and research
- **用到的题**（1 道，1 个模型）：`ac20-24`
- **知识探针题**（一般 · recall）：In German (DIN-based) design practice: In university planning, what are the guideline office floor areas for scientific personnel: (a) a professor and (b) a scientific assistant?
  - 标准答案：Professor 20–24 m²; scientific assistant 15 m²
  - 选项：A. Professor 15 m²; scientific assistant 20–24 m²；B. Professor 30–36 m²; scientific assistant 20 m²；C. Professor 12–15 m²; scientific assistant 10 m²；**D. Professor 20–24 m²; scientific assistant 15 m²** ✓
- **原文**：
  - p.202（原文含换行/制表符，按原样）：

    ```text
    professor 20–24 m²
    scientific assistant 15 m²
    assistant 20 m²
    secretary 15 m² (double occupation 20 m²)
    ```

### K136 单间办公：疏散通道内不得放家具

单间办公：单人间和双人间沿一条多为人工照明的走廊成排布置；因疏散通道内不允许放置家具，共用设施只能占用使用房间里昂贵的靠窗面积。

- **早期设计**：★★ · LOD 200 · 决定疏散
- **IFC**：`IfcSpace`、`IfcFurnishingElement` · 还需要：家具/洁具（`IfcFurnishingElement / IfcFurniture / IfcSanitaryTerminal / IfcFlowTerminal`）；用途/人数（`IfcSpace.Name / LongName, Pset_SpaceOccupancyRequirements, 建筑类型`）
- **页码**：p.239 (page_0251) · Administration and offices
- **用到的题**（0 道，0 个模型）：
- **知识探针题**（须 · recall）：In German (DIN-based) office design practice: In a conventional single-room (cellular) office layout along a corridor, why does jointly used infrastructure end up occupying window space inside the rooms?
  - 标准答案：Because no furniture is allowed in escape routes (the corridor), so shared equipment cannot stand there
  - 选项：**A. Because no furniture is allowed in escape routes** ✓；B. Because corridors must be at least 2.50 m wide；C. Because shared equipment needs natural ventilation；D. Because the corridor is too dark for shared equipment
- **原文**：
  - p.239：“Single and double rooms are arranged in rows along a mostly artificially lit corridor.”
  - p.239：“Jointly used infrastructure occupies expensive window space in occupied rooms, because no furniture is allowed in escape routes.”

### K137 大空间办公的进深

大空间（开敞）办公适合主要从事协同工作的大群体和专注度要求低的常规工作；其 20–30 m 的大进深导致建筑设备成本高，改造适应性有限。

- **早期设计**：★★ · LOD 100–200 · 决定平面进深
- **IFC**：`IfcSpace` · 还需要：用途/人数（`IfcSpace.Name / LongName, Pset_SpaceOccupancyRequirements, 建筑类型`）
- **页码**：p.233 (page_0245) · Administration and offices
- **用到的题**（0 道，0 个模型）：
- **知识探针题**（descriptive · recall）：In German (DIN-based) office design practice: What room depths were typical of the open-plan offices of the 1960s, a depth that resulted in high costs for building services?
  - 标准答案：20–30 m
  - 选项：**A. 20–30 m** ✓；B. 7–10 m；C. 12–13 m；D. 40–50 m
- **原文**：
  - p.233：“are suitable for large groups of employees who are predominantly engaged in shared work and for routine activities with a low concentration threshold.”
  - p.233：“The extensive room depths of 20–30 m resulted in high costs for building services”

### K140 工位面积的构成

标准不再规定工位的固定尺寸，而要求有足够的工作面积和活动面积。面积分为：工作面（桌面）、搁置面（家具的平面面积）、家具功能面（门和抽屉开启所需）、工位活动面、交通与通行面；各类面积在不影响功能时可以重叠。

- **早期设计**：★★ · LOD 300 · 决定房间尺寸
- **IFC**：`IfcSpace`、`IfcFurnishingElement` · 还需要：家具/洁具（`IfcFurnishingElement / IfcFurniture / IfcSanitaryTerminal / IfcFlowTerminal`）
- **页码**：p.235 (page_0247) · Administration and offices
- **用到的题**（0 道，0 个模型）：
- **知识探针题**（须 · recall）：In German (DIN-based) office design practice: The current standard no longer fixes workplace dimensions but distinguishes several kinds of area at a workstation. Name the five areas.
  - 标准答案：Work area (table), shelf area (plan area of the furniture), furniture function area (space for doors and drawers), movement area at the workstation, and traffic and through-passages
  - 选项：A. Work, storage, meeting, break and printing areas；**B. Work, shelf, furniture function, movement, and traffic/through-passage areas** ✓；C. Net, gross, usable, technical and circulation areas；D. Desk, chair, screen, cabinet and lighting areas
- **原文**：
  - p.235：“The standard no longer prescribes fixed dimensions for workplaces, but requires sufficient working and movement areas for changing positions at work and for the individually adaptable placing of work equipment.”
  - p.235（原文含换行/制表符，按原样）：

    ```text
    – work area: table
    – shelf area: plan area of the furniture
    – furniture function area: space required for doors and drawers
    – movement area at the workstation
    – traffic and through-passages
    ```
  - p.235：“The assignments of various areas are differentiated by the standard; however, they can overlap if this results in no limitation of the function.”

### K142 屏幕工位与窗的关系

屏幕工位的视线方向应与窗立面及灯带平行，屏幕尽量位于两者之间。

- **早期设计**：★★ · LOD 300 · 决定户型布局
- **IFC**：`IfcSpace`、`IfcFurnishingElement`、`IfcWindow` · 还需要：家具/洁具（`IfcFurnishingElement / IfcFurniture / IfcSanitaryTerminal / IfcFlowTerminal`）；相邻/围合（`IfcRelSpaceBoundary`）
- **页码**：p.236 (page_0248) · Administration and offices
- **用到的题**（0 道，0 个模型）：
- **知识探针题**（宜 · recall）：In German (DIN-based) office design practice: How should the direction of view to a computer screen be oriented relative to the window façade and the light bands?
  - 标准答案：Parallel to the window façade and to the light bands, with the screen if possible in between
  - 选项：A. With the back to the window；B. Facing the window；C. At 45° to the window façade；**D. Parallel to the window façade and light bands** ✓
- **原文**：
  - p.236：“The view to the screen should be parallel to the window façade and to light bands, with the screen if possible in-between.”

### K143 档案存放的面积与位置

档案系统所需面积 = 家具面积 + 通道面积，其中家具面积 = 长 × 宽，通道面积 = ½ 长 × 宽 + 0.5 m；档案系统应设在中心位置；密集架（移动式档案系统）取消中间通道，可节省 100–120% 的空间。

- **早期设计**：★ · LOD 200–300
- **IFC**：`IfcSpace`、`IfcFurnishingElement` · 还需要：家具/洁具（`IfcFurnishingElement / IfcFurniture / IfcSanitaryTerminal / IfcFlowTerminal`）；用途/人数（`IfcSpace.Name / LongName, Pset_SpaceOccupancyRequirements, 建筑类型`）
- **页码**：p.237 (page_0249) · Administration and offices
- **用到的题**（0 道，0 个模型）：
- **知识探针题**（descriptive · recall）：In German (DIN-based) office design practice: In the formula for the space needed by a filing system (filing furniture of length L and width W), how is the passage space calculated?
  - 标准答案：½ L × W + 0.5 m
  - 选项：A. L × W + 1.0 m；B. ¼ L × W + 1.0 m；**C. ½ L × W + 0.5 m** ✓；D. 2 × L × W
- **原文**：
  - p.237（原文含换行/制表符，按原样）：

    ```text
    L × W (filing furniture) = space for furniture
    + ½ L × W + 0.5 m = passage space
    ```
  - p.237：“The filing system should be centrally located.”
  - p.237：“enable a space saving of 100–120%) by eliminating intermediate passages”

### K144 收发室

收发室负责全部进出邮件和货物的分发；工作位（打包台、分拣台）应足够大，以便高峰时快速分发；面积需求约每工位 0.3–0.5 m²。

- **早期设计**：★ · LOD 200
- **IFC**：`IfcSpace` · 还需要：用途/人数（`IfcSpace.Name / LongName, Pset_SpaceOccupancyRequirements, 建筑类型`）
- **页码**：p.238 (page_0250) · Administration and offices
- **用到的题**（0 道，0 个模型）：
- **知识探针题**（descriptive · recall）：In German (DIN-based) office design practice: What space requirement is given for the post room of an office building?
  - 标准答案：About 0.3–0.5 m² per work position
  - 选项：A. 0.05–0.1 m²；B. 1.0–1.5 m²；**C. 0.3–0.5 m²** ✓；D. 2.0–2.5 m²
- **原文**：
  - p.238：“Work positions (packing and sorting tables) should be sufficiently large so that distribution can be rapid at peak times.”
  - p.238：“Space requirement – 0.3-0.5 m² per work position.”

### K145 数据中心与服务器机房

数据中心或服务器机房因安装量大，应设 70 cm 高的架空地板并设空调；门禁尤其重要；备份系统应尽量与数据中心分开，设在有防火保护的区域。

- **早期设计**：★ · LOD 200–300
- **IFC**：`IfcSpace` · 还需要：用途/人数（`IfcSpace.Name / LongName, Pset_SpaceOccupancyRequirements, 建筑类型`）
- **页码**：p.238 (page_0250) · Administration and offices
- **用到的题**（0 道，0 个模型）：
- **知识探针题**（宜 · recall）：In German (DIN-based) office design practice: What raised-floor height should data centres or server rooms have because of the large amount of installation?
  - 标准答案：70 cm
  - 选项：**A. 70 cm** ✓；B. 30 cm；C. 120 cm；D. 15 cm
- **原文**：
  - p.238：“These rooms should have a 70 cm raised floor on account of the large amount of installation, and should be air-conditioned.”
  - p.238：“Back-up systems should if possible be separated from the data centre in fire-protected areas.”

# Element

构件：门、窗、墙、屋面及其构造层和性能

## 门

### K22 住宅门的常规宽度

住宅中单扇门的净开启宽度：房门约 80 cm，浴室/WC 门约 70 cm，户门 ≥ 90 cm，入户大门最大 115 cm。

- **早期设计**：★★ · LOD 300
- **IFC**：`IfcDoor` · 还需要：用途/人数（`IfcSpace.Name / LongName, Pset_SpaceOccupancyRequirements, 建筑类型`）
- **页码**：p.113 (page_0125) · Building components
- **用到的题**（5 道，4 个模型）：`hotel1-08`, `frb1-07`, `fzk_house-05`, `fzk_house-06`, `samuel-05`
- **知识探针题**（一般 · recall）：In German (DIN-based) dwelling planning, what are the usual clear widths of single-leaf doors in dwellings for (a) room doors, (b) bathroom/WC doors and (c) entrance doors to flats?
  - 标准答案：(a) approx. 80 cm; (b) approx. 70 cm; (c) min. 90 cm
  - 选项：A. 90 / 80 / 100 cm；B. 75 / 65 / 85 cm；**C. 80 / 70 / 90 cm** ✓；D. 70 / 60 / 80 cm
- **原文**：
  - p.113（原文含换行/制表符，按原样）：

    ```text
    room doors      approx. 80 cm
    ```
  - p.113（原文含换行/制表符，按原样）：

    ```text
    bath, WC        approx. 70 cm
    ```
  - p.113（原文含换行/制表符，按原样）：

    ```text
    entrance doors
        to flats      min. 90 cm
    front doors      up to 115 cm
    ```

### K23 内门净高

内门净开启高度最小 2.10 m。

- **早期设计**：★★ · LOD 300
- **IFC**：`IfcDoor`
- **页码**：p.113 (page_0125) · Building components
- **用到的题**（3 道，3 个模型）：`ac20-03`, `fzk_house-05`, `samuel-06`
- **知识探针题**（须 · recall）：In German (DIN-based) building planning, what is the minimum clear opening height of internal doors?
  - 标准答案：210 cm
  - 选项：A. 200 cm；B. 195 cm；C. 225 cm；**D. 210 cm** ✓
- **原文**：
  - p.113（原文含换行/制表符，按原样）：

    ```text
    clear opening height of internal doors
    minimum	210 cm
    ```

### K24 紧急出口的门型

紧急出口处不允许使用推拉门和旋转门，因为危险情况下它们可能堵塞出口；旋转门通行能力较低，高峰时门扇可折叠推到一侧（图示有带附加紧急出口的旋转门示例）。

- **早期设计**：★★ · LOD 300
- **IFC**：`IfcDoor` · 还需要：性能属性（`Pset_*Common（FireRating, ThermalTransmittance, AcousticRating, IsExternal …）`）；用途/人数（`IfcSpace.Name / LongName, Pset_SpaceOccupancyRequirements, 建筑类型`）
- **页码**：p.10 (page_0022), p.113 (page_0125), p.115 (page_0127) · Basics / Building components
- **用到的题**（3 道，3 个模型）：`ac20-02`, `office3-08`, `fzk_house-06`
- **知识探针题**（须 · recall）：In German (DIN-based) design practice: Which two door types are not permissible at emergency exits because they can block the exit in circumstances of danger?
  - 标准答案：Sliding doors and revolving doors
  - 选项：**A. Sliding doors and revolving doors** ✓；B. Double-swing doors and outward-opening side-hung doors；C. Fire doors and smoke-control doors；D. Doors with panic hardware and glazed doors
- **原文**：
  - p.10：“Because revolving doors can cope with relatively little through traffic, the door leaves can be folded at peak times and pushed to the side.”
  - p.113：“Sliding doors and revolving doors are not permissible at emergency exits, which they can block in circumstances of danger.”
  - p.115：“Revolving door with additional emergency exits”

### K25 电梯入户的户门

按 MBO，经电梯到达的住户户门须有 90 cm 净开启宽度（供轮椅通行），此时门高宜 ≥ 2.10 m。

- **早期设计**：★★ · LOD 300
- **IFC**：`IfcDoor`、`IfcTransportElement` · 还需要：电梯/坡道（`IfcTransportElement / IfcRamp`）；用途/人数（`IfcSpace.Name / LongName, Pset_SpaceOccupancyRequirements, 建筑类型`）
- **页码**：p.146 (page_0158) · Residential buildings
- **intent**：`page_0158_intent_001`
- **用到的题**（2 道，1 个模型）：`frb1-06`, `frb1-17`
- **知识探针题**（须 · recall）：According to the German model building regulations (MBO), what clear opening width must the front doors of flats that are accessed by lifts have (for wheelchair access)?
  - 标准答案：90 cm
  - 选项：A. 80 cm；B. 85 cm；C. 100 cm；**D. 90 cm** ✓
- **原文**：
  - p.146：“front doors of flats which are accessed by lifts must have a clear opening width of 90 cm (for wheelchair access). The door height in this case should be at least 2.10 m.”

## 无障碍

### K26 无障碍门净宽

无障碍公共建筑中，门净通行宽度 ≥ 0.90 m；按 MBO §50，公众可达建筑须至少能经一个净开口宽度 ≥ 0.90 m 且无台阶的入口进入。

- **早期设计**：★★★ · LOD 300 · 决定无障碍
- **IFC**：`IfcDoor` · 还需要：用途/人数（`IfcSpace.Name / LongName, Pset_SpaceOccupancyRequirements, 建筑类型`）
- **页码**：p.22 (page_0034), p.25 (page_0037) · Basics
- **用到的题**（10 道，8 个模型）：`ac20-03`, `digital_hub-03`, `hotel1-08`, `office1-09`, `office3-08`, `frb1-07`, `frb1-17`, `fzk_house-07`, `samuel-05`, `samuel-06`
- **知识探针题**（须 · recall）：In barrier-free (accessible) building design per German guidance, what is the minimum clear passage width of doors?
  - 标准答案：0.90 m
  - 选项：**A. 0.90 m** ✓；B. 0.80 m；C. 1.00 m；D. 0.85 m
- **原文**：
  - p.22：“Clear passage width of doors \( \geq 0.90 \) m”
  - p.25：“must be accessible through an entrance with a clear opening width of at least 0.90 m without steps.”

## 疏散与防火

### K40 疏散窗

作为疏散路线的窗，净开口 ≥ 0.9 × 1.2 m，窗台高 ≤ 1.2 m。

- **早期设计**：★★ · LOD 300
- **IFC**：`IfcWindow` · 还需要：洞口（`IfcOpeningElement + IfcRelFillsElement`）
- **页码**：p.97 (page_0109) · Building components
- **用到的题**（2 道，2 个模型）：`ac20-05`, `hotel1-04`
- **知识探针题**（须 · recall）：Under German building regulations, if a window serves as an escape route, what minimum clear opening (width × height) must it have, and what maximum sill height above floor level?
  - 标准答案：Clear opening at least 0.9 × 1.2 m; sill height max. 1.2 m
  - 选项：A. 0.6 × 0.9 m; 1.1 m；B. 1.0 × 1.4 m; 1.0 m；**C. 0.9 × 1.2 m; 1.2 m** ✓；D. 0.6 × 1.0 m; 1.2 m
- **原文**：
  - p.97：“If the window serves as an escape route, it must have a clear opening of at least 0.9 × 1.2 m and a sill height of max. 1.2 m above floor level.”

### K41 出口宽度（按人数）

紧急出口宽度每 150 人 1.0 m（餐饮章节）。

- **早期设计**：★★ · LOD 200
- **IFC**：`IfcDoor` · 还需要：用途/人数（`IfcSpace.Name / LongName, Pset_SpaceOccupancyRequirements, 建筑类型`）
- **页码**：p.175 (page_0187) · Accommodation
- **用到的题**（0 道，0 个模型）：
- **知识探针题**（须 · recall）：In German (DIN-based) design practice: In planning guidance for restaurants and catering establishments, emergency exits must be 1.0 m wide per how many people using them?
  - 标准答案：150 people
  - 选项：A. 100 people；B. 200 people；**C. 150 people** ✓；D. 250 people
- **原文**：
  - p.175：“Emergency exits 1.0 m wide per 150 people using them.”

### K44 疏散走廊侧墙 F 30

作为疏散路线侧墙的走廊墙须为阻燃构造（F 30）；其上的采光开口是 G 级玻璃的典型应用（仅在无更高防火要求处允许），此时玻璃下沿须离地 ≥ 1.80 m。非承重分隔墙可做成不同品质的龙骨隔墙。

- **早期设计**：★★ · LOD 300
- **IFC**：`IfcWall`、`IfcWindow` · 还需要：性能属性（`Pset_*Common（FireRating, ThermalTransmittance, AcousticRating, IsExternal …）`）；用途/人数（`IfcSpace.Name / LongName, Pset_SpaceOccupancyRequirements, 建筑类型`）
- **页码**：p.514 (page_0526), p.516 (page_0528) · Building services
- **用到的题**（1 道，1 个模型）：`office3-13`
- **知识探针题**（须 · recall）：Under German building regulations, (a) what fire resistance class must corridor walls have when they are the side walls of escape routes, and (b) if lighting openings with G-glazing are installed in such walls, what minimum height above floor level must the lower edge of the glass be?
  - 标准答案：(a) F 30 (fire-retarding); (b) at least 1.80 m
  - 选项：**A. F 30; 1.80 m** ✓；B. F 90; 1.80 m；C. F 30; 1.20 m；D. F 60; 1.50 m
- **原文**：
  - p.514：“Non-load-bearing separating walls can be constructed as stud partitions of various qualities”
  - p.516：“A typical area of application for G-glazing is the openings for lighting installed in corridor walls, which have to be constructed fire-retarding (F 30) as the side walls of escape routes. The lower edge of the glass must in this case be at least 1.80 m above floor level, so that in case of fire the corridor remains usable in the radiation shadow.”

### K46 高层建筑立面的层间防火

高层建筑每层须有高 ≥ 1 m 的 W 90 A 防火窗槛墙，或外挑 ≥ 1.5 m 的 W 90 A 水平构件；全玻璃（含双层）幕墙须特别审批并采用喷淋等措施防止火势窜层。

- **早期设计**：★★ · LOD 200–300
- **IFC**：`IfcWall`、`IfcCurtainWall`、`IfcSlab` · 还需要：性能属性（`Pset_*Common（FireRating, ThermalTransmittance, AcousticRating, IsExternal …）`）
- **页码**：p.246 (page_0258) · Administration and offices
- **用到的题**（1 道，1 个模型）：`office1-14`
- **知识探针题**（须 · recall）：Under German fire-protection requirements for high-rise building façades, a W 90 A fire-resistant parapet (the 'fire spreading height') is used to stop fire spreading from one storey to the next. What minimum height must this parapet have?
  - 标准答案：1 m
  - 选项：A. 0.8 m；B. 1.5 m；**C. 1 m** ✓；D. 1.2 m
- **原文**：
  - p.246：“In order to avoid fire spreading from one storey to the one above, there must be W 90 A fire-resistant parapets at least 1 m high (fire spreading height).”
  - p.246：“Alternatively, a W 90 A horizontal building element projecting at least 1.5 m from the façade can be provided.”
  - p.246：“All-glass façades (also double façades) are permitted only with special approvals if particular protection measures (area sprinklers, mist extinguishing systems) can prevent the spread of fire to the next storey”

## 围护结构与保温

### K57 单层外墙与附加保温层

单层外墙在建筑物理上没有问题，但由于保温要求高，只能用高保温材料（如加气砌块）配专用保温砂浆和抹灰砌筑；因此单层墙加附加保温层（外保温或内保温）是常见的替代做法。保温层外侧因受热积聚和基层抗剪强度低而有开裂风险，因此这里采用网格增强的矿物抹灰（或聚合物改性抹灰）。

- **早期设计**：★★★ · LOD 300 · 决定构造选型
- **IFC**：`IfcWall` · 还需要：构造层（`IfcMaterialLayerSet`）
- **页码**：p.75 (page_0087), p.473 (page_0485) · Building components / Building services
- **用到的题**（6 道，4 个模型）：`ac20-18`, `digital_hub-18`, `digital_hub-20`, `office1-11`, `fzk_house-23`, `fzk_house-26`
- **知识探针题**（须 · recall）：In German (DIN-based) design practice: Single-leaf external masonry walls without an additional insulation layer must meet high thermal insulation requirements. What materials does this restrict their construction to?
  - 标准答案：Materials with high thermal insulation value (e.g. aerated blocks) laid with special thermally insulating mortars and plasters
  - 选项：A. Dense solid clay bricks with standard mortar and lime plaster；B. Calcium-silicate blocks with cement render；**C. Highly insulating blocks (e.g. aerated blocks) with special thermally insulating mortar and plaster** ✓；D. Any masonry unit, provided a mesh-reinforced render is applied
- **原文**：
  - p.75：“Single-leaf external walls → ① – ② are unproblematic regarding building physics, but on account of the high thermal insulation requirements can only be built with materials with high thermal insulation value (e.g. aerated blocks) and special thermally insulated mortars and plasters.”
  - p.75：“Single-leaf walls with additional insulation layers → ③ – ⑥ (external, internal insulation → Building physics, p. 471 ff.) are therefore a common alternative.”
  - p.75：“are unproblematic regarding building physics, but on account of the high thermal insulation requirements can only be built with materials with high thermal insulation value (e.g. aerated blocks) and special thermally insulated mortars and plasters.”
  - p.473：“On the external side of the insulating layers, there is a risk of cracking due to heat build-up and substrate with poor shear strength, so mineral render reinforced with mesh is used here (or plastic modified render).”

### K58 夹心墙（双叶墙）的外叶与空气层

夹心墙由内侧承重叶墙和外侧非承重防护面层组成，外叶最小厚 90 mm，可做空气层、空气层加保温、满填保温或中间抹灰层；空气层宽度至少 40 mm、最多 150 mm。

- **早期设计**：★★ · LOD 300
- **IFC**：`IfcWall` · 还需要：构造层（`IfcMaterialLayerSet`）
- **页码**：p.75 (page_0087) · Building components
- **用到的题**（0 道，0 个模型）：
- **知识探针题**（宜 · recall）：In German masonry construction, for a two-leaf cavity wall with a non-load-bearing outer weather-protection leaf, what is the minimum thickness of the outer leaf, and what are the minimum and maximum widths of the air gap?
  - 标准答案：Outer leaf min. 90 mm; air gap min. 40 mm, max. 150 mm
  - 选项：A. 150 mm; 40–90 mm；**B. 90 mm; 40–150 mm** ✓；C. 90 mm; 20–40 mm；D. 40 mm; 90–150 mm
- **原文**：
  - p.75：“Cavity walls consist of an inner load-bearing wall and an outer non-load-bearing weather protection facing (minimum thickness 90 mm). They can be built with an air gap, with air gap and thermal insulation, with cavity-filling insulation and with intermediate plaster layer”
  - p.75：“The width of the air gap should be min. 40 mm (max. 150 mm).”

### K59 混凝土外墙必须附加保温

实心混凝土墙只有加设附加保温层才能用作外墙：外保温系统，或带夹心保温（可加背通风）的多叶构造；带夹心保温的双层钢筋混凝土墙常用作大尺寸外墙构件。

- **早期设计**：★★★ · LOD 300 · 决定构造选型
- **IFC**：`IfcWall` · 还需要：构造层（`IfcMaterialLayerSet`）
- **页码**：p.78 (page_0090) · Building components
- **用到的题**（4 道，3 个模型）：`digital_hub-19`, `digital_hub-20`, `office1-11`, `frb1-18`
- **知识探针题**（须 · recall）：In German (DIN-based) design practice: Can a solid concrete wall be used as an external wall without an additional thermal insulation layer?
  - 标准答案：No; only with an additional thermal insulation layer (external insulation system, or multi-leaf construction with core insulation)
  - 选项：A. Yes, if the wall is at least 30 cm thick；B. Yes, if it is pre-cast；C. Only in building classes 1 and 2；**D. No, only with an additional thermal insulation layer** ✓
- **原文**：
  - p.78：“Solid concrete walls can be used as external walls only with an additional thermal insulation layer. This can be as an external thermal insulation system → ① or as a multi-leaf construction (analogous to p. 75) with core insulation and possibly back-ventilation.”
  - p.78：“Solid concrete walls can be used as external walls only with an additional thermal insulation layer.”
  - p.78：“Two-layer reinforced concrete walls → ① with core insulation are used particularly as large-format external wall elements.”

### K60 背通风外挂层的空气间层

背通风可消除较不透汽外层的隔汽效应；板材类外挂层后的空气间层至少 20 mm，砖砌外层至少 40 mm。

- **早期设计**：★ · LOD 350
- **IFC**：`IfcWall`、`IfcCovering` · 还需要：构造层（`IfcMaterialLayerSet`）
- **页码**：p.473 (page_0485) · Building services
- **用到的题**（1 道，1 个模型）：`digital_hub-18`
- **知识探针题**（须 · recall）：In German (DIN-based) design practice: In external walls with a rear-ventilated outer skin, what minimum air-gap width is required behind a panel-like outer skin, and behind a brickwork outer skin?
  - 标准答案：Panel-like skin: min. 20 mm; brickwork skin: min. 40 mm
  - 选项：A. Panel: 40 mm; brickwork: 20 mm；B. Panel: 10 mm; brickwork: 40 mm；**C. Panel: 20 mm; brickwork: 40 mm** ✓；D. Panel: 40 mm; brickwork: 60 mm
- **原文**：
  - p.473：“The rear ventilation of the skin removes the vapour barrier effect of the relatively vapour-sealed outer layers. The width of the air gap with panel-like external skin amounts to min. 20 mm, or for brickwork outer skin min. 40 mm.”

### K61 热阻与传热系数计算

单层热阻 R = d/λ（d 以 m 计）；总热阻 1/U = R_si + R + R_se，U 为其倒数；表面空气层热阻只能占 1/U 的有限比例。

- **早期设计**：★★★ · LOD 300 · 决定构造选型
- **IFC**：`IfcWall`、`IfcRoof`、`IfcSlab` · 还需要：构造层（`IfcMaterialLayerSet`）；性能属性（`Pset_*Common（FireRating, ThermalTransmittance, AcousticRating, IsExternal …）`）
- **页码**：p.471 (page_0483), p.472 (page_0484) · Building services
- **用到的题**（2 道，1 个模型）：`fzk_house-23`, `fzk_house-24`
- **知识探针题**（一般 · recall）：In German (DIN-based) design practice: How is the thermal resistance R of a single building layer calculated, and how is the overall resistance 1/U of a building element composed?
  - 标准答案：R = d/λ (d = layer thickness in m); 1/U = R_si + R + R_se
  - 选项：**A. R = d/λ; 1/U = R_si + R + R_se** ✓；B. R = d·λ; U = R_si + R + R_se；C. R = λ/d; 1/U = R_si + R + R_se；D. R = d/λ; 1/U = R − R_si − R_se
- **原文**：
  - p.471：“Thermal resistance R, unit m^2K/W [m^2hK/kcal] is a property of a layer: R = d/λ (d = layer thickness in m).”
  - p.471：“Overall resistance 1/U, unit m^2K/W [m^2hK/kcal], is the sum of the resistances of a building element to the transmission of heat (thermal resistances and surface resistances): 1/U = R_{si} + R + R_{se}”
  - p.472：“The surface air film cannot exceed a certain proportion X of the overall resistance 1/U”

### K63 平屋面排水坡度

坡度不超过 5% 的屋面为平屋面；无坡平屋面只在例外情况下作为特殊构造；平屋面一般至少 2% 坡度，考虑平整度误差和挠度建议至少 5%（3°）。

- **早期设计**：★★ · LOD 300
- **IFC**：`IfcRoof`、`IfcSlab`
- **页码**：p.91 (page_0103) · Building components
- **用到的题**（3 道，3 个模型）：`office2-12`, `office3-12`, `samuel-18`
- **知识探针题**（宜 · recall）：In German (DIN-based) design practice: What minimum slope should a flat roof generally have, and what minimum slope is recommended to allow for unavoidable flatness tolerances and deflection?
  - 标准答案：Generally min. 2%; recommended min. 5% (3°)
  - 选项：**A. 2% / 5% (3°)** ✓；B. 2% / 3% (1.7°)；C. 3% / 8% (5°)；D. 1% / 2%
- **原文**：
  - p.91：“Flat roofs are defined as roofs with a slope of up to 5%. Flat roofs without slope are possible as a special construction in exceptional cases. Flat roofs should generally have a minimum slope of 2%.”
  - p.91：“it is recommended to construct flat roofs with a minimum slope of 5% (3°).”

### K65 隔汽层设在暖侧

若隔汽层在外侧（冷侧），整个水蒸气压力梯度都发生在那里，会产生冷凝；要避免冷凝，须在暖侧设置隔汽层。较新的构造（暖屋面、暖立面）外侧有隔汽层（如防水层），因此另设内侧隔汽层。坡屋面中隔汽层位于保温层下方，以防屋面构造内部冷凝。

- **早期设计**：★ · LOD 350
- **IFC**：`IfcRoof`、`IfcWall` · 还需要：构造层（`IfcMaterialLayerSet`）
- **页码**：p.90 (page_0102), p.472 (page_0484), p.473 (page_0485) · Building components / Building services
- **用到的题**（2 道，2 个模型）：`office2-13`, `samuel-18`
- **知识探针题**（须 · recall）：In German (DIN-based) design practice: To avoid condensation within a building element, on which side must the vapour barrier be installed?
  - 标准答案：On the warm (interior) side
  - 选项：A. On the cold (exterior) side；**B. On the warm (interior) side** ✓；C. In the ventilated cavity outside the insulation；D. In the middle of the insulation layer
- **原文**：
  - p.90：“The vapour barrier is under the thermal insulation to prevent condensation inside the roof construction.”
  - p.472：“If there is a vapour barrier on the outside, then the entire vapour pressure gradient occurs there and the result is condensation → 8; if this is to be avoided, then a vapour barrier must be installed on the warm side”
  - p.473：“More recent building ('warm roof', 'warm façade') features an external vapour barrier layer (e.g.”

### K66 种植屋面的坡度

种植的坡屋面坡度不应超过 25°，种植平屋面坡度最大 2–3%。

- **早期设计**：★ · LOD 300
- **IFC**：`IfcRoof`、`IfcSlab` · 还需要：构造层（`IfcMaterialLayerSet`）
- **页码**：p.94 (page_0106) · Building components
- **用到的题**（1 道，1 个模型）：`office2-12`
- **知识探针题**（宜 · recall）：In German (DIN-based) design practice: For roofs with planting (green roofs), what maximum pitch should a gabled roof have, and what maximum slope should a planted flat roof have?
  - 标准答案：Gabled roof max. 25°; flat roof max. 2–3%
  - 选项：A. 15°; 1–2%；**B. 25°; 2–3%** ✓；C. 10°; 5–8%；D. 25°; 5%
- **原文**：
  - p.94：“The pitch of gabled roofs should not exceed 25° and flat roofs should have a maximum slope of 2–3%.”

### K67 坡屋面保温位置与通风构造

坡屋面保温一般为矿棉卷材，铺在椽间和椽下，室内侧设隔汽层；通风屋面在挂瓦下垫层与保温之间另有通风层，需更大椽高且只有在隔汽层和通风都可靠时才有效，因此业内多采用非通风构造。

- **早期设计**：★★ · LOD 300–350
- **IFC**：`IfcRoof` · 还需要：构造层（`IfcMaterialLayerSet`）
- **页码**：p.90 (page_0102) · Building components
- **用到的题**（2 道，2 个模型）：`office2-13`, `fzk_house-25`
- **知识探针题**（一般 · recall）：In German (DIN-based) design practice: Why does the building industry commonly prefer unventilated over ventilated insulated pitched-roof construction?
  - 标准答案：Ventilated roofs need additional rafter depth and only work properly with a correctly installed vapour barrier and functioning roof ventilation
  - 选项：A. Unventilated roofs allow insulation only above the rafters；B. Unventilated roofs need no vapour barrier；C. Ventilated roofs are not permitted under the energy saving regulation；**D. Ventilated roofs need deeper rafters and depend on a correct vapour barrier and airflow** ✓
- **原文**：
  - p.90：“Thermal insulation is generally in the form of mineral wool roll material and is installed between and under the rafters or as prefabricated insulation elements, sometimes with interlocking, vapour barrier on the room side and battens fixed to the rafters”
  - p.90：“ventilated roof construction has an additional ventilation gap between underlay and thermal insulation, to remove spray and condensate.”
  - p.90：“Ventilated roofs require additional rafter depth and work properly only with a correctly installed vapour barrier and functioning roof ventilation. Therefore the building industry commonly prefers unventilated roof construction.”

## 墙体与构造

### K68 分户墙隔声

住宅之间或户与户之间的分户墙宜始终达到至少 400 kg/m² 的面密度。对于贯通整栋房屋进深设分隔缝的（房屋之间的）双叶分户墙：每叶（含抹灰）面密度须至少 150 kg/m²，分隔缝至少 30 mm；缝宽大于 50 mm 时每叶可为 100 kg/m²；缝腔内须满铺无缝的纤维隔声板。

- **早期设计**：★★★ · LOD 300 · 决定构造选型
- **IFC**：`IfcWall` · 还需要：性能属性（`Pset_*Common（FireRating, ThermalTransmittance, AcousticRating, IsExternal …）`）；构造层（`IfcMaterialLayerSet`）；房间分组（`IfcZone / IfcSpatialZone`）
- **页码**：p.478 (page_0490), p.479 (page_0491) · Building services
- **用到的题**（0 道，0 个模型）：
- **知识探针题**（宜 · recall）：In German (DIN-based) design practice: For sound insulation, party walls between flats or houses should always have a mass per unit area of at least how much?
  - 标准答案：400 kg/m²
  - 选项：**A. 400 kg/m²** ✓；B. 250 kg/m²；C. 500 kg/m²；D. 150 kg/m²
- **原文**：
  - p.478：“for this reason, party walls between flats or houses should always weigh at least 400 kg/m².”
  - p.479：“The mass per unit area of the individual layers with plaster must be at least 150 kg/m^2, and the thickness of the separating joint must be at least 30 mm.”

### K69 模数协调与标志尺寸

基本模数 M = 100 mm，扩大模数 3M = 300 mm、6M = 600 mm、12M = 1200 mm；构造（标志）尺寸由模数尺寸扣除或加上灰缝/面层厚度得到，如砖模数长 25 cm、灰缝 1 cm、标志尺寸 24 cm，现浇混凝土墙 25 cm。

- **早期设计**：★★ · LOD 200–300
- **IFC**：`IfcWall`、`IfcGrid`
- **页码**：p.34 (page_0046), p.35 (page_0047) · Basics
- **用到的题**（1 道，1 个模型）：`fzk_house-22`
- **知识探针题**（一般 · recall）：In the modular coordination system for building dimensions (DIN 18000, metric modular system), what is the basic module M, and which multi-modules are defined?
  - 标准答案：M = 100 mm; multi-modules 3M, 6M and 12M
  - 选项：A. M = 100 mm; 4M, 8M, 16M；B. M = 100 mm; 2M, 5M, 10M；**C. M = 100 mm; 3M, 6M, 12M** ✓；D. M = 200 mm; 3M, 6M, 12M
- **原文**：
  - p.34：“Structural dimensions or nominal dimensions (for construction types with joints and wall finishes) are derived from modular dimensions by deducting or adding the component for the joint or the finish thickness.”
  - p.34：“Example: modular dimension for the length of a brick = 25 cm; thickness of the vertical joint = 1 cm; nominal dimension for the length of the brick = 24 cm; modular dimension for the thickness of poured concrete walls = nominal dimension = 25 cm”
  - p.35：“The units of the modular system are the basic module M = 100 mm and the multi-modules 3 M = 300 mm, 6 M = 600 mm and 12 M = 1200 mm.”

### K70 建筑等级与承重墙耐火

（书中在垃圾间规定处以括号注明）住宅超过两套或使用面积达 400 m² 的建筑属于建筑等级 3–5。承重及支撑墙、柱在等级 5 的建筑中须为防火（耐火）构造，等级 4 须为高度阻燃，等级 1 和 2 须为阻燃；此规定不适用于其上方无居室的屋顶空间最上层及阳台；在地下室中须为防火构造，等级 1 和 2 的建筑为阻燃。

- **早期设计**：★★★ · LOD 200 · 决定构造选型
- **IFC**：`IfcWall`、`IfcColumn` · 还需要：性能属性（`Pset_*Common（FireRating, ThermalTransmittance, AcousticRating, IsExternal …）`）；用途/人数（`IfcSpace.Name / LongName, Pset_SpaceOccupancyRequirements, 建筑类型`）
- **页码**：p.464 (page_0476), p.514 (page_0526) · Agriculture / Building services
- **用到的题**（3 道，3 个模型）：`ac20-17`, `frb1-19`, `samuel-19`
- **知识探针题**（须 · recall）：Under the German model building code building classes, what fire-resistance quality must load-bearing and bracing walls and columns (above ground) have in building class 5, in class 4, and in classes 1–2?
  - 标准答案：Class 5: fireproof (fire-resistant); class 4: highly fire-retarding; classes 1–2: fire-retarding
  - 选项：A. Class 5: highly fire-retarding; class 4: fire-retarding; classes 1–2: no requirement；B. Class 5: fire-retarding; class 4: highly fire-retarding; classes 1–2: fireproof；C. Class 5: fireproof; class 4: fireproof; classes 1–2: highly fire-retarding；**D. Class 5: fireproof; class 4: highly fire-retarding; classes 1–2: fire-retarding** ✓
- **原文**：
  - p.464：“buildings with more than two flats or a usable area of 400 m² (building classes 3–5)”
  - p.514：“Load-bearing and bracing walls and columns must be constructed fireproof in buildings of class 5, highly fire-retarding in buildings of class 4 and fire-retarding in buildings of classes 1 and 2”
  - p.514：“This does not apply to the uppermost storeys of roof spaces without occupied rooms above them and balconies.”

### K72 住宅/商业单元之间的分隔墙

居住或商业单元之间（或单元与其他用途房间之间）分隔墙的耐火时间须与该层承重构件相当，并须一直砌到结构楼板（屋顶空间内到屋面覆层）。

- **早期设计**：★★★ · LOD 300 · 决定构造选型
- **IFC**：`IfcWall` · 还需要：性能属性（`Pset_*Common（FireRating, ThermalTransmittance, AcousticRating, IsExternal …）`）；房间分组（`IfcZone / IfcSpatialZone`）
- **页码**：p.514 (page_0526) · Building services
- **用到的题**（1 道，1 个模型）：`frb1-19`
- **知识探针题**（须 · recall）：In German (DIN-based) design practice: For separating walls between residential or commercial units, what fire resistance duration is required and how far up must the walls extend?
  - 标准答案：Fire resistance corresponding to the load-bearing components of that storey; extending up to the structural slab (in roof spaces up to the roof cladding)
  - 选项：**A. Fire resistance equal to the storey's load-bearing components; up to the structural slab (in roof spaces to the roof cladding)** ✓；B. Always 30 minutes; up to the suspended ceiling；C. Always 90 minutes; up to the underside of the roof insulation；D. Fire resistance equal to the storey's load-bearing components; up to the suspended ceiling
- **原文**：
  - p.514：“The fire resistance duration of separating walls between residential or commercial units (or units and rooms used otherwise) must correspond to the quality of the load-bearing components of the storey. These must extend to the structural slab (in roof spaces up to the roof cladding).”

### K73 外墙及外墙饰面的燃烧性能

非承重外墙及承重外墙的非承重部分（建筑等级 1–3 除外）须用不燃（至少阻燃）材料建造；外墙饰面（含保温层及支撑构造）须用难燃材料；等级 1、2 的建筑如能有效防止火势蔓延至相邻建筑，允许外墙饰面采用普通可燃材料。

- **早期设计**：★★ · LOD 300
- **IFC**：`IfcWall`、`IfcCovering` · 还需要：性能属性（`Pset_*Common（FireRating, ThermalTransmittance, AcousticRating, IsExternal …）`）；构造层（`IfcMaterialLayerSet`）
- **页码**：p.514 (page_0526) · Building services
- **用到的题**（1 道，1 个模型）：`samuel-19`
- **知识探针题**（须 · recall）：Under German building regulations, for buildings other than those of building classes 1 and 2 (and below high-rise level), what minimum fire behaviour must the materials of external wall claddings, including insulation and support construction, have?
  - 标准答案：Flame-resistant (schwer entflammbar)
  - 选项：A. Normally flammable；B. Easily flammable if rendered；**C. Flame-resistant** ✓；D. Any material if sprinklered
- **原文**：
  - p.514：“Non-load-bearing external walls and non-load-bearing parts of load-bearing external walls are (except for buildings of building classes 1–3) to be constructed of non-combustible (at least fire-retarding) materials.”
  - p.514：“For buildings of classes 1 and 2, external wall claddings of normally flammable materials are permissible, if the spread of fire to neighbouring buildings is effectively prevented.”
  - p.514：“External wall claddings, including insulation and support construction, have to be made of flame-resistant materials.”

## 办公

### K147 立面竖梃与隔墙的连接

位于模数网格上的立面竖向型材应有足够宽度以连接隔墙；更好的做法是沿立面设置隔声型材；须注意窗的开启扇。

- **早期设计**：★★ · LOD 300 · 决定立面与采光
- **IFC**：`IfcCurtainWall`、`IfcMember`、`IfcWall`
- **页码**：p.240 (page_0252) · Administration and offices
- **用到的题**（0 道，0 个模型）：
- **知识探针题**（宜 · recall）：In German (DIN-based) office design practice: What requirement applies to the vertical profiles of an office façade that lie on the modular grid?
  - 标准答案：They should be wide enough to connect a partition
  - 选项：A. At most 50 mm wide to maximise daylight；B. Set back at least 20 cm behind the columns；**C. Wide enough to connect a partition** ✓；D. Thermally broken and at least F 30
- **原文**：
  - p.240：“Vertical profiles in the façade, which lie on the modular grid, should be wide enough to connect a partition.”
  - p.240：“A better solution is with sound-insulated profiles running along the façade.”

### K148 轻质隔墙的隔声与上下延续

轻质隔墙的节点要特别注意隔声；采用架空地板和吊顶时，要么让隔墙在竖向上延续，要么这些构件本身须具备隔声性能。

- **早期设计**：★★ · LOD 300 · 决定构造选型
- **IFC**：`IfcWall`、`IfcCovering` · 还需要：性能属性（`Pset_*Common（FireRating, ThermalTransmittance, AcousticRating, IsExternal …）`）；构造层（`IfcMaterialLayerSet`）
- **页码**：p.240 (page_0252) · Administration and offices
- **用到的题**（0 道，0 个模型）：
- **知识探针题**（须 · recall）：In German (DIN-based) office design practice: Where light partitions are combined with raised access floors and suspended ceilings, what must be provided to prevent sound transfer above and below the partitions?
  - 标准答案：Either the partitions are continued vertically (through floor void and ceiling void), or these elements are sound-insulating in themselves
  - 选项：A. Carpet throughout and acoustic plaster on the walls；**B. Vertical continuation of the partitions, or floor and ceiling elements that are sound-insulating in themselves** ✓；C. Double partitions with 40 mm mineral wool only；D. A 10 cm air gap above every partition
- **原文**：
  - p.240：“The junctions of light partitions demand particular attention to noise reduction.”
  - p.240：“With raised access floors and suspended ceilings, either vertical continuation of any possible partitions is to be provided or these elements are to be sound-insulating in themselves”

## 高层建筑

### K154 高层外窗的清洁

不能从室内安全清洁的窗面，须由受过训练的人员使用合适的设备从室外清洁。

- **早期设计**：★ · LOD 300
- **IFC**：`IfcWindow`、`IfcCurtainWall`
- **页码**：p.246 (page_0258) · Administration and offices
- **用到的题**（0 道，0 个模型）：
- **知识探针题**（须 · recall）：In high-rise building design practice: how must window areas be cleaned that cannot be cleaned safely from inside?
  - 标准答案：From the outside, by trained personnel using suitable apparatus
  - 选项：**A. From the outside by trained personnel using suitable apparatus** ✓；B. They are not permitted above 22 m；C. They must be designed as fixed self-cleaning glazing；D. From inside using extendable tools only
- **原文**：
  - p.246：“Window areas which cannot be cleaned safely from inside, must be cleaned from the outside by trained personnel using suitable apparatus”

# 已归档：32 个

范围核对时标为“待定”或“不在范围”的知识点。它们不进入上面的清单和 `knowledge_probes.jsonl`，探针题保存在 `knowledge_probes_archived.jsonl`。要恢复某一条，把 `knowledge/_scope.json` 里它的 label 改成 `in` 再重新生成。

| 知识点 | 标注 | 层级 | 主题 | 内容 | 优先级 | 页码 |
|---|---|---|---|---|---|---|
| K02 | 待定 | Site & Building | 场地与体量 | 私宅停车 | ★ | p.166 |
| K03 | 待定 | Site & Building | 场地与体量 | 车位与通道尺寸 | ★★ | p.390, p.392, p.400 |
| K04 | 待定 | Site & Building | 场地与体量 | 体形系数 A/Ve | ★★★ | p.474 |
| K54 | 不在范围 | Site & Building | 采光、日照、通风与窗 | 办公与工作建筑的朝向 | ★★ | p.241, p.266 |
| K111 | 不在范围 | Site & Building | 住宅·卧室、卫浴与储藏 | 婴儿车与自行车公共储藏间 | ★★ | p.165, p.464 |
| K31 | 待定 | Space | 无障碍 | 轮椅停车位 | ★ | p.22 |
| K49 | 待定 | Space | 采光、日照、通风与窗 | 厨房朝向 | ★ | p.149 |
| K50 | 待定 | Space | 采光、日照、通风与窗 | 无窗厨房 | ★★ | p.149 |
| K75 | 待定 | Space | 居室标准与面积计算 | 厨房作为居室 | ★★★ | p.149 |
| K84 | 不在范围 | Space | 住宅·户型组织与入户 | 设备噪声与安静房间 | ★★ | p.480, p.481 |
| K86 | 待定 | Space | 住宅·户型组织与入户 | 卧室朝向与位置 | ★★ | p.157 |
| K88 | 不在范围 | Space | 住宅·户型组织与入户 | 防风门斗 | ★ | p.146, p.147 |
| K95 | 不在范围 | Space | 住宅·厨房与就餐 | 厨房宽度与操作空间 | ★★★ | p.149 |
| K96 | 不在范围 | Space | 住宅·厨房与就餐 | 厨房面积与类型 | ★★ | p.150 |
| K97 | 不在范围 | Space | 住宅·厨房与就餐 | 开放式厨房 | ★ | p.150 |
| K98 | 不在范围 | Space | 住宅·厨房与就餐 | 厨房位置 | ★ | p.149 |
| K99 | 不在范围 | Space | 住宅·厨房与就餐 | 就餐区的朝向与连接 | ★★ | p.154 |
| K100 | 不在范围 | Space | 住宅·厨房与就餐 | 餐桌尺寸与就餐人数 | ★ | p.154 |
| K101 | 不在范围 | Space | 住宅·厨房与就餐 | 储藏与食品间靠近厨房 | ★ | p.162 |
| K102 | 待定 | Space | 住宅·卧室、卫浴与储藏 | 卧室最小面积 | ★★★ | p.157 |
| K104 | 不在范围 | Space | 住宅·卧室、卫浴与储藏 | 没有洗衣间时 | ★★ | p.161 |
| K105 | 不在范围 | Space | 住宅·卧室、卫浴与储藏 | 洗衣间 | ★ | p.163 |
| K106 | 待定 | Space | 住宅·卧室、卫浴与储藏 | 衣柜的位置与通风 | ★ | p.159 |
| K108 | 待定 | Space | 住宅·卧室、卫浴与储藏 | 卫生间朝向、采光与通风 | ★★ | p.145, p.160 |
| K110 | 不在范围 | Space | 住宅·卧室、卫浴与储藏 | 卫浴与厨房共用管井 | ★★ | p.160 |
| K21 | 待定 | Element | 门 | 洞口尺寸 ≠ 净通行宽度 | ★★ | p.114 |
| K51 | 待定 | Element | 采光、日照、通风与窗 | 玻璃面最小高度 1.3 m | ★ | p.97 |
| K55 | 待定 | Element | 采光、日照、通风与窗 | 按朝向选择遮阳 | ★★ | p.500 |
| K56 | 待定 | Element | 采光、日照、通风与窗 | 遮阳挑檐的出挑计算 | ★ | p.500 |
| K62 | 待定 | Element | 围护结构与保温 | 热桥与构件连接 | ★★ | p.473, p.474 |
| K64 | 不在范围 | Element | 围护结构与保温 | 平屋面构造：暖屋面与倒置屋面 | ★★ | p.92 |
| K71 | 待定 | Element | 墙体与构造 | 地下室墙体与楼板耐火 | ★★ | p.514, p.515 |

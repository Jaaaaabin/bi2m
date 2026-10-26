# 知识 → 规则 → IFC 实例：试点

目的：验证 `knowledge/KNOWLEDGE.md` 里的知识点能不能改写成 **context → 设计要求** 的规则形式，再在 `data/ifc_bench/fantasy_office_building_1/arc.ifc` 里找到这些规则的实例。本目录只是试点，先做 12 条规则、12 个实例。

- `rules_pilot.jsonl` — 12 条规则（由 19 个知识点合并而来），每条带 Neufert 原文，30 条引文全部与 `embeddings.sqlite` 逐字核对一致（同 `knowledge/tools/exact_check.py` 的标准）。
- `rules_office.jsonl` — 第二批：**35 条办公楼规则（R13–R47，111 条原文）**，由 `build_rules_office.py` 生成，脚本在写文件前把每条引文和 `embeddings.sqlite` 逐字核对，不一致就不写。只做了知识 → 规则，还没映射到 IFC。覆盖范围：办公楼章节（书 p.231–243）全部可规则化的内容，加上一个 5 层学生办公楼模型会碰到的通用章节——退距、防火分区与建筑等级、疏散路线与距离、必要楼梯的限值与楼梯间、无障碍（电梯、坡道、入口、走廊）、工作场所厕所布置、窗面积、门洞模数、平屋面、隔墙与吊顶。第二遍扫库（conversion、车库、医院等提到 office 的页）没有再找到适用的早期设计硬规则。
- `instances_fantasy_office_building_1.jsonl` — 12 个实例：规则的 context 在这个 IFC 里具体是哪些实体、推导出的数值、判定结果和证据（GlobalId / 属性 / 数值）。

## 1. 规则的形式

每条知识拆成五个部分：

| 字段 | 含义 | 例（R06 护栏高度） |
|---|---|---|
| `context.entity` | 规则作用在哪类 IFC 实体上 | `IfcRailing` |
| `context.match` | 进入规则的前提（实体自身属性、所属建筑/房间的用途） | 护栏有防坠功能 |
| `context.derive` | 需要从模型推导、但不直接存在实体上的变量 | `drop` = 护栏所在楼面 − 下方楼面；`h` = `Pset_RailingCommon.Height` |
| `condition` | 触发条件（可为 always） | `drop ≥ 1 m` |
| `requirement` + `params` | 要求，参数化 | `drop < 12 → h ≥ 0.90；drop > 12 → h ≥ 1.10；工作场所 → 1.00` |
| `modality` | must / should / typical（沿用知识库） | must |
| `basis` | 书页 + 原文 | p.122 “drop <12 m, h = 0.90 m” … |
| `ifc_needed` | 检查时要用到的 IFC 数据 | Height、楼层关系 |

几个观察：

1. **“一条知识”往往不是一条规则，而是一个 context 分支树。** K112 净高一条就拆成三支（办公 2.75 / 坐姿 2.50 / 走廊卫生间 2.30），分支变量是房间功能。K15 护栏按坠落高度分三档。规则形式比问答形式更能暴露这种结构。
2. **反过来，几条知识常要合并成一条规则才可检查。** 楼梯的 K09（≤18 步）、K10（层高 ≥ 2.75 须设平台）、K20（平台宽 ≥ 梯宽）作用于同一个 `IfcStair`，共用同一组推导变量，合成 R04 更自然；K07（2r+t 公式）单独看会放过 20/20 的 45° 楼梯，必须和 K11 的 17/28 一起用（见 I03）。
3. **条件变量大多不在实体自己身上。** 12 条规则里只有 R03（踏步比）和 R07（门尺寸）能只看实体属性判定；其余都要楼层标高差、房间功能、房间里的家具数、墙的材料集、建筑用途（IFC 里根本没有，来自 model_card）。这决定了第 3 节的表达方式选择。
4. **modality 必须保留。** R09 工位面积（should/typical）不满足只是“偏紧”，R04 没平台（must）是违规；LLM 判题时要区分。

## 2. 在 fantasy_office_building_1 里的实例

| # | 规则 | context 在这个模型里是什么 | 推导值 | 结论 |
|---|---|---|---|---|
| I01 | R01 高层判定 | 5 层，最高有人楼层 OG4 标高 19.2 m | H_top = 19.2 ≤ 22 | 不是高层，规则不触发 |
| I02 | R02 办公净高 | 44 个 IfcSpace 的 `Qto_SpaceBaseQuantities.Height` | 全部 2.75 m；层高 4.8 − 板 0.41 留 1.64 m 技术空间 | **pass**，和 Vst 的 2.75 完全对上，连“留给架空地板和吊顶”的理由都对上 |
| I03 | R03 2r+t | 14 段梯段，r = 20 cm，t = 23.5 或 20 cm | 63.5 / 60.0 cm | 公式 pass，但 r=20 偏高，20/20 的四段坡度 45° |
| I04 | R04 平台与步数 | 每个 IfcStair = 1 段 Run + 2 扶手，无 LANDING；层高 4.8 | 24 步一口气 4.8 m，无平台 | **fail**（平台 must；18 步 should） |
| I05 | R05 梯宽与扶手 | 直跑梯段包围盒短边 1.54 m；每梯 2 个 IfcRailing | w = 1.54 ≥ 1.00；n_rail = 2 | 宽度与扶手 pass，踏步比不合 17/28 |
| I06 | R06 护栏高度 | 28 个 Holzhandlauf，`Height` = 1.2192 m（4 ft） | 最严档 1.10（OG3 处 drop 19.2 m） | pass；设计用了一刀切的高值 |
| I07 | R07 门 | 28 扇内门 0.885 × 2.26；入口门 2.34 / 2.50 宽，±0 无台阶 | 高 2.26 ≥ 2.10；宽 0.885 < 0.90 | 高度 pass，**无障碍净宽 fail**；入口 pass |
| I08 | R08 混凝土外墙保温 | 14 面外墙类型 `STB 20.0/25.0 WD 12.0`，材料集含 `Wärmedämmung - Hart` + `StB - Ortbeton` | has_insulation = True，总厚 0.37 | **pass**；内墙 `STB 25.0` 无保温且非外墙，也一致 |
| I09 | R09 每工位面积 | 4 个放了桌子的 Working Space：34.9 m²/6–7 桌，53.5 m²/8 桌 | 5.0–6.7 m²/工位 | **fail**（书 11–15） |
| I10 | R10 采光进深 | 两条 3.58 × 31.26 的办公长条贴幕墙，两端 4.26 m 进深；中间 14 m 无房间（中庭） | d = 3.58 / 4.26 ≤ 7 | pass；整楼 22 m 进深不适用 12–13 m 的中廊经验值 |
| I11 | R11 工作场所厕所 | 30 桌 > 5 人；每层有 WC 房；10 WC + 10 洗手盆 + 2 小便器 | 洗手盆/WC = 1 ≥ 1/5；每层有 WC | 距离、洗手盆 pass；**男女分设 unknown**（IFC 无此属性） |
| I12 | R12 会议区 | 2 间 16.34 m² 会议室，家具族名 `- 8 Stühle` | 2.04 m²/座 | 略低于 2.5（typical） |

值得注意的三个点：

- **I02 和 I08 是“正向实例”**：模型的取值和书上的推荐值精确一致（2.75 m；混凝土 + 保温），而且 IFC 里能找到设计者这样做的原因所需的全部 context。这类实例最适合做“intent”题：问“为什么净高是 2.75 而不是 2.50”。
- **I04、I07、I09 是“负向实例”**：规则 context 完全满足，但设计不满足要求。做 diagnosis 题。
- **I11 的 unknown 很重要**：规则需要的变量（男/女）IFC 没有标准表达。规则的 `ifc_needed` 字段就是用来提前暴露这种缺口的；整个知识库里 `needs = zone / adjacency / transport` 的知识点都有同样问题（见 KNOWLEDGE.md 的“检查时需要的 IFC 数据”表）。

这个模型里**没有** `IfcRelSpaceBoundary`、`IfcZone`、`IfcGrid`、`IfcMaterialLayerSet`（Revit 导出成了 `IfcMaterialConstituentSet`，没厚度）。所以“家具在哪个房间”“房间哪一面是外墙”“保温层多厚”都是我用几何包围盒或类型名推出来的，不是模型里直接写着的。

## 3. context 用什么表达

三个候选：原始 IFC、ifcJSON、图。我的建议是**图作为规则匹配层，IFC 作为事实来源，两者之间用一个固定的抽取器**；不要用 ifcJSON。理由：

**原始 IFC（STEP）不行，不是因为格式，而是因为密度和缺失。** 这个 13 MB 的文件里 828 个 `IfcMember` + 453 个 `IfcPlate` 是幕墙杆件，和任何一条规则都无关；而规则真正需要的关系——房间邻接、房间里有什么、墙是不是围着这个房间——要么没导出，要么要跑几何才能得到。把 IFC 直接喂给 LLM，它要在噪音里找不存在的边。

**ifcJSON 只是换了语法。** 它 1:1 对应 IFC 实体和 `#123` 引用，密度问题和缺失问题一个都没解决，还更长。它的唯一好处是 LLM 读起来比 STEP 顺一点，但那是 token 层面的问题，不是信息层面的。

**图合适，因为规则的 context 本身就是一个子图模式。** 看 12 条规则的 `context` + `derive`：

```
R06:  (Railing)-[:IN_STOREY]->(Storey{elev})  ,  (Storey)-[:ABOVE]->(Storey{elev'})      → drop
R09:  (Space{function:office})-[:CONTAINS]->(Furniture{kind:desk})                         → n_ws
R08:  (Wall{external})-[:HAS_MATERIAL]->(Material{category})                               → has_insulation
R10:  (Space)-[:BOUNDED_BY]->(Wall|CurtainWall{external})                                  → 采光面
R04:  (Stair)-[:AGGREGATES]->(StairFlight{n_riser}) , (Stair)-[:AGGREGATES]->(Slab{LANDING})
```

每条规则 = 一个 match 模式 + 对绑定变量的条件。这正是图查询（Cypher / SPARQL / SHACL）的形状；实例就是一次匹配的绑定结果。KNOWLEDGE.md 已经按 BOT 的 Site → Building → Storey → Zone → Space → Element 分层，BOT 本身就是图本体，接上很直接。

具体建议的图结构（不必上三元组库，一个 JSON 的节点列表 + 边列表就够）：

- **节点**：只保留规则会碰到的实体类型（Site, Building, Storey, Zone, Space, Wall, CurtainWall, Slab, Roof, Door, Window, Stair, StairFlight, Railing, Column, Furniture, SanitaryTerminal, Material），每个节点带 `GlobalId`、少量属性（Pset 里规则用到的那几个 + Qto）、以及包围盒。幕墙杆件、面板、洞口不进图。
- **边**：IFC 里现成的（`containedIn`, `aggregates`, `hasMaterial`, `hasType`, `fills/voids`）直接搬；IFC 里没有但规则需要的（`space CONTAINS furniture`, `space BOUNDED_BY wall`, `space ADJACENT space`, `storey ABOVE storey`, `space HAS_EXTERNAL_FACE`）由抽取器从几何推导，边上标 `source: derived` 以区分“模型里写了”和“我们算出来的”。
- **建筑级事实**（用途 office、公众可达、建筑等级）IFC 里没有，作为 Building 节点属性由 model_card 注入，同样标 `source: model_card`。
- **给 LLM 的输入**不是整张图，而是按规则 context 切出来的**子图卡片**：对 R09 就是“Space 6 + 它的 6 张桌子 + 面积”，对 R06 就是“这根护栏 + 它所在楼层 + 下方楼层”。这就是 `instances_*.jsonl` 里 `context_instance` 字段现在的样子，只是我手写的；下一步应该由抽取器自动生成。

这样做还顺便回答了一个问题：**哪些知识在哪些模型上可检查**，就等于“这条规则的 match 模式在那张图上有没有非空匹配”，可以自动算，取代 KNOWLEDGE.md 里手工维护的 `models` 字段。

一个保留意见：如果最终目的是**探测 LLM 是否能直接读 BIM**（而不是读我们整理好的图），那原始 IFC 或 ifcJSON 作为对照组仍有价值——用同一组实例，分别给“子图卡片”和“IFC 片段”，看准确率差多少。图是 ground truth 的组织方式，不必是唯一的 probe 输入。

## 4. 全量知识 → 规则（2026-10-20）

`rules_general.jsonl`（R48–R103，56 条，94 条原文，`build_rules_general.py`）把剩下的知识点也改成了规则：住宅、无障碍、高层、围护与屋面、面积与体积计量、模数。至此 122 个知识点里 119 个进入了 103 条规则；只有 3 个没转——K139（可逆办公楼“主要适合出租给未定租户”）、K146（全空调建筑体积 ×1.3–1.5）、K138（非固定工位省 20–50%）都是描述性陈述，没有“在什么 context 下该怎么设计”的结构。

**context 的抽象问题**是这一轮的主要改动。书里的前提常常是“必要楼梯”“疏散走廊”“一户”“公众可达”“使用单元”，IFC 里一个都没有。R48 起每条规则多了两项：

- `context.grounding`：match / IF 里每个抽象概念在图上怎么读出来。例如“必要楼梯”= 连接各层且通向出口的 IfcStair，户内附加楼梯除外；“走廊”= 名含 corridor/Flur，或长宽比 > 3 且 opensTo ≥ 3 扇门的 IfcSpace；“一户”= IfcZone，或由户门划分的房间组。
- `context.concreteness`：`direct`（IFC 属性 / Pset 就有，8 条）、`derived`（抽取器从几何或关系算，43 条）、`external`（IFC 没有，要靠 model card / 任务书，5 条：地块面积、人数、租户、房间用途）。external 的规则在实例里只能写 `unknown`。

另有几条是**计量规则**而非判定规则（R48 容积率口径、R49 DIN 277 分类、R50 体积量法、R66 居住面积、R82 卫生间类型、R98 U 值）：它们定义后续规则用的量怎么算，verdict 是“能否按口径算出”。

## 5. 第二个模型：ifc4_0204

`data/model_ifc4_0001-0370/` 里的 370 个匿名 IFC4 模型中，按房间名选了 **0204**（Revit 25 导出，16 MB；6 层，159 个 IfcSpace，20 部楼梯，318 扇门，1081 件家具；房间名 Office / Outer office / Open-plan office / Conference / Tea kitchen / Bathroom / Stairs / Storage / Hall）。

- `extract_graph.py` 跑出 `runs/graphs/ifc4_0204.json`：2270 节点、6717 边、81 s。这个导出没有 Qto，房间面积用网格体积 ÷ 高度算；IfcSpace 只在 Level 1–3，入口层和地下室没有房间。
- `build_instances_0204.py` → `instances_ifc4_0204.jsonl`：103 条规则每条一个实例。18 pass、12 fail、14 mixed、11 unknown、48 not_applicable（住宅 24、高层 8、其他 16）。
- 值得看的判定：净高 2.75 又是精确的 Vst 值（R02）；楼梯 2r+t = 65.7、踢面 19.37 cm 双双超限 0.4–0.7 cm（R03、R25）；两个 258/274 m² 的大开间和 5 间“Outer office”完全没有窗（R10、R36、R38）；办公室窗宽只占房间宽 37–49%（R39）；600 m² 环形 Hall 是唯一疏散走道，150 m 无分段门且放了沙发组（R65、R87）；卫生间入口门 0.585 m（R07）；旋转门之外只有一扇 1.81 m 的出口（R43）；5 个楼梯间、最远 24 m（R22、R23 pass）；17 部电梯是 IfcBuildingElementProxy，Level 1–3 没有电梯门（R27）。
- 映射时暴露的落地问题正是 grounding 要解决的：这里的“疏散走廊”不是细长房间而是一圈大厅；“工位”要数 Furniture_Desk；“电梯”不是 IfcTransportElement；“用途”“单元”“地块”完全缺失。

## 下一步

1. 把 `grounding` 写成可执行的图模式（先做 derived 类 43 条），规则 × 图自动产出实例表，用 0204 的 103 条手写实例当测试集。
2. 对 370 个模型批量跑抽取器（每个 1–2 分钟），按“哪些模式有非空匹配”给模型分组，挑住宅模型去跑 R51–R81。
3. 从实例生成 compliance / diagnosis / intent 三类题。

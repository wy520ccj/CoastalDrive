# 环境重做：游戏参考、失败与下一段实机样板

2026-10-23。用户再次明确否定“又空又丑还散”“草像随机放放了一坨坨屎”。这是当前美术结论，不以自动测试覆盖。

## 实际查看的游戏与作者资料

以下为浏览器实际打开的游戏画面与一手作者资料，不是只读搜索摘要；第三方图片仅在线审看，未拷入游戏或冒充本项目资产。

| 参考 | 实际看到什么 | 采用到本项目的工作方法 |
|---|---|---|
| [FH5 乡野，场景构图作者 Litha Bacchi](https://lithabacchi.artstation.com/projects/GablEQ)；查看作者第3张 Farmlands 图 | 公路近处是泥土、碎石和连续短草，灌木连接农田边界；中景田块有大面积结构，树和电塔引导道路向远处延续 | 先定义地块、边界、视线与地标，再布置小植物；公路边不铺一排分离的盆栽式草团 |
| [Motorfest 草甸，植被作者 Théa Dorangeon](https://salemium.artstation.com/projects/aoXoG8)；查看 Fields 02 图 | 草甸形成连贯的低层覆盖，较高开花植物和灌木从中长出；主树冠、远山、建筑有明确前中后层次 | 先制作能连成面的低矮地被；灌木与树根、林缘和裸地相关，不能独立生成黑色孤岛 |
| [art of rally 官方商店截图](https://store.steampowered.com/app/550320/art_of_rally/)；查看弯道、草坡和针叶林截图 | 简化模型仍用整片草坡、成组林带、观众和房屋组织弯道；色块和树冠轮廓足够明确 | 学习预算受限时的构图与轮廓控制，保留本项目现有车辆/天空方向，不因此改成另一套低模风格 |
| [Playground Games 在 Adobe 的 FH5 制作访谈](https://www.adobe.com/products/substance3d/magazine/forza-horizon-5-crafting-rich-and-diverse-mexican-biomes.html)；展开 Processing Scans of Local Mexican Foliage | 作者展示叶片采集，以及底色、法线、粗糙度、AO和透明轮廓的统一来源 | 同一植被的材质通道和叶片轮廓一起核对；不能只追求三角面数更低 |
| [Motorfest 材质作者 Maximilien Fouchou-Lapeyrade](https://maximilienfl.artstation.com/projects/dKxPwK)、[Ubisoft 的 Maui 说明](https://www.ubisoft.com/en-gb/game/the-crew/motorfest/news-updates/5eP8hUuQc2dnmLiAyHMF7q) | 作者明确负责地表、植被图集、群落结构与材质一致性；Maui 使用不同区域和可辨识地标组织道路 | 地表、植物、地形共同定义一条路线的身份，不靠更换随机种子区分地图 |

上表的构图分析与实施取舍是本项目的观察和决定，并非声称移植上述游戏的资产或渲染技术。

## 本轮候选为什么不接受

1. Tree Small 02 整株面内简化仍有166.9万/104.1万/67.1万三角面，拒绝直接接入。
2. 整株大角度溶解会吞掉闭合薄叶，Island Tree 候选变成秃枝。改为只溶解枝干、按完整叶簇抽稀后，源叶形保住，但实机仍显空、叶簇过大且风格不统一。
3. Bermuda 17/12三角面源草及按20m小片合批的密度实验，实图仍是断开的暗团和细杆。增加数量未解决植被与地表脱节，拒绝把该方案当运行版改进。
4. 新赛道接地实验发现装饰可生成到地形覆盖范围外；复现与修正证明了问题，但整套随机群落方案已撤出运行版，接地扩展也未保留为无调用代码。

原生产树/草/BAM/制作脚本恢复到本轮基线。候选二进制和记录保留在 `logs/play-repair-art-rejected-r7/`，固定机位图在 `logs/play-repair-art-r4/`、`r6/`、`r7/`；路线图在 `logs/play-repair-course-art-r5/`、`r6/`、`r7/`。独立制作脚本 `tools/blender/prepare_vegetation_candidate.py` 与 `tools/environment/pack_vegetation_candidate.py` 只写 `art/expressway/candidates/`，不覆盖生产资源。

地表法线/粗糙度、米制UV和多尺度混合也曾作为材质候选；用户再次指出实机没有按设计落地后，相关运行代码一并撤出。来源输入和实验记录保留，不能写成最终画面改进。天空及环境光资源不改。

研究三款游戏的实际画面后，使用内置 imagegen 生成[24沿海设计图](../../design/garage-v2/24-coastal-environment.png)，[完整提示词](../../design/garage-v2/24-coastal-environment-prompt.txt)保留。它把左侧林缘/岩坡、右侧草甸/海湾与连续近地覆盖组织在同一驾驶构图中，作为接下来制作的方向。生成图也改变了部分车辆细节、画面尺寸和天空像素，不能据此覆盖已认可的天空、车辆、HUD或物理；只提取护栏外的景观组织，最终必须回到实际镜位比较。用户尚未接受此设计，不称实机效果。

## 验证账本

- 初次T0在Ruff导入排序处失败，修正后第二次38过2失败：旧断言写死树木2档，新树为3档；另一次树根简化后偏离2.5mm。均保留日志。
- 候选接地边界/叶簇修复后的T0 42项通过；第一次完整相关T1 76项和三种子通过，路径 `logs/validation/PLAY-REPAIR-01-art-T1/`。
- 撤回模型、保留地表并把草量降回试验档后的完整T1再次76项和三种子通过，路径 `logs/validation/PLAY-REPAIR-01-art-final-T1/`。用户再次否定随机散布后，进一步撤销新增群落/接地代码及其2项测试；该T1是撤出前候选的结果，不能写成最终场景的人工验收。
- `check_surface_materials.py` r4/r6/r7均完成240个真实新驾驶步，GPU材质未报编译错误；之后相机采集固定快照。路线r5/r6/r7仅各132初始化步，0新驾驶步。r4路线采集因地形覆盖范围外KeyError失败，日志保留；r5漏选决赛ID，r6/r7补齐。
- 当前没有完成正式实时性能Gate、长期撞击、用户驾驶趣味性或视觉通过。生产树/草模型恢复到本轮起点，弃用候选与最终运行资源分开记账。

## 下一段样板：沿海组合弯 0–240m

先做一个能在普通驾驶视角成立的连续场景，不先全图铺设。

- 空间：一侧林带与岩坡形成连续背景，另一侧低草坡逐渐打开海景；不要让两侧都是空白黄绿色山包。
- 路肩：道路外窄土带与4–12cm短草连续过渡；高草只用于坡脚或排水沟，不沿路等距摆成一坨坨。
- 林缘：树冠有重叠的整体轮廓，灌木填接林下；保留原碰撞树干和行车/弯心视线。树种、叶色与地被属于同一套环境。
- 地面：泥土、短草、叶屑与岩脚有连续过渡和明确尺度；避免只在一张平铺底色上加孤立道具。现有正常驾驶和固定碰撞不能被美术修改暗中影响。
- 节奏：起点林缘框景 → 弯前开阔草坡/海湾 → 出弯可记忆的岩体或道路设施。草木服从这三个空间，而不是以seed决定整个场景。
- 实机验收：普通追车镜位先看整体，再看路肩近景和弯道中景；必须同时有前后同机位图与真实短驾驶。概念图、源资产预览和T1均不能代替。

样板成立后再分路线深化：沿海组合弯强调开阔海岸/低草坡，山脊回头弯强调岩坡/林带/高差，决赛按路段组合并加入可记忆节点。三条路不能继续只换弯向、换seed或换计时。

## 24样板再次失败后的纠正

用户明确追问设计图和新规则执行情况。事实是：案例和图24已具备，但源草实际是稀疏细茎，源树轮廓/密度也不匹配图24。把它们缩小、增加数量和染亮，没有完成“按图选资源”；r1细碎暗线、r2亮色草线均未达标，不能再解释为只有精细度差一点。

本次两版均有240个实际新驾驶步及相机图，路径 `logs/play-repair-coastal-sample-r1/`、`r2/`。新增T0仅到Ruff失败，未进入pytest，不报通过。当前已将样板代码、网格、打包工具、地表候选代码归入 `logs/play-repair-coastal-sample-rejected/`，运行文件恢复到本轮HEAD `d757ddd8`；未撤销已提交的碰撞、无限高速、赛事路线与车库改装。

下一动作回到资源筛选：以图24的饱满树冠、成片多草叶地被、沿坡裸岩和真实岸线为逐项匹配要求。先核对单件真实外形/材质/尺度和组合效果；不再以“现成且能加载”作为选中理由，不再直接把旧资源铺进场景。已向用户展示图24，明确其为设计目标而非实机。

## 资源筛选与本机《天国：拯救2》研究

用户指定《天国：拯救》系列作为自然环境参考，并提供本机安装目录 `D:/SteamLibrary/steamapps/common/KingdomComeDeliverance2`。安装目录只读；本项目只记录方法与证据位置，没有把其模型、贴图或关卡转入生产资源。

### 实际检查的本机证据

| 位置 | 已核实事实 | 对本项目的决定 |
|---|---|---|
| `Engine/Engine.pak::Config/CVarGroups/sys_spec_Vegetation.cfg` | 存在合并网格、植被LOD、HLOD切换距离、地形颜色取样距离和渐隐参数；默认配置启用合并网格渐隐 | 从近到远组织草面、完整树冠、林带整体轮廓；不让远景只剩裸山或孤立树点。参数含引擎相关比例，不能照抄数值当作米 |
| `Data/IPL_Objects-part4.pak::Objects/natural/vegetation/grass/grass_groups/grass.mtl` | `Vegetation`材质，含`BLENDTERRAIN`、`VERTCOLORS`、法线及透光通道；底色/法线/反射/透光各有地形混合控制 | 草根、地面和草叶共用连续的宏观颜色；保留根部遮蔽与叶端光照差异，不能靠把整簇染亮解决 |
| 同包 `plants_grass_merged_diff.dds` 与流送mip | 原图8192×8192；实际查看1024×1024的源mip。图集包括低草、高草、干草、阔叶草本与花，不是单棵细茎反复复制 | 草甸以低草成面，少量高草/花形成变化；资源先有足够连续的多叶轮廓，再考虑数量和合批 |
| `Data/IPL_Objects-part5.pak::Objects/natural/vegetation/trees/normal_trees/quercus_robur/quercus_robur.mtl`及`quercus_atlas_diff.dds` | 原图4096×2048；实际查看1024×512的源mip。叶图集是带枝干的完整枝簇；近中距离材质共用该图集，并分离树皮、叶、阴影代理和LOD | 采用保留枝簇外形的叶卡/烘焙方案，而不是对整株薄叶大幅减面；树的近中远轮廓必须一致 |
| `Data/IPL_GameData.pak::Libs/vegetation/mastervegetationobjects.vgo` | 606个主植被定义；`grass_green_a`启用`AutoMerged=1`、`UseTerrainColor=1`、`GlobalIllumination=1`，其单体投影关闭 | 用低成本合批覆盖草面，把主要投影预算给车、树冠、岩体；不能为每棵小草重复构造独立大型节点 |
| `Data/IPL_GameData.pak::Materials/terrain/forest/forest_beech_oak.mtl` | 独立林地地表材质，使用4m尺度底色、法线、位移及软深度过渡 | 林下与开阔草坡应有不同地表；先组织完整地块和过渡，不能同一草底纹铺遍所有区域 |
| `Data/Levels/trosecko`和`kutnohorsko` | 都有独立`hlod_vegetation.pak`及分区`merged_meshes_sectors` | 远处树林应有整体表示，近处细节逐步接入；分区应服务视觉连续性和已有生命周期 |

以上是本机文件事实及本项目据此作出的推论，不声称已复现其引擎或完整制作流程。局部参考图仅在忽略目录 `logs/play-repair-kcd-research/local-reference/`，未加入仓库。DDS查看只选择现成流送mip，在内存中调整预览头以交给标准BC3解码器；源文件未修改。没有启动或操控用户游戏，也没有加载或修改其存档。

同时读取作者的一手说明：[Petr Sušanka的Nebakov Nature](https://petrsusanka.artstation.com/projects/6LxVJw)说明当地将密林、草甸、砂岩和湿地围绕湖泊组织；[Rattay环境作者](https://siriusbudha.artstation.com/projects/aRVV20)区分农田、小路、崖壁、河岸和森林；[Crytek对Warhorse的访谈](https://www.cryengine.com/news/view/achieved-with-cryengine-kingdom-come-deliverance-launches-today)明确提到植被与SVOTI间接光。后者说明“贴图也能好看”并不等于只换贴图即可：空间组织、材质与光照要共同成立。

本轮浏览器控制后来被Work设置禁用，未继续操控浏览器或使用其他方式绕过；上述作者页面是文字资料，不声称已通过该入口查看完整画廊。搜索命中的GDC2018《Procedural World Generation》实际是Ubisoft/Far Cry 5资料，**不归为Warhorse制作证据**。

### 可用于本项目的候选与预览

1. 实际查看LOLIPOP的9款草和17款橡树原始预览。草的多叶轮廓与专门制作的树木LOD值得研究；下载入口要求登录，未取得源件，不能列为已接入。OpenGameArt的TeKniKosCave草片叶形粗直，与图24不符，排除。
2. 取得Daniel Greenheck的EZ-Tree官方网页导出`Oak Large/seed 23399`及三档模型：22566/9240/5364三角形；同时保留预设。取得同作者仓库MIT草簇（6三角形）及花、可编辑草源文件，树皮来自ambientCG/CC0；完整许可和固定仓库修订`dcf309bd86bd521083d9c70f01f2de45fdc7c457`保存在`art/expressway/sources/ez-tree/`。当前橡树冠形偏窄、纵向尖，**不能直接当作图24的沿海主树**；可用于技术预览和后续枝簇制作研究。
3. 实际查看并取得Poly Haven的`coastal_cliff_01`及`coast_rocks_01`完整2K扫描、法线及ARM；来源和SHA见`art/expressway/sources/coastal-scans/manifest.json`。它们分别是约92m的连贯崖壁和59.5m的岩岸，而非散放的小石块；尚需制作适合本机预算的距离档及完整接地。
4. `tools/environment/preview_coastal_sources.py`仅建立离线预览，保留同一游戏天空/太阳/反射和固定物理快照。r1查看原树三档、草近远景、岩体，发现草片法线使同簇明暗割裂、间距露底。r2在渲染线程运行时修改候选顶点后停滞，三张树图后无草图，进程CPU两次均为18.328125秒；终止本工具进程，不报完成。r3仅将**预览工具**设为单线程并释放顶点写入器，完整完成7张图，源草的WebP通道转换为兼容PNG，向上受光与更密重叠消除了明显独立暗团。r3草仍过于同色、像平毯；树冠仍偏窄，均不判最终景观通过。
5. 最终r3：`logs/play-repair-source-review/render-r3/summary.json`，0新驾驶拍，仅初始化后固定快照原件审看；工具Ruff通过。没有生产行为变更，未重复物理T0/T1。原生模块、认可的天空、间接光和原生产植被SHA均与冻结账本相同。

下一块应将本机研究转成完整样板：按图24先确定林缘/岩岸/地被共同的颜色与空间关系，使用带枝叶簇的树冠素材和多种连续低草图集，草根与真实地表颜色/遮蔽同步；先用普通追车视角及30–150m中景判断整体，再看近景。单件预览、下载和研究均不等于已经完成运行场景，总目标继续active。

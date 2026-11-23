# 随车视角环境重建证据

2026-10-24；任务[ENV-REAL-01](../../tasks/ENV-REAL-01.md)。本轮基线 `15c321f5`，所有输出为本地候选，未提交/推送，非人工接受结果。

## 来源和设计

先看作者完整场景，再自行生成[26](../../design/garage-v2/26-coastal-rebuild.md)和[27](../../design/garage-v2/27-driving-view-environment.md)。27针对用户澄清后的正常随车视角，草树地石在约10–100m共同构图，远山只承担背景。

KCD2原件安装 `D:/SteamLibrary/steamapps/common/KingdomComeDeliverance2/Data` 全程只读；`local-source.json`、`local-shrub-source.json`、`original-environment.json`、`driving-meadow-source.json`记录实际来源和网格SHA。原件/解码PNG/环境探针只在ignored logs。HD2安装只读确认DSAR包，未取得可用网格，不称移植HD2资源。可分发的短岩坡来自已登记CC0 Poly Haven扫描，源URL/作者/校验在 `art/expressway/sources/coastal-scans/manifest.json`，加工记录在 `art/expressway/candidates/driving-rocks/source.json`。

## 普通随车画面与真实物理

命令：`.venv/Scripts/python.exe tools/environment/check_driving_composition.py --output logs/visual-upgrade-20261024/<独立目录>`；`--baseline`载入开始时保存的失败本地候选，比较控制器/路线/物理相同。车从静止由ViewDriver经原Control/Simulation驶入组合弯，未模拟键盘、瞬移、时缩或关碰撞。每次450m运行4505个新增120Hz物理步、568个显示帧，六个距离取景，0碰撞。逐拍记录 `actual-driving.json`，取景位置/镜头/FOV见 `summary.json`。这不代表人工驾驶或实时帧率验收。

`r15-driving-baseline`是HUD排版修正后的基线；`r16-driving-composition`是短岩坡/树尺寸修正后的首个完整候选。`r17-driving-ground`开始取消整坡单侧枯土地表，改为实际树冠下混林地底色。仍有草层终止后大面积浅色坡面、树组孤立、岩坡不充分的问题。

## 失败和复用边界

所有原目录保留在 `logs/visual-upgrade-20261024/`，不覆盖：

- r1/r2草木发灰；r3/r5逐分量GPU排查证实环境镜面项过强。r4/r6为材质/灌丛局部试验，不能代替普通行车构图。
- r7的多重采样遮罩导致树冠稀疏/半透明，撤回。
- r8缺根坡uniform失败；r9补齐后完整直道440m/起伏及两赛道起步运行，但仍有树尺寸和构图问题。
- r10虽然创建GraphicsWindow并正常退出，但保存图片全黑，是无效可见证据，不算可见验收；后续取景工具增加黑图检测。
- r12首个实际450m取景暴露92m长岩体穿入270m弯道和HUD未resize；r13为同一HUD问题的旧基线。r14短岩坡后在270m之后遇到边缘树缺root_slope中断。r15/16分别补齐后完整运行。
- r18诊断误读flatten后的Node材质，触发NoneType；r19只读父级通用shader，所示底色不能代表实际地表。r20诊断替换Geom ShaderAttrib丢失输入后中断；r21恢复输入但优先级不足，r22显式提高诊断shader优先级。以上失败均不能作画质通过证据。

本组早期 `logs/validation/ENV-REAL-01-T0-r2` 的Ruff/82项、`ENV-REAL-01-T1` 的82项及三种子1200步通过，但都在用户澄清后新增地表/短岩坡/正常行车工具之前，不能冒称最终版T1。r9静态帧耗是冻结快照30帧采样，不能外推正式实时性能。

## 保持项

`logs/visual-upgrade-20261024/preserved-and-static-timing.json`记录早期四项冻结资源SHA一致及九项生产源码内容与HEAD一致。包括已认可晴空HDR/环境、原生求解器、生产植被，以及Simulation/车辆/地形/道路核心源码。本地表现可替换照明和装饰资源，不更改物理/评分/存档。最终检查和新增图见后续补记。

## 中间样板r24

`r24-driving-medium-ground`：正常随车视角完整450m、4505新物理步、0碰撞。地表回到原始Pasture A全通道，干草只混5–14%；树冠下按真实树的位置混林地底色，不再整侧涂枯土。树组加密并增加依附树下的灌丛；短岩坡直立在树群间。草层从道路两侧39m扩展至73m（含半格），外圈用16簇/格，内圈64簇/格；相机距离100–140m渐隐。中距离地表/草共享大色块，减少明显覆盖断层。源图像/网格未修画成预渲染背景。

与 `r15-driving-baseline` 比较，4505行**所有已记录的输入/位置/朝向/原点/进度/碰撞字段完全相同**，不把未记录字段说成逐拍全量Snapshot比较。四项冻结资源SHA保持，九项生产源码归一化LF后与HEAD内容一致；复核记录见[preserved-and-driving.json](preserved-and-driving.json)。

| 普通随车位置 | 开始时失败基线 | r24候选 |
|---|---|---|
| 40m推进 | [修改前](before-40m.png) | [修改后](after-40m.png) |
| 270m入弯 | [修改前](before-270m.png) | [修改后](after-270m.png) |
| 450m组合弯 | [修改前](before-450m.png) | [修改后](after-450m.png) |

`r25-window-final`额外在真正GraphicsWindow/1920×1080中运行两赛道各240步后取景，正常追车镜头、场景返回释放通过。此前窗口前缓冲回读黑图改为同一窗口最终颜色缓冲RTMCopyRam复制，并检查非黑图；[实际窗口输出](window-coast-1080p.png)已查看。它是窗口渲染结果，仍不是用户人工驾驶结论。原r25 summary的通用scope文字误写440m，该文件字段已明确straight=0、两赛道各240步；修正说明见logs中的capture-boundary.json，后续工具已按career-only给正确scope，未冒称重跑直道。

最终相关验证：`.venv/Scripts/python.exe tools/validate.py T1 --area environment --output logs/validation/ENV-REAL-01-T1-final-r2 --timeout 300`，Ruff、83项环境/本地资源测试和三种子各1200步通过。新增一次实际短岩坡顶点投影检查，防止组合弯穿路；第一次final因测试lambda未绑定循环root而Ruff失败，未进入pytest，修正后通过。随后仅修检查工具summary文案，不改表现/物理。

该样板仍不通过整体美术验收：明暗与材质仍偏平，草坡/岩坡和树组之间的组织不及设计27，部分坡面仍有明显平铺规律。没有宣称达到KCD2/HD2品质、正式性能Gate或人工接受。r24时仅本地候选入口可运行，本轮成果留在未提交工作区，开始时已有文件完整保留，无远端操作。

## 最新r29与本机默认入口

r26补草根明暗/高度、薄叶包裹受光，并把两组前排树移至护栏外14/15m，让树影进入路面；r27将间接漫反射从原探针45%恢复至65%，保留已修正的叶片环境镜面项。r29只平滑原有限赛道地形的显示法线，顶点不动；细节法线在12–40m淡出，草地底色叠加转向/错周期原图采样，减少大坡面的三角棱线和平铺规律。r28曾将赛道预载范围之外的原条带网格误作8m格读取法线，起步KeyError失败，r29明确只处理实际笛卡尔地形，未吞错。

r29完成相同450m/4505新步/六点原随车镜位，0碰撞；与原r15的4505行全部已记录字段仍完全相同。[当前保持复核](current-entry-preserved.json)另记四项冻结资源/九项生产源码SHA保持。与设计27仍有整体明暗、植物群落组织和岩坡衔接差距，不宣称美术完成。

| 正常随车位置 | 失败基线 | 最新实际图 |
|---|---|---|
| 40m推进 | [原图](before-40m.png) | [当前](current-40m.png) |
| 270m入弯 | [原图](before-270m.png) | [当前](current-270m.png) |
| 450m组合弯 | [原图](before-450m.png) | [当前](current-450m.png) |

r30在真正GraphicsWindow/1920×1080中补验两赛道各240步起步及返回释放，[实际窗口输出](current-window-1080p.png)已查看。r25/r30都是窗口最终颜色缓冲回读，不冒称桌面截屏/人工驾驶。r31经与本机默认启动器相同的 `local_kcd_drive.py → main.main` 完整入口跑 `--smoke --track endless`，实际加载资源、tick296/12NPC，20次重启节点/任务/事件稳定，退出0；输入环境变量LOCALAPPDATA隔离至该次logs/user，不触碰真实用户记录。命令中的 `--output`只给资源缓存，不再转发给游戏/实验台。[入口原始报告](current-entry-smoke.json)。

本机默认 `launchers/game-current.cmd`现接入这版本地表现，`game-kcd-local.cmd`为同版控制台入口。`src/main.py`及分发资产没有KCD二进制；直接原main仍可查看生产资源版。新增回归确认缓存参数不再改写实验台输出位置，完整参数与sys.argv正常恢复。

最新完整相关T1命令：`.venv/Scripts/python.exe tools/validate.py T1 --area environment --output logs/validation/ENV-REAL-01-current-entry-T1-r2 --timeout 300`；Ruff、84项、三种子各1200步通过，详见[验证摘要](current-entry-validation.json)。首轮仅测试导入排序Ruff失败，修复后完整通过；前一材质小组T0 14项通过单独留在 `ENV-REAL-01-leaf-ground-T0`。当前未再修改表现代码，只整理证据/文档，无新提交或推送。

下一步仍以相同随车视角继续改善中距离资源的整体质感；人工审美、人工驾驶和正式实时性能Gate保持开放，不用通过的短测代替。

## 当前林缘样板r46：设计28与真实中距离资源

先检查全部9种橡树/6种林下树的实际尺寸、源砂岩图集，再以r35正常120m实图生成[设计28](../../design/garage-v2/28-driving-woodland.md)。28保留原丘陵右弯，没有27中不属于此地形的海湾。真实树高与冠幅归一、三种幼橡树、五种原件砂岩及三档LOD随后按图落地；主石与后侧CC0暗岩脊分工，右侧树组移到当前镜位能读出的前方。原件模型/纹理继续只在ignored logs，未改生产模型和物理碰撞。

材质研究使用[CryEngine植被参数](https://www.cryengine.com/docs/static/engines/cryengine-3/categories/1114113/pages/1048607)和[Crytek作者的GPU Gems植被着色](https://developer.nvidia.com/gpugems/gpugems3/part-iii-rendering/chapter-16-vegetation-procedural-animation-and-shading-crysis)：源TransmittanceColor/BackDiffuseMultiplier/NormalViewDependency分别进入背面透光和视向法线，高光使用源Specular。属于simplepbr本地近似，不称还原CryEngine GI。原始DDS作者mip直接载入RGB/alpha，底层像素与更低源分辨率逐字节对比；只对小于4像素的链尾补常规生成。草/树/山楂可见阈值分别为源0.15/0.25/0.4，遮罩边缘重映射后使用已有4x MSAA。阴影相机的高优先级状态不能继承逐物体uniform，暂保留统一0.25阴影遮罩。

r43/r44同一120m冻结镜位分别比较原距离档、保留叶面细节法线、全LOD0和扩大树冠阴影。法线/LOD改善有限；180m/4096²阴影并向车前安排覆盖后，中距离树冠才有可见自阴影。r44静态24帧中位11.30→11.61ms，P95 12.62→12.35ms；仅供定位，不能据此声称实时性能提升或Gate通过。[原诊断记录](woodland-distance-diagnostics.json)。最终仍用原45/130/700m树LOD范围与原细节法线淡出，未因模型缩放错误补偿LOD。太阳颜色取原件强度80%，方向未变；r47对照已认可晴空原太阳方位，未采用。

草格横向密度保持，高度从原格内缩放后约0.14–0.55m提高至约0.24–0.92m，地表融合从50%降至25%；地表干草混合8–35%。这些改变针对正常随车时的轮廓和色块，不增加贴脸叶纹制作。

r46正常120Hz驾驶450m，新增4505步/568显示帧/0碰撞，六点镜位均已查看。[逐拍保持复核](woodland-preserved.json)与r15原失败基线的4505行全部已记录字段相同；四项冻结资源SHA保持，九项生产源码归一化LF后与HEAD相同。[驾驶摘要](woodland-driving.json)中的oak/young_oak/sandstone计数是已流送节点数，不能当成屏幕可见数。

| 正常随车位置 | r46实际输出 |
|---|---|
| 40m推进 | [完整图](woodland-40m.png) |
| 120m右弯前 | [与设计28同镜位](woodland-120m.png) |
| 190m入弯 | [完整图](woodland-190m.png) |
| 270m转换 | [完整图](woodland-270m.png) |
| 360m | [完整图](woodland-360m.png) |
| 450m组合弯 | [完整图](woodland-450m.png) |

r48在真实GraphicsWindow/1920×1080运行两赛道各240步并返回菜单释放；[实际窗口最终颜色缓冲图](woodland-window-1080p.png)已查看，[窗口摘要](woodland-window.json)。r49重新经过默认启动器相同的local_kcd_drive→main完整入口：tick272/12NPC/20次重启节点、任务、事件稳定/退出0，LOCALAPPDATA隔离；[原始报告](woodland-entry-smoke.json)。不冒称桌面截屏或人工驾驶。

本组验证：`tools/validate.py T0 --tests tests/test_local_kcd_drive.py --output logs/validation/ENV-REAL-01-authored-mips-T0 --timeout 300`为Ruff/16项通过。最终`tools/validate.py T1 --area environment --output logs/validation/ENV-REAL-01-woodland-T1 --timeout 300`为Ruff/85项及种子0/17/23各1200步通过；[摘要](woodland-validation.json)。新增实际源mip字节对比，并用真实原件砂岩和CC0短岩坡的实际LOD0顶点独立检查道路净空。T1后仅补太阳方位诊断与诊断状态恢复，相关工具Ruff另过；未改运行表现。

中间失败完整保留：r32读错草材质根层而KeyError；r34 AlphaTest构造少参数；r38手动mip需要PTAUchar而不是bytes；r39虽运行但强行固定覆盖率使树冠变稀，方案撤回。r40无有效输出，r41明确因阴影相机缺逐物体uniform中断，r42改为固定阴影阈值后正常。r33/35/36/37/42/45/47均为短段或固定镜位诊断，不累计成新的450m全程验收。

当前尚未达到设计28：整片坡地草色仍较均一，草层与底色在部分距离有界面，坡地树木有疏散感，石群与林下尚未形成图中连续的自然岩草关系。源材质通道、模型和阴影改进不等于整体美术通过。保留active/in_progress、人工驾驶/审美与正式实时性能Gate开放；默认本机入口可体验，成果仍未提交，无远端操作。

## 当前r62/r64：连续草坡、原三角面接地与随车视频

继续按设计28的青绿/浅金色中距离草坡制作，未另换目标。先核对真实干草a/b/c网格及其共同grass材质/图集：新增b/c，当前共三鲜草、三干草、两混合草。b/c源高度0.94/1.28m，直接套旧倍率会超过2m；r55实图过高，随后归一最高原点至0.65m，再按格内尺度布置，实际约0.2–1.1m，原件像素和文件不修改。源SHA/材质路径记录在每次assets/local-source.json；只保留于本地缓存。

原所谓宏观纹理采样仍含细叶纹，不能提供连贯大色块。当前鲜/干品系与地表共享原图低通mip6的世界坐标斑块，40m/转向62.5m双周期混合，地表干草混8–55%；近/远4m格分别预备121/36个候选，按品系权重显示约一半。源图集、原始mip、透光/高光与可见阈值保持。顶点色仅存草簇坐标/品系/随机种子，实际叶片颜色仍取源图，不把元数据乘入底色。草叶内部保持完整遮罩，100–140m通过整簇密度减小，随机数同时依赖世界格位，避免重复模板的淡出纹路。120/270m冻结镜位比较底色60/75/100%后，选60%减少草层结束后的浅色地毯；不改原天空或全局曝光。

真实随车实图仍暴露4m格状浮草，因此另做[2000点原地面高度审计](meadow-ground-audit.json)：四角双线性近似的绝对误差P95约5.6cm、最大16.9cm。r62将原8m网格的float32高度打包小型R32F纹理，草根逐顶点按原三角面对角线插值；原道路、地形顶点、碰撞完全不动。r61至r62同镜位的格状浮草已消除。新增回归逐个核对实际course-terrain源顶点与纹理RAM值、世界Y行向；无限道路明确继续使用原分段控制点模式。

| 普通随车位置 | 当前r62实际图 |
|---|---|
| 40m | [完整图](meadow-40m.png) |
| 120m，设计28镜位 | [完整图](meadow-120m.png) |
| 190m | [完整图](meadow-190m.png) |
| 270m，原浮草位置 | [完整图](meadow-270m.png) |
| 360m | [完整图](meadow-360m.png) |
| 450m | [完整图](meadow-450m.png) |

[连续随车视频预览](meadow-driving-preview.mp4)为真实渲染输出，960×540/15FPS/564帧/37.6s；[1440×810原视频](../../../logs/visual-upgrade-20261024/r64-meadow-video/driving-view.mp4)保留在ignored logs。r64从正常120Hz物理每8步采一帧，tick202→4706，没有插帧、换镜位或用设计图合成；编码期间墙钟不代表实时帧率。ffprobe核对尺寸/帧数/时长；解码第312帧与同tick2698的270m PNG比较，8bit RGB平均绝对差3.10，并已查看方向/HUD/颜色正常。[视频原始摘要](meadow-video.json)。这不是人工驾驶结论。

r62与r64均450m/4505新步/0碰撞，与r15全部已记录输入/位置/朝向/时间/原点/进度/碰撞字段相同；四项冻结资源SHA和九项生产源码保持，[复核](meadow-preserved.json)。r63真实GraphicsWindow/1920×1080两赛道各240步及返回释放通过，[窗口图](meadow-window-1080p.png)、[摘要](meadow-window.json)。该次固定快照中位约21.6/23.0ms，包含窗口同步且与回归负载并行；不据此声称严格性能A/B、完整120Hz求解或实时Gate通过。

r65再次经默认启动器相同的local_kcd_drive→main完整入口，在无限道路模式验证新增高度场的控制点分支及草着色器：tick280/12NPC，20次重启节点/任务/事件稳定，退出0，用户记录隔离至该次logs/user。[入口报告](meadow-entry-smoke.json)。连续视频的同tick帧方向/颜色比较见[编码核对](meadow-video-verification.json)。

最终相关命令：`tools/validate.py T1 --area environment --output logs/validation/ENV-REAL-01-native-ground-grass-T1-r2 --timeout 300`，Ruff/86项/种子0/17/23各1200步通过，[摘要](meadow-validation.json)。首轮仅新测试导入排序导致Ruff失败，未进入pytest；修正后完整通过。此前meadow-T1、meadow-cells-T1各85项为接地修复前的覆盖，不能代替当前86项。T1后只给正常行车取景工具加可选ffmpeg记录，工具Ruff和实际视频编码通过，未改运行表现。

失败保留：r52草法线诊断替换少分号，只有该诊断分量编译失败；r53/54修正后正常。r56视频取色诊断把Texture当PNMImage而中断，r57转换后完成。r50/51/53/54/55/57/58/59为源检查、短段或固定镜位诊断；r55过高草和早期过长的单周期斑块未作为最终版。所有旧证据保留，不累计为额外长程验收。

当前草坡已有鲜/干斑块与稳定接地，但完整场景的树冠/林下体积、灰岩群落衔接和整体光色仍不及28；未获得用户审美/人工驾驶接受，实时性能也未过Gate。目标继续active，当前成果未提交，无推送。


## r74树组与最新人工反馈

继续按设计28制作。r67用真实网格统一14m做九树技术轮廓图，选D/E作A宽冠后的中层；不是设计图或随车验收。主树后侧加入9–12m完整树冠，幼树3–4.8m、山楂1.2–2.2m；成熟/幼树与灌木按实际岩体外廓留根部净距，原地形和碰撞不动。岩群先确定再种树，避免无限道路原生成器提前植树。石群集中，右侧小石跟随实际树组；岩面法线不再20–80m整体抹去。

r70同镜位比较180/240/320m树冠阴影后，选320m/4096²并向车前80m，保留0.0007偏移。0.0003/0.00015在车/石出现条纹，弃用。[静态诊断](grove-shadow-diagnostics.json)包含GPU回读，不能称实时性能A/B。

r73对照[Crytek作者GPU Gems 16.2.4](https://developer.nvidia.com/gpugems/gpugems3/part-iii-rendering/chapter-16-vegetation-procedural-animation-and-shading-crysis)及[引擎ForwardShading最终底色调制](https://raw.githubusercontent.com/ValtoGameEngines/CryEngine/release/Engine/Shaders/HWScripts/CryFX/ForwardShading.cfi)修正背面透光：源颜色是色调，透光同样乘底色；旧的绝对加亮冲淡原叶色。属于重写近似，不声称还原KCD2专有着色。冻结同镜位的[当前](grove-transmission-albedo.png)、[旧加亮](grove-transmission-absolute-old.png)、[半强度候选](grove-transmission-albedo-half.png)已查，保留原参数强度。当前树色更深，用户仍认为缺少自然光感，不能宣布美术通过。

r74正常120Hz实际450m，4505新步/568显示帧/0碰撞；六图均已查看：[40](grove-40m.png)、[120](grove-120m.png)、[190](grove-190m.png)、[270](grove-270m.png)、[360](grove-360m.png)、[450](grove-450m.png)。[视频预览](grove-driving-preview.mp4)为960×540/15FPS/37.6s；1440×810原视频在ignored logs/r74-groves-transmission-video。第312帧解码与tick2698/270m图方向、HUD和颜色已核对，平均RGB差2.93，[编码报告](grove-video-verification.json)。编码墙钟不是实时帧率。

[r74复核](grove-preserved.json)中r72/r74全部4505行已记录字段与r15相同，四项冻结资源和九项生产源码保持，**该结论仅适用于随后加载代码修改之前**。r75真实1920×1080窗口直路440m/2543新步、坡道/两生涯各240步及卸载通过，[报告](grove-window.json)、[直路](grove-window-straight-440.png)、[山脊起步](grove-window-ridge-club-start.png)。该工具仍手动推进，不能证明默认交互流程无故障。树组阶段T1 Ruff/87项/三种子通过，[报告](grove-validation.json)；随后透光T0 Ruff/18项通过，[报告](grove-transmission-validation.json)。

**用户实际体验否定当前版：树靠近时突然变化；天空像雾而无KCD2/HD2的光线感；明显卡顿；地面丑而秃。** 这些作为开放验收项，覆盖旧的天空冻结假设。后续重做天空/照明仍须研究、更新设计，再落地；资源/着色通道完整不等于视觉成功。

## 山脊正常入口与分帧加载

用户报告game-current.cmd进入生涯山脊卡住/退出。真实用户记录仅复制到本轮隔离目录。此前取景使用手动循环且通常关闭/Draw，因此补正常菜单入口、默认/Draw和独立权威会话：r77弯道tick705、r78山脊tick682成功，未复现退出；不是人工驾驶接受。r76诊断启动器未正确隔离spawn主入口，记录无效，停止其自有进程后以带主入口保护的r77/r78重做。

r78进入阶段约17秒同步阻塞，包含会话准备及约12秒模板/整窗景物生成。现只在正式分帧加载路径传4ms景物预算，加载迭代器持续生成完整段，所有段到齐才进入游戏；期间暂停倒计时，权威120Hz/车辆/碰撞不改。r79正常山脊达到tick1081并退出，但初次模板读取仍可能阻塞数秒，不能称完全解决无响应，更不能把未复现退出写成崩溃已修复。该次与测试并行，不作严格时间A/B。

新增修改src/application.py和src/scene.py的加载接口，本机profile转发参数；r74九源码冻结结论不外推到此。首批T0 60过/1失败：原测试仅等16显示帧，与分帧加载不符；改为有时限地等待完整就绪，保留倒计时>330和零赛事计时阈值，并覆盖生涯/自由驾驶独立会话。最终T1 Ruff/48项及种子0/17/23各1200步通过，[报告](loading-validation.json)，原60项无关覆盖复用。未修LOD过渡、自然天空光照和秃地，正式实时Gate及山脊偶发退出继续开放。


## r82–86修正山脊草层消失

用户的秃地反馈在正常山脊中得到实图确认。r81同一冻结镜位关闭高度校正，草立即恢复；这说明已有草节点却被移到地下，不能用继续堆密度掩盖。定位为高度纹理使用TFloat RAM加普通FRed GPU格式，世界高度被归一化到0–1。此前r62等只检查RAM数组、称其R32F不准确，未验证GPU是覆盖缺口。

已改Texture.FR32。新增check_heightfield_gpu.py把每个GPU texelFetch结果按IEEE浮点位编码进RGBA8再回读，对照原CPU高度。r82[旧格式诊断](ridge-gpu-height-before.json)真实范围0–83.8999m被截成0–1m，最大误差82.8999m，命令故意保留失败退出1；[新格式](ridge-gpu-height.json)全纹理最大误差0。参考[Panda纹理格式定义](https://docs.panda3d.org/1.10/python/reference/panda3d.core.Texture)，由本机GPU结果证明本次故障，未改变任何地形/碰撞。

[r81旧实图](ridge-grass-before.png)与[r83同镜位修复图](ridge-grass-fixed-diagnostic.png)只用于草高度诊断，工具未完整刷新正式HUD，不作为UI成品；r86[正常默认/Draw入口实际图](ridge-grass-fixed-normal.png)与[入口报告](ridge-grass-fixed-normal.json)已查看，保持用户存档副本所选车辆。r80[山脊进入→返回→再进入](ridge-normal-repeat.json)两次tick1104/1058均正常，退出0；不把未复现退出写成彻底修复崩溃。

r85当前450m/4505步/0碰撞：[120m](gpu-height-120m.png)、[270m](gpu-height-270m.png)、[450m](gpu-height-450m.png)，其余40/190/360同前缀；[摘要](gpu-height-driving.json)、[保持复核](gpu-height-preserved.json)。八项原源码和四项冻结资源保持；application/scene加载改变另列。r74视频与r75山脊图均早于本次浮点格式修复，不能冒称最新视频。

最终GPU草地T1：`tools/validate.py T1 --tests tests/test_local_kcd_drive.py --output logs/validation/ENV-REAL-01-gpu-height-T1 --timeout 300`，Ruff/21项/三种子各1200步通过，[报告](gpu-height-validation.json)。新增三赛道真实GPU回读，旧RAM检查保留；与加载48项T1分组记账，未再重跑无关长测。r86起步静止/低速281显示帧中位26.92ms、P95 31.84、P99 32.68，观察窗丢时0，[局部帧耗](ridge-entry-frame-times.json)；没有完整运动中的求解/IPC等待分解，不据此通过实时Gate。初始模板读入仍长、树LOD突变、灰雾照明与地表整体自然感继续开放。


## 2026-10-25 当前：原生树LOD过渡与设计29日照

回应用户“靠近突然变树”，保留原45/130/700距离档，采用0.45秒原生FadeLODNode；源叶片alpha先裁剪/重映射，再乘过渡alpha，避免原先阈值吃掉渐入叶片。参考[Panda原生过渡实现](https://github.com/panda3d/panda3d/blob/master/panda/src/pgraphnodes/fadeLodNode.cxx)。[最终真实原树逐帧检查](daylight-lod-transition.json)用固定正交镜位跨48→42m阈值，60Hz仅取样时钟/0新驾驶步；硬切最大RGB变化约5.64，过渡最大约0.66并分布跨多帧。不是用该像素指标宣布人工观感通过。[第0](daylight-lod-00.png)、[13](daylight-lod-13.png)、[29帧](daylight-lod-29.png)。

用户灰雾/缺乏光线反馈后，先以正常r89山脊120m图生成[设计29](../../design/garage-v2/29-driving-daylight.md)，再选[Poly Haven多云晴空](https://polyhaven.com/a/kloofendal_48d_partly_cloudy_puresky)，Greg Zaal摄影/Jarod Guest编辑/CC0。原4K HDR像素不改，MD5/SHA/许可在art/expressway/sources/daylight-29；离线128px/64样本GGX，天空/反射/漫反射共用同图，向西47.8125度日照配准。原晴空文件仍保留，但不能再说当前外观冻结。

同镜位r93/r94发现只换天空或低估填光会让树冠更黑；r96另修正双面叶片背面法线，参照[CryEngine VegetationPS按正背面翻转TBN](https://raw.githubusercontent.com/ValtoGameEngines/CryEngine/release/Engine/Shaders/HWScripts/CryFX/Vegetation.cfx)。[关闭修复](daylight-unflipped-leaves.png)/[启用修复](daylight-corrected-leaves.png)；未改源面序/法线数据。保留[最终固定镜位候选](daylight-frozen-candidate.png)，SH1.2/原光强1.6为本渲染器标定。该图诊断环境使用橙色车；正常入口实际图使用存档副本选车，不把诊断图当成完整UI或实际用户体验。

当前正常/Draw、独立120Hz会话、Controller→Control→Simulation实际山脊270m：[40](daylight-ridge-40m.png)、[120](daylight-ridge-120m.png)、[190](daylight-ridge-190m.png)、[270](daylight-ridge-270m.png)，约50km/h/0碰撞，[摘要](daylight-ridge-driving.json)。输入来自可绑定权威世界的原ViewDriver，无键盘模拟、瞬移或时间比例变化；不是人工驾驶。r102当前沿海450m：[40](daylight-coast-40m.png)、[120](daylight-coast-120m.png)、[190](daylight-coast-190m.png)、[270](daylight-coast-270m.png)、[360](daylight-coast-360m.png)、[450](daylight-coast-450m.png)，[摘要](daylight-coast-driving.json)。[保持复核](daylight-preserved.json)与r15的4505行已记录字段相同，原四资源字节/八源码保持；application/scene为前轮明确加载修改。不是完整Snapshot或实时性能等价。

当前T1：`tools/validate.py T1 --tests tests/test_local_kcd_drive.py --output logs/validation/ENV-REAL-01-daylight29-T1 --timeout 300`，Ruff/22项及三种子各1200步通过，[报告](daylight-validation.json)。运行改动之后只补诊断记录字段，未再改外观。r92诊断未解锁隔离smoke赛事而scene为空，r93修夹具后正常；r93未resize HUD的图仅作光照诊断，r94起修正。API首次403后使用项目已有的User-Agent正常取原件，源文件MD5验证通过。

固定1280×720的RTX4060Laptop正常行驶局部帧耗：r100草层完整显示中位43.14ms/P9553.08/P9956.32，r101仅诊断隐藏草层40.39/49.16/52.61；两个观察窗权威丢时0。帧耗包含绘制/同步，parent CPU不含独立物理进程；不将该粗分解当全步求解/等待/CPU Gate。[草层诊断报告](daylight-no-grass-diagnostic.json)。r98画幅被改变，r99与回归并行，均不作为性能A/B。r89/r90的旧光照硬切/过渡短窗也不宣称严格性能提升。截图回读后的帧单列，原始all_frames保留，不隐藏长帧。

画面虽有云层和更清楚的叶片受光，但仍未达到29的整体光色、林下自然感和连续草地组织；用户审美/人工驾驶与正式实时Gate开放，偶发山脊退出未复现。当前默认本地入口可体验，未提交、无推送；继续查树木/阴影/绘制成本，不靠削减中距离资源或物理标准过关。

## 2026-10-25 接续：保持原画面的逐树参数传递优化

使用当前Panda3D1.10.16自带text-stats及GPU计时获取原生剖析。r103显示绘制/材质设置和同步开销突出；r104仅诊断移除逐树root_slope后加快，但根部变形也消失，不保留该减质方式。最终保留两项原坡度和原公式，放入[p3d_TextureMatrix自动输入](https://docs.panda3d.org/1.10/python/programming/shaders/list-of-glsl-inputs)中二维UV不使用的Z列，避免每棵树产生独立ShaderAttrib、重复设置叶片整套输入。UV.xy不变，未增加纹理查找、复制源顶点或减少树/草/阴影质量。

实际GPU验证五种原树、三档LOD、两组陡坡：30组新旧根部镜位画面逐通道完全相同，[报告](root-transport-image-identity.json)、[技术根部图](root-transport-root.png)。该图只核对形状/贴图，不冒充正常追车美术验收。r105首次直接修改常量Mat4，在驾驶前报错；复制矩阵后r106正常完成。

正常/Draw、4x MSAA、独立120Hz权威会话的山脊270m，同一Controller与用户记录隔离副本，固定1280×720/RTX4060Laptop，未与GPU回归并行：

| 参数方式 | 显示帧中位 | P95 | P99 | 最大值 |
| --- | ---: | ---: | ---: | ---: |
| r108恢复旧逐树ShaderInput | 29.39ms | 36.01ms | 38.19ms | 40.27ms |
| r106当前矩阵传递 | 22.04ms | 25.96ms | 28.96ms | 36.92ms |

两轮均约50km/h、四次正常随车取景、0碰撞、观察窗权威丢时0；中位减少约25%。表内单列截图回读后的帧；[新摘要](root-transport-driving.json)/[完整新帧](root-transport-driving-frames.json)、[旧摘要](root-transport-previous.json)/[完整旧帧](root-transport-previous-frames.json)保留全部长帧，未将回读成本伪装成不存在。[对照与12项保持复核](root-transport-comparison.json)：原四二进制按字节、八源码沿用LF归一哈希。参数传递只改本机美术工具；四图[40](root-transport-ridge-40m.png)、[120](root-transport-ridge-120m.png)、[190](root-transport-ridge-190m.png)、[270m](root-transport-ridge-270m.png)已取，120m已实际审看。

[新原生剖析](root-transport-pstats.txt)/[旧原生剖析](root-transport-previous-pstats.txt)是周期采样，不能从这些稀疏GPU样本声称逐帧P95。parent CPU不含物理子进程，未完成求解/IPC等待/CPU全分解，表格不是正式性能Gate；此前r100/101不与本轮交叉拼接。仍有超过16.67ms的帧，不能称稳定60FPS或卡顿彻底解决。

最终命令：`tools/validate.py T1 --tests tests/test_local_kcd_drive.py --output logs/validation/ENV-REAL-01-root-transport-T1 --timeout 300`，Ruff/23项/0、17、23各1200步通过，[报告](root-transport-validation.json)。该组覆盖三赛道GPU高度、原树LOD逐帧和新根部同图验证；加载48项复用前轮有效结果，未重跑无关长测。原地形/碰撞/驾驶参数和存档保持。当前默认入口已用新方式，未提交、无推送；林下/坡地连续性、人工审美与偶发山脊退出仍开放。

## 2026-10-25 接续：草带覆盖与冠内天空填光

沿用已生成28/29，施工前补齐具体规格。外侧草格候选数较少却沿用近处宽度，导致大片露底；r110将36候选横向宽度补偿11/6并作稳定小偏移，保持高度和原件轮廓，不加贴脸密度。草带边界由距路71m补到103m，整簇密度淡出140–190m、局部LOD220m；底层原法线交给mip过滤，取消40m后的全量抹平。正常/Draw的r111山脊270m确认后保留，r118复测使用同一组草层。

参考[Crytek作者Tiago Sousa的植被着色资料](https://developer.nvidia.cn/gpugems/gpugems3/part-iii-rendering/chapter-16-vegetation-procedural-animation-and-shading-crysis)与[官方材质说明](https://www.cryengine.com/docs/static/engines/cryengine-5/categories/23756816/pages/25534107)，区分摆动用RGB、可选烘焙遮蔽与atlas轮廓。实际检查本机树/三档与幼树的[顶点统计](canopy-source-color-inspection.json)，alpha绝大部分255，不能宣称直接恢复了完整原AO。当前新增的是本项目离线估计：五种原树、24条上半球射线、源尺度5m半径/0.04m偏移，按真实UV/源atlas alpha0.25裁剪；每种树三档顶点都对同一LOD0枝叶计算天空可见率。[制作报告](canopy-visibility-bake.json)保留源网格/atlas SHA与参数；二进制/逐顶点衍生数据仍仅ignored logs，未进分发资源。

最终将灰度遮蔽存入RGB、alpha保持1；可见材质不把该RGB再乘到底色，只以0.7强度调节环境光项。直接日照、透光、atlas裁剪和LOD alpha继续独立。r113将遮蔽放alpha时连带削弱树影，该候选弃用；r114改RGB后的同一120m正常随车镜位：[关闭](canopy-meadow-sky-disabled.png)/[启用](canopy-meadow-sky-enabled.png)。r115技术工具误用不存在的makeCopy接口，在GPU比较前失败；r116改复制构造后通过。

[真实GPU报告](canopy-meadow-gpu.json)：原树A的三档分别比较白色顶点、遮蔽数据但强度0、遮蔽数据且强度0.7。前两者可见画面逐通道一致，三种状态的太阳深度图SHA相同；同时与隐藏树后的深度图不同，证明实际包含了原树，并非空图相等。[技术树冠图](canopy-meadow-technical-tree.png)只核对材料，60Hz仅技术采样/0新驾驶步。它不是原引擎GI、完整多次反弹或人工审美接受。

最终r118正常/Draw、独立120Hz会话、1280×720山脊270m：[40](canopy-meadow-ridge-40m.png)、[120](canopy-meadow-ridge-120m.png)、[190](canopy-meadow-ridge-190m.png)、[270m](canopy-meadow-ridge-270m.png)，约50km/h/0碰撞，[摘要](canopy-meadow-ridge-driving.json)/[完整帧](canopy-meadow-ridge-frames.json)。单列截图回读后的显示帧中位21.49ms、P9525.62/P9928.14/最大35.90，原始全帧含回读长帧保留，观察窗权威丢时0。[r111无新增树冠遮蔽摘要](canopy-meadow-ridge-without-ao.json)仅为相同草层下的短程观测；不从小幅波动声称这项着色令性能加快，也不作为完整求解/IPC等待/CPU或稳定60FPS Gate。

r120完整450m/4505步：[40](canopy-meadow-coast-40m.png)、[120](canopy-meadow-coast-120m.png)、[190](canopy-meadow-coast-190m.png)、[270](canopy-meadow-coast-270m.png)、[360](canopy-meadow-coast-360m.png)、[450m](canopy-meadow-coast-450m.png)，[摘要](canopy-meadow-coast-driving.json)。全部已记录Control/位置/朝向/时间/原点/进度/碰撞字段与r15相同，[保持报告](canopy-meadow-preserved.json)含原四资源字节/八源码LF归一哈希，不扩大为完整Snapshot等价。已实际查看120/270/450m；坡面连续性有所改善，冠内变暗但仍缺少设计29的整体光色和林下自然组织。

最终T1：`tools/validate.py T1 --tests tests/test_local_kcd_drive.py --output logs/validation/ENV-REAL-01-meadow-canopy-T1 --timeout 300`，Ruff/24项/三种子各1200步通过，[报告](canopy-meadow-validation.json)。验证后只补缓存原子写入，r121重烘A三档数据与当前缓存相同、无遗留tmp；有效缓存检查0.024s、未重新烘焙，Ruff通过。原包变更/文件缺失才重算，网格或atlas不匹配时明确报错。当前默认入口已采用，未提交、无推送；人工审美/驾驶、偶发山脊退出和正式性能Gate继续开放。

## 2026-10-25 接续：布局30、真实岩群选型与连续林地

复用26已实际查看的KCD2/HD2作者场景，先比28与r120，再内置ImageGen生成[30](../../design/garage-v2/30-woodland-floor.md)，原图/完整提示词已保存。它限定原相机/路形/照明中的林群、岩脚和地表关系；生成器仍改车/HUD/局部牌架与色调，这些不落地。30不是实机或人工接受。

岩群第一次放大后[被树挡住](woodland30-hidden-outcrop-candidate.png)，第二次[接近裁镜左侧](woodland30-cropped-outcrop-candidate.png)。用原120m相机和镜头投影核对：[数据](woodland30-stone-projection.json)，(-29,150)中心约x8px，(-22,172)约x432px；移动艺术摆放而非相机。r125[方块感候选](woodland30-square-outcrop-candidate.png)未算通过，再在同一光照/6m高度下实际看五原石/0与137度：[选型全图](woodland30-stone-catalog.png)/[尺寸](woodland30-stone-catalog.json)。最终主石用较宽medium源网格归一6.5m，辅以4.2m large_a与小石。源cgfm包围盒和点云匹配，未根据其他格式的压缩说明盲改坐标；原点/UV/源法线不改。真实变换外廓净空检查仍覆盖道路其他支路。

提高后层宽冠A比例，岩群侧后补12m完整树和3.2–3.8m幼橡树、1.4–1.8m山楂。保留主石道路侧开口，根部绕实际岩块外廓。12/108m前树方案虽露石面却削弱路面明暗，已恢复44/120m原前层，不能为一个岩面把整幅树影去掉。没有改物理树/道路/驾驶参数、车辆、HUD或天空。

林地覆盖改按实际树位/冠幅计算2m世界对齐纹理，邻段共享周围树冠；落叶土、地表法线/粗糙度与整簇草密度读同场，密林下约四分之一草、林缘回到完整草层。旧段移除时刷新，分帧更新带局部版本标记。GPU[覆盖输出](woodland30-coverage-diagnostic.png)/[无草材质](woodland30-floor-diagnostic.png)和[纹理统计](woodland30-coverage.json)只作诊断；R8用于0–1覆盖，原高度仍FR32。高斯用局部/可分离栅格，正常参考样本与原密集计算差≤1/255，不能扩大为所有输入绝对等价。草带实例包围球按真实控制点最大半径+3m，不再用旧85m裁103m外圈。

当前r133完整随车450m：[40](woodland30-coast-40m.png)、[120](woodland30-coast-120m.png)、[190](woodland30-coast-190m.png)、[270](woodland30-coast-270m.png)、[360](woodland30-coast-360m.png)、[450m](woodland30-coast-450m.png)，[摘要](woodland30-coast-driving.json)。120/270/450m已实际查看。全部4505行已记录Control/位置/朝向/时间/原点/进度/碰撞同r15，六处相机/车位/FOV同r120，[保持报告](woodland30-preserved.json)另含四原资源字节/八源码LF归一哈希；相机/HUD源码git diff为空。这不是完整Snapshot或性能等价。

r131正常/Draw、独立120Hz会话、当前栅格/包围、山脊270m：[40](woodland30-ridge-40m.png)、[120](woodland30-ridge-120m.png)、[190](woodland30-ridge-190m.png)、[270m](woodland30-ridge-270m.png)，[摘要](woodland30-ridge-driving.json)/[完整显示帧](woodland30-ridge-frames.json)。约50km/h/0碰撞，观察窗权威丢时0；截图回读后帧单列时中位23.58ms/P9527.58/P9930.01/最大36.78，原始含回读长帧仍保留。当前不满足稳定60FPS，也未完成完整求解/IPC等待/CPU Gate。

进入赛事到可驾驶含倒计时约28.85s，整体等待未改善；[r129栅格优化前](woodland30-before-raster-optimization.json)约27.72s，不能拿内部运算量减少冒充入口提速。[r130同缓存生命周期重复入口](woodland30-ridge-repeat.json)进入→返回→再进，tick1088/1060、退出0；在栅格/包围优化前完成，缓存清理逻辑之后未改，此覆盖复用而非重跑。单次流送步骤最高44.67ms，未定位每个阶段的贡献；初始解析/流送仍需分解，偶发退出不称彻底修复。

最终命令：`tools/validate.py T1 --tests tests/test_local_kcd_drive.py --output logs/validation/ENV-REAL-01-woodland30-T1 --timeout 300`，Ruff/26项/0、17、23各1200步通过，[报告](woodland30-validation.json)。新增相邻实际原树覆盖一致/移除释放、局部栅格对密集参考；其余GPU高度、LOD、根部与树冠深度为同组实跑，加载48项复用前轮。不用这组短测替代实际审美/人工驾驶。验证后只改一条文档字符串和归档。当前默认入口已采用，全组未提交、无推送；30的整体自然感与光色、实时性能/加载及用户体验继续开放。


## 2026-10-25 接续：实际入口分解与原件解析缓存

r134在LocalVegetation安装后包裹实际绑定的load_kit/segment_steps，逐次next仅记录执行，不含yield等待；主线程CPU单列。此前runpy类追踪未命中入口的记录不当作资产分解。[原分量](native-cache-baseline-loading-phases.json)：load_kit 7.521s，排水阴影2.303s，林地覆盖0.196s；ground-normals首次步骤44.83ms。林地覆盖不是主要等待来源。本轮未改排水几何，仍是下一项加载优化对象。

先试完整BAM快照，实际出现ShaderAttrib不能读取，鲜进程失败，该缓存弃用，未接默认入口。改为无Python对象的NPZ数值网格和原生TXO纹理；allow_pickle=False，材质/着色器/当前树冠遮蔽每次照常创建。键包含当前解析文件SHA、源网格SHA或原包身份/相关成员CRC及解码选项，材质筛选另计；原包只读，衍生数据仍仅ignored logs。临时文件完成后替换，manifest最后写；无有效缓存时从原件构建，首次不会变快。缓存不包含玩家记录，不改变资源分发许可。

[38节点等价](native-cache-equivalence.json)/[完整数值签名](native-cache-model-signatures.json)：原解析、首次建缓存、缓存命中，顶点数组、索引、着色器源码、各通道贴图所有RAM mip、LOD与高度标签一致。[鲜进程TXO](native-cache-fresh-process-txo.json)12级作者图集mip完全相同，读取约0.023s；不能用PNG代替作者mip。独立草树石准备命中约0.65s，不能扩大为整场加载或FPS。

同一固定1280×720/4xMSAA、默认/Draw、独立120Hz会话正常山脊270m，三次均0碰撞/观察窗权威丢时0：[未缓存](native-cache-baseline-summary.json)、[首次建缓存](native-cache-cold-summary.json)、[命中](native-cache-warm-summary.json)，对应完整帧和loading-phases同前缀保存。点赛事到可驾驶含倒计时28.258/27.856/24.292s，load_kit 7.521/7.828/4.111s；本次命中较原观测少约3.97s，是单次同条件观测，未声称稳定统计结论。未降低草树数量、阴影或纹理。命中显示帧中位23.22ms/P9527.76/P9930.92/max39.42ms（截图回读另列），未解决稳定60FPS或全步性能Gate。实际查看[120m](native-cache-ridge-120m.png)，其余40/190/270m保留；画面仍未达到设计30。

[保持SHA](native-cache-preserved.json)再次核对原四资源字节/八源码LF归一，物理/相机/HUD未改。相关T1结果补在下段。当前本机默认入口采用缓存，首次启动需生成；未提交、无推送。用户审美/驾驶接受、整体卡顿和偶发山脊退出仍开放，两次本轮正常入口不能证明偶发问题消失。

最终相关T1：`tools/validate.py T1 --tests tests/test_local_kcd_drive.py --output logs/validation/ENV-REAL-01-native-cache-T1`，Ruff/27项（120.98s）及0/17/23各1200步通过；[报告](native-cache-validation.json)。新增实际源网格/筛选缓存与12级作者mip一致性检查。之后仅归档/文档，无运行代码修改。


## 2026-10-25 接续：排水格栅重复角点

实际load分解确认drain-shadow为主要CPU构建项后，将每个排水子节点的重复局部角点结果复用；世界变换、curve.project、当前日照坐标公式与按Geom让出预算均保持。缓存只活到当前排水节点完成，不跨世界/路段/日照，不以近似路面或降低阴影质量换速度。[四场景ABBA](drain-cache-geometry-abba.json)：真实山脊、沿海、起伏道路负段、直路，逐次属性坐标及最终全部Geom数组/索引字节相同。技术记录器首轮遇非索引primitive的getVertices返回None，改读实际getVertexList后才完成，首次失败不作验证。

r141默认/Draw、独立120Hz、1280×720/4xMSAA正常山脊270m/0碰撞/观察窗权威丢时0：[摘要](drain-cache-summary.json)/[全帧](drain-cache-frames.json)/[入口分解](drain-cache-loading-phases.json)。drain-shadow累计0.630s（上轮r1392.429s），点赛事到可驾驶含倒计时20.189s（r13924.292s）；load_kit本次4.068s（r1394.111s）。整体时间还有帧调度等差别，不能将4.10s全部归因于1.80s局部节省。不是稳定统计或完整物理性能Gate。

本次剔除截图回读后显示中位22.37ms/P9526.82/P9931.13，最大162.07ms：发生约73.52m，update_wall141.03ms而update_cpu0/parent_cpu15.625ms，stream_frame0.045ms；与截图长帧分别保留，未从统计删除。单条显示等待记录不足以锁定根因，更不能宣称卡顿解决。仍有初始法线构建约44ms，下一分帧但保持原结果。

[120m实图](drain-cache-ridge-120m.png)已查看，40/190/270m保留。[四资源/八源码保持](drain-cache-preserved.json)，本轮仅expressway_route排水重复值计算有新生产差异；不改物理、相机、材质或草树覆盖。相关T1 Ruff/25项及0/17/23各1200步通过，[报告](drain-cache-validation.json)。正常入口未退出不代表偶发崩溃消失。无提交/无推送，原有未提交成果保留。之后局部入口的法线分帧为另组证据。


## 2026-10-25 接续：原地形法线分帧

首次法线累计原来在surface_weights的一个next内同步完成，约44ms；现在按原面/顶点顺序，每96面累计、每128点归一化让出预算，全部完成后才存入当前本机profile的按赛道缓存。取消时不发布半成品；原网格/法线数值算法不变，缓存仅当前进程三张有限赛道。三赛道原始整表逐点逐值一致，未按段分别算法线而引入接缝。

r142[首次超时](normal-steps-first-timeout.log)在120m后未完成：[部分入口分量](normal-steps-first-partial-loading.json)。保留现场后用同版本Python的sys.remote_exec请求线程快照，[主线程](normal-steps-first-thread-43916.log)在ShowBase渲染提交，[物理进程](normal-steps-first-thread-46224.log)等待下一管道请求；之后测试抛120s TimeoutError/exit1。Windows系统/应用事件当次窗口未找到Display或1000/1001/1002错误；桌面截图显示其他应用，不能据此断言窗口最小化或将故障归因于失焦。这次不是成功行驶/性能证据，也不认定法线分帧造成或修复了卡住。

停止状态确认后r143加faulthandler20s周期栈记录复测，默认/Draw、固定1280×720/4xMSAA、独立120Hz会话驶完270m/0碰撞/观察窗权威丢时0，exit0：[摘要](normal-steps-summary.json)/[完整帧](normal-steps-frames.json)/[加载分量](normal-steps-loading-phases.json)/[周期栈](normal-steps-completed-thread-samples.log)。周期栈含渲染提交处，正常完成的采样不能当作死锁证明。入口含倒计时20.348s，未声称分帧令整体入口加快（r14120.189s）。累计分量max0.582ms/归一化max0.135ms，原法线写入max3.01ms；总流送单步max18.38ms，仍有地形/表面等剩余单步。显示中位22.79ms/P9527.31/P9930.64/max38.46ms（截图回读另列），带线程采样仅局部观测，不作为严格性能Gate，且不以此覆盖r141162ms长帧或r142超时。

真实[120m](normal-steps-ridge-120m.png)/[270m](normal-steps-ridge-270m.png)及40/190m保留，270m已查看；本轮未变美术参数、相机、物理。目标设计30、整体光色/地表观感、用户接受、卡顿与偶发退出仍开放。相关T1结果在完成后补入。未提交/无推送，先前工作保留。

法线组最终T1：`tools/validate.py T1 --tests tests/test_local_kcd_drive.py --output logs/validation/ENV-REAL-01-normal-steps-T1`，Ruff/30项（109.19s）及0/17/23各1200步通过，[报告](normal-steps-validation.json)；[四资源/八源码保持](normal-steps-preserved.json)。之后只有归档/文档修改。


## 2026-10-25 接续：林地参数的实际读取范围

林地覆盖原来放在每段根节点，树、路牌、石块与地面/草都继承各段不同纹理。现在只放在真实读取它的course-landscape/route-landscape/kcd-stream-grass节点，根节点PythonTag仅供统计与重算；统一空默认仍在场景render。场景几何、密度、源参数/贴图、阴影尺寸与物理不变。旧模式仅留在诊断工具的--legacy-woodland-state中；正常入口用缩小范围后的方式。

r144[首次GPU静态对比](woodland-state-gpu-woodland-state.json)四次完整RGB帧相同，3118个树Geom状态条目保持，独立树ShaderAttrib从44变4。这是全部已流送Geom状态计数，不是屏幕可见数或44→4次draw call。技术随车[旧](woodland-state-gpu-woodland-state-root.png)/[新](woodland-state-gpu-woodland-state-scoped.png)同一120m、固定时刻。禁止将一次相等扩大为默认排序下所有帧绝对相等。

随后完整T1为30通过/1失败，[原失败](woodland-state-first-validation-failed.json)：原生状态排序在两个像素/五通道有差异，max36；两模式各自重复相等，失败[数值](woodland-state-failed-native-woodland-state.json)/[旧帧](woodland-state-failed-native-woodland-state-root.png)/[新帧](woodland-state-failed-native-woodland-state-scoped.png)保留，未改阈值冒称全帧相等。r149再试固定全场景绘制顺序，车漆自身重复也出现1级RGB变化，未取得绝对相等，[原尝试](woodland-state-fixed-order-attempt-woodland-state.json)保留；固定排序仅诊断，未接产品。排序影响与车漆重复变化不能直接视为着色参数错误，也没有以它们消除失败记录。

最终GPU回归改为逐个真实Geom检查：几何对象不变、ShaderAttrib以外全部RenderState相同，除两个林地输入之外的ShaderAttrib相同；着色器源声明使用覆盖场时，纹理对象与四项边界逐值相同；其余着色器没有这两个uniform。全场景原生排序画面与每模式重复帧仍完整保存/报告，不再声称所有像素绝对相同。最终检查与T1结果补在后段。

串行同条件scoped/root/root/scoped正常/Draw、独立120Hz、1280×720/4xMSAA山脊270m，各0碰撞、观察窗权威丢时0：[ABBA记录](woodland-state-abba.json)，四轮摘要/全帧按r145/r146/r147/r148前缀归档。新中位22.03/21.61ms，旧22.87/22.80ms；P95新26.86/25.89、旧26.79/26.50ms，首对P95没有改善，不宣称所有分位提升。两组中位约改善4.4%，这只反映显示侧短程、parentCPU不含物理进程，也没有分解全部求解/IPC等待。原r141162ms长帧和r142超时仍开放，非稳定60FPS/全步Gate。

最后[120m实机](woodland-state-ridge-120m.png)及40/190/270m保留，前述正常驾驶不冒充人工接受。四轮入口约20s，无模型删减、阴影降级或相机更改，未提交/推送。


最终[GPU逐Geom报告](woodland-state-final-woodland-state.json)：209个真实读取覆盖的Geom输入相同，3933个Geom的着色器不声明该uniform，总4142个几何及其余RenderState/ShaderAttrib不变；树Geom状态3118，44→4种ShaderAttrib。默认排序本次两通道/max2RGB8差，两模式自身重复零差，仍不宣称任意整帧像素恒等。[最终旧](woodland-state-final-woodland-state-root.png)/[最终新](woodland-state-final-woodland-state-scoped.png)完整保留。

修复检查口径后仅运行变更的GPU单项：`tools/validate.py T1 --tests tests/test_local_kcd_drive.py::test_scoped_woodland_preserves_consumed_inputs_and_reduces_tree_states --output logs/validation/ENV-REAL-01-woodland-state-T1-repair`，Ruff/1项（34.12s）及0/17/23各1200步通过，[最终报告](woodland-state-final-validation.json)。同批其余30项使用首次T1中的有效通过结果，未再重跑或声称出现完整31项同次全绿；中间固定排序失败没有接生产。之后仅文档/归档，无运行代码修改。[四资源/八源码保持](woodland-state-preserved.json)，正常r148120m实际图已查看。

下阶段回到设计30/29与实际画面的差距，优先树冠整体受光、林缘到地表的自然过渡及石体轮廓。旧r43/r44已证明单纯保留叶片细节法线或全LOD0改善有限，本轮实际查看其两种图后不再重复该候选。按根状态优化不代替美术改进，用户接受、偶发渲染等待/退出与正式性能Gate继续开放。


## 2026-10-25 接续：山脊设计31与中距离草坡生长场

复用26已经实际查看的KCD2/HD2作者完整场景研究，本轮重新打开[作者Nebakov页](https://petrsusanka.artstation.com/projects/6LxVJw)/[HD2岩体页](https://stefanwilliamsc.artstation.com/projects/nJEX9X)核对内容，随后实际看r148山脊120m与设计30，再内置imagegen生成[31原图/规格](../../design/garage-v2/31-ridge-meadow.md)。提示词与原图保存，注册资源表。31右坡不规则草高与林下关系更清楚，但有整体偏黄、车/HUD和局部道路漂移，明确排除；不在运行画面全局染黄/改路/改车，不把设计图当成成品。

只用现有原件牧草低通mip6，旋转约22m/另一约53m双周期组成世界坐标生长场。每株在根部取同值，草高乘0.3–1.35，地表底色乘0.88–1.08，较高簇保留更多原面法线的中距离受光；高度改变同步按逆缩放校正几何法线，草根仍逐顶点读取原8m三角网格。原候选数、鲜/干品系筛选、林冠覆盖密度、LOD/alpha/mip/透光/高光保持；这改变表现高度，不冒称渲染顶点完全不变。没有修改树木颜色、天空/太阳或全局曝光。

r150初版正常山脊270m/0碰撞，但实际看120/270m变化偏弱，[初版观测](meadow31-before-field-calibration.json)。r151同一沿海120m比较[初版高度](meadow31-height-variant-current.png)、[较强](meadow31-height-variant-strong.png)、[适中](meadow31-height-variant-moderate.png)与[生长场输出](meadow31-height-variant-field.png)，它们是选型诊断，非最终实图。选择适中的高度区间，未使用更高的1.65倍版本。显式位编码GPU回读[原低通信号](meadow31-source-signal.json)：P10/50/90约0.05830/0.06430/0.07092；初0.052–0.083区间只有3.17%高生长，不能靠看经色调映射的白灰场误判信号分布。[最终实测](meadow31-final-field.json)用0.059–0.071，400×400m/2m采样中约35.00%低于0.2、25.35%高于0.8；原点0/±2000m逐样本最大差0。只是该世界区域的统计，不扩为所有路线分布承诺。

r154默认/Draw、独立120Hz、1280×720/4xMSAA实际山脊270m/0碰撞/观察窗权威丢时0：[摘要](meadow31-ridge-driving.json)/[全帧](meadow31-ridge-frames.json)/[120m](meadow31-ridge-120m.png)/[270m](meadow31-ridge-270m.png)，40/190另存。入口20.711s，剔除截图回读后的显示中位22.33ms/P9527.44/P9930.88/max39.61ms，仍非稳定60FPS；没有同条件旧版实时ABBA，不声称这项美术令性能提升或完全无代价。不能覆盖旧r141162ms长帧、r142超时和偶发退出。

r155沿海450m/4505记录行，Control/位置/朝向/时间/原点/进度/碰撞同r15，六处相机/车位/FOV同r133：[保持报告](meadow31-preserved.json)/[驾驶摘要](meadow31-coast-driving.json)。真实[120](meadow31-coast-120m.png)/[270](meadow31-coast-270m.png)/[450m](meadow31-coast-450m.png)已查看，40/190/360同前缀；四原资源字节/八源码LF归一保持。静态正常相机不等于人工驾驶或完整Snapshot等价。

最终T1：`tools/validate.py T1 --tests tests/test_local_kcd_drive.py --output logs/validation/ENV-REAL-01-meadow31-T1`，Ruff/32项（140.34s）及0/17/23各1200步通过，[报告](meadow31-validation.json)。新增真正GPU草坡场分布和原点重定位核对，原三赛道GPU高度仍过；初单独Ruff发现常量join提示并改为直接PRC文字，未把该提示冒称T1失败。之后仅归档/文档，无运行代码修改。

草高与地表开始有连贯斑块，但整体仍远不及31的自然感；树冠大受光、岩体轮廓与林下组织未完成。下一先分离实际树冠的直射、自阴影与天空漫反射，固定120m判断主要差距；不继续堆贴脸法线或全LOD0。新读[NVIDIA SpeedTree渲染](https://developer.nvidia.com/gpugems/gpugems3/part-i-geometry/chapter-4-next-generation-speedtree-rendering)明确讨论叶卡自阴影与双面透光，不能把其转向billboard的深度偏移直接套到当前固定叶卡。SpeedTree card_generator原页请求403，只看到搜索摘要，未当作完整制作资料或实施依据。本轮没有实施任何树冠法线重定向、额外阴影过滤或新光照模型。

默认game-current采用当前候选；未提交/无推送，初始未提交工作保留。人工视觉/驾驶接受、偶发退出/渲染等待和严格性能Gate均开放。


## 2026-10-25：树冠光照分量与背面天空透光

沿用已生成并保存的设计31，实施前补齐木本叶片填光规格。r156在原沿海120m镜位，直接读取simplepbr色调映射前HDR；固定10–150m可见树木（含枝干）掩码181516像素，[分量数据](canopy-components.json)。[原效果](canopy-components-current.png)、[直射](canopy-components-direct.png)、[太阳透光](canopy-components-transmission.png)、[天空漫反射](canopy-components-sky-diffuse.png)、[高光](canopy-components-specular.png)、[阴影因子](canopy-components-shadow.png)分别输出；[去接收阴影](canopy-components-no-shadow.png)显著变亮但失去形体，未采用。[双倍天空漫反射](canopy-components-double-sky-diffuse.png)也非解决方案。分量诊断输出强制alpha1，真实效果/消融保留原覆盖，均值用于相对观察，不将分量均值相加冒充严格材质能量分解或物理照度。

源码显示已有太阳背光透射，天空项只有正面反射。参考[NVIDIA GPU Gems3 4.4薄叶双面受光](https://developer.nvidia.com/gpugems/gpugems3/part-i-geometry/chapter-4-next-generation-speedtree-rendering)，在本项目中估计反法线方向的同一天空SH，以原SSS贴图、TransmittanceColor、BackDiffuseMultiplier和原天空遮蔽调制。这是本项目局部近似，不是文献原式、KCD2 GI或现场照度还原。太阳/天空照片/曝光/源法线/源alpha和阴影生成不改，不用给全树统一乘颜色代替受光。

r157同镜位[0](sky-candidates-current.png)/[0.5](sky-candidates-sky-transmission-half.png)/[1](sky-candidates-sky-transmission-one.png)/[2](sky-candidates-sky-transmission-two.png)实际选型，[数据](sky-candidates.json)。采用1，不采用夸张2；当前样本HDR亮度P10约0.00590→0.00861，P50约0.02332→0.02884，P90约0.11031→0.11703，暗部相对抬升更多，仍保留自阴影。只在橡树、幼树和山楂模板启用；草直接将此项编译成0，石/路/车无该项。未增加逐树独立变化参数。

正面结果使用未截断的原SH辐照度，反向的二阶项不变，仅减去两倍一阶项，避免再算整套SH。r166[三档真实GPU](sky-transmission-final-gpu.json)：同一原树A的LOD0/1/2复用计算与原反向采样最大线性误差均9.54e-7；新项确实改变受光，三个LOD的太阳深度SHA与关闭时相同且与空图不同；把原SSS遮罩换为0时，开/关画面逐像素相同。r158初始完整采样结果也单独保留。[r164](r164-sky-sh-reuse-gpu-failed.log)/[r165](r165-sky-sh-reuse-gpu-fixed-failed.log)校验失败：整屏误差纳入背景，改缓冲清屏仍被显示区域清屏0.819824影响；最终在HDR alpha标记真树片元，不改1e-5阈值、不删非零误差，不改产品背景。此项是纯技术取景，0新驾驶步。

性能观察分开保留：r159/160只是同一新程序的强度1/0，中位25.40/25.55ms，不能代表没有编译成本；r162草编译掉后26.53ms；r163连木本项也编译掉为25.53ms。最终SH复用r167中位25.91ms/P9529.81/P9932.50/max48.70ms，入口20.33s，809记录帧均前台/0最小化，270m/0碰撞/观察窗权威丢时0。各轮摘要/全帧按r159/r160/r162/r163/r167前缀保留。没有严格同次ABBA/完整求解与IPC等待分解，不从这些时段小差值宣称性能提高或没有成本；稳定60FPS和旧长帧/超时仍未解决。

最终[r167山脊120m](sky-transmission-ridge-120m.png)已查看，40/190/270同前缀；r168沿海450m，[120](sky-transmission-coast-120m.png)/[270](sky-transmission-coast-270m.png)/[450m](sky-transmission-coast-450m.png)已查看，六图保留，[摘要](sky-transmission-coast-driving.json)。[保持报告](sky-transmission-preserved.json)：4505行已记录Control/位置/朝向/时间/原点/进度/碰撞同r15，六镜位/车位/FOV同r155，四原资源字节/八源码LF归一保持；不扩大为完整Snapshot等价或人工体验。

最终T1：`tools/validate.py T1 --tests tests/test_local_kcd_drive.py --output logs/validation/ENV-REAL-01-sky-transmission-T1`，Ruff/32项（148.99s）及0/17/23各1200步通过，[报告](sky-transmission-validation.json)。修改原GPU树冠检查加入透光/零遮罩/SH误差/太阳深度，并非新增32项；独立Ruff只修了工具导入换行。之后仅文档与归档，无运行代码修改。新材质已进默认game-current；未提交/无推送，原未提交工作保留。整体仍达不到31，用户视觉/驾驶接受、偶发退出/等待、严格性能Gate开放。

下一性能候选先审计了原近/外圈草模板：[数据](grass-primitive-audit.json)，3402/1008个真实三角形的三个顶点株根UV/品系/种子都相同。初始grass_present判定不依赖各顶点位置，故可试整株被判不显示时立即把整图元送出裁剪区，跳过后续地形取样与变换；当前尚未实施，不能称已提升性能。只能放在初始判定后，不能把可能逐顶点不同的高度边界判定也提前整株裁掉。之后再按31比较树冠整体漫反射形体；已读[Gaijin植被法线工具](https://gaijinentertainment.github.io/DagorEngine/dagor-tools/addons/3ds-max/dagor-maxscript-toolbox/editing_normals_tool.html)关于部分混合及排除树皮的说明，未实施法线重定向。DreamWorks聚合法线论文请求重定向到研究首页，未读到PDF，不作为已研究依据。

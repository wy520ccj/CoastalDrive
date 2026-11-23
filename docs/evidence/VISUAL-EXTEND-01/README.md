# VISUAL-EXTEND-01 跨入口画面统一

2026-10-28，状态in_progress。用户扩展授权包括其它UI、游戏模式与试验台；本轮第一块是试验台车辆视窗。不能把这一块当成全面升级或原性能目标完成。

## 研究与设计

深入核对RenderPipeline f858d071的环境探针空间混合/视差修正/粗糙度mip、稳定PSSM、GPU曝光、SSR多目标与场景准备/资源生命周期；另读原06-Car样例入口和模型来源。实际浏览作者汽车、材质球SSR及编辑器整图，提炼车身连续反射、材质粗糙差异、接地阴影和功能分组。[源码链接、采用理由、许可、事前规格及限制](../../design/garage-v2/36-lab-daylight.md)。原文只读副本和各blob SHA位于B盘logs/visual-extend-20261028/reference，未导入对方模型/贴图或整套管线。

本轮真实初始实验台1280×720图已采看，再用内置ImageGen编辑参考生成[设计36](../../design/garage-v2/36-lab-daylight.png)，[完整提示词](../../design/garage-v2/36-lab-daylight-prompt.txt)已保存。生成器重画的车身曲面/字形不纳入制作，原布局和实际车辆网格保持；设计图不作为运行证明。

## 实施范围

- 实验台复用当前生涯已采用的48d晴空离线环境，同一源图太阳方向。只新增原生过滤环境/源metadata/CC0许可约3MiB，SHA与原候选精确相同；不再为实验台解码整张20MiB HDR，不改原模式天空。
- 使用已有Asphalt03底色/法线/粗糙度；米制2m重复，颜色保持中性，既有十米网格、试验轨迹、凸起/对开路面标记保留。纯表现平面不改变附着或路面物理。
- 一个方向灯投影1024²→2048²，固定22m覆盖并按投影像素格跟随，抑制回看时亚像素投影游动。未增加灯或渲染通道；显存/帧时成本仍需后续正常窗口测量，不能据少灯宣称免费。
- 反射/SH输入只写实验台根和本车节点，关闭时随根与阴影缓冲释放；共享render与返回驾驶的环境不被覆盖。独立实验台采用已有ScenePipeline，主窗口仍共用原渲染器。
- 原车型几何、轮位/参数、相机位置与FOV、界面版式、曲线、120Hz和试验算法保持。正常试验由原update/run.advance推进，无第二套状态。

实际r1仅底色地面偏褐且层次有限；r2接同一道路法线/粗糙度公式后更中性，均保留。两次Ruff导入折行问题修正，最终通过，未发生本轮行为测试失败。

## 验证

针对性T0 1项通过：环境绑定局部于视窗，独立入口使用ScenePipeline，回放位置变化时投影中心沿像素格移动。完整相关T1 **43项**、Ruff、0/17/23三种子通过，覆盖实验台输入/回放、主窗口往返与渲染。新采集工具单独Ruff通过；结果及最终源/资源指纹保存于summary.json和source-sha256.json。

真实1280×720及1024×768两画幅各6图：独立初始视窗、原update完成60步试验后的追车/顶视/侧视、共享窗口载入当前驾驶车、返回游戏。均保持同一窗口/渲染器，实验台根和阴影释放，所有model_fingerprint前后保持，原过滤环境SHA核对通过。原始记录分别在logs/visual-extend-20261028/lab-final-720及lab-final-4x3；12图为真实离屏运行，不是正常驾驶/帧率或人工验收。

```text
.venv\Scripts\python.exe tools/validate.py T0 --tests tests/test_lab_ui.py::test_lab_environment_is_scoped_to_scene_and_shadow_tracks_on_texel_grid --output logs/visual-extend-20261028/T0-lab-daylight
.venv\Scripts\python.exe tools/validate.py T1 --tests tests/test_lab_ui.py tests/test_workspace_transition.py tests/test_rendering.py --output logs/visual-extend-20261028/T1-lab-daylight
.venv\Scripts\python.exe tools/check_lab_daylight.py --output logs/visual-extend-20261028/lab-final-720
.venv\Scripts\python.exe tools/check_lab_daylight.py --size 1024 768 --output logs/visual-extend-20261028/lab-final-4x3
```

所有新输出及TEMP/TMP均在B盘；无全局安装、提交或推送。原性能留窗已结束（实际进程不再存在），原因未确认，不声称仍可体验；新实验台预览另行提供。整体画面尚比设计图平，人工接受、正常窗口性能与其它模式/UI推广继续开放。

收尾原生窗口实查：CoastalDrive · Vehicle Dynamics Lab（2361712，会话53916）已置前台并最大化，初始空态可交互；先观察最大化过渡后再次确认最终画面，无启动试验或改用户记录。数据隔离在B盘player-lab-preview。保留的[原始视窗](lab-before.png)、[当前独立视窗](lab-after.png)、[游戏内共享视窗](lab-shared.png)均为实际运行截图。物理/资源/检查原值见[summary.json](summary.json)，[当前源码与资源指纹](source-sha256.json)。

## 剩余入口

最新共用性能增量：[精确静态签名复用与凸体包刷新](../PERF-SMOOTH-01/static-signature.md)。完整步ABBA约减6.59%、最终两模式720快照同原版、48项T1/Ruff/三种子过；滨海两模式/山地真实入口各190/270m验证，仍有38.76/51.06ms长帧。未修改视觉方案，设计38与其它场景/UI/试验台范围保持。当前PERF76/视觉95，B盘、无保留窗口、无提交推送，总目标active。

2026-10-28最新接续：[短草实体样段](coastal-meadow-candidate.md)修正源遮罩后仍稀疏发暗，未采用；默认动态海面/天空/镜位保持。[正常配置物理热点与两项拒绝实验](../PERF-SMOOTH-01/coastal-static-candidates.md)保留完整快照/ABBA证据，不宣称性能改善。实际补海浪纹理/地表glsl漏打包，5项T1/Ruff/三种子过；本轮无新增正常驾驶，当前严重卡顿结论保持。PERF72/视觉91，整体目标active，无保留窗口，无提交/推送。

**滨海当前接续**：用户要求落日，并否定与设计38不符及模糊。当前8K完整天空/多尺度风浪已接入，相关42项T1通过，两模式正常各190m/0碰撞丢时，但自由出现41.16ms一帧，视觉仍未验收。[实际图、失败和正常驾驶证据](coastal-sunset.md)。原实验台第一块证据仍有效，不能据本次通过宣布全面升级。

**水面静止修复**：用户反馈后确认静态合批将sea_time固化在Geom中；现排除原动态水面，实际Geom/GPU随时间变化，正常入口4秒实录已留。相关T1 42项通过，单窗口两模式仍有一次34.32ms长帧，分项集中快照调用。[修复、动态视频与边界](water-motion.md)。

| 范围 | 当前真实状态 | 下一步 |
| --- | --- | --- |
| 生涯/无限高速及制动、过门、山路、超车等endless模式 | 共用local_kcd_drive表现装配，已有部分升级；各模式目标/交通/天气仍需实图核对 | 在各自真实入口检查资源与可读性，不能仅据共用函数视为全部验收 |
| 滨海自由驾驶/计时挑战coastal模式 | 使用原有限海岸场景，尚未扩展本机中距离资源方案 | 先采图/研究并生成完整可驾驶样板设计，保护原赛道与碰撞 |
| 主菜单/生涯车库/生涯赛事页 | 已有实际车库背景与统一字体、构图 | 复用认可设计，逐页修未统一部分，不重建整套UI |
| 制动/过门/道路复测/驾驶进阶/试验工坊子页 | 仍有独立工程面板或旧布局 | 先按操作链采图，复用主次层级，补相应设计图后施工 |
| 专家试验台 | 第一块实现及相关检查完成 | 实机人工看光照/接地，后续其它试验条件和正常窗口性能 |

原PERF-SMOOTH-01中被拒种植位置的预算缺口已单独修正并通过40项T1；[原值与边界](../PERF-SMOOTH-01/rejected-site-budget.json)。这项离场结果不能替代正常驾驶卡顿验收。下一继续其它入口的实际差异，保留总性能目标active。

2026-10-28 17:06状态更新：上文保留窗口均已关闭/失效，当前没有试玩窗口。动态水面已修并有视频；最新正常驾驶和旧函数对照均出现明显卡顿，不能再用旧短测说明当前流畅度，见[当前负载边界](water-motion.md)。离线云层实际偏糊已[拒绝](cloud-sky-candidate.md)，未替换默认天空。总目标继续active。

草地增量当前：原inland接入已登记同源底色/法线/粗糙度，几何精确保持；42项T1/三种子过，正常两模式仍明显卡顿，美术/性能门未过。[实际前后与完整边界](coastal-ground.md)。

滨海HUD40已按先研究/生成设计再实现推广生涯四角层级：最终23项T1/三种子与补充4项T0过，两画幅12张夹具图及两模式190米真实图分开记账。当前卡顿明显，不能报性能通过，设计38环境/其它入口仍未完成。[实际结果与失败](coastal-hud.md)。

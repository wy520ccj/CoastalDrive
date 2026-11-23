# 撞击后持续卡顿：重复查询与相机等待

2026-10-28。用户明确反馈滨海严重卡顿、所有模式撞击后会卡一段时间，并提供无限高速实际截图。优先处理这一触发条件，暂停未采用短草样段的扩展。**当前有改善，仍未修完，更未获得人工通过。**

本轮基于HEAD 15c321f5上已有未提交工作，原4份源码备份在`logs/visual-extend-20261028/post-impact-source-before/`。不覆盖旧成果，无提交/推送，所有新输出B盘。完整数值见[post-impact.json](post-impact.json)，[当前真实窗口实图](post-impact-current.png)仅证明运行画面，不证明流畅。

## 触发条件与剩余成本

原Simulation在真实接触临近或撞击后启用120拍细化窗口，期间完整世界至少4子步。固定样本的两次真实撞击共触发179个细化拍；正常120Hz每拍预算8.333ms，旧完整细化拍约15.895ms，积压后显示还需等待权威世界的相机查询。原细化规则、120Hz、完整模拟时间、车辆参数和精度全部保留。

使用玩家实际保存的`coastal-roadster`车辆，经与正常入口完全相同的DrivingMode.GAME配置转换，质量1040kg、平时1子步；保存文件中的2子步不是正常GAME入口的实际值。固定诊断与大窗口报告的完整车辆配置逐字段相等。原玩家文件只读，窗口测试数据隔离在B盘。

旧剖析的260拍中，完整轮胎查询调用18560次，原因是WorldSurface先算缓存路面，再因候选含护栏凸体丢弃结果、重新查询整条射线；四轮共用的大覆盖盒还让远离护栏的轮胎重复扫栏。当前同一剖析样本降至3866次，finite_contact_system仍4852次、共同接触系统仍7682次、真实世界推进仍797次。剖析带观察开销，只用于定位调用链，不当性能百分比。

改后剖析仍主要耗在Bullet实际推进、静态世界读取、共同机械求解与有限接触。注册护栏凸体使当前原生共同接触路径整体退出到Python路径；这是下一项需要保持完整凸体与变换精度来处理的成本，不能直接忽略护栏或仅用当前覆盖盒代替完整世界。

## 本轮修改

- `suspension_contacts.py`抽出原Panda单精度轮轴/姿态转换；新增缓存凸体补查，只补同一冻结世界的原凸体求交，不重复算已得到的路面。原顺序、相同距离时凸体优先、每个刚体内部的最近命中上限保持。
- `vehicle_suspension.py`复用上述路面结果；若四轮总候选含护栏，各轮迭代首次改用自己的真实5cm覆盖盒，离开覆盖范围仍重取完整世界候选。新混合路面/护栏72条射线与完整路径结果精确相同。
- `session_clock.py`与`session.py`让已到达的串行相机查询先结束，再进入下一追赶拍。查询仍在唯一世界锁下执行，异常通过finally释放等待；不增加固定休眠、不跳拍、不丢时间。实际一个长物理拍与系统调度仍能造成等待峰值。

## 固定初态完整步ABBA

8辆交通，正常与撞击各480拍。仅在测试开始设置初态与速度，之后由原Control/Bullet推进；这不是正常驾驶或人工流畅度验收。四次运行每次960个完整Snapshot哈希相同（只将跨会话contact/impact epoch归零），全部车辆配置相同，两次撞击和179细化拍保持。

| 顺序 | 细化拍均值 | P95 | 最大 |
| --- | ---: | ---: | ---: |
| A1原 | 15.904ms | 22.267ms | 38.681ms |
| B1新 | 12.278ms | 15.940ms | 25.324ms |
| B2新 | 12.476ms | 16.819ms | 22.753ms |
| A2原 | 15.885ms | 20.660ms | 36.768ms |

两组均值15.895→12.377ms，减少约22.13%。**新值仍超过8.333ms预算，不能宣布撞后实时通过。**

## 实际大窗口与反向对照

2509×1180实际渲染尺寸，原音效、8交通、玩家原车型、默认画质与120Hz。从静止正常加速，在20米后转向撞护栏；全程没有中途修改姿态/速度。每轮都在tick938、模拟时间7.816667秒发生真实撞击，再观察5模拟秒。全部窗口全程前台、0最小化、0丢时，结束后才截图，不把截图开销混入帧时。

| 版本 | 帧数/全前台 | 最大权威积压 | 撞后第2–5模拟秒帧时P95 | 同区间最大帧 |
| --- | ---: | ---: | ---: | ---: |
| 原查询/原时钟 | 901 | 1013.787ms | 61.952ms | 77.047ms |
| 新查询/原时钟 A1 | 1053 | 635.710ms | 24.769ms | 96.143ms |
| 新查询/查询交接 B1 | 1034 | 636.163ms | 18.381ms | 80.157ms |
| 新查询/查询交接 B2 | 1051 | 632.369ms | 22.584ms | 72.079ms |
| 新查询/原时钟 A2 | 1042 | 631.045ms | 39.433ms | 86.551ms |

窗口百分位采用线性插值，原始帧与各阶段耗时保留。查询交接ABBA的恢复区间P95两次均较原时钟低；物理积压约0.63秒基本不变，符合它只减少读取饥饿的职责。不能用这组短样本归因全部最大帧变化。

原版77.047ms恢复帧中相机往返60.735ms、快照10.214ms、音效0.049ms、渲染4.810ms。改后仍有72–80ms长帧，长步、读取等待与积压继续开放。本轮仅对滨海真实撞击做窗口对照，**未据此宣布山地、高速或所有碰撞模式通过**，也没有用自动转向代替用户驾驶体验。

## 回归与失败

- 初次诊断静置阶段缺少solve_ms计数导致KeyError，随后修复工具；初次T0 Ruff报导入排序失败，修正后T0-cached-hulls-r2、T0-per-wheel、T0-query-handoff通过。失败目录原样保留。
- 首次相关T1包括完整车辆碰撞模块：88通过、1失败，后续三种子按fail-fast未跑。失败是悬空对称制动子步收敛检查`test_symmetric_airborne_braking_preserves_symmetry_as_tire_step_refines`，断言0.2999916116738177 < 0.25041580251126305失败。
- 在本轮修改前的4份原源码重新运行同一节点，得到完全相同的失败/数值（16.21s）。该旧问题继续开放；没有删测试、放宽断言或称完整碰撞模块通过。
- 最终独立相关T1覆盖完整convex_queries、suspension_query_lifetime、suspension_contacts、static_support_cache、session_clock、session_process、impact_events、world_substeps：**60通过/21.69s**，全src/tests/tools Ruff与0/17/23各1200步种子通过。新增正常/异常相机交接均过。最后诊断工具仅补源文件元数据，针对这些文件再跑Ruff通过，未重跑有效T1。
- 180份生产源码/原生文件仅session.py、session_clock.py、suspension_contacts.py、vehicle_suspension.py变化，其余176份保持，所有原生二进制和模型/美术/镜位保持。旧PERF76中72份保持、4份明确更新，新增登记后82；视觉95中91份保持、4份明确更新，新增后101。旧指纹另存B盘，当前两登记全部匹配。
- 所有测试窗口已结束，没有保留预览。没有新增人工接受、长期性能Gate或全模式验收结论。

主要复现命令（原版通过工具或前置模块加载使用上述只读源码备份）：

```text
.venv/Scripts/python.exe tools/performance/check_post_impact.py --workspace <玩家vehicle.json> --output logs/visual-extend-20261028/post-impact-<版本> --steps 480 --traffic 8
.venv/Scripts/python.exe tools/performance/check_post_impact_window.py --workspace <玩家vehicle.json> --output logs/visual-extend-20261028/post-impact-window-<版本> --size 2509 1180 [--baseline-source <4份源码目录>]
.venv/Scripts/python.exe tools/validate.py T1 --tests tests/test_convex_queries.py tests/test_suspension_query_lifetime.py tests/test_suspension_contacts.py tests/test_static_support_cache.py tests/test_session_clock.py tests/test_session_process.py tests/test_impact_events.py tests/test_world_substeps.py --output logs/visual-extend-20261028/T1-post-impact-current --timeout 300
```

## 高速截图中的未完成美术

用户[无限高速原图](../VISUAL-EXTEND-01/highway-user-feedback.png)确实有重复格子山体与白色粗盒城市。

`tools/environment/local_coastal_landscape.py::landscape_materials`将`coastal_cliff_01_diff_2k.jpg`接入通用rock/MOUNTAIN_MATERIAL；原图实际是扫描模型的UV展开图，含多个不连续岛与边界，后者却按世界坐标/18三向平铺，形成大面积重复拼块。已实际查看原图确认，尚未更换或声称已修好。

无限道路城市实际来源是`src/environment/expressway_route.py`中route-city、city-window-band与crown盒体，当前仅分层盒体/整圈窗带，确实未完成，不是资源加载成功就算完工。旧有限高速原型不是本截图的来源，后续不能修错入口。实质性山体/建筑制作仍须按地区规格39先研究/设计，再按图制作与实际驾驶视角对照；保留原道路/物理及认可山地48d天空。整体VISUAL-EXTEND-01与性能目标继续active。

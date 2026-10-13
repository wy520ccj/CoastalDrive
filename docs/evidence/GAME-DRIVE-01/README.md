# 当前游戏路径与操控取舍

基线：2026-10-13 main `ebcc448`（实验台/字体/菜单修订版）。任务：[GAME-DRIVE-01](../../tasks/GAME-DRIVE-01.md)。原setup.py、悬架准备源码与测试未改；使用现有DLL，不重建另一施工线的扩展。冻结源码/DLL：`logs/game-drive-r1/baseline/src`；资源只读引用当前assets。

## 初始入口与转向块（r1历史结果）

游戏与实验台共用当前Simulation、完整玩家车辆、轮胎/悬架/传动/电子控制、碰撞/CCD、120Hz及两个机械子步。实验室的VehicleCommand仍进入原完整执行器。游戏优先使用已有TrafficVehicle：真实Bullet车身/碰撞、原生悬架/轮胎，省略NPC的有限传动联合迭代、胎体弹性、转子输运及ABS/TCS/ESC。没有进一步削减玩家模型，也没有还原旧源码。

游戏启动忽略旧保存的simulation输入设置；F2只设置ABS/TCS/ESC，不再通过输入选项改变NPC模型。底层simulation模式保留供研究与显式诊断参数使用，实验台界面不属本任务。

游戏Control采用一次无超调转向响应：打舵时间常数0.10s、回正/反打0.06s，沿用硬件50°/s限速；松键后每拍减舵，反打不继承旧角速度。键盘不再另加累积。车速包络名义横向加速度7.5→4.5m/s²（非实际横向加速度硬限制），GR86在100km/h的目标上限1.405→0.843°。低速保留完整机械限位；油门、刹车、自动倒车与相机规则保持。游戏成绩隔离为game-keyboard-v31。

## 测量

同GR86、seed23、弯坡高速，预热60拍/采样240拍完整世界（不含绘制/IPC）；分别串行测量，不能当作前台FPS：

| 冻结基线 | 完整步均值 | P95 |
|---|---:|---:|
| 正常0NPC | 3.004ms | 3.506ms |
| 正常12原生NPC | 5.047ms | 7.464ms |
| 直接输入12完整NPC/9worker | 11.589ms | 14.667ms |

120Hz预算8.333ms。因此先固定正常NPC路径，保留玩家完整模型；无依据再删玩家仿真量。

同100km/h真实GR86/同一lab平面，仅初始化设置滚动初速，之后全部由Simulation推进：

| 右转按键 | 原直接输入松键角/后续峰值 | 新游戏松键角/后续首拍 | 新游戏松键0.3s后 |
|---|---:|---:|---:|
| 0.1s | 0.260° / 0.921° | 0.533° / 0.464° | 0.00359° |
| 0.3s | 3.544° / 6.674° | 0.805° / 0.700° | 0.00542° |
| 0.5s | 9.665° / 14.068° | 0.845° / 0.736° | 0.00569° |

新游戏松键后不继续增加转角，三条轨迹零玩家碰撞。这是离线操控数值证据，非人工手感。对应`steering-before-r2`/`steering-after`。原正常分支未单独重跑该操控探针，不将其与原直接输入混称同一基线。

直接VehicleCommand旧/新对照：三工况共192+216+240=648拍，完整Snapshot SHA逐拍相同，所有记录行相同（`exact-comparison.json`）；人工实验室效果仍由其施工线验收。

## 有效前台

两次保持同一当前外部应用负载，不关闭用户应用、不调优先级/亲和性。1080p、Draw管线、独立权威会话、GR86/seed23/弯坡高速；音频按既有smoke工具关闭。旧默认路径30秒、新游戏60秒为各自短样本，时长不同，不计算配对性能百分比。

| 场景 | 物理Hz | 绘制FPS | P95 / P99 | 丢时 | 玩家碰撞 | 短Gate |
|---|---:|---:|---:|---:|---:|---|
| 原直接输入12完整NPC | 70.421 | 73.697 | 17.844 / 20.704ms | 11.1s | 0 | fail |
| 新游戏12原生NPC | 119.987 | 81.941 | 17.062 / 20.072ms | 0 | 0 | pass |

两次窗口前台/父进程/权威会话/worker源码有效。新游戏距离1356.559m，>50ms长帧0，近景pending0。原窗口距离240.490m，未满足工具距离与实时Gate，不把显示流畅作为实时证据。18NPC检查及T1结果待记录。

## 命令与失败

```powershell
.venv/Scripts/python.exe tools/performance/benchmark_physics.py --source logs/game-drive-r1/baseline/src --output logs/game-drive-r1/baseline-game-12 --workers 0 --traffic 12 --mode game --traffic-input-mode game --track endless --shape hills --driver endurance --seed 23 --warmup 60 --steps 240 --capture-hashes
.venv/Scripts/python.exe tools/game_drive_check.py --source logs/game-drive-r1/baseline/src --output logs/game-drive-r1/steering-before-r2 --mode simulation
.venv/Scripts/python.exe tools/game_drive_check.py --output logs/game-drive-r1/steering-after --mode game
# --exact分别输出exact-before/exact-after，比较完整快照；默认模式为game。
.venv/Scripts/python.exe tools/performance/benchmark_runtime.py --output logs/game-drive-r1/window-after --shape hills --seconds 60 --track endless --vehicle-design gr86-2022-premium-6mt --driving-mode game --traffic-count 12 --independent-clock
```

首次T0为20通过/2失败：低速大转角回正仍受50°/s硬件限速，新增测试误把所有车速都要求0.3秒回到1%；修正测试按低速1秒/高速0.3秒、保持逐拍立即减舵及限速断言后22项T0/Ruff通过。原测试未放宽。新增100km/h真实反打回正回归待执行。

操控工具首次误用不存在的LabRun类名，改为实际LabExperiment后成功。前台冻结基线首次缺少子进程assets路径，确认进程结束后补只读资源junction再测，原失败保留；未使用该启动作为性能样本。繁忙检查首次工具只核对数量而未设置密度，实际12辆导致启动失败/退出清理挂起；仅终止本次已核实PID的两个诊断进程。修工具通过真实Session的busy密度重开，并在数量不支持时关闭会话后报错，18辆重新测量。没有关闭用户实验台或其它应用。

T2/T3/长时间前台/声音未跑，本任务不将既有旧海岸长跑求解失败宣称修复。游戏自动收据、用户实际驾驶分别记账；用户手感验收待确认。

## 当前试玩

[当前游戏源码入口](../../../launchers/game-current.cmd)固定game输入，沿用本机车型/皮肤及电子开关；支持从主菜单进入实验室。根试玩与其他独立包仅为历史版本，不承载本轮结果。本轮不推送、不替换公开包。


## 实时追赶与后续取舍（2026-10-13，施工中）

FixedStepper每批最多八拍后交还执行机会，未完成时间保留，下一批必须真实计算；没有变大dt、外推车辆、删欠账或修改现实时间。会话传输新增真实物理落后毫秒诊断。200ms人为停顿后完成全部拍并追到25ms以内；相关T0通过。长期超预算仍会积压，因此不能用丢时0单独认定实时通过。

| 有效前台短窗 | 物理Hz | FPS | 物理落后P95 / 峰值 | 结论 |
|---|---:|---:|---:|---|
| 18NPC原两子步、原丢时钟 | 118.713 | 67.041 | 未记录 | 丢时0.55s，fail |
| 18NPC保留欠账、两子步 | 119.929 | 66.302 | 96.228 / 123.433ms | fail，用户指出明显卡顿 |
| 恢复原相机查询，权威分项诊断 | 114.003 | 56.643 | 1288.149 / 1424.505ms | fail，含计时插桩，不作最终性能 |
| 一次机械求解、纯数值期间释放查询锁，诊断 | 119.980 | 63.915 | 22.779 / 45.617ms | FPS仍fail，含计时插桩 |
| 初始车辆合批60s候选 | 119.148 | 75.456 | 589.933 / 809.978ms | 实时fail；轮枢轴烘焙错误，禁止采用为最终结果 |

全部窗口保留真实18NPC、碰撞、弯坡、1080p、seed23、GR86硬件；音频按smoke关闭。窗口有效性与绘制采样在对应report.json中核对。没有关闭用户应用或实验台。短Gate现在要求FPS≥70、物理Hz≥119.9、落后P95≤25ms/峰值≤100ms、丢时0；工具旧passed只含路线完成，必须看short_performance_passed。无绘制8s的119.804Hz/落后P95 15.999ms只是隔离证据。

权威进程分项计时：两子步完整session-tick均值8.24～8.69ms，预算8.333ms；其中世界推进约6.72～7.04ms，联合数值求解约0.66～0.70ms/子步。主窗口renderFrame均值10.767ms/CPU10.276ms，窗口更新5.260ms，相机往返2.657ms；嵌套项不能相加。计时插桩有开销，不用它认定稳定吞吐。

游戏现在每120Hz拍一次完整机械求解（tire_substeps=1），保留当前弹性轮胎/转子/有限传动/耦合悬架/电子控制/碰撞方程；实验台SIMULATION保留设计两子步，不读取游戏取舍。成绩版本game-keyboard-v32。单步路径也通过已有数值请求/提交边界释放查询锁，不让相机等完整拍。独立无绘制18NPC480拍均值4.475ms/P95 8.011ms；不是前台验收。

新增game_mechanics_check对五种车型的μ1.1/0.6制动与100km/h键盘反打做同初始化/两子步与单步对照，各15条。30条全部完成、无非有限状态、无异常求解；单步停车距离比两子步少0.082～0.119m，反打后第一拍立即减舵、300ms余角约0.0046～0.0053°。例如GR86 μ1.1为37.749→37.656m、μ0.6为66.844→66.742m；游戏调校为43.980→43.897m、66.350→66.237m。仅该工况的数值取舍证据，不宣称所有场景完全等价。实验台完整方程和界面没有修改。

另外消除交通控制重复数学、NPC同一请求两子步的重复原生执行器设置、Snapshot metadata二次replace；各480拍完整SHA相同。NPC准备单对均值6.551→6.193ms，不能认定稳定收益。玩家碰撞与音效共用一次玩家接触集合，原冲量/距离/顺序/碰撞计数保持；480拍SHA相同，单对4.757→4.775ms无明确整步收益。

车辆表现合批仅发生在Scene的涂装完成后，车身装配变换和轮枢轴保持；在单位子节点中合并静态几何，转向灯不合并。原直接flatten轮枢轴候选出现车轮悬空，已修正，未进入主源码。修正后六张1920×1080同物理姿态/前后视点，每图176～315像素变化，单通道RMS≤0.136/255；实图已查看，轮位及外观保持。统计原2897节点/2502Geom，修正候选约785节点/1769Geom。首图片工具遗漏PBR任务更新导致shader input断言，修正后重跑；原截图只作失败记录。此为静态对照，不替代动态HUD/车辆无闪烁检查。

被拒绝的候选：省略玩家胎体弹性/转子输运后求解更慢；NPC决策分摊、75Hz显示限帧均无实时收益；相机由物理所有者排队执行及混合排队均更慢，已撤回；子进程1ms线程切换更差，撤回。Cull/Draw已有PERF-04-FIX真实动态文字缺失证据，保持/Draw，未重新采用。合批依据Panda3D官方的局部网格合并说明：https://docs.panda3d.org/1.9/cpp/optimization/too-many-meshes 。不合并整个地图或动态车辆根。

验证账：初始输入T1为61测试/Ruff/三种子1200拍通过；最近游戏120Hz相关T0为32测试通过。合批/接触T0初48通过/2失败：既有撞击测试的计时覆写未接收新增manifolds参数，更新覆写并继续转发，原真实冲量和计数断言保持；补充世界子步生命周期覆写同样接入。最终T1为88测试/Ruff/三种子各1200拍通过（t1-current-r2）；两次当前源码前台窗口状态无效，T2/T3和用户手感仍待完成。旧10000拍求解失败冻结基线同残差复现，未声称修复。

日志根：logs/game-drive-r1。主要新增目录：window-authority-detail、window-120mechanics-query-r2、mechanics-one-r2、mechanics-two、contact-before/after、render-before-batch-r3、render-after-batch-r4、t0-batch-contact。完整源码、现有DLL和原失败均保留在本地日志，不做远端发布。


## 当前源码收据

- 最终T1：88测试、Ruff、0/17/23各1200拍通过；含五种实际资产合批后的动态轮位/车身包围检查、游戏输入/实际反打、模式/界面、NPC、时钟停顿/暂停、独立会话/快照传输、实验室/工况、真实护栏音效接触及两子步瞬时障碍撤除。原撞击断言和数值阈值未放宽。
- window-current-r2：GR86硬件/18NPC/60s；第29秒起minimized=true/foreground=false，整段前台无效。独立进度119.984Hz、丢时0、落后P95 17.415ms/峰值202.172ms，绘制有效区间85.594FPS；不能用此组合认定完整前台实时通过。
- window-current-game-tuned：用户当前游戏调校/18NPC/30s；第4秒起foreground=false、未最小化，前台Gate无效。119.940Hz、丢时0、76.132FPS、P95 21.669ms/P99 26.541ms、落后P95 30.925ms/峰值66.736ms，零>50ms/零碰撞；即便忽略失焦，P95落后仍超25ms，不改门槛。
- 两次失焦与先前用户指出的有效窗口卡顿分开记录，后者仍是明确fail。所有进程已正常结束，只保留用户已有实验台进程；没有反复强抢前台。
- protected-files-final.json证实vehicle_suspension.py/wheel_contact_kernels.c/suspension_prepare.h与初始冻结源SHA相同；未重建DLL。source-checkpoint-hashes.json保存本次源/DLL版本。已有setup.py和悬架准备及其测试保持未提交，提交范围只含GAME-DRIVE-01。

```powershell
.venv/Scripts/python.exe tools/game_mechanics_check.py --source logs/game-drive-r1/candidate-120mechanics --output logs/game-drive-r1/mechanics-one-r2 --substeps 1
.venv/Scripts/python.exe tools/game_mechanics_check.py --output logs/game-drive-r1/mechanics-two --substeps 2
.venv/Scripts/python.exe tools/validate.py T1 --tests tests/test_vehicle_batch.py tests/test_game_steering.py tests/test_keyboard_steering.py tests/test_driving_modes.py tests/test_driving_mode_ui.py tests/test_vehicle_commands.py tests/test_npc_physics.py tests/test_session_clock.py tests/test_session_process.py tests/test_snapshot_wire.py tests/test_lab_experiment.py tests/test_lab_maneuvers.py tests/test_impact_events.py tests/test_world_substeps.py --output logs/game-drive-r1/t1-current-r2
.venv/Scripts/python.exe tools/performance/benchmark_runtime.py --output logs/game-drive-r1/window-current-game-tuned --shape hills --seconds 30 --track endless --vehicle-design game-tuned --driving-mode game --traffic-count 18 --independent-clock
```

下一步：保留当前修正，在有效前台条件下核验普通12/繁忙18的真实时间欠账及动态HUD/轮姿，再针对已测的CPU准备/提交与流送尖峰继续优化；用户真实操控验收独立待确认。整体目标保持active。

提交前边界复核补充：单次世界推进的非耦合配置可能仍有内部轮胎细分，保留其原多请求串行入口；游戏配置明确tire_substeps=1，继续使用单次请求边界。增加1/2子步纯数值释放锁及异常恢复覆盖，相关world/steering/modes T0通过（t0-world-boundary）；原T1其余节点复用，不重复整套测试。

## r2 最新有效短测与未完成边界

源码检查点8ce3d51；其后src/traffic.py只缓存同参数投影数学，src/simulation.py复用本拍已读位置/同批邻车表，src/highway_driver.py只缓存同一20Hz不可变感知批中的邻车查询。决策频率、随机序列、重定位/生成/回收和碰撞规则保持。logs/game-drive-r2/before-step、after-step、after-neighbors的1200拍完整快照SHA全部相同；全推进单次序列均值4.282679→4.176124ms、P95 8.145635→7.637355ms，非稳定配对整体收益。T0 27项/T1 11项、Ruff、0/17/23各1200拍及0/23各30模拟秒弯坡通过；原88项T1/世界边界有效覆盖复用。未修改/重建protected悬架原生工作。

| r2有效1080p前台，game-tuned | 时长 | 物理Hz | 绘制FPS | 帧P95/P99 ms | 落后P95/峰值 ms |
|---|---:|---:|---:|---:|---:|
| window-normal，高速12NPC | 60s | 120.005200 | 87.116560 | 15.5272/17.5485 | 13.5600/37.9065 |
| window-busy，高速18NPC | 60s | 119.989365 | 86.073011 | 17.3984/20.1333 | 15.4121/37.8105 |
| window-time-trial-active，计时0NPC | 45s | 119.997032 | 87.489730 | 14.6638/16.1365 | 8.3721/8.8552 |

以上三份report.json的window_sampling_valid/short_performance_passed均true；丢时0、>50ms帧0、驾驶presentation停滞0、碰撞0，真实路线均≥600m。高速seed23/hills，计时coastal；音频按既有smoke关闭。不将短测等同长期/声音/实际操控验收。2026-10-13用户反馈当前画面可以，未明确认定操控通过。

诊断工具增补驾驶阶段/显示停滞统计、实际玩法/完赛停止和闭环路线增量。初window-time-trial跨完赛后结算静止约9.4秒，原100.214Hz与812停滞帧含正常停止，不能用于驾驶慢动作诊断；原报告保留。同时其结算切换67.0319ms是真实长帧。window-results-trace完成50.606秒有效比赛，但窗口最小化/失焦，前台Gate无效；panel-refresh峰值34.8225ms、成绩写盘2.2713ms仅作线索，结算切换尚无最终修复/通过结论。

```powershell
.venv/Scripts/python.exe tools/validate.py T0 --tests tests/test_endless.py tests/test_traffic_behavior.py tests/test_highway_curve.py --output logs/game-drive-r2/t0-traffic
.venv/Scripts/python.exe tools/validate.py T1 --tests tests/test_h4a_traffic.py tests/test_session_process.py --output logs/game-drive-r2/t1-traffic
.venv/Scripts/python.exe tools/performance/benchmark_runtime.py --output logs/game-drive-r2/window-busy --track endless --shape hills --seconds 60 --vehicle-design game-tuned --driving-mode game --traffic-count 18 --independent-clock
.venv/Scripts/python.exe tools/performance/benchmark_runtime.py --output logs/game-drive-r2/window-normal --track endless --shape hills --seconds 60 --vehicle-design game-tuned --driving-mode game --traffic-count 12 --independent-clock
.venv/Scripts/python.exe tools/performance/benchmark_runtime.py --output logs/game-drive-r2/window-time-trial-active --track coastal --game-mode time_trial --seconds 45 --vehicle-design game-tuned --driving-mode game --traffic-count 0 --independent-clock
```

r2当时源码/诊断/文档未提交；旧失败保留，后续本地收口范围见r3，本轮无推送/公开包更新。

## r3 结算切换、真实绘制与本地收口

日志logs/game-drive-r3。probe_results_panel使用真实UI/完成态夹具，仅定位结算创建，不冒充跑圈或前台Gate。panel-before-r2为35.0478ms，逐前缀TextNode.getWidth约30ms；panel-after直接calcWidth候选134.0889ms更慢，已撤回。当前加载阶段生成并保留固定结算字形几何/prepareScene，关闭时释放；fit_lines整行放得下则只测一次，溢出沿用原算法。panel-after-r2与panel-after-wrap分别7.0382/6.6503ms，100组换行旧/新相同。截图结算面板RGB区域(470,155)-(1440,850)逐像素相同，标题/说明/成绩区域亦全同；全幅背景622像素变化/RMS 0.663664/255。初RGBA getbbox受零alpha差影响误报全图一致，随后转RGB实测并修正；rgb-image-comparison.json保留结果。离屏初帧仍有冷初始化开销，不能当作整个流程性能证明。最初probe漏PBR任务更新导致shader输入缺失，后补真实taskMgr.step；初失败/profile保留。

window-results真实完赛但即时退出，原始物理119.878Hz包含约48ms结算尾部，shortGate false报告保留；显示最大24.915ms、0帧>50ms。工具后续显式记录第一/最后驾驶状态权威进度，不把结算正常停止算吞吐；新增--results-seconds及切换附近帧记录，控制器标签改为实际route-driver-90。

window-results-r2实际有效完赛50.606模拟秒，另观察2.000秒结果页，全程foreground且未最小化，短Gate通过。驾驶119.947380Hz、落后P95 8.3156/峰值13.0752ms；绘制86.617877FPS/P95 15.3896/P99 16.8071/最大23.8332ms；切换主帧22.5819ms，0帧>50ms、丢时0、驾驶显示停滞0、碰撞0。该收据是实际RouteDriver跑圈，不是完成态夹具；仍按smoke关闭音频。

T0初Ruff导入格式失败，修正后9通过/1失败。失败仅test_ui_modes_results_and_existing_keys仍要求六按钮，与既有实验室第七入口冲突；baseline-ui-test.log加载冻结application-before.py同失败复现。仅修旧菜单预期，完整该节点T1与Ruff/0/17/23各1200拍通过，复用其余九项有效T0。不重复r2物理/交通和r1完整机械有效检查。protected-files.json记录三悬架源SHA不变；未重建原生扩展。

```powershell
.venv/Scripts/python.exe tools/performance/probe_results_panel.py --output logs/game-drive-r3/panel-after-wrap
.venv/Scripts/python.exe tools/validate.py T0 --tests tests/test_results_keyboard.py tests/test_ui.py tests/test_ui_assets.py --output logs/game-drive-r3/t0-results-r2
.venv/Scripts/python.exe tools/validate.py T1 --tests tests/test_ui.py::test_ui_modes_results_and_existing_keys --output logs/game-drive-r3/t1-results
.venv/Scripts/python.exe tools/performance/benchmark_runtime.py --output logs/game-drive-r3/window-results-r2 --track coastal --game-mode time_trial --seconds 60 --results-seconds 2 --vehicle-design game-tuned --driving-mode game --traffic-count 0 --independent-clock
```

本地收口包含r2交通复用、r3结算字形/换行准备、诊断工具/既有测试预期及任务文档；protected工作不提交。当前画面已获用户认可，实际转向手感、长期/声音与T2/T3阶段仍开放；goal active，不推送或替换公开包。

## r4 正式音频负载、120秒测量与未解决绘制等待

基线b70c8ce，日志logs/game-drive-r4。smoke_audio隔离设置/成绩但使用正式OpenAL/Soundscape，默认静音smoke与交互音频语义保持。--audio核对有效OpenAL设备、每秒采实际声音状态；--extended显式允许60秒以上到300秒，默认短测不变。首次120秒命令缺--extended被原边界拒绝，未启动窗口，不算样本。声音T0九项、声音键/设置隔离节点T1与Ruff/三种子通过；新增诊断同步参数后收口T1-final同节点/三种子通过，旧数值/操控/实验台结果复用。

| r4有效前台/18NPC/弯坡/seed23/game-tuned/正式声音 | 时长 | 物理Hz | FPS | 帧P95/P99/最大 ms | 落后P95/峰值 ms | 结论 |
|---|---:|---:|---:|---:|---:|---|
| window-busy-audio，无分项插桩 | 120s | 119.996423 | 83.811312 | 18.1881/20.4717/111.3062 | 16.0858/120.3650 | 严格样本Gate fail |
| window-busy-audio-trace，分项 | 60s | 120.002700 | 见report.json | 0帧>50ms | 16.2122/43.4414 | 短阈值通过；诊断非最终收益 |
| window-busy-audio-trace-r2，分项/物理GC | 120s | 120.000108 | 83.357287 | 18.7652/21.0092/131.8157 | 16.1301/43.0290 | fail；定位绘制等待 |
| window-busy-audio-no-vsync，同步关闭候选 | 120s | 120.002824 | 84.292169 | 17.8409/20.2908/98.2337 | 16.1683/41.7735 | fail；未用于正式入口 |

以上窗口有效，丢时/碰撞/驾驶显示停滞均0。三个120秒样本实际14040～14041拍，117模拟秒与117墙钟秒一致；不是用绘制FPS冒充物理吞吐。三个120秒样本各118个稳态采样中，十层引擎与所选电台真实状态均PLAYING，OpenAL设备有效；不宣称新的人工听感结论。

长帧定位：第二次120秒第54.459秒绘制131.816ms；同刻render-frame慢调用started_at=1819.282176、wall=121.5939ms/cpu=0。两端GC、物理、声音/设备更新无同刻对应长事件。常规physics-road-attach约20～27ms与camera-roundtrip约33ms时间戳相关，不解释122ms绘制等待。证据定位到绘制等待，未证明具体GPU/驱动故障。首无插桩120秒111.306ms失败保留，60秒未复现不能关闭它。

诊断峰值修正：原phase_timing.wall_max只取最近4096调用，可能漏掉前半程大峰值；slow_calls保留了上述122ms原始事件。工具改为全区间最大值和慢调用起点/CPU/墙钟；原报告不改。分位数仍标window_samples，嵌套耗时不能相加。

同步对照依据Panda3D官方[同步配置说明](https://github.com/panda3d/panda3d-docs/blob/1.10/optimization/index.rst)与[v1.10.16 WGL上下文reset源码](https://github.com/panda3d/panda3d/blob/v1.10.16/panda/src/wgldisplay/wglGraphicsStateGuardian.cxx)：同步值在上下文初始化时设置，因此诊断参数在ShowBase创建前传入；不能运行后只改PRC值假装对照。关闭候选仍98.234ms长帧，未采用；正式游戏同步默认true、原/Draw管线保持。

主要命令（各诊断输出目录独立）：

    .venv/Scripts/python.exe tools/validate.py T0 --tests tests/test_soundscape.py --output logs/game-drive-r4/t0-audio
    .venv/Scripts/python.exe tools/validate.py T1 --tests tests/test_ui.py::test_driving_radio_keys_defer_disk_save_and_leave_panel_intact --output logs/game-drive-r4/t1-final
    .venv/Scripts/python.exe tools/performance/benchmark_runtime.py --output logs/game-drive-r4/window-busy-audio --track endless --shape hills --seconds 120 --extended --vehicle-design game-tuned --driving-mode game --traffic-count 18 --independent-clock --audio

两次分项另加--trace-phases；同步候选另加--vsync off。不删模型、不修改实验台/保护悬架文件、不重建DLL、不推送/换公开包。实际操控与偶发绘制等待仍开放，goal active；下一绘制线程/驱动等待分项，复用已有数值/短测证据。

## r5 / 2026-10-14 用户验收收口

实际反馈原文：“短按可控，松键和反打响应正常”；在明确告知约84FPS/120Hz/无丢时、较长样本仍有一次约0.1秒停顿后，用户确认“整体流畅，偶发短停可接受”。本次目标据此通过人工验收；严格零长帧样本仍fail，旧自动结论不改，不推广为长期/阶段T2/T3通过。

单线程120秒有效对照window-busy-audio-single-r2：物理120.000258Hz、75.967184FPS、P95/P99 17.4841/21.2731ms、最大137.2034ms，两帧>50ms；落后P95/峰值15.8984/37.4624ms，丢时/碰撞0。未用于正式游戏。首single对照第11秒起失焦（本次pstats -h实际弹出辅助GUI）；已关闭本次helper，报告无效且保留。

text-stats全量GPU采集window-pstats仅为高开销诊断；UDP发送异常后转TCP，原始输出约2.684GB，停止的只是一经PID/命令确认的本次采集器，客户端正常完成120秒。Main/Draw/GPU接收帧数5071/3739/5087，协议允许丢失/乱序；不能当完整帧序列。第265绘制帧120.016ms中，111.910ms属于PStats自身Check residency，Flip:End仅0.063ms；不能把该停顿归因于正常游戏。依据[该版本TextMonitor原始格式](https://github.com/panda3d/panda3d/blob/v1.10.16/pandatool/src/text-stats/textMonitor.cxx)和[GL驻留检查的连接条件](https://github.com/panda3d/panda3d/blob/v1.10.16/panda/src/glstuff/glGraphicsStateGuardian_src.cxx)。归档render-pstats/raw.txt.gz为282080545字节，原始2683708975字节，SHA b12818eed7b5fef70338e8eca983ca0149fdea86ee7b12602eb15434b8445a04；解压逐字节SHA一致。原始文件清理被自动审批拒绝、未给具体原因，因此原文件也保留。

PStats端口/GPU/限时改版未完成运行验收，整体从正式工具撤回；原型logs/game-drive-r5/benchmark-pstats-experimental.py仅供历史定位，不能作为产品入口。生产代码与ef6d377相同，正式/Draw、同步、声音、机械与实验台保持。收口核对r1～r4实际报告/源码SHA/命令边界：直接命令648拍完整SHA相同、交通1200拍相同、五车型30条积分工况无错误/碰撞、制动差0.0820507～0.1186269m；相关T0/T1/Ruff/三种子有效结果复用，未重跑不变的检查。保护三源SHA一致、未重建DLL。

完成本次游戏共享新力学机制、实时与手感目标；用户明确接受偶发短停，保留绘制等待为已接受改进项，不将严格Gate fail改pass。当前源码入口仍game-current.cmd；收口仅本地文档提交，不推送或替换公开包。

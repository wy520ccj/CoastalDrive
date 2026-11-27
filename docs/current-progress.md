# 当前进度

更新：2026-11-26。历史流水账（2026-09 至 2026-11-23 原全文）完整归档于 [current-progress-2026-11-23.md](archive/current-progress-2026-11-23.md)，不再堆积在本文。

## 当前恢复路线与协作方式

项目于 2026-11-23 重启正轨，按单条施工线顺序推进（每阶段独立验收并本地提交）：
1. **阶段 0（已完成）**：拆分本地安全提交、归档瘦身进度页、修正过期 T2 状态。
2. **阶段 1（已完成）**：`LAB-M3` 试验台宿主闭环验收。
3. **阶段 2（已完成）**：定位并修复 `test_continuous_solver.py` 在 `road-edge-sdk` 下的 ULP 校验，T2 全部 14 项物理/道路/交通场景检查 `passed=True`，并完成测试体系整顿与按需分层。
4. **阶段 3（已完成并经用户口头验收通过，已锁入本地基线 `28feaa73`）**：
   - 修复双击 `game-current.cmd` / `vehicle-lab.cmd` 与游戏内进入专家试验台闪退（`ScenePipeline.sync_frame()` 事件泵、`LPoint3d`→`LVecBase3f` 双精度兼容、`vehicle_menu` 11 车型动态填充）。
   - 全站 6 站界面统一至落日工坊（Sunset Atelier）视觉语言并回归浅瓷专家试验台与轻透无盒悬浮 HUD，修复 `application.py` 预算生涯开局右上角按钮重叠与 `test_driving_mode_ui.py` 文案断言；全部 93 份改动已锁入本地提交 `28feaa73`。
5. **阶段 4（`PERF-SMOOTH-01` 常态渲染 + 物理/撞后积压专项优化已落地并完成 ABBA 对照，待人工桌面流畅度复核）**：
   - 渲染热路径（`src/scene.py`、`tools/environment/local_kcd_drive.py`、`tools/environment/kcd_local_environment.py`、`tools/environment/kcd_tree_batches.py`）：`self.render` 根级 `sea_time` / `career_origin_y` 改为按 Draw 阶段复用的 `PTAFloat` `ShaderInput`（单节点 `self.ocean` 保持原接口以兼容全部水面测试），消除每帧令全场景 1.4 万+ GeomNode 组合 `RenderState` 失效的根因；`local_origin_y` 与路段 `setPos` 仅在原点/位置实际变化时写入；交通车与转向灯仅在显隐状态变化时调用 `show()`/`hide()`；远树合批索引保持 32 位运算。
   - 物理与交通热路径（`src/suspension_contacts.py`、`src/tire_drivetrain.py`、`src/static_support_read.h` 重编 `src/wheel_contact_kernels.cp314-win_amd64.pyd`、`src/highway_curve.py`、`src/highway_driver.py`、`src/traffic.py`、`src/npc_physics.py`、`src/vehicle_dynamics.py`、`src/vehicle_suspension.py`、`src/vehicle_tires.py`、`src/world_step.py`、`src/simulation.py`、`src/physics_workers.py`）：
     - 滨海/含凸体护栏赛道在保守四轮子步包络内无未接管刚体时直走已支持表面的原生 C 路径（靠近护栏自动无缝回退原世界查询），消除常态每帧大量 Python 回调；
     - 原生 `static_support_read` 静态驻留方法名、无父节点直接复用 `body.getTransform()`、单形状直读 `getShape(0)` 且先比对 `TransformState` 再按需算矩阵（滨海 `0.878→0.467 ms/次`、高速 `0.779→0.325 ms/次`）；
     - 消除 `HighwayCurve.signs` 重复哈希与 `on_asphalt` 远距离无效 `project()`、`HighwayDriver` 弯道重复曲率/邻车计算、`Suspension` 同子步重复 `on_asphalt` 及单子步空 `dataclasses.replace`、`native_*_workspace` 重复哈希百字段 `VehicleConfig`、`observe` 远距交通车无谓 `contactTestPair` 与空流形矩阵求逆、`TrafficVehicle` 重复 `getWheels()`。
   - **第 2 轮定向修复（2026-11-25，基于用户实机反馈，基线 `eeefec54`）**：针对实机反馈“海岸自由驾驶撞栏后仍严重卡顿/操作延迟；无尽高速高速行驶间歇掉帧且进入城市段尤为严重”定位并修复三大根因：
     - **海岸撞栏物理与锁阻塞**：① `src/coastal_collision.py` + `src/simulation.py` 将海岸 `inner-rail` / `outer-rail`（各 256 凸体）拆分为沿线 8 凸体小刚体（保留原命名、原凸体顶点与碰撞掩码），消除全岛大包围盒令 9 车 `BulletWorld.doPhysics` 慢 4× 的根因（`0.545→0.233 ms/substep`，`-57.2%`），并避免远离护栏时误触发 Python 慢查询；② `src/wheel_contact_kernels.c`（重编 `wheel_contact_kernels.cp314-win_amd64.pyd`）+ `src/vehicle_suspension.py` / `src/suspension_contacts.py` / `src/physics_workers.py` 在 `surface_packet_entry` / `joint_surface_values` 接入懒加载跨网格解析面预检（常规拍 0 开销、仅进边 GJK 时提前取后续网格面界跳过冗余 GJK）并将 `cached_surface_entry` / `surface_initial_hits` 切至原生 C Jacobi SVD 消除 Python `numpy.linalg.lstsq` 回调；③ `src/tire_drivetrain.py` 在全部未接管静态体均为已注册纯数值凸体且轮冠启用时交出 `world_lock`，避免海岸撞栏阻塞相机与快照线程；④ `src/simulation.py:_player_manifolds` 跳过空接触流形。
     - **无尽高速城市段渲染**：`tools/environment/local_kcd_drive.py` + `tools/environment/kcd_tree_batches.py` 在城市段接入 `city_static_candidate.batch_static_steps` 静态表面合批（街道/人行道/路缘/标线/路灯/地基/庭院围墙）、将城市 `mainland-city` 橡树（过滤隐藏父节点）纳入远树合批、为中庭/绿带低灌木补齐 190 m `FadeLODNode` 距离裁剪并关闭 1 m 灌木与远离高速的内外街/庭院树 4K 太阳阴影（保留近高速绿带乔木与建筑完整太阳阴影）。
     - **高速流式加载尖峰**：`tools/environment/local_kcd_drive.py` 将 `surface_weights` / `woodland_texture` 覆盖盒从包含 650 m 海面与 480 m 远山的整段球包围盒（`774×774` 像素）收紧为实际采样地表与树冠影响紧包围盒（按 GLSL 越界恒返 0 保持逐像素等价，重算重叠段由 7 段减至 1–2 段）并补齐 `yield` 边界，同时为草格角点增加段内 `floor_point` 缓存；`src/environment/expressway_route.py` 拆分 `surface-prepare` 并将 `surface-coordinates` 每 8 顶点交还预算；`src/environment/surface_mesh.py` 改为 NumPy 向量化顶点/索引打包。
     - **第 2 轮验证证据（分别记账）**：① 同机交叉 ABBA 对照（相对 `eeefec54`）：海岸 8 NPC 撞栏三场景积压分别减少 **`-50.5% / -63.7% / -49.0%`**（`RailScrape` P95 `13.38→11.10 ms`、max `24.24→16.19 ms`；`HighSpdOuterRail` P95 `14.99→11.11 ms`、max `29.78→17.75 ms`；`HardWallGrind` P95 `12.15→10.89 ms`）；无尽高速 KCD2 城市段 `seg 18` 1280×720 离屏渲染静态中位 `21.78→17.79 ms`（`-18.3%`）、P95 `26.43→22.03 ms`（`-16.6%`），**50 m/s 真实穿越城市段中位 `22.79→18.25 ms`（`-19.9%`）、P95 `27.81→22.00 ms`（`-20.9%`）**；流式单帧 `sync_segments(3 ms)` 峰值 `23.51→14.76 ms`（`>16.67 ms` 帧 `1→0`）；城市段优化前后截图人工核对无回归。② 自动化回归：全部修改文件 `ruff check` 0 错；12 份定向物理/环境测试 **145 passed**（另有 `test_h2_map.py::test_oblique_guardrail_impact_does_not_tunnel[120]` 经核实为 `28feaa73` 基线既有失败，原样保留未掩盖）；0/17/23 三种子无头校验 3/3 通过。③ 人工桌面实机体验：待用户通过 `launchers/game-current.cmd` 复测海岸撞栏与无尽高速城市段流畅度。
   - **第 3 轮体验精修与回退修正（2026-11-25，基于两轮实机复测反馈，基线 `5f06043c`→`e37555d0`→`48a3f2ac`）**：
     - 护栏分块调至 `chunk_size=16`、高速左侧树冠净空 0 侵界、消除随相机移动的草地刷漆波纹、近组橡树直用 `LOD1`。
   - **第 5 轮四大实机顽疾综合根治与深度审查收口（2026-11-26，已锁入本地基线 `b1980b53`）**：
     - 全站 UI 极简清扫与微缩公路小车动态加载条；游戏驾驶（`GAME_INPUT` 有界工程容差）与专家试验台（`SIMULATION_INPUT` 严格容差）求解双轨解耦（200 km/h 斜撞护栏与 8 NPC 连撞 `ArithmeticError = 0`）；短窗撞击细分与 `session_clock` 120 Hz 全步无丢时恢复；无限高速流送 3–4× 提速、LOD 外推、`fwidth` 法线粗糙度滤波与太阳阴影扩展；全量审查 P0–P2 修复与 156 项定向回归全通。
6. **阶段 5（`SIM-FIDELITY-02` 汽车理论与高保真实验台 M1–M5 全链路深化已完成自动化 T1 验收，基线 `b1980b53`，当前工作区未提交，待人工桌面体验复核）**：
   - **M1《汽车理论》解析基线与稳态对账**：新增 `src/theory_baselines.py`（旋转质量换算系数 $\delta_k$、功率/坡度平衡、等速百公里油耗包络、制动 `I/β/f/r` 曲线与同步附着系数 $\varphi_0$、二自由度线性不足转向梯度 $K_{\text{lin}}$ 与特征车速 $u_{\text{ch}}$）及 `quasi_steady_circle` 定半径缓增车速扫点实算 $K_{\text{sim}}$ 对账。
   - **M2 悬架 K&C 与外倾推力**：新增 `src/suspension_kc.py`（默认 `suspension_kc_enabled=False`，旧配置逐拍字节兼容）、`mechanical_kernels.c` 摩擦圆受限联合滑移外倾推力重编及支持变外倾与 $M_z$ 独立留出校验的 `coastal-tire-fit-v2`（满秩 8，留出 $M_z$ 最大归一化误差 `2.13e-12`）。
   - **M3 独立簧下 C 内核 18× 提速与 ISO 平顺性**：将 34 维 `solve_unsprung_joint` 固定构型评估与第 10–33 列雅可比下沉至 C 内核（`ride_bump` 单拍由 `~230 ms` 降至 **`13.02 ms/step`**，保持 `1e-9 / 1e-5 / 1e-9` 严格门槛，单子步最大能量误差 `2.10e-10 J`），新增 `unsprung_energy_ledger` 与 `src/iso_ride.py`（ISO 8608 A–D 级随机路面、独立轮心 64 位双精度解析板元空间裁剪、ISO 2631-1 $W_k$ 加权 $a_{wz}$、双峰 PSD 与车轮相对动载）。
   - **M4 2022 GR86 多源留出标定**：新增 `tools/physics/calibrate_gr86_holistic.py`，在保持 `gr86-2022-premium-6mt.json` 原参数零改动前提下生成 `assets/game/vehicle-configs/gr86-2022-kc-calibrated.json` 与盲测报告（二维 Gauss-Newton 2 步收敛，`rank=2, cond=6.69`；训练误差 `+0.06% / +0.15%`；零调参留出盲测 `100–0 mph` 误差 `-3.69%`、`1/4 mile` 尾速 `101.19 mph` vs 实测 `101.0 mph`）。
   - **M5 传感器 EKF 观测闭环与试验台接线**：新增 `src/chassis_observer.py`（带噪 IMU + 轮速滑移 NIS 门控 + GNSS 融合 $\hat{v}_x, \hat{\beta}, \hat{r}, \hat{\mu}$），支持实验台一键切换 `truth` vs `sensor_ekf` 驱动 `ABS+ESC` 与 `LAB-M3` `CoordinatedABSDYCController`，补齐 4 组工程指标面板、65 项（97 行）STIX 公式贴图、5 张离屏实图核对与官方 `T1` 全绿报告（`logs/sim-fidelity-02/t1-validation/summary.json`）。

## 持续生效的用户人工红线

- **存储边界**：所有新增工作、临时文件、日志与构建输出均留 **B 盘**；外部游戏原件、`archive/2026-10-17/legacy/` 与 `../ADAS` 只读。
- **物理与验证**：保持 120 Hz 固定步、唯一权威 Simulation 与既有认可驾驶参数；不丢弃模拟时间、不靠瞬移/放宽断言掩盖问题；外观不暗改物理性能；试验台不将装饰环境混入试验物理。
- **视觉与镜位**：保留用户认可的 **3.2 m 默认追车镜位**与山地认可天空；**建筑大致完成即可，停止立面精细化，优先房子周边景物融洽度与性能**；“自然不等于真实”，新视觉遵循研究 → 设计图 → 实现 → 实机对照。
- **性能优先级**：驾驶中卡顿与**撞击后持续卡顿（物理积压）**优先；进入游戏加载速度低优先级，但加载期间短暂“无响应”需妥善处理。
- **测试与防卡顿纪律（2026-11-23 确立）**：实行“**只测修改部分**”的按需精准测试，不再惯性全量重跑所有历史测试；21 个历史 C 内核逐位微步测试（759 项）已归档至 `tests/deep_native/`，`tests/conftest.py` 自动区分 `@pytest.mark.ui` 与纯 CPU 逻辑测试，菜单 UI 测试支持 `load_initial_scene=False` 跳过无用 3D 场景冷启。
- **实事求是**：自动测试、离屏渲染与人工驾驶/画面/声音体验分开记账；失败、超时、中断、未跑如实记录；本地提交不推远端。

## 活跃任务状态

| 任务包 | 状态 | 最新核实事实 | 当前待办 / 阻断 |
| --- | --- | --- | --- |
| [SIM-FIDELITY-02](tasks/SIM-FIDELITY-02.md) | `in_progress`（待人工桌面复核） | 2026-11-26 完成方向 4（M1–M5）全链路深化：余志生《汽车理论》解析基线与准稳态定圆扫点对账、悬架 K&C 运动学与外倾推力 + `coastal-tire-fit-v2`、34 维簧下算子 C 化提速 ~18×（`13.02 ms/step`）+ 能量账闭合 + ISO 8608/2631-1 随机路面平顺性、2022 GR86 二维满秩留出标定（`cond=6.69`，`100–0 mph` 盲测 `-3.69%`、`1/4 mile` 尾速 `101.19 mph`）、15 维传感器 EKF 观测闭环驱动 `ABS+ESC` / `ABS–DYC`；官方 `T1`（全仓 Ruff + 定向 Pytest + 0/17/23 无头）与 5 张离屏实图核对全通 | 待用户通过 `launchers/vehicle-lab.cmd` 桌面体验新工况、四组工程指标与 `sensor_ekf` 闭环对比 |
| [LAB-M3](tasks/LAB-M3.md) | `done`（人工桌面随时复核） | 2026-11-23 宿主闭环与前端精修全部通过：课程单测 12 passed、五工况闭环及 S2 A/B 读回通过（S2 停距 38.30→32.70 m、侧偏 10.53°→3.64°）、试验台 UI 43 passed、Ruff 与 0/17/23 三种子通过，已修复结果卡压字并补齐 A/B 控制策略标识（16:9/4:3 实图核对） | 无自动阻塞；可随时经 `launchers/vehicle-lab.cmd` 桌面复核 |
| [CAREER-SEASON-01](tasks/CAREER-SEASON-01.md) | `in_progress`（待人工试玩验收） | 2026-11-23–24 已完成阶段 2–3：① 修复 `test_continuous_solver.py` 并全通 T2 全部 14 项场景检查；② 修复 `game-current.cmd`/`vehicle-lab.cmd`/游戏内进试验台闪退及加载期无响应；③ 完成全游戏界面与专家试验台全面视觉/布局重做（`b13ec964`、`37d7c440`、`72b360be`），定向测试（试验台 39 passed、车库/挑战/巡回/切换 63 passed）与真窗口 `game→lab` 切换验证通过 | 待用户通过 `launchers/game-current.cmd` 与 `launchers/vehicle-lab.cmd` 实机体验给出视觉、交互、手感与流畅度验收结论（物理手柄实测待外设） |
| [PERF-SMOOTH-01](tasks/PERF-SMOOTH-01.md) | `in_progress`（待人工桌面流畅度与视觉复核） | 2026-11-26 完成四大实机顽疾综合根治（基线 `48a3f2ac`，工作区未提交）：① 全站 UI 去废料与微缩公路小车动态加载条；② 游戏/试验台求解双轨解耦与碰撞有界兜底（200 km/h 撞栏/8 车连撞 `ArithmeticError=0`）；③ 短窗细分、高速相机本地免锁与时钟超额重锚定（呈现倍速锁 `1.00×`、`backlog=0 ms`、撞后转向响应 `22.7–26.7 ms`）；④ 高速构段提速 3–4×（`161–230 ms`）、LOD 外推至 `240–290 m`、移除白噪声/Bayer `discard`、接入 `fwidth` 法线粗糙度滤波并扩展太阳阴影裁面（`NearFar 20–780`）；Ruff 0 错、后端 812 / UI 56 / 环境 119 passed、0/17/23 三种子与离屏实图全通 | 待用户通过 `launchers/game-current.cmd` 真机复测新版加载条与界面、恶意撞击响应及无限高速树木/光影稳定性 |
| [VISUAL-EXTEND-01](tasks/VISUAL-EXTEND-01.md) | `in_progress` | 试验台光照（设计 36）、滨海 8K 落日天空/动态水面/草地贴图/新版 HUD（设计 40）、流送海面时间、沿海生涯光照、城市近中景与林缘重组已落地 | 高速山体 UV 误平铺待修；城市木本阴影代理未接入；海岸近中景层次未达设计 38；全场景推广与人工画面验收开放 |
| [CHALLENGE-REBUILD-01](tasks/CHALLENGE-REBUILD-01.md) | 已并入第一季 | 统一预算报价、子步燃油计量、联合奖牌（10 固定路线 + 五公里 6 路况）、自动试车、滨海幽灵与山脊内部边修正均已合入主线并支撑第一季 | 剩余部分路况改装平衡与整包/人工验收统一随 `CAREER-SEASON-01` 收口 |

## 近期基线与验证索引

- 阶段 0 本地拆分基线：在原 `15c321f5` 上按性能核心、视觉环境、预算挑战与第一季玩法、`LAB-M3` 试验台接入及文档归档整理为清晰本地提交（详见 `git log -n 6 --oneline`）。
- 2026-11-26 工作区架构整理（基线 `b5a68cb2`）：将 12,517 份历史验收证据（`docs/evidence/`，~5.68 GB）、旧设计草图目录、~180 份已完成任务包、过时阶段评审文档、345 个零引用历史脚本、`src/phase0_app.py` 及本地旧构建/历史日志（`builds/*`、`logs/*` 非缓存项、过期 `build/` 子目录，合计 ~83 GB）统一归档至 `archive/2026-11-26/`（完整映射见本地 `moves.json`）；测试依赖的 21.8 MB 最小夹具沉淀至 `tests/data/fixtures/`，README 展示图移至 `docs/screenshots/`，本机运行缓存与活跃 SDK 原位保留。验证：`ruff check src tests tools` 0 错、0/17/23 三种子 headless 1200 步全通、夹具重定位非 UI 176 项与 UI 22 项均零路径错误通过（既有非路径失败如实留存：`test_local_kcd_drive.py` 2 项 GPU 脚本与异步加载假设、`test_virtual_driver_ui.py`/`test_workshop_journey_ui.py` 13 项历史接口差异）。
- 下一步执行：由用户运行 `launchers/game-current.cmd` 实机体验阶段 4 性能优化后的常态驾驶与撞栏流畅度；确认后按需推进最显眼视觉硬伤（山体 UV 误平铺、木本阴影代理与近景融洽度）或下一阶段收口。

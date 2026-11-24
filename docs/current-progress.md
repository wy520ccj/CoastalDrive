# 当前进度

更新：2026-11-24。历史流水账（2026-09 至 2026-11-23 原全文）完整归档于 [current-progress-2026-11-23.md](archive/current-progress-2026-11-23.md)，不再堆积在本文。

## 当前恢复路线与协作方式

项目于 2026-11-23 重启正轨，按单条施工线顺序推进（每阶段独立验收并本地提交）：
1. **阶段 0（已完成）**：拆分本地安全提交、归档瘦身进度页、修正过期 T2 状态。
2. **阶段 1（已完成）**：`LAB-M3` 试验台宿主闭环验收。
3. **阶段 2（已完成）**：定位并修复 `test_continuous_solver.py` 在 `road-edge-sdk` 下的 ULP 校验，T2 全部 14 项物理/道路/交通场景检查 `passed=True`，并完成测试体系整顿与按需分层。
4. **阶段 3（启动修复 + 全界面落日黑曜石与琥珀金重做已完成，待人工试玩收官）**：
   - 修复双击 `game-current.cmd` / `vehicle-lab.cmd` 与游戏内进入专家试验台闪退（`ScenePipeline.sync_frame()` 事件泵、`LPoint3d`→`LVecBase3f` 双精度兼容、`vehicle_menu` 11 车型动态填充）。
   - 按用户选定的参考图风格（`docs/design/workshop-garage/01-garage-concept.png`）独立补齐真实美术资源并全面重构前端空间布局与高分控件（**落日海岸工坊 Sunset Atelier**）：
     - 独立补齐美术资源并登记于 `docs/asset-register.csv`：真实黄金时段海岸汽车工坊空车库底图（`assets/game/ui/backgrounds/garage-sunset-workshop.png`）、手刷质感透明 `COASTAL DRIVE` 标识图（`assets/game/ui/atelier/wordmark-brush.png`）、与工坊实景光影方向完全一致的 360° 落日车库预过滤 HDRI（`assets/game/vehicles/garage-sunset-workshop.env`，由 `tools/vehicles/prepare_sunset_workshop_env.py` 烘焙）、4 枚暗调写实汽车摄影模式缩略图（`assets/game/ui/atelier/thumb-*.png`），以及 `tools/build_atelier_assets.py` 生成的拉丝微颗粒面板、磨砂玻璃控件与矢量图标贴图（`assets/game/ui/atelier/*.png`），由 `src/ui/atelier.py` 轻量缓存加载；
     - 统一全车型工坊材质与落日摄影光影（`src/ui/garage_vehicle_style.py`、`src/ui/workshop_vehicle.py`、`src/ui/garage_reflection.py`）：全车系工坊展示自动统一为深烟熏玻璃、炭黑内饰、缎面碳纤外饰件（消除 BRZ 等白色塑料套件与金属胎壁的“贴图/P图感”）、暗调橡胶轮胎与黄昏暖琥珀灯微光；3D 镜头校准为 34° 中焦低机位前左 3/4 视角，搭配落日工坊专属 HDRI、0.94 接触阴影与 0.34 暖色地面镜像反射，不改动任何物理参数或原模型文件；
      - 全站 6 站界面逐屏精细统一至落日工坊（Sunset Atelier）视觉语言并逐站离屏复核通过：① 首页（`main_menu.py`，`logs/season-20261124/home-photoreal-v3/`）与海岸车库（`garage_layout.py`，`garage-photoreal-v1/`）；② 生涯赛事板与赛前简报（`career_layout.py`，同步修复 `tools/career_art.py` 道路/天空同步并刷新开源资产预览，另于 `tools/environment/local_kcd_drive.py` 接入 9 张真实 `game-current.cmd` 实机预览图至忽略目录 `logs/local-kcd-drive/career-previews/`，`career-board-brief-kcd/`）；③ 预算调校/结算/暂停、参考 A/B 结算与生涯结算/暂停（`challenge_layout.py`、`career_layout.py`，新增 `panel-obsidian.png` 与 `bar-top.png`，`challenge-result-pause-v2/`）；④ 声音设置、驾驶辅助、普通驾驶暂停与结算（`menu_layout.py`、`menu_settings.py`、`driving_summary.py`，`settings-driving-v1/`）；⑤ 俱乐部赛段追时、自选车综合杯、预算巡回、无限高速卡片矩阵与道路 A/B 对照（`sector_chase.py`、`season_cup.py`、`driving_tour.py`、`driving_cards.py`、`player_road_ab.py`、`player_road_diagram.py`，彻底移除旧白纸底板，`modes-ab-v1/`）；⑥ 加载页、滨海/生涯/无限高速驾驶 HUD 与专家试验台返工重做（`workspace_loading.py` 改用通栏黑曜石顶栏 + 底部黑曜石进度坞，完整保留中部手绘海岸画卷；`coastal_hud.py`、`career_hud.py`、`hud.py` 回归设计 40 轻透与无盒悬浮数字仪表，同步修复 `application.py` 预算生涯开局右上角 `返回方案` 与 `Esc 暂停` 重叠及旧白底驾驶按钮；`lab_application.py`、`lab_workbench.py`、`lab_plot.py`、`lab_widgets.py` 及全部试验台子弹窗按用户偏好回归通体明净浅瓷工程主题，消除黑顶白身割裂、按钮黑边与低对比度，`loading-hud-lab-v2/` & `loading-hud-lab-v3/`）；
      - 验证证据（分别记账）：① 离屏渲染目检：6 站全屏实图及 16:9/4:3 布局均已核对通过（第 6 站真状态复核见 `loading-hud-lab-v2/` 加载页/滨海 HUD 与 `loading-hud-lab-v3/` 浅瓷专家试验台 16:9/4:3/弹窗 + 挂载 `local_kcd_drive.py` 实机 KCD2 植被的海岸初驶/无限高速 HUD，全部零重叠）；② 自动化测试：第 6 站全部改动文件 `ruff check` 全通；最新定向回归 `test_ui_theme` + `test_lab_ui` + `test_design_loop_ui` **52 passed**，HUD 套件 `test_coastal_medals_ui` + `test_race_feedback_ui` + `test_hill_traffic_ui` + `test_slalom_feedback_ui` + `test_career_ui -k "hud or driving"` 全通（注：`test_driving_mode_ui` 仍有 2 项旧首页按钮文案断言待与第 1 站文案对齐，非本轮第 6 站改动引入）；③ 人工桌面实机体验：待用户通过 `launchers/game-current.cmd` 与 `launchers/vehicle-lab.cmd` 试玩整套统一 UI。当前改动留于本地未提交工作区（完整保留用户原有 5 个 launcher 删除项）。
5. **阶段 4**：待用户实机试玩反馈后，定向攻克高速撞后物理积压与最显眼视觉硬伤（山体 UV 误平铺、木本阴影代理与近景融洽度）。

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
| [LAB-M3](tasks/LAB-M3.md) | `done`（人工桌面随时复核） | 2026-11-23 宿主闭环与前端精修全部通过：课程单测 12 passed、五工况闭环及 S2 A/B 读回通过（S2 停距 38.30→32.70 m、侧偏 10.53°→3.64°）、试验台 UI 43 passed、Ruff 与 0/17/23 三种子通过，已修复结果卡压字并补齐 A/B 控制策略标识（16:9/4:3 实图核对） | 无自动阻塞；可随时经 `launchers/vehicle-lab.cmd` 桌面复核 |
| [CAREER-SEASON-01](tasks/CAREER-SEASON-01.md) | `in_progress`（待人工试玩验收） | 2026-11-23–24 已完成阶段 2–3：① 修复 `test_continuous_solver.py` 并全通 T2 全部 14 项场景检查；② 修复 `game-current.cmd`/`vehicle-lab.cmd`/游戏内进试验台闪退及加载期无响应；③ 完成全游戏界面与专家试验台全面视觉/布局重做（`b13ec964`、`37d7c440`、`72b360be`），定向测试（试验台 39 passed、车库/挑战/巡回/切换 63 passed）与真窗口 `game→lab` 切换验证通过 | 待用户通过 `launchers/game-current.cmd` 与 `launchers/vehicle-lab.cmd` 实机体验给出视觉、交互、手感与流畅度验收结论（物理手柄实测待外设） |
| [PERF-SMOOTH-01](tasks/PERF-SMOOTH-01.md) | `in_progress` | 3.2 m 追车镜位已人工验收；1 m 加密路面、ShaderInput 复用、状态回收 0.5、分帧合批、护栏原生内核与 GIL 交接、结算预热（山脊结算首帧 364→91 ms）已落地；720p 滨海常态 P95 8.63 / 7.12 ms | 高速 12 车撞栏后 5 秒仍有 385 ms 峰值 / 304 ms 尾帧积压；加载短暂无响应、旧悬空制动失败与稳定 60 FPS / 人工流畅度 Gate 开放 |
| [VISUAL-EXTEND-01](tasks/VISUAL-EXTEND-01.md) | `in_progress` | 试验台光照（设计 36）、滨海 8K 落日天空/动态水面/草地贴图/新版 HUD（设计 40）、流送海面时间、沿海生涯光照、城市近中景与林缘重组已落地 | 高速山体 UV 误平铺待修；城市木本阴影代理未接入；海岸近中景层次未达设计 38；全场景推广与人工画面验收开放 |
| [CHALLENGE-REBUILD-01](tasks/CHALLENGE-REBUILD-01.md) | 已并入第一季 | 统一预算报价、子步燃油计量、联合奖牌（10 固定路线 + 五公里 6 路况）、自动试车、滨海幽灵与山脊内部边修正均已合入主线并支撑第一季 | 剩余部分路况改装平衡与整包/人工验收统一随 `CAREER-SEASON-01` 收口 |

## 近期基线与验证索引

- 阶段 0 本地拆分基线：在原 `15c321f5` 上按性能核心、视觉环境、预算挑战与第一季玩法、`LAB-M3` 试验台接入及文档归档整理为清晰本地提交（详见 `git log -n 6 --oneline`）。
- 第一季 `r3` 独立候选与真实 T2 失败日志：`builds/season-20261118-r3/build-receipt.json`、`logs/season-20261118/final-candidate-T2-r3/summary.json`、`logs/season-20261118/final-candidate-T2-r3/pytest.log`。
- 下一步执行：由用户运行 `launchers/game-current.cmd` 实机试玩第一季（含启动加载、首页/赛事板/调校界面及赛道手感），根据真实反馈决定是小修收官还是切入阶段 4（高速撞后物理积压 + 山体 UV 误平铺修复）。

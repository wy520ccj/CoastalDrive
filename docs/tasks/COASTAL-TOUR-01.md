# COASTAL-TOUR-01 三站海岸巡回

- 状态：done（本功能自动验收完成，人工趣味性待体验）；基线main/377383ef，开始前干净。持续目标active；本批仅本地，无推送/发布。
- 目标：把单项变成连续的驾驶目标，用同一套硬件跨控速、连弯和车流；失败重试当前站、暂离/重开续跑、有完整三站的综合最佳。
- 范围：现有山谷节奏→平路连弯→弯坡车流；每站至少原铜牌，铜/银/金=1/2/3分；全程3–5分铜、6–7分银、8–9分金，有效三站合计只比较同分完整轮次。独立巡回进度按现有硬件/输入variant隔离；旧单项最佳保持独立。
- 玩法：报名从第1站或当前配方断点继续；失败/未达铜不前进，过站立即存进度，下一站由玩家确认进入。重开清本轮、保留完整最佳；回菜单/去实验台暂停本轮，正常单跑不计巡回，返回巡回总览明确继续。改装/输入改变按新组报名，原配方进度保留。
- 禁止：改变原路线/目标/评分/物理/120Hz/NPC/默认硬件/SDK；不拼凑跨轮/跨配置分段，不自动应用硬件，不制造玩家成绩；无推送/发布授权。原主菜单8入口与单项入口保留。
- 验收：纯规则/持久化边界、失败/无牌/跨配置/重复结果/较慢轮次、完整最佳/原子写失败/坏文件/独立重启、菜单键盘/鼠标/每站转场/模态/实验台暂停/原单项、宽屏/4:3与两库短流程。完整旧驾驶可明确复用做规则重放；需至少一套新真实三站串联控制请求验证生命周期，实际与夹具分别记账。相关T0/T1与三种子，T2/实时/人工Gate独立开放。
- 使用直接巡回规则/存储与一个固定面板，不引入页面管理器、事件总线、第二车辆状态或通用赛事框架。

## 实现与实际证据

- `src/driving_tour.py`直接消费原单项权威结果，校验路线/站序/正有限时间/原奖牌标准，按完整硬件与输入variant保存本轮及整轮最佳；原子写失败保留磁盘旧最佳，内存允许继续并提示。坏根文件不覆盖，坏本轮与坏最佳分别隔离。
- `src/ui/driving_tour.py`固定三站总览；短途赛事新增巡回入口，赛中站数/积分，结算下一站/失败重试/总览。原主菜单8项、5项独立挑战及同窗实验台往返保持。实验台/菜单暂停巡回，单跑不计巡回，必须回总览续跑。
- 新规则与实际UI夹具共13项覆盖奖牌/整轮最佳、较慢轮次、重开/恢复、无牌/失败/重复消费、跨配方/输入、原子写/坏文件、键盘导航、实验台暂停与原单项。夹具只验证规则/界面，不冒充真实通关。

两库新真实三站串联，未拼接历史轨迹。前两站原`KeyboardController`二值请求，第三站原`HighwayDriver`试车Control，均经原120Hz Simulation，原路线/车流/硬件/辅助不改。

| SDK | 山谷节奏 | 平路连弯 | 弯坡车流 | 新实际记录拍数 | 全程 |
| --- | --- | --- | --- | --- | --- |
| Normal | 60.945058s / 7314拍 | 75.142180s / 9018拍 | 92.733333s / 11128拍 | 27460 | 9分金 / 228.820572s |
| Double | 61.140218s / 7337拍 | 75.141937s / 9018拍 | 92.733333s / 11128拍 | 27483 | 9分金 / 229.015488s |

- 合计54943新记录拍，各站原始快照/请求/结果gzip及原规则独立复核一致；每次过站重新读取磁盘验证断点，完整三站同窗/同配方、整轮最佳相等，首末源码与SDK保持。倒计时/初始化拍不计上表。
- 完整驾驶后最终只调整巡回按钮外观、避免重复文本刷新、补无铜牌提示。完整驾驶明确复用；`before-final-display`保留修前两文件、原始SHA、最终差异与比较。最终两库另起实际`SessionProcess`只读恢复3站/9分/整轮最佳，文件字节未变，首末源码/SDK一致；不是第二次完整驾驶。
- 已查看Normal 1280×720与Double 1024×768实际图：最终`restored-tour.png`为完成总览；驾驶/结算/初次总览图为最终显示微调前的完整驾驶版本。界面图是离屏渲染，非人工试玩或实时性能证据。

## 验证命令与未通过记录

- 完整驾驶：`.venv/Scripts/python.exe tools/driving_tour_check.py --output logs/validation/COASTAL-TOUR-01-normal`；Double以`tools/physics/run_sim_double.py tools/driving_tour_check.py --output logs/validation/COASTAL-TOUR-01-double --size 1024 768`执行。
- 最终独立恢复：对应命令追加`--restore`，Double保持`--size 1024 768`；均passed，新驾驶拍数0。
- T0：`tools/validate.py T0 --tests tests/test_driving_tour.py tests/test_driving_tour_ui.py --output logs/validation/COASTAL-TOUR-01-final-ui-T0`，最终Ruff/13项通过。
- T1范围：一个`--tests`依次传`tests/test_driving_tour.py tests/test_driving_tour_ui.py tests/test_sprint_ui.py tests/test_overtake_ui.py tests/test_hill_traffic_ui.py tests/test_workspace_transition.py tests/test_workshop_journey_ui.py tests/test_driving_mode_ui.py tests/test_mode_lifecycle.py tests/test_highway_run.py tests/test_sprint_run.py tests/test_overtake_run.py`；Normal输出`COASTAL-TOUR-01-T1`，Double用原启动器输出`COASTAL-TOUR-01-double-T1`。最终两库Ruff、各76项与各seed0/17/23短测全部通过；pytest分别287.78/252.02秒。
- 保留全部先前失败：`core-T0` Ruff TRY004、`ui-T0` Ruff导入顺序，均未进入pytest；`ui-fixed-T0` 11过2失败，原因是夹具未填原结果reason及测试在驾驶中调用仅允许主菜单的改装接口。已修夹具并走原合法UI路径，未放宽生产接口；`core-fixed-T0`10过、`ui-final-T0`13过及最终13过分别留档。
- 归档：`docs/evidence/COASTAL-TOUR-01`，81份原始证据共36,335,872字节，清单`archive-manifest.json`及最终10个源码LF SHA `source-manifest.json`。本批无物理/默认参数/原评分/原生模块改动；完整驾驶不证明任何改装收益。

## 后续

用户最新选择“让不同改装更影响挑战表现”。下一块先用相同课题、相同输入策略测出现有制动/轮胎配方的真实收益与代价，再决定挑战目标及反馈；不为奖牌暗改默认车或物理。原T2落地制动细化失败、实时性能与人工手感/趣味性Gate仍开放，本批未重跑T2/T3。

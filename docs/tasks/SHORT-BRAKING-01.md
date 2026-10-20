# SHORT-BRAKING-01 短距制动验车与分配方案

- 状态：done（自动部分；人工体验待确认）；基线main/9d179b4d，开始前干净。上一玩家道路A/B为progress，持续目标active，仅本地无推送。
- 目标：可选短距制动题，当前车从静止进入100m门，入门80–85km/h、过门后尽快停稳1s；以过门后最大前进距离计成绩，金≤33/银≤36/铜≤42m。直行带中心横向≤1m、车头±5°，碰撞/复位/倒车/超时30s失败。原170m定点刹停与驾驶进阶保持。
- 前测：原参考制动工坊45/60/70/80%分配，同一82.5km/h键盘目标、过100m门后制动/低速松S，分别36.906/32.621/32.436/33.579m；完整原始记录/源与SDK在BRAKE-ROAD-01-probe。此距离含实际入门约83.964km/h与反应，不冒充实验台纯80–0能力。
- 交互：原制动说明页切换新题，直接预览/确认45/60/70/80%前制动分配，结果可再次改装；共享现有完整原车副本/原子安装/恢复链，不改总制动扭矩/轮胎/路面/其他硬件。前胎界面保持，当前驾驶配置交接实验台与同题返回保持。
- 数据：新增明确GameMode与原BrakingResult的short/距离字段；独立成绩文件/规则键，完整硬件/输入隔离，旧误差成绩不混入新距离。只消费Simulation完成步，不施力、不模拟车辆；门线纯显示。新题不自动授工坊奖牌。
- 允许：直接新规则、现有制动指标持久化上限参数、Session/HighwayRun/菜单/HUD/标线/结果/实验台返回、现有驾驶配方面板两种硬件选择与小型共用存储函数；不预建改装框架。
- 禁止：物理/默认驾驶参数/原输入/旧课题阈值/SDK/原Gate，瞬移/关闭碰撞/以修改路面当升级。旧副本兼容读取，不覆盖旧方案/原车/未提交工作。
- 验证：入门边界/停稳/倒退不减距离/方向带/失败不授奖/独立保存及写失败；旧BrakingLesson前测全旧字段重放保持；前胎回归/制动配方只改分配且可恢复；Normal/Double新实际45%铜→70%银、原规则逐拍复核/原方案保持/独立进程最佳与恢复/同窗实验台回原题，宽屏4:3。相关T0/T1三种子，原T2物理失败/实时/人工Gate开放。


## 实现与测量口径

- 新增可选短距课题，入口为“高速→定点刹停→短距制动验车”；原170米定点刹停、驾驶进阶和旧成绩不变。结果可直接调整制动分配，确认保存后准备同一道题，取消保持原结果。
- 45/60/70/80%前轴份额只改`front_brake_share`，总扭矩/轮胎/路面保持；完整原车按内容SHA保留，与前胎改装共用可逐次恢复链，兼容旧`tire_tuning_previous`引用。新车解除旧工坊报告关联，原副本保留原关联。
- 新成绩使用独立`short-braking-best.json`、`short-braking-v1:`和完整硬件/输入分组。失败不授奖，写失败保留旧最佳。现有前胎道路A/B不收录制动题，不用不同指标伪造提升。
- 纠正前测解读：原旧题的36.906/32.621/32.436/33.579米是最终位置，包含低速回退；对应最大前进分别37.462/33.350/33.209/34.154米。旧题原始7273拍全部旧字段由当前原规则重放保持，无新物理复跑。本题按最大前进计分，不能靠回退变短。
- 最初两种低速脚本（0.3m/s松S、低速间歇S）均在约1386拍出现负向回弹并触发原定−0.15m/s倒车失败；Normal/Double失败原始记录保留。未修改物理、阈值或关闭碰撞。更早在1m/s松S后能稳定停住；首轮实际铜→银，但脚本错误期待金，断言失败保留在`failed-gold-expectation`。按真实银牌修正验收预期，金33米线保持。

## 新实际驾驶

同一82.5km/h目标的二值KeyboardController，从静止到100米门、过门后S制动，1m/s时松S；没有直接施力或注入车辆状态。含入门速度与驾驶反应，不是纯80–0台架指标，也不是人工驾驶。

| SDK | 45%前份额 | 70%前份额 | 新完成步记录 |
| --- | --- | --- | --- |
| Normal | 入门83.963km/h，39.515976m铜 | 入门83.964km/h，35.192795m银 | 2423+2357=4780 |
| Double | 入门83.963km/h，39.516276m铜 | 入门83.964km/h，35.192504m银 | 2423+2357=4780 |

- 正式流程共9560新拍，全部新规则字段逐拍纯规则复核（最佳/保存提示另由文件验证）。同策略最大前进减少约4.323米/10.94%；不能据此声称所有驾驶条件或更大分配均有同样收益。
- 两库在实际结算安装70%后同题重跑，再同窗进入实验台，当前70%硬件传入并返回原短距课题。未生成原170米成绩，也未冻结前胎A。
- 两库各另起真实独立`SessionProcess`恢复70%分组最佳，成绩文件字节保持，随后从备份恢复完整原车；无新完整驾驶。恢复版本已经包含仅结果面板底边修正。
- 完整驾驶时源码与SDK首末一致。最终生产变化只有结果面板底边由−.62扩至−.74，修复底排按钮出框；源文件精确旧版本/最终SHA与归档均保留。当前验证工具另修正强制刷新结果遮住配方的截图问题，只影响捕获；最终配方面板/实际银牌结算静态复载、保存失败文字UI夹具均重新渲染。未重跑完整驾驶冒充新结果。
- 已查看1280×720实际铜牌/最终银牌与1024×768规则页、最终长保存提示/制动预览，图像为离屏。人工趣味性、实际手感与实时性能仍待确认。

## 命令与验证

- T0：`tools/validate.py T0 --tests tests/test_short_braking.py tests/test_short_braking_ui.py tests/test_braking_lesson.py tests/test_tire_tuning.py --output logs/validation/SHORT-BRAKING-01-T0`，Ruff及61项通过，pytest56.91秒。
- 正式新驾驶：`tools/short_braking_check.py --output logs/validation/SHORT-BRAKING-01-normal-accepted`；Double经`tools/physics/run_sim_double.py tools/short_braking_check.py --output logs/validation/SHORT-BRAKING-01-double-accepted --size 1024 768`。独立恢复同目录追加`--restore`。
- 主批T1：`tools/validate.py T1 --tests tests/test_short_braking.py tests/test_short_braking_ui.py tests/test_braking_lesson.py tests/test_braking_lesson_ui.py tests/test_tire_tuning.py tests/test_tire_tuning_ui.py tests/test_result_tuning.py tests/test_player_road_ab_ui.py tests/test_workspace_transition.py tests/test_mode_lifecycle.py tests/test_driving_journey_ui.py`，Double相同范围经原启动器；两库各97项及seed0/17/23各1200步通过，pytest541.35/479.25秒。主批采集原3项新UI，后续显示修正与第4项长提示夹具由最终排版T1覆盖；其他模块完整复用。
- 最终排版T1：`tools/validate.py T1 --tests tests/test_short_braking_ui.py tests/test_braking_lesson_ui.py`，Double相同范围；两库各9项及seed0/17/23各1200步通过，pytest112.49/94.03秒。新增按钮完整位于面板内/长保存失败文字与按钮留距检查，未改模块复用主批。
- 旧规则复核与最终渲染脚本见证据`scripts/`。原旧前胎/道路A/B完整实际流程明确复用上一任务证据，不重复运行；本批相关旧UI/存储/返回回归在主批T1。
- 原始证据`docs/evidence/SHORT-BRAKING-01`含失败/正式驾驶、测量、规则复核、独立恢复、两分辨率图及T0/T1；清单155份原始文件、18,787,720字节及15源码LF SHA逐项保持。原生机械模块SHA仍为c84bfb06cae9d51a46f5cdff69107f96e73c6757d2853ef46673d0710010e7a2。没有物理/默认参数/原输入/原SDK/旧题标准变化，T2/T3未跑；原T2物理失败、实时与人工Gate开放，持续目标active，仅本地无推送。

- 下一步：把制动题的最近整次改装前后距离/入门速度/失败原因接入道路对照，保留原成绩与原胎A/B；不把不同反应时机归因为纯硬件收益。

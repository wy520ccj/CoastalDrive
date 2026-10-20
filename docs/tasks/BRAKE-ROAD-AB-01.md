# BRAKE-ROAD-AB-01 制动改装前后道路对照

- 状态：done（自动部分；人工体验待确认）；基线main/c6920d30，开始前工作区干净。上一轮SHORT-BRAKING-01为progress，持续目标active，仅本地无推送。
- 目标：在现有制动分配面板打开独立道路A/B；定点/短距结算安装不同硬件时固定完整A，同题目标硬件最近一次结束记录为完整B。展示入门速度、停车误差或最大前进距离、停稳和失败原因；两次有效且条件相符才显示同指标差值，同时标出入门速度差，驾驶操作可不同，不推断纯硬件因果。
- 范围：直接扩展现有player_road_ab.py存储/校验与ui/player_road_ab.py表现；application.py现有结束记录/安装/入口，ui/tire_tuning.py按钮，必要测试/验证工具/任务与证据。
- 数据：独立player-braking-ab.json/version，原前胎player-road-ab.json保持原格式与行为；相同配方/取消/车辆写失败不固定A。对照写失败保留旧对照但不回滚已保存车辆，A写失败阻止本会话错误跟进旧A。坏文件不静默覆盖，跨题/非目标车不更新B，输入/源/SDK或其他硬件不同只并列。
- 禁止：改物理/默认参数/原输入/旧规则/评分/成绩/原车与方案；不拼接最佳，不把失败已走距离当成功成绩，不新增管理框架。Simulation仍唯一120Hz权威。
- 验收：独立文件、完整最近B/失败/取消/原子错误/坏文件/异条件；原前胎回归；Normal/Double实际45%铜→结算70%银自动成对且逐拍规则复核、打开前后最佳/对照不变、另进程只读恢复/原车恢复，同窗实验台返回及宽屏4:3。原物理T2失败、实时和人工趣味性Gate开放。
- T0：新制动A/B规则/UI与原A/B相关短检查；T1：相关完整模块及三种子。现有未修改纯物理前测和工坊完整证据明确复用；不重复宽泛T2/T3。任务收尾归档原始失败/命令/源SHA，更新精简进度页与本地提交。


## 实现与边界

- 同一现有PlayerRoadAB增加直接的制动存储选项；旧`player-slalom-ab-v1`格式保持，制动独立`player-braking-ab-v1`及文件。无新存储框架/注册器。校验定点170米误差、短距最大前进、成功测速/停稳/奖牌一致性，坏值不成为可读对照。
- 结束记录生命周期由原slalom字段直接改为road字段，覆盖两类现有课题；只记录已结束Snapshot，不模拟车辆。车辆保存成功且确实变化后固定A；B要求同题、完整目标硬件，最近失败/更慢整次也替换，不动个人最佳。A写失败阻止本会话错误跟进旧A。
- 制动分配面板沿用原八个按钮，打开同一并排页；短距显示最大前进，定点显示带符号停车误差、比较绝对误差。失败显示原因/已有数值但不算有效成绩；跨源/SDK/输入设置或除制动分配外硬件不同只并列。有效差值旁同时列出入门速度B−A，驾驶操作/时机仍可不同。
- 原前胎对照入口、版本、完整A/B和指标保持。原车恢复链/车辆保存/旧方案/原规则/辅助/120Hz/物理不改。最终无生产微调复用差异，正式驾驶和独立恢复均为当前源码。

## 实际流程与验证

- Normal/Double各新实际KeyboardController跑45%铜→结算安装70%→同题银，2423+2357=4780拍/库，总9560拍；不是人工驾驶。自动固定的A/B完整结果与本次结束记录相同，逐拍原ShortBraking复算一致。
- Normal距离39.515976→35.192795m，B−A−4.323181m；Double39.516276→35.192504m，B−A−4.323772m。两次入门均约83.964km/h、差约+0.001km/h，含驾驶反应，不是纯80–0性能归因。
- 新9560拍与SHORT-BRAKING-01归档相应拍的所有已记录字段精确一致，见`old-new-records.json`；这是真正重跑后的对照，不另计复算为新物理。旧定点7273拍及更早工坊/前胎完整实际驾驶明确复用，不重复执行。
- 开始前从PLAYER-ROAD-AB-01两库归档逐字节复制原前胎对照；新流程、打开制动页及恢复后该文件SHA保持。打开前后短距最佳与制动对照也保持；同窗实验台传入70%并返回原课题。
- 两库各另起实际独立120Hz SessionProcess，恢复70%分组最佳/原A/B并只读截图，再经原面板恢复完整原车，成绩与原胎A/B保持；无新完整驾驶。恢复后当前车为原45%，保存B仍是70%的历史记录。
- 已查看Double1024×768本次A/B与Normal1280×720重开A/B，均为实际存储结果。定点对照、失败/异条件、文件错误用明确规则/UI夹具验收；不声称新实际定点完整驾驶或人工接受。
- 初次T0因新测试导入排序在Ruff失败，pytest未跑；只修导入。最终T0：`tools/validate.py T0 --tests tests/test_brake_road_ab.py tests/test_brake_road_ab_ui.py tests/test_player_road_ab.py tests/test_player_road_ab_ui.py tests/test_short_braking_ui.py --output logs/validation/BRAKE-ROAD-AB-01-T0-final`，41项通过，pytest169.37秒。原失败日志保留。
- 新实际：`tools/short_braking_check.py --output logs/validation/BRAKE-ROAD-AB-01-normal --road-ab`；Double同脚本经`tools/physics/run_sim_double.py`并加`--size 1024 768`。独立恢复同目录追加`--restore --road-ab`，两库passed，首末源/SDK一致。
- 最终T1：`tools/validate.py T1 --tests tests/test_brake_road_ab.py tests/test_brake_road_ab_ui.py tests/test_player_road_ab.py tests/test_player_road_ab_ui.py tests/test_short_braking_ui.py tests/test_tire_tuning_ui.py tests/test_result_tuning.py tests/test_workspace_transition.py`，Double同范围经原启动器；两库Ruff、各58项及seed0/17/23各1200步通过，pytest474.60/377.54秒。
- 原始证据`docs/evidence/BRAKE-ROAD-AB-01`，清单76份原始文件、9,201,425字节及9源码LF SHA逐项可核对；原生机械模块SHA仍为c84bfb06cae9d51a46f5cdff69107f96e73c6757d2853ef46673d0710010e7a2。T2/T3未跑；原T2物理失败、实时/人工趣味性Gate开放，持续目标active，仅本地无推送。
- 下一步：在当前对照中更直观地定位改装收益与失败发生位置，继续围绕驾驶中的可观察选择完善体验。

- 本地功能提交：`731cad69`（基线`c6920d30`）；76份原始文件与9最终源码的Git索引SHA逐项保持，提交后工作区干净，无推送。后续只补本条提交记录与进度，不改已验源码。

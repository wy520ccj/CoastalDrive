# OVERTAKE-FEEDBACK-01 留距提示与失败解读

- 状态：done（自动功能与渲染，人工体验待确认）；基线main/83fb54b5，开始前干净。上一轮工坊解读完成实现/真实短测/渲染/本地提交，为progress；持续目标active。
- 目标：驾驶中看到当前近车净距/并行侧距/整车领先量，提前决定节奏；失败可区分跟车、并行或尚未拉开，解释实际触发余量而非只展示最后一拍。
- 范围：只读权威道路局部车身包络的观测；直线与弯坡、身份/回收/重定位、拍间触发点；HUD/结算文字，独立进程传输；原始历史拍新旧规则逐字段比较、两库短违规实际运行、宽屏/4:3图与相关T0/T1三种子。
- 禁止：改变原阈值/成绩/奖牌/候选逻辑/规则字段含义、物理/SDK/车辆/NPC/道路算法；不承诺相邻车道安全，不自动驾驶或应用控制。没有推送授权。
- 设计：新增观察字段，原字段精确保持。赛中仅显示当前近车，与原成功超车消息分行；跟车阈值10m/并行1m保持，接近趋势只按当前相对速度计算到10m边界的匀速余时。失败取原扫掠禁区开区间内部点，明确是原保守包络的拍间触发点，不能伪称新物理状态。
- 验收：同道追近、并行/后方拉开、远车/相邻车道、反向/非active/代次切换、恰好边界/跨拍穿越/尺寸变化；事件冻结/重试清空、最佳字节保持；原直线22169与弯坡39528历史拍全部旧字段不变；正常独立SessionProcess能传递观察。完整驾驶明确复用，不为表现重跑长途。
- 人工体验、原T2物理失败和实时Gate开放；收尾记录失败/复用/未跑及证据和本地提交。

## 已执行

- 新增只读近车/触发点记录，直线/弯坡均用原完整俯视车身包络。前方同路带120m、附近并行/后方；到10m线的匀速余时≤2s或并行侧距<1.5m仅转橙色，不改原1m/10m标准或任何控制。后方只报整车领先量，不把起步已在身后的车辆冒充完成超车。
- 保留所有旧字段含义与原原因字符串；拍间事件另取原扫掠开区间内部点，使用原保守宽/长包络并注明插值来源。结算按跟车/并行/尚未拉开给建议，事件在结束后冻结，重试清空。独立进程随原比赛结果传输，无新物理世界。
- 原直线22169拍、弯坡39528拍，共61697拍的全部旧字段精确保持；9份原始记录SHA核对，新的前方/接近并行/并行/后方读数均出现，原违规均有两项不足的触发点。这是历史重算，不算新物理。
- Normal/Double各新执行弯坡追近1036拍（共2072），均8.633333s/~120m、无碰撞时按原间距失败，无新最佳；约6.75s前方净距32m时显示匀速约2s到10m线。原始请求/道路姿态/代次/每拍新旧结果完整记录。两库宽屏/4:3实际警示与结算图已查看；3次超车+事件+存储提示的长结算用明示呈现夹具检查边界，不伪称实际完成。
- 首T0 36项通过；集成T0 39过/2失败，新增进程等待被误放本地会话；修正后4项补测2过/2失败，发现直线起点本就没有120m内同路带近车。改为验证真实空读数/实际弯坡读数、12拍进程推进及非空事件传输夹具；一次补测被Ruff导入顺序阻断，修正后完整进程模块4项通过。原失败日志全部保留，生产探测范围未放宽。
- 最终Normal/Double相关完整T1各66项及0/17/23三种子各1200步通过；原计时目标/HUD、短途菜单、场景和模式生命周期一起覆盖。没有重跑T2/T3，原Gate开放。
- [证据包](../evidence/OVERTAKE-FEEDBACK-01/README.md)：49份原始文件/9170020字节、13份源码LF SHA；所有历史原始输入的路径/SHA保留在legacy/summary.json，新试验首末源码/SDK一致。49份暂存区原始字节、13源码LF SHA及机械模块SHA核对通过；功能提交04b60ff6，随后只补录文档。物理/参数/NPC/道路与原评分保持；仅本地，无推送。

主要命令（目录须不存在）：

```powershell
.venv/Scripts/python.exe tools/validate.py T0 --tests tests/test_overtake_observations.py tests/test_overtake_run.py tests/test_hill_traffic.py --output logs/validation/OVERTAKE-FEEDBACK-01-T0
.venv/Scripts/python.exe tools/overtake_feedback_check.py --output logs/validation/OVERTAKE-FEEDBACK-01-legacy
.venv/Scripts/python.exe tools/overtake_check.py --output logs/validation/OVERTAKE-FEEDBACK-01-normal-unsafe --mode hill_traffic --unsafe
.venv/Scripts/python.exe tools/physics/run_sim_double.py tools/overtake_check.py --output logs/validation/OVERTAKE-FEEDBACK-01-double-unsafe --mode hill_traffic --unsafe --size 1024 768
.venv/Scripts/python.exe tools/validate.py T1 --tests tests/test_overtake_observations.py tests/test_overtake_run.py tests/test_hill_traffic.py tests/test_overtake_session.py tests/test_overtake_ui.py tests/test_hill_traffic_ui.py tests/test_highway_run.py tests/test_coastal_medals_ui.py tests/test_sprint_ui.py tests/test_mode_lifecycle.py tests/test_scene_lifecycle.py --output logs/validation/OVERTAKE-FEEDBACK-01-T1
.venv/Scripts/python.exe tools/physics/run_sim_double.py tools/validate.py T1 --tests tests/test_overtake_observations.py tests/test_overtake_run.py tests/test_hill_traffic.py tests/test_overtake_session.py tests/test_overtake_ui.py tests/test_hill_traffic_ui.py tests/test_highway_run.py tests/test_coastal_medals_ui.py tests/test_sprint_ui.py tests/test_mode_lifecycle.py tests/test_scene_lifecycle.py --output logs/validation/OVERTAKE-FEEDBACK-01-double-T1
```

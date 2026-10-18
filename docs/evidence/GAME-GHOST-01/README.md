# 个人最佳幽灵

基线main/634ffcd；任务功能范围为权威记录/持久化/元数据、只读显示与开关。物理方程、参数、输入调校、120Hz、碰撞和原生扩展均未改。没有第二个物理车。

## 真实数据与图像

- `normal-scores.json`和`double-scores.json`关联`ghosts/`中的原始内容文件：普通/Double各6074帧完整真实完成步，终线时间50.6059580613/50.6059567615秒。原始4轮姿态保留；末次固定步按真实终线插值时间显示，终点后不外推。
- 输入由现有RouteDriver测试驾驶员产生，全部位姿来自实际Simulation；独立进程专项故意以0.25秒间隔领取窗口帧，仍保存完整逐拍记录。它证明记录不依赖绘制历史，不能代替人工驾驶结论。
- 图像为真实记录静态预览：主车显示较参考早0.6秒的另一真实时刻，用于观察透明度/遮挡/轮姿与开关。世界保持初态，物理快照及124刚体不变。截图文字明确说明预览，不把图中的HUD用时/速度当新的驾驶结果。
- `normal-replay.json`、`double-replay.json`含完整SDK内容摘要、物理依赖清单和投影范围。普通/Double开关变化4052/2601像素，车身投影框外均0；同状态框外背景控制为0。Double重复透明绘制中车身内部2–3像素的变化原值保留，不用它宣称整帧逐字节稳定。
- 主相机位29专供幽灵，阴影相机排除该位；无影子由真实遮罩及开关框外0像素联合检查。3米内隐藏，3–8米渐显；关闭/重叠、无效圈及参考结束隐藏，不裁掉真实车辆碰撞。

## 自动证据

所有命令使用本项目`.venv/Scripts/python.exe`，不安装依赖；Double使用现有`tools/physics/run_sim_double.py`。

| 范围 | 命令/目录 | 结论 |
|---|---|---|
| 首次T0 | `tools/validate.py T0 --tests tests/test_lap_ghost.py tests/test_ghost_visual.py tests/test_ghost_session.py tests/test_h3_review.py::test_actual_physics_lap_records_and_reloads --output logs/validation/GAME-GHOST-01-T0 --timeout 300` | 13通过/1遮罩断言失败，真实本地/独立进程圈通过；原failed保留 |
| 第二T0 | `logs/validation/GAME-GHOST-01-T0-r2`：8记录/版本边界、2显示、1真实圈 | 11项/Ruff通过 |
| 完整T1 | `tools/validate.py T1 --area gameplay --tests tests/test_ui.py tests/test_driving_mode_ui.py --output logs/validation/GAME-GHOST-01-T1 --timeout 600` | 133项/Ruff/0、17、23各1200步通过，含独立进程完整实际圈与元数据回传 |
| Double专项 | `logs/validation/GAME-GHOST-01-double` 11项；最终`...-double-final`8记录/版本+1真实圈 | 11项及最终9项/Ruff通过；上下文收窄后重新保存当前依赖的原始记录 |
| 资源补验 | `tools/validate.py T0 --tests tests/test_ghost_visual.py::test_missing_or_invalid_ghost_asset_keeps_main_scene_and_world --output logs/validation/GAME-GHOST-01-assets --timeout 300` | T1后增加的缺文件/无效资产/运行库加载错误3项通过，主车/世界不变 |
| 图像 | `tools/ghost_replay_check.py`，普通`logs/GAME-GHOST-01/normal-final-replay`；Double最终`.../double-delivery --size 1024 768` | 真实记录读入、G/按钮/贴近渐隐、阴影与物理不变；实际图像已查看 |

为节省重复验证，T1其他133项明确复用；最后资产边界仅补验3项，静态工具暖帧/HUD.resize调整只影响采集工具，不改变生产物理或输入。源码依赖校验覆盖108个源码/原生文件，实际SDK摘要普通39文件；纯Scene/Application改动不使记录失效。

## 失败记录与边界

- 初版遮罩测试把Panda全局可见位31当作相机位；修正为实际主相机掩码交集，阴影位29仍要求完全排除。
- 初次对照采集只有3帧，路缘尚未稳定；同状态重复图证实变化在开关前已发生。暖帧后保留严格框外0，未改阴影阈值；原图/诊断在`normal-replay`、`pixel-diagnostic`、`double-final-replay`。
- 初版上下文把全部顶层源码纳入，后按Session/Simulation/控制/判圈的实际import依赖及原生源码/扩展计算；测试证明单独Scene修改不失效而模型依赖修改会失效。SDK内容另外校验，不把数字版本相同视作二进制相同。
- T2已在250be45/干净工作区启动，`logs/validation/GAME-GHOST-01-T2/summary.json`目前running；`T2-start.json`仅保存启动范围，不是通过证据。后续按活进程和最终汇总接续，不重复启动。T3、长期性能与用户主观趣味性未验收，持续目标active。

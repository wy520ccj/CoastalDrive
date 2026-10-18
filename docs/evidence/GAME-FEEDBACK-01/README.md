# 滨海分段反馈证据

基线main/9c21f2f；仅计时/成绩持久化、HUD/结算和必要的旧测试修正。物理、输入调校、道路/判圈门槛、原生物理快照与扩展未改。RaceSnapshot新增字段通过既有pickle会话状态传输，不写入原生物理快照布局。

## 已验证

- 固定步实际穿门线的插值时刻，4检查点+终点共5段；允许倒车调姿，重过门线不重复记录。复位/越界/未完成不更新最佳。
- 开始时冻结整圈最佳及其分段，新个人最佳也对照旧参考；较慢圈即使某一段更快也不能把该段拼入参考。
- 原数字成绩键不变，可选`_splits_v1`与数字同时原子保存。损坏分段保留有效总成绩并提示，坏文件/保存失败不妨碍驾驶。完整配置SHA256和显式规则版本隔离成绩组；旧组仍留在文件中，不迁移混比。
- HUD区分本段差与累计差，结算5段表/新纪录/无效圈不比较；宽屏720p和Double 4:3实际渲染及控件边界已查看。截图明确标注规则夹具，100/97秒仅是夹具示例，不是实车或人工圈速。
- `test_h3_review.py::test_actual_physics_lap_records_and_reloads`独立跑了真实物理圈，要求有效完成、45–65秒原范围、5段严格递增/终点等于总时长/保存重读一致。它在首轮T0及完整T1中均通过；没有用渲染夹具替代该证据。

## 验证账本

所有Python使用`.venv/Scripts/python.exe`；Double经现有`tools/physics/run_sim_double.py`隔离SDK，不安装依赖。

| 检查 | 命令入口/日志 | 结论 |
|---|---|---|
| 首轮T0 | `tools/validate.py T0 --tests tests/test_race.py tests/test_race_splits.py tests/test_race_feedback_ui.py tests/test_h3_review.py::test_actual_physics_lap_records_and_reloads --output logs/validation/GAME-FEEDBACK-01-T0 --timeout 300` | 21通过/2布局失败，保留failed |
| 布局修正 | `logs/validation/GAME-FEEDBACK-01-layout-final`，T0完整`test_race_feedback_ui.py` | Ruff/5项通过 |
| 完整T1 | `tools/validate.py T1 --area gameplay --tests tests/test_ui.py tests/test_driving_mode_ui.py --output logs/validation/GAME-FEEDBACK-01-T1 --timeout 300` | 117通过/2历史失败；三种子not_run，原汇总仍failed |
| 首次补验 | `logs/validation/GAME-FEEDBACK-01-T1-supplement`，v32标签与键盘设置节点 | 标签1项通过；设置节点继续发现旧选中项偏移，仍failed |
| 最终补验 | `tools/validate.py T1 --tests tests/test_ui.py::test_keyboard_navigation_for_secondary_menus --output logs/validation/GAME-FEEDBACK-01-T1-supplement-r2 --timeout 300` | Ruff/1项及0/17/23各1200步通过 |
| Double最终T0 | `tools/physics/run_sim_double.py tools/validate.py T0 --tests tests/test_race.py tests/test_race_splits.py tests/test_race_feedback_ui.py --output logs/validation/GAME-FEEDBACK-01-double-final --timeout 300` | Ruff/22项通过 |
| 实际UI | `tools/race_feedback_check.py --output logs/GAME-FEEDBACK-01/wide-delivery`；Double同工具`--output logs/GAME-FEEDBACK-01/double-4x3-delivery --size 1024 768` | 两库各6图通过，最终代码图像已查看 |

原T1的119个节点由117项明确复用+2项修正后的补验覆盖，不伪称重新完整运行通过。T1后只调整分段表字体/新纪录与警告排版，以及暂停声音设置返回后的选中项；前者由最终普通/Double UI专项和实际渲染覆盖，后者由最终键盘补验覆盖。

## 历史失败与修正

- 旧牵引力测试仍要求game-native-traffic-v26，但基线生产早已为game-keyboard-v32；改为匹配实际版本，保留模式/ABS/TCS全部8组互异检查。
- 旧键盘测试把暂停第2项当作“设置”，而基线第2项已有“返回实验台”。更新为实际键盘两次下移；继续执行后发现`back_from_audio_settings`也仍返回旧索引1，修为2，并继续验证重启/倒计时和回菜单。
- `baseline-failures.txt`记录基线重现；`baseline_check.py`冻结9c21f2f四个相关源码及两份原测试，命令`--output <新目录>`预期以两项失败退出。实际再验证在`logs/GAME-FEEDBACK-01/frozen-baseline.log`，不是当前实现回归通过。
- 首次表格行距导致警告页重叠；一次误用TextNode行距接口报错，改为独立字体副本设置实际字体行距，未改变全局UI字体。最早渲染工具冻结更新前没有应用驾驶相机，产生车内视角；最终工具调用生产apply_scene后重拍。失败和早期图像保留。

T2安排在分段/幽灵这批完成后；T3、长期性能、用户人工驾驶/趣味性与原物理Gate未执行，持续目标仍active。

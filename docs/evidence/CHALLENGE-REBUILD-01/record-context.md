# 玩法规则更新后的成绩兼容

2026-11-06，基线 HEAD 15c321f5。五公里更新车道判罚后，原先共享整个源码指纹的滨海个人最佳、幽灵、自动试车对照及巡回分组也变化。现区分逐拍原始记录的运行指纹与玩家成绩的兼容分组。

- 原始记录的首末指纹继续按实际代码、SDK 和物理模块核验。评分、试车对照、滨海幽灵及巡回只在兼容表命中完整源码指纹时替换分组中的源码值。输入、车辆、规则、种子、报价、油耗及 SDK 匹配要求仍按各原有存档检查。
- 按原始实跑指纹逆向复算，车道更新与前一工作版本只差 `challenge_catalog.py`、`highway_run.py`、`session.py` 的该次规则及接线。无关赛事继续使用已核对的车道更新前分组。五公里沿用车道规则已生效时的分组，旧越界规则的记录保留在原处。中间开发版的其他分组也保留原文件。兼容表对未来未核对版本不匹配。
- 兼容条目位于 `assets/game/rules/record-context-aliases.json`。若真实源码或 SDK 改变，继续按实际条件判断。新记录原始指纹与任何旧分组值保持各自口径。无需重写旧存档文件。

T1 共 19 项，Ruff 与种子 0/17/23 离屏启动通过。覆盖幽灵损坏和版本边界、源码依赖变更、分组命中及不匹配、原始逐拍记录、五公里路况隔离。命令为：

```powershell
$sdk=(Resolve-Path 'build/road-edge-sdk/panda/built-road-edge').Path
$env:PYTHONPATH="$sdk;$env:PYTHONPATH"
.venv/Scripts/python.exe tools/validate.py T1 --tests tests/test_lap_ghost.py tests/test_challenge_trace.py tests/test_ghost_session.py::test_authority_records_without_window_and_pause_focus_reset_restart_are_consistent tests/test_highway_run.py::test_budget_distance_keeps_best_separate_for_selected_shape_and_traffic --output logs/challenge-context-compat-20261106/T1 --timeout 165
.venv/Scripts/python.exe logs/challenge-context-compat-20261106/reopen.py
```

独立离屏游戏经正常菜单重开隔离存档，读回 **55.290 秒**的滨海最快幽灵和 **55.174 秒**的自动试车对照。确认巡回分组键一致。五公里用已实跑成绩作存档夹具，当前规则读到 **176.028 秒**的同规则记录，未采用旧规则的较快夹具。读档过程保持成绩文件逐字节一致，另起的短试跑写出当前首末原始指纹。本轮未重跑整圈或五公里，未做整包 T2。

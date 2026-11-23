# 赛事流程合包

2026-11-07，基线 `15c321f5`。本次合包包含[山谷制动与对照](valley-trial-comparison.md)、[预算超车冲线裁定](overtake-finish-order.md)和[巡回重开及单站练习隔离](tour-recovery.md)。继续以实际开发改动推进，已有自动试车数据用于有针对性的核对。

本次新增巡回待保存状态恢复。保存失败后切换驾驶模式，各组仍独立；切回原模式可以继续查看已过站状态和重试保存。待保存状态在同一次游戏运行中保留，磁盘仍按正常保存流程写入。

冻结包诊断按上一版实际使用的成绩分组构造兼容夹具，并分别核验两版程序的原始指纹。这样从已经使用独立成绩分组的试玩版升级，也能核对个人最佳和试车对照是否延续。预算超车因裁判变更按新版规则另开成绩分组。

新版独立程序位于 `builds/challenge-preview-20261107-events/app/win_amd64/coastaldrive.exe`。复用本地道路运行库，清除 `PYTHONPATH` 后程序离屏启动通过，退出码 0、物理步 290。以紧邻的 `challenge-preview-20261107-records` 为基准，冻结程序从正常山谷入口读回旧组的个人最佳和试车对照夹具。包指纹改变，成绩分组相同。结果在构建目录的 `verification/smoke/h0-render-smoke.json` 和 `verification/record-upgrade.json`。

T1 的 12 项、Ruff 与三种子短启动通过。巡回用故障注入验证切换模式往返和重试保存，本轮没有重跑关卡标定。源码和构建保留本地，整包 T2 及实际性能开放。

```powershell
$sdk=(Resolve-Path 'build/road-edge-sdk/panda/built-road-edge').Path
$env:PYTHONPATH="$sdk;$env:PYTHONPATH"
.venv/Scripts/python.exe tools/validate.py T1 --tests tests/test_driving_tour_ui.py::test_switching_driving_mode_keeps_unsaved_round_in_its_own_group tests/test_lap_ghost.py --output logs/challenge-event-preview-20261107/T1 --timeout 130
```

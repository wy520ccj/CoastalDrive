# 巡回重开与单站练习草稿

2026-11-07，基线 `15c321f5`。巡回重开先保存空的新轮次，成功后才切到第一站。写入失败时留在巡回总览，当前站序、已保存历史和待保存完赛都能保留。玩家可以继续原来的下一站，也可以再次重开。原有过站保存失败的重试入口仍能提交本轮进度。

历史或本轮的单站练习使用临时草稿。练习发车、重试及退出均不自动覆盖正式挑战草稿。玩家明确点击「保存方案」且保存成功后，才把该版本带回正式挑战。正式续跑仍从原巡回站序出发。

隔离存档从正常巡回和历史练习控件核对。写入故障夹具验证旧文件字节一致、原站序可继续，场次夹具只用于验证保存和界面流程。T1 通过 14 项、Ruff 和种子 0/17/23 短启动。改动位于源码，现有独立试玩包尚未更新，整包 T2 开放。

```powershell
$sdk=(Resolve-Path 'build/road-edge-sdk/panda/built-road-edge').Path
$env:PYTHONPATH="$sdk;$env:PYTHONPATH"
.venv/Scripts/python.exe tools/validate.py T1 --tests tests/test_tour_budget.py tests/test_driving_tour_ui.py --output logs/challenge-tour-recovery-20261107/T1 --timeout 140
```

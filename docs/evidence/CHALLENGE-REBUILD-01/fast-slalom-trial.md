# 高速验车的逐门自动试车

2026-11-06，基线 HEAD 15c321f5。高速验车加入可套用的原车与前轮响应方案。后者费用 2000，前轴侧偏刚度从 50 提至 65 kN/rad。两套都可继续编辑，并用同一套试车策略跑现有六门。驾驶中显示自动试车状态。结算沿用[预算三列母版](../../design/challenge-controls-v2/design.md)和高速验车已有逐门数据，显示各门累计用时、车身余量和相对上次有效试车的余量差。

首组按门中心预瞄的自动策略在第三门漏门，原车越线 2.726 米、前轮升级越线 0.095 米。原失败逐拍数据保留。最终策略利用门内侧空间，提前按曲率给转向请求，再依据实际横向位置和速度修正。车道几何、70–80 km/h 带、门宽、玩家输入及奖牌门槛保持。

| 方案 | 费用 | 入门车速 | 实际过门 |
| --- | ---: | ---: | --- |
| 原车 | 0 | 73.979 km/h | 通过 3/6，第四门越线 1.818 米 |
| 前轮响应 | 2000 | 73.978 km/h | 通过 6/6，计时段 11.515 秒，最窄余量 0.522 米 |

前轮升级在同一驾驶策略下达到现行银牌时间，距金牌时间约 0.015 秒。原车的失败描述仅针对该策略。两趟均用原始 120 Hz 位置、朝向和车速重跑原裁判，逐拍结果一致。只有有效的六门完赛能覆盖试车对照。正式成绩、玩家道路 A/B 和已存草稿分别隔离。

相关 T1 20 项、全仓 Ruff 与种子 0/17/23 离屏启动通过。正常菜单两次实跑证据、首组失败和方案/成功结算截图位于 `logs/challenge-fast-slalom-trial-20261106/`。独立进程从磁盘恢复六门余量，再用同一次真实完赛数值核对 960×720 的上次试车对照。该次读档未再次驾驶，存档字节保持。

```powershell
$sdk=(Resolve-Path 'build/road-edge-sdk/panda/built-road-edge').Path
$env:PYTHONPATH="$sdk;$env:PYTHONPATH"
.venv/Scripts/python.exe tools/validate.py T1 --tests tests/test_trial_references.py tests/test_fast_slalom.py tests/test_fast_slalom_ui.py tests/test_slalom_practice.py --output logs/challenge-fast-slalom-trial-20261106/T1 --timeout 165
.venv/Scripts/python.exe logs/challenge-fast-slalom-trial-20261106/run.py
.venv/Scripts/python.exe logs/challenge-fast-slalom-trial-20261106/reopen.py
```

旧整包 T2 仍停在此前主动中止的状态，本轮未重启。其它路线的改装平衡与实际体验仍开放。改动保留在本地。

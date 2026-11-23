# 奖牌升级后的方案恢复与平路重复达标

2026-11-06，基线 `15c321f5`。方案键此前直接使用评价版本。启用正式奖牌后，实际试玩档中海岸初驶已保存的动力、前胎和制动调校仍在旧键下，当前入口会退回原车。现优先读取当前版本草稿，找不到时读取已确认兼容的前一评价版本。识别仍包含关卡、原车、允许改装和报价版本，山脊v4与v5分别读取。读取实际试玩档核对恢复结果，文件字节未变。新保存写入当前版本，旧档保留。

复用[原车与两个付费方案的平路实跑](bend-trial-comparison.md)。在当前接缝修正SDK及轮胎接触修正下，只补两套已确认有明确取舍的方案各一次。种子17，目标105 km/h、曲率预瞄4.4 m/s²、90%转向余量。新记录均无碰撞、四门完成，原始燃油和终点时间复算。两方案的新旧赛段用时与油耗在当前显示精度一致，均两次满足现正式金牌线95.6秒及20.1 L/100km。

| 方案 | 费用 | 用时 / s | L/100km |
| --- | ---: | ---: | ---: |
| 原车，复用已验结果 | 0 | 93.922 | 19.288 |
| 前胎130%，本次 | 2000 | 92.150 | 19.436 |
| 减重4%与风阻面积95%，本次 | 4780 | 93.770 | 18.946 |

前胎方案在该策略下最短，轻量低阻耗油最少，原车零费用。试玩说明已把轻量低阻的可输入值对齐同档报价，0.6514 m²与实跑使用的精确95%略有舍入差。自动试跑没有写玩家奖牌。其余主要路线的可重复改装收益、报价及整包验收仍开放。

最终T0 6项及全仓Ruff通过，覆盖旧草稿读取、新草稿优先、不同山脊路线隔离、写入失败保持以及正常发车。复算结果和原始数据在 `logs/challenge-build-continuity-20261106/`。本轮无视觉布局调整，未提交推送。

```powershell
$sdk=(Resolve-Path 'build/road-edge-sdk/panda/built-road-edge').Path
$env:PYTHONPATH="$sdk;$env:PYTHONPATH"
.venv/Scripts/python.exe tools/challenge_balance_check.py --output logs/challenge-build-continuity-20261106/bend-current --routes bend_sprint --builds front-tire130 efficiency --seconds 125 --target-kph 105 --curve-acceleration 4.4 --steering-reserve .9
.venv/Scripts/python.exe tools/validate.py T0 --tests tests/test_challenge_plans.py tests/test_challenge_ui.py::test_save_load_start_authoritative_hardware_then_adjust_restores_original --output logs/challenge-build-continuity-20261106/T0 --timeout 120
```

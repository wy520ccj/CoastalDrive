# 滨海计时与弯坡车流的参考方案

2026-11-06，基线 `15c321f5`。沿用[图03的参考方案栏](../../design/challenge-controls-v2/design.md)，正常菜单打开滨海计时或弯坡车流即可套用两套实跑方案。滨海前轮响应与轻量低阻均含前制动份额65%、前防倾份额40%。弯坡车流分别采用动力115%和轻量低阻。两个轻量低阻方案均为减重4%和风阻面积95%，弯坡的免费调校保持原车。四套方案均可继续编辑，费用取实时报价。路线按关卡标识与几何区分，直道车流不套用弯坡方案。

| 路线 | 方案 | 费用 | 原实跑 用时 / 油耗 | 本轮 用时 / 油耗 |
| --- | --- | ---: | ---: | ---: |
| 滨海计时 | 前轮响应 | 2000 | 54.324 / 21.142 | 54.324 / 21.142 |
| 滨海计时 | 轻量低阻 | 4780 | 55.174 / 20.996 | 55.174 / 20.996 |
| 弯坡车流 | 动力升级 | 3940 | 88.778 / 11.324 | 88.972 / 11.236 |
| 弯坡车流 | 轻量低阻 | 4780 | 92.700 / 10.239 | 92.756 / 10.125 |

用时为秒，油耗为 L/100km。逐一复算八次原始完赛的终点和油耗，滨海复算几何门线，弯坡均核对安全超越三辆及抵达固定终点。四套方案的两次完赛均达到现行金牌线，历史样本按原赛制复算后再与现行门槛比较。本轮滨海目标车速105→103 km/h，结果相同，支持该策略下复现。弯坡144→140 km/h，结果有差异且速度和油耗的取舍保持。自动试车无玩家奖牌或最佳写入。原六份玩家记录哈希保持。

原始样本来源见[滨海计时](coastal-circuit-choices.md)及[弯坡车流](hill-traffic-driving-cues.md)。四次补跑、复算脚本、`verified.json` 和两张已核对的960×720正常入口实图在 `logs/challenge-coastal-traffic-setups-20261106/`。T1 相关3项、全仓 Ruff、种子0/17/23启动通过，覆盖实际菜单选方案和发车、滨海重试、弯坡安全反馈及关卡范围。改动在本地未提交工作区。山谷与山脊改装平衡及整包验收仍开放。

```powershell
$sdk=(Resolve-Path 'build/road-edge-sdk/panda/built-road-edge').Path
$env:PYTHONPATH="$sdk;$env:PYTHONPATH"
.venv/Scripts/python.exe tools/challenge_balance_check.py --output logs/challenge-coastal-traffic-setups-20261106/coastal-103 --routes time_trial --builds tuned-front-tire130 tuned-efficiency --seconds 80 --target-kph 103 --curve-acceleration 3.3 --steering-reserve 0.9
.venv/Scripts/python.exe tools/challenge_balance_check.py --output logs/challenge-coastal-traffic-setups-20261106/hill-140 --routes hill_traffic --builds power-only efficiency --seconds 130 --target-kph 140
.venv/Scripts/python.exe logs/challenge-coastal-traffic-setups-20261106/review.py
```

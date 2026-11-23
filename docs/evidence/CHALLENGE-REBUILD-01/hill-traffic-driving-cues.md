# 车流挑战的安全提示与改装取舍

2026-11-06，基线 `15c321f5`。预算车流赛的说明与实际固定终点对齐。直道须150秒内跑完2公里并安全超越2辆，弯坡须180秒内跑完2.4公里并安全超越3辆。达标后的 HUD 提示继续驶至终点，并保留更紧急的近车读数。切回前显示还差多少净距，差值小于0.1米时明确提示。驾驶和结算将自动计量点标成分段或具体里程。

间距失败沿用原裁判和扫掠包络。结算使用已保存的触发点间距，显示车号、未达标的间距类型、触发净距和最低要求。跨拍复现中，下一帧侧距已超过1米，裁判采样到的侧距仍低于门槛。界面使用后者解释失败。旧专家赛事继续显示完整事件明细。

使用本机修正 SDK、固定弯坡种子23、12辆原生车流及同一自动驾驶策略实跑。四套均安全超越3辆并抵达2.4公里终点，无碰撞、间距事故或计分写入。原始燃油子步与终点时刻复算通过。并排侧距列取本次三次有效超越中的最小值。

| 方案 | 费用 | 用时 / s | 油耗 / L/100km | 并排最小侧距 / m |
| --- | ---: | ---: | ---: | ---: |
| 原车 | 0 | 92.925 | 12.804 | 2.217 |
| 动力115% | 3940 | 88.778 | 11.324 | 2.217 |
| 轻量低阻 | 4780 | 92.700 | 10.239 | 2.216 |
| 均衡 | 5000 | 86.383 | 11.777 | 2.371 |

同策略下，三套付费方案在用时与油耗间形成取舍，原车提供零成本完成路径。不同配置遇到的实际车辆及通过时机有差异，油耗只代表各自完整试跑。原六份真人记录按原 SHA256 校验一致。

相关38项 T0 和全仓 Ruff 通过。后续边界文案补验12项观察测试，最终赛事入口另验直道和弯坡两项 UI 用例。三种驾驶提示及失败结算的实际控件图已查看，均用状态夹具显示，原始驾驶记录另存。正式报价、奖牌线及真人体验仍开放。完整数据和截图在 `logs/challenge-takeover-20261106/hill-traffic-main-choices`、`hill-traffic-balanced`、`hill-traffic-cues-scene`、`hill-traffic-returning-final` 及 `hill-traffic-result-fixture`。

```powershell
$sdk=(Resolve-Path 'build/road-edge-sdk/panda/built-road-edge').Path
$env:PYTHONPATH="$sdk;$env:PYTHONPATH"
.venv/Scripts/python.exe tools/challenge_balance_check.py --output logs/challenge-takeover-20261106/hill-traffic-main-choices --routes hill_traffic --builds stock power-only efficiency --seconds 150 --target-kph 144
.venv/Scripts/python.exe tools/challenge_balance_check.py --output logs/challenge-takeover-20261106/hill-traffic-balanced --routes hill_traffic --builds balanced --seconds 150 --target-kph 144
.venv/Scripts/python.exe logs/challenge-takeover-20261106/verify_hill_traffic.py hill-traffic-main-choices
.venv/Scripts/python.exe logs/challenge-takeover-20261106/verify_hill_traffic.py hill-traffic-balanced
```

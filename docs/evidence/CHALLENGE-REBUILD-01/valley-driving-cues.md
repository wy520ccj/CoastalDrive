# 山谷控速提示与改装取舍

2026-11-06，基线 `15c321f5`。沿用山谷 v2 的路线、门位、牌面和 HUD 布局。驾驶时现有提示行显示距250米测速门的剩余距离及至少60 km/h的要求。过门后显示距400米入口的距离及35—50 km/h要求。带内同时显示裁判使用的沿道路车速和到650米出口的剩余距离，出带后提示重新加速。门位、限速和裁判逻辑保持原规则。

初版在1280×720时将两处提示拆行，最终精简文字后各自单行显示。已查看四阶段的实际控件截图。截图是用真实 HUD 渲染的状态夹具，背景保持起点，驾驶数据另从正式路线实跑取得。最终相关13项和全仓 Ruff 通过。日志为 `logs/challenge-takeover-20261106/valley-cues-final-T0` 与 `valley-cues-final-scene`。

具备接缝修正的本机 SDK 下，按同一策略重验三套预算内方案。均无碰撞、四门有效，燃油子步和终点时刻由原始记录复算通过。

| 方案 | 费用 | 用时 / s | 油耗 / L/100km |
| --- | ---: | ---: | ---: |
| 动力115% | 3940 | 58.779 | 21.390 |
| 轻量低阻 | 4780 | 59.626 | 19.963 |
| 制动125%与前制动份额65% | 1840 | 60.866 | 19.728 |

三个结果复现此前矩阵的完赛用时和油耗。在该策略下，动力最快，轻量低阻在两项之间，制动方案最慢且耗油最少。完整赛段的油耗差同时受驾驶节奏和传动状态影响。

另用较晚制动策略，在相同前制动份额65%与前防倾份额40%下隔离制动容量。两例均四门有效且复算通过。原制动峰值踏板请求69.3%，制动125%为56.7%，观察区间是250—400米。用时58.966→59.068秒，油耗21.810→21.788 L/100km。这里有踏板余量，仍缺同条件下的实质提速证据。

原始数据和复算在 `logs/challenge-takeover-20261106/valley-v2-main-choices`、`valley-v2-later-braking` 和 `verify_valley.py`。五次均为自动驾驶，奖牌线、报价和真人体验继续待标定，整包验收仍开放。

```powershell
$sdk=(Resolve-Path 'build/road-edge-sdk/panda/built-road-edge').Path
$env:PYTHONPATH="$sdk;$env:PYTHONPATH"
.venv/Scripts/python.exe tools/challenge_balance_check.py --output logs/challenge-takeover-20261106/valley-v2-main-choices --routes valley_pace --builds power-only braking efficiency --seconds 120 --target-kph 105 --curve-acceleration 3.8
.venv/Scripts/python.exe tools/challenge_balance_check.py --output logs/challenge-takeover-20261106/valley-v2-later-braking --routes valley_pace --builds free-setup tuned-braking --seconds 120 --target-kph 105 --curve-acceleration 3.8 --braking-acceleration 5
.venv/Scripts/python.exe tools/validate.py T0 --tests tests/test_valley_pace.py tests/test_sprint_ui.py --output logs/challenge-takeover-20261106/valley-cues-final-T0 --timeout 180
.venv/Scripts/python.exe tools/challenge_ui_check.py --output logs/challenge-takeover-20261106/valley-cues-final-scene --road-feedback --size 1280 720
```

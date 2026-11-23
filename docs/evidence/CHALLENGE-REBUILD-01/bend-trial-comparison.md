# 平路连弯的试行奖牌与重试对照

2026-11-06，基线 `15c321f5`。有奖牌目标的预算道路结算此前只显示目标数值，驾驶 HUD 已经能对照发车前的最快完赛。现在预算内有效完赛、且已有同组成绩时，结算沿用同一次最快驾驶显示时间和油耗差值。本次刷新最快也继续使用发车时的对照。奖牌要求和升牌差距沿用原有表格与提示。

本机游戏入口使用的接缝修正 SDK，固定种子17。两组都使用曲率目标4.4 m/s²和90%转向余量，组间只调整控制器目标速度。六次自动试跑均无碰撞、四门完赛。实际子步油耗、首次过终点时刻、来源指纹和原六份真人记录哈希均已核对。

| 目标速度 / km/h | 方案 | 费用 | 用时 / s | 油耗 / L/100km | 符合的试行数值 |
| ---: | --- | ---: | ---: | ---: | --- |
| 105 | 原车 | 0 | 93.922 | 19.288 | 金 |
| 105 | 前胎130% | 2000 | 92.150 | 19.436 | 金 |
| 105 | 轻量低阻 | 4780 | 93.770 | 18.946 | 金 |
| 105 | 均衡 | 5000 | 92.938 | 20.286 | 银 |
| 125 | 前胎130% | 2000 | 90.662 | 21.413 | 银 |
| 125 | 动力115% | 3940 | 91.212 | 22.880 | 铜 |

105 km/h目标组中，原车零费用，前胎比原车快1.772秒，轻量低阻比原车少耗0.342 L/100km。均衡方案相较前胎方案费用更高、用时更长、油耗更多。把前胎方案的目标车速提高至125 km/h后，省1.488秒，油耗增加1.977 L/100km；同策略的动力方案比前胎慢0.550秒。这些数值用于核对现有试行门槛和具体策略，自动驾驶未获得奖牌或写入玩家成绩。正式价格、真人重复样本和最终验收保持开放。

相关T0共24项及全仓Ruff通过。使用实跑数字构造结算状态，检查1280×720金牌页和960×720银牌页，个人差值、试行目标及银牌升金提示均清晰可读。两张图是实际界面渲染，采集时未推进车辆或写入成绩。本轮未做前台手感或实时性能验收，未提交推送。

```powershell
$sdk=(Resolve-Path 'build/road-edge-sdk/panda/built-road-edge').Path
$env:PYTHONPATH="$sdk;$env:PYTHONPATH"
.venv/Scripts/python.exe tools/challenge_balance_check.py --output logs/challenge-takeover-20261106/bend-trial-choices --routes bend_sprint --builds stock front-tire130 efficiency balanced --seconds 125 --target-kph 105 --curve-acceleration 4.4 --steering-reserve 0.9
.venv/Scripts/python.exe tools/challenge_balance_check.py --output logs/challenge-takeover-20261106/bend-exit-speed --routes bend_sprint --builds front-tire130 power-only --seconds 125 --target-kph 125 --curve-acceleration 4.4 --steering-reserve 0.9
.venv/Scripts/python.exe logs/challenge-takeover-20261106/verify_bend_trial.py bend-trial-choices
.venv/Scripts/python.exe logs/challenge-takeover-20261106/verify_bend_trial.py bend-exit-speed
.venv/Scripts/python.exe tools/validate.py T0 --tests tests/test_challenge_run.py tests/test_challenge_ui.py --output logs/challenge-takeover-20261106/T0-bend-trial-comparison --timeout 180
```

# 山脊长周期缓弯接入

2026-11-06，HEAD `15c321f5`。沿用 [图08与已确认的米制规格](../../design/challenge-courses-v2/08-ridge-012-design.png)。具备路面内部边修正的本机游戏与试玩入口加载 `budget-ridge-long-waves` / `budget-route-v5`。普通 Panda3D 继续使用旧预算山脊 v4，专家路线仍为 `hills`。新旧成绩和方案按现有规则版本分组，六份原试玩逐拍记录按 SHA256 校验一致。

起伏段530—770米，累计转向30°，峰谷高差0.12米，16、24、20米周期各四组。全长1400米、预算5000、13.5米路宽、350/700/1050/1400米四门和540米下坡提示牌沿用原规格。

正常关卡目录直接发车三次。目标105 km/h，起伏局部目标140 km/h，控制器根据曲率和转向余量调整车速。三次均四门完赛，原始油耗和终点复算通过，同策略的隔离候选与正式入口的轨迹、轮荷文件逐字节一致。

| 方案 | 费用 | 用时 / s | 油耗 / L/100km |
| --- | ---: | ---: | ---: |
| 原车 | 0 | 72.771 | 22.102 |
| 前胎与免费调校 | 2000 | 71.096 | 23.452 |
| 同调校加软弹簧 | 3500 | 70.753 | 23.637 |

三套方案在这组策略下形成费用、时间、油耗取舍。此前较稳策略下，软簧改善贴地，但用时优势反转，见[接缝修正实测](ridge-edge-adjusted.md)。这些自动试跑作为路线决策证据，正式奖牌和价格仍待真人样本。

修正版 SDK 的 T0 含相关44项和全仓 Ruff，普通 SDK 的山脊入口测试另过。现有场景工具经正常应用入口生成435/590/790米和总览四张图，均已查看并对照设计，起终点投影在画内，原下坡牌可见，地形条带仍存在。完整输出在 `logs/challenge-takeover-20261106/ridge-v5-main`、`ridge-v5-main-scene` 和 `ridge-v5-T0`。本轮采用本机路线，整包T1/T2、真人体验和打包版接入仍开放。

```powershell
$sdk=(Resolve-Path 'build/road-edge-sdk/panda/built-road-edge').Path
$env:PYTHONPATH="$sdk;$env:PYTHONPATH"
.venv/Scripts/python.exe tools/challenge_balance_check.py --output logs/challenge-takeover-20261106/ridge-v5-main --routes ridge_sprint --builds stock rough-free rough-free-soft --seconds 120 --target-kph 105 --curve-acceleration 3.8 --rough-acceleration 7.5 --rough-target-kph 140 --steering-reserve 0.9
.venv/Scripts/python.exe tools/challenge_ui_check.py --output logs/challenge-takeover-20261106/ridge-v5-main-scene --course-scenes --course-route ridge_sprint --size 1280 720
.venv/Scripts/python.exe tools/validate.py T0 --tests tests/test_career_courses.py tests/test_challenge_catalog.py tests/test_challenge_balance_policy.py --output logs/challenge-takeover-20261106/ridge-v5-T0 --timeout 180
```

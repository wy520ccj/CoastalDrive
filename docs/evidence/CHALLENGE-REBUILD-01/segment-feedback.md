# 分段结算与赛前方案补齐

2026-11-06，基线 `15c321f5`。道路挑战结算保留[图02原三列表](../../design/challenge-budget-v1/02-result.png)，改为每段真实用时和按该段长度折算的油耗。山谷四段按测速、减速、限速、冲线命名。括号为发车前冻结的最快完赛在同一段的差值。失败只显示已通过路段的本次值。驾驶提示与结算使用同一个分段换算，专项结算仍展示累计值。奖牌依据仍是完整赛段的同次结果。

| 路线 | 方案 | 原策略 用时 / 油耗 | 本轮 用时 / 油耗 |
| --- | --- | ---: | ---: |
| 山谷节奏 | 制动升级 | 60.866 / 19.728 | 60.688 / 19.778 |
| 山谷节奏 | 轻量低阻 | 59.626 / 19.963 | 59.896 / 19.819 |
| 山脊冲刺 v5 | 前轮与调校 | 71.096 / 23.452 | 71.477 / 22.547 |
| 山脊冲刺 v5 | 软簧与调校 | 70.753 / 23.637 | 70.898 / 22.180 |

用时为秒，油耗为 L/100km。四次补跑及四次已有结果均复算终点和油耗，按现行门槛每套两次达金。山谷本轮轻量低阻共快0.793秒，出带后贡献0.602秒，该段油耗高约0.75 L/100km。山脊本轮软簧快0.579秒、低0.367 L/100km，起伏区间未全轮接地的采样数25→20、俯仰跨度3.52°→3.11°，垂向跟踪误差反而略增。原策略软簧也更快但更耗油，早期保守策略用时次序相反。结果支持当前参考方案，价格与其它打法仍需在后续开发中收口。

普通 SDK 的山脊 v4 现提供原车、前轮与调校，沿用本路线标定样本72.295秒/20.316与71.974秒/20.230。直道车流安全超车现提供原车、轻量低阻（含前制动65%、前防倾40%），沿用84.441秒/10.979与83.788秒/10.742。四条标定记录均已达到各自金牌线，这两条路线本轮直接复用原完赛数据。山脊 v5 仍采用自己的两套配置。

原始文件、验证脚本和截图在 `logs/challenge-segment-feedback-20261106/`。山谷与山脊的 4:3、16:9 结算截图用本轮两套完整实跑构成显示夹具，原始驾驶和夹具存档隔离。普通版山脊和直道车流各核对一张真实方案页并从正常入口发车。两组 T1 分别22项和2项通过，均含 Ruff 与三个固定种子启动。改动留在本地工作区，整包 T2 和实际性能验收开放。

```powershell
$sdk=(Resolve-Path 'build/road-edge-sdk/panda/built-road-edge').Path
$env:PYTHONPATH="$sdk;$env:PYTHONPATH"
.venv/Scripts/python.exe tools/challenge_balance_check.py --output logs/challenge-segment-feedback-20261106/valley --routes valley_pace --builds braking efficiency --seconds 90 --target-kph 100 --curve-acceleration 3.4 --braking-acceleration 2.8
.venv/Scripts/python.exe tools/challenge_balance_check.py --output logs/challenge-segment-feedback-20261106/ridge --routes ridge_sprint --builds rough-free rough-free-soft --seconds 105 --target-kph 102 --curve-acceleration 3.8 --rough-acceleration 6.5 --rough-target-kph 125 --steering-reserve 0.9
.venv/Scripts/python.exe logs/challenge-segment-feedback-20261106/review.py 960 720
.venv/Scripts/python.exe logs/challenge-segment-feedback-20261106/review.py 1280 720
```

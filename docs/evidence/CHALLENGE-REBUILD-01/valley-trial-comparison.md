# 山谷试车保留制动对照

2026-11-07，基线 `15c321f5`。完整自动试车把测速门速度、25 米平均制动踏板请求和入带速度与同次用时、油耗、改装一起保存。结算沿用已有分段表的括号差值，继续支持重开后对照另一套改装和套用完整方案。旧试车仍能对照用时与油耗，缺少的制动读数留空。失败试车不会写入完赛对照。

复用上一趟制动升级，只补一趟轻量低阻，用正常入口加载对照并驾驶，复算 120 Hz 终点和原始机械子步耗油。试车档从磁盘重开，核对两次完整配置和各自制动读数。

| 方案 | 费用 | 用时 / s | L/100km | 测速门 / km/h | 平均踏板 | 入带 / km/h |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 制动升级 | 1840 | 59.828 | 20.199 | 83.0 | 71.89% | 45.7 |
| 轻量低阻 | 4780 | 59.001 | 20.228 | 83.1 | 82.17% | 46.0 |

两套在现行 375 米规则下各有两次完整实跑达到金牌线。免费调校保留零费用有效完赛路径，已测 59.249 秒、20.743 L/100km 达银。该策略下，轻量低阻最快，制动升级的平均制动踏板请求与油耗更低。自动试车不写玩家奖牌。

T1 通过 21 项、Ruff 和三种子短启动。首次 960×720 结算图中三项差值靠近用时列，缩小原数据列文字后复用已存数据离屏核对。本轮只新增一次完整驾驶。证据在 `logs/challenge-valley-trial-comparison-20261107/`。源码已更新，独立试玩包和整包 T2 待更新。

```powershell
$sdk=(Resolve-Path 'build/road-edge-sdk/panda/built-road-edge').Path
$env:PYTHONPATH="$sdk;$env:PYTHONPATH"
.venv/Scripts/python.exe logs/challenge-valley-trial-comparison-20261107/drive.py --render-only
.venv/Scripts/python.exe tools/validate.py T1 --tests tests/test_trial_references.py tests/test_valley_pace.py tests/test_challenge_ui.py::test_automatic_comparison_keeps_other_build_across_retries --output logs/challenge-valley-trial-comparison-20261107/T1 --timeout 150
```

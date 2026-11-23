# 赛前参考方案实跑值

2026-11-07，基线 `15c321f5`。保留图03的方案栏、两枚按钮和费用，当前草稿与有样本的方案完全一致时，原栏标题显示该配置一次实跑的用时和油耗。选另一套就切换到对应数据。手改任何参数导致配置不同后恢复普通标题，保留自由编辑与原发车流程。显示到 0.1 秒和 0.01 L/100km。

复用 24 份此前已复算的完整记录。同一路线的两个方案来自同策略，逐一核对了完整改装、价格、原始记录存在和屏幕显示精度。山脊 v4/v5 分开，五公里只在直线普通车流显示。短距制动和高速验车的参考按钮沿用原样。

| 实跑来源 | 赛前方案 |
| --- | --- |
| [正式样本](agent-calibration.md) | 海岸初驶、山脊穿行、山脊冲刺 v4、直道安全超车 |
| [生涯对比](career-balance.md) | 沿海冲刺、海岸杯决赛 |
| [平路重复达标](build-continuity.md) | 平路连弯 |
| [山谷制动窗口](valley-braking.md) | 山谷节奏现行 375 米测速门 |
| [山脊分段反馈](segment-feedback.md) | 山脊冲刺 v5 |
| [滨海及弯坡车流](coastal-traffic-setups.md) | 滨海计时、弯坡车流 |
| [五公里改装](distance-straight-setups.md) | 直线普通车流 |

T1 通过五项相关用例、Ruff 和三种子短启动。正常高速菜单选低风阻时，960×720 实际界面显示 189.0 秒、9.96 L/100km 和 1780 费用；手调风阻后实跑数字收起。画面、方案校对脚本及输出见 `logs/challenge-preset-measurements-20261107/`。本轮未重跑标定。整包 T2、实际性能与剩余平衡开放。

独立试玩包更新到 `builds/challenge-preview-20261107/app/win_amd64/coastaldrive.exe`，包含此前试车对照和五公里方案。构建复用已导出的路面修正版 wheel。实际程序在清除 `PYTHONPATH` 后离屏启动成功，退出码 0、完成 289 个物理步。验证与来源清单见构建目录的 `verification/smoke/h0-render-smoke.json` 和 `build-receipt.json`。本地构建，未提交、推送或发布。

```powershell
$sdk=(Resolve-Path 'build/road-edge-sdk/panda/built-road-edge').Path
$env:PYTHONPATH="$sdk;$env:PYTHONPATH"
.venv/Scripts/python.exe logs/challenge-preset-measurements-20261107/review.py
.venv/Scripts/python.exe tools/validate.py T1 --tests tests/test_challenge_ui.py::test_road_reference_builds_replace_draft_and_feed_normal_start tests/test_challenge_ui.py::test_reference_builds_only_match_their_supported_road_geometry tests/test_challenge_ui.py::test_career_sprint_presets_fit_each_budget_and_specialists_remain_manual tests/test_challenge_ui.py::test_automatic_comparison_keeps_other_build_across_retries tests/test_highway_entry.py::test_budget_distance_uses_highway_menu_conditions_on_start_and_retry --output logs/challenge-preset-measurements-20261107/T1 --timeout 150
```

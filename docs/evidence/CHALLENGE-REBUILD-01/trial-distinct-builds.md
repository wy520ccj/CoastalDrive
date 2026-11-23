# 试车保留不同改装对照

2026-11-07，基线 `15c321f5`。各路线在原有条件分组内保留最近两套不同方案的完整自动试车。重试当前方案时优先对照另一套，只有同一套时沿用它的上一趟。失败试车不更新记录，进入本趟时冻结对照。结算沿用原表格与套用按钮，已知参考方案直接显示名称，可恢复对照的完整改装。

旧单次试车存档直接读回，下次完整保存才更新格式。保存失败保留原文件，本次打开游戏仍可比较。试车不写入正式成绩、幽灵或巡回。

复用山谷新版两份已复算记录作为正常入口的结算夹具。重复轻量低阻后仍对照制动升级，显示前者快 0.83 秒、每百公里多耗约 0.03 L、贵 2940。整段试车对照油耗显示两位小数，正式奖牌规则沿用原精度。960×720 离屏图和夹具在 `logs/challenge-trial-distinct-20261107/`。本轮没有重跑驾驶标定。

T1 通过 8 项相关测试、Ruff 和三种子短启动。显示精度调整后，T0 通过 3 项自动及正式结算用例，最终离屏图已查看。

改动保留在本地源码，已有独立预览包是前一轮版本。新版山谷两套金牌方案仍各有一次完整驾驶样本，重复达标、其余改装平衡及整包 T2 开放。

```powershell
$sdk=(Resolve-Path 'build/road-edge-sdk/panda/built-road-edge').Path
$env:PYTHONPATH="$sdk;$env:PYTHONPATH"
.venv/Scripts/python.exe tools/validate.py T1 --tests tests/test_trial_references.py tests/test_challenge_ui.py::test_automatic_comparison_keeps_other_build_across_retries tests/test_challenge_ui.py::test_automatic_tour_trial_leaves_draft_unsaved_and_can_return_to_player_driving tests/test_highway_entry.py::test_budget_distance_uses_highway_menu_conditions_on_start_and_retry --output logs/challenge-trial-distinct-20261107/T1 --timeout 150
.venv/Scripts/python.exe tools/validate.py T0 --tests tests/test_challenge_ui.py::test_automatic_comparison_keeps_other_build_across_retries tests/test_challenge_ui.py::test_result_table_uses_same_run_metrics_and_marks_missing_grade_honestly --output logs/challenge-trial-distinct-20261107/T0-precision --timeout 110
.venv/Scripts/python.exe logs/challenge-trial-distinct-20261107/render.py
```

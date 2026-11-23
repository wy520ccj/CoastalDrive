# 按升牌差距选择对照

2026-11-06，基线 HEAD 15c321f5。道路驾驶中的个人最快对照保持发车时的选择。预算内有效完赛后，若还可以升牌，结算按用时、油耗相对下一档上限的差距选择对照。油耗差距较大时取已达到该档的最省油记录，用时差距较大或并列时取最快。缺少达标记录则沿用已有最快完赛。候选都来自发车前保存的本关完整成绩，时间、油耗、费用、分段和改装使用同一次驾驶。自动试车仍用上次有效试车。

结算沿用[原三列表和套用入口](reuse-reference-build.md)，显示所选达标记录及升牌差距。可以直接套用该次改装，草稿按原保存或发车操作写入。奖牌阈值、物理、报价和正式成绩存档格式保持。已核对的成绩分组沿用，逐拍原始指纹记录实际版本。

用既有山谷三套实跑在隔离存档做结算夹具。免费调校 59.249 秒、20.743 L/100 km 达银，已经满足金牌时间。发车时最快对照是轻量低阻的 59.001 秒，结算正确选中油耗最低的制动升级方案，显示 59.828 秒、20.199 L/100 km 和 1840 费用。套用后完整参数恢复，已存草稿保持。正常入口的 960×720 实际画面已查看。本轮未重复实跑。

相关 T1 21 项、全仓 Ruff 与种子 0/17/23 离屏启动通过。覆盖油耗或用时差距、两项都差、排除未达下一档的完赛、缺参照回退、发车后新纪录不混入、同次分段和现有方案恢复。更新山谷结算夹具到 375 米测速门，确认新 25 米制动段按真实长度折算油耗。

```powershell
$sdk=(Resolve-Path 'build/road-edge-sdk/panda/built-road-edge').Path
$env:PYTHONPATH="$sdk;$env:PYTHONPATH"
.venv/Scripts/python.exe tools/validate.py T1 --tests tests/test_challenge_run.py tests/test_challenge_scores.py tests/test_challenge_ui.py::test_result_table_uses_same_run_metrics_and_marks_missing_grade_honestly tests/test_challenge_ui.py::test_valley_result_compares_each_segment_and_keeps_partial_runs_unranked --output logs/challenge-promotion-reference-20261106/T1 --timeout 155
.venv/Scripts/python.exe logs/challenge-promotion-reference-20261106/render.py
```

证据和截图位于 `logs/challenge-promotion-reference-20261106/`。改动保留在本地，整包 T2 与实际驾驶体验仍开放。

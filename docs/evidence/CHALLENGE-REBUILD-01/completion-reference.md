# 未标定道路的有效完赛对照

2026-11-02。核对到真实逻辑断点：所有未标定道路的`targets`为空，`ChallengeScores.record`原来只保存有奖牌的结果。因此预算内有效完赛虽有原始逐拍文件，却没有个人最佳，后续发车始终没有最佳分段对照。不是缺少真人样本本身导致该功能必须失效。

## 修改

- `challenge_scores.py`在当前条件组增加`completed`，保存预算内有效完赛的最快、最低燃油和最低费用三个完整记录。奖牌记录仍在原`records`中；没有目标的完赛不创建奖牌。失败、超预算、缺少燃油及自动控制仍不能写入这些正式个人记录。
- 每个记录保留完整方案、用时、燃油、费用、车辆校验和及同次分段，不拼接各项最低值。旧文件没有`completed`也正常读取；新目标、输入、物理或其它条件仍分组隔离，原内容保留。
- `ChallengeRun`出发时优先冻结已保存最快完赛，旧有奖牌文件可沿用原最快记录。下次实际驾驶的现有分段提示由此可用；本次刷新最快不会改变出发时的对照。
- 未标定道路的既有结算主表右列显示“最快完赛”，用时、油耗、费用全部来自出发时同一次记录。首次无对照继续显示“目标待标定”。沿用已实现的预算结算设计、列宽和控件，只替换已有表格的数据与文字，没有新增页面布局。

本轮生产修改仅为上述三文件。车辆、道路、物理精度、价格、目标与解锁规则未改。当前仅有6份初章真人记录，原文件哈希全部保持；没有把它们补写为当前版本成绩，也没有把合成记录写入玩家目录。

## 验证

一次相关短检查13项与Ruff通过，覆盖跨方案完整记录、失败/超预算排除、保存失败保护、旧文件加载、新目标隔离、重启读取与出发对照冻结，以及实际结算控件的内容和4:3缩放。不增加驾驶矩阵、三种子物理长跑或T2；整包尚未完成，未声称新T1/Gate通过。

```powershell
.venv/Scripts/python.exe -m ruff check src/challenge_scores.py src/challenge_run.py src/ui/challenge_layout.py tests/test_challenge_scores.py tests/test_challenge_run.py tests/test_challenge_ui.py
.venv/Scripts/python.exe -m pytest tests/test_challenge_scores.py tests/test_challenge_run.py tests/test_challenge_ui.py::test_result_table_uses_same_run_metrics_and_marks_missing_grade_honestly -q --junitxml=logs/challenge-rebuild-20261102/completion-reference/checks.xml
```

实际结算截图`logs/challenge-rebuild-20261102/completion-reference/result-vs-completed.png`已查看：本次60.0秒/7.0L/100km/2250，出发时最快64.0秒/8.0L/100km/0分别呈现，表头、三行及四个道路门无重叠；仍明确“评级标定中”，无奖牌。数字为隔离目录的合成控件夹具，不是实际驾驶或真人标定依据；当前物理快照未推进。首次截图因夹具遗漏`taskMgr.step`初始化而失败，沿用现有采集工具顺序修正后成功，失败记录和原夹具文件保留，生产渲染未因此改动。

原文件副本、检查XML、采集脚本/JSON、真人文件哈希核对均在`logs/challenge-rebuild-20261102/completion-reference/`。当前来源单独存`manual-ready-after-completion-reference.json`；原准备版本不覆盖，标定仍以实际当前源码/SDK核对。改动未提交推送。

悬架收费价值、主要路线的改装竞争性、两套真人方案各两次与正式奖牌线、最终T2及用户体验仍未收口；本修复只让实际完赛能成为后续比较依据。

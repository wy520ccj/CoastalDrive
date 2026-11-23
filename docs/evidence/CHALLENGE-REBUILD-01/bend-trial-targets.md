# 平路试行目标接手核对

2026-11-05，基线HEAD `15c321f5`，工作区含已有大量未提交修改。本轮保留生产实现，仅补结果页回归和事实记录，未提交、未推送。

## 当前实际规则

上轮末尾已在正常平路挑战接入 `budget-bend-trial-v1`，`provisional=True`。铜/银/金的联合要求分别为124.3秒与26.2 L/100km、107.1秒与22.6 L/100km、95.6秒与20.1 L/100km。来源为 `logs/challenge-agent-20261102/bend-trial-targets/candidate.json` 中两套代理方案各两次记录；这是试行目标，不是真人冻结线或付费平衡验收。

人工驾驶预算内达标可保存试行奖牌；成绩上下文包含完整规格及试行标记，与后续正式规格隔离。自动控制由 `ChallengeRun.stop` 清除奖牌、设为非正式并跳过成绩写入。规则对象的 `official` 表示本次是否符合记分条件，不表示门槛已完成人工标定。其它无目标道路仍保存预算内有效完赛对照，不授奖。

## 遗留验证修正

旧 `capture.py` 要求银牌结算连续出现“试行目标”，但该页目标列为“金牌目标 · 试行”，反馈行按实际差距显示“油耗已达标，用时需缩短0.5秒”。生产显示正确，原金牌结果测试也通过。保留旧失败脚本，在 `logs/challenge-takeover-20261105/fixture/` 复制并修正核对条件；新增银牌结果参数化回归，保护目标标记和差距反馈。

离屏实际控件三图（参数、金牌、银牌差距）已查看，标记和数字可见，截图脚本通过。合成结算只验证控件，不作驾驶或真人样本；未改布局、美术、车辆、道路、报价及门槛。

验证命令：

```powershell
.venv/Scripts/python.exe logs/challenge-takeover-20261105/fixture/capture.py
.venv/Scripts/python.exe -m pytest tests/test_challenge_rules.py tests/test_challenge_scores.py tests/test_challenge_run.py tests/test_challenge_catalog.py tests/test_challenge_ui.py::test_result_table_uses_same_run_metrics_and_marks_missing_grade_honestly -q --tb=short --junitxml=logs/challenge-takeover-20261105/checks.xml
.venv/Scripts/python.exe -m ruff check tests/test_challenge_ui.py src/challenge_catalog.py src/challenge_rules.py src/challenge_scores.py src/challenge_run.py src/ui/challenge_layout.py
```

结果：相关45项通过，Ruff通过，截图脚本3图通过。未重启参数矩阵、完整T2、物理三种子或前台驾驶。下一施工块仍是区分驾驶策略限速与硬件能力，并解决付费改装的实际关卡收益；三种竞争解、可重复金牌、真人标定、性能和最终验收继续开放。

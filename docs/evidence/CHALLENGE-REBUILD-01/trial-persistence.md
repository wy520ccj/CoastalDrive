# 自动试车对照存档

2026-11-06，基线 HEAD 15c321f5，接续已有未提交玩法改动。

- 每种有效试车条件保留最近一次完整完赛、改装方案和分段用时/燃油。下次发车时读取并固定上次参照，行驶和结算均可比较，结算可套用该方案。分组含赛事及规则、实际路形和车流、驾驶辅助、自动驾驶策略、车辆仿真、油耗和报价版本。
- 有效超预算试车也可对照。未完赛、撞车等无效试车不覆盖。记录独立放在用户数据目录的 `trial-references/`，读取异常保留原文件，写入失败可在当前运行内继续对照。历史日志继续留作开发证据，旧日志不会自动导入玩家存档。
- T1 通过 Ruff、3 项存档与入口用例及种子 0、17、23 的离屏检查。入口用例覆盖重新实例化读档、完整方案恢复、条件隔离、写入失败后保留原记录。命令为 `.venv/Scripts/python.exe tools/validate.py T1 --tests tests/test_trial_references.py tests/test_challenge_ui.py::test_automatic_comparison_uses_last_complete_trial_and_keeps_its_build --output logs/challenge-trial-persistence-20261106/T1 --timeout 140`，使用项目的道路 SDK。
- 用 `logs/challenge-trial-persistence-20261106/reopen.py` 在两个独立进程经普通预算入口验证重启对照。沿用之前两次滨海自动完赛的实际数据，首进程保存前胎方案（54.324 秒、21.142 L/100 km），第二进程加载该参照并显示减重低阻方案（55.174 秒、20.996 L/100 km），核对五段和“套用上次方案”，同组文件为 788 字节，隔离用户目录未产生玩家成绩或草稿。截图见 `logs/challenge-trial-persistence-20261106/isolated-game/reopened-comparison.png`。

本块未重复驾驶，未安排整包 T2 或性能测试。改动保留在本地工作区。

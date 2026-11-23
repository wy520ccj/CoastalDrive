# 完整回归接续

2026-11-02接手更新：第二轮最终379过1滚动求根失败；正式修复相关82项通过，见[接手核查](rolling-root-handoff.md)。之后旧第三轮已中断。本轮新`T2-takeover`亦在用户要求停止反复测试后主动停止，未完成，不重启。原summary残留running不是通过结论，单独记账在`logs/challenge-rebuild-20261102/verification-stop.json`；其后才实施山脊v4，不能把这些旧运行称为v4完整回归。

2026-11-01。三条短途预算路线及相关39项T1通过后启动完整T2。自动结果、画面与真人门槛分开记账；整包仍in_progress，未提交推送。

首轮：`logs/challenge-rebuild-20261101/T2-challenge-integrated`，Ruff过，pytest146过1失败，262.84秒后按入口fail-fast停止，后续检查未跑。失败为`test_career_entries_pair_coastal_light_and_restore_mountain_and_menu[False]`仍假定生涯点击后直接发车，实际现在先进入预算页，故career_event_id仍为空；没有观察到生产光照断言失败。

仅更新`tests/test_career_lighting.py`的实际流程：先断言预算页，再调用正常challenge-start，保留全部天空、环境、曝光、太阳、候选海面与退出恢复原断言。`T0-career-lighting-entry`全模块8项通过，pytest65.59秒、Ruff过；旧报告重试单项另1项通过，未改该流程或随意迁移夹具。

第二轮已启动：`.venv/Scripts/python.exe tools/validate.py T2 --timeout 7200 --output logs/challenge-rebuild-20261101/T2-challenge-integrated-fixed`，pytest临时文件隔离到`full-T2-fixed-temp`。上限仅为每检查墙钟等待，不改变物理时钟、精度或测试集合。当前仍在执行，不能称完整通过；状态以该目录summary及实际进程为准。

当前目录库存另保存`current-challenge-catalog.json`，供后续补生涯、车流、长距离和环路等未完整测量情境；它不是这些关卡平衡已完成的证据。正式道路targets仍空，无真人金牌样本。

第二轮期间仅扩展独立对比工具以支持生涯及正确环路入口，生产src和pytest集合未改；该工具没有pytest导入，另跑全Ruff与四个真实Session的0.1秒启动/主动中止核对。详见[入口证据](career-comparison-entry.md)，不把中止样本当平衡结果，也不把前轮Ruff冒称检查了后增代码。当前进度页将本任务旧段落归并为当前事实，原前缀保存在日志，其他任务后缀字节保持。

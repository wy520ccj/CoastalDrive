# 生涯与环路对比入口

2026-11-01。扩展独立的`tools/challenge_balance_check.py`，准备补齐三条短途以外的关卡平衡。生产源码和当前pytest集合保持；完整T2仍运行，不宣称已通过。

工具现在从实际ROAD_CHALLENGES中选择road类课题，解析GameMode键与生涯字符串ID；以course_mode/course_shape/course_track启动正常Session，并为生涯传真实career_event_id。滨海使用实际coastal闭环，不能因工具写死endless而误测直路。排除刹停/过门等需要专项控制的课题；原三条短途调用和方案预检保持。

输出增加实际track、shape选项与本次仿真碰撞增量，继续保存完整预算方案、策略、原始120Hz燃油/分段与20Hz路径/轮荷。自动驾驶不授奖，超预算候选预先拒绝。

新增后全Ruff通过；`catalog-entry-smoke`实际启动coast-sprint、ridge-run、coastal-cup和time_trial各0.1秒，再由工具主动结束。四例实际track/shape分别为endless/coast-club、endless/ridge-club、endless/coast-final、coastal/straight（环路忽略shape选项）。原始trace的spec.id对应真实课题，源码首末稳定，四例均invalid/non-official，零授奖。这里只验证入口，未把启动或中止样本当作完整关卡/价格/金牌证据。

实际命令：`.venv/Scripts/python.exe tools/challenge_balance_check.py --output logs/challenge-rebuild-20261101/catalog-entry-smoke --routes coast-sprint ridge-run coastal-cup time_trial --builds stock --seconds 0.1`。

后续先在完整回归结束后实跑生涯沿海/山脊/决赛预算矩阵，再补环路和车流策略。若某自动策略不能完成，只按失败处理，不修改物理或裁判来凑样本。

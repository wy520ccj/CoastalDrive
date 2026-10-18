# 海岸制动工坊证据

- 版本：基线main/cfa221b，本任务源码/测试/工具；未改物理核心或原生扩展。
- `normal.json`、`double.json`：普通/Double各实际计算三次完整A/B（原方案、超预算组合、节约金牌），同窗进入计时并返回、关闭后从实际导出记录重建窗口。
- 普通停车：A32.406474m，B28.293530m，改善12.691737%；Double：A32.406444m，B28.293632m，改善12.691338%。超预算组合即使约24.57%改善仍不获奖。不同精度分别计算，没有要求跨库逐浮点相同。
- `final-ui.json`：最后HUD任务说明/结算“返回工坊”动作/直接回到面板的Double补验，复用同库已生成原始A/B，不重复测物理。
- `gold-double.png`、`ab-curves.png`为真实挑战结果与曲线；`road-result-fixture.png`是显式注入规则夹具后的结果页，90秒是假定圈速，不是实际驾驶成绩。自动工具证明控件/规则/保存/交接，人工驾驶与趣味性待确认。

## 命令与范围

- 普通T0：`tools/validate.py T0 --tests tests/test_workshop.py tests/test_workshop_ui.py --output logs/validation/DESIGN-CHALLENGE-01-T0 --timeout 300`，Ruff/9项通过。
- 普通T1：`tools/validate.py T1 --area design --output logs/validation/DESIGN-CHALLENGE-01-T1 --timeout 300`，Ruff/46项与0/17/23各1200步通过。
- T1后补充持久化指标校验/全屏模态遮挡/保存记录恢复/取消与模式约束：Double最终针对T0，`tools/physics/run_sim_double.py tools/validate.py T0 --tests tests/test_workshop.py tests/test_workshop_ui.py tests/test_vehicle_workspace.py tests/test_workspace_transition.py --output logs/validation/DESIGN-CHALLENGE-01-T0-final-double --timeout 300`，15项/Ruff通过。
- 最后普通T0：`tools/validate.py T0 --tests tests/test_workshop.py tests/test_workshop_ui.py tests/test_workspace_transition.py tests/test_driving_mode_ui.py --output logs/validation/DESIGN-CHALLENGE-01-final --timeout 300`，16项/Ruff通过。最后仅结果页返回入口/HUD文案/直接显示工坊及错误提示更新；实际Double最终UI再覆盖这些入口，T1其他结果复用。
- 普通实际流程：`tools/workshop_check.py --output logs/DESIGN-CHALLENGE-01/normal-r3`。
- Double实际流程：`tools/physics/run_sim_double.py tools/workshop_check.py --output logs/DESIGN-CHALLENGE-01/double`。
- 最终UI补验：`tools/physics/run_sim_double.py tools/workshop_check.py --output logs/DESIGN-CHALLENGE-01/double-final-ui --vehicle logs/DESIGN-CHALLENGE-01/double/test-workspace-vehicle.json`。
- 所有Python命令使用本项目`.venv/Scripts/python.exe`，Double使用现有隔离SDK。工具隔离LOCALAPPDATA，不覆盖用户车辆或实验记录。

## 保留的失败与未执行项

- 首次普通流程在两个连续RESULTS夹具间没有清空界面缓存，第二页未刷新；修正工具夹具，生产逻辑不因测试而重算规则。
- 第二次在新建ShowBase后直接renderFrame，simplepbr尚未更新camera_world_position而失败；工具先真实taskMgr.step，再截图，后续通过。原失败日志/截图保留于normal、normal-r2，不计作通过。
- T2/T3、实车标定、独立物理进程长测、性能/人工手感/趣味性未跑，不随本任务关闭。

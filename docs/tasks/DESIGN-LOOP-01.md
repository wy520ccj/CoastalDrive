# DESIGN-LOOP-01 车辆设计—实验—游戏闭环

- 状态：done（实现与自动验收完成；本批人工驾驶待体验）
- 基线：main / 72fabc1ed3aa1e0d4d33b3c0fc72a017b5366d13；开始前工作区干净。
- 单条施工线；本轮实现一个可试用的闭环，AI接口留作后续。

## 目标与范围

游戏当前车辆进入实验室；配置/导入工程车并完成试验后，可保存试验车辆并带入游戏自由驾驶。重启后保留应用的工程车。游戏对照使用同车、同工况、相同直接命令序列，比较实验配置与游戏单机械步配置，导出两份原始记录及差异报告。

- 修改：车辆交接/保存、实验台游戏对照、相关窗口入口、测试、验证映射及说明。
- 不改：物理公式、默认车辆硬件、游戏键盘辅助、120Hz、原生扩展、只读归档。
- 数值对照仅评价游戏积分配置差异；不自动调参、不虚构误差合格阈值。未完成、失败或旧版本记录不能冒充当前完整对照。

## 验收

- [x] 工程参数/电子配置从实验带到游戏，再回实验室；只改游戏已有单步配置。
- [x] 保存/重启恢复；车库明确切换新车型解除原工程车。
- [x] 同命令真实运行、终止/长度差异如实显示、两份记录及报告可追溯。
- [x] T0/T1相关模块与种子通过；实际UI渲染/往返切换通过。
- 人工驾驶手感：待用户体验，自动项不代替。
- T2/T3：本次功能包不运行全阶段长测。

## 验证

- T0：`tools/validate.py T0 --tests tests/test_vehicle_workspace.py tests/test_lab_game_comparison.py tests/test_design_loop_ui.py tests/test_vehicle_design_entry.py tests/test_lab_ui.py`
- T1：`tools/validate.py T1 --area lab --area design`，及真实往返/渲染检查工具。
- 工程车性能不预先宣称实时；完整精度/实车标定及既有Gate继续独立记账。

## 交接

实现：`vehicle_workspace`保存完整参考配置；`lab_game_comparison`重放参考命令、计算公共时间段误差并导出两侧完整记录；`ui/lab_design_loop`提供游戏联动操作；main负责先释放旧会话再切换。应用来自正常完成的参考试验，未重跑的输入不进入游戏；工程车重启恢复，电子开关同步保存，同设计换色保留工程车，切换其他设计解除覆盖。

双精度实验室直接进入游戏暴露原绘图API只收float向量：scene/expressway写入改为解包分量；expressway_route的float顶点经tuple进入当前精度的NodePath。只处理显示边界，物理公式、默认硬件、机械步、原生扩展未改。旧车型测试错误地要求game/simulation逐参数相同，已明确只允许游戏`tire_substeps=1`；Double高速测试读取float网格处同步做边界转换，几何净空阈值保持。

### 验证结果

- 普通T0最终：`tools/validate.py T0 --tests tests/test_vehicle_workspace.py tests/test_lab_game_comparison.py tests/test_design_loop_ui.py tests/test_vehicle_design_entry.py tests/test_lab_ui.py tests/test_driving_mode_ui.py tests/test_vehicle_designs.py tests/test_expressway.py --output logs/validation/DESIGN-LOOP-01-T0-normal-final --timeout 300`，Ruff/74项通过。
- Double T1主体：`tools/physics/run_sim_double.py tools/validate.py T1 --area lab --area design --tests tests/test_driving_mode_ui.py tests/test_environment.py tests/test_expressway.py --output logs/validation/DESIGN-LOOP-01-T1-double-complete --timeout 300`，Ruff/230项通过，剩余1项旧测试中另一处float向量读取失败；该次整体仍为failed，种子not_run。
- 最后只改该测试的tuple转换，生产代码与上述230项版本相同。补测：`tools/physics/run_sim_double.py tools/validate.py T1 --tests tests/test_expressway.py::test_kit_clearance_uses_serialized_geometry --output logs/validation/DESIGN-LOOP-01-T1-double-supplement --timeout 300`，Ruff/1项及0/17/23各1200拍通过。231项为230项同源复用+1项补测，未伪称单次全绿。
- 普通原T0-first为测试使用不支持的Session lab赛道、多个ShowBase夹具及清理fake缺新成员3项；T0-fixed 58项通过。Double首次T1 192通过/2失败（游戏mesh向量边界与旧子步断言），扩展final批227通过/3失败（高速float读取边界）；原日志均保留，无失败改填成功。
- 真实工作流：普通`tools/design_loop_check.py --ui-only --output logs/design-loop-01/normal-ui-final`，Double `tools/physics/run_sim_double.py tools/design_loop_check.py --output logs/design-loop-01/double`均通过。真实ShowBase与SessionProcess读取已改质心/轮胎基准载荷配置，游戏单步、返回实验室恢复完整配置，关闭真实子进程后才开下一窗口。渲染查看1280×720游戏/实验联动与1024×768返回界面。普通第一次完整工具在游戏关闭后错误查询已关闭进程对象而终止；四组数值报告与此前截图保留，修正检查后普通仅补完整UI往返，不重复四组计算。
- 普通/Double各4组完整数值对照：参考基线/低质心0.40m × 100km/h制动/60km/h阶跃转向3s。8组输入前缀完全相同、配置唯一差异为2→1子步。普通基线停车44.113571→44.030898m；低质心44.002667→43.922692m。Double相应44.113526→44.030924m、44.002754→43.922707m。报告含RMSE/最大差及实际计算耗时，不设误差合格范围。
- 数值原始报告在`logs/design-loop-01/{normal,double}/{base,lower-cg}-{braking,step_steer}/`；各自source/runtime摘要保存实际生成版本，之后仅UI提示/报告按钮及显示float读取适配，不拼称全源哈希相同。汇总、验证原始summary和代表截图保存在`docs/evidence/DESIGN-LOOP-01/`。

### 交付与下一步

- 提交范围：72fabc1..本任务提交；只含本功能、必要显示边界修复、测试与文档；本地提交，不推送。
- 流程见[车辆设计闭环](../vehicle-design-loop.md)。人工驾驶待用户体验；T2/T3、当前工程车实时性能、跨32/64运行库标定、完整实车/精度Gate未跑，不作阶段通过。
- 下一步：体验闭环后确定标准工况覆盖与可接受误差，才开展游戏标定；AI接口/训练运行档另立任务。

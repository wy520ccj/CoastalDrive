# DESIGN-LOOP-02 试驾直接返回并恢复实验台

- 状态：done（实现、自动回归和实际渲染完成；用户新窗口体验待确认）；基线main/7bf24c8，开始前工作区干净。
- 用户复现：游戏联动后没有直接返回实验台入口；经主菜单返回时工况和参数看起来是默认值。
- 原因：上一版只传递WorkspaceVehicle硬件；新建LabOptions丢失工况/编辑值、记录、A/B及游标；游戏仅有主菜单入口。
- 范围：驾驶/暂停返回入口、实验台工作区交接与保存记录恢复、针对测试/渲染；不改车辆物理、辅助输入或性能配置。
- 验收：驾驶界面/暂停有返回按钮；真实关闭游戏世界后恢复原工况、所有输入值、A/B、曲线组及游标；新进程能从已应用记录恢复试验参数/结果；未重新试验的编辑值不能进入试驾硬件。
- T0：设计闭环UI、入口和实验UI相关测试。T1：lab/design完整相关模块+三种子。本次不重复车辆数值对照或T2/T3；人工体验另记。
- 修正旧验收：DESIGN-LOOP-01的往返只验证了硬件和μ，没有验证完整工作台状态，不能作为本次用户用例已通过的证据。

## 实现

- 驾驶HUD右上角、暂停菜单均可直接返回实验台；原主菜单入口仍可用。暂停六个动作使用0.155间距，最后按钮保留在底板内。
- `ui/lab_workspace.py`保存纯数据：车型/工况、所有普通及执行器输入文本（含未运行/无效草稿）、电子开关、工程配置/来源、A/B记录、曲线组、时间游标、视角/播放倍率和报告路径。main离开实验室时捕获，下一次进入时恢复；世界仍先关闭再创建，回放不保留第二个物理世界。
- 新进程没有内存工作区时，从WorkspaceVehicle已有report_path恢复完整已应用试验及参数。今后应用车辆时同时保存已有baseline-A；旧版没导出的A不能凭空恢复。未应用草稿/游标只在同次程序往返保留，重启恢复已保存试验。
- 未改变物理、机械子步、游戏辅助或原生模块。

## 验证

- 普通T0：`tools/validate.py T0 --tests tests/test_design_loop_ui.py tests/test_vehicle_design_entry.py tests/test_lab_ui.py --output logs/validation/DESIGN-LOOP-02-T0 --timeout 300`，Ruff/52项通过。
- Double T1：`tools/physics/run_sim_double.py tools/validate.py T1 --area lab --area design --tests tests/test_driving_mode_ui.py tests/test_mode_lifecycle.py --output logs/validation/DESIGN-LOOP-02-T1-double --timeout 300`，204项通过，1项旧生命周期测试仍要求GAME配置对象就是CAR（忽略既有单子步副本）失败；本次汇总保留failed、种子not_run。
- 仅修测试：配置值与`mode.configured_vehicle()`相同，全部车辆/部件仍要求引用同一实际config，未放宽硬件/物理阈值。Double T1补测该节点：`--tests tests/test_mode_lifecycle.py::test_switch_mode_restart_track_and_pause_keep_selected_configuration --output logs/validation/DESIGN-LOOP-02-T1-double-supplement`，该项/Ruff/0、17、23各1200拍通过。205项为204项复用+1补测。
- 最后只调整暂停页六按钮间距；Double最终T0：`--tests tests/test_design_loop_ui.py::test_driving_and_pause_provide_direct_return_button tests/test_driving_mode_ui.py --output logs/validation/DESIGN-LOOP-02-T0-final-ui`，5项/Ruff通过，含最后按钮不超底板的真实控件几何断言。上述T1其余结果明确复用，未再重复全跑。
- 普通/Double分别执行`tools/design_loop_check.py --ui-only --output logs/design-loop-02/{normal,double}`（Double经隔离入口），均通过。真实SessionProcess的HUD按钮、暂停动作和主菜单动作都请求返回；游戏进程关闭后，重建实验台恢复阶跃转向、65.5km/h与cg=.44编辑值、原60km/h/cg=.42已计算记录、A/B和第60拍游标；新窗口无内存快照时恢复已保存试验。最后间距单独Double实际渲染并查看；未重复上一批8组数值试验或T2/T3。
- 对用户真实已保存记录只读检查：`20261017-041330-319663-applied-vehicle`，新窗口恢复定圆60km/h、12秒、cg=.4、轮胎基准3000N及1441样本；查看高级参数渲染，未写原用户文件。该旧记录没有baseline-A，只恢复实际存在的B。
- 代表截图和summary在`docs/evidence/DESIGN-LOOP-02/`；原日志保留在上述logs路径。

## 交付

- 7bf24c8..本任务提交；只提交本修复、必要旧测试修正与说明；本地提交不推送。
- 当前旧进程不自动加载源码修改，需要用户重开原启动器；下次可自动载入上述已保存定圆记录。未关闭用户窗口、未覆盖用户配置或原记录；本批用户实际操作待确认。

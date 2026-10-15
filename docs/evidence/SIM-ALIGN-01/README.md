# SIM-ALIGN-01证据

基线b53527c，codex/simulation-fidelity独立树，main未整合。本块均布刷毛受力中心、指定转向接触速度/输入功进入Python及原生共同末状态。参考设计启用，游戏和GR86保持；默认120Hz/两机械子步。模型近似与实测缺口见[tire-aligning](../../tire-aligning.md)。

- 原生构建：`.venv/Scripts/python.exe setup.py build_ext --inplace`；本树mechanical_kernels由严格浮点源码重建，其他模块保持本树既有构建，未复制main DLL。
- T0：独立刷毛积分、正反行驶/指定转向能量、实际世界完整存档、原生/Python同输入与完整机械能量、旧布局测试15项通过。首次LabOptions使用错误字段steering后改为实际steering_deg；随后真实试验Mz为零揭示候选轮荷为零，改用上一施力轮荷后通过；没有修改力阈值。旧布局测试首次包装少一层，与真实存档包装对齐后通过。
- 中间相关原有测试346项通过，唯一失败为新公式清单尚未生成；离线生成35行后参数说明通过。两项Ruff导入顺序已修正。中间结果不当作T1。
- 最终T1：`.venv/Scripts/python.exe tools/validate.py T1 --area lab --tests tests/test_tire_aligning.py tests/test_tire_drivetrain.py tests/test_joint_suspension.py tests/test_drivetrain_jacobian.py tests/test_vehicle_parameters.py tests/test_vehicle_designs.py tests/test_physics_wire.py tests/test_world_substeps.py --output logs/validation/SIM-ALIGN-01-T1 --timeout 180`，414项/Ruff/0、17、23三种子各1200拍通过，收据与全部日志在T1。
- 实际世界：`tools/physics/tire_aligning_check.py --output logs/SIM-ALIGN-01/world-r1`，off/on-2/on-4/on-8/half-2均完成3s、无碰撞、原阈值通过，完整输出/读回核对保存world-records.zip；来源文件SHA保留在各记录。后续仅UI读数/浏览页修改，不重复相同力学试验。
- GUI：`tools/tire_aligning_ui_check.py --output logs/SIM-ALIGN-01/ui-720-r2 --height 720`，1080同命令；实际菜单回调、键盘F1/Esc、非零力矩、公式纹理尺寸及正文边界通过，各3图已目视。r1发现切换图后游标读数沿用上一信号，修复为当前采样；F1显示对应参数所在页。离屏渲染不等于人工验收。
- 真实旧归档：读回SIM-TIRE-FIT-01/vehicle-AB.zip的A396帧/B393帧，旧完整信号逐值验证、新机制默认为0；提取到logs的副本，原文件及源码指纹未回填。新版本复算仍须原模型指纹匹配，不把旧数据冒充新模型运行。

summary.json记录单开关A/B与细化：横摆峰值0.377226→0.361163rad/s，Mz峰值56.2705N·m；半长减半为28.3486N·m；相对八子步末横摆率误差两/四步为1.40995e−4/3.20673e−5rad/s。此证据只证明机制与数值作用，未证明实车准确度。八步也不是解析真值，各版本有自己的初始化。T2/T3、实测Mz、人工体验、外倾/K&C/独立簧下与main整合仍开放。

# INTEGRATE-20261015 游戏与实验台集成发布

- 状态：done（集成与发布检查完成；实验台人工与产品阶段Gate独立保留）。
- 用户本轮授权：检查游戏优化与试验台优化，合并工作，消除旧版本文件对判断的影响，然后提交推送。
- 主目录：`B:/AI agent/暑期计算机程序设计/CoastalDrive`，main，基线`722ecfd`；fetch后origin/main为`396084a`，本地领先8个提交、远端无独有提交。
- 范围：审核既有8个提交的集成状态，统一README/进度/入口与版本边界，隔离已提交源码编译和相关T1，提交本次整理并推送main。
- 保留未提交：setup.py、src/vehicle_suspension.py、src/wheel_contact_kernels.c、src/suspension_prepare.h、tests/suspension_prepare_reference.py、tests/test_native_suspension_prepare.py。原生悬架准备尚未完成整步/性能验收，本次不整合或发布；冻结SHA，保持原样。

## 审核结论

实验台24dbdc2/a8dff88/6704b9a/ebcc448与游戏8ce3d51/b70c8ce/ef6d377/722ecfd已经串联在同一main，不需要merge或cherry-pick。源码共用Simulation、VehicleCommand与Snapshot；入口切换关闭上一世界。游戏单次机械求解/120Hz、实验台设计两子步，直接执行器不经键盘辅助；LabRecords校验源码/模型/快照与信号完整性。

旧README将RADIO-02独立包称为当前版本，根试玩也启动旧包；本次改为当前源码游戏，独立旧包入口仍保留于archive。实验台说明补齐游戏积分配置已不同的事实。进度页只保留当前事实，原页面完整归档；历史失败与未验收项不删除。pytest限定tests，Ruff补排除旧工程/构建/日志/第三方目录；不改车辆方程、驾驶参数或既有证据。

相邻VI-v1为7dcf30a，gr86-physics为8deb721，simulation-fidelity为0944541，各自历史/辅助施工线不自动合入。当前8个提交是本次两方向成果来源。

## 验证及发布

隔离快照从git archive 722ecfd生成，使用主项目.venv重新编译全部4个原生扩展，不复制本地pyd；实际模块来源均在快照src，src/tests/tools/setup.py与722ecfd无差异。本次README/入口/验证配置另同步核对。新证据归档于[INTEGRATE-20261015](../evidence/INTEGRATE-20261015/README.md)，完整本地命令日志在logs/integration-20261015。

在隔离目录，使用主项目.venv的Python：

```text
setup.py build_ext --inplace --force --build-temp builds/integration-native-temp
tools/validate.py T1 --area lab --area research --tests tests/test_core.py tests/test_game_steering.py tests/test_driving_modes.py tests/test_driving_mode_ui.py tests/test_world_substeps.py tests/test_session_clock.py tests/test_session_process.py tests/test_snapshot_wire.py tests/test_keyboard_steering.py tests/test_npc_physics.py tests/test_vehicle_batch.py tests/test_impact_events.py tests/test_ui.py --output <主目录>/logs/integration-20261015/T1 --timeout 240
tools/lab_lifecycle_check.py --output <主目录>/logs/integration-20261015/lifecycle
tools/lab_menu_check.py --height 1080 --output <主目录>/logs/integration-20261015/menu-1080
```

结果：4模块严格浮点重编通过；130项pytest（193.57秒）、Ruff、三种子各1200拍通过。两轮往返世界和控件全部释放；五类下拉/24行真实鼠标/每类120帧悬停通过，已查看游戏菜单及实验台工况截图。根Ruff发现943文件，排除旧工程/构建/日志/第三方；原进度文本完整保留，6个保护文件SHA保持。

辅助隔离脚本最初遇Git元数据和Windows文本编码/换行问题，产品测试尚未运行；修正后正式T1一次完整通过。没有重跑T2/T3/长性能采样，没有删除历史包、证据或旧工程。

本次新增提交只含文档/收据、启动器历史标记、根试玩接线与Ruff发现范围；连同既有8个提交发布至origin/main。提交SHA由Git记录提供，推送后核对HEAD与远端main一致、ahead/behind为0/0；主工作区仍只保留上述6个原悬架未提交文件，不声称工作区干净。

复用有效游戏648拍直接命令SHA、1200拍交通SHA、五车型30工况及正式声音120秒前台记录，不重复性能长测。游戏人工已通过且接受偶发绘制短停；实验台人工体验待确认；旧T2海岸共同求解失败、严格零长帧fail、T3/长期Gate保持，不提升阶段结论。

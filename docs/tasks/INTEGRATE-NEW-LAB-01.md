# INTEGRATE-NEW-LAB-01 真实新版试验台与已验收游戏合并

- 状态：done（真实新版合并与相关验收完成；试验台计算性能/完整物理与人工Gate另列）。
- 用户2026-10-15指出刚才画面像旧版慢动作，要求找到准确新版；原始授权为检查游戏/试验台两个方向、合并并提交推送。
- 纠正：上轮6ca4cb4仅发布主目录8个游戏/初始实验台提交，遗漏了仿真工作树的25个提交。simulation-fidelity不是历史版本，主目录README/进度对它的归类错误，本次明确修正，不把先前“已合并”当全部完成。
- 真实来源：游戏main/722ecfd（生产ef6d377，已验收）；试验台codex/simulation-fidelity/0944541，实际路径C:/Users/15120/.codex/worktrees/simulation-fidelity/CoastalDrive，最近提交2026-10-15 14:25。该树干净，最新UI含参数F1数学排版、工程分析/标定、簧下质量/非线性部件及独立双精度SDK。
- 唯一主目录仍为B:/AI agent/暑期计算机程序设计/CoastalDrive。本轮悬架准备先保存独立检查点，不覆盖任何成果，然后正常三方合并25个提交；保留游戏120Hz单机械求解和已验收输入，实验台保留离线/两子步/新工程开关及双精度隔离。

## 验收

1. Git来源、提交范围、冲突逐项核对；修正当前说明，归档旧误判。
2. main重编5个原生扩展，恢复最新试验台归档双精度SDK，实际检查32/64位入口；不安装到共享环境。
3. 最新游戏入口短验收；最新实验台F1数学参数/工程导入/真实试验与完整复算、世界切换通过。已有同源有效节点复用，新增交集相关T1，T2/T3/完整能量/人工仍独立记录。
4. 最新试验台普通/双精度/预览明确命名，根试玩固定新版游戏；旧simulation整车实时诊断不充当新版产品入口。
5. 本地提交并推送main，核对远端一致；原仿真工作树保持不改动，旧数据/证据/未闭合物理结论不回写。

## 完成与验证

真正合并来源为主线65bcbe3和仿真线0944541，共同基线ebcc448，后者25个提交。仅两个显式冲突：当前进度改为准确来源并存档仿真原记录；Vehicle.snapshot同时保留主线active/generation/signal/hazards参数和新版reference_pose。另修复参考车型启用回正而正常NPC已关闭弹性轮轴的适配冲突；玩家机制保持，简化NPC显式关闭完整模型专属回正/压缩弹簧/曲线。游戏9个核心输入/时钟/交通/UI文件与65bcbe3逐字相同。

5个原生扩展从当前源码force编译；隔离SDK从23.47MiB归档及成员SHA恢复，实际64位/Bullet285；普通共享环境仍32位/Bullet284。原仿真树0944541保持干净不改动。

相关收据见[真实合并证据](../evidence/INTEGRATE-NEW-LAB-01/README.md)，完整日志在logs/new-lab-merge：

- 普通游戏T1：13个相关模块初114通过/5个交集失败；NPC适配和测试旧数值布局修复后，完整3交集模块37项/Ruff/三种子通过，原有效覆盖复用。旧52次完整原生结果仍按原布局逐字节核对，原二进制夹具未改，生产数值包仍拒绝错误布局。
- 双精度实验台T1：`run_sim_double.py tools/validate.py T1 --area lab --area research --tests tests/test_parameter_help.py tests/test_tire_reference_load.py tests/test_tire_calibration.py tests/test_tire_aligning.py tests/test_suspension_bench.py tests/test_suspension_preload.py tests/test_suspension_motion.py tests/test_suspension_damper.py tests/test_suspension_work.py tests/test_vehicle_unsprung.py tests/test_snapshot_wire.py --output logs/new-lab-merge/T1-lab-double --timeout 600`，128 passed/94.94s、Ruff与三种子各1200拍通过。
- 1080p参数真实鼠标/F1/焦点、138项说明/边界通过，已查看公式与当前/待编辑数据截图；GUI工具旧“.0”格式和标题预期失败保留并修正，没有改产品布局/降低门槛。`tools/lab_lifecycle_check.py`两轮往返世界/控件/任务全部释放。
- 当前游戏正式声音/18NPC/hills/45秒有效前台：120.002Hz、83.831绘制FPS、落后P95/峰17.053/46.537ms，930.317m，0丢时/碰撞/>50ms绘制帧，short Gate true。首30秒只到560.309m，唯一未达项为原600m行程；原报告fail保留，改用默认45秒补足，不改阈值。
- `run_sim_double.py tools/performance/benchmark_lab_compute.py --output logs/new-lab-merge/compute-budget`，同一独立轮心预览0.2模拟秒/24拍，直接5.460s、离屏GUI6.030s（物理/快照5.569s），初始化28.8s，全部快照/信号/命令一致。纯计算约27倍于仿真时间，主要成本是单拍约0.23s的共同求解；6ms界面预算与回放倍率不是主要限速。当前真实实验台计算性能仍需优化，不虚称完成。

本次T2/T3未完成，原main T2因用户纠正版本而中断；完整有限姿态能量、K&C/实测、人工体验和长期Gate保持原始边界。合并不会因SDK双精度或相关T1通过而关闭这些项。

提交为正常双父merge，保留25个提交祖先；最终提交SHA/推送后HEAD与origin/main一致性以Git记录和本地发布收据为准。

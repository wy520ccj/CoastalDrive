# LAB-BUGFIX-02 提示、布局与全流程排障

2026-10-17；main/bd50d27起点，单条施工线。性能优化暂缓，未改物理求解/阈值/默认硬件或游戏操控。

## 证据

- [分区布局稿](layout.svg)：车型与工况、车辆说明与播放控制、结果操作与图表分别留空间。
- [中文错误条](error-1280.png)：22wd保留原值，明确“时长”字段并聚焦；错误在最上层且不输出Python英文。
- [1080p完成实体凸起制动](main-1080p.png)：30km/h、0.6s制动起始、完整工程模型；停止距离显示4.02m，计时非性能验收。无A时曲线为B/橙色。
- [4:3主界面](main-4x3.png)：1024×768信箱式布局完整显示，没有按16:9裁掉控件。
- [最长参数说明](help-1080p.png)：内容有裁切滚动区域；正文/公式/来源/底部说明分离。
- [旧方法复现](baseline-reproduction.json)：隔离bd50d27 UI及文件方法，沿用当前导入backend，仅证明所列方法问题，非旧全模型重放。

完整渲染在`logs/lab-bugfix-02/{workflow-double,layout-4x3,layout-1080p,ride-braking-30}`，包含主界面、高级、信号、工程指标、F1首尾和记录菜单；代表图片由原始渲染直接复制，无后处理。

## 自动检查

均使用项目`.venv/Scripts/python.exe`；Double加`tools/physics/run_sim_double.py`包装，不覆盖普通SDK。

| 检查 | 命令/路径 | 结果 |
|---|---|---|
| 普通初批T0 | `tools/validate.py T0 --tests tests/test_lab_ui.py tests/test_lab_inputs.py tests/test_lab_records.py tests/test_vehicle_parameters.py --output logs/validation/LAB-BUGFIX-02-T0` | 101项/Ruff通过 |
| 普通全部lab及参数/IO/台架 | `tools/validate.py T0 --tests <rg --files tests -g test_lab*.py返回的29文件> tests/test_vehicle_parameters.py tests/test_physics_config_io.py tests/test_suspension_bench.py --output logs/validation/LAB-BUGFIX-02-all-lab-normal --timeout 300` | 908项/Ruff通过；5条float16旧参考范数overflow warning保留 |
| Double T1 | `tools/physics/run_sim_double.py tools/validate.py T1 --area lab --tests tests/test_vehicle_parameters.py tests/test_physics_config_io.py tests/test_lab_ride.py tests/test_lab_ride_braking.py --output logs/validation/LAB-BUGFIX-02-T1-double-final --timeout 300` | 164项/Ruff及三种子各1200步通过 |
| 最终Double T0 | `tools/physics/run_sim_double.py tools/validate.py T0 --tests tests/test_lab_inputs.py tests/test_lab_ui.py tests/test_lab_records.py tests/test_physics_config_io.py tests/test_vehicle_parameters.py --output logs/validation/LAB-BUGFIX-02-T0-final --timeout 300` | 106项/Ruff通过，覆盖最后小幅UI错误处理变化；不冒充重跑T1 |
| Double全流程/138说明 | `tools/physics/run_sim_double.py tools/lab_workflow_check.py --output <新目录> --full` | 5车型入口、10类工况、138字段、实际记录导出/载入/回放/单帧和A操作通过 |
| 比例与实际默认凸起制动 | 同工具`--width 1024 --height 768`、`--width 1920 --height 1080`；后者另加`--maneuver ride_braking` | 3种分辨率实际渲染并目视检查；30km/h实体凸起制动通过 |

首次Double T1原日志`logs/validation/LAB-BUGFIX-02-T1-double/pytest.log`为163通过/1失败，导出说明表缺字段；seed按fail-fast为not_run。修复3项说明与过期固定字段数量测试后，新目录164项及seed通过。代表JSON摘要保存在本目录。

全流程前8类工况是12拍短检查，5车型是6拍入口，不是完整操稳验收；18km/h轮跳360拍、18km/h制动141拍，另按实际默认30km/h跑实体制动并保存图片。自动流程不替代用户体验，也没有T2/T3或性能结论。

用户旧窗口结果已通过UI单独导出到用户数据目录，未复制进仓库。新版窗口只读取其已有快照，不宣称旧记录能在修改后的源码下确定性重算。

恢复该记录时，最后补正模型说明为“已保存试验模型”和载入/清A提示，不把工程记录误称默认设计模型或仍要求导入；`logs/validation/LAB-BUGFIX-02-loaded-notice`完整UI模块16项与Ruff通过。其余物理、IO、回放实现未变，复用前述范围的检查。

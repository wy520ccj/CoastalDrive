# 连续机械输入装配与原生交通布局 r6

2026-10-12，主目录main，基线 `c299620`。完整机械输入准备已接入原生入口，困难高速慢动作仍未关闭。当前是可试玩检查点，**实时120Hz、整体流畅、T2/T3与人工Gate未通过或待办**。仅本地保存，不推送。

## 改造

`drivetrain_prepare.h` 一次完成四轮轴、八/九维传动约束、实体输出/前/后轴惯量消元、发动机阻尼、转向反力和自由广义速度装配，替代原Python生成器/闭包及分散调用。直接产出原共同求解的只读系数，不新增世界或积分器。有限几何、共同20/30轮、精度、两次机械/世界子步、120Hz、原冲量顺序及全部遥测保持；保留原运算次序及Python3.14补偿求和，严格浮点构建。

扩大回归发现正常前驱/四驱参考车确有启动故障：原生交通关闭完整传动后，配置仍按旧后驱对照分支拒绝非后驱。新增明确的 `native_tire_forces` 资格，仅原生交通构造启用，保留完整轮端互斥和旧对照限制；驱动和发动机制动按原前/后份额分配。玩家和困难NPC继续完整传动，没有把非后驱车辆改为后驱。

三份机械生命周期测试要求NPC提供实体轴、限滑热和完整轮端状态，现明确选择困难交通模型，仍覆盖两套完整机械参数和三种布局，原断言不降低。正常原生模型另外检查真实Bullet轮驱动/制动、布局、回收和完整玩家边界。

## 数值与性能

- 24种轴/轮端/布局/下游转子组合各32输入：系数、自由状态、单位基及初态的惯量响应/转子动量逐float位型一致；含八维旧机制、九维实体轴、空挡、倒挡及惯量/维数错误边界。
- 13车/无限坡道/GR86/seed23/9工作进程，预热120拍、采样480拍，ABBA四次和最终源码/DLL第五次，完整Snapshot SHA逐拍相同。
- ABBA完整步均值 **12.483253→12.305229ms（−1.426%）**，仍超过8.333ms预算。最终独立确认11.507220ms/P95 14.380495ms，只作当前结果，不跨负载拼接收益。
- 冻结26份真实完整数值子步，各20轮、520结果：旧1.250030→新1.194189ms（−4.467%），两者均与原结果数值包逐字节一致。此为无IPC完整车辆子步，不是完整世界或120Hz验收。
- **有效前台30秒短对照**，1080p坡道/GR86/12完整NPC/seed23/9工作进程：旧64.975129Hz物理、71.771656绘制FPS、丢时12.425秒；新70.499479Hz、75.061952FPS、丢时11.125秒，均零玩家碰撞。窗口及权威/工作源码来源有效，两次均退出1，原因是性能Gate失败。只有一对，不认定稳定整体收益。
- 主进程13车和工作进程9车profile分开执行，只用于诊断。静态几何读取、控制/观测/完整快照及通信等待仍占据串行时间；没有改进程数、亲和性、优先级或关闭用户应用。
- 本版没有重测正常60秒前台；r5约120Hz及两次>50ms长帧的有效记录独立保留，不能移作本版已通过。

## 验证与失败记录

初始T0 **379通过**；Ruff发现两处新测试格式问题并修复。扩大检查 **398通过/9失败**，冻结c299620源码、原DLL和原测试实际复现同9失败（另6通过、19未选）。后续T1 **61通过/9失败**：只改交通输入仍不能切换模型，模型由会话输入选择。明确完整交通模型后，相关18项/Ruff/三种子各1200拍通过；最后装配25项边界/Ruff通过。未改范围的379/398/61结果按节点复用，失败项以修复后的检查为准，未重复长阶段验证。

较早T1重复使用 `--tests`，实际只选中最后SessionProcess文件，5项及三种子通过，**不算所请求的全部模块通过**；其余模块随后以单个明确列表实际执行。第一基线复现缺tools路径而收集失败，修正后才复现9失败；第一旧前台缺资源路径而未采样，排除。隔离基线仅把 `paths.resource_root` 指向原工作目录资源，物理代码/旧DLL不改。组合profile参数被工具拒绝的记录也保留。完整失败清单见receipt和原日志，不将非零退出改写为通过。

## 包与下一步

r6四原生DLL与最终src SHA一致。仓库外正常/困难真实会话启动、海岸8车120拍、离屏及各20次重开通过，截图已查看；前驱/四驱参考车各自正常模式8车120拍也通过。启动和离屏不代替手感/性能验收。

[正常入口](../../../../launchers/physics-native-traffic-game.cmd) / [困难入口](../../../../launchers/physics-native-traffic-simulation.cmd) 已指r6。公开0.8.3和根试玩入口保持独立。下一继续主世界读取、完整轮端观测/快照和完整车辆原生边界；困难70.5Hz仍有真实慢动作，正常长帧原因、人工驾驶和声音待确认。

```powershell
.venv/Scripts/python.exe tools/performance/benchmark_physics.py --output <新目录> --workers 9 --traffic 12 --mode simulation --traffic-input-mode game --track endless --shape hills --driver endurance --seed 23 --warmup 120 --steps 480 --capture-hashes
.venv/Scripts/python.exe tools/performance/benchmark_vehicle_solver.py --fixture docs/evidence/PHYS-PERF-01/structural-20261009/native-input-fixture --output <新目录> --warmup 4 --repeats 20
.venv/Scripts/python.exe tools/performance/benchmark_runtime.py --output <新目录> --seconds 30 --track endless --shape hills --vehicle-design gr86-2022-premium-6mt --driving-mode simulation --traffic-count 12 --independent-clock
.venv/Scripts/python.exe tools/validate.py T1 --tests tests/test_drivetrain_prepare.py tests/test_tire_drivetrain.py tests/test_continuous_solver.py tests/test_driveline_inertia.py tests/test_input_shaft.py tests/test_differential_lifecycle.py tests/test_drive_layout_lifecycle.py tests/test_npc_physics.py --output <新目录>
.venv/Scripts/python.exe setup.py build_apps --build-base <新目录>
```

原报告在 `logs/performance/whole-step-r1/`，归档仅省略逐次GC数组并保存原路径/SHA。未执行T2/T3，未取得人工验收结论。

# 连续原生车辆求解 r1：实际实现与运行收据

2026-10-09，主目录main，基线`d3d056904276d425c747a10b130192aea785c7a9`。本阶段已整合生产源码并编译两个实际C扩展；完整实时任务仍in_progress。没有新性能工具、车型简化、NPC分级、物理降频或产品包发布。

## 已执行的连续路径

`tire_drivetrain.advance_drivetrain → mechanical_kernels.joint_solve → joint_iterate`：原20轮共同迭代、内部30轮机械端口分区、四轮本构求根、制动/接触/六维悬架联合修正以及真实末姿态有限几何查询连续在C中执行。真实26输入的独立profile为26次joint_solve，旧shared/solve_wheel/contact_system各0次；专项测试将旧Python求解/几何/残差入口换成抛异常函数，52次完整推进仍全部通过。

每进程按配置保留数值工作区，每次入口完整重置暖分区和几何memo；不会把上一车/上一拍机械状态当成当前暖解。几何使用当前完整只读SurfacePacket、TrianglePacket和候选覆盖盒，覆盖盒外直接查完整同世界数据；几何换版更换capsule。两个C扩展用数值函数指针连接，不回调Python接触函数。退化单纯形使用实际实现的小型Jacobi SVD，保留良态双列补偿叉积。

已接管真实轴系、顺应性轮胎及WorldSurface/FrozenWorldSurface的有限Box/Plane/三角面组合。含需要原Bullet凸体扫掠的未知静态形状、其他车辆机制入口先明确选择原完整路径，不能丢弃候选。收敛异常直接报告，不通过失败后重跑Python掩盖。真实fixture的182组几何无未支持形状，9/13车原序提交到唯一Bullet世界、每拍两个真实机械/Bullet子步未改。

仍有Python输入/系数/初始观测准备与最终机械状态、能量账装配；当前原生区仍持GIL，以沿用底层错误处理。进程数仍为9，尚未实现GIL释放/原生线程池/批量多车入口。不能称为整个车辆管线已全原生化。

## 同输入与完整步收益

正式顺序A1→B1→B2→A2，A冻结源码/旧DLL在`logs/performance/native-r1/oracle`，B在`candidate`。单车每次8轮预热、120轮×26输入计时；完整步每次240拍预热、600拍测量，GR86、玩家simulation/NPC game、EnduranceDriver、无限坡道、种子23、9数值进程。不并行运行测试/构建，onmyoji、wallpaper32已按固定负载授权停止；系统调度/调频仍有波动。

| 范围 | 旧均值ms | 原生均值ms | 完整耗时下降 |
|---|---:|---:|---:|
| 实际完整单车数值子步，无IPC | 1.8322 | 1.4017 | 23.50% |
| 9车完整120Hz物理步 | 10.8650 | 10.3478 | 4.76% |
| 13车完整120Hz物理步 | 15.8127 | 13.5222 | 14.49% |

单车四次每次3120完整结果字节相同；每个9/13车ABBA系列的600拍完整Snapshot SHA逐拍相同。最终生产边界修复后另验：单车3120次字节相同/1.3874ms；9车600拍10.1226ms/P95 12.2624ms/max16.2795ms；13车600拍13.2768ms/P95 16.1885ms/max20.7095ms，快照仍与各A1全部相同。这些是生产确认，不与最慢旧样本拼接宣称更高收益。**9/13车均未达到8.333ms预算。**

## 实际前台与回摆

以下为1920×1080、30秒短测、已有smoke关闭声音、独立时钟、9进程、highway-driver。窗口有效性及子进程来源均已核对；控制器与无窗口EnduranceDriver不同，不能混合比较。

| 有效窗口 | 实际物理Hz | 绘制FPS | 采样丢时s | 绘制P95 ms |
|---|---:|---:|---:|---:|
| 13车旧A2 | 44.63 | 83.64 | 16.91 | 见原收据 |
| 13车原生B | 48.06 | 74.90 | 16.15 | 20.55 |
| 9车旧A | 63.13 | 116.14 | 12.78 | 见原收据 |
| 9车原生B2 | 64.96 | 117.73 | 12.37 | 12.66 |
| 主目录最终13车 | 48.60 | 74.86 | 16.07 | 20.47 |

不是前台ABBA或最终Gate；13车绘制FPS下降不隐藏。上述有效窗口没有>50ms绘制帧，但仍严重物理丢时和慢动作。最初`window-13-A`窗口无效；`window-9-B`与约0.35秒测试重叠，均剔除、保留原记录，再测B2。全部有效窗口玩家发布/插值道路y没有倒退；最终13车玩家相对相机y单帧变化−112.49至64.15mm，回摆未关闭。不是完整三维视觉/所有NPC人工验收。

## 验证与保留的失败

- 原力门槛0.001N、制动1e-9Nm、法向1e-10N、几何共轭冲量1e-12及局部轮力0.0001N、20/30轮保持。硬件、方程、120Hz、两个子步不改。
- 连续内核16项：52真实推进/工作区重置/几何换版；独立SVD维数1/2/3、条件数1/1e4/1e8、秩亏最小范数；实际有限Box边与倾斜胎冠轴端独立几何核对通过。
- T1首轮450通过/1失败：保存WorldSurface没有static_shapes。修为迭代前统一读取唯一真实世界；失败节点及连续内核17项、Ruff、0/17/23各1200拍通过。原其余450项按未改范围复用，不累计重测数量。原有高载护栏能量残差<3e-9、共同反力/真实Bullet提交、FWD/AWD/空挡/生命周期、两子步、接触缓存专项保持通过；未改这些测试阈值。
- 初轮真实装配梯度变量遮蔽、T0覆盖盒外缺完整几何及直接单车入口无缓存，均修真实实现，原失败文件保留。最终生产编译无警告。
- T2/T3/两模式人工驾驶/长前台Gate本轮not_run或pending；历史默认车型收敛失败未关闭。公开0.8.3/既有候选包未重建。

原始测量、模块/DLL SHA、600拍序列摘要、表现统计与验证状态见[receipt.json](receipt.json)；此目录保留各原report及失败/T1日志，完整表现序列和独立源码/DLL仍在本地`logs/performance/native-r1`。实现范围仅数值模块、构建依赖及专项测试；需要撤销时revert本次实现提交并重新`build_ext --inplace`，不要恢复其他工作区成果或只换Python不换DLL。

复现命令（替换输出目录；旧/新均使用同fixture、参数）：

```powershell
.venv/Scripts/python.exe setup.py build_ext --inplace
.venv/Scripts/python.exe tools/performance/benchmark_vehicle_solver.py --fixture docs/evidence/PHYS-PERF-01/structural-20261009/native-input-fixture --source src --warmup 8 --repeats 120 --output logs/performance/native-r1/recheck-single
.venv/Scripts/python.exe tools/performance/benchmark_physics.py --source src --workers 9 --traffic 12 --mode simulation --traffic-input-mode game --track endless --shape hills --driver endurance --seed 23 --warmup 240 --steps 600 --capture-hashes --output logs/performance/native-r1/recheck-13
.venv/Scripts/python.exe tools/performance/trace_presentation.py --output logs/performance/native-r1/recheck-window-13 --track endless --shape hills --seconds 30 --vehicle-design gr86-2022-premium-6mt --driving-mode simulation --independent-clock --physics-workers 9 --traffic-count 12
```

9车分别把traffic/traffic-count改为8；对照source为冻结oracle或candidate。完整步/前台命令因实时预算失败返回1，不能改判成功。下一工程边界是尚在Python的每车准备/装配与批量数值入口；已有结果只证明连续共同求解应保留，不能把所有剩余等待都归因IPC。

# 真实物理深度优化：第一检查点

2026-10-09，主目录 `CoastalDrive/main`，施工基线 `9bcad620451cda6c6892f34bb0a4fa1596c84452`，开始时工作区干净。用户本次恢复优化。**本检查点有实际实现和收益，持续实时120Hz目标未通过。** 未推送、未替换公开试玩包；后续几何换版实验在 logs 中隔离。

## 审计与测量口径

实际链路为 `Session.tick → Simulation.step → advance_world → Vehicle.physics_stages → TireAdvanceInput/DrivetrainInput → Tires.advance_stages → advance_drivetrain → 原序冲量提交 → Bullet.doPhysics → 接触观测/after_step → Snapshot`。控制和交通计划按原频率执行；每个120Hz拍包含两个机械/Bullet子步，第二子步必须读取第一个Bullet步完成后的真实姿态，不能将两步合并成脱离世界的一次任务。

数值进程先准备悬架有限接触，再装配轮端/传动系、求共同末状态；末几何依次进入 `finite_contact_system/cylinder_contact_system → WorldSurface.relative_entry → cached_surface_entry/有限网格或Box求交`。薄道路、边角及原Hull扫掠仍走真实几何。`mechanical_kernels.c` 已承载共享机械状态、局部轮力及残差；整个共同迭代和大量对象装配仍在Python。数值包只交换当前状态，进程没有Bullet世界。所有车辆读完本子步后才按原序提交，世界随后推进，两个子步都观察碰撞。

硬件为 i9-13900HX，24物理核/32逻辑处理器；Win32实际拓扑为8个带SMT的性能核和16个效率核，见 [拓扑](cpu-topology.json)。使用仓库Python、GR86工程硬件、种子17、玩家加8车。主要基准预热240拍，再测1200拍；确定性序列覆盖加速、小幅转向和制动。每次计时含 `Simulation.step + 完整Snapshot`，不含快照存档；完整模拟时间固定10秒。物理时间与窗口墙钟另计。分位数采用排序后线性插值。

`benchmark_physics.py --trace` 分别计量生成器实际读取、收集结果和恢复提交，不能量生成器对象的创建。阶段值是包含子调用的耗时，不能相加；`wait_receive_decode` 包含尚未完成的远程计算、调度及解码，不等于IPC成本。profile单独用于定位，不用于性能结论。Windows进程CPU时间在单次请求上有约15.625ms量化，CPU只看整段聚合估计。

原窗口工具的 `--source` 曾被耐久工具的路径插入及Windows spawn覆盖。此次已修复，正式窗口记录同时保存并核对主进程和每个数值进程实际模块路径。修复前的窗口样本保留于logs，排除旧/新对照。

## 瓶颈与实际迭代

初次分段诊断14.48ms/拍，收集结果约8.25ms/拍，真实静态几何读取约0.83ms，两个Bullet步合计约1.08ms，完整快照约0.66ms；编码约0.47ms、解码约0.80ms，后两者已包含在上级提交/收集阶段。车辆观测、控制、对象恢复和其他世界工作还占串行时间。

实际子进程profile：2160次完整求解累计约8.31s，其中共同求解约5.40s，末接触几何约2.11s；候选筛选/构造约1.02s、Python三角索引遍历约0.62s、重复几何构造约0.28s。单轮原生求根约0.33s，共享机械原生求根约0.29s。嵌套值不累加，profile时长不当作吞吐。

隔离原生计数内核保持原公式和分支：2160次推进的共同外迭代为4–10轮，5轮占1565次；63816次共享机械求根为1–6轮，仅223次进入解析Newton。滚动轮力外括根为1–6轮，横向括根为1–4轮。样本是预热后加速窗口，不代表所有静摩擦/极端工况，后者由实际T1另验证。原迭代上限和残差门槛均未改。

串行/2/4/6/8/9进程的首次可比基线平均为43.64/29.55/19.91/16.80/15.33/14.11ms。增加进程的收益递减；9进程在该场景最好，但仍远慢于8.333ms预算。

## 保留的实现

1. `coastal_map.project/on_road` 的完整有序折线遍历进入原生内核。道路几何、原距离算术、边界比较、最近点并列顺序保持；不是近邻近似或材料缓存。6656个随机点及边界相邻浮点点与独立原源码零差异。
2. `TriangleSupport.window` 在原生内核筛出原顺序三角面，复用它们已有的顶点、法线和包围盒。世界查询及越界重查的窗口范围保持，未扩大预取、未减少精确求交。窗口持有自己的原面引用，支持空窗口、嵌套、源对象生命周期和序列化恢复。
3. 新完整物理基准和原窗口基准修复，明确记录实际模拟tick、墙钟、丢时、真实加载源码、CPU估计及尾部耗时。相关生成器计时专项已通过。

独立道路ABBA约5.06%，窗口ABBA约4.22%；这些阶段比例不能相加。最终同条件总ABBA如下，每行两次1200拍的统计量均值，源哈希前后未变：

| 项目 | 基线 | 保留实现 |
|---|---:|---:|
| 完整物理平均 ms/拍 | 14.022 | 12.880 |
| P95 ms | 17.641 | 16.274 |
| P99 ms | 20.864 | 19.265 |
| 两次最坏值的均值 ms | 24.355 | 23.040 |
| 真实完成频率 Hz | 71.315 | 77.643 |
| 完成10秒模拟所需计算时间 s | 16.827 | 15.456 |
| CPU平均使用核数，粗粒度估计 | 3.319 | 3.217 |

**整体平均下降8.15%，仍不满足实时预算。** 原始四次报告在 [measurements](measurements)，摘要见 [final-abba-summary.json](final-abba-summary.json)。

正式1080p海岸8车30秒前台短测、约27秒采样、主/子源码核对和非最小化检查均成立：旧版实际物理59.15Hz，新正常61.47Hz、新困难仿真62.15Hz；对应绘制125.17/126.10/127.47FPS，采样丢时13.67/13.17/13.05秒。**三个实时Gate都失败。** 这些是自动前台测量，声音按现有smoke工具关闭，不能代表人工驾驶和完整有声产品体验。

## 正确性与撤销

海岸正常、单车困难、海岸困难、弯坡正常和弯坡困难各1200拍完整快照载荷SHA序列与冻结基线完全相同；仅规范化独立会话的contact_epoch，连带事件epoch同步规范化，其他字段包括接触、残差、能量账和事件不删减。见 [轨迹](trajectory-equivalence.json)、[场景对照](scenario-equivalence.json)。

最终相关T1：500项pytest、Ruff、0/17/23各1200拍启动通过；额外生成器/分位数T0两项通过。道路T0、窗口T0及实际重开、资源释放、碰撞/子步观测、坡停、离地与再接地、传动及轮胎机械账包含在记录中。未把不同验证轮的数量累计成新的覆盖数。

撤销：接触数据包ABBA仅约0.9%；只绑P核更慢；扩大预取/共享候选无足够收益；同源码Cython两版15.98/15.66ms更慢；主进程解一车无前台收益；固定车辆归属ABBA约1.9%，不值得增加协议和状态。失败、排序检查未跑pytest、错误源码守卫及未完成构建均保留，见 [receipt.json](receipt.json) 与其中本机logs路径。Cython仅在仓库venv用于隔离实验，未加入生产构建/项目依赖。

## 复现与后续

先运行 `.venv/Scripts/python.exe setup.py build_ext --inplace`，再运行：

```powershell
.\.venv\Scripts\python.exe tools/performance/benchmark_physics.py --workers 9 --traffic 8 --warmup 240 --steps 1200 --output <新目录>
.\.venv\Scripts\python.exe tools/performance/benchmark_physics.py --workers 9 --traffic 8 --mode simulation --track endless --shape hills --warmup 240 --steps 1200 --capture-hashes --output <新目录>
.\.venv\Scripts\python.exe tools/performance/benchmark_runtime.py --seconds 30 --track coastal --vehicle-design gr86-2022-premium-6mt --driving-mode game --independent-clock --physics-workers 9 --output <新目录>
```

完整T1命令在对应validation/summary.json；`--source` 可使用本机冻结目录，主目录新旧版本不能混装原生模块。JSON `passed` 表示采样执行完成，实时预算及整个任务的结论另列，不能由命令退出0推导。

当前仍需降低连续共同求解/接触路径和主世界串行成本。双模式长弯坡样本出现约158/172ms峰值，下一以实际几何换版事件关联计时，验证未变网格的跨版本只读复用；实验尚未整合。T2/T3和人工驾驶状态见任务包，实时目标保持未完成。

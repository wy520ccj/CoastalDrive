# 联合传动计算开销诊断 r5

当前r5冻结源、游戏单车平面原生240步落定+120步起步，真实120Hz、两个轮胎子步。命令：`.venv/Scripts/python.exe -m cProfile -o docs/evidence/PHYS-DRIVE-01/native-profile-r5.pstats tools/physics/drivetrain_probe.py --output docs/evidence/PHYS-DRIVE-01/native-profile-r5 --modes game --cases launch --seconds 1`。

诊断已完成，原力残差门槛通过，280源前后与当前T1冻结清单相同。数据在[统计](native-profile-r5-summary.json)、原始pstats与native-profile-r5连续轨迹中。记录期间完整T1并行运行；cProfile有插桩开销，不能将本表当作正常运行帧耗时或可见窗口性能Gate。

| 函数 | 调用次数 | 插桩自身/累计秒 |
|---|---:|---:|
| advance_drivetrain | 720 | 0.207 / 12.832 |
| clutch_brake_plans | 2880 | 0.334 / 7.005 |
| _solve_three | 302400 | 1.138 / 5.468 |
| clutch_brake_state | 19276 | 0.361 / 1.203 |

clutch_brake_plans累计约占联合传动累计的54.6%。源码确认它每轮子步为全部活动模式计算三个逆矩阵列，每列重复计算同一余子式和行列式；它缓存本子步的列，不是跨步缓存。局部求解只需访问实际检查的候选。

下一数值工作应首先检验同一矩阵余子式复用，并在需要时检验候选逆列按需计算。不得舍弃活动模式、量化响应系数、改摩擦/容量/残差门槛或回写RPM。新旧矩阵列、端口独立台架、联合能量/动量、当前16条原生轨迹的逐tick实际状态需在同参数下对照；收益另用无插桩受控短测核对。当前完整T1源码保持冻结，本诊断没有实现上述修改。最终仍须真实前台窗口/实际帧耗时与人工驾驶。

## 独立表达式等价核对

[cofactor-reuse-audit-r5.py](cofactor-reuse-audit-r5.py)与[完整结果](cofactor-reuse-audit-r5.json)在证据目录独立运行，不修改src/tests/tools。固定种子构造400个正定响应，覆盖两种效率、全部锁止/滑动/静止行组合：9600矩阵、86400个double的网络字节序完全相同，SHA均为60cb602de8f41c269a9316c8b28111d15068983297f4487da4bebc532730f6b0。

同时核对402个响应、两种效率及四种零/非零容量，共3216组完整候选；只复用完全相等的行矩阵，候选模式、顺序、符号和全部逆列字节零差异。容量均非零、效率0.88时45个候选对应12个不同矩阵。复用范围仅本次调用，未量化系数或改变求解约束。局部纯函数交替计时仅作诊断，完整T1同时运行，不能据此报告整车加速或性能Gate通过。接入后仍需已有独立端口/联合守恒台架、当前原生轨迹及完整新版本验证。

[独立原生运行器](cofactor-native-audit-r5.py)仅在自己的进程中替换clutch_brake_plans函数绑定，合并余子式复用与本次调用内相同行矩阵复用；生产文件与后台T1没有改变。当前两模式12条柔性6s/4条刚性4s全部完成，共10560拍。与native-mode-control-r5/native-rigid-control-r5的每条解压JSONL字节完全相同，包含每拍输入及完整CarState；原力残差<0.001N和真换挡容量0的断言保持。原生运行前后280源哈希与对应r5基线完全相同，另记录实验算法/运行器SHA，避免把进程内原型误当作生产源码。

[原生对照回执](cofactor-native-audit-r5.json)状态completed_identical_native_traces，stdout/stderr原日志均保留。该结果证明当前16工况的数值等价，不代表完整T1/T2、全部工况或可见性能通过；未记录受控整车加速结论。当前完整T1终态后再决定接入次序，正式改动后须补独立台架与新版本完整验证。

[原生短测](cofactor-native-timing-r5.json)已完成：单车平面、240拍相同制动落定不计时、120拍全油门起步计时，两个模式各一次AB/一次BA。没有渲染或cProfile，完整T1同时运行；分别记录进程CPU时间和墙钟时间。游戏原版/原型平均CPU为2.59375/1.890625s，降低27.1084%；困难仿真2.65625/1.875s，降低29.4118%。每个模式四次终态SHA均一致，280生产源前后不变。这是指定单车短工况的成本证据，不能外推NPC密集场景或可见帧率。

[独立台架运行器](cofactor-port-audit-r5.py)在单独进程中为端口与联合轮胎替换同一矩阵复用函数，完整既有test_transmission_ports/test_tire_drivetrain **532项通过（3.59s）**。其独立区间求根、物理模式、虚功、反力、能量/动量及负对照保持原断言；[回执](cofactor-port-audit-r5.json)与JUnit保留280源稳定及两个实验脚本SHA。该隔离原型pytest不记作生产版本完整T0/T1/T2。

对应[最小补丁](matrix-reuse-proposed-r6.patch)已准备，git apply --check通过；[基线/补丁SHA](matrix-reuse-proposed-r6.json)状态prepared_not_applied。当前完整T1的1377项pytest及三种子启动已通过，弯坡仍运行，故磁盘源码继续冻结。补丁只改transmission_ports的逆列预计算：一次余子式、一次调用内按完全相同行复用；端口函数接口和候选检查顺序保持。

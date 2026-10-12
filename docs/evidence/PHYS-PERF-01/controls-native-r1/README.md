# 完整电子控制数值与重复原生Action清理 r8

2026-10-12，主目录main，基线 `334857e`。源码与独立r8包已更新，**慢动作/120Hz与整体流畅目标仍未实现**，不将当前功能块替代完整目标。仅本地保存，不推送。

## 实现

TCS驱动轮反馈、四轮液压/ABS、ESC横摆参考/制动力矩分配与完整冻结记录在原生代码连续计算。顺序、阈值、响应、上一完成步真值、字段/类型与浮点精度不变；ESC实际Panda向量几何保持原代码，避免坐标运算舍入改变。原生入口没有积分或施力，不维护另一套运动状态。

完整耦合车辆的原生弹簧/阻尼/切向力原已归零，却仍登记BulletVehicle Action并做逐轮射线/同步。现完整车只登记原真实刚体，保留完整机械求解、CCD、碰撞响应及原掩码；BulletVehicle只保留轮端硬件读数，原生力字段显式初始化为零。正常原生NPC和历史原生悬架仍登记Action。退役/回收/关闭通过直接车辆方法统一登记/移除，去掉完整车的重复零值设置；完整快照轮姿来自原机械转角/悬架。

依据：[Panda3D 1.10.16 World源码](https://raw.githubusercontent.com/panda3d/panda3d/v1.10.16/panda/src/bullet/bulletWorld.cxx)中Action登记与刚体登记分开，removeVehicle会同时移除刚体；因此生命周期同步改为按实际登记角色操作。[Bullet 2.84车辆源码](https://raw.githubusercontent.com/bulletphysics/bullet3/2.84/src/BulletDynamics/Vehicle/btRaycastVehicle.cpp)展示原生逐轮查询及力更新。Action清理的物理无损性以本项目逐拍对照和实际碰撞检查证明，不只凭源码推断。

## 数值与性能

- 24种控制开关/响应时间/连续参考/驱动布局，各80次，共1920次推进，旧Python冻结参考与新实现的全部字段类型/浮点位型一致；含倒行、离地、整型/浮点请求、零响应时间与历史反馈。原记录冻结及不可变性保持。
- 13車/GR86/无限坡道/12完整NPC/seed23/9工作进程，预热120、采样480：电子控制ABBA四次、Action原型及合并后四次，全部完整Snapshot SHA逐拍相同。
- 电子控制ABBA完整步13.761816→13.523333ms（−1.733%）。合并控制与Action的四次交替B/A/B/A完整步13.606358→13.157305ms（−3.302%）；这是另一组对照，不和前段拼接收益。仍超8.333ms预算。合并B1的构造力字段初始化与后段略有不同，只发生在计时外；各版完整快照相同，来源记录分别保存。
- 电子控制有效困难前台一对30秒：旧60.349467Hz/63.138153绘制FPS/丢时13.341667秒，新61.124457Hz/63.947489FPS/丢时13.216667秒。合并后的独立短样本62.987997Hz/65.537504FPS/丢时12.758333秒，不与较早旧样本拼接为稳定整体收益。所有窗口/权威和工作源码有效、玩家碰撞0；性能Gate都失败，退出1。

## 检查与未关闭项

现有电子控制T0 43通过。新增参考初Ruff格式/未用导入失败、pytest未跑；下一次24个新夹具因漏填WheelContactState字段失败，填齐实际9字段后24项通过。扩大电子T1 150通过/1旧正常NPC ABS同配置断言失败，原源码/DLL复现；改为分别核对正常原生与困难完整NPC的真实配置及记忆重置，两模式修复和三种子通过，原150项复用。

Action相关首T0 45通过/4失败：两个新关闭检查错误要求保留引用的世界连静态道路一起销毁；改为所有动态车身和Action释放。未登记轮端原生力字段尚未有原生推进，显式初始化零后原断言通过。另一个旧空中制动子步细化的单调距离断言，在原源码/DLL同样以 **.2999916116738177 < .25041580251126305** 失败，**未放宽/删除/宣称修复**。补充T1 20项/Ruff/三种子通过，包含实际双模式碰撞响应、回收、关闭、完整悬架/轮端、工作进程及会话进程。该既有细化失败仍阻止完整阶段验收。

0/23各30秒12NPC正常弯坡检查通过。r8四DLL与最终src SHA一致，仓库外双模式实际会话启动/海岸8车120拍/离屏各20次重开通过，截图已查看。正常前台60秒未重测，T2/T3和人工手感/流畅Gate未跑或待办；自动和离屏不能代替人工体验。

## 下一步与复现

继续主进程实际车身/轮端观测和完整快照装配，再处理完整车辆原生边界；当前约63Hz仍有真实慢动作。两个原试玩入口已指r8，公开0.8.3/根入口保持独立。

```powershell
.venv/Scripts/python.exe tools/validate.py T1 --tests tests/test_native_vehicle_controls.py tests/test_vehicle_brakes.py tests/test_vehicle_traction.py tests/test_vehicle_stability.py tests/test_vehicle_action.py tests/test_rotor_lifecycle.py tests/test_physics_workers.py tests/test_session_process.py --output <新目录>
.venv/Scripts/python.exe tools/performance/benchmark_physics.py --output <新目录> --workers 9 --traffic 12 --mode simulation --traffic-input-mode game --track endless --shape hills --driver endurance --seed 23 --warmup 120 --steps 480 --capture-hashes
.venv/Scripts/python.exe tools/performance/benchmark_runtime.py --output <新目录> --seconds 30 --track endless --shape hills --vehicle-design gr86-2022-premium-6mt --driving-mode simulation --traffic-count 12 --independent-clock
```

原报告在 `logs/performance/controls-native-r1/`。归档只省略逐次GC数组，保留原文件路径/SHA；隔离基线仅资源根目录改为原工作目录，物理代码/旧DLL不改。冻结参考在tests保留，按源码AST提取原三类控制运算，格式修复不改运算顺序。

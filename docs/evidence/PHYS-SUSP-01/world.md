# PHYS-SUSP-01：机械与真实世界子步对齐

2026-10-05，基线`dba1742`。两模式的SI悬架、轮胎和完整传动现在每完成一个机械子步，立即推进同一个Bullet世界，再从真实姿态查询下一子步。默认每个120Hz外拍含两个1/240s原生世界步；输入辅助、电子控制、执行器准备、撞击生命周期和快照仍每外拍结算一次。硬件、驾驶参数、原残差门槛保持。

`src/world_step.py`负责准备请求和依次推进世界，Vehicle负责当前姿态上的受力；没有第二个物理世界。Bullet每次推进清空持续力，调用方施加的整拍外力/力矩因此在后续子步恢复；悬架、轮胎和传动的功、损耗及冲量累加全拍，末状态保留最后施力子步。真实碰撞逐子步读取，第一子步发生、末子步已经结束的碰撞仍交给同一120Hz事件生命周期。

碰撞后真实姿态刷新引入一个挑战模式求解回归：轮荷突变使上一子步轮胎力落到非线性曲线下降支，阻尼牛顿法停在残差局部极小值。首轮SI滚动接触改用同一隐式接触方程在零滑移处的切线预测初值，然后求原完整曲线；后续共同迭代保留暖初值。没有异常后切换模型、裁剪轮荷或放宽误差。实际挑战工况修复后通过。

## 本轮证据

- T0-world-r1：13通过/1失败。旧预载断言把第二个真实世界子步的几何刷新也当作初始化；保留首子步初始化功严格为零的门槛，第二阶段按独立弹性势能差检查。r2修正节点通过。
- T0-world-r3：17通过/5失败，保留全部日志。首版旧源码审计实际被测试入口覆盖搜索路径，`world-impact-baseline.json`已明确标为无效旧版证据，原始失败不删除。修正审计先载入冻结Git模块并断言路径，`world-impact-baseline-r2.json`确认四项护栏失败在`dba1742`已有，挑战模式则是新增回归。
- r4仅工具重复导入导致Ruff失败，pytest未跑。修正导入和上述真实求解初值后，**r5全Ruff及317项定向T0通过，pytest6.96s**，包括原挑战碰撞门槛、两模式真实姿态推进、整拍外力、早期子步碰撞、原生悬架及完整传动机械账。未重跑T1/T2/T3。四项旧护栏失败保留为未收口事项；最终初值修复后没有重复跑它们，不把旧结果冒充最终结果。
- 原单侧工况两模式各360外拍/720原生步完成。独立Box内核/margin表面误差≤1.88e−8m，轮胎残差峰值≤9.62e−5N，局部悬架能量残差≤9.51e−14J；源码310份前后相同。真实翻覆保留。
- 关闭耦合两模式各120拍仍使用单次1/120s世界推进，与`6be5f54`已保存实际Git运行快照的既有字段逐字节相同，仅投影`suspension_state=None`；原缓存不重跑。海岸两模式各120外拍/240原生步短集成完成，原始快照保存。详见`world-boundaries-r1/summary.json`。
- `reference-v21/parameters.json`已真实导出两模式各240外拍/480原生步，完整91车辆/9输入字段，明确外拍与原生步长。成绩版本game-controls-v18/reference-v21。两组运行与参考表的生产源码哈希一致。

|模式|旧/新累计有符号几何刷新J|新累计正几何刷新J|旧/新最大轮荷N|
|---|---:|---:|---:|
|游戏|17.47722 / 23.16928|28.84206|8798.03 / 9311.10|
|仿真|0.51151 / 10.81059|18.28862|8466.65 / 8827.29|

本增量解决了第二机械子步读取旧姿态的问题，但该单侧翻覆工况的几何刷新功反而增大，不宣称整车能量闭合。下一项直接处理曲面/碰撞后的几何刷新与材料能量一致性，以及遗留护栏工况；有限胎宽/实车型、整组T1/T2/T3、性能和用户两模式体验仍未完成。

## 命令

```powershell
.venv/Scripts/python.exe tools/validate.py T0 --tests tests/test_impact_delivery.py::test_real_challenge_impact_failure_frame_is_delivered_once tests/test_world_substeps.py tests/test_suspension_native.py tests/test_tire_drivetrain.py --output docs/evidence/PHYS-SUSP-01/validation-T0-world-r5
.venv/Scripts/python.exe tools/physics/suspension_contact_probe.py --output docs/evidence/PHYS-SUSP-01/world-native-r1 --prior docs/evidence/PHYS-SUSP-01/joint-native-r2
.venv/Scripts/python.exe tools/physics/export_reference.py --output docs/evidence/PHYS-SUSP-01/reference-v21/parameters.json
.venv/Scripts/python.exe logs/physics/audit_world_baseline.py
.venv/Scripts/python.exe logs/physics/finish_world_increment.py
```

最后两项是本地一次性审计/收尾入口，不进入生产源码；证据JSON保留输入协议、实际源码路径、哈希与结果。本轮按用户“运行完这轮就提交推送”收尾；提交/远端事实以Git核对为准。[机器回执](world-receipt.json)。

原生推进依据：[Bullet 2.84 doPhysics的单步/清力逻辑](https://github.com/bulletphysics/bullet3/blob/2.84/src/BulletDynamics/Dynamics/btDiscreteDynamicsWorld.cpp)，[实际位移和旋转积分](https://github.com/bulletphysics/bullet3/blob/2.84/src/LinearMath/btTransformUtil.h)。上游源码仅用于核对时钟，结果以本机运行证据为准。

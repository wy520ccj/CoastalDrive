# PHYS-SUSP-01：真实圆角曲面的共轭悬架反力

2026-10-05，基线`cc345bb`。两模式SI悬架已把球形包络/Box内核加margin的真实末端交点、曲面割线法线接入现有法向/轮胎/完整传动共同末状态。每120Hz外拍仍两个真实1/240s世界步。本轮按用户要求收住验证并提交推送开发增量；整个任务继续。

## 实现

`src/suspension_geometry.py`按支撑几何职责集中既有球/Box求交内核，以及从唯一Bullet世界实际选中形状读取的不可变几何。查询层和机械末姿态共用这一内核，求解层不持有Bullet对象。

Box距离平方水平集为`q(c)=Σ(c_a−clamp(c_a,±h_a))²`。对两端球心按分量构造割线`N`，满足`q(c1)−q(c0)=N·(c1−c0)`。同分区直接化简平方差，跨分区保留完整差商。实际末姿态重新求包络交点，结合同一有限转动路径和`Δ(d*l)=mean(d)*Δl+mean(l)*Δd`，得到行程与功共轭线/角冲量。

真实曲面反力进入原20轮共同迭代，实际提交冲量及Snapshot的`force_gradients`直接来自最终求解系统；即时接触点/法线仍记录真实查询。末端无入射点或近掠不合既有资格时进入原自由轮方程，车身碰撞保留。Plane/原生网格继续上一增量切平面机制；有限胎宽、簧下刚体、动态支撑和跨多个形状的末端换接尚未接入。

## 本轮有效证据

- r1全Ruff及50项既有几何/包络/联合机械T0通过，pytest0.91s。r2只因新测试未使用导入Ruff失败，pytest未跑，原日志保留；删除导入后r3的22项新曲面几何/完整机械账、4项世界子步和1项原挑战碰撞通过，共27项，pytest0.60s。
- 最终r4原生状态/静载/预载及配置/成绩版本15项通过，pytest9.26s。合计92项有效定向T0，未重复其他已有效检查。独立末端由Rodrigues旋转后直接二分距离场求出；完整机械账沿用3e−9J、角动量1e−10Nms门槛。硬件、驾驶参数、轮胎0.001N残差及真实碰撞保持。
- `curved-native-r1`原单侧两模式各360外拍/720原生步完成，接点表面误差≤1.96e−8m、轮胎残差≤9.35e−5N、局部悬架能量残差≤7.09e−14J。初始预载339.20005J及接触偏移功0保持；真实翻覆保留。
- `curved-boundaries-r1`关闭耦合两模式共240拍，与实际`6be5f54`缓存既有CarState字节一致，仅新增`suspension_state=None`显式投影；两模式海岸各120外拍/240原生步完成。完整原始快照保存，收尾脚本存为`curved-boundaries.py`。
- `reference-v23/parameters.json`两模式各真实240外拍/480原生步完成，完整91车辆/9输入字段及实际悬架状态导出；成绩game-controls-v20/reference-v23，新增纯几何源纳入参考哈希。单侧/边界314份Python源前后稳定且同源，参考导出的源哈希逐项核对一致。

|模式|旧/新有符号几何刷新J|旧/新累计正几何刷新J|旧/新最大轮荷N|
|---|---:|---:|---:|
|游戏|−41.90790 / 0.0002867|0.014014 / 0.027427|9366.48 / 9306.39|
|仿真|−37.41871 / 0.0082832|0.012417 / 0.025881|8904.29 / 8903.21|

圆角切平面造成的大幅负误差已消除，正误差略增及约179.87°真实翻覆原样保留，尚未达到整车能量闭合/人工验收。原四项护栏失败、其余同协议工况、一次功能T1、整组T2/T3、前台性能/人工驾驶及真实车型继续；本轮未追加长实验。下一直接处理遗留护栏的实际力/矩及接触行为。

## 已运行命令

```powershell
.venv/Scripts/python.exe tools/validate.py T0 --tests tests/test_suspension_contacts.py tests/test_suspension_envelope.py tests/test_joint_suspension.py --output docs/evidence/PHYS-SUSP-01/validation-T0-curved-r1
.venv/Scripts/python.exe tools/validate.py T0 --tests tests/test_curved_suspension.py tests/test_world_substeps.py tests/test_impact_delivery.py::test_real_challenge_impact_failure_frame_is_delivered_once --output docs/evidence/PHYS-SUSP-01/validation-T0-curved-r3
.venv/Scripts/python.exe tools/validate.py T0 --tests tests/test_suspension_native.py tests/test_physics_config_io.py tests/test_traction_lifecycle.py::test_mode_abs_tcs_variants_get_distinct_score_keys --output docs/evidence/PHYS-SUSP-01/validation-T0-curved-r4
.venv/Scripts/python.exe tools/physics/suspension_contact_probe.py --output docs/evidence/PHYS-SUSP-01/curved-native-r1 --prior docs/evidence/PHYS-SUSP-01/finite-native-r2
.venv/Scripts/python.exe tools/physics/export_reference.py --output docs/evidence/PHYS-SUSP-01/reference-v23/parameters.json
.venv/Scripts/python.exe logs/physics/finish_curved_increment.py
```

命令输出/失败、原始轨迹、源与证据SHA见[curved-receipt.json](curved-receipt.json)。本包记录Box曲面增量，不替代其他支撑类型及阶段验收。

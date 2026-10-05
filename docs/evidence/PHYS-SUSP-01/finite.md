# PHYS-SUSP-01：有限转动的悬架行程与共轭反力

2026-10-05，基线`f0ed868`。两模式SI共同机械求解已从起点瞬时雅可比，改为有限转动下的行程差与功共轭法向冲量/力矩。仍是每120Hz外拍两个真实1/240s世界步；车身、轮胎、传动共用末速度，控制及快照时钟保持。驾驶参数、硬件、原刚体碰撞和轮胎残差门槛保持。本轮仅本地增量，整个任务继续。

## 机制

`src/suspension_kinematics.py`保存本子步真实接点的切平面、轮心安装点、悬架方向及起点长度；数据是纯向量，机械求解不持有Bullet对象。轮心球形包络在固定平面上的长度为`l=p/a`，其中`a=−n·d`。使用末角速度对应的实际指数转动，先匹配Bullet的原生角阻尼、运动限制和归一化，再从末轮心与末方向求几何量。

采用离散乘积恒等式：`Δl = Δp * mean(1/a) + mean(p) * Δ(1/a)`。沿转动路径的平均安装点/方向满足`Δr=dt*Ω×mean(r)`，得到六维雅可比；因此`dt*G·(v_end,Ω_end)`等于完整有限转动的长度差。法向线冲量仍沿真实接触法线，角冲量采用同一离散虚功的共轭力矩。

该雅可比进入原20轮法向/轮胎/制动/完整传动共同迭代，轮荷和提交冲量使用最终实际系统。有限转动的法向力一致性要求`<1e−10N`，共轭冲量差要求`<1e−12Ns/Nms`；原轮胎`0.001N`、制动`1e−9Nm`、完整能量`3e−9J`及角动量`1e−10Nms`门槛保持。近掠末姿态沿既有0.1支撑资格进入原自由轮释放方程。初始预载、自由材料及真实碰撞不清除。

适配层直接累加实际提交的线/角冲量；Snapshot的末轮荷、接地资格和有效接触对齐量同源。独立台架连续机械子步也推进局部几何描述，正式世界子步随后重新查询实际接点。`kinematics=None`明确表示纯线性机械台架，关闭耦合支路保持原生机制。

## 验证及失败记录

- r1只因测试导入顺序Ruff失败，pytest未跑。r2为42通过/11失败：两项独立旋转恒等式错误地用了输入字面量而非Bullet实际保存的单精度角速；改用实际输入，原容差保持。九项完整机械账暴露法向收敛停止误差与实际提交冲量不一致；把新有限转动法向门槛从1e−8N收紧到1e−10N后，r3的53项通过。
- r4为67通过/1挑战碰撞失败，保留原始日志。共轭雅可比判据当时错误地用力/矩绝对差作为统一停止量；最后一轮法向5.82e−11N、共轭力/矩1.51e−10，折算成实际冲量已小于1e−12。判据改按实际Ns/Nms检查，r5的31项联合机械/挑战通过；原测试门槛保持。
- r6配置/版本5项通过。随后补入实际原生角阻尼路径，最终r7全Ruff及**90项定向T0通过，pytest7.44s**，覆盖独立末姿态/虚功、零转动及原生角限制/阻尼、两模式真实子步/冲量、质量静载、预载与自由轮、前驱/后驱/四驱完整能量/动量和挑战碰撞。配置字段与版本未随阻尼路径改变，复用r6；最终真实导出另核对完整字段。
- 最终`finite-native-r2`为原单侧两模式各360外拍/720原生步；接点距实际Box内核/margin表面≤1.78e−8m，局部悬架能量残差≤7.95e−14J，轮胎残差≤9.39e−5N，真实翻覆保留。
- 最终两模式海岸各120外拍/240原生步完成，`finite-boundaries-r2`保存原始快照。关闭耦合240拍在r1与实际`6be5f54`冻结运行缓存的既有字段逐字节相同；最终只改SI法向输入/角阻尼路径，关闭支路不执行它，具体5份源码差异和复用边界写在r2，未重跑原缓存。
- 最终`reference-v22-r2/parameters.json`两模式各240外拍/480原生步，完整91车辆/9输入字段。成绩game-controls-v19/reference-v22；原生对照、最终海岸、最终参考表的312份Python源核对同源稳定。阻尼接入前的轨迹/边界/导出全部保留其实际版本，不冒充最终结果。

|模式|旧/新累计正几何刷新J|旧/新累计有符号几何刷新J|旧/新最大轮荷N|
|---|---:|---:|---:|
|游戏|28.84206 / 0.01401|23.16928 / −41.90790|9311.10 / 9366.48|
|仿真|18.28862 / 0.01242|10.81059 / −37.41871|8827.29 / 8904.29|

正功显著下降，负几何误差及轮荷增大原样保留，不宣称整车能量闭合。剩余负误差峰值约−2.3J/拍，集中在约80–90°侧倾时球形包络接触Box圆角的阶段，真实法线逐拍明显变化；当前切平面在该曲面上仍是近似。原四项护栏失败、有限胎宽/实车型、整组T1/T2/T3、性能和人工体验均未收口。本轮不追加整套长实验。

## 下一直接施工

将实际Box内核+轮半径包络带入末姿态几何。对两端球心`c0,c1`的距离平方水平集，按分量差商构造割线法线`N`，使`N·(c1−c0)=0`；与`Δ(d*l)=mean(d)*Δl+mean(l)*Δd`合用，得到真实圆角/面/棱之间的离散共轭行程及反力，继续进入当前共同求解。形状/变换只读取唯一真实世界，不另建碰撞世界。此前有效短检查继续复用；该曲面机制尚未实施。

## 命令与依据

```powershell
.venv/Scripts/python.exe tools/validate.py T0 --tests tests/test_finite_suspension.py tests/test_joint_suspension.py tests/test_world_substeps.py tests/test_suspension_native.py tests/test_impact_delivery.py::test_real_challenge_impact_failure_frame_is_delivered_once --output docs/evidence/PHYS-SUSP-01/validation-T0-finite-r7
.venv/Scripts/python.exe tools/physics/suspension_contact_probe.py --output docs/evidence/PHYS-SUSP-01/finite-native-r2 --prior docs/evidence/PHYS-SUSP-01/world-native-r1
.venv/Scripts/python.exe tools/physics/export_reference.py --output docs/evidence/PHYS-SUSP-01/reference-v22-r2/parameters.json
.venv/Scripts/python.exe logs/physics/finish_finite_damped.py
```

单次本地收尾入口只做海岸短集成和明确的关闭分支复用，生产不依赖它。具体源码/原始证据哈希见[finite-receipt.json](finite-receipt.json)。

原生路径依据：[Bullet 2.84指数转动和归一化](https://github.com/bulletphysics/bullet3/blob/2.84/src/LinearMath/btTransformUtil.h)、[先阻尼的实际公式](https://github.com/bulletphysics/bullet3/blob/2.84/src/BulletDynamics/Dynamics/btRigidBody.cpp)。离散功共轭的理论背景见[Gonzalez的机械积分论文目录](https://web.ma.utexas.edu/users/og/numerics.html)；本包恒等式按上述具体几何独立推导，原生行为另由本机检查证明。

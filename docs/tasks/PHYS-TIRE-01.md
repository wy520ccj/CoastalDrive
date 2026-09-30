# PHYS-TIRE-01 轮速、滑移与唯一轮胎力

- 状态：done（本功能块自动验收完成；完整阶段人工驾驶/可见性能仍待完成）
- 实施提交：`30c7909036d250ab917e76d47822a5f01dd0bb1d`，本地未推送；该源码完整T2通过
- 基线：PHYS-04 `558d218`，七工况与紧弯A/B已保存
- 功能范围：PHYS-05/06/07/08/09合并迁移，主代理决定模型与积分；确定性记录/测试可交允许的低度代理
- 原因：ω、κ和Fx必须互相反馈，不先加入没有受力反馈的“真实轮速”标签；迁移前后分别保存A/B，不并行叠加旧新轮胎力

## 必要边界

车体仍由Bullet推进、碰撞/重力/悬架正常保留。自定义模型独占接触切平面的Fx/Fy与车轮转动方程`I*dω=Td−Tb−r*Fx`。每轮原生frictionSlip/EngineForce/Brake持续归零；原Vehicle.apply_command不得继续覆盖这些三零设置。风阻独立保留；驱动轴发动机制动与制动踏板应转为车轮转矩，不再同时施加旧中心制动力。准静态估计轴荷保留为诊断，实际轮胎力使用真实动态法向支撑。

刚体接点速度必须含角速度项，并以接触切平面和真实左右轮角建坐标。正反向、空中、低速起步/停车、静摩擦与联合滑移分别定义；低速正则化属于明确数学模型，不作为静默兜底。选择不会在120Hz低速形成非物理抖动的耦合积分，验证力学符号/耗散/旋转与平移动能，不能只看速度曲线。

WheelState/Contact诊断中的原生rotation与skid不能冒充ω/κ。独立wheel状态保存在物理核心，reset清零、坐标重定位保留，Snapshot给出真实采样时刻；可视滚动随后对应独立角度。

## 本机原生实现事实

2026-10-01本机`PandaSystem.getVersionString()`为1.10.16，`getBulletVersion()`为284，即Bullet2.84；以后核对这个版本，不用master代替。

- [Bullet2.84 vehicle](https://github.com/bulletphysics/bullet3/blob/2.84/src/BulletDynamics/Vehicle/btRaycastVehicle.cpp#L279)：悬架冲量先施加，随后updateFriction。EngineForce/Brake为0使纵向冲量为0；frictionSlip=0使侧向摩擦预算与缩放冲量为0。函数仍执行，法向悬架保留。本机独立平面短探针报告水平速度(5,10)一步不变、四轮悬架非零、skid=0；下一实施应加入持久化所有权验证，不能只靠这个临时观察。
- [world时序](https://github.com/bulletphysics/bullet3/blob/2.84/src/BulletDynamics/Dynamics/btDiscreteDynamicsWorld.cpp#L436)：碰撞检测→solveConstraints→integrateTransforms→updateActions。车辆action里的轮胎/悬架冲量改变速度，下一步再积分位姿。自定义施力选择应记录采样和施力阶段，避免把事后读数说成同一求解阶段。
- [原生轮旋转](https://github.com/bulletphysics/bullet3/blob/2.84/src/BulletDynamics/Vehicle/btRaycastVehicle.cpp#L301)由车体接点速度/r重写，离地仅延续增量并乘.99，没有轮惯量/转矩积分。
- **不调用getGroundObject来查真实路面**：[原生rayCast](https://github.com/bulletphysics/bullet3/blob/2.84/src/BulletDynamics/Vehicle/btRaycastVehicle.cpp#L171)替换为fixedBody；[Panda接口](https://github.com/panda3d/panda3d/blob/v1.10.16/panda/src/bullet/bulletWheel.cxx#L582)将该指针强转PandaNode。本机代理独立进程调用曾报Invalid TypeHandle并退出。真正侧墙接触、动态地面或路面类型识别应使用支持的world查询/明确接触模型；不采用ctypes或反射绕过原生接口。

护栏假三角法线已修复，真正轮射线命中侧面仍是接触分类问题：原始in_contact保留实际事实，侧墙不能当成路面坡度或μFz路面支撑。需要明确可用路面法线/接触来源，以及Bullet原生悬架的剩余边界。

## 验收

1. 实际原生切向力归零验证，证实自定义唯一所有权；悬架、重力和真实碰撞仍存在。
2. 前进/倒车驱动、制动转矩与Fx符号，纯自由滚动、空中受转矩、抱死与空转，κ/α及能量收支；120Hz与更小内部积分步的比较。
3. 同配置/初始条件的七标准工况、紧弯、坡面/草地与护栏A/B，解释理论方向与幅度。参数仍为游戏设计数据，不能编造车型标定。
4. 相关T0/T1通过后本迁移块T2。ABS/TCS/ESC下一功能块使用真实单轮反馈；输入辅助和车型电子控制各归自身职责。人工驾驶/可见性能在完整阶段Gate统一取得，不由headless替代。

## 已有组件研究

`tools/physics/wheel_integration_lab.py`和[evidence/PHYS-TIRE-01](../evidence/PHYS-TIRE-01/README.md)保存一维隐式Fx/ω/v耦合原型。四工况×两步长，能量账最大残差约2.22e−11J、制动无反转。此处使用300kg单轮等效平动质量和单调tanh曲线，只验证积分机制；不是Bullet整车、三维接点有效质量或ABS峰值滑移曲线。下一步由主代理决定三维轮胎/积分模型后实施，不需要用户逐票授权。

## 2026-10-01实施与当前证据

四轮独立轴向ω/转角、κ/α、隐式Fx/Fy、摩擦圆内低速静摩擦已接入Tires；Powertrain返回轮端转矩，原生切向三零持续保持。风阻/滚阻独立，准静态轴荷仅作诊断，实际悬架支撑决定轮胎预算。真实转角对应视觉滚动。力的最后子步求解与完成Bullet后的采样分开，整步实际Fx/Fy/制动冲量另存并验证轮角动量账。

外层120Hz改Bullet max_substeps=0，消除旧车身显示位置与当前接点约v*dt的错位；不调侧偏刚度掩盖高速假失稳。150km/h扰动现在衰减，20条件内部步长研究全部完成、零错误；5°坡停10s位移约3.3e−5m，平均Fx1025.997N与mg sin5°吻合。

正式A/B/C均同单步协议：A为558d218，B为完整轮胎迁移且动力曲线不变，C仅在B上把正常游戏曲线×1.055补偿约66kg等效转动质量。B原游戏起步/22s速度/坡道三门槛失败，原始数据保留；C保留原门槛并通过。split-μ无ABS/ESC的失稳明确报告，尚不等同于完成正常游戏或仿真模式。

T0最终72项/Ruff通过。迁移首T1 8失败、扩大T1 5失败完整记录，失败后的smoke/弯坡为not_run。后续碰撞事故以真实manifold独立记账，持续擦碰以恒轮角真实工况核验，制动优先级按执行器/轮动能核验；不放宽6m/45°、5s擦碰或既有动力门槛。修复后扩大T1：248项、三种子启动、双种子30s弯坡全部通过。T2的427测试、三种子启动、操控、地表通过；交通七工况中rear_approach失败，原记录保留，原未运行项在独立目录全部通过。NPC已响应并横向让行，但真实轮胎响应下换道过冲，未满足原完成条件，随后旧车道IDM制动放大摆动。已分开当前路径/前方预瞄，并按期望横摆和真实横摆的差补偿齿条迟滞，未改变车辆受力、IDM或门槛。控制T0 32项、T1 155项及启动/弯坡通过，新版本完整T2：429测试、三个种子启动、操控、20组地表、七交通工况、两有限赛道及三种子120s直路/弯坡全部通过，运行前后214文件哈希一致。完整报告与命令见[evidence](../evidence/PHYS-TIRE-01/README.md)。

用户追加两个模式及通用参考车目标，下一入口[PHYS-MODES-01](PHYS-MODES-01.md)，游戏动力补偿需与仿真参考车分离。随后CTRL-01/02/03按真实滑移/横摆反馈实现车型电子控制。整个物理goal、人工驾驶与可见性能仍未完成。

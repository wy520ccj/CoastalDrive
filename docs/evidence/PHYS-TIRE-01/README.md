# 轮速、唯一轮胎力与标准试验

2026-10-01。PHYS-04基线`558d218`已保存；当前工作区已接入四轮独立转动与唯一切向力。Bullet保留重力、碰撞、射线悬架和刚体积分。当前正在完成迁移回归；两模式入口、参考车参数化、ABS/TCS/ESC为后续功能，整项物理goal仍active。

## 实际机制

`tire_forces.py`按单轮实际法向支撑、轮心纵向速度、接点侧向速度和独立ω计算κ/α。`κ=(rω−vx)/max(|vx|,1m/s)`，`α=atan2(vy,max(|vx|,1m/s))`；轮速正向为向前滚动，对应世界轮轴右向的负角速度。转子绝对轴向ω与相对车体ω分别保存，视觉角度积分相对ω。

联合滑移使用径向简化Magic Formula：`q=(Cκκ,−Cα tanα)`，刚度乘`Fz/(mg/4)`；幅值以`μFz`为预算，shape1.9、curvature0.97，包含峰值与高滑移衰减。默认纵向刚度60000N、前后侧偏刚度均50000N/rad。参数属于设计参考，不是实车标定。

`wheel_dynamics.py`同时求解Fx/Fy、轮速和刚体接点速度，`Iw Δω=h(Td−Tb−rFx)`，Iw1.8kg·m²。刚体有效逆质量包含实际质量、世界惯量、接点/轮心力臂与内部转矩反作用。制动器在容量内保持相对轴转速为零，容量外耗散滑动；低速0.25m/s以下另求无滑移滚动/静止约束，所需力在摩擦圆内才成立，否则进入滑动曲线。没有车身速度/位姿钳制或运行期轮速同化。Fx/Fy力方程残差目标0.001N，迭代失败明确报错。

`vehicle_tires.py`将Fx/Fy冲量施于地面接点，同时施加右轴`h(Td−Tb−rFx)`转矩冲量；最后的`−rFx`避免把轮转动反作用同时算进车身俯仰。每外层tick两个轮胎子步，正/反轮次交替，刚体仍只推进一次120Hz。前轮采用真实Ackermann角。每轮原生frictionSlip/EngineForce/Brake持续归零，原生悬架与车身碰撞存在。准静态轴荷仅作诊断；滚阻使用实际支持轮荷总量，仍为独立中心阻力；风阻独立施加。已知重力/外力增量作为轮胎求解的预测输入，只由Bullet施加一次。

## 时刻与账本

外层已固定120Hz，改用`world.doPhysics(FIXED_DT,0,FIXED_DT)`，避免重复的Bullet内部时间累加与运动状态插值。此前40m/s时，Panda返回的旧车身位置与当前原生接点相差0.333333m，错误力臂制造了高速不稳定；现在接点平均纵向位置与车身差小于1e−4m。150km/h/.02m/s横向/.001rad/s横摆扰动在修复前发展到约1.88rad/s，修复后峰值约.000970rad/s并衰减。未通过调后轮刚度掩盖时刻错误。依据：[Panda1.10.16 world](https://github.com/panda3d/panda3d/blob/v1.10.16/panda/src/bullet/bulletWorld.cxx)、[vehicle同步](https://github.com/panda3d/panda3d/blob/v1.10.16/panda/src/bullet/bulletVehicle.cxx)、[Bullet2.84步进顺序](https://github.com/bulletphysics/bullet3/blob/2.84/src/BulletDynamics/Dynamics/btDiscreteDynamicsWorld.cpp)。

`force_contact_tick`是采用的上一完成步轮荷/几何；`force_kappa/force_alpha/fx/fy/brake_torque`属于最后轮胎子步。`sample_tick`、当前κ/α与轮心/接点速度在完成Bullet后独立采样。整步实际施加量另存`longitudinal_impulse/lateral_impulse`（N·s）及`brake_angular_impulse`（N·m·s），不能拿最后子步的力代表整步均值。快照插值保留最新物理诊断，reset清状态，坐标重定位保留ω/转角。

Bullet车辆action的悬架冲量在位姿积分后施加，静止坡面完成步速度会有沿支撑法线约.081m/s的相位分量，投影水平约.0071m/s；停车同时检查连续位移、道路切向运动和整步受力，不能用水平速度单值代替静止受力检验。

## A/B/C与汽车理论

正式对照使用相同120Hz单步协议。A加载558d218原车辆实现；标准平面工具统一max_substeps=0。完整Simulation护栏A使用独立研究副本，仅把simulation.py一行max_substeps4→0，原sha和唯一diff见[协议记录](guardrail-A-synchronized/protocol-overlay.json)，不改历史原件。

- **A**：[standard-A-synchronized](standard-A-synchronized/summary.json)，旧原生切向力/准静态纵向限幅。
- **B**：[standard-B-static](standard-B-static/summary.json)，轮速、真实轮荷、联合滑移、静摩擦接管，旧发动机曲线不变。
- **C**：[standard-C-calibrated](standard-C-calibrated/summary.json)，B机制不变，正常游戏发动机曲线非零节点整体×1.055；补偿约66kg等效轮转动质量对既有动力性目标的影响。用户确认困难仿真主打真实，**该补偿不作为仿真参考车标定**，下一PHYS-MODES-01明确分离。

| 同条件指标 | A | B | C | 解释 |
|---|---:|---:|---:|---|
| 12s全油门末速度(m/s) | 32.398 | 31.105 | 32.160 | 新轮惯量吸收驱动功，B变慢；C恢复游戏动力性 |
| 12s全油门行程(m) | 222.345 | 212.655 | 220.703 | 保留原始慢车，不只报告调校后的版本 |
| 转向阶跃累计横摆(°) | −16.778 | −16.063 | −16.031 | 保持右转符号，有限侧偏刚度产生不同侧偏/横摆响应 |
| 弯中制动停止时刻(s) | 3.083 | 3.167 | 3.167 | 轮转动与真实摩擦预算影响制动；没有额外中心制动力 |
| split-μ停止路径(m) | 50.463 | 56.586 | 56.586 | 无ABS/ESC时低附着侧抱死、联合滑移削弱横向控制 |
| split-μ累计横摆(°) | 3.244 | 320.030 | 320.030 | 新模型暴露无电子控制失稳；不能以“更真实”概括其幅度，须后续标定及控制A/B |
| 6m紧弯有效质心半径(m，右转) | 6.156 | 6.144 | 6.144 | 同目标理论质心半径6.1m，左右近似对称；保留Ackermann |

[A/B差值](comparison-A-B.json)、[B/C差值](comparison-B-C.json)记录配置变化。H1原始B：3s起步11.694m、22s149.912km/h、坡道最终y54.872m，三项原游戏阈值失败，0–10010.042s/制动46.293m。显式C研究及正式曲线：3s12.444m、22s154.137km/h、坡道y57.435m、0–1009.525s/制动46.261m；原游戏门槛保持。见[h1-static-raw.txt](h1-static-raw.txt)、[h1-calibration-trial.txt](h1-calibration-trial.txt)。

## 耦合、静摩擦与极限

[最终研究矩阵](coupling-probe-final/summary.json)包含五工况×2/8子步×后侧偏刚度50k/60k，共20个完成、零求解错误，最大残差小于.001N。后轮60k仅研究，默认仍50k。

- 150km/h扰动：横摆峰值.000970rad/s，8s末约1.17e−6rad/s；未产生持续偏航。
- 草地全油门3s再滑行1s：4s末约.627m/s，κ峰值约57.02，后轮有924个轮-tick满足κ≥.2；同一驱动转矩在低μ下用于自转而非等量车速。
- 柏油100km/h制动：3.183s水平速度低于.1m/s，544个轮-tick满足κ≤−.95，证明抱死来自制动/转动方程；尚未实现ABS。
- 5°坡停10s位移约−3.33e−5m；整步平均Fx1025.997337N，对应`mg sin5°=1025.997404N`。8子步位移约5.16e−7m。[独立观测](model-observations.json)保存数值；测试以10s连续位移和整步力平衡双核对。
- 广义动量/后向离散能量账、空中等反转矩、正反驱动、制动不反转与真实接点冲量有组件及Bullet测试。积分耗散为显式模型属性，未以空中速度重置伪造停车。

## 碰撞与回归工况

[护栏A/C](guardrail-A-synchronized-vs-C-calibrated.json)：120km/h最大侧距4.834→4.842m，roll10.199→11.336°；60km/h最大侧距4.551→4.624m，roll1.391→1.027°。保持6m/45°门槛。新120km/h轨迹只有一次事故，旧A为两次；[独立manifold事故账](guardrail-episode-accounting.json)核对实际接触、事件时刻和计数，不强迫新车重演旧反弹。

旧fixtures已按其验证目的修正，原边界/性能门槛没有放宽：显式初速同时初始化自由滚动ω；草地/柏油滑行使用同10m/s和相同轮动能；换道准备期间避免先自动换道再被测试重置信号；制动优先级检查立即关驱动、轮能耗散及踏板完成时减速，不要求5%刹车首tick强制压车速。

持续5s擦碰改用恒定2°轮角/半油门的实际执行器工况，连续726tick接触、单撞击/单scrape。原随速度输入包络不能保证恒轮角和持续接触。移动NPC采用真实斜向来车，先撞角转动后新接点重撞，保留至少两个音频脉冲与一个事故计数。[逐tick证据](impact-fixtures/summary.json)保留原fixture、正确滚动正碰和新工况；音频实现不变。

## 交通控制兼容

原迁移版本所有剩余专项在[t2-remaining](t2-remaining/summary.json)通过，运行前后214个Python文件哈希一致；七交通工况中的rear_approach仍是原T2的唯一失败，原失败未覆盖。NPC已触发让行，但在目标横向窗口内车头未收敛，随后旧车道跟车控制放大摆动。[原轨迹](rear-yield-original.json)和原七工况完整记录保留。

主线只改`traffic.py/highway_driver.py`的控制：当前位置的计划横坐标供偏离/恢复判据使用，前方预瞄横坐标供转向使用。纯追踪误差`e=bearing−heading`给出期望横摆`r_ref=2*v*sin(e)/distance`；按本项目临界阻尼齿条的低频迟滞`τ=2/steering_response`，用`e+τ*(r_ref−r_actual)`跟踪横摆，再生成转向角。弯道参考是计划曲率对应的非零横摆，不能把车辆横摆单独压向零。该反馈是本项目推导与真实轨迹验证的控制补偿；[CMU纯追踪原报告](https://publications.ri.cmu.edu/storage/publications/pub_files/pub3/coulter_r_craig_1992_1/coulter_r_craig_1992_1.pdf)提供几何曲率关系，并指出该几何法没有执行器动态。

[最终独立副本](split-preview-yaw-tracking/interactions.json)七工况全通过：rear_approach在tick733完成换道，x4.45563m、heading−2.71371°，零碰撞/零制动/零恢复；最大x4.83689m、末x4.46857m。真实横摆与heading有限差分568个有效tick同号，RMS差9.73e−5rad/s。[源码差异账](controller-source-delta.json)确认车辆受力/轮胎/动力总成/Simulation不变；原3°/0.25m完成门槛、IDM、预瞄距离均保持。主线T0：32项通过，见[t0-controller-verified](t0-controller-verified/summary.json)，新增当前/预瞄误差分离与物理让行回归。

未采用的探索均保留：course方向替代、只对实际横摆作lead、延长预瞄、分离目标后延长预瞄均未通过。延长预瞄还曾暴露当前误差/未来目标混用的误恢复；分开读数修复这一职责问题，但独立分离不足以通过让行。[线性辅助分析](preview-linear-analysis.json)是简化自行车/齿条模型，未含悬架、角阻尼、碰撞及非线性轮胎，不代替实际Bullet验收。

## 验证及模型范围

T0最终：Ruff及72项相关测试通过，见[t0-final](t0-final/summary.json)。首次整车T1失败8项，扩大T1失败5项且后续smoke/弯坡未运行，分别保留[t1-trial](t1-trial/summary.json)、[t1-final](t1-final/summary.json)。修复后的[扩大T1](t1-verified/summary.json)：248项、三种子启动、双种子30s弯坡全部通过。本迁移块[t2-final](t2-final/summary.json)中427测试、三种子启动、操控和地表通过；交通七工况的rear_approach失败，其余六项通过，后续专项在原报告标为not_run。[原版剩余专项](t2-remaining/summary.json)全部通过，不能覆盖原交通失败。上述控制修正已接入主线，T0 32项通过；[控制T1](t1-controller/summary.json)155项、三种子启动、两种子30s弯坡通过，新版本完整T2待执行。额外碰撞/跨接缝试验的自由滚动初条件已补齐并短测6项通过。人工驾驶、可见窗口性能、完整阶段T3未执行。

复核命令：`.venv/Scripts/python.exe tools/validate.py T0 --tests tests/test_tire_forces.py tests/test_wheel_dynamics.py tests/test_vehicle_tires.py tests/test_driving_response.py tests/test_road_loads.py tests/test_vehicle_commands.py tests/test_vehicle_contacts.py tests/test_physics_testbed.py --output <新目录>`；扩大T1使用`--area vehicle --area road --area traffic --area core --tests tests/test_race.py tests/test_highway_run.py tests/test_impact_events.py tests/test_impact_integration.py`，T2不带模块限制。标准试验和探针分别为`testbed.py`、`steering_geometry_probe.py`、`tire_dynamics_probe.py`、`guardrail_probe.py`，均要求新输出目录，历史源码用`--source-dir`在独立进程加载。

历史探索目录保留但不作最终验收：`coupling-probe`为旧姿态错位，`coupling-probe-synchronized`为无静摩擦蠕移，`coupling-probe-static`为补偿前研究；早期`standard-A/standard-B/standard-B-v2`尚未统一当前时刻协议，`standard-B-no-electronics`的停止量曾错误使用车身纵向速度（横向滑移时可假停止）；`comparison.json`属于这一早期系列。最终结论使用上文带`synchronized/static/calibrated/final`的目录与显式测量定义。

当前模型为静态路面射线悬架、独立轴向轮转子与简化联合滑移；轮胎接触使用上一外层步几何/载荷，未建松弛长度、轮转动陀螺项、动态支撑体相对速度与作用反作用、完整发动机/离合动力学。原生悬架仍可能对射线命中的侧墙施加作用，虽然自定义轮胎已排除侧墙支撑。困难仿真参考车按实际需求逐项完善这些机制，参数与适用工况一并核对。

## 原一维积分研究（迁移前保留）

`tools/physics/wheel_integration_lab.py`把车轮角速度与平动速度耦合隐式求解。300kg单轮等效平动质量、1.8kg·m²轮惯量、0.33m半径、3000N法向力、μ=1.1、纵向刚度60000N均是明确的研究输入，不是车辆标定。实际整车需使用刚体质量/惯量与轮接点的有效动力学，不能把300kg直接作为每轮独立车体。

给定Fx后，v_next=v+dt Fx/m，ω_free=ω+dt(Td−rFx)/I；制动以干摩擦软阈值求ω_next，允许保持ω=0，反力矩由变化量反算。Fx用μFz*tanh[Cκ(rω_next−v_next)/(μFz max(|v_next|,1m/s))]，在±μFz内固定32次二分解一致性方程。

后向离散的能量恒等式为：

`ΔE = dt Td ω_next − dt Tb_used ω_next − dt Fx(rω_next−v_next) − m(Δv)²/2 − I(Δω)²/2`。

四工况（自由滚动2s、起步驱动2s、20m/s制动3s、仅轮自转衰减2s）×1/120、1/480s两个步长均通过：最大力方程残差约1.4e−5N，最大能量恒等式残差约2.22e−11J；无外功工况耗散，制动无反转。原始component-lab.json记录全部参数、实际转矩、动能变化与检查条件。

命令：`.venv/Scripts/python.exe tools/physics/wheel_integration_lab.py --output docs/evidence/PHYS-TIRE-01/component-lab.json`。输出须为新文件；复跑使用另一路径。新增工具Ruff通过。本结果只证明这一组件的耦合/制动与能量账正确，下一实现仍须处理三维联合滑移、实际接触/轮荷、旋转反力矩与完整A/B。

该单调tanh曲线用于积分研究；ABS所需的峰值滑移与滑动段行为尚未选择/验证，不把此曲线冒充最终ABS轮胎模型。后续滑移与低速模型可核对[MathWorks Tire-Road Interaction](https://www.mathworks.com/help/sdl/ref/tireroadinteractionmagicformula.html)的实际滑移定义及平滑低速分母，再由同条件试验验证所选游戏模型。

# 车辆参数参考表

本文同步当前 `VehicleConfig`、`InputConfig` 与 `DrivingMode`。所有参数均为程序设计值或设计推导值；本机 Bullet 读回证明实际装入的配置，不是实车测量或标定。困难仿真使用通用设计参考车，保留自动前进换挡、简化虚拟离合、射线悬架及简化轮胎模型，不称完整车辆仿真软件。

当前冻结数据见 [reference-parameters.json](evidence/PHYS-MODES-01/reference-parameters.json)。该文件逐项保存配置、单位与职责、实际几何、两模式各240tick静置读数，以及相关源码的 SHA-256。Git HEAD 仅为工作区历史上下文，不能代表未提交源码；旧参考表的 HEAD/hash 已不用于指认当前实现。

本次 `src/vehicle_config.py` SHA-256：`e37beb7a53a75ef3fed21bd74d5732f0807e822953c68de0f0a77bda0eef0ee2`。Panda3D 1.10.16，Bullet 2.84。

## 模式与实例边界

`DrivingMode.GAME`（正常游戏）选择 `CAR` 与 `GAME_INPUT`；`DrivingMode.SIMULATION`（困难仿真）选择 `REFERENCE_CAR` 与 `SIMULATION_INPUT`。模式与计时/自由驾驶/高速玩法正交。Vehicle → Simulation → Session直接传入冻结配置实例，部件创建、reset与跨赛道重建沿用配置；主菜单切换选择后，起步按配置重建世界。不得对存活Bullet车身替换参数对象。

参考车与游戏车共用力学核心；明确差异是曲轴转矩曲线、游戏速度/倒挡力渐退、刚体角阻尼与惯量来源，以及三个输入辅助开关。Q/E只请求R/D方向，S为制动；并未新增手动前进挡或离合踏板。

## VehicleConfig完整字段

每个字段单独一行。值均为设计；职责中注明换算或设计推导。`—`表示与正常游戏相同，`null`表示自动惯量，不代表零惯量。

| 字段 | 正常游戏 | 困难仿真参考车 | 单位 | 设计/推导与计算职责 |
|---|---|---|---|---|
| mass | 1200 | — | kg | Bullet车身质量；轮胎标称载荷与道路载荷 |
| torque_curve | [[900,116.05],[1800,174.075],[3200,211],[4500,200.45],[6000,158.25],[6500,0]] | [[900,110],[1800,165],[3200,200],[4500,190],[6000,150],[6500,0]] | rpm,N·m | 曲轴转矩节点线性插值；game为raw非零节点×1.055 |
| gear_ratios | [3.25,2.05,1.45,1.1,0.88] | — | 1 | 五个自动前进挡传动比 |
| final_drive | 3.7 | — | 1 | 主减速比 |
| drivetrain_efficiency | 0.88 | — | 1 | 驱动转矩效率 |
| idle_rpm | 900 | — | rpm | 发动机转速下限 |
| shift_time | 0.28 | — | s | 换挡驱动转矩衰减时长 |
| torque_response | 0.12 | — | s | 轮端转矩一阶响应时间常数 |
| engine_braking | 24 | — | N·m | 闭油门曲轴拖曳转矩估计 |
| max_speed | 44.44444444 | — | m/s | game前进驱动转矩渐退速度；160/3.6 |
| reverse_speed | 6.111111111 | — | m/s | game倒车驱动转矩渐退速度；22/3.6 |
| reverse_force | 2200 | — | N | game倒车轮端力上限，按半径换算转矩 |
| reverse_gear_ratio | 3 | — | 1 | 倒挡机械传动比 |
| game_speed_limits | true | false | bool | 启用游戏速度渐退/倒车力上限；不是车身速度钳制 |
| brake_torque | 3643.2 | — | N·m | 四轮制动总容量 |
| front_brake_share | 0.6 | — | 1 | 前轴制动容量份额 |
| steering_degrees | 26 | — | ° | 虚拟前轴中心角机械限位 |
| steering_rate | 50 | — | °/s | 齿条角速度限位 |
| steering_response | 7 | — | s⁻¹ | 齿条输入临界阻尼响应系数 |
| steering_return | 10 | — | s⁻¹ | 齿条回正临界阻尼响应系数 |
| wheel_radius | 0.33 | — | m | 原生射线轮半径、独立轮速/滑移/力臂 |
| wheel_inertia | 1.8 | — | kg·m² | 独立单轮轴向转动惯量 |
| longitudinal_stiffness | 60000 | — | N/κ | 标称单轮载荷下纵向滑移刚度 |
| lateral_stiffness | 50000 | — | N/rad | 标称载荷下前轮侧偏刚度 |
| rear_lateral_stiffness | 50000 | — | N/rad | 标称载荷下后轮侧偏刚度 |
| tire_shape | 1.9 | — | 1 | 简化联合Magic Formula形状 |
| tire_curvature | 0.97 | — | 1 | 简化联合Magic Formula曲率 |
| slip_speed | 1 | — | m/s | 低速滑移分母尺度 |
| static_contact_speed | 0.25 | — | m/s | 低速静摩擦约束尝试尺度 |
| tire_substeps | 2 | — | 次/tick | 轮胎车体耦合子步数 |
| suspension_stiffness | 40 | — | s⁻² | Bullet质量归一化悬架刚度；平路k=mass×值 |
| suspension_compression | 4.4 | — | s⁻¹ | 质量归一化压缩阻尼；平路c=mass×值 |
| suspension_relaxation | 2.3 | — | s⁻¹ | 质量归一化伸张阻尼；平路c=mass×值 |
| air_density | 1.225 | — | kg/m³ | 环境空气密度 |
| drag_coefficient | 0.32 | — | 1 | 气动阻力Cd |
| frontal_area | 2.142857143 | — | m² | 迎风面积；保持旧CdA乘积的推导设计值 |
| rolling_coefficient | 0.01359157322 | — | 1 | 铺装滚阻160/(1200×9.81)，乘实际Fn及低速线性项 |
| grass_rolling_coefficient | 0.07645259939 | — | 1 | 草地滚阻900/(1200×9.81) |
| road_friction | 1.1 | — | 1 | 铺装摩擦预算μFn |
| grass_friction | 0.45 | — | 1 | 草地摩擦预算μFn |
| wheelbase | 2.2 | — | m | 轴距、Ackermann和轴荷诊断 |
| track_width | 1.68 | — | m | 轮距、实际轮连接点横坐标 |
| collision_half_width | 1.05 | — | m | 真实车身碰撞盒半宽 |
| collision_half_length | 2.15 | — | m | 真实车身碰撞盒半长 |
| collision_half_height | 0.42 | — | m | 真实车身碰撞盒半高 |
| body_center_height | 0.84 | — | m | 设计地面基准下碰撞盒中心高度 |
| wheel_connection_height | 0.67 | — | m | 设计地面基准下射线悬架连接点高度 |
| center_of_mass_height | 0.42 | — | m | 真实几何相对CG偏移与轴荷诊断高度 |
| front_weight_share | 0.5 | — | 1 | 通过真实轴连接点相对CG纵向距离实现静态前载份额 |
| body_inertia | null | [1919.56,511.56,2290.0] | kg·m² | null由Bullet碰撞盒生成；reference显式设计惯量 |
| angular_damping | 0.2 | 0 | 1 | Bullet刚体角阻尼 |
| suspension_travel | 0.2 | — | m | 射线悬架最大行程，传API时×100cm |
| suspension_force_limit | 6000 | — | N | 每轮实际施加悬架力上限 |

## InputConfig完整字段

原输入字段已从VehicleConfig迁至InputConfig。仿真开关关闭后对应速率/等待/包络数值仍保留在冻结配置中，但该输入分支不使用。

| 字段 | 正常游戏 | 困难仿真参考车 | 单位 | 设计职责 |
|---|---|---|---|---|
| progressive_pedals | true | false | bool | 启用键盘踏板渐变 |
| speed_sensitive_steering | true | false | bool | 启用速度相关键盘转向包络 |
| automatic_reverse | true | false | bool | 低速S持续制动后辅助切倒挡；false用Q/E显式R/D |
| throttle_rise | 1.6 | — | 比例/s | 游戏油门上升速率；仿真渐变关闭时不使用 |
| throttle_release | 5 | — | 比例/s | 游戏油门释放速率；仿真渐变关闭时不使用 |
| brake_rise | 6 | — | 比例/s | 游戏制动上升速率；仿真渐变关闭时不使用 |
| brake_release | 10 | — | 比例/s | 游戏制动释放速率；仿真渐变关闭时不使用 |
| assisted_lateral_acceleration | 7.5 | — | m/s² | 游戏速度转向包络目标；仿真包络关闭时不使用 |
| reverse_delay | 0.4 | — | s | 游戏辅助倒挡等待；仿真自动倒挡关闭时不使用 |

## CG与实际几何

车身设计以地面为高度基准，刚体原点是CG。连接点顺序为前左、前右、后左、后右。`wheel_hubs(config)`定义x=±track_width/2；前轴y=wheelbase×(1−front_weight_share)，后轴y=−wheelbase×front_weight_share；z=wheel_connection_height−center_of_mass_height。`body_center(config)`定义y=wheelbase×(.5−front_weight_share)，z=body_center_height−center_of_mass_height。改变CG高度/前载份额同时改变真实悬架连接点与碰撞盒相对CG的力臂；不是只改诊断轴荷。

默认两模式hubs均为(±.84,前+1.10/后−1.10,.25)m，碰撞盒中心(0,0,.42)m，半尺寸(1.05,2.15,.42)m。游戏惯量由Bullet盒形生成；参考惯量显式设置为设计值(1919.56,511.56,2290)kg·m²，沿用同设计车身尺度，非实车惯量。显式惯量与后续几何修改不会自动联动，使用者需提供一致设计。

## 当前保留的模型常数与职责

| 项目 | 数值/关系 | 作用 |
|---|---|---|
| native suspension rest length | .4 m | Panda创建轮默认值；初始化轮姿按同长度，尚未独立配置 |
| rollInfluence | .1 | 原生轮侧倾影响参数；原生切向摩擦已关闭，该值保留读回 |
| CCD | threshold .5 m，swept sphere radius .35 m | 车身连续碰撞检测设计 |
| 重力 | 9.81 m/s² | 默认世界重力与标称载荷 |
| 游戏转向包络低速尺度 | speed²+16 | 输入包络的设计平滑尺度 |
| 游戏方向辅助低速判据 | .15 m/s | 制动/倒车输入分支 |
| 滚阻低速线性尺度 | min(horizontal_speed,1 m/s) | 滚阻随实际Fn与低速变化 |
| 自动变速与起步 | 自动升降挡、换挡冷却及虚拟起步离合规则 | 简化传动；参考模式仍保留 |
| 诊断轴荷滤波 | .15 s，纵加速度±12 m/s² | 仅诊断，不替代真实四轮Fn或钳制车身速度 |
| fixed step | 1/120 s，world max_substeps=0 | 权威物理步；显示插值独立 |

`road_grip`、`grass_grip`未使用字段已删除，不能当作现参数或摩擦系数别名。真实摩擦预算来自road_friction/grass_friction×动态Fn。原生每轮frictionSlip、EngineForce、Brake均置零，仅保留Bullet悬架与碰撞；自定义轮胎独占Fx/Fy与独立轮速积分。低速静摩擦约束只有所需力位于μFn圆内时成立，超预算转入简化联合Magic Formula。

本机对应 [Bullet2.84 updateSuspension源码](https://github.com/bulletphysics/bullet3/blob/2.84/src/BulletDynamics/Vehicle/btRaycastVehicle.cpp#L379)给出 `Fn_raw=mass×(S×compression×projection−C×relative_normal_speed)`；负力截零、施加时受每轮悬架力上限限制。平路每轮k=1200×40=48000N/m，压缩c=5280N·s/m，回弹c=2760N·s/m，乘的是完整车身质量。名义静态2943N/轮对应压缩.0613125m。坡面须使用法线投影，不能套平路系数。

## 本次真实Bullet读回

两模式各创建真实Vehicle，在水平无限平面、重力(0,0,−9.81)下用VehicleCommand()静置240tick；每步严格1/120s、max_substeps=0。完整四轮接点/法线/raw与cappedFn/长度存于JSON。

| 项目 | 正常游戏实际值 | 困难仿真实际值 | 单位 |
|---|---|---|---|
| mass | 1200 | 1200 | kg |
| inertia | [1919.560302734375,511.55987548828125,2290.000244140625] | [1919.56005859375,511.55999755859375,2290.0] | kg·m² |
| angular_damping | 0.200000003 | 0 | 1 |
| shape_half_extents | [1.0499999523162842,2.1500000953674316,0.41999998688697815] | [1.0499999523162842,2.1500000953674316,0.41999998688697815] | m |
| shape_center | [0.0,0.0,0.41999998688697815] | [0.0,0.0,0.41999998688697815] | m |
| 单轮radius | 0.3300000131 | 0.3300000131 | m |
| 单轮rest_length | 0.400000006 | 0.400000006 | m |
| 单轮travel_cm | 20 | 20 | cm |
| 单轮force_limit | 6000 | 6000 | N |
| 单轮stiffness | 40 | 40 | s⁻² |
| 单轮compression_damping | 4.400000095 | 4.400000095 | s⁻¹ |
| 单轮relaxation_damping | 2.299999952 | 2.299999952 | s⁻¹ |
| 单轮roll_influence | 0.1000000015 | 0.1000000015 | 1 |
| 静置前左normal_load | 2943.000977 | 2943.000977 | N |
| 静置前左suspension_length | 0.3386875689 | 0.3386875689 | m |

## PHYS-TIRE历史B/C动力性证据

下面保留PHYS-TIRE-01历史试验数字。B为未补偿曲线，C为非零节点×1.055的游戏候选；当时通过独立研究进程改变曲线。它们是历史软件/Bullet试验，不是当前困难仿真模式的重新测量，旧模块级CAR monkeypatch也不是当前配置接口。对应原始记录：[h1-static-raw.txt](evidence/PHYS-TIRE-01/h1-static-raw.txt)、[h1-calibration-trial.txt](evidence/PHYS-TIRE-01/h1-calibration-trial.txt)。

| 历史测量 | B | C |
|---|---|---|
| 0–100km/h | 10.0417 s | 9.5250 s |
| 制动距离 | 46.2925 m | 46.2610 m |
| 起步样本末速度 | 9.70003 m/s | 10.38680 m/s |
| 起步样本位移 | 11.69393 m | 12.44400 m |
| 22s末速度 | 149.91162 km/h | 154.13663 km/h |
| 浅坡最大高度 | 1.27661 m | 1.27926 m |
| 浅坡最大pitch | 6.73091° | 7.89623° |

原参考表另记录同平路条件12s末速度B=31.1048m/s、C=32.1601m/s，末3挡转速分别4900.61/5070.15rpm。这组保留为历史记录，当前冻结JSON没有重新跑该动力工况。

## 当前实例用法与重现

```python
from driving_modes import DrivingMode
from simulation import Simulation
sim = Simulation(driving_mode=DrivingMode.SIMULATION)
```

配置研究使用dataclasses.replace(mode.vehicle_config, ...)生成新冻结对象，并在创建Simulation/Vehicle时传入vehicle_config/config；Control走所选InputConfig，VehicleCommand是明确的执行器请求。JSON导出：

```powershell
.venv/Scripts/python.exe tools/physics/export_reference.py
```

标准试验入口已提供以下参数；一次选择一个明确工况并写新证据目录，不对存活实例做全局参数替换：

```powershell
.venv/Scripts/python.exe tools/physics/testbed.py --driving-mode simulation --actuator-input --cases flat_acceleration --output logs/reference-flat
.venv/Scripts/python.exe tools/physics/testbed.py --driving-mode simulation --vehicle-config config.json --actuator-input --cases steering_step --output logs/reference-steering
```

`--vehicle-config`接收车辆字段覆盖的JSON对象；`--actuator-input`绕过键盘辅助，仍使用同一真实齿条、动力总成、轮胎和Bullet世界。此表只冻结参数与一次静置读回，不据此宣称全部动力性、驾驶手感或视觉验收通过。

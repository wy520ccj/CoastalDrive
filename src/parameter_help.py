"""参数计算说明索引；统一提供试验台参数定义、公式索引与源码对应关系。"""

from dataclasses import dataclass

from vehicle_parameter_info import BRAKE_FIELDS, STABILITY_FIELDS, TRACTION_FIELDS, VEHICLE_FIELDS
from vehicle_parameters import PARAMETER_GROUPS

EDITOR_INFO = {
    "bump_height": ("实体凸起高度", "m", "路面几何输入", "凸起顶面高程 z = h。", "适用于单侧凸起工况；矩形台阶实体几何直接参与轮胎接触求交与法向加载。", "src/lab_experiment.py · install_bump"),
    "bump_length": ("实体凸起长度", "m", "路面几何输入", "沿行驶方向覆盖区间 [d, d + L]。", "凸起宽度固定为 0.48 m，布置于左侧轮迹；左前轮与左后轮依次通过。", "src/lab_experiment.py · install_bump"),
    "bump_distance": ("凸起前缘距起点", "m", "路面几何输入", "凸起前缘纵向位置 y = y0 + d。", "试验时长与初速应保证左前、左后轮完整通过凸起段，以获得完整平顺性统计指标。", "src/lab_experiment.py · install_bump"),
    "speed": ("初始车速", "km/h", "初始条件", "v0 = V0 / 3.6；轮端角速度按静态加载半径匹配纯滚动初值。", "设定试验起始瞬时车速，运行过程中的实际车速由整车动力学积分确定。", "src/lab_experiment.py · LabExperiment.__init__；src/vehicle_unsprung.py · initialize_rolling"),
    "mu": ("主路面附着系数", "1", "附着边界条件", "D = μ·Fn·(Fn/Fn0)^(pD−1)。", "定义当前路面—轮胎界面的标称峰值附着系数；纵向力 Fx 与侧向力 Fy 共享联合滑移摩擦圆预算。", "src/tire_properties.py · tire_grip"),
    "right_mu": ("右侧路面附着系数", "1", "对开路面条件", "当接地点横向坐标 x ≥ 分界线时采用右侧附着系数。", "适用于对开附着制动与对接附着弯道制动工况，按轮胎实际接地点空间坐标动态判定路面区域。", "src/lab_experiment.py · LabExperiment.__init__"),
    "duration": ("试验时长", "s", "终止条件", "Δt = 1/120 s，t_n = n·Δt；当 t_n ≥ T 时终止试验。", "采用 120 Hz 固定仿真时间步长，每步内部按配置执行多子步机械求解。", "src/lab_experiment.py · step / advance"),
    "onset": ("输入起始时刻", "s", "激励时序", "转向工况于 t0 时刻施加转角；延迟制动工况于 t0 时刻施加全制动请求。", "正弦转向频率固定为 0.5 Hz；制动压力与 ABS 响应由液压执行器及轮速闭环动力学决定。", "src/lab_experiment.py · command_at"),
    "steer": ("目标前轮中心转角", "deg", "转向激励输入", "R = L / tanδ；δL/R = atan[L / (R ± tf/2)]。", "表示虚拟前轴中心车轮转角（非方向盘转角），经转向齿条限位与二阶响应后按阿克曼几何分配至左右前轮。", "src/vehicle_steering.py · SteeringRack.advance / wheel_angles"),
    "cg": ("整车质心高度", "m", "整车几何输入", "稳态纵向轴荷转移估算式：ΔFz ≈ m·hg·ax / L。", "决定车身质心相对悬架上支点的垂向偏置；瞬时四轮法向载荷由耦合悬架动力学求解得出，修改质心高度时车身转动惯量保持独立配置。", "src/vehicle_config.py · wheel_hubs；src/vehicle_suspension.py"),
    "radius": ("目标定圆半径", "m", "参考路径参数", "参考前轮角 δref = atan(L/R)；路径跟踪曲率 κ = 2·ey / ld²。", "用于定圆及准稳态扫点工况的参考圆轨迹定义，闭环路径跟踪控制器据此输出转向与车速控制指令。", "src/lab_maneuvers.py · target_point / path_command"),
    "tire_load": ("轮胎标称参考轮荷", "N", "固定标定基准", "D = μ·Fn·(Fn/Fn0)^(pD−1)；Cx = Cx0·(Fn/Fn0)^pX；Cy = Cy0·(Fn/Fn0)^pY。", "轮胎刚度与附着幂律曲线的固定标定参考载荷 Fn0（不随整车装载质量自动缩放），调整该基准需同步重标定轮胎刚度参数。", "src/tire_properties.py；src/joint_iteration.h · joint_load_parameters"),
    "manual.throttle": ("油门请求", "%", "执行器输入", "归一化请求 u = u% / 100。", "经电子节气门一阶响应与 TCS 限幅后查表计算曲轴输出转矩。", "src/powertrain.py；src/vehicle_traction.py"),
    "manual.brake": ("制动请求", "%", "执行器输入", "Tcap,i = Ttotal · bi · pi。", "制动请求经 ABS 滑移闭环调节及液压一阶响应输出归一化压力比例 pi ∈ [0, 1]。", "src/vehicle_controls_native.h · brakes_advance；src/vehicle_brakes.py"),
    "manual.gear": ("请求挡位", "1", "执行器输入", "同步锁合关系：ωin = ig · if · ωwheel。", "R = −1，N = 0，前进挡为 1, 2, …；换挡过程包含离合器分离、同步器摩擦调速与重新结合。", "src/powertrain.py；src/shaft_transmission.py"),
    "manual.clutch": ("离合器请求", "%", "执行器输入", "结合率限速 Δc ≤ Δt / τengage；传递容量 Tmax = c · Tclutch。", "离合器结合与分离按各自时间常数限速，瞬时传递扭矩由有限传动系统联立求解确定。", "src/powertrain.py · _advance_clutch；src/tire_drivetrain.py"),
    "vehicle": ("车辆模型", "1", "配置选择", "加载选定车型的完整整车动力学工程配置。", "各车型参数依据原厂规格、工程先验或试验标定分类归档，详见具体参数的来源说明。", "src/vehicle_designs.py；assets/game/vehicle-configs"),
    "maneuver": ("试验工况", "1", "试验协议", "按试验协议将仿真时刻与车辆状态映射为对应控制指令。", "涵盖开环制动、阶跃／正弦转向、闭环定圆、双移线、准稳态扫点及 ISO 随机路面平顺性试验。", "src/lab_experiment.py · command_at；src/lab_maneuvers.py"),
    "abs": ("ABS 防抱死开关", "bool", "电控机制开关", "纵向制动滑移率 λ ≈ (vx − r·ω) / |vx|。", "在车轮接地且高于最低介入车速时激活，依据预测滑移率与有限增减压速率独立调节各轮制动压力。", "src/vehicle_controls_native.h · brakes_advance"),
    "esc": ("ESC / 协调稳定控制", "bool", "电控机制开关", "基于实际横摆角速度、车身侧偏角与参考模型的偏差生成差动制动指令。", "支持标准分轮制动 ESC 与 ABS–DYC 协调控制两种策略，通过轮端制动力矩实现横摆稳定性控制。", "src/vehicle_stability.py；src/vehicle_controls_native.h"),
    "plot": ("遥测曲线组", "1", "信号显示选择", "切换 120 Hz 仿真记录的遥测通道组合。", "用于同图对比多组时域信号；实线与虚线分别对应同通道的参考请求与实际响应。", "src/lab_signals.py；src/ui/lab_plot.py"),
    "sweep_end": ("扫点末速", "km/h", "扫点工况参数", "vref(t) = v0 + (vend − v0) · min(1, t/T)。", "适用于准稳态定圆扫点工况；令车速沿定圆线性缓增并维持较低纵向加速度 |ax|，以辨识线性至非线性侧向区的不足转向梯度。", "src/lab_experiment.py · command_at / step；src/lab_maneuvers.py"),
    "road_class": ("ISO 随机路面等级", "1", "路谱等级输入", "Gq(n) = Gq(n0) · (n/n0)^(-2)，n0 = 0.1 m⁻¹。", "依据 ISO 8608 / GB/T 4970 A–D 级路面功率谱密度标准，合成左右轮迹随机高程路面用于平顺性仿真。", "src/iso_ride.py · generate_iso_road_profile / install_iso_road"),
    "feedback_source": ("控制器反馈源", "1", "观测闭环模式", "truth 直接读取仿真状态真值；sensor_ekf 由 15 维误差状态 EKF 融合 IMU、轮速与 GNSS 信号输出估计状态。", "用于对比理想状态反馈与带噪传感器状态估计闭环下的 ABS/ESC 及协调控制性能。", "src/chassis_observer.py · ChassisObserver / EstimatedNativeStabilityController"),
}
ALIASES = {"mu": "road_friction", "right_mu": "grass_friction", "cg": "center_of_mass_height", "tire_load": "tire_reference_load"}
CONTROL_FIELDS = {"braking": BRAKE_FIELDS, "traction": TRACTION_FIELDS, "stability": STABILITY_FIELDS}
SPECIAL = {
    "tire_aligning_enabled": ("轮胎回正力矩机制", "bool", "动力学机制开关", "等效受力点 p* = p − t·ex；回正力矩 Mz = t·Fy。", "回正力矩与轮胎接触速度、质量矩阵及车身广义冲量保持能量共轭（当前转向角由转向执行器闭环控制）。", "src/tire_aligning.py；src/tire_drivetrain.py"),
    "tire_contact_half_length": ("印痕纵向半长", "m", "轮胎几何参数", "均布压力刷毛模型气动拖距 t = a·z(3 − 2z) / [3(2 − z)]，z 为黏着区比例。", "表征接地区纵向半长 a（与胎宽及车轮半径不同），决定侧向力作用中心后移量与回正力矩幅值；需结合 Mz 特性标定。", "src/tire_aligning.py · brush_trail / aligning_frame"),
    "tire_reference_load": EDITOR_INFO["tire_load"],
    "center_of_mass_height": EDITOR_INFO["cg"],
    "road_friction": EDITOR_INFO["mu"], "grass_friction": EDITOR_INFO["right_mu"],
    "longitudinal_stiffness": ("标称纵向滑移刚度", "N/κ", "标称载荷下刚度", "Cx(Fn) = Cx0 · (Fn/Fn0)^pX；小滑移区 Fx ≈ Cx · κ。", "标称载荷 Fn0 下轮胎纵向力对纵向滑移率的初始斜率，决定加速与制动初期的纵向响应刚度。", "src/tire_properties.py · tire_stiffness"),
    "lateral_stiffness": ("前轮标称侧偏刚度", "N/rad", "标称载荷下刚度", "Cy(Fn) = Cy0 · (Fn/Fn0)^pY；小侧偏区 Fy ≈ −Cy · α。", "标称载荷 Fn0 下前轴单轮侧向力对侧偏角的初始斜率，直接影响转向灵敏度与整车不足转向梯度。", "src/tire_properties.py · tire_stiffness"),
    "rear_lateral_stiffness": ("后轮标称侧偏刚度", "N/rad", "标称载荷下刚度", "后轴单轮采用独立标称刚度 Cy0 与同源载荷幂律 pY。", "与前轮侧偏刚度共同决定前后轴侧偏角平衡及二自由度稳态不足转向特性。", "src/vehicle_tires.py · 后轴配置"),
    "suspension_spring_rates": ("轮心等效弹簧刚度", "N/m", "弹性标定参数", "弹性势能 Us = ½Σki·qi²；回复力由势能对行程梯度导出。", "定义参考位置（q = 0）处折算至轮心的线性弹簧刚度；变运动比机构下总切线刚度另计受载几何项。", "src/suspension.py；src/unsprung_contact.py；src/suspension_installation.py；src/suspension_bench.py"),
    "suspension_installation_curves": ("悬架安装位移曲线", "m", "安装运动学输入", "部件位移 xs = x0 + s(q)，瞬时运动比 rs = s′(q)；轮心等效弹力 Fw = ks·max(xs, 0)·rs。", "采用保形分段三次埃尔米特插值（PCHIP）保证位移一阶连续，数据域外沿端点切线线性外推。", "src/suspension_installation.py；src/unsprung_contact.py；src/suspension_bench.py"),
    "suspension_damper_curves": ("减振器分段力速曲线", "m/s,N", "部件特性表", "参考轮心特性表 T(v) 分段线性插值；实际阻尼力 Fw = ρ·T(ρ·dq/dt)，ρ = rd(q)/rd(0)。", "配置力速表后替代常阻尼系数；单步阻尼耗散功恒非负，数据域外沿端段斜率线性外推。", "src/suspension_damper.py；src/unsprung_contact.py；src/suspension_bench.py"),
    "suspension_spring_preloads": ("轮心等效安装预载", "N", "弹性预载参数", "F0 = rs·ks·x0；压缩势能 Uc = ½Σkw·max(q + F0/kw, 0)²。", "在参考位置（q = 0）处定义；螺旋弹簧松弛至自由长度以外时弹力为零，防倾杆与限位止挡另计。", "src/unsprung_contact.py；src/suspension_bench.py"),
    "suspension_coil_enabled": ("单向压缩螺旋弹簧", "bool", "本构模型开关", "开启时采用带安装预载的非负压缩弹簧势能模型；关闭时采用双向对称线性弹性。", "与独立轮心模型配套使用，用于准确刻画大回弹工况下弹簧卸荷松弛现象。", "src/vehicle_config.py；src/unsprung_contact.py"),
    "suspension_compression_damping": ("轮心等效压缩阻尼", "N·s/m", "阻尼标定参数", "Fd = c+ · dq/dt（dq/dt ≥ 0）；回弹行程采用伸张阻尼 c−。", "依据轮心与车身相对垂向速度计算阻尼力，可由减振器部件阻尼系数经安装运动比平方换算得到。", "src/unsprung_motion.py；src/unsprung_contact.py；src/suspension_bench.py"),
    "suspension_extension_damping": ("轮心等效伸张阻尼", "N·s/m", "阻尼标定参数", "Fd = c− · dq/dt（dq/dt < 0）；压缩行程采用压缩阻尼 c+。", "控制悬架回弹速度与车身姿态收敛特性，单步粘性耗散功率恒非负。", "src/unsprung_motion.py；src/unsprung_joint.py；src/suspension_bench.py"),
    "suspension_antiroll_rates": ("前后防倾杆刚度", "N/m", "弹性标定参数", "Ubar = ½kbar · (qL − qR)²。", "由同轴左右轮行程差产生反向抗侧倾力矩，用于调节车身侧倾角及前后轴横向载荷转移分配。", "src/suspension.py；src/suspension_contacts.py"),
    "body_inertia": ("车身转动惯量张量", "kg·m²", "惯量参数", "I_a = Σ(m_j · d_j,a² + I_j,a)。", "车身绕局部三主轴的转动惯量；已单独建模的轴向旋转部件惯量不重复计入，为空时按碰撞盒均质近似估算。", "src/vehicle.py；src/rotor_dynamics.py"),
    "torque_curve": ("发动机外特性扭矩曲线", "rpm,N·m", "动力特性输入", "相邻转速节点间分段线性插值计算满负荷有效转矩。", "实际曲轴输出转矩由外特性曲线结合瞬时节气门开度、怠速控制、发动机制动与红线断油共同确定。", "src/powertrain.py · engine_torque"),
    "braking.response_time": ("制动液压响应时间", "s", "执行器参数", "p_{n+1} = u_n + (p_n − u_n)·exp(−Δt/τ)。", "描述制动液压系统从控制指令 u 到实际轮缸压力比例 p 的一阶响应滞后；τ = 0 对应无滞后理想执行器。", "src/vehicle_controls_native.h · brakes_advance"),
    "braking.target_slip": ("ABS 目标滑移率", "1", "控制标定参数", "λ ≈ (vx − r·ω) / |vx|，结合滑移率预测值与滞环控制增减压。", "设定防抱死控制维持的目标纵向滑移率区间，以兼顾高纵向制动力与侧向转向稳定余量。", "src/vehicle_controls_native.h · brakes_advance"),
    "camber_stiffness": ("前轴外倾刚度", "N/rad", "标称载荷下刚度", "Cγ(Fn) = Cγ0 · (Fn/Fn0)^pγ；等效侧向偏移项 Cγ·sinγ。", "开启 K&C 后由轮胎外倾角产生侧向推力，并与侧偏力共同受联合滑移附着圆约束。", "src/tire_properties.py · tire_camber_stiffness；src/tire_forces.py"),
    "rear_camber_stiffness": ("后轴外倾刚度", "N/rad", "标称载荷下刚度", "后轴采用独立标称外倾刚度 Cγ0，共享轮荷幂律指数 pγ。", "前后轴外倾推力分配共同影响整车稳态侧偏角与不足转向梯度。", "src/vehicle_tires.py；src/unsprung_joint.py"),
    "camber_load_exponent": ("外倾刚度轮荷指数", "1", "轮荷幂律指数", "Cγ(Fn) = Cγ0 · (Fn/Fn0)^pγ。", "表征外倾推力刚度随法向载荷的非线性缩放规律，在标称轮荷 Fn0 处等于 Cγ0。", "src/tire_properties.py · tire_camber_stiffness"),
    "suspension_kc_enabled": ("悬架 K&C 运动学模型", "bool", "运动学机制开关", "依据静态定位角、轮心压缩行程及前轮转角实时计算各轮实际转角与外倾角。", "关闭时采用纯阿克曼前轮转向几何且忽略静动态外倾与前束变化。", "src/suspension_kc.py · wheel_kinematics"),
    "static_camber_deg": ("静态外倾角", "°", "悬架定位输入", "γ汽车 = γ0 + kγ,1·q + kγ,2·q²；轮顶外倾为正、内倾为负。", "前／后轴二元组；按左右侧对称符号映射至向右为正的轮胎坐标系倾角 γ。", "src/suspension_kc.py · wheel_kinematics"),
    "static_toe_deg": ("静态前束角", "°", "悬架定位输入", "δi = δack,i + si·(τ0 + ktoe·q)；正值表示前束。", "前／后轴单轮静态前束角二元组；左侧取 +1、右侧取 −1 叠加至实际车轮转角。", "src/suspension_kc.py · wheel_kinematics"),
    "camber_jounce_gains": ("外倾跳动一次增益", "°/m", "K&C 运动学输入", "Δγ1 = kγ,1 · q；正行程 q 表示轮心压缩。", "前／后轴外倾角随轮跳行程的线性变化率；负值使外侧受压车轮向负外倾发展以补偿车身侧倾。", "src/suspension_kc.py · wheel_kinematics"),
    "camber_jounce_quad": ("外倾跳动二次增益", "°/m²", "K&C 运动学输入", "Δγ2 = kγ,2 · q²；刻画大压缩行程下的非线性外倾特性。", "前／后轴二次项系数，与一次增益共同构成轮跳外倾多项式特性。", "src/suspension_kc.py · wheel_kinematics"),
    "camber_steer_gain": ("转向外倾增益", "°/°", "主销几何输入", "γsteer = ksteer · δi（仅前轴）；右转时正增益使轮顶右倾。", "表征主销后倾角与内倾角引起的随转向外倾角变化，仅作用于前轴左右轮。", "src/suspension_kc.py · wheel_kinematics"),
    "bump_steer_gains": ("跳动前束增益", "°/m", "K&C 运动学输入", "τ(q) = τ0 + ktoe · q；正值表示压缩行程增加前束。", "前／后轴跳动转向系数，直接影响侧倾转向特性与整车不足转向梯度。", "src/suspension_kc.py · wheel_kinematics；src/theory_baselines.py"),
}
GROUP_SOURCES = {
    "chassis": "src/vehicle.py；src/vehicle_dynamics.py；src/vehicle_steering.py",
    "powertrain": "src/powertrain.py；src/tire_drivetrain.py；src/shaft_transmission.py",
    "tires": "src/vehicle_tires.py；src/tire_properties.py；src/tire_compliance.py",
    "suspension": "src/vehicle_suspension.py；src/suspension_contacts.py",
    "electronics": "src/vehicle_brakes.py；src/vehicle_traction.py；src/vehicle_stability.py",
}

METRIC_INFO = {
    "metric.mfdd": ("充分发出平均减速度", "m/s²", "制动性能指标", "dm = (vb² − ve²) / [2(se − sb)]。", "vb、ve 分别对应制动起始参考车速的 80% 与 10%，沿水平路径交点线性插值计算；要求统计区间内车速单调递减。", "src/lab_metrics.py · mfdd"),
    "metric.yaw_gain": ("稳态横摆角速度增益", "1/s", "操稳稳态指标", "Gr = −rz / δactual。", "定义右转为正，分母为实际前轮中心转角（rad）。要求试验末 1 s 窗口内车速与转角峰峰波动 ≤ 2%、横摆角速度波动 ≤ 5%。", "src/lab_metrics.py · yaw_gain"),
    "metric.beta": ("峰值车身侧偏角", "deg", "瞬态操稳指标", "β = atan2(v右, |v前|)。", "统计水平车速大于 1 m/s 区间内车身质心速度矢量相对纵轴偏角的最大绝对值。", "src/vehicle.py · update_dynamics；src/lab_metrics.py"),
    "metric.roll": ("峰值车身侧倾角", "deg", "车身姿态指标", "统计车身刚体相对水平面侧倾角的最大绝对值。", "由整车多体动力学求解得到的车身实际侧倾姿态统计得出。", "src/vehicle.py；src/lab_metrics.py"),
}
for _axle in ("front", "rear"):
    METRIC_INFO[f"metric.ltr_{_axle}"] = ("轴左右轮荷转移率", "1", "轮荷分配指标", "LTR = (Fz,R − Fz,L) / (Fz,R + Fz,L)。", "基于单轴左右轮实际法向接触载荷计算（整轴离地时无定义），统计全程最大绝对值以评估横向载荷转移程度。", "src/lab_signals.py；src/lab_metrics.py")
for _wheel in ("fl", "fr", "rl", "rr"):
    METRIC_INFO[f"metric.utilization_{_wheel}"] = ("峰值附着利用率", "1", "轮胎受力指标", "η = √(Fx² + Fy²) / D。", "按末机械子步实际轮胎平面合力与当步联合附着力上限 D 之比计算（车轮离地时无定义）。", "src/lab_signals.py；src/lab_metrics.py")
    METRIC_INFO[f"metric.ride.min_load_{_wheel}"] = (f"最小法向轮荷 {_wheel.upper()}", "N", "接地性能指标", "Fmin = min(Fn)。", "统计完整试验区间内该车轮末机械子步法向接触载荷的最小值，用于评估轮胎接地保持能力。", "src/lab_metrics.py · ride_analysis")
for _key, _title, _unit, _formula, _use in (
    ("body_rms", "簧上垂向加速度 RMS", "m/s²", "aRMS = √(Σaz² / N)。", "基于世界 Z 轴簧上质心惯性加速度计算的未加权均方根值。"),
    ("body_peak", "簧上垂向加速度峰值", "m/s²", "apeak = max|az|。", "覆盖完整凸起激励区间的簧上质心世界 Z 轴惯性加速度最大绝对值。"),
    ("hub_peak", "轮心垂向加速度峰值", "m/s²", "apeak = max|az,i|。", "四轮独立轮心在世界 Z 轴方向惯性加速度的最大绝对值。"),
    ("max_travel", "悬架最大压缩行程", "m", "qmax = max(qi)。", "四轮相对车身导向机构的最大压缩行程，用于校核悬架动挠度工作空间。"),
    ("unload_fraction", "零轮荷采样占比", "1", "p0 = Σ[Fn,i = 0] / (4N)。", "全部离散仿真步中四轮法向载荷为零的采样比例，表征轮胎离地频度。"),
    ("load_cv_fl", "FL 动态轮荷波动比", "1", "DL = √(Σ(Fn − Fn,0)² / N) / Fn,0。", "左前轮瞬时法向载荷相对初始静载的均方根偏差与静载之比。"),
):
    METRIC_INFO["metric.ride."+_key] = (_title, _unit, "凸起激励平顺性指标", _formula, _use,
                                        "src/lab_metrics.py · ride_analysis；src/lab_signals.py")
for _key, _title, _unit, _formula, _use in (
    ("awz_rms", "Wk 加权垂向加速度 RMS", "m/s²", "awz = √(∫|Wk(f)Az(f)|²df)。", "剔除前 0.6 s 起步瞬态并去均值后，按 ISO 2631-1:1997 Wk 频域加权计算的均方根值及主观舒适度分级。"),
    ("unweighted_rms", "未加权垂向加速度 RMS", "m/s²", "aRMS = √(Σ(az − āz)² / N)。", "剔除前 0.6 s 瞬态后簧上质心垂向惯性加速度的未加权均方根值。"),
    ("sprung_peak_hz", "车身偏频主峰", "Hz", "f1 = argmax_{0.5..4Hz} PSD(az)。", "Welch 平均周期图在 0.5–4.0 Hz 簧载频段内的主共振峰值频率。"),
    ("unsprung_peak_hz", "车轮跳动频峰", "Hz", "f2 = argmax_{6..25Hz} PSD(az,hub)。", "6.0–25.0 Hz 非簧载频段内的轮跳主峰频率（需启用独立轮心模型）。"),
    ("dynamic_load_fl", "FL 相对动载", "1", "σFd/G0 = std(Fz,FL) / Fz,FL,0。", "左前轮法向载荷标准差与静态轮荷之比，反映随机路面激励下的轮胎接地稳定性。"),
    ("travel_rms_mm", "悬架动挠度 RMS", "mm", "qRMS = 1000·std(qFL)。", "左前轮悬架压缩行程的均方根波动幅值，用于评估随机路面下的工作空间余量。"),
):
    METRIC_INFO["metric.iso." + _key] = (
        _title, _unit, "ISO 随机路面平顺性", _formula, _use,
        "src/iso_ride.py · rough_road_ride_analysis；src/lab_metrics.py",
    )
for _key, _title, _unit, _formula, _use in (
    ("vmax", "理论最高车速", "km/h", "Ft(vmax) = Ff + Fw(vmax)。", "最高挡驱动力曲线与平路滚动及空气阻力曲线交点对应的理论最高车速（受红线转速约束）。"),
    ("time_0_100", "理论 0–100 加速时间", "s", "t = ∫[δ(u)·m / (Ft,max − Ff − Fw)]du。", "平路全油门理想换挡包络下的驱动加速度倒数数值积分，计入旋转质量换算系数 δ。"),
    ("max_grade", "1 挡最大爬坡度", "%", "i_max = 100·min(tanα动力, tanα附着)。", "综合 1 挡动力因数上限与驱动轴附着极限（计入坡道轴荷转移与从动轮滚阻）。"),
    ("phi0", "同步附着系数 φ0", "1", "φ0 = (L·β − b) / hg。", "前后轮同时抱死的临界附着系数；φ < φ0 时前轮先抱死，φ > φ0 时后轮先抱死。"),
    ("brake_eff", "当前 μ 制动效率", "1", "E = min(Ef(μ), Er(μ))。", "固定制动力分配 β 在当前路面附着系数 μ 下可发挥的理论制动减速度利用效率。"),
    ("stop_dist", "理论制动距离", "m", "S = v0·τb + v0²/(2a_max) − 0.5·a_max·τb²。", "计入制动液压一阶滞后时间常数 τb 的平路解析制动距离，用于与多体仿真结果对账。"),
    ("k_lin", "理论不足转向度 K_lin", "deg/g", "K = (m/L)(b/Cαf − a/Cαr) + K_K&C。", "二自由度线性单轨理论不足转向梯度；启用 K&C 时计入跳动前束与外倾推力增量。"),
    ("u_ch", "特征车速 u_ch", "km/h", "u_ch = 3.6·√(L / K_lin)。", "不足转向车辆（K_lin > 0）稳态横摆角速度增益达到最大值时对应的车速。"),
    ("k_sim", "扫点实算 K_sim", "deg/g", "δactual ≈ δ0 + K_sim · ay。", "在准稳态定圆扫点 |ay| ∈ [0.6, 3.5] m/s²、|ax| ≤ 0.65 m/s² 区间内线性回归拟合的实算不足转向梯度。"),
    ("k_delta", "实算与理论差 ΔK", "deg/g", "ΔK = K_sim − K_lin。", "仿真拟合不足转向梯度相对二自由度线性理论的偏差，体现悬架变形、载荷转移与轮胎非线性效应。"),
):
    METRIC_INFO["metric.theory." + _key] = (
        _title, _unit, "《汽车理论》解析对账", _formula, _use,
        "src/theory_baselines.py；src/lab_metrics.py",
    )


@dataclass(frozen=True)
class Explanation:
    title: str
    unit: str
    role: str
    formula: str
    use: str
    source: str


def explanation(key):
    if key in ("unsprung_enabled", "unsprung_masses", "tire_radial_stiffness", "tire_radial_damping"):
        unit, definition = VEHICLE_FIELDS[key]
        title, _, body = definition.partition("；")
        source = ("src/radial_geometry.py；src/unsprung_contact_geometry.py；src/unsprung_joint.py"
                  if key.startswith("tire_radial_") else
                  "src/vehicle_unsprung.py；src/unsprung_dynamics.py；src/unsprung_contact.py；src/unsprung_joint.py")
        return Explanation(title, unit, "轮端动力学参数",
                           "轮端动力学基础参数，具体耦合关系见上方公式。",
                           (body or title) + "。", source)
    if key in METRIC_INFO:
        return Explanation(*METRIC_INFO[key])
    if key in EDITOR_INFO:
        return Explanation(*EDITOR_INFO[key])
    if key in SPECIAL:
        return Explanation(*SPECIAL[key])
    if "." in key:
        parent, child = key.split(".")
        unit, definition = CONTROL_FIELDS[parent][child]
        group = "electronics"
    else:
        unit, definition = VEHICLE_FIELDS[key]
        group = next(group for group, names in PARAMETER_GROUPS.items() if key in names)
    title, _, body = definition.partition("；")
    return Explanation(title, unit, "工程配置参数",
                       "模型基础输入参数，直接读取车辆工程配置，无衍生计算公式。",
                       (body or title) + "。", GROUP_SOURCES[group])


def parameter_group(key):
    field = ALIASES.get(key, key)
    if field.startswith(("braking.", "traction.", "stability.")) or key in (
        "abs", "esc", "manual.brake", "feedback_source"
    ):
        return "electronics"
    if key.startswith("manual."):
        return "powertrain"
    if key == "road_class" or key.startswith("metric.iso."):
        return "suspension"
    return next((group for group, names in PARAMETER_GROUPS.items() if field in names), "chassis")


def group_parameters(group):
    names = []
    for field in PARAMETER_GROUPS[group]:
        names.append(field)
        if field in CONTROL_FIELDS:
            names.extend(f"{field}.{key}" for key in CONTROL_FIELDS[field])
    return tuple(names)

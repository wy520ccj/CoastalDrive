"""参数说明是只读文档；输入数据、公式和真实求解结果明确区分。"""

from dataclasses import dataclass

from vehicle_parameter_info import BRAKE_FIELDS, STABILITY_FIELDS, TRACTION_FIELDS, VEHICLE_FIELDS
from vehicle_parameters import PARAMETER_GROUPS

EDITOR_INFO = {
    "bump_height": ("实体凸起高度", "m", "道路几何输入", "实体路面顶面z=输入高度。", "仅轮跳工况生效；矩形台阶真实参与轮胎求交与碰撞，不按高度生成轮荷或动画。", "src/lab_experiment.py · install_bump"),
    "bump_length": ("实体凸起长度", "m", "道路几何输入", "实体沿前进方向覆盖距离d至d+L。", "宽度固定0.48m，位于左轮轨迹；前后轮依实际运动先后经过。", "src/lab_experiment.py · install_bump"),
    "bump_distance": ("凸起前缘距起点", "m", "道路几何输入", "前缘y=y初始+d。", "试验需覆盖左前和左后轮；不足时指标显示未满足条件，不能仅看前轮峰值。", "src/lab_experiment.py · install_bump"),
    "speed": ("初始车速", "km/h", "初速", "v0=输入值/3.6；独立轮心按实际加载半径和轮轴角速度初始化滚动。", "只设置试验初值，运行后车速来自实际刚体；旧刚体初始化沿用名义半径v0/r0。", "src/lab_experiment.py · LabExperiment.__init__；src/vehicle_unsprung.py · initialize_rolling"),
    "mu": ("主路面附着", "1", "轮胎峰值预算", "D=μ·Fn·(Fn/Fn0)^(pD−1)。", "μ是路面/轮胎条件的标定输入，不是由天气名称计算；Fx/Fy共用联合滑移预算。", "src/tire_properties.py · tire_grip"),
    "right_mu": ("右侧附着", "1", "对开制动", "实际接触点x≥分界线时使用右侧μ。", "仅对开附着工况生效；按接触点位置分类，不固定绑定某个轮号。", "src/lab_experiment.py · LabExperiment.__init__"),
    "duration": ("试验时长", "s", "停止条件", "Δt=1/120s；t=n·Δt，首次t≥输入时长时结束。", "每拍内部仍有两个机械子步；计算墙钟时间不是试验时间。", "src/lab_experiment.py · step / advance"),
    "onset": ("转向开始时刻", "s", "输入时序", "t<onset时δreq=0，之后施加指定转角。", "正弦工况为δreq=A·sin[2π·0.5·(t−onset)]；制动/路径工况采用各自协议。", "src/lab_experiment.py · command_at"),
    "steer": ("目标中心转角", "deg", "转向请求", "R=L/tanδ；δL/R=atan[L/(R±前轮距/2)]。", "先经过真实齿条限位/速率/二阶响应，再按Ackermann几何分成左右前轮角；不是方向盘角。", "src/vehicle_steering.py · SteeringRack.advance / wheel_angles"),
    "cg": ("质心高度", "m", "工程输入", "稳态解释式：纵向轴荷转移约m·h·ax/L。", "实际Fn来自耦合悬架求解，不直接施加此近似式；高度改变CG相对连接点，不自动推算车身惯量。", "src/vehicle_config.py · wheel_hubs；src/vehicle_suspension.py"),
    "radius": ("目标定圆半径", "m", "目标路径", "几何参考δ=atan(L/R)；跟踪曲率κ=2·ey/ld²。", "真实路径跟踪控制器产生转向和速度请求，车辆仍按物理推进，不钉在圆上。", "src/lab_maneuvers.py · target_point / path_command"),
    "tire_load": ("轮胎标定基准轮荷", "N", "固定标定量", "D=μ·Fn·(Fn/Fn0)^(pD−1)；Cx=Cx0·(Fn/Fn0)^pX；Cy=Cy0·(Fn/Fn0)^pY。", "Fn0是轮胎曲线的固定参考，不能随装载质量自动变化；并非额定承载上限。换基准需成组重标定曲线。", "src/tire_properties.py；src/joint_iteration.h · joint_load_parameters"),
    "manual.throttle": ("油门请求", "%", "执行器输入", "请求u=输入百分数/100。", "电子油门/发动机响应后读取扭矩曲线，并受TCS反馈限制；请求值不同于实际节气门。", "src/powertrain.py；src/vehicle_traction.py"),
    "manual.brake": ("制动请求", "%", "执行器输入", "Tcap_i=T总·轴分配_i·压力比例_i。", "ABS先按预测滑移/有限升降速率调节指令，再经过一阶压力响应。压力是0～1比例，不是绝对液压MPa。", "src/vehicle_controls_native.h · brakes_advance；src/vehicle_brakes.py"),
    "manual.gear": ("请求挡位", "1", "执行器输入", "锁合时ω输入=挡位比·主减比·差速平均轮速。", "R=-1、N=0、前进挡1…；实际换挡包含离合释放、同步和重新结合，不能用此锁合关系替代滑摩过程。", "src/powertrain.py；src/shaft_transmission.py"),
    "manual.clutch": ("离合请求", "%", "执行器输入", "结合量限速Δc≤Δt/结合时间；容量Tmax=c·离合容量。", "分离采用分离时间；实际传递矩由有限传动联合求解，不等于容量。", "src/powertrain.py · _advance_clutch；src/tire_drivetrain.py"),
    "vehicle": ("车辆模型", "1", "配置选择", "读取选定VehicleDesign及完整工程配置。", "原厂/实测/推导/工程初值分别记录；选中模型不等于已通过实车验证。", "src/vehicle_designs.py；assets/game/vehicle-configs"),
    "maneuver": ("试验工况", "1", "试验协议", "将试验时刻和当前Snapshot映射为VehicleCommand。", "制动为全制动；阶跃/正弦为开环转向；定圆和双移线由真实路径控制器施加输入。", "src/lab_experiment.py · command_at；src/lab_maneuvers.py"),
    "abs": ("ABS开关", "bool", "控制机制", "制动滑移≈(vx−r·ω)/|vx|；预测滑移超目标时降压。", "仅有接地和足够速度时启用；压力按有限降压/升压率更新，不能直接改车身速度。", "src/vehicle_controls_native.h · brakes_advance"),
    "esc": ("ESC开关", "bool", "控制机制", "比较实际横摆/侧偏与稳态转向参考，产生分轮制动请求。", "实际响应仍取决于轮胎、压力和联合传动；控制目标不是对车辆姿态的强制修正。", "src/vehicle_stability.py；src/vehicle_controls_native.h"),
    "plot": ("曲线组", "1", "只读显示", "读取既有120Hz记录的对应真实信号。", "不会创建第二套车辆状态或修改物理；实线/虚线用于区分请求与响应等同图变量。", "src/lab_signals.py；src/ui/lab_plot.py"),
}
ALIASES = {"mu": "road_friction", "right_mu": "grass_friction", "cg": "center_of_mass_height", "tire_load": "tire_reference_load"}
CONTROL_FIELDS = {"braking": BRAKE_FIELDS, "traction": TRACTION_FIELDS, "stability": STABILITY_FIELDS}
SPECIAL = {
    "tire_aligning_enabled": ("轮胎接触区回正机制", "bool", "模型机制开关", "受力点p*=p−t·纵向单位矢量；Mz=t·Fy。", "与同一接触速度、质量响应和冲量共轭；转向仍由理想执行器指定，不能把反力称为方向盘手感。低速没有停车扭矩模型。", "src/tire_aligning.py；src/tire_drivetrain.py"),
    "tire_contact_half_length": ("轮胎接触区纵向半长", "m", "待标定设计输入", "均布压力刷毛积分给出t=a·z(3−2z)/[3(2−z)]；z为黏着区长度比例。", "不是胎宽或轮半径；用上一子步轮荷/滑移冻结分布，力仍由现有联合曲线求解。需要轮胎Mz试验；六参数Fx/Fy拟合不能标定此量。", "src/tire_aligning.py · brush_trail / aligning_frame"),
    "tire_reference_load": EDITOR_INFO["tire_load"],
    "center_of_mass_height": EDITOR_INFO["cg"],
    "road_friction": EDITOR_INFO["mu"], "grass_friction": EDITOR_INFO["right_mu"],
    "longitudinal_stiffness": ("纵向滑移刚度", "N/κ", "固定基准下标定量", "Cx(Fn)=Cx0·(Fn/Fn0)^pX；小滑移时Fx≈Cx·κ。", "实车值需轮胎台架拟合；不是仅由轮胎尺寸计算。", "src/tire_properties.py · tire_stiffness"),
    "lateral_stiffness": ("前轮侧偏刚度", "N/rad", "固定基准下标定量", "Cy(Fn)=Cy0·(Fn/Fn0)^pY；小侧偏时Fy≈−Cy·α。", "影响转向/不足转向；需在规定Fn、胎压、温度下标定。", "src/tire_properties.py · tire_stiffness"),
    "rear_lateral_stiffness": ("后轮侧偏刚度", "N/rad", "固定基准下标定量", "后轮采用独立Cy0，同一轮荷幂律。", "改变前后刚度分配会改变操稳平衡；不能仅用停车距离辨识。", "src/vehicle_tires.py · 后轴配置"),
    "suspension_spring_rates": ("四轮弹簧刚度", "N/m", "弹性标定量", "Us=½Σki·qi²；力由势能对行程的梯度给出。", "实际固定步使用离散势能梯度并与轮胎/车体共同求法向力。", "src/suspension.py；src/suspension_contacts.py"),
    "suspension_antiroll_rates": ("前后防倾刚度", "N/m", "弹性标定量", "Ubar=½kbar·(qL−qR)²。", "左右行程差产生相反反力，改变轮荷分配及轴总附着能力。", "src/suspension.py；src/suspension_contacts.py"),
    "body_inertia": ("车身惯量", "kg·m²", "惯量输入/推导", "各轴惯量I=Σ(m·垂直轴距离²+部件自身惯量)。", "本模型已有独立轴向转子；整车随动惯量先协调这些部分，不能重复计入。None表示Bullet按碰撞形状估计。", "src/vehicle.py；src/rotor_dynamics.py"),
    "torque_curve": ("发动机扭矩曲线", "rpm,N·m", "部件输入数据", "当前转速在相邻曲线点之间线性插值。", "全负荷有效扭矩的原厂/实测锚点与估计曲线形状区分；实际输出还受节气门/怠速/损失/限速影响。", "src/powertrain.py · engine_torque"),
    "braking.response_time": ("压力响应时间常数", "s", "执行器标定量", "p_next=command+(p−command)·exp(−Δt/τ)。", "command先由ABS预测滑移/有限升降速率确定；τ=0是显式理想执行器对照。p是压力比例。", "src/vehicle_controls_native.h · brakes_advance"),
    "braking.target_slip": ("ABS目标制动滑移", "1", "控制标定量", "λ≈(vx−r·ω)/|vx|，结合预测值和滞环决定升压/降压。", "目标应按轮胎/路面试验标定；不是程序自动寻找的最优值。", "src/vehicle_controls_native.h · brakes_advance"),
}
GROUP_SOURCES = {
    "chassis": "src/vehicle.py；src/vehicle_dynamics.py；src/vehicle_steering.py",
    "powertrain": "src/powertrain.py；src/tire_drivetrain.py；src/shaft_transmission.py",
    "tires": "src/vehicle_tires.py；src/tire_properties.py；src/tire_compliance.py",
    "suspension": "src/vehicle_suspension.py；src/suspension_contacts.py",
    "electronics": "src/vehicle_brakes.py；src/vehicle_traction.py；src/vehicle_stability.py",
}

METRIC_INFO = {
    "metric.mfdd": ("充分发出平均减速度", "m/s²", "距离平均指标", "dm=(vb²−ve²)/[2(se−sb)]；速度以m/s计。", "vb=80%初速，ve=10%初速；水平路径交点线性插值，未到区间或区间增速/异常终止保留无效原因。不是瞬时减速度峰值。", "src/lab_metrics.py · mfdd"),
    "metric.yaw_gain": ("稳态横摆增益", "1/s", "工况条件指标", "Gr=−r世界z/δ实际。", "右转为正，δ为实际中心前轮角。末1s速度/角度变化≤2%、横摆≤5%才发布；不是方向盘增益，不从单点推算不足转向梯度。", "src/lab_metrics.py · yaw_gain"),
    "metric.beta": ("峰值车身侧偏", "deg", "完成步观测", "β=atan2(v右, |v前|)。", "水平速度≤1m/s未定义；峰值来自真实车身速度，不用几何转弯参考值代替。", "src/vehicle.py · update_dynamics；src/lab_metrics.py"),
    "metric.roll": ("峰值车身侧倾", "deg", "完成步观测", "读取实际刚体姿态的侧倾角，统计绝对峰值。", "本量不是道路倾角，也不是通过横向加速度乘一个常数生成的动画。", "src/vehicle.py；src/lab_metrics.py"),
}
for _axle in ("front", "rear"):
    METRIC_INFO[f"metric.ltr_{_axle}"] = ("轴左右轮荷差比", "1", "完成步轮荷指标", "LTR=(Fz,R−Fz,L)/(Fz,R+Fz,L)。", "使用完成步真实接点轮荷，右减左；整轴失去支撑时未定义。峰值取绝对值，不以此单项宣称翻车合格。", "src/lab_signals.py；src/lab_metrics.py")
for _wheel in ("fl", "fr", "rl", "rr"):
    METRIC_INFO[f"metric.utilization_{_wheel}"] = ("末子步附着利用率", "1", "施力阶段指标", "η=√(Fx²+Fy²)/D施力。", "实际末子步Fx/Fy与同阶段D共同计算；离地/预算零未定义，不把η限制为1，数值分量残差单独记录。", "src/lab_signals.py；src/lab_metrics.py")
    METRIC_INFO[f"metric.ride.min_load_{_wheel}"] = (f"最小施力轮荷 {_wheel.upper()}", "N", "接地描述指标", "Fmin=min(Fn)。", "取完整区间末机械子步实际法向力；零轮荷意味着该采样没有承载力。", "src/lab_metrics.py · ride_analysis")
for _key, _title, _unit, _formula, _use in (
    ("body_rms", "簧上垂向RMS", "m/s²", "aRMS=√(Σaz²/N)。", "完成步实际簧上CG世界Z速度差/固定步长；未做频率加权，不是座椅ISO舒适等级。"),
    ("body_peak", "簧上垂向峰值", "m/s²", "apeak=max|az|。", "簧上CG惯性加速度，包含完整凸起区间；不同初速/路谱下不可直接比较。"),
    ("hub_peak", "轮心垂向峰值", "m/s²", "apeak=max|az,i|。", "四轮实际轮心速度差/固定步长；同一末状态读数，不用车身运动复制轮跳。"),
    ("max_travel", "最大压缩行程", "m", "qmax=max(qi)。", "真实轮心相对车身导向行程，正值为压缩；用于检查悬架工作空间。"),
    ("unload_fraction", "零轮荷采样比例", "1", "p0=Σ[Fn,i=0]/(4N)。", "四轮末子步Fn=0样本的比例；不是插值后精确离地时长。"),
    ("load_cv_fl", "FL动态轮荷比", "1", "DL=√(Σ(Fn−Fn初始)²/N)/Fn初始。", "FL轮荷相对初始静载的均方根变化；不是绕运行均值的标准差。"),
):
    METRIC_INFO["metric.ride."+_key] = (_title, _unit, "完整凸起区间", _formula, _use,
                                      "src/lab_metrics.py · ride_analysis；src/lab_signals.py")


@dataclass(frozen=True)
class Explanation:
    title: str
    unit: str
    role: str
    formula: str
    use: str
    source: str


def explanation(key):
    if key in ("unsprung_enabled","unsprung_masses","tire_radial_stiffness","tire_radial_damping"):
        unit,definition = VEHICLE_FIELDS[key]
        source = ("src/radial_geometry.py；src/unsprung_contact_geometry.py；src/unsprung_joint.py"
                  if key.startswith("tire_radial_") else
                  "src/vehicle_unsprung.py；src/unsprung_dynamics.py；src/unsprung_contact.py；src/unsprung_joint.py")
        return Explanation(definition.split("；")[0],unit,"轮心与径向材料",
            "输入来自部件试验/工程设计；下式说明其力学用途，不由程序反推输入量。",definition,
            source)
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
    return Explanation(definition.split("；")[0], unit, "工程配置输入", "直接读取车辆工程数据；此量没有程序自动推算公式。",
                       definition + "。数据应由部件试验、设计或有说明的工程推导提供；本页不臆造推导式。", GROUP_SOURCES[group])


def parameter_group(key):
    field = ALIASES.get(key, key)
    if field.startswith(("braking.", "traction.", "stability.")) or key in ("abs", "esc", "manual.brake"):
        return "electronics"
    if key.startswith("manual."):
        return "powertrain"
    return next((group for group, names in PARAMETER_GROUPS.items() if field in names), "chassis")


def group_parameters(group):
    names = []
    for field in PARAMETER_GROUPS[group]:
        names.append(field)
        if field in CONTROL_FIELDS:
            names.extend(f"{field}.{key}" for key in CONTROL_FIELDS[field])
    return tuple(names)

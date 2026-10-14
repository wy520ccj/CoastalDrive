"""说明面板的数学排版源；公式对应现有算法，不参与物理计算。"""

from parameter_help import ALIASES

# 每项为独立数学行、符号释义。保留近似号，避免把解释式当成实际求解器。
FORMULAS = {
    "metric.ride.body_rms": ((
        r"a_{z,n}=\frac{v_{z,n}-v_{z,n-1}}{\Delta t},\qquad \Delta t=\frac{1}{120}\,\mathrm{s}",
        r"a_{\mathrm{RMS}}=\sqrt{\frac{1}{N}\sum_{n=1}^{N}a_{z,n}^{\,2}}",
    ), "vz：实际簧上CG世界Z速度；N：完成步数。等间隔离散样本，不做频率加权。"),
    "metric.ride.body_peak": ((r"a_{\mathrm{peak}}=\max_n |a_{z,n}|",), "az：簧上CG世界Z惯性加速度。"),
    "metric.ride.hub_peak": ((r"a_{i,z,n}=\frac{v_{i,z,n}-v_{i,z,n-1}}{\Delta t},\qquad a_{\mathrm{peak}}=\max_{i,n}|a_{i,z,n}|",), "vi：实际轮心速度；i遍历四轮。"),
    "metric.ride.max_travel": ((r"q_{\max}=\max_{i,n} q_{i,n}",), "qi：轮心相对车身导向的压缩行程；正值为压缩。"),
    "metric.ride.unload_fraction": ((r"p_0=\frac{1}{4N}\sum_{i=1}^{4}\sum_{n=1}^{N}\mathbf{1}_{F_{z,i,n}=0}",), "指示函数在末机械子步实际Fn为零时取1，否则为0。"),
    "metric.ride.min_load_fl": ((r"F_{z,i,\min}=\min_n F_{z,i,n}",), "Fz：末机械子步实际法向施力；i为指定轮。"),
    "metric.ride.load_cv_fl": ((r"D_L=\frac{\sqrt{\frac{1}{N}\sum_{n=1}^{N}(F_{z,\mathrm{FL},n}-F_{z,\mathrm{FL},0})^2}}{F_{z,\mathrm{FL},0}}",), "Fn,0：试验初始静载；该比值围绕初始值，未减运行均值。"),
    "unsprung_masses": ((
        r"m_s=M-\sum_i m_i,\qquad \mathbf{c}_s=-\frac{\sum_i m_i\mathbf{r}_i}{m_s}",
        r"\mathbf{I}_s=\mathbf{I}_0-\sum_i P(m_i,\mathbf{r}_i)-P(m_s,\mathbf{c}_s)",
    ), "mi：输入的轮端平动质量；ms/cs/Is：分出的簧上质量/CG/中央惯量。P为平行轴项，轴向转子惯量另计。"),
    "unsprung_enabled": ((
        r"\mathbf{v}_i=\mathbf{V}_s+\boldsymbol{\Omega}\times\mathbf{r}_i+u_i\mathbf{n}_i",
        r"\mathcal{M}=\mathrm{diag}(m_s\mathbf{1},\mathbf{I}_s,\mathbf{0})+\sum_i m_i\mathbf{J}_i^T\mathbf{J}_i",
    ), "轮心有真实平动惯性；Ji是轮心速度雅可比，ui是相对导向速度。与径向轮荷/Fx/Fy/有限传动同一末状态。"),
    "tire_radial_stiffness": ((
        r"F_n^*=\max\left(0,k_r\delta_++c_r\frac{\Delta\delta_+}{h}\right)",
        r"s=\|\overline{\mathbf{n}}\|,\quad F_n=sF_n^*,\quad U_r=\frac{1}{2}k_r\delta_+^2",
        r"\delta_1-\delta_0=-hs\left(\mathbf{g}_n\mathbf{z}+v_n^{\mathrm{steer}}\right)",
    ), "δ来自连续有符号距离；F*为材料系数力，Fn为实际施力大小。s由有限空间梯度计算，不是可调增益。"),
    "tire_radial_damping": ((
        r"F_n^*=\max\left(0,k_r\delta_++c_r\frac{\Delta\delta_+}{h}\right)",
        r"F_n=\|\overline{\mathbf{n}}\|F_n^*",
        r"E_{r,\mathrm{damp}}=h c_r\left(\frac{\Delta\delta_+}{h}\right)^2",
    ), "耗散采用真实末压缩变化；有限空间梯度把材料力变为实际施力。径向阻尼与悬架阻尼作用于不同自由度。"),
    "tire_contact_half_length": ((
        r"z=\min\left(1,\frac{D}{2\sqrt{(C_\kappa\kappa)^2+(C_\alpha\tan\alpha)^2}}\right)",
        r"t=\mathrm{sgn}(v_x)\frac{a z(3-2z)}{3(2-z)},\qquad M_z=t F_y",
    ), "a：接触纵向半长；z：黏着比例；零滑移取z=1。上一子步冻结分布；低速/零轮荷取t=0。"),
    "tire_aligning_enabled": ((
        r"\mathbf{p}_*=\mathbf{p}-t\mathbf{e}_x,\qquad M_z=t F_y",
        r"W_{\mathrm{steer}}=-\Delta t\, F_y\, v_{y,\mathrm{steer}}",
    ), "p*：等效受力点，不改变悬架/碰撞接点；Wsteer：指定转向运动对接触系统的输入功。"),
    "metric.mfdd": ((r"d_m=\frac{v_b^2-v_e^2}{2(s_e-s_b)},\quad v_b=0.8v_0,\quad v_e=0.1v_0",),
                    "v采用m/s，s采用m；b/e分别为80%/10%初速交点。"),
    "metric.yaw_gain": ((r"G_r=\frac{\overline{r}_{\mathrm{right}}}{\overline{\delta}_{\mathrm{actual}}}",),
                        "分子为右转横摆率rad/s，分母为实际中心前轮角rad；仅稳态窗有效。"),
    "metric.beta": ((r"\beta=\arctan\left(\frac{v_{\mathrm{right}}}{|v_{\mathrm{forward}}|}\right)",),
                    "车身局部速度分量；源码采用atan2处理象限，低速不发布。"),
    "metric.ltr_front": ((r"\mathrm{LTR}=\frac{F_{z,R}-F_{z,L}}{F_{z,R}+F_{z,L}}",),
                         "R/L：同轴右/左轮；轮荷采用完成步采样。"),
    "metric.utilization_fl": ((r"\eta=\frac{\sqrt{F_x^2+F_y^2}}{D_{\mathrm{force}}}",),
                              "Fx/Fy与D采用同一个末机械子步；预算D不是完成步sample_grip。"),
    "speed": ((r"v_0=\frac{V_0}{3.6}",
               r"\omega_{i,0}=\frac{v_{i,x}^{\mathrm{ns}}}{r_{i,\mathrm{load}}}-\boldsymbol{\Omega}\cdot\mathbf{a}_i"),
              "独立轮心模型：ns为不含自旋的实际胎面纵向速度；rload为加载半径；ai为轮轴。旧刚体初值采用名义半径v0/r0。"),
    "road_friction": ((r"D=\mu F_z\left(\frac{F_z}{F_{z0}}\right)^{p_D-1}",),
                      "D：联合附着力预算；Fz：实际轮荷；Fz0：固定标定轮荷；pD：负荷指数。"),
    "tire_reference_load": ((
        r"D=\mu F_z\left(\frac{F_z}{F_{z0}}\right)^{p_D-1}",
        r"C_\kappa=C_{\kappa0}\left(\frac{F_z}{F_{z0}}\right)^{p_\kappa}",
        r"C_\alpha=C_{\alpha0}\left(\frac{F_z}{F_{z0}}\right)^{p_\alpha}",
    ), "Fz：实际轮荷；Fz0：固定标定轮荷；D：力预算；Cκ / Cα：纵向 / 侧偏刚度；p：对应负荷指数。"),
    "longitudinal_stiffness": ((
        r"C_\kappa=C_{\kappa0}\left(\frac{F_z}{F_{z0}}\right)^{p_\kappa}",
        r"F_x\approx C_\kappa\kappa",
    ), "κ：纵向滑移率；Cκ0：基准刚度；第二式仅适用于小滑移。"),
    "lateral_stiffness": ((
        r"C_\alpha=C_{\alpha0}\left(\frac{F_z}{F_{z0}}\right)^{p_\alpha}",
        r"F_y\approx-C_\alpha\alpha",
    ), "α：侧偏角；Cα0：基准侧偏刚度；第二式仅适用于小侧偏。"),
    "duration": ((r"\Delta t=\frac{1}{120}\,\mathrm{s},\qquad t_n=n\Delta t",),
                 "n：已完成物理拍数；时长达到输入值后结束。"),
    "onset": ((r"\delta_{\mathrm{req}}=A\sin\left[2\pi f(t-t_0)\right],\quad f=0.5\,\mathrm{Hz}",),
              "正弦工况：t0前请求为零；A为转角幅值。阶跃工况在t0后施加固定转角。"),
    "steer": ((r"R=\frac{L}{\tan\delta}",
               r"\delta_{L,R}=\arctan\left(\frac{L}{R\pm t_f/2}\right)"),
              "δ：中心前轮角；L：轴距；tf：前轮距；左右符号依转弯方向分配。"),
    "center_of_mass_height": ((r"\Delta F_{z,\mathrm{axle}}\approx\frac{m h a_x}{L}",),
                              "稳态解释式：m为质量，h为质心高度，ax为纵向加速度，L为轴距。"),
    "radius": ((r"\delta_{\mathrm{ref}}=\arctan\left(\frac{L}{R}\right)",
                r"\kappa_{\mathrm{path}}=\frac{2e_y}{l_d^2}"),
               "R：目标半径；ey：前视目标横向偏差；ld：目标距离；κpath：路径曲率。"),
    "manual.throttle": ((r"u=\frac{u_{\%}}{100}",), "u：归一化油门请求；u%：编辑百分数。"),
    "manual.brake": ((r"T_{\mathrm{cap},i}=T_{\mathrm{total}}\,b_i\,p_i",),
                     "bi：第i轮轴分配份额；pi：压力比例；Tcap：容量，不等于实际传递矩。"),
    "manual.gear": ((r"\omega_{\mathrm{in}}=i_g i_f\overline{\omega}_{\mathrm{wheel}}",),
                    "仅锁合关系：ig为挡位比，if为主减比，平均轮速由差速机构定义。"),
    "manual.clutch": ((r"\Delta c\leq\frac{\Delta t}{\tau_{\mathrm{engage}}},\qquad T_{\max}=c T_{\mathrm{clutch}}",),
                      "c：结合比例；τengage：结合时间；Tclutch：满结合容量。"),
    "braking.response_time": ((r"p_{n+1}=u_n+(p_n-u_n)\exp\left(-\frac{\Delta t}{\tau}\right)",),
                              "p：压力比例；u：ABS调节后的指令；τ：响应时间常数；Δt：控制步长。"),
    "braking.target_slip": ((r"\lambda\approx\frac{v_x-r\omega}{|v_x|}",),
                            "λ：制动滑移；vx：接触点纵向速度；rω：轮缘速度；仅在足够速度时启用。"),
    "suspension_spring_rates": ((r"U_s=\frac{1}{2}\sum_i k_i q_i^2,\qquad Q_i=-\frac{\partial U_s}{\partial q_i}",),
                                "ki：弹簧刚度；qi：行程；Q：与行程对应的恢复力。"),
    "suspension_antiroll_rates": ((r"U_{\mathrm{bar}}=\frac{1}{2}k_{\mathrm{bar}}(q_L-q_R)^2",),
                                  "qL / qR：同轴左右行程；kbar：防倾刚度。"),
    "body_inertia": ((r"I_a=\sum_j\left(m_j d_{j,a}^{\,2}+I_{j,a}\right)",),
                     "a：指定转轴；j：部件；d：部件质心到轴的垂距；Ij,a：部件自身惯量。"),
    "torque_curve": ((r"T(\omega)=T_1+\frac{\omega-\omega_1}{\omega_2-\omega_1}(T_2-T_1)",),
                     "相邻曲线点之间线性插值；ω与曲线横坐标采用相同转速单位。"),
}


def formula_key(key):
    field = ALIASES.get(key, key)
    if field == "rear_lateral_stiffness":
        return "lateral_stiffness"
    if field == "abs":
        return "braking.target_slip"
    if field == "metric.ltr_rear":
        return "metric.ltr_front"
    if field.startswith("metric.utilization_"):
        return "metric.utilization_fl"
    if field.startswith("metric.ride.min_load_"):
        return "metric.ride.min_load_fl"
    return field if field in FORMULAS else None

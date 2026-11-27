"""参数说明面板的数学公式源与符号释义；仅用于排版渲染。"""

from parameter_help import ALIASES

# 每项为独立 TeX 公式行元组与对应中文符号释义。
FORMULAS = {
    "metric.ride.body_rms": ((
        r"a_{z,n}=\frac{v_{z,n}-v_{z,n-1}}{\Delta t},\qquad \Delta t=\frac{1}{120}\,\mathrm{s}",
        r"a_{\mathrm{RMS}}=\sqrt{\frac{1}{N}\sum_{n=1}^{N}a_{z,n}^{\,2}}",
    ), "vz：簧上质心世界 Z 轴速度；N：有效仿真步数。等间隔离散样本未加权统计。"),
    "metric.ride.body_peak": ((r"a_{\mathrm{peak}}=\max_n |a_{z,n}|",), "az：簧上质心世界 Z 轴惯性加速度。"),
    "metric.ride.hub_peak": ((r"a_{i,z,n}=\frac{v_{i,z,n}-v_{i,z,n-1}}{\Delta t},\qquad a_{\mathrm{peak}}=\max_{i,n}|a_{i,z,n}|",), "vi：第 i 轮轮心速度；i 遍历四轮。"),
    "metric.ride.max_travel": ((r"q_{\max}=\max_{i,n} q_{i,n}",), "qi：轮心相对车身导向机构的压缩行程（正值表示压缩）。"),
    "metric.ride.unload_fraction": ((r"p_0=\frac{1}{4N}\sum_{i=1}^{4}\sum_{n=1}^{N}\mathbf{1}_{F_{z,i,n}=0}",), "指示函数在末机械子步法向载荷为零时取 1，其余时刻取 0。"),
    "metric.ride.min_load_fl": ((r"F_{z,i,\min}=\min_n F_{z,i,n}",), "Fz：第 i 轮末机械子步的法向接触载荷。"),
    "metric.ride.load_cv_fl": ((r"D_L=\frac{\sqrt{\frac{1}{N}\sum_{n=1}^{N}(F_{z,\mathrm{FL},n}-F_{z,\mathrm{FL},0})^2}}{F_{z,\mathrm{FL},0}}",), "Fz,FL,0：左前轮初始静态轮荷；分子为相对初始静载的均方根偏差。"),
    "unsprung_masses": ((
        r"m_s=M-\sum_i m_i,\qquad \mathbf{c}_s=-\frac{\sum_i m_i\mathbf{r}_i}{m_s}",
        r"\mathbf{I}_s=\mathbf{I}_0-\sum_i P(m_i,\mathbf{r}_i)-P(m_s,\mathbf{c}_s)",
    ), "mi：单轮簧下平动质量；ms、cs、Is：分离后的簧上质量、质心偏移及中心惯量张量；P 为平行轴移轴项。"),
    "unsprung_enabled": ((
        r"\mathbf{v}_{i,1}=\mathbf{J}_{i,0}\mathbf{z}_1+\mathbf{b}_i",
        r"\mathcal{M}=\mathrm{diag}(m_s\mathbf{1},\mathbf{I}_s,\mathbf{0})+\sum_i m_i\mathbf{J}_i^T\mathbf{J}_i",
    ), "Ji：由簧上平动、角速度叉乘力臂及相对行程构成的运动学雅可比；下标 0、1 分别表示步初与步末；bi 为导向约束位置修正项。"),
    "tire_radial_stiffness": ((
        r"F_n^*=\max\left(0,k_r\delta_++c_r\frac{\Delta\delta_+}{h}\right)",
        r"s=\|\overline{\mathbf{n}}\|,\quad F_n=sF_n^*,\quad U_r=\frac{1}{2}k_r\delta_+^2",
        r"\delta_1-\delta_0=-hs\left(\mathbf{g}_n\mathbf{z}+v_n^{\mathrm{steer}}+\widehat{\mathbf{n}}\cdot\mathbf{b}_i\right)",
    ), "δ：轮胎径向有符号压缩量；F*：材料本构法向力；s：接触距离空间梯度模长；Fn：作用轮心的等效法向载荷。"),
    "tire_radial_damping": ((
        r"F_n^*=\max\left(0,k_r\delta_++c_r\frac{\Delta\delta_+}{h}\right)",
        r"F_n=\|\overline{\mathbf{n}}\|F_n^*",
        r"E_{r,\mathrm{damp}}=h c_r\left(\frac{\Delta\delta_+}{h}\right)^2",
    ), "cr：轮胎径向阻尼系数；h：机械子步长；Er,damp 为单子步轮胎径向阻尼耗散功。"),
    "tire_contact_half_length": ((
        r"z=\min\left(1,\frac{D}{2\sqrt{(C_\kappa\kappa)^2+(C_\alpha\tan\alpha)^2}}\right)",
        r"t=\mathrm{sgn}(v_x)\frac{a z(3-2z)}{3(2-z)},\qquad M_z=t F_y",
    ), "a：接地区纵向半长；z：黏着区比例（零滑移取 1）；t：气动拖距（低速或离地时取 0）。"),
    "tire_aligning_enabled": ((
        r"\mathbf{p}_*=\mathbf{p}-t\mathbf{e}_x,\qquad M_z=t F_y",
        r"W_{\mathrm{steer}}=-\Delta t\, F_y\, v_{y,\mathrm{steer}}",
    ), "p*：考虑气动拖距后的等效侧向力作用点；Wsteer：指定转向运动对轮胎接触系统所做的功。"),
    "metric.mfdd": ((r"d_m=\frac{v_b^2-v_e^2}{2(s_e-s_b)},\quad v_b=0.8v_0,\quad v_e=0.1v_0",),
                    "v 单位为 m/s，s 单位为 m；下标 b、e 分别对应初速 80% 与 10% 处的路径插值交点。"),
    "metric.yaw_gain": ((r"G_r=\frac{\overline{r}_{\mathrm{right}}}{\overline{\delta}_{\mathrm{actual}}}",),
                        "分子为右转横摆角速度均值（rad/s），分母为实际中心前轮转角均值（rad），于末段稳态窗口内计算。"),
    "metric.beta": ((r"\beta=\arctan\left(\frac{v_{\mathrm{right}}}{|v_{\mathrm{forward}}|}\right)",),
                    "车身局部横向与纵向速度分量之比；实现中采用 atan2 处理象限，水平车速低于 1 m/s 时不统计。"),
    "metric.ltr_front": ((r"\mathrm{LTR}=\frac{F_{z,R}-F_{z,L}}{F_{z,R}+F_{z,L}}",),
                         "Fz,R、Fz,L 分别为同轴右、左轮的法向接触载荷。"),
    "metric.utilization_fl": ((r"\eta=\frac{\sqrt{F_x^2+F_y^2}}{D_{\mathrm{force}}}",),
                              "Fx、Fy 与附着上限 Dforce 均取自同一末机械子步的轮胎受力状态。"),
    "speed": ((r"v_0=\frac{V_0}{3.6}",
               r"\omega_{i,0}=\frac{v_{i,x}^{\mathrm{ns}}}{r_{i,\mathrm{load}}}-\boldsymbol{\Omega}\cdot\mathbf{a}_i"),
              "独立轮心模式下按不含自旋的胎面纵向速度与加载半径初始化角速度；常规刚体模式按名义半径 v0/r0 初始化。"),
    "road_friction": ((r"D=\mu F_z\left(\frac{F_z}{F_{z0}}\right)^{p_D-1}",),
                      "D：联合滑移附着力上限；Fz：瞬时法向轮荷；Fz0：标称参考轮荷；pD：峰值负荷指数。"),
    "tire_reference_load": ((
        r"D=\mu F_z\left(\frac{F_z}{F_{z0}}\right)^{p_D-1}",
        r"C_\kappa=C_{\kappa0}\left(\frac{F_z}{F_{z0}}\right)^{p_\kappa}",
        r"C_\alpha=C_{\alpha0}\left(\frac{F_z}{F_{z0}}\right)^{p_\alpha}",
    ), "Fz：瞬时法向轮荷；Fz0：固定标称参考轮荷；D：附着上限；Cκ、Cα：纵向与侧偏刚度；p：对应负荷指数。"),
    "longitudinal_stiffness": ((
        r"C_\kappa=C_{\kappa0}\left(\frac{F_z}{F_{z0}}\right)^{p_\kappa}",
        r"F_x\approx C_\kappa\kappa",
    ), "κ：纵向滑移率；Cκ0：标称纵向滑移刚度；第二式为小滑移线性区近似。"),
    "lateral_stiffness": ((
        r"C_\alpha=C_{\alpha0}\left(\frac{F_z}{F_{z0}}\right)^{p_\alpha}",
        r"F_y\approx-C_\alpha\alpha",
    ), "α：轮胎侧偏角；Cα0：标称侧偏刚度；第二式为小侧偏角线性区近似。"),
    "duration": ((r"\Delta t=\frac{1}{120}\,\mathrm{s},\qquad t_n=n\Delta t",),
                 "n：已完成固定仿真步数；仿真时长达到设定值 T 时终止。"),
    "onset": ((r"\delta_{\mathrm{req}}=A\sin\left[2\pi f(t-t_0)\right],\quad f=0.5\,\mathrm{Hz}",
               r"u_{\mathrm{brake,req}}=\mathbb{1}_{t\geq t_0}"),
              "第一式为正弦转向激励（t < t0 时请求为零）；第二式为延迟制动阶跃请求，实际轮缸压力保留液压滞后与 ABS 调节。"),
    "steer": ((r"R=\frac{L}{\tan\delta}",
               r"\delta_{L,R}=\arctan\left(\frac{L}{R\pm t_f/2}\right)"),
              "δ：虚拟前轴中心转角；L：轴距；tf：前轴轮距；左右轮符号按转向方向分配。"),
    "center_of_mass_height": ((r"\Delta F_{z,\mathrm{axle}}\approx\frac{m h a_x}{L}",),
                              "稳态纵向轴荷转移估算式：m 为整车质量，h 为质心高度，ax 为纵向加速度，L 为轴距。"),
    "radius": ((r"\delta_{\mathrm{ref}}=\arctan\left(\frac{L}{R}\right)",
                r"\kappa_{\mathrm{path}}=\frac{2e_y}{l_d^2}"),
               "R：目标圆半径；ey：前视点横向偏差；ld：前视距离；κpath：纯追踪控制期望曲率。"),
    "manual.throttle": ((r"u=\frac{u_{\%}}{100}",), "u：归一化油门请求；u%：输入百分数。"),
    "manual.brake": ((r"T_{\mathrm{cap},i}=T_{\mathrm{total}}\,b_i\,p_i",),
                     "bi：第 i 轮制动力分配份额；pi：实际制动压力比例；Tcap 为轮端制动容量上限。"),
    "manual.gear": ((r"\omega_{\mathrm{in}}=i_g i_f\overline{\omega}_{\mathrm{wheel}}",),
                    "挡位完全同步锁合时的转速关系：ig 为挡位传动比，if 为主减速比，平均轮速由差速机构定义。"),
    "manual.clutch": ((r"\Delta c\leq\frac{\Delta t}{\tau_{\mathrm{engage}}},\qquad T_{\max}=c T_{\mathrm{clutch}}",),
                      "c：离合器结合度；τengage：结合行程时间；Tclutch：完全结合容量。"),
    "braking.response_time": ((r"p_{n+1}=u_n+(p_n-u_n)\exp\left(-\frac{\Delta t}{\tau}\right)",),
                              "p：实际压力比例；u：经 ABS 调节后的目标压力指令；τ：液压一阶时间常数；Δt：控制步长。"),
    "braking.target_slip": ((r"\lambda\approx\frac{v_x-r\omega}{|v_x|}",),
                            "λ：纵向制动滑移率；vx：接地点纵向速度；rω：轮缘线速度。"),
    "suspension_spring_rates": ((
        r"U_s=\frac{1}{2}\sum_i k_i q_i^2,\qquad Q_i=-\frac{\partial U_s}{\partial q_i}",
        r"q_{i,1}=q_{i,0}+\mathbf{r}_{i,1}\cdot\mathbf{g}_1-\mathbf{r}_{i,0}\cdot\mathbf{g}_0",
        r"r_s=\frac{\mathrm{d}x_s}{\mathrm{d}q},\qquad k_w=r_s^2 k_s",
    ), "q：轮心压缩行程；r：簧上质心指向轮心矢量；g：导向单位矢量；xs、rs、ks、kw 分别为弹簧位移、运动比、部件刚度与轮心等效刚度。"),
    "suspension_compression_damping": ((
        r"\dot{q}_i=\mathbf{g}_1\cdot\left(\mathbf{v}_{i,1}-\mathbf{V}_{s,1}-\boldsymbol{\Omega}_1\times\mathbf{r}_{i,1}\right)",
        r"F_{d,i}=c_i^{\pm}\dot{q}_i,\qquad E_d=h\sum_i c_i^{\pm}\dot{q}_i^{\,2}\geq 0",
        r"r_d=\frac{\mathrm{d}x_d}{\mathrm{d}q},\qquad c_w^{\pm}=r_d^2 c_d^{\pm}",
    ), "c+、c− 分别为压缩与伸张等效阻尼系数；xd、rd、cd、cw 分别为减振器活塞行程、运动比、部件阻尼与轮心等效阻尼。"),
    "suspension_spring_preloads": ((
        r"a_i=q_i+\frac{F_{0,i}}{k_{w,i}},\qquad U_c=\frac{1}{2}\sum_i k_{w,i}[a_i]_+^2",
        r"F_{c,i}=k_{w,i}[a_i]_+,\qquad k_{t,i}=k_{w,i}\,\mathbf{1}_{a_i>0}",
        r"F_{0,i}=r_{s,i}k_{s,i}x_{0,i},\qquad k_{w,i}=r_{s,i}^2k_{s,i}",
    ), "[a]+ = max(a, 0)；q 为轮心行程，x0 为参考位安装压缩量，F0 为轮心等效预载；单向压缩螺旋弹簧模式下启用。"),
    "suspension_installation_curves": ((
        r"x_s(q)=x_0+s(q),\qquad U_c=\frac{1}{2}k_s[x_s(q)]_+^2",
        r"F_w=k_s[x_s]_+r_s,\qquad k_t=k_s(r_s^2+x_s r_s')\mathbf{1}_{x_s>0}",
        r"k_s=\frac{k_{w,0}}{r_s(0)^2},\qquad x_0=\frac{F_0}{k_s r_s(0)}",
    ), "s(q) 为弹簧位移增量，rs = s′(q)；总切线刚度 kt 包含受载几何项 ks·xs·rs′，kw,0 对应 q = 0 处参考刚度。"),
    "installation_damping": ((
        r"v_d=r_d(q)\dot q,\qquad F_{d,w}=c_d^{\pm}r_d(q)^2\dot q",
        r"c_d^{\pm}=\frac{c_{w,0}^{\pm}}{r_d(0)^2},\qquad P_d=c_d^{\pm}v_d^2\geq0",
    ), "rd(q) 为减振器位移对轮心行程的导数；由参考轮心阻尼 cw,0 折算回部件阻尼 cd，再按瞬时运动比映射至轮心。"),
    "suspension_damper_curves": ((
        r"T(v)=T_j+\frac{T_{j+1}-T_j}{v_{j+1}-v_j}(v-v_j)",
        r"\rho(q)=\frac{r_d(q)}{r_d(0)},\qquad v_* =\rho\dot q,\quad F_{d,w}=\rho T(v_*)",
        r"P_d=F_{d,w}\dot q=T(v_*)v_*\geq0",
    ), "T(v) 为 q = 0 处参考轮心分段力速特性表；瞬时运动比 ρ(q) 同步缩放速度与阻尼力，区间外沿端段斜率外推。"),
    "suspension_antiroll_rates": ((r"U_{\mathrm{bar}}=\frac{1}{2}k_{\mathrm{bar}}(q_L-q_R)^2",),
                                  "qL、qR：同轴左右轮行程；kbar：等效轮心防倾刚度。"),
    "body_inertia": ((r"I_a=\sum_j\left(m_j d_{j,a}^{\,2}+I_{j,a}\right)",),
                     "a：参考转轴；j：部件索引；d：部件质心至转轴的垂距；Ij,a：部件自身主惯量。"),
    "torque_curve": ((r"T(\omega)=T_1+\frac{\omega-\omega_1}{\omega_2-\omega_1}(T_2-T_1)",),
                     "相邻转速节点间分段线性插值；ω 与曲线横坐标单位一致。"),
    "camber_stiffness": ((
        r"C_\gamma(F_z)=C_{\gamma 0}\left(\frac{F_z}{F_{z0}}\right)^{p_\gamma}",
        r"q_y=\frac{C_\alpha\tan\alpha+C_\gamma\sin\gamma}{D}",
    ), "Cγ0：标称外倾刚度；pγ：外倾轮荷指数；γ：向右为正的轮胎倾角；外倾推力随联合滑移受附着上限 D 约束。"),
    "suspension_kc_enabled": ((
        r"\delta_i=\delta_{\mathrm{ack},i}+s_i\left(\tau_0+k_{\mathrm{toe}}q_i\right)",
        r"\gamma_i=\gamma_0+k_{\gamma,1}q_i+k_{\gamma,2}q_i^2,\qquad \gamma_{\mathrm{tire},i}=-s_i\gamma_i+k_{\mathrm{steer}}\delta_i",
    ), "si ∈ {+1, −1} 分别对应左、右轮；qi 为轮心压缩行程；ksteer 仅作用于前轴，统一映射至向右为正的轮胎倾角。"),
    "static_camber_deg": ((
        r"\gamma_{\mathrm{auto}}=\gamma_0+k_{\gamma,1}q+k_{\gamma,2}q^2",
        r"\gamma_{\mathrm{tire}}=-s\gamma_{\mathrm{auto}}+k_{\mathrm{steer}}\delta",
    ), "γ0：静态外倾角；kγ,1、kγ,2：一次与二次外倾压缩增益；s 为左右侧符号，轮顶右倾为轮胎正倾角。"),
    "static_toe_deg": ((
        r"\tau(q)=\tau_0+k_{\mathrm{toe}}q,\qquad \delta_i=\delta_{\mathrm{ack},i}+s_i\tau(q_i)",
    ), "τ0：静态单轮前束角（前束为正）；ktoe：跳动前束增益；si 取 +1（左轮）或 −1（右轮）。"),
    "sweep_end": ((
        r"v_{\mathrm{ref}}(t)=\frac{1}{3.6}\left[v_0+(v_{\mathrm{end}}-v_0)\min\left(1,\frac{t}{T}\right)\right]",
    ), "v0：初速（km/h）；vend：扫点末速（km/h）；T：试验时长（s），通过缓增车速保持准稳态条件。"),
    "road_class": ((
        r"G_q(n)=G_q(n_0)\left(\frac{n}{n_0}\right)^{-W},\qquad n_0=0.1\,\mathrm{m}^{-1},\quad W=2",
    ), "Gq(n0) 按 ISO 8608 A–D 级分别取 16、64、256、1024 × 10⁻⁶ m³，由 256 条对数等比谐波合成左右轮迹。"),
    "feedback_source": ((
        r"\hat{\mathbf{x}}_{k|k}=\hat{\mathbf{x}}_{k|k-1}+\mathbf{K}_k(\mathbf{z}_k-\mathbf{h}(\hat{\mathbf{x}}_{k|k-1}))",
        r"\hat{\mu}_{k+1}=\hat{\mu}_k+\alpha_\mu\left(\frac{\sqrt{a_x^2+a_y^2}}{g}-\hat{\mu}_k\right)",
    ), "sensor_ekf 采用 15 维误差状态 EKF 融合 IMU、轮速与 GNSS 信号，并基于滑移门控在线辨识路面峰值附着系数 μ。"),
    "metric.iso.awz_rms": ((
        r"a_{wz}=\sqrt{\frac{1}{N}\sum_{n=1}^{N}\left[\mathcal{F}^{-1}\left(W_k(f)\mathcal{F}(a_z-\bar{a}_z)\right)\right]_n^2}",
    ), "Wk(f) 为 ISO 2631-1:1997 垂向全身振动频率加权函数；剔除前 0.6 s 瞬态后计算 RMS 与舒适度分级。"),
    "metric.iso.unweighted_rms": ((
        r"a_{z,\mathrm{RMS}}=\sqrt{\frac{1}{N}\sum_{n=1}^{N}(a_{z,n}-\bar{a}_z)^2}",
    ), "az：去均值后的簧上质心世界 Z 轴惯性加速度（未加权）。"),
    "metric.iso.sprung_peak_hz": ((
        r"f_{\mathrm{peak}}=\arg\max_{f\in[f_{\min},f_{\max}]}S_{aa}(f)",
    ), "Saa(f)：50% 重叠 Hann 窗 Welch 平均功率谱；车身偏频区间 0.5–4.0 Hz，轮跳区间 6.0–25.0 Hz。"),
    "metric.iso.dynamic_load_fl": ((
        r"\frac{\sigma_{F_d}}{G_0}=\frac{\sqrt{\frac{1}{N}\sum_{n=1}^{N}(F_{z,\mathrm{FL},n}-\bar{F}_{z,\mathrm{FL}})^2}}{F_{z,\mathrm{FL},0}}",
    ), "Fz,FL,0 为左前轮静态轮荷 G0，比值表征随机路面下轮胎法向动载波动幅值。"),
    "metric.iso.travel_rms_mm": ((
        r"q_{\mathrm{RMS}}=1000\sqrt{\frac{1}{N}\sum_{n=1}^{N}(q_{\mathrm{FL},n}-\bar{q}_{\mathrm{FL}})^2}",
    ), "qFL：左前轮悬架压缩行程，乘以 1000 换算为毫米（mm）。"),
    "metric.theory.vmax": ((
        r"F_t(v_{\max})=\frac{T_e i_g i_0 \eta_T}{r}=m g f\cos\alpha+\frac{1}{2}\rho C_D A v_{\max}^2+m g\sin\alpha",
    ), "最高挡驱动力与滚动、空气及坡道阻力平衡车速；若红线处仍有驱动余力则取红线车速。"),
    "metric.theory.time_0_100": ((
        r"\delta_k=1+\frac{4I_w+(I_e+I_{\mathrm{in}})i_g^2i_0^2\eta_T}{mr^2},\qquad t=\int_0^{100/3.6}\frac{\delta_k m}{F_{t,\max}-F_f-F_w}\mathrm{d}u",
    ), "沿各前进挡最大驱动加速度包络对车速数值积分得到的理论 0–100 km/h 加速时间。"),
    "metric.theory.max_grade": ((
        r"D_1=\frac{F_{t1}-F_w}{mg},\qquad i_{\max}=\min\left(\tan\alpha_{\mathrm{drive}},\tan\alpha_{\mathrm{adhesion}}\right)\times 100\%",
    ), "综合 1 挡动力因数上限与驱动轴附着极限（含坡道轴荷转移与从动轮滚阻）。"),
    "metric.theory.phi0": ((
        r"\varphi_0=\frac{L\beta-b}{h_g}",
    ), "L：轴距；β：前轴制动力分配份额；b：质心至后轴距离；hg：质心高度。"),
    "metric.theory.brake_eff": ((
        r"E_f(\varphi)=\frac{b/L}{\beta-\varphi h_g/L},\qquad E_r(\varphi)=\frac{a/L}{(1-\beta)+\varphi h_g/L},\qquad E=\min(E_f,E_r)",
    ), "按固定分配比 β 在当前路面附着系数 μ 下计算的前后轴附着利用效率较小值。"),
    "metric.theory.stop_dist": ((
        r"S=v_0\tau_b+\frac{v_0^2}{2a_{\max}}-\frac{1}{2}a_{\max}\tau_b^2",
    ), "τb 为制动器一阶响应时间常数；开启 ABS 时 amax = min(μg, Tmax/(mr))，无 ABS 时乘以制动效率 E。"),
    "metric.theory.k_lin": ((
        r"K_{\mathrm{lin}}=\frac{m}{L}\left(\frac{b}{C_{\alpha f}}-\frac{a}{C_{\alpha r}}\right)+K_{\mathrm{KC}}",
    ), "Cαf、Cαr 为静态轴荷下前后轴总侧偏刚度；启用 K&C 时叠加侧倾转向与外倾推力增量并换算为 deg/g。"),
    "metric.theory.u_ch": ((
        r"u_{\mathrm{ch}}=3.6\sqrt{\frac{L}{K_{\mathrm{lin}}}}\quad (K_{\mathrm{lin}}>0)",
    ), "不足转向车辆的特征车速，对应稳态横摆角速度增益最大值。"),
    "metric.theory.k_sim": ((
        r"\delta_{\mathrm{actual}}\approx \delta_0+K_{\mathrm{sim}}a_y\qquad \left(|a_y|\in[0.6,3.5]\,\mathrm{m/s^2},\ |a_x|\leq 0.65\,\mathrm{m/s^2}\right)",
    ), "基于准稳态定圆扫点数据，对实际前轮中心转角与侧向加速度执行最小二乘线性回归。"),
    "metric.theory.k_delta": ((
        r"\Delta K=K_{\mathrm{sim}}-K_{\mathrm{lin}}",
    ), "准稳态扫点实算不足转向梯度与二自由度线性理论预测之差（deg/g）。"),
}


def formula_key(key):
    field = ALIASES.get(key, key)
    if field == "suspension_coil_enabled":
        return "suspension_spring_preloads"
    if field == "suspension_extension_damping":
        return "suspension_compression_damping"
    if field == "rear_lateral_stiffness":
        return "lateral_stiffness"
    if field in ("rear_camber_stiffness", "camber_load_exponent"):
        return "camber_stiffness"
    if field in ("camber_jounce_gains", "camber_jounce_quad", "camber_steer_gain"):
        return "static_camber_deg"
    if field == "bump_steer_gains":
        return "static_toe_deg"
    if field == "abs":
        return "braking.target_slip"
    if field == "metric.ltr_rear":
        return "metric.ltr_front"
    if field.startswith("metric.utilization_"):
        return "metric.utilization_fl"
    if field.startswith("metric.ride.min_load_"):
        return "metric.ride.min_load_fl"
    if field == "metric.iso.unsprung_peak_hz":
        return "metric.iso.sprung_peak_hz"
    return field if field in FORMULAS else None

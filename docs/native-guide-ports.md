# 原生导向的有限步动量与功

本节点对齐共同机械求解和实际Bullet推进。轮心仍是同一世界中的四个真实点质量，车身仍由原生刚体推进；预测不写回位置或速度。连续机械算子的向心/科氏项保留，修正的是把连续加速度公式直接叠加在原生冻结约束步上的混用。

## 同一构型的有限步

Bullet 2.84的6DOF线性行在步初构型计算雅可比，横向位置误差通过ERP生成相对速度。依据[官方约束源码](https://raw.githubusercontent.com/bulletphysics/bullet3/2.84/src/BulletDynamics/ConstraintSolver/btGeneric6DofConstraint.cpp)，当前两锁止轴的数值速度为

$$
\mathbf b_i=-\frac{\mathrm{ERP}}{h}\mathbf R_0(e_{i,x},e_{i,y},0)^T,
\qquad \mathbf v_{i,1}=\mathbf J_{i,0}\mathbf z_1+\mathbf b_i.
$$

本项目ERP沿用0.2；误差从实际原生导向读取。它是求解器的位置稳定化量，不是悬架阻尼、轮胎参数或可调执行器。自由轴不参与纠偏。旧实际轮心速度完整保留，不先投影为导向速度。

以车身/行程/转子共同末速度为未知量，轮心部分的有限动量关系为

$$
\mathcal M_0\mathbf z_1+
\sum_i\mathbf J_{i,0}^T m_i\mathbf b_i-\mathbf p_0
=h\mathbf Q_1+\mathbf P_{\mathrm{gyro}}.
$$

初始广义动量由实际车身、轮心和从动轴速度构造。原生约束在相邻步改变方向，并从实际旧轮心速度承接转动的几何惯性；在这个冻结行离散中，再减连续模型的轮心几何偏置会重复计入。连续瞬时加速度算子仍保留完整惯性偏置，供理论验证使用。

无外力、无路面、0.5rad/s自由转动的真实五刚体测试仍产生约−0.25的向心加速度系数。故本修复依据推进方程，而不是为了让结果变小关闭惯性机制。具体误差和执行输入见[证据](evidence/SIM-UNSPRUNG-01/guide-ports/README.md)。

## 接触与数值功

有限接触末轮心位置、胎面速度和径向离散梯度都使用同一个带偏置的速度。法向压缩关系改为

$$
\delta_1-\delta_0=-hs\left(
\mathbf g_n\mathbf z_1+v_n^{\mathrm{steer}}+\widehat{\mathbf n}\cdot\mathbf b_i\right).
$$

指定转向是执行器输入，导向纠偏是数值约束量，两者分别记账。由轮心动量计算约束冲量和数值功：

$$
\mathbf P_i^c=m_i(\mathbf v_{i,1}-\mathbf v_{i,0})-h\mathbf F_i^{\mathrm{physical}},
\qquad W_c=\sum_i\mathbf P_i^c\cdot\mathbf b_i.
$$

物理力包含实际轮胎、悬架、重力及外力。共同动能账也采用实际旧轮心速度和带偏置末速度。真实储能诊断同时保留原始残差、数值导向功和扣除明确数值功后的残差，不把纠偏功改名为真实耗散或道路输入。

## 刚体陀螺顺序

原生提交先施加真实力矩冲量，随后Bullet按此时角速度做一次隐式body-gyro Newton更新，最后由约束行传递导向反力。依据[官方刚体源码](https://raw.githubusercontent.com/bulletphysics/bullet3/2.84/src/BulletDynamics/Dynamics/btRigidBody.cpp)和[实际求解顺序](https://raw.githubusercontent.com/bulletphysics/bullet3/2.84/src/BulletDynamics/ConstraintSolver/btSequentialImpulseConstraintSolver.cpp)，世界惯量形式为

$$
\mathbf A=\mathbf I+h\left([\boldsymbol\omega_f]_\times\mathbf I-[\mathbf I\boldsymbol\omega_f]_\times\right),
\qquad \Delta\mathbf P_{\mathrm{gyro}}
=-\mathbf I\mathbf A^{-1}h(\boldsymbol\omega_f\times\mathbf I\boldsymbol\omega_f).
$$

共同残差内的自由角速度来自同一未知物理力矩冲量，排除尚未由原生加入的外部持续力矩。这个函数只预测原生增量；实际gyro仍由唯一原生世界执行一次。其有限步功单列，不当作外界做功或真实耗散。

## 工程用途与验收

企业关注轮荷保持、悬架工作空间、簧下质量对轮跳/接地的影响、ABS利用率和制动距离。若求解预测与实际推进不一致，轮胎负荷、胎面滑移和能量会错误耦合；调节质量、阻尼或附着只能补偿某一工况。本节点先修离散方程一致性，保持所有物理参数、碰撞和原求解门槛。

该导向仍是理想直线悬架，不能代替真实悬架K&C几何；原生动态单精度、有限末姿态与行程、完整能量细化、旧10m非均匀自由落体及实测标定仍按各自证据验收。默认独立轮心开关继续关闭，未整合main。局部动量/虚功闭合不等于全车仿真验收通过。

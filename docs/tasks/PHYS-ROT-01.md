# PHYS-ROT-01 机械轮轴、转子输运与车身反力

- 状态：ready；PHYS-TIRE-04新CG分区T2已收口并本地提交；本任务尚未修改生产源码。
- 上游：PHYS-TIRE-04当前生产版本，reference-v8。基线提交为`e63512486dd93a68badbe925d8e44de0943b1e4a`；不用早期Hull候选或独立陀螺冲量原型作生产基线。
- 原始A源码：[最终CG分区验证源码归档](../evidence/PHYS-TIRE-04/final-validation-source-cg.zip)，266文件逐项校验通过，ZIP SHA-256为`05e4947a55580d6f20949cc490903a9bb76e2a22fd709e16eb50a2666d1891d6`；其中manifest保留实际验证时原始文件哈希。
- 目标：补齐旋转轮轴的轴承反力，机械轴与路面接触坐标分离，保持四轮轮胎/制动/车身共同末状态。发动机/离合/差速器随后另包接入。

## 范围与边界

按功能直接修改`vehicle_tires.py`、`tire_coupling.py`、`wheel_dynamics.py`和必要的状态/配置/参考导出/验证映射；`vehicle_brakes.py`、`vehicle_traction.py`及稳定控制仅允许适配同一真实接触速度/有效滚动力臂反馈，控制增益与压力硬件保持。几何计算可用单个明确函数或功能模块，不建立通用求解框架。Simulation继续负责唯一Bullet世界与120Hz积分。

不得顺带调发动机曲线、轮胎峰值、制动容量、电子增益、交通策略或声音门槛。保持Bullet碰撞/重力/射线悬架及自身刚体陀螺机制，不重设运行姿态或速度，不增加人工角阻尼抵消动量缺口。轮轴反力必须进入共同末状态，不在完成制动/轮胎之后追加另一轮物理。

既有轮胎柔性与本功能开关分别记录，仅用于同输入冻结A/B与明确机制配置；开关关闭时保留既有运算与轨迹。正常游戏/困难仿真共用新机制；配置版本、完整参数表、玩家/NPC和生命周期一起接通。

## 设计入口

先读[机械推导、20组平面/54组倾斜联合台架、45组独立虚功及12条原生世界轨迹](../evidence/PHYS-TIRE-04/rotor-joint-findings.md)、[实际原缺口与时间细化](../evidence/PHYS-TIRE-04/rotor-transport-audit/README.md)。机械正转转子角动量为`−Jw ω e`；接触方向、相对壳体转速和实际纵向力臂不能再由一个路面axle代替。

转向执行器改变机械轴时，轴承反力功一般不为零。明确区分车身随动的零功陀螺反力、转向指定运动的执行器功及时间离散误差，保存原始符号。道路normal改变不能冒充机械轮轴转向。射线支撑仍是当前近似，不虚构薄圆盘碰撞或独立簧下刚体。

## 验收

- 几何/虚功：平路与倾斜路面、转向、正反转，独立接触点速度与转矩/功恒等式；总动量只留下外部接触力矩。保留原轮胎0.001N残差、制动互补及原能量门槛，不靠放宽阈值通过。
- 无外力真实Bullet：重力/外力/角阻尼为0，零轮速和60rad/s对照，初始yaw=.2rad/s，1秒完整世界角动量/能量轨迹；120/240/480/960Hz作为精度诊断，生产仍120Hz。记录单精度原生读回误差，不把瞬时轴向账目当成有限旋转严格守恒。
- 共同末状态：轮胎/制动/陀螺同一末速度，所有力残差和功/动量数据有限；首次失败/超时/未跑保留。只处理明确接口和真实边界，不加内部silent fallback。
- A/B：同reference-v8完整配置/输入，正常游戏与困难仿真的加速、定转、阶跃、倒车、split-μ、弯中制动、坡停、离地与再接触；保存全过程、参数差异与理论方向。不用改加速门槛掩盖转子效应。
- 生命周期：玩家/NPC、reset、rebase、回收及模式重建；四轮真实轴向/有效力臂/反力与执行器功在诊断中可读。
- 行为修改跑相关T0，完成后完整vehicle/core/gameplay/traffic/road T1。传动功能组完成再T2；T3、可见性能及用户两模式驾驶属于整体Gate。

## 验证记录

生产T0/T1未跑；基线A、生产B、时间细分和人工体验均待执行。上游04的T2不能当作本功能验收。新任务完成后归档此包，不重读无关历史。

实现后T0入口：`.venv/Scripts/python.exe tools/validate.py T0 --tests tests/test_rotor_transport.py --tests tests/test_tire_coupling.py`，先新增覆盖真实轴向输运的`test_rotor_transport.py`并注册相关完整模块，不用只断言新字段存在的测试。每项必要集成变化补其真实风险节点。

完整T1入口：`.venv/Scripts/python.exe tools/validate.py T1 --area vehicle --area core --area gameplay --area traffic --area road --output logs/validation/PHYS-ROT-01-T1 --timeout 7200`；输出目录首次使用，已存在时另取新目录。机械专项及精度A/B另保留独立轨迹，不拿T1 headless替代。

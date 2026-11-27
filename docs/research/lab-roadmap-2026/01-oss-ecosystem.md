# 专题 1：开源车辆仿真器与 Python 生态防重造轮子调研报告

> **调研角色**：开源车辆仿真器与 Python 生态防重造轮子专家  
> **核验基线日期**：2026-11-26（GitHub REST API、PyPI JSON API、arXiv API 与开放获取原文实测校验；所有未直接核验项均显式标注 `未核实`）  
> **对应溯源台账**：[sources-01-oss.csv](file:///b:/AI%20agent/%E6%9A%91%E6%9C%9F%E8%AE%A1%E7%AE%97%E6%9C%BA%E7%A8%8B%E5%BA%8F%E8%AE%BE%E8%AE%A1/CoastalDrive/docs/research/lab-roadmap-2026/sources-01-oss.csv)  
> **本地原始资料归档**：`logs/research/lab-roadmap-2026/downloads/01-oss/`（8 份经 SHA-256 与魔数校验通过的一手原文）

---

## 执行摘要（TL;DR）

CoastalDrive 当前已建成一套极为稀缺的混合架构：**极简依赖的 Windows 原生 Python 3.14 运行栈（仅 Panda3D 1.10.16 + NumPy + Matplotlib + Cython/cffi）+ 自研 34 维耦合簧上/独立四轮心/有限惯量传动/刷毛联合滑移 C 内核（120 Hz 固定步 / 240 Hz 机械子步、64 位双精度隔离 SDK、SHA-256 逐位确定性复算、能量账闭合至 2.10e-10 J、K&C、ISO 8608/2631-1 与 15 维 EKF 观测闭环）+ 可玩 3D 海岸/高速实时驾驶与预算工坊闭环**。

通过横评 **10 个主流开源/学术免费车辆与驾驶仿真器、12 个 Python 车辆/控制/优化/标准开源库、以及 4 大商业标杆公开架构**，得出三条战略级结论：

1. **防重造边界清晰**：CoastalDrive 的 **主线物理核心（34 维 C 内核 + Bullet 3D 接触）必须保持零重依赖自研**；而一旦迈向高级底盘控制（NMPC/LQR/力矩分配）、非线性参数辨识、跨工具联合仿真、标准路试数据交换与 RL 评测，**绝不能重造**优化求解器（`acados` / `OSQP` / `CVXPY` / `CasADi`）、线性控制库（`python-control`）、科学计算底座（`SciPy`）、FMI 联合仿真器（`FMPy`）、标准数据/路面/场景解析器（`asammdf` / `OpenCRG` / `scenariogeneration`）与 RL 接口（`Gymnasium`）。应通过 **`pyproject.toml` 可选扩展组（`core` 保持零重依赖，`lab-control` / `lab-io` / `lab-rl` 按需安装）** 隔离引入，并严格区分宽松许可（MIT/BSD/Apache-2.0）与弱传染许可（LGPL-3.0 / MPL-2.0）。
2. **最高价值的跨项目工程借鉴**：不是照搬重型框架（严守 CoastalDrive 禁止 ECS/DI/多层 Manager 的架构红线），而是精准吸收 5 项高杠杆设计——① `Chrono::Vehicle` 的顶层装配 JSON 引用 + Canonical 冻结哈希双轨；② `Chrono::Vehicle` `ChSuspensionTestRig` 的“推杆纯运动学 vs 平台含胎面柔度”虚拟 K&C 分离范式；③ `CommonRoad` Section 10“高保真多体主参数向低阶预测模型（ST/STD）自动降维投影 + 共享状态前缀”；④ `TUMFTM/Open-Car-Dynamics` 的“3 有状态子模型 + 2 无状态力元”显式契约；⑤ 商业标杆（CarSim / CarMaker / VI-CarRealTime / MathWorks VDB）的“车-路-工况-评价四元解耦 + FMI Co-Simulation C-ABI”。
3. **不可替代生态位明确**：全开源生态存在一道巨大断层——**高保真多体工具（Chrono / OpenModelica / Open-Car-Dynamics）要么依赖极重、无 Windows pip 开箱生态，要么缺失实时 3D 驾驶/交通/碰撞闭环；游戏与 AD 仿真器（MetaDrive / CARLA / TORCS / AirSim）物理保真度差 1–2 个量级；BeamNG.tech 闭源且受限于非商许可与非确定性**。CoastalDrive 精准卡位在 **“桌面级开箱即用、逐位确定性白盒教学/科研车辆动力学实验室 × 真实 3D 驾驶体验”** 的独有蓝海，应坚决放弃 FEA/软土力学、软体碰撞变形、UE5 光追多传感器感知、1000+ FPS 宏观交通 RL 底座等红海赛道。

---

## 1. 横向对比矩阵

### 1.1 多体、高保真及驾驶仿真器全景对比

> 活跃度字段均为 2026-11-26 通过 GitHub REST API / PyPI JSON API 实测结果；未直接从 API 取得的指标标 `未核实`。

| 项目 | 物理深度与典型建模范围 | 数值方法 / 守恒与精度特性 | Python 与控制接口友好度 | 实测许可证 | 活跃度（2026-11-26 实测） | 与 CoastalDrive 核心差异 | 归类决策 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Project Chrono (`Chrono::Vehicle` / `PyChrono`)** | 完整 3D 多体刚柔耦合（显式双叉臂/麦弗逊/多连杆/整体桥、转向连杆、2WD/4WD 轴系）、多种轮胎（Rigid/Fiala/Pac89/Pac02/TMeasy/TMsimple/ANCF FEA）、刚体/SCM 软土/颗粒 DEM 地形、含 `ChSuspensionTestRig` K&C 台架 | DAE 求解，支持 HHT 隐式积分（二阶精度 + 高频数值阻尼）、NSC/SMC 接触；高精度但无内建轻量 120 Hz 逐位能源账单 | `PyChrono` 暴露 C++ API，但**无官方 PyPI wheel**，强绑 Conda 与特定 Python 次版本（如 3.9–3.12），Windows 缺 `vsg3d`/`cascade` 常需 MSVC 源码编译 | `BSD-3-Clause` | 3,173 stars，最新 `10.0.0`，pushed `2026-11-25`（极活跃） | 物理广度（FEA 胎/软土/履带/连杆多体）远超 CoastalDrive，但部署重、多车实时驾驶与交互游戏体验弱，且无法直接装入 CoastalDrive 的 Python 3.14 `.venv` | **交叉验证对标** / **吸收设计或算法** |
| **OpenModelica (`VehicleInterfaces` / `PlanarMechanics`)** | 通用非因果多域物理（机/电/液/热/控制）；`VehicleInterfaces` 提供整车/底盘/转向/制动标准信号总线，`PlanarMechanics` 为 2D 平面多体 | 符号化简 + 隐式 DAE 积分（DASSL/IDA/CVODE），物理守恒性强，但编译期开销大、不适合强交互 3D 实时碰撞 | `OMPython`（v4.1.0）通过 ZeroMQ 控 OMC 编译运行；支持导出标准 FMI 2.0/3.0 FMU | 主体 `OSMC-PL-1.8` / `AGPL-3.0` 双许可；`VehicleInterfaces` 与 `PlanarMechanics` 为 `BSD-3-Clause` | OpenModelica 1,502 stars，`v1.27.2`，pushed `2026-11-26`；`VehicleInterfaces` 54 stars `v2.0.2`；`PlanarMechanics` 3 stars | 强项是方程级多物理场离线仿真与模型交换，非 3D 实时交互实验室；`VehicleInterfaces` 的总线分层值得借鉴，交互层通过 FMU 互通而非引入 OMC | **明确不做或避坑**（主体）；**吸收设计或算法**（`VehicleInterfaces`） |
| **BeamNG.tech + `BeamNGpy`** | 实时软体节点-梁（Node-Beam / `JBeam`）底盘/悬架/轮胎/碰撞变形物理，含视觉/LiDAR/IMU 等传感器 | 约 2 kHz 软体显式积分，碰撞与形变真实度行业独一档；但单车算力极重、多车并发瓶颈明显，跨 Socket 异步控制下难以实现严格逐位确定性复算 | `BeamNGpy`（PyPI `1.37`）API 成熟、文档好，但必须绑定闭源专有 `BeamNG.tech` 服务端与 `tech.key` 授权文件 | 引擎**闭源专有**（学术免费仅限非商，产出数据默认 `CC-BY-NC v4`，商用需付费）；`BeamNGpy` 为 `MIT` | `BeamNGpy` 407 stars，`v1.37`，pushed `2026-11-23`（活跃） | 黑盒专有引擎、非商数据条款与不可审计内部方程，与 CoastalDrive 白盒可验证《汽车理论》实验室及自由部署目标根本冲突 | **明确不做或避坑** |
| **Speed Dreams / TORCS** | 基于 `simuV2/V3/V4` 的赛道车辆动力学（扩展类 Pacejka 轮胎、热衰/磨损、空气动力、悬架近似） | 定步显式欧拉积分（如 0.002 s），高冲击易产生能量漂移与翻车奇异；赛道基于分段硬边界 + 简化包围盒碰撞 + 0–10000 数值损伤 | 缺乏原生现代 Python/Gym 控制接口（历史 `gym_torcs` 依赖过时 IPC/屏幕截取），C++ 插件架构陈旧 | `GPL-2.0-or-later`（源码）；`Free Art License`（部分美术） | 已从 SourceForge 迁至 Forgejo (`forge.a-lec.org/speed-dreams`)，最新系列 `v2.4.x`（社区慢节奏维护；具体 Star 数 `未核实`） | `GPL-2.0+` 强传染许可、显式欧拉精度与旧式分段包围盒物理已落后于 CoastalDrive 34 维耦合 C 内核 | **明确不做或避坑** |
| **CARLA** | 城市自动驾驶全栈仿真（Unreal Engine 4/5 渲染 + 传感器套件 + 交通流）；车辆默认用 UE PhysX/Chaos 刚体，可选 `--chrono` 挂载 Chrono 后端 | 默认游戏级刚体物理（轮胎极限区与悬架大幅简化）；外挂 Chrono 后存在引擎同步开销高、版本受限与编译配置复杂问题 | Python Client API、ROS 2 桥与 OpenSCENARIO 生态极强，但服务端需高配 GPU 与数十 GB 资产 | 代码 `MIT` + 资产 `CC-BY` + **Unreal Engine EULA** | 14,713 stars，release `1.0`，pushed `2026-11-26`（极活跃） | 重资产城市视觉/感知 AD 平台，而非轻量化高精度底盘动力学实验室；物理白盒深度与确定性复算远不如 CoastalDrive | **明确不做或避坑** |
| **MetaDrive** | **同用 Panda3D + Bullet 引擎栈**！侧重程序化路网生成、真实数据集（Waymo/nuScenes）回放与单/多智能体 RL 训练 | 仅使用单刚体车身 + `BulletVehicle` 射线悬架与简化抓地（无独立四轮簧下、无真实传动惯量、无联合滑移刷毛/K&C），借此换取极高采样 FPS | 原生 Gymnasium 接口、`pip install metadrive-simulator` 开箱即用，RL 友好度顶级 | `Apache-2.0` | 1,288 stars，`MetaDrive-0.4.3`（PyPI `0.4.3`），pushed `2026-10-16`（活跃） | **最具价值的直接对照组**：证明同样在 Panda3D+Bullet 栈上，MetaDrive 选择了“牺牲底盘物理换取 1000+ FPS RL 吞吐”，而 CoastalDrive 彻底接管轮端物理建成了 34 维工程动力学求解器 | **交叉验证对标**（反例标杆与 RL 接口参考） |
| **Microsoft AirSim** | 基于 Unreal/Unity 的多旋翼 UAV 与地面车辆仿真，地面车沿用基础 PhysX 刚体射线轮模型 | 物理保真度偏向无人机气动，地面车辆轮胎/悬架/传动极为基础 | Python/C++ RPC API，但上游已实质停滞 | `MIT`（实测 `LICENSE` 原文） | 18,639 stars，最后正式版 `v1.8.1-windows`（上游微软 2022 宣布归档，虽 GitHub `archived=false` 但核心开发已停滞） | 已过时且地面底盘物理薄弱，无借鉴或集成价值 | **明确不做或避坑** |
| **CommonRoad (`commonroad-vehicle-models`)** | 6 档标准状态空间 ODE 模型阶梯：PM(4 态) → KS(5 态) → KST(6 态挂车) → ST(7 态含纵载转移) → STD(9 态 PAC2002 漂移) → **MB(29 态多体：簧上+前/后整体轴+4 轮速+柔顺销关节+PAC2002)** | 纯 ODE 显式状态空间（依赖 `scipy.integrate` 等外部求解器），低速 $|v|<0.1\text{ m/s}$ 切换质心运动学避免奇异；**无 3D 地形/碰撞、无真实动力总成换挡、无独立四轮簧下、无限位块/几何抗抬头** | `pip install commonroad-vehicle-models`（PyPI `3.0.2`），Python/MATLAB 双实现 + YAML 标定车参数（Ford Escort / BMW 320i / VW Vanagon / 卡车） | `BSD-3-Clause`（实测 `LICENSE.txt`） | PyPI `3.0.2`（GitLab 托管 `tum-cps/commonroad-vehicle-models`，Star 数 `未核实`） | CoastalDrive 34 维独立四轮心+有限传动+真实 3D 接触在物理深度上全面超越其 29 态平面 MB；但它的**模型阶梯、Section 10 高保真→低阶参数转换公式与公开参考车集**极有吸收与对标价值 | **吸收设计或算法** / **交叉验证对标** |
| **F1TENTH (`f1tenth_gym`)** | 1:10 自动驾驶赛车 2D 平面仿真，基于 CommonRoad ST（单轨）动力学 + 2D LiDAR 扫描 | 轻量 2D 单轨模型（无垂向/侧倾/俯仰/悬架/独立四轮/真实 3D 碰撞），计算极快 | 原生 Gymnasium 兼容、纯 Python/Numba、极易做多车竞速控制基准 | `MIT` | 255 stars，pushed `2026-09-04`（持续维护） | 面向 1:10 缩比车 2D 竞速决策基准，物理深度不可替代 CoastalDrive，适合作为 2D 控制基准接口参考 | **交叉验证对标** |
| **TUMFTM `Open-Car-Dynamics`（及 TUMFTM 赛道套件）** | `Open-Car-Dynamics` 为 C++20 模块化多体状态空间 ODE（3 有状态子模型：车体/传动/转向 + 2 无状态子模型：气动/轮胎，共 48 组合，含 MF5.2 轮胎，经 IAC AV21 实车验证）；配套 `laptime-simulation`、`global_racetrajectory_optimization`、`YawMomentDiagrams`、`sim_vehicle_dynamics` | 定步 Dormand-Prince (ode4)，最复杂模型单步 **`< 10 µs`**（Ryzen 9 7950X）；平面/准 3D 需外挂 `3d-road-geometry-coupling`，**无 3D 刚体碰撞、无视觉渲染/交通/K&C 台架** | 提供 ROS 2、Python 字典参数接口与实验性 MATLAB MEX，但**仅支持 Ubuntu 22.04/24.04（需 Eigen3/Boost/C++20/colcon 或 Docker）**，Windows 不原生开箱 | `Open-Car-Dynamics` 为 **`Apache-2.0`**；其余 TUMFTM 轨迹/圈速/YMD 仓库均为 **`LGPL-3.0`** | `Open-Car-Dynamics` 152 stars `v2.1.3`（pushed `2026-11-13`，活跃）；`global_racetrajectory_optimization` 636 stars（pushed `2023-07-06`）；`laptime-simulation` 169 stars（pushed `2026-04-13`） | 工程速度与模块划分极其出色，是 CoastalDrive 物理内核的**最佳学术近邻对标**；但无 Windows 零依赖运行体验、无 3D 碰撞/地形/交通与游戏化试车闭环 | **吸收设计或算法** / **交叉验证对标** |

### 1.2 Python 科学计算、底盘控制与行业标准开源库对比

| 库名 | 核心定位与车辆工程用途 | 实时性 / 性能特征 | 实测许可证 | 活跃度（2026-11-26 实测） | 与 CoastalDrive 集成策略 | 归类决策 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`SciPy`** | 非线性最小二乘标定（`least_squares`）、ISO 2631 滤波/Welch PSD、稀疏线性代数、插值、ODE 交叉验证 | C/Fortran 底层，离线标定与后处理极快 | `BSD-3-Clause` | PyPI `1.18.1`（GitHub API 限流 403，Star 数 `未核实`） | 作为 `lab` 可选依赖直接复用，不污染纯游戏最小运行核 | **直接复用** |
| **`acados`** | 嵌入式超高速非线性最优控制（NMPC / MHE / SQP-RTI），内置 BLASFEO 紧凑线性代数与 HPIPM QP | 生成纯 C 求解器，毫秒/亚毫秒级（支持 kHz 级底盘控制与 120 Hz 实时闭环） | **`BSD-2-Clause`**（实测 `LICENSE` 原文） | 1,533 stars，`v0.6.1`，pushed `2026-11-26`（极活跃） | 作为高级底盘控制（NMPC 轨迹跟踪、ABS-DYC、主动转向）首选框架 | **直接复用** |
| **`CasADi`** | 稀疏计算图前向/反向自动微分、OCP 建模、连接 IPOPT/SUNDIALS 并生成自包含 C 代码 | 建模期符号构造极强，生成的纯 C 残差/雅可比可用于离线最优轨迹（如最小圈速）与 `acados` 前端 | **`LGPL-3.0`** | 2,338 stars，`3.8.2`（PyPI `3.8.2`），pushed `2026-11-26` | 可选控制/离线轨迹优化依赖；因 LGPL-3.0 保持插件化动态隔离 | **直接复用** |
| **`OSQP`** | 算子分裂（ADMM）凸二次规划求解器，支持热启动与矩阵分解缓存 | 亚毫秒级 C 求解器，支持无矩阵重分解的在线控制分配 | `Apache-2.0` | 2,234 stars，GitHub `v1.0.0` / PyPI `1.1.3`，pushed `2026-01-12` | 底盘四轮制动力/横摆力矩摩擦圆分配（Control Allocation）与线性 MPC 首选 | **直接复用** |
| **`CVXPY`** | 凸优化 Python 嵌入式声明式建模语言（可调用 OSQP/Clarabel/SCS 等后端） | 适合原型期快速表达约束优化，高频 120 Hz 热路径建议直连 OSQP 消除 Python 建模开销 | `Apache-2.0` | 6,402 stars，`v1.9.3`（PyPI `1.9.3`），pushed `2026-11-26` | 实验台控制算法原型探索与离线标定凸子问题 | **直接复用** |
| **`python-control`** | 线性系统传递函数/状态空间分析、Bode/Nyquist/根轨迹、LQR/LQG/极点配置/Kalman | 离线分析与教学基准足够快（底层 NumPy/SciPy） | `BSD-3-Clause` | 2,125 stars，`0.10.2`（PyPI `control 0.10.2`），pushed `2026-10-28` | 专家试验台线性二自由度频域分析、不足转向特征根校验与 LQR 控制器设计 | **直接复用** |
| **`PyDy`** | 基于 SymPy 的 Kane / Lagrange 符号多体动力学推导与 C/Cython/NumPy 代码生成 | 仅适用于**离线**方程推导与雅可比符号校验，不可直接跑 120 Hz 运行时 | `BSD-3-Clause` | 417 stars，`v0.9.4`（PyPI `0.9.4`），pushed `2026-11-16` | 离线验证 CoastalDrive 34 维 C 内核/K&C 方程及解析雅可比零手算失误 | **直接复用** |
| **`FMPy`** | FMI 1.0 / 2.0 / 3.0 标准 FMU 加载、校验与 Model Exchange / Co-Simulation 执行 | 纯 C 回调调度，开销低 | **`BSD-2-Clause`**（实测 `LICENSE.txt` 原文） | 602 stars，`v0.3.32`（PyPI `0.3.32`），pushed `2026-11-02` | 薄适配：让试验台可直接挂载外部 Simulink/OpenModelica 控制器 FMU，或验证 CoastalDrive 导出的 Plant FMU | **薄适配兼容** |
| **`Gymnasium`** | 强化学习与闭环控制评测标准 `Env` 接口（`reset`/`step`/`observation_space`/`action_space`） | 极轻薄 Python 封装层，几乎零开销 | `MIT` | PyPI `1.4.0`（GitHub API 限流 403，Star 数 `未核实`） | 薄适配封装 `Simulation.step` + `VehicleCommand` + `Snapshot`，无缝对接主流 RL/控制库 | **薄适配兼容** |
| **`asammdf`** | 汽车行业标准 ASAM MDF（`.mf4`/`.dat`）高速读写、重采样、通道裁剪与信号导出 | Cython/NumPy 加速，百万点路试数据秒级解析 | **`LGPL-3.0-or-later`**（PyPI `8.8.33` 实测，注意并非 MIT） | PyPI `8.8.33`（GitHub API 限流 403，Star 数 `未核实`） | 可选离线工具：导出试验台仿真结果为 `.mf4` 或导入实车 CAN/IMU 路试数据对账，保持 LGPL 动态隔离 | **薄适配兼容** |
| **`ASAM OpenCRG`** | 行业标准 3D 曲面规律网格路面（`.crg`）规范与 ANSI-C 求值库 | 原生 ANSI-C 求值，微秒级查询局部路面高程/法向/附着 | `Apache-2.0` | 官方托管 `asam-ev/OpenCRG`（具体 Star 数 `未核实`） | 已有 `cffi` 环境下薄包装 C-API，导入实测扫描路面以扩展 ISO 8608 随机路面库 | **薄适配兼容** |
| **`scenariogeneration`** | ASAM OpenDRIVE (`.xodr`) 与 OpenSCENARIO (`.xosc` 1.0–1.3) Python 参数化生成库（整合原 `pyodrx`/`pyoscx`） | 离线场景 XML 生成与参数扫描 | `MPL-2.0` | PyPI `0.16.7`（GitHub API 限流 403，Star 数 `未核实`） | 仅当未来需要与外部 ADAS 场景库互通标准测试工况时作薄导入/导出层 | **薄适配兼容** |

### 1.3 商业标杆公开架构与功能分层参考

| 商业标杆 | 公开核心求解架构 | K&C 与轮胎建模分层 | 场景 / 协同仿真与工程工作流特点 | 对 CoastalDrive 的核心启发 |
| :--- | :--- | :--- | :--- | :--- |
| **CarSim (Mechanical Simulation / Applied Intuition)** | 符号化自动生成优化的多体方程（**VS Solver**），高速实时运行 | 查表化悬架 K&C 特性 + 内建轮胎模型 + 第三方 MF-Swift / FTire 插件接口 | 基于文本化 **Parsfile** 与 **VS Commands** 定义参数与事件；经 S-Function / DLL / FMU 接入 Simulink 与 HiL | 证明**“中等自由度精确多体 + 查表 K&C + 清晰文本参数脚本”**足以覆盖 95% 操稳/制动/主动底盘验证，无需盲目堆砌复杂连杆几何求解 |
| **IPG CarMaker** | 模块化实时整车仿真内核，覆盖 MiL → SiL → HiL → DiL 全周期 | CarMaker Suspension K&C 生成/导入 + 丰富轮胎接口（Pacejka/FTire/CDTire/自定义 DLL） | 清晰的 **InfoFile** 参数格式 + **TestRun**（将 Vehicle / Road / IPGDriver / Maneuver / Traffic 四元解耦）+ 开放 C/Simulink 钩子 | **TestRun 声明式工况规范**是专家试验台批量回归、参数扫描和 A/B 对比的最佳蓝本 |
| **VI-CarRealTime (VI-grade)** | 面向静/动态驾驶模拟器（DiL）极致优化的亚毫秒级实时多体模型（常见 14-DOF 级） | 强调从 Adams/Car 全连杆多体或物理 K&C 台架**无损压缩转换为查表实时模型** | 原生耦合硬件驾舱与 Simulink/FMU 联合仿真，聚焦“真实人体驾乘主观评价 + 客观指标闭环” | 与 CoastalDrive **“真实人工试驾手感 + 专家试验台客观指标”**的双轨理念高度共鸣，验证了“降阶查表 K&C + 实时人工闭环”的工程正确性 |
| **MATLAB Vehicle Dynamics Blockset (MathWorks)** | 白盒 Simulink 物理模块库，内置 **3-DOF（单轨）与 14-DOF（6 车身 + 4×2 轮跳/转）** 双保真度阶梯 | 内置 **Virtual K&C Test Laboratory** 虚拟试验台与拟合标定流 + 魔术公式轮胎模块 | **Virtual Vehicle Composer** 图形化装配整车并一键派生标准工况（加速/制动/双移线/稳态回转），可选 Unreal 3D 联合渲染 | 值得借鉴“同源参数一键切换 3-DOF 控制模型与高保真整车模型”及“虚拟 K&C 台架→参数回填”闭环 |

---

## 2. “绝不重复造轮子”清单与依赖隔离策略

### 2.1 分层依赖原则（守住 CoastalDrive 极简运行栈优势）

核对 `.venv` 实测可知，CoastalDrive 当前仅安装 `Panda3D==1.10.16`、`numpy==2.5.3`、`matplotlib==3.11.2`、`Cython==3.2.9`、`cffi==2.1.1`、`pillow`、`SoundCard` 等极少包，连 `scipy` 均未强绑。这是一个**极其宝贵的工程资产**——确保了桌面启动极快、Windows 打包体积小、C 内核纯确定性不受外部科学栈浮点差异污染。

因此，**“绝不重复造轮子”绝不意味着把重型库塞进 `Simulation` 120 Hz 核心**，而是通过分层可选依赖（`pyproject.toml` extras）精准接入：

| 依赖分层 | 包含模块 / 库 | 许可证类型 | 绝不重造的理由与边界 |
| :--- | :--- | :--- | :--- |
| **`core`（强制最小集，保持零重依赖）** | 现有 Panda3D + NumPy + 自研 34 维 C 内核 | BSD / 自研 | 保持双击 `.cmd` 秒启、120 Hz 确定性复算零外部浮点污染、游戏发行版轻量干净 |
| **`lab-math`（离线标定/平顺性/线性控制）** | `scipy` (`1.18.1`)、`python-control` (`0.10.2`)、`PyDy` (`0.9.4`, 仅开发期) | 全 `BSD-3-Clause`（完全宽松） | ① 绝不手写 Levenberg-Marquardt/Trust-Region 非线性最小二乘、稀疏矩阵或 IIR/Welch PSD；② 绝不重造状态空间频域分析/Bode/LQR/ARE 求解器；③ 离线符号方程推导与解析雅可比校验交由 `PyDy`/SymPy 生成对照测试，绝不手抄几十行偏导公式 |
| **`lab-control`（实时最优底盘控制）** | `OSQP` (`1.1.3`, Apache-2.0)、`CVXPY` (`1.9.3`, Apache-2.0)、`acados` (`v0.6.1`, BSD-2-Clause)、`CasADi` (`3.8.2`, **LGPL-3.0**) | Apache-2.0 / BSD-2-Clause；`CasADi` 需按 **LGPL-3.0 动态隔离** | ① 四轮纵向/横摆力矩摩擦圆分配（Control Allocation）直接用 `OSQP`，绝不自写内点法/有效集 QP 求解器；② 实时 NMPC / MHE 直接用 `acados`（C 代码生成 + BLASFEO），原形探索用 `CVXPY`/`CasADi`，绝不自写 SQP 与自动微分计算图；③ 若未来闭源分发，将 `CasADi` 仅留在离线建模/可选插件进程边界，运行时只加载 `acados` 生成的 BSD-2 级 C 代码与 `OSQP` |
| **`lab-io`（行业标准互通与联仿）** | `FMPy` (`0.3.32`, BSD-2-Clause)、`ASAM OpenCRG` C-API (`Apache-2.0`, 经现有 `cffi`)、`scenariogeneration` (`0.16.7`, MPL-2.0)、`asammdf` (`8.8.33`, **LGPL-3.0+**) | BSD-2 / Apache-2.0；`scenariogeneration` MPL-2.0 文件级；`asammdf` **LGPL-3.0+ 动态隔离** | ① 绝不自造跨软件联合仿真 RPC 协议——遵循 FMI 2.0/3.0 标准，用 `FMPy` 接入外部 Simulink/OpenModelica 控制器 FMU；② 绝不手写 `.mf4` 二进制块解析或 `.crg`/OpenDRIVE/OpenSCENARIO XML 规范；③ **注意纠偏**：`asammdf` 经 PyPI 实测为 `LGPLv3+`（非 MIT），必须作为独立可选导出/导入插件使用，不静态内嵌进主线核心 |
| **`lab-rl`（AI 与自动试车接口）** | `Gymnasium` (`1.4.0`, MIT) | `MIT` | 仅需 ~100 行薄壳封装 `Simulation.step` + `VehicleCommand` + `Snapshot`，即免费接入 Stable-Baselines3 / CleanRL / RLlib 全部算法生态，绝不另造私有训练循环接口 |

### 2.2 明确“禁止侵入主线”的许可证红线

- **严禁将 GPL-2.0+/GPL-3.0/AGPL-3.0 源码拷入主线**：如 Speed Dreams/TORCS (`GPL-2.0+`)、OpenModelica 编译器 (`OSMC-PL/AGPL-3.0`)。
- **严禁依赖非商限制资产或数据**：如 `BeamNG.tech`（生成数据默认 `CC-BY-NC v4`，会污染 CoastalDrive 未来商用或公开数据集发布权）。
- **警惕弱传染许可（LGPL-3.0）的静态耦合**：如 `CasADi`、`asammdf` 及 `TUMFTM` 的 `laptime-simulation`/`global_racetrajectory_optimization`；它们可作为**独立进程/动态导入的可选 Python 工具或离线验证对标脚本**合法使用，但不得复制其代码片段粘贴进 CoastalDrive 核心模块。如需吸收最小曲率 QP 或准稳态 $g\text{-}g$ 包络思想，须依据公开论文数学公式自行用 NumPy/`OSQP` 净室实现。

---

## 3. 值得深度吸收的优秀工程设计

> 以下设计均严格遵循 CoastalDrive `AGENTS.md` 原则：**保持 `Controller → Control → Simulation → Snapshot` 单向权威数据流，拒绝 ECS、事件总线、DI、Service Locator、多层 Manager、抽象 Factory 堆叠和预建抽象**。

### 3.1 分层装配配置 Schema + Canonical 冻结哈希双轨（借鉴 `Chrono::Vehicle`）

对照本地归档的 `Chrono::Vehicle` 原件 [chrono_vehicle_hmmwv_template.json](file:///b:/AI%20agent/%E6%9A%91%E6%9C%9F%E8%AE%A1%E7%AE%97%E6%9C%BA%E7%A8%8B%E5%BA%8F%E8%AE%BE%E8%AE%A1/CoastalDrive/logs/research/lab-roadmap-2026/downloads/01-oss/chrono_vehicle_hmmwv_template.json)（47 行）与 CoastalDrive 当前配置 [gr86-2022-kc-calibrated.json](file:///b:/AI%20agent/%E6%9A%91%E6%9C%9F%E8%AE%A1%E7%AE%97%E6%9C%BA%E7%A8%8B%E5%BA%8F%E8%AE%BE%E8%AE%A1/CoastalDrive/assets/game/vehicle-configs/gr86-2022-kc-calibrated.json)（1,855 行全量内联）：
- **痛点**：当前 CoastalDrive 单一巨型 JSON 很利于单文件确定性复算，但当扩展多车型、多轮胎配方、多悬架 K&C 包和预算工坊改装件组合时，会产生大量参数拷贝与漂移风险。
- **借鉴落地方案（无重型配置框架）**：在保持现有 `vehicle-engineering-v1` 全量内联格式 100% 向后兼容的前提下，允许在顶层配置中以简单字典字段引用子组件文件（如 `tire_ref`、`suspension_kc_ref`、`powertrain_ref`），加载器在构造 `VehicleConfig` 前做一次纯函数展开（resolve）得到**规范化冻结快照（Canonical JSON）**，SHA-256 依然直接哈希展开后的冻结值。这样既复用了 `Chrono::Vehicle` 的“底盘/悬架/轮胎/制动/传动独立建库”，又不破坏逐位确定性审计链。

### 3.2 虚拟 K&C 试验台双激励模式（借鉴 `Chrono::Vehicle` `ChSuspensionTestRig` & MathWorks VDB）

`Chrono::Vehicle` 明确将悬架 K&C 台架拆分为两种物理边界清晰的激励器：
1. **`ChSuspensionTestRigPushrod`（推杆直驱轮毂/羊角）**：绕过轮胎接触斑，直接对轮心施加上下跳动与转向位移，提取纯几何运动学（Kinematics：轮跳-外倾、轮跳-前束、侧倾中心迁移、轮距变化）。
2. **`ChSuspensionTestRigPlatform`（轮胎踏板平台加载）**：通过轮胎接地平台施加垂直、纵向与侧向载荷，测出含轮胎刚度与衬套柔度的综合柔顺性（Compliance：侧向力转向、制动力前束/抗点头）。
- **CoastalDrive 落地价值**：CoastalDrive M2 已在 `src/suspension_kc.py` 落地 K&C 与外倾推力，下一步在专家试验台补齐“单轴纯运动学推杆扫掠 + 含胎面平台载荷柔度扫掠”两种零场景开销的独立测试模式，并支持导出与 CarSim / MathWorks 同构的 K&C 特征曲线（camber/toe vs jounce & lateral force），能直接把实验室可信度抬升至商业台架范式。

### 3.3 高保真主参数向低阶控制模型自动降维投影（借鉴 `CommonRoad` Section 10）

对照本地归档的 [commonroad_vehicle_models_doc.pdf](file:///b:/AI%20agent/%E6%9A%91%E6%9C%9F%E8%AE%A1%E7%AE%97%E6%9C%BA%E7%A8%8B%E5%BA%8F%E8%AE%BE%E8%AE%A1/CoastalDrive/logs/research/lab-roadmap-2026/downloads/01-oss/commonroad_vehicle_models_doc.pdf)（Section 10, pp. 23–26）：
- **精妙设计**：CommonRoad 所有 6 档模型共享相同前缀状态语义（$x_1 \dots x_7 = s_x, s_y, \delta, v, \Psi, \dot{\Psi}, \beta$），并且明确给出从 29 态多体（MB）参数向 7 态单轨（ST）与 9 态漂移（STD）模型的**解析参数映射与初值转换公式**（例如在零侧偏角处将非线性轮胎公式线性化求等效侧偏刚度 $C_i = K_{y,i} = F_{z,i} p_{Ky1}$，并拆出 $C_{S,i} = p_{Ky1}/\mu$），同时在 $|v|<0.1\text{ m/s}$ 平滑切换至质心参考运动学模型消除 $1/v$ 奇异。
- **CoastalDrive 落地价值**：CoastalDrive 已有 `src/theory_baselines.py`（二自由度解析线性基线）和 34 维 C 内核，下一步只要把 `VehicleConfig` 抽象出一个纯函数 `derive_reduced_control_model(vehicle_config)`：
  - 自动导出供 `python-control` 频域分析的线性 2-DOF 状态空间矩阵 $(A, B)$；
  - 自动导出供 `acados` / `OSQP` NMPC/MPC 使用的非线性单轨/双轨预测模型参数（零手动抄参，保证“被控对象改一个弹簧或轮胎参数，控制器内部模型同步感知或有意设置失配做鲁棒性实验”）。

### 3.4 “3 有状态子模型 + 2 无状态力元”契约边界（借鉴 `TUMFTM/Open-Car-Dynamics`）

对照本地归档的一手文档 [tumftm_open_car_dynamics_readme.md](file:///b:/AI%20agent/%E6%9A%91%E6%9C%9F%E8%AE%A1%E7%AE%97%E6%9C%BA%E7%A8%8B%E5%BA%8F%E8%AE%BE%E8%AE%A1/CoastalDrive/logs/research/lab-roadmap-2026/downloads/01-oss/tumftm_open_car_dynamics_readme.md)：
- `Open-Car-Dynamics` 之所以能在保持 48 种车型自由组合的同时跑出 `< 10 µs/step`，关键在于严格区分：
  - **有状态子模型（Stateful）**：车体多体动力学、动力传动系、转向执行器（持有积分状态变量）；
  - **无状态力元（Stateless）**：气动模型、准稳态轮胎力模型（纯函数：输入当前运动状态与法向载荷，输出力与力矩）。
- **CoastalDrive 落地价值**：CoastalDrive 的 34 维 C 内核已包含刷毛瞬态柔性状态，建议在 C 结构体与 Python 侧明确标明“状态向量归属 vs 纯函数力元（气动、静态滚阻、稳态外倾/刷毛映射）”，避免把缓存或隐藏状态悄悄塞进力元函数里；扩展新轮胎模型（如支持解析 `.tir` PAC2002 子集参数映射，**注意仅解析文本参数键，不触碰商业 Siemens MF-Tyre 二进制 DLL**）时，只需按 C 函数指针/静态分发替换纯函数力元，无需引入 OOP Factory 层级。

### 3.5 “车-路-工况-评价”四元解耦与 FMI C-ABI 对齐（借鉴 IPG CarMaker / CarSim / Chrono）

- **声明式试验工况（TestRun 范式）**：借鉴 CarMaker 的 `TestRun` 与 CarSim 的 `Parsfile`，将专家试验台的每个标准试验抽象为纯数据清单：`{vehicle_config, road_surface, maneuver_input_or_controller, observer_mode, metrics_assertions, seed}`。支持 CLI 一键批跑矩阵扫描（如多附着系数 $\mu \times$ 多车速 $\times$ `truth`/`sensor_ekf` $\times$ 控制策略 A/B）并自动产出结构化对照表与 SHA-256 复算凭证。
- **FMI 2.0/3.0 Co-Simulation 薄适配边界**：`Chrono::Vehicle` 的 `Synchronize(t, inputs)` + `Advance(dt)` 步进范式与 CoastalDrive 的 `Simulation.step(VehicleCommand)` + `Snapshot` 天然同构，也与 FMI Co-Simulation 的 `set_inputs → do_step(h) → get_outputs` 完美一一对应。未来只需为 64 位隔离 C SDK 包一层极薄的 FMI 2.0/3.0 C-ABI 导出壳，CoastalDrive 就能直接被 Simulink、`FMPy`、OpenModelica 甚至商业 HiL 工具链当作标准 Plant FMU 调用，彻底打通高校与车企生态。

---

## 4. CoastalDrive 不可替代的差异化护城河与明确放弃的红海赛道

### 4.1 开源与商业生态中真正存在的“真空地带”

把现有生态按 **“物理白盒深度与确定性”** × **“桌面轻量化交互与可玩闭环”** 二维切分，可以清楚看到 CoastalDrive 占据了一个几乎没有直接竞争对手的黄金象限：

```text
物理白盒深度 / 工程可验证性
   ▲
   │  [Project Chrono / OpenModelica]        ★ [CoastalDrive 独有生态位] ★
   │   高保真多体/DAE，但部署重、             34维自研C核 + 64位确定性复算 + 能量账本
   │   缺实时3D交通/游戏手感闭环              + K&C/ISO/EKF + Windows零重依赖秒启
   │                                          + 真实3D落日海岸/无限高速试驾与预算工坊
   │  [CommonRoad MB / TUMFTM OCD]
   │   纯ODE数学/实时极快，但无3D碰撞/
   │   无渲染/无交通/仅Linux或无实车试驾      [VI-CarRealTime / CarSim / CarMaker]
   │                                          商业闭源天价，偏企业HiL/DiL机台
   │  [F1TENTH]                              [BeamNG.tech]
   │   2D单轨缩比车                           软体碰撞顶尖，但闭源/非商受限/非确定性
   │
   │  [MetaDrive]                            [CARLA / Speed Dreams / AirSim]
   │   同Panda3D+Bullet但仅射线简化轮         视觉/交通强，但默认游戏刚体物理粗糙
   └──────────────────────────────────────────────────────────────────────────►
        离线脚本 / 纯命令行 / 2D                       实时 3D 交互驾驶 + 试验台体验
```

### 4.2 CoastalDrive 不可替代的 4 大护城河

1. **同源权威物理下的“工程实验室 × 真实 3D 驾驶”双态融合**：
   同一套 120 Hz/240 Hz 权威 34 维 C 求解器同时服务专家试验台与海岸/高速自由驾驶及预算改装生涯。你在试验台里标定出的 GR86 K&C 与 ABS-DYC 策略，下一秒就能切进 3D 海岸弯道亲自用手柄/键盘开出真实手感并做幽灵/数据对账——这是 Chrono、OpenModelica、CommonRoad、TUMFTM OCD 完全不具备的闭环体验。
2. **极致的工程可审计性与教学/科研透明度**：
   64 位双精度隔离 SDK + SHA-256 全链路确定性复算 + 单子步能量守恒账本（`2.10e-10 J`）+ 《汽车理论》解析基线实时对照（65 项 STIX 公式）+ `truth` vs 15 维 `sensor_ekf` 一键闭环切换 + 实车满秩留出盲测（2022 GR86 `100–0 mph` `-3.69%`、`1/4 mile` 尾速 `101.19` vs `101.0 mph`）。对比 BeamNG.tech 的黑盒非商限制与 MetaDrive/CARLA 的射线近似，CoastalDrive 天然是**高校《汽车理论》/车辆动力学课程、大学生方程式/智能车底盘控制验证与个人底盘工程师实验室**的理想载体。
3. **Windows 原生、Python 3.14 零重依赖与微秒/毫秒级桌面闭环**：
   对比 `PyChrono`（无 PyPI wheel、Conda 版本冲突）、`TUMFTM/Open-Car-Dynamics`（绑死 Ubuntu/ROS2/Eigen/Boost）、`CARLA`（UE 引擎与几十 GB 资产），CoastalDrive 保持轻量化 `.venv` 与自编译 C 内核，双击 `.cmd` 即开即用，在普通消费级 PC 上同时跑通实时 3D 渲染与高精度物理试验台。
4. **“真 3D 刚体接触 + 独立四轮心耦合求解”的甜蜜点**：
   在比 MetaDrive/BulletVehicle/CommonRoad MB 高出一个量级的同时，规避了 Chrono 全连杆 DAE 与 BeamNG 软体节点-梁的算力灾难，使单机同时运行高精度自车动力学、护栏真实凸体碰撞、ISO 8608 路面激励与多车流式高速交通成为可能。

### 4.3 明确放弃的红海赛道（战略避坑清单）

1. **绝不涉足 FEA/ANCF 可变形轮胎与松软土壤/颗粒力学（Terramechanics/DEM）**：Project Chrono 在该领域有十年积累与庞大 C++/GPU 生态，CoastalDrive 聚焦硬质铺装路面及路肩力学即可。
2. **绝不涉足软体碰撞结构变形与被动安全仿真（Crashworthiness）**：节点-梁形变与碰撞安全是 BeamNG.tech 与 LS-DYNA 的壁垒；CoastalDrive 保持刚体凸体碰撞零穿模、撞后零卡顿与有界求解兜底即可。
3. **绝不涉足照片级光追多传感器（Camera/LiDAR/Radar 物理射线追踪）城市端到端感知大模型训练场**：那是 CARLA (UE5)、NVIDIA Isaac Sim 等巨头的资本与资产红海；CoastalDrive 传感器层保持**面向底盘状态估计的 IMU / 轮速 / GNSS / 转向角 / 制动压力等动力学传感器闭环**（已有 15 维 EKF），不做重型视觉感知渲染器。
4. **绝不追求 1,000+ FPS 宏观城市交通强化学习吞吐**：MetaDrive 与 SUMO 已经把极速宏观交通 RL 做到极致；CoastalDrive 若提供 `Gymnasium` 薄壳，定位也应是**“高保真极限工况底盘控制与动力学感知决策评测（数十到百 Hz 级精控）”**，而非百万步宏交通刷分。
5. **绝不做通用非因果多物理场 DAE 编译器（热管理/电池电化学/复杂液压管网）**：留给 OpenModelica / Simscape，真有跨学科联合仿真需求时通过 FMI 2.0/3.0 FMU 接口外接。
6. **绝不自研通用数值优化器（QP/NLP/SQP/AD）、通用线性控制库或专有数据/场景文件解析器**：全部按第 2 章策略以可选依赖复用成熟开源库。

---

## 5. 完整可溯源参考表与本地已归档资料索引

### 5.1 本地已核验下载的开放获取一手资料（共 8 份，全部校验通过）

所有文件存放于 `b:\AI agent\暑期计算机程序设计\CoastalDrive\logs\research\lab-roadmap-2026\downloads\01-oss\`，均已通过 Python 脚本验证：文件大小 > 1 KB、PDF 魔数 `%PDF` 校验通过、计算 64 位 SHA-256 哈希。

| 台账 ID | 文件名与点击路径 | 类型 | 大小 (Bytes) | SHA-256 (前 16 位 / 完整见 CSV) | 核心价值 |
| :--- | :--- | :--- | ---: | :--- | :--- |
| `OSS-02` | [chrono_vehicle_hmmwv_template.json](file:///b:/AI%20agent/%E6%9A%91%E6%9C%9F%E8%AE%A1%E7%AE%97%E6%9C%BA%E7%A8%8B%E5%BA%8F%E8%AE%BE%E8%AE%A1/CoastalDrive/logs/research/lab-roadmap-2026/downloads/01-oss/chrono_vehicle_hmmwv_template.json) | JSON 模板 | 1,461 | `8f87369fbfe355c8` | Chrono::Vehicle 官方主分支顶层装配模板，直接对照 CoastalDrive 单体 JSON |
| `OSS-11` | [dosovitskiy2017_carla_arxiv1711.03938.pdf](file:///b:/AI%20agent/%E6%9A%91%E6%9C%9F%E8%AE%A1%E7%AE%97%E6%9C%BA%E7%A8%8B%E5%BA%8F%E8%AE%BE%E8%AE%A1/CoastalDrive/logs/research/lab-roadmap-2026/downloads/01-oss/dosovitskiy2017_carla_arxiv1711.03938.pdf) | PDF (`%PDF`) | 5,923,478 | `b03673e878fe3cd4` | CARLA 原始论文（arXiv:1711.03938），城市 AD 视觉平台与物理局限对比依据 |
| `OSS-12` | [li2022_metadrive_arxiv2109.12674.pdf](file:///b:/AI%20agent/%E6%9A%91%E6%9C%9F%E8%AE%A1%E7%AE%97%E6%9C%BA%E7%A8%8B%E5%BA%8F%E8%AE%BE%E8%AE%A1/CoastalDrive/logs/research/lab-roadmap-2026/downloads/01-oss/li2022_metadrive_arxiv2109.12674.pdf) | PDF (`%PDF`) | 10,473,784 | `ae04f7e4a3976f97` | MetaDrive 原始论文（arXiv:2109.12674），同为 Panda3D+Bullet 引擎栈的最佳对照组 |
| `OSS-14` | [commonroad_vehicle_models_doc.pdf](file:///b:/AI%20agent/%E6%9A%91%E6%9C%9F%E8%AE%A1%E7%AE%97%E6%9C%BA%E7%A8%8B%E5%BA%8F%E8%AE%BE%E8%AE%A1/CoastalDrive/logs/research/lab-roadmap-2026/downloads/01-oss/commonroad_vehicle_models_doc.pdf) | PDF (`%PDF`) | 425,578 | `b605361442969ab0` | CommonRoad Version 2020a 完整 30 页数学手册（PM/KS/KST/ST/STD/29 态 MB + Section 10 降维公式） |
| `OSS-15` | [okelly2020_f1tenth_pmlr123.pdf](file:///b:/AI%20agent/%E6%9A%91%E6%9C%9F%E8%AE%A1%E7%AE%97%E6%9C%BA%E7%A8%8B%E5%BA%8F%E8%AE%BE%E8%AE%A1/CoastalDrive/logs/research/lab-roadmap-2026/downloads/01-oss/okelly2020_f1tenth_pmlr123.pdf) | PDF (`%PDF`) | 9,119,629 | `45e171299565b5c9` | F1TENTH PMLR v123 开放获取论文，单轨控制与轻量 Gym 评测范式 |
| `OSS-16` | [tumftm_open_car_dynamics_readme.md](file:///b:/AI%20agent/%E6%9A%91%E6%9C%9F%E8%AE%A1%E7%AE%97%E6%9C%BA%E7%A8%8B%E5%BA%8F%E8%AE%BE%E8%AE%A1/CoastalDrive/logs/research/lab-roadmap-2026/downloads/01-oss/tumftm_open_car_dynamics_readme.md) | Markdown | 15,227 | `d22cf4faff3ad255` | TUMFTM/Open-Car-Dynamics 官方架构文档（3 有状态 + 2 无状态子模型、C++20 模板拼接 `<10 µs`、DOI `10.1109/IV55156.2024.10588858`） |
| `OSS-20` | [verschueren2019_acados_arxiv1910.13753.pdf](file:///b:/AI%20agent/%E6%9A%91%E6%9C%9F%E8%AE%A1%E7%AE%97%E6%9C%BA%E7%A8%8B%E5%BA%8F%E8%AE%BE%E8%AE%A1/CoastalDrive/logs/research/lab-roadmap-2026/downloads/01-oss/verschueren2019_acados_arxiv1910.13753.pdf) | PDF (`%PDF`) | 960,179 | `9157a08a54f5e62c` | `acados` 原始论文（arXiv:1910.13753），嵌入式高速实时 NMPC/MHE 权威蓝本 |
| `OSS-21` | [stellato2017_osqp_arxiv1711.08013.pdf](file:///b:/AI%20agent/%E6%9A%91%E6%9C%9F%E8%AE%A1%E7%AE%97%E6%9C%BA%E7%A8%8B%E5%BA%8F%E8%AE%BE%E8%AE%A1/CoastalDrive/logs/research/lab-roadmap-2026/downloads/01-oss/stellato2017_osqp_arxiv1711.08013.pdf) | PDF (`%PDF`) | 832,173 | `de60ca7972a63eb8` | `OSQP` 原始论文（arXiv:1711.08013），算子分裂 QP 与热启动控制分配核心依据 |

### 5.2 仅留元数据条目（`metadata_only` 共 27 条）及合规说明

全部 35 条调研条目的完整字段均已结构化登记在 [sources-01-oss.csv](file:///b:/AI%20agent/%E6%9A%91%E6%9C%9F%E8%AE%A1%E7%AE%97%E6%9C%BA%E7%A8%8B%E5%BA%8F%E8%AE%BE%E8%AE%A1/CoastalDrive/docs/research/lab-roadmap-2026/sources-01-oss.csv)，其中 27 条按严格合规准则保留为 `metadata_only`：
- **明确记录的下载未获取或受限项**：
  - `OSS-03`（Serban et al. 2019 `IJVP_2019_097096.pdf`）：作者原链接返回 `HTTP 404`；
  - `OSS-04`（Serban & Negrut 2016 `SBEL TR-2016-10.pdf`）：站端返回 `HTTP 202` 防爬/WAF 挑战页，严守不绕过反爬红线，未下载；
  - `OSS-17`（`TUMFTM/global_racetrajectory_optimization` README）：`master`/`main` raw 均返回 `HTTP 404`（已改为完整下载更具时效与 Apache-2.0 价值的 `TUMFTM/Open-Car-Dynamics` README `OSS-16`）；
  - `OSS-18` / `OSS-19`（Heilmeier 2020 & Christ 2021 *Vehicle System Dynamics* 期刊论文）：出版商付费墙未绕过；
  - **额外核验纠偏记录**：本次经 `arXiv API` 实测确认，网络二手摘要常误关联为 Heilmeier 论文的 `arXiv:1711.07300` 实为 Liniger, Domahidi & Morari (2017) *Optimization-Based Autonomous Racing of 1:43 Scale RC Cars*，故本报告严格剔除该错误归属，仅引用经 DOI 核实的期刊题录；同时通过 PyPI 与 GitHub 原始 LICENSE 文件实测，纠正了二手摘要中将 `asammdf` 误标为 MIT（实为 `LGPLv3+`）及将 `FMPy` 误标为 BSD-3（实为 `BSD-2-Clause`）的两处高风险许可误差。
- **其余 `metadata_only` 条目**：为开源软件主代码仓库、PyPI 软件包及 4 家商业标杆官网（CarSim / IPG CarMaker / VI-CarRealTime / MathWorks VDB），仅记录其权威 URL、核实版本号、许可证与战略评估决策。

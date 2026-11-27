# SIM-FIDELITY-02 汽车理论与高保真实验台全链路深化（M1–M5 协同任务包）

- 状态：in_progress（自动化 T1 验收、GR86 留出标定与离屏实图核对全部通过；待用户桌面体验复核）
- 基线 commit：`b1980b53`
- 所属阶段/前置：方向 4（阶段 7A / 汽车理论与实验台高保真深化）
- 多模型协同分工（全部产物与临时缓存严格留在 B 盘）：
  - **统筹监督、跨边界对齐与二分排障**：Antigravity Carbon High（主会话）
  - **Wave 1A 底层耦合力学与 C 内核攻坚**：Codex `gpt-6.2-sol` (`high`)
  - **Wave 1B 理论基线、ISO 路谱与观测器模块**：Antigravity Hydrogen High（`flash` 子代理）
  - **Wave 2A 试验台前后端、公式说明与记录全链路接线**：Antigravity Neon High（`pro` 子代理）
  - **Wave 2B GR86 多源留出标定器与单批高密度联调套件**：Antigravity Hydrogen High（`flash` 子代理）

## 目标与完成范围（M1–M5）

保持 `Controller → Control/VehicleCommand → Simulation (120 Hz) → Snapshot` 唯一物理权威单向数据流，默认 `CAR` 游戏车型、`GAME_INPUT` 手感、第一季生涯记分指纹与 `CDP1` 二进制快照格式（`src/snapshot_wire.py`）零改动：

1. **M1《汽车理论》解析基线与稳态扫点对账（`src/theory_baselines.py` + `quasi_steady_circle`）**：
   - 实现余志生《汽车理论》（第 6 版）第 1/2/4/5 章解析计算：旋转质量换算系数 $\delta_k$（空挡、教材标准与含输入轴/下游转子精确值）、各挡驱动力-行驶阻力平衡、最大车速、`0–100 km/h` 图解积分加速时间、1 挡动力/附着最大爬坡度、等速百公里油耗 `L/100km` U 型包络、制动 `I/β/f/r` 线组与同步附着系数 $\varphi_0 = (L\beta - b)/h_g$、制动效率与理论制动距离、二自由度线性不足转向梯度 $K_{\text{lin}}$（含可选 K&C 侧倾转向与外倾推力解析增量）及特征车速 $u_{\text{ch}}$。
   - 新增 `quasi_steady_circle` 定半径缓增车速扫点工况与 `fit_quasi_steady_understeer` 线性窗口回归（$|a_y|\in[0.6, 3.5]\,\text{m/s}^2, |a_x|\le 0.65\,\text{m/s}^2$），直接对账实算 $K_{\text{sim}}$ 与解析 $K_{\text{lin}}$。
2. **M2 悬架 K&C 运动学与轮胎外倾推力（`src/suspension_kc.py` + C 内核扩展 + `coastal-tire-fit-v2`）**：
   - `VehicleConfig` 新增显式默认关闭开关 `suspension_kc_enabled=False` 及 9 个 K&C/外倾字段（`static_camber_deg`、`static_toe_deg`、`camber_jounce_gains`、`camber_jounce_quad`、`camber_steer_gain`、`bump_steer_gains`、`camber_stiffness`、`rear_camber_stiffness`、`camber_load_exponent`）。
   - `mechanical_kernels.c` 与 `tire_forces.py` / `tire_aligning.py` 扩展联合滑移外倾推力（严格服从摩擦圆上界 $\sqrt{F_x^2+F_y^2} \le D(F_n)$ 且静止平路零横漂）；`tire_calibration.py` 保留 `coastal-tire-fit-v1`（满秩 6）并新增支持变外倾辨识与回正力矩 $M_z$ 独立留出校验的 `coastal-tire-fit-v2`（满秩 8，留出 $M_z$ 最大归一化误差 `2.13e-12`）。
3. **M3 独立簧下 34 维算子 C 化提速、能量账与 ISO 随机路面平顺性（`unsprung_joint` + `src/iso_ride.py`）**：
   - 将 `solve_unsprung_joint` 的固定构型残差与第 10–33 列雅可比下沉至 `mechanical_kernels.c`（C 雅可比列耗时 `0.025 ms` vs Python `1.266 ms`），`ride_bump` 平均单拍耗时由 `~230 ms/step` 降至 **`13.02 ms/step`（提速 ~18×）**，完整保留 `1e-9 Ns / 1e-5 N / 1e-9 Nm` 严格收敛门槛，单子步最大能量误差 `2.10e-10 J`；新增 `unsprung_energy_ledger` 汇总全车机械能闭合账本。
   - 新增 `src/iso_ride.py` 与 `iso_rough_road` 工况：按 ISO 8608（GB/T 4970）合成 A–D 级随机路面（刚体悬架走圆角三角网，独立轮心走 `O(1)` 纵向窗口裁剪的 64 位双精度 `box_section` 解析长方体板元以消除单精度 GJK/EPA 台阶噪声），计算 ISO 2631-1:1997 $W_k(f)$ 频域加权垂向加速度均方根 $a_{wz}$、主观舒适度分级、簧载/非簧载双峰 PSD 与车轮相对动载 $\sigma_{F_d}/G_0$。
4. **M4 首款实车（2022 GR86 Premium 6MT）多源留出标定（`tools/physics/calibrate_gr86_holistic.py`）**：
   - 保持 `assets/game/vehicle-configs/gr86-2022-premium-6mt.json` 原有 110 项参数与 `test_gr86.py` 零改动，同步补齐 10 项 K&C/外倾默认元数据。
   - 构建四级溯源标定流（Tier 1 原厂/实测几何与 FA24 扭矩、Tier 2 麦弗逊/双叉臂 K&C 文献先验、Tier 3 训练锚点辨识、Tier 4 明确工程初值）：仅用 Car & Driver `70–0 mph` 制动（`156 ft = 47.55 m`）与 `300 ft` 定圆稳态侧向抓地（`0.98 g`）2 步收敛辨识 `theta = (road_friction=1.10886, tire_peak_load_exponent=0.78950)`（`rank=2, cond=6.69`，无贴界；训练误差分别为 **`+0.06%`** 与 **`+0.15%`**）。
   - 零调参运行五大留出盲测集：`100–0 mph` 高速制动 **`95.40 m`（`313.0 ft` vs 实测 `325 ft`，误差 `-3.69%`）**；6MT `7350 rpm` 红线换挡 `1/4 mile` 冲线尾速 **`101.19 mph`（vs 实测 `101.0 mph`，误差 `+0.19%`）**、`0–60 mph` `6.72 s`（含 900 rpm 怠速柔和起步 vs 媒体 4500 rpm 弹射起步物理归因）；准稳态定圆 $K_{\text{sim}} = 1.18\,\text{deg}/g$（$R^2=0.865$）；`72 km/h` 双移线平均路径误差 `0.458 m`、峰值侧偏 `0.40°`；`70 km/h` ISO-C 随机路面 $a_{wz} = 1.397\,\text{m/s}^2$、车身偏频主峰 `1.875 Hz`、相对动载 `0.332`。输出 `assets/game/vehicle-configs/gr86-2022-kc-calibrated.json` 与 `logs/sim-fidelity-02/gr86-calibration/calibration-report.{json,html}`。
5. **M5 传感器 EKF + 底盘侧偏/附着观测闭环（`src/chassis_observer.py` + `feedback_source`）**：
   - 在 `Snapshot` 下游独立融合带噪 IMU、轮速滑移 NIS 门控与延迟 GNSS，抗全轮抱死车速塌陷并在线非对称辨识峰值附着系数 $\hat{\mu}$，通过 `adapt_snapshot` 与 `EstimatedNativeStabilityController` 零侵入驱动 `CoordinatedABSDYCController`（`LAB-M3`）及原生 `ABS+ESC`。
   - 实验台新增 `路谱等级`、`控制反馈`（`仿真真值` / `观测 EKF`，结果卡自动标注 `·EKF`）、4 组工程指标面板（新增 `ISO 平顺性` 与 `理论—仿真对账`）、2 组新曲线（`K&C 外倾 / 转角`、`状态估计对比`）、65 项（97 行）STIX 离线排版公式贴图及 HTML/JSON 导出读回复算闭环。

## 验证记账（分别记账）

1. **官方 T1 自动化套件（通过）**：
   - 命令：`.\.venv\Scripts\python.exe tools/validate.py T1 --tests tests/test_sim_fidelity_02.py tests/test_parameter_help.py tests/test_gr86.py tests/test_tire_calibration.py tests/test_lab_records.py tests/test_snapshot_wire.py --output logs/sim-fidelity-02/t1-validation`
   - 结果：`ruff`（全仓 `src tests tools` **0 错误**，`0.1s`）、`pytest`（**全部通过**，`86.5s`；另前序批次含 `test_lab_m3.py`、`test_challenge_scores.py`、`test_state_estimation.py` 全部通过）、`headless-0` / `headless-17` / `headless-23`（各 1200 步 **3/3 通过**）。
   - 证据：`logs/sim-fidelity-02/t1-validation/summary.json`、`logs/sim-fidelity-02/codex_wave1_last_gpt-6.2-sol.md`、`logs/sim-fidelity-02/gr86-calibration/calibration-report.json`。
2. **离屏渲染与实图核对（通过）**：
   - 命令：`.\.venv\Scripts\python.exe logs/sim-fidelity-02/capture_ui_verify.py`
   - 结果：生成并逐图人工核对 `logs/sim-fidelity-02/ui-verify/01-advanced-panel-menus.png` 至 `05-kc-camber-formula-help.png` 共 5 张 1280×720 实图，排版清晰、无压字裁剪、无字体缺字警告。
3. **人工桌面实机体验（待用户确认）**：
   - 待用户运行 `launchers/vehicle-lab.cmd` 体验准稳态定圆扫点、ISO 随机路面、`truth` vs `sensor_ekf` A/B 闭环对比、4 组工程指标面板及导入 `assets/game/vehicle-configs/gr86-2022-kc-calibrated.json` 后的分析交互。

## 交接

- 实现结果：M1–M5 全部代码、原生 `.pyd` 重编、65 项公式贴图与 GR86 留出标定配置已落位。
- 验证：官方 `T1` 自动化校验、标定满秩盲测报告与 5 张离屏 UI 实图全部通过。
- 提交范围：当前工作区未提交（基线 `b1980b53`，待按需本地提交）。
- 人工结论：待用户通过 `launchers/vehicle-lab.cmd` 实机体验确认。
- 下一步：用户桌面体验 `SIM-FIDELITY-02` 实验台新能力，或将标定版 GR86 带入海岸/山脊试驾对比。

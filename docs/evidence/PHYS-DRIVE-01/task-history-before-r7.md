# PHYS-DRIVE-01 真实曲轴、有限离合与后驱开放差速

- 状态：in_progress。当前完整T1-r5a在隐藏后台PID37488运行；1377项pytest完整通过（8014.01s），0/17/23三种子启动通过；种子0十二车/30s弯坡通过（745.1s墙钟），种子23仍运行，随后功能组T2。
- 上游基线：ROT自动验收提交`2b7f908df29176ce99ccb1fb0d848ce318474b02`；端口子块`7745282cc00ba1d58da2a997597a999882e68363`。当前HEAD `771ddd0f059fc67719e6217a610162b7ab3e1748`；整车联合改动尚未提交、未推送。
- 用户完整要求与剩余项：[物理目标核对](../physics-goal-audit.md)。本任务只完成当前后驱传动闭环，FWD/AWD、限滑/轴惯量、悬架、估计器、实车型与总Gate仍须继续。
- 当前源：280份Python文件冻结于[candidate-validation-r5-source.zip](../evidence/PHYS-DRIVE-01/candidate-validation-r5-source.zip)，SHA-256 `2d4c92f167ebcde4d9b1e701464dbea6cf4e03732adda931ec157d37b584e715`。完整T1运行期间不改src/tests/tools Python。

## 行为与职责

1. `powertrain.py`：真实曲轴轴速/相对RPM、节气门/怠速/红线请求、有限离合与卸载换挡；prepare只推进控制，accept_step只接受共同积分。不用目标RPM或轮速重设机械状态。
2. `transmission_ports.py`：离合/双向效率/制动活动约束；`tire_drivetrain.py`：车身角速、曲轴及四轮的八维共同末状态，真实壳体反力和陀螺、符号明确的功/热。空挡无虚构输入轴惯量。
3. `vehicle_tires.py`：同一接触子步内联立胎体、轮转、制动与传动，向唯一Bullet车身提交真实冲量；原0.001N力残差、容量、能量与迭代门槛保持。
4. `vehicle.py`：玩家Control保留制动优先；显式研究VehicleCommand可双踏板、gear/clutch经有限执行器。显式gear覆盖自动direction，TCS读上一完整机械步的实际gear，空挡无驱动资格；gear=None及关闭有限机制保留原方向语义。
5. 两模式共用120Hz机械核心。游戏Je=0.02、困难参考Je=0.2kg·m²均为设计值；原动力曲线、驾驶辅助、制动硬件与电子控制增益保持。低速ESC只修参考连续性，原介入门槛不改。
6. 主动发动机请求共享原全负荷曲线能力；游戏道路软限速按实际挡位只削驾驶请求，有限怠速补偿仍受能力约束。绝不钳RPM、清轮矩、瞬移或关闭碰撞掩盖响应。

不建Manager/Registry/DI/通用动力学框架；内部明确接口直接访问，设备/文件/配置边界正常处理错误。legacy、ADAS、DS及旧证据只读。

## 当前证据

| 项目 | 已确认事实与边界 | 原始入口 |
|---|---|---|
| 当前相关T0-r5 | Ruff及131项pytest完整通过；135.08s，280源前后相同。含发动机能力、怠速/挡位、手动方向与空挡TCS、原研究请求 | [手动挡与TCS](../evidence/PHYS-DRIVE-01/manual-gear-tcs-r5.md)及validation-T0-manual-tcs-r5 |
| 发动机/原玩家集成T0-r4c | 当时141项完整通过，1086.69s；当前只增手动TCS分支，自动路径保持 | [能力与怠速](../evidence/PHYS-DRIVE-01/engine-control-boundaries-r4.md) |
| 标准两模式A/B | r4的44条已完成，逐tick主动能力最大越界0Nm，开放差速等矩，最大力残差0.000999784N、最小热−1.22e−13J在原门槛内；不要求所有指标改善 | ab-mode-control-r4；31724行gear=None，当前自动路径AST保持见[适用性](../evidence/PHYS-DRIVE-01/mechanical-evidence-r5-applicability.json)，保留原r4哈希 |
| 当前手动原生 | r5两模式12柔性/4刚性连续工况完成，真实换挡容量0，最大柔性力残差0.000999822542N，280源与当前冻结版相同 | native-mode-control-r5 / native-rigid-control-r5及[native回执](../evidence/PHYS-DRIVE-01/native-control-r5-receipt.json) |
| 坡停 | r4两模式5°/10s原门槛通过，位移0.00192839/0.00192758m、平均Fx约1026N；命令gear=None、增量分支不活跃，保留原源哈希 | grade-control-r4 |
| 参数与读回 | r5 reference-v10真实240tick，两模式74车辆/8制动/10TCS/10稳定/9输入字段；通用设计参考，非实车测量 | [当前参数](../evidence/PHYS-DRIVE-01/reference-v10-control-r5.json) |
| 独立机械/关闭分支 | 原机械台架/负对照、147316旧单元零差异、无外力原生细化已有冻结证据；原生单精度误差回升与游戏小正能量漂移原样保留 | [证据总入口](../evidence/PHYS-DRIVE-01/README.md)与control-calibration.md，不能当作当前完整T1 |
| 当前完整T1/T2 | T1-r5a的1377项pytest、三种子启动、种子0十二车/30s弯坡通过；种子23运行，T2未跑；无整轮通过结论 | logs/validation/PHYS-DRIVE-01-T1-r5a |
| 开销诊断/隔离原型 | 9600矩阵与3216完整候选组逐字节一致；16条原生/10560拍输入及完整状态字节一致，独立端口/联合机械532项通过。单车起步AB/BA平均CPU下降27.1%/29.4%，仅该短工况，非可见FPS。280生产源保持；最小补丁已准备/适用性检查通过，尚未应用 | [开销与等价核对](../evidence/PHYS-DRIVE-01/solve-cost-diagnosis-r5.md) |

## 完整验证与收口

当前T1命令：`.venv/Scripts/python.exe tools/validate.py T1 --area vehicle --area core --area gameplay --area traffic --area road --output logs/validation/PHYS-DRIVE-01-T1-r5a --timeout 9000`。进程局部PYTEST_ADDOPTS=-x，仅实际失败时立即终止；成功必须完整1377节点、0/17/23各1200步启动、0/23各30s弯坡。后台PID37488；stdout/stderr与运行协议在docs/evidence/PHYS-DRIVE-01/T1-r5a-*。

完整T1终态后核对280源SHA、保存全部原日志；失败先复现并保留原门槛。若当前T1通过，接入已核对的[matrix-reuse-proposed-r6.patch](../evidence/PHYS-DRIVE-01/matrix-reuse-proposed-r6.patch)，只复用相同矩阵，接口、模式顺序、物理参数及门槛保持。正式源码先跑T0的完整transmission_ports/tire_drivetrain台架并核对原生轨迹，再按`.venv/Scripts/python.exe tools/validate.py T2 --output logs/validation/PHYS-DRIVE-01-T2-r6 --timeout 9000`完成本功能组全部16项检查。最终同版完整T2覆盖全部T1模块/三种子启动/弯坡及功能组专项，不额外重复同版长T1；记录为真实T2，不改名r5a结果。新280源清单和源ZIP独立冻结，所有旧结果保持原版本归属。

必要修复后按实际新版本完整验证，独立runner不拼接通过。T2/本地提交后再按[下一布局范围](../evidence/PHYS-DRIVE-01/next-layout-scope.md)建立下一任务。实际前台性能、T3和用户两模式驾驶结论仍独立待验。

## 失败与中断档案

r1/r2完整T1见集成失败后主动中断；r3因独立发动机主动能力反例中断，r4因手动挡TCS反例中断。r5 exec10078/实际进程消失，raw summary停在running、45个通过标记，无终态数量，原因未确认；当前r5a以相同冻结源完整新跑，不拼接。各轮interruption.json、原日志/配置/源ZIP及初始失败均在[证据目录](../evidence/PHYS-DRIVE-01/README.md)。

旧施工与各轮当时状态完整保留于[任务历史](../evidence/PHYS-DRIVE-01/task-history-before-r5a.md)；当前事实以本页及当前实际源码/进程/终态报告为准。

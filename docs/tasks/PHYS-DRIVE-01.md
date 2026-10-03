# PHYS-DRIVE-01 真实曲轴、有限离合与后驱开放差速

- 状态：in_progress。r5完整T1-r5a全部7项通过：1377项pytest、三种子启动、双种子十二车/30s弯坡。当前r7相关T0完整671项通过（78.94s）、16条原生完成；完整T2-r7已失败终止：439项pytest通过、1项护栏连续刮擦失败（330拍＜600拍）；后续14项检查未跑。280源前后一致，原始日志已归档。
- 上游基线：ROT自动验收提交`2b7f908df29176ce99ccb1fb0d848ce318474b02`；端口子块`7745282cc00ba1d58da2a997597a999882e68363`。当前HEAD `771ddd0f059fc67719e6217a610162b7ab3e1748`；整车联合改动尚未提交、未推送。
- 用户完整要求与剩余项：[物理目标核对](../physics-goal-audit.md)。本任务只完成当前后驱传动闭环，FWD/AWD、限滑/轴惯量、悬架、估计器、实车型与总Gate仍须继续。
- 当前源：280份Python文件冻结于[candidate-validation-r7-source.zip](../evidence/PHYS-DRIVE-01/candidate-validation-r7-source.zip)，SHA-256 `19169bd9502cdda8d5c9ec90fe5270fe66a1dfa7249b35447223d702e02f8bc4`，清单validation-r7-source-before.json。该版本运行前后280源SHA一致；r5/r6/r7源ZIP与原日志各自保留，后续实质修复使用新版本验证。

## 行为与职责

1. `powertrain.py`：真实曲轴轴速/相对RPM、节气门/怠速/红线请求、有限离合与卸载换挡；prepare只推进控制，accept_step只接受共同积分。不用目标RPM或轮速重设机械状态。
2. `transmission_ports.py`：离合/双向效率/制动活动约束；`tire_drivetrain.py`：车身角速、曲轴及四轮的八维共同末状态，真实壳体反力和陀螺、符号明确的功/热。空挡无虚构输入轴惯量。
3. `vehicle_tires.py`：同一接触子步内联立胎体、轮转、制动与传动，向唯一Bullet车身提交真实冲量；原0.001N力残差、容量、能量与迭代门槛保持。
4. `vehicle.py`：玩家Control保留制动优先；显式研究VehicleCommand可双踏板、gear/clutch经有限执行器。显式gear覆盖自动direction，direction=0可保持实际挡位。有限传动的TCS统一读上一完整机械步实际gear，空挡无驱动资格；关闭有限机制保留原方向语义。
5. 两模式共用120Hz机械核心。游戏Je=0.02、困难参考Je=0.2kg·m²均为设计值；原动力曲线、驾驶辅助、制动硬件与电子控制增益保持。低速ESC只修参考连续性，原介入门槛不改。
6. 主动发动机请求共享原全负荷曲线能力；游戏道路软限速按实际挡位只削驾驶请求，有限怠速补偿仍受能力约束。绝不钳RPM、清轮矩、瞬移或关闭碰撞掩盖响应。

不建Manager/Registry/DI/通用动力学框架；内部明确接口直接访问，设备/文件/配置边界正常处理错误。legacy、ADAS、DS及旧证据只读。

## 当前证据

| 项目 | 已确认事实与边界 | 原始入口 |
|---|---|---|
| 当前相关T0-r7 | Ruff及671项pytest完整通过，78.94s；覆盖发动机能力/换挡、原生TCS/研究请求、端口与联合守恒。8项自动挡保持/空挡待挂挡反例初测全失败，修复后完整通过；T0源码清单在执行后取样，不宣称前后哈希 | validation-T0-r7；validation-T0-auto-tcs-initial；[当前控制边界](../evidence/PHYS-DRIVE-01/automatic-gear-tcs-r7.md) |
| 发动机/原玩家集成T0-r4c | 当时141项完整通过，1086.69s；r5手动/r7自动TCS扩展各有独立反例和回归，旧结果保留原版本 | [能力与怠速](../evidence/PHYS-DRIVE-01/engine-control-boundaries-r4.md) |
| 当前标准两模式A/B（r7） | 44条完整完成、280源与r7冻结版一致；31724行全部字段与r4核对，仅两模式滑行扰动/倒车的TCS wheel_slips观测改变，其余字段精确相同。开放差速等矩、力残差0.000999784N、最小热−1.22e−13J仍在原门槛内 | ab-mode-control-r7；[全部字段对照](../evidence/PHYS-DRIVE-01/current-standard-r7-comparison.json)，旧r4源结果独立保留 |
| 当前原生（r7） | 两模式12柔性/4刚性/10560拍完成，真实换挡容量0，最大力残差0.000999822542N。12条完整字节一致；4条倒车仅前15拍TCS wheel_slips观测改变，其余全部字段字节一致；280源稳定 | [完整轨迹回执](../evidence/PHYS-DRIVE-01/native-production-r7-receipt.json)及native-production-r7-comparison.json |
| 当前坡停（r7） | 两模式5°/10s原门槛通过，位移0.001928389564/0.001927583046m、平均Fx1025.997381/1025.997277N；280源前后与r7冻结版相同 | grade-control-r7；[当前标准回执](../evidence/PHYS-DRIVE-01/current-standard-r7-receipt.json) |
| 参数与读回 | r5 reference-v10真实240tick，两模式74车辆/8制动/10TCS/10稳定/9输入字段；通用设计参考，非实车测量 | [当前参数](../evidence/PHYS-DRIVE-01/reference-v10-control-r5.json) |
| 独立机械/关闭分支 | 原机械台架/负对照、147316旧单元零差异、无外力原生细化已有冻结证据；原生单精度误差回升与游戏小正能量漂移原样保留 | [证据总入口](../evidence/PHYS-DRIVE-01/README.md)与control-calibration.md，不能当作当前完整T1 |
| 完整T1（r5）/当前T2 | T1-r5a全部7项通过、280源哈希一致，原始日志已归档。当前T2-r7失败：439通过、1失败，余14检查未跑；1561全套选择未完成，不拼接不同runner结果 | [T1完整回执](../evidence/PHYS-DRIVE-01/validation-T1-r5a/receipt.json)；logs/validation/PHYS-DRIVE-01-T2-r7 |
| 矩阵复用（r6） | 已正式接入，模式顺序/门槛/接口保持；532项正式T0通过，16条正式原生/10560拍与r5完整字节一致。原型单车短起步CPU下降27.1%/29.4%，非可见FPS | [开销与等价核对](../evidence/PHYS-DRIVE-01/solve-cost-diagnosis-r5.md)；native-production-r6-receipt.json |

## 完整验证与收口

当前T2命令：`.venv/Scripts/python.exe tools/validate.py T2 --output logs/validation/PHYS-DRIVE-01-T2-r7 --timeout 9000`。进程已退出；进程局部PYTEST_ADDOPTS=-x在真实失败时终止，本次439项通过、1项失败，pytest耗时2438.27s，Ruff通过，其余14项检查未跑。stdout/stderr与协议在T2-r7-*。T2同版包含全部T1模块、三种子启动、更长弯坡与功能组专项，记录为真实T2，不另重复同版长T1或改名r5a结果。

完整T2终态已核对280源SHA相同，原始日志与[失败回执](../evidence/PHYS-DRIVE-01/validation-T2-r7/receipt.json)已归档。失败为护栏连续刮擦最长330拍、要求600拍，根因尚待独立复现。失败先复现、保留原门槛；必要修复按新版本重新完整验证。当前原生与T0只证明对应范围，不代表完整T2/阶段通过。

必要修复后按实际新版本完整验证，独立runner不拼接通过。T2/本地提交后再按[下一布局范围](../evidence/PHYS-DRIVE-01/next-layout-scope.md)建立下一任务。实际前台性能、T3和用户两模式驾驶结论仍独立待验。

## 失败与中断档案

r1/r2完整T1见集成失败后主动中断；r3因独立发动机主动能力反例中断，r4因手动挡TCS反例中断。r5 exec10078/实际进程消失，raw summary停在running、45个通过标记，无终态数量，原因未确认；当前r5a以相同冻结源完整新跑，不拼接。各轮interruption.json、原日志/配置/源ZIP及初始失败均在[证据目录](../evidence/PHYS-DRIVE-01/README.md)。

旧施工与各轮当时状态完整保留于[早期任务历史](../evidence/PHYS-DRIVE-01/task-history-before-r5a.md)与[r7前任务历史](../evidence/PHYS-DRIVE-01/task-history-before-r7.md)；当前事实以本页及当前实际源码/进程/终态报告为准。

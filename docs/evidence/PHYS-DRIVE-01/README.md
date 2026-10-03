# PHYS-DRIVE-01 施工证据

2026-10-04终态更新：完整T2-r7失败，Ruff通过，pytest为439通过/1失败（2438.27s），护栏连续刮擦最长330拍＜原要求600拍；余14检查未跑，280源前后相同。[原始日志与失败回执](validation-T2-r7/receipt.json)。联合实现开发检查点`87712e3`已本地提交，用户授权本轮结束后推送，下一步独立复现原因。


当前以[r7控制边界与验证](automatic-gear-tcs-r7.md)和[任务包](../../tasks/PHYS-DRIVE-01.md)为入口。r5完整T1全部7项通过；r6正式矩阵复用532项T0、16条原生字节一致；r7自动保持挡位/真空挡TCS修复671项T0、16条当前原生完成，完整T2-r7已失败终止（439通过/1失败，余14项未跑）。当前280源ZIP为candidate-validation-r7-source.zip，T2终态为失败，开发检查点`87712e3`已本地提交，用户授权本轮结束后推送；阶段、可见性能、人工和整个goal待验。以下按版本保留施工时证据，旧running/未接入描述不代表当前状态。

当前r7标准44条A/B和两模式坡停已完整完成；31724行与r4逐字段核对，仅滑行扰动/倒车的TCS滑移观测改变，其他字段完全相同。新[回执](current-standard-r7-receipt.json)与[对照](current-standard-r7-comparison.json)保存自己的源哈希，不改写旧证据。

基线为已通过完整730项T1及全部专项的ROT实现`2b7f908df29176ce99ccb1fb0d848ce318474b02`，冻结源码与原始回执见[ROT归档](../PHYS-ROT-01/README.md)。本包仍在施工，整个物理goal保持active。

## 机械端口模块

`src/transmission_ports.py`已把预研的有限离合、双向齿轮损失与单轮制动活动集转为直接生产函数；两端口闭式解与三端口缓存明确约束，暖模式只改变检查顺序。没有迭代失败回退或末速度修正；无可行解显式抛出。端口容差保持1e−11，静止损失反力留在物理区间；尚未接到Vehicle驾驶路径，空挡由后续机械拓扑明确处理。

[T0-r1](validation-T0-ports-r1/summary.json)ruff及230项pytest通过。216个定向节点覆盖离合/齿轮/制动正负运动和锁止组合、两效率及两步长；另14个节点循环覆盖零容量、随机自由速度及两端口。独立嵌套有界求根与缓存活动集交叉对照，暖模式错配仍重新检查物理可行性。已注册完整vehicle测试集合。首次[T0](validation-T0-ports-initial/summary.json)仅import排序失败，pytest未跑；修正格式后通过，记录保留。

将正式端口函数接入冻结几何四轮联合台架：[48组比较](ports-joint-r1/comparison.json)读数与原预研状态精确相同，最大能量误差1.50093e−11J、角动量误差4.08562e−13Nms，最多7轮。原0.001N力残差与3e−9J能量门槛保持，275源码/测试/工具文件运行前后稳定。该结果验证端口迁移，整套联合求解和车辆连续驾驶尚未生产接入。

首次[联合包装失败](ports-joint/failure.json)发生在包装脚本提前创建输出目录，机械工况运行数为0；包装修正后另取r1目录，旧文件保留。实际运行包装副本在r1目录，入口脚本移到本任务目录时只改固定证据路径，未重跑已有效机械结果。

## 端口子块收尾时的后续验收

下一步：共同末状态求解的空挡/刚性轮胎/转向反力，真实曲轴及有限离合执行器，再接Vehicle玩家/NPC生命周期和连续换挡。每步先相关T0，完整任务结束才跑完整T1；本包尚无整车T1或A/B结论。功能组T2、整体T3、可见性能和用户两模式驾驶继续待验。未推送或发布。

端口子块实现/证据本地提交：7745282cc00ba1d58da2a997597a999882e68363；完整DRIVE任务保持in_progress，未推送。

## 当前整车候选与回归

真实曲轴与有限离合已接入唯一Vehicle/Bullet路径，`tire_drivetrain.py`共同解四轮接触、离合/双向齿轮、制动和五转子输运。Snapshot来自同一状态，输入允许gear/clutch直接请求。默认候选reference-v10/game-controls-v9；当前74字段（移除试算的3000RPM损失参考参数），旧75字段试验保留其当时配置，不能当作当前导出。

[联合T0-r2](validation-T0-joint-r2/summary.json)148项通过，原能量3e−9J、力0.001N与20轮门槛保持。首轮[146失败](validation-T0-joint-r1/summary.json)为从三维工具借用dot截掉曲轴/轮轴；生产修正为八维点积，不改期望。原生首轮[4失败/13通过](validation-T0-native-controls/summary.json)包含两项将有限制动残余压力误断为精确0、两项刚性冷初值20轮残差约0.0016N；分别核对真实压力与使用上一已收敛力暖初值后，[395项通过](validation-T0-native-controls-r2/summary.json)。添加冷/暖对照和完整世界非对角惯量/曲轴轴向旋转后，[403项通过](validation-T0-world-warm-r1/summary.json)。无迭代失败后冷启动回退。

[首批6条原生轨迹](native-r1/summary.json)、[6条松油/手动/中断换挡](native-shifts-r2/summary.json)、[4条刚性倒车/换挡](native-rigid-shifts/summary.json)完整运行，源码前后稳定。全部齿比变化容量为0，真正曲轴ω/RPM和功/热逐tick保存。它们是前一控制版的结果，后续控制变动不能沿用为当前自动验收。

[关闭分支147,316旧单元零差异](compat-off/comparison.json)，全部A字段及共同配置精确相同，B新增的powertrain_state=None明确记录。A由ROT源码ZIP解包在独立进程运行，解包目录已移到`logs/physics/PHYS-DRIVE-01-frozen-rot`；可从ROT ZIP复建，不重复提交273份冻结源文件。

[默认候选扩大T0](validation-T0-default/summary.json)421 passed/1 failed，279文件哈希一致，候选源码归档[default-source.zip](default-source.zip)。松油4s速度13.35566→13.06554m/s，未达到原>1m/s门槛；[完整松油轨迹](coast-initial/summary.json)显示早期自动换挡时速度先升高。恢复原换挡15%规则到实际燃烧请求后，[单节点仍失败](validation-T0-coast-shift-cut/summary.json)，减速0.63287m/s。保留原24Nm近似闭节气门损失口径（相对ω/怠速尺度形成本拍隐式系数）后，松油通过，但[短按和首半秒失败](validation-T0-coast-pumping/summary.json)。怠速补偿与驾驶请求相加后短按恢复，[两项仍失败](validation-T0-idle-additive/summary.json)：首半秒0.46332km/h、松油0.89918m/s。门槛保持，没有隐藏失败或把T0替代完整T1。

当前修复明确时序缺口：先形成本拍燃烧/损失请求，再用它预测有限离合容量；正在单独运行两个失败节点，结果以新原始日志为准。整体任务未收口/未提交新整车候选，无完整T1/A/B、原生有限旋转精度/坡停/再接触或完整NPC生命周期结论。目标继续active。

## 后续校准与当前冻结版本

上节为前一时点状态。[0.30s反馈24项T0](validation-T0-launch-calibrated/summary.json)、[17项原生分支](validation-T0-native-branches/summary.json)、[12条连续轨迹](native-calibrated/summary.json)、[轮胎/转子隔离与缺项负对照270项](validation-T0-isolation/summary.json)通过。[首轮完整T1](validation-T1-r1/interruption.json)见4个H1失败后主动终止，启动/弯坡未跑，280源码SHA一致；[候选源码ZIP](candidate-validation-source.zip)是失败候选，不是最终验收版本。[4项单独复现](validation-T0-broad-failures/summary.json)及[目标时序4失败/7通过](validation-T0-executed-launch/summary.json)保留。

[控制闭环和模式校准](control-calibration.md)说明ESC跨介入速度的零参考误削矩，以及两模式新增Je的设计标定；[连续参考28项T0](validation-T0-continuous-reference/summary.json)通过，原门槛/电子增益保持。正常游戏Je=0.02、困难参考Je=0.2，[当前完整参数](reference-v10-calibrated.json)为74顶层车辆/10稳定控制/9输入字段、两模式真实静置读回。[扩大T0](validation-T0-mode-calibration/summary.json)365通过/1失败，失败为新增首拍容量=0预期；改按真实有限执行器界后[4项研究请求T0](validation-T0-command-capacity/summary.json)通过，不拼接成完整runner通过。

[当前关闭对照](compat-off-r2/comparison.json)同时关闭有限传动/连续参考，147,316旧单元再次精确相同。[前一候选44条A/B](ab-calibrated/summary.json)已完成，但当时仅切有限传动、未含新参考/两模式惯量标定，不当作当前版本结果。[参考车8条原生完整机械账](free-native-initial/summary.json)与[游戏新惯量8条](free-native-game-calibrated/summary.json)保留全部世界角动量/能量符号；仅曲轴960Hz误差回升，游戏240/480Hz微小正能量漂移原样保存，机械台架3e−9J不等于原生有限世界精确守恒。

当前完整T1-r2在`logs/validation/PHYS-DRIVE-01-T1-r2`运行，原始会话89335；[280文件冻结源码](candidate-validation-r2-source.zip)SHA-256为08c15160d3efa5b0e5e0151ed9a1dc20113f3b45d04625d2f12752fa804d2828，[运行前SHA](validation-T1-r2-source-before.json)用于结束后核对。当前44条完整机制A/B在`ab-mode-calibrated-r2`运行（会话36300），只有有限传动/连续参考两个开关不同，完整配置和原生执行器输入保存。结果未预记通过；当前Python源/测试/工具保持冻结。整体任务仍in_progress，未提交整车候选，未推送。

上述A/B运行现已结束：[44条原生标准A/B](ab-mode-calibrated-r2/summary.json)22组全部完成；[两模式5°坡停](grade-calibrated/summary.json)原位移/力平衡/0.001N门槛通过；[当前4条刚性倒车/手动换挡](native-rigid-calibrated/summary.json)通过、全部齿比变化容量0。三组运行前后280文件SHA均与T1-r2冻结清单精确相同。B最大力残差0.000999784N，最小每tick热−1.22e−13J原符号保留；开放差速每tick左右输出转矩精确相同。正常游戏6s加速末速A21.4054/B21.0643m/s，困难参考A20.5455/B19.1909m/s；不要求所有操稳指标同时改善。

坡停10s位移游戏0.00192839/仿真0.00192758m，两者平均轮胎纵力约1026N，与理论1025.997N符合原1%门槛。柔性六工况两模式6s原生轨迹当前在`native-mode-calibrated`运行（exec73903）；完整T1-r2仍运行。当前刚性/坡停不替代完整T1、T2或用户驾驶。

当前柔性六工况两模式12条720步轨迹已全部完成，[回执](native-mode-calibrated-receipt.md)。最大力残差0.000999822542N、所有齿比变化容量0，280文件与T1-r2冻结清单完全相同。完整T1-r2已见三项集成失败，正在独立复现；尚未结束，不记完整通过。

完整T1-r2后来出现第4项玩家制动优先失败；[四项实际因果与明确研究配置](integration-regressions-r2.md)已记录。默认柏油当前无抱死，1.5倍研究硬件保留原抱死恢复严格门槛；TCS首拍退出而有限离合第二拍才零矩；纵向曲轴离地旋向产生真实偏航，横向对称配置原偏航/细化/一拍停车门槛通过。玩家请求优先级需在Control入口恢复，显式VehicleCommand工况保持。生产源码仍冻结，完整T1尚在运行，原始独立失败保存。

T1-r2已在3812.4s主动停止：可见1176个通过标记/4个失败标记（不是终态pytest数量），最后18000步高速生命周期未完成，全部后续启动/弯坡not_run。[中断与280源哈希](validation-T1-r2/interruption.json)原样保留。源码随后仅修改Vehicle玩家Control输入优先级、ABS明确配置入口和4份对应测试（6文件）；原动力/轮胎/硬件/电子参数未改。T0-integration-r3首轮仅Ruff要求pairwise、pytest未跑；修正后同完整相关短测r3a运行中，不预记通过。

恢复玩家Control制动优先后的完整相关T0-r3a：Ruff和21项pytest全部通过（347.1s），280源/测试/工具前后与integration-r3-source-before逐项相同。追加研究双踏板真实Snapshot与请求均为1的断言后，单节点T0-r3b通过（28.8s）；玩家输入优先与研究请求独立口径均验证。原停车速度/时限、0.4s倒车等待、真挂挡之后半秒<−0.5m/s、偏航0.001°、严格距离细化及最后一拍停车门槛保持。

新完整T1-r3已运行：原完整vehicle/core/gameplay/traffic/road入口，exec59196；进程局部PYTEST_ADDOPTS=-x，仅失败时立即终止，成功须完整所有选定节点。280源冻结ZIP candidate-validation-r3-source.zip，SHA-256为63223cea9fc5f64dbc2baaa5092a2127cdccfd8451402b542ae0955f58b1be55；未预记通过。r2标准机械A/B等均显式VehicleCommand，除apply_control之外所有Vehicle方法AST及其余src字节不变，适用边界记录在mechanical-evidence-r3-applicability.json，保留原r2 SHA而不改写成r3。新Control全轨迹driver-brake-diagnosis-r3两端SHA稳定，真倒挡半秒−0.66009m/s。整车施工仍未提交/推送，T2/总Gate待验。


## 发动机能力边界复核

当前T1-r3已因独立主动转矩越界反例终止，[中断](validation-T1-r3/interruption.json)记录1058.7s、1106个通过进度标记、无pytest失败/终态数量，后续启动与弯坡not_run，280SHA稳定。[初始数值](engine-envelope-initial.json)含600RPM全油门110Nm曲线却请求151.8879Nm；原12条标准原生轨迹均未进入越界域，证明标准工况不能代表所有机械负载能力。

[新增边界初测](validation-T0-engine-envelope-initial/summary.json)17失败/55通过；真实主动请求受原曲线能力限制、轴速保持真实后，[相关T0-r4](validation-T0-engine-envelope-r4/summary.json)102通过，280SHA稳定。20Nm能力不能凭空抵消24Nm怠速损失，原生怠速自然下降。

[实际挡位初始反例](game-gear-limit-initial.json)及[6项初测](validation-T0-gear-limit-initial/summary.json)3失败/3通过：游戏显式倒挡direction=0漏软限制、空挡body速度错误限制曲轴。游戏策略已按实际挡位修正、所有原数值保持；困难模式无游戏限速。扩大相关T0-r4b在exec20813运行，当前控制版专项/完整T1继续待验，未提交/推送。

## 当前控制能力 r4

[发动机能力/实际挡位/自由怠速边界](engine-control-boundaries-r4.md)：141项完整T0、44条当前标准A/B、12柔性/4刚性传动及两模式坡停完成，280源哈希稳定。1365节点完整T1-r4在exec93821运行，未预记通过；T2/人工/可见性能与整个goal待验。

当前r5以[显式挡位/TCS交叉边界](manual-gear-tcs-r5.md)为入口：131项完整T0通过，1377项完整T1在exec10078运行；r4 T1主动中断记录保留。

[360步联合求解开销诊断](solve-cost-diagnosis-r5.md)已完成，定位候选逆矩阵预计算；仅插桩定位，非可见性能Gate，当前完整T1源码保持冻结。

当前完整运行为隐藏后台T1-r5a，旧exec10078中断已存档，不能沿用其running状态。独立矩阵复用核对见同一开销诊断：9600矩阵及3216完整候选组逐字节相同；仅证据目录实验，生产源码尚未接入，完整T1/T2仍待终态。

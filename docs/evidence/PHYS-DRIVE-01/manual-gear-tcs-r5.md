# 显式挡位与TCS统一机械方向

## 原生反例

显式gear覆盖自动direction用于传动，但旧TCS仍按direction判断资格/滑移符号。低附着原生2秒核对：游戏倒挡direction=0时TCS全程未介入、峰值后轮滑移19.4651；direction=-1时223tick介入、峰值0.474093。困难模式对应峰值19.4857/1.95150；前进也存在同类遗漏。完整12条独立诊断及280源SHA保留在manual-gear-tcs-audit-r4.json。它不是新版本结果。

新增两模式前进/倒车×零值/相反自动方向8项整车原生对照，初测8失败；两模式真空挡落定后一次初始化残余轮转、检查电子驱动请求4项初测4失败。原代码、测试、完整日志分别保留在validation-T0-manual-tcs-initial与validation-T0-manual-neutral-initial。

## 实施与验证

有限传动且显式gear非None时，Vehicle的TCS方向取上一完整机械步实际gear的符号；空挡为0。自动请求gear=None及关闭有限传动路径保留原direction语义。未改TCS资格之外的控制增益、预测/执行器时间、制动硬件、动力曲线、机械求解或120Hz时序。VehicleCommand说明明确gear覆盖自动direction，车型电子控制仍有效。

完整相关T0-r5：131 passed（135.08s，runner135.7s）、Ruff通过，280Python文件前后SHA一致。两模式8项逐tick完整CarState完全相等，且真实TCS实际介入；4项空挡验证始终scale=1、无TCS轮制动、真实D=0。与发动机曲线、怠速、实际挡位和原玩家/研究请求测试同一runner完成。

## 源码与旧证据适用性

r4完整T1在442.652s主动终止，126个通过标记、无pytest失败，无终态完整数量，全部启动/弯坡not_run；validation-T1-r4/interruption.json及280冻结源码原样保留。不能把主动中断标成完整通过。

r5仅src/vehicle.py、src/vehicle_state.py说明、tests/test_finite_powertrain.py改变。去掉新增手动分支后Vehicle完整模块AST与r4一致，VehicleState仅说明改变；r4标准A/B全部31724行gear均None，故其实际执行路径保持，证据继续保留原r4哈希。[适用性记录](mechanical-evidence-r5-applicability.json)。手动挡轨迹须新跑r5，不借旧哈希冒充当前结果。

当前完整T1-r5a共1377节点及启动/弯坡，隐藏PID37488；进程局部PYTEST_ADDOPTS=-x，完整终态尚未取得。冻结280源candidate-validation-r5-source.zip SHA 2d4c92f167ebcde4d9b1e701464dbea6cf4e03732adda931ec157d37b584e715。当前整车联合实施未提交/推送，T2/T3/可见性能/人工驾驶与整个goal未完成。

T1-r5执行会话10078在后续读取时消失，进程亦不在、raw summary仍running，日志45个通过标记且无终态；原因未确认，validation-T1-r5/interruption.json保留当时完整源280哈希一致。以同一r5冻结源码隐藏启动完整T1-r5a，PID37488，输出logs/validation/PHYS-DRIVE-01-T1-r5a；两个中断/新跑结果不拼接。

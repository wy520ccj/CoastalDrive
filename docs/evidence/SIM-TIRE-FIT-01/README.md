# SIM-TIRE-FIT-01 部件标定与应用链

基线bde41b6，隔离树codex/simulation-fidelity，C:/Users/15120/.codex/worktrees/simulation-fidelity/CoastalDrive。本块不改变轮胎/悬架/传动方程或默认车型，也不覆盖main游戏AI的文件。

## 已验证事实

- 独立手写公式生成的三轮荷纯滑移拟合、两留出轮荷纯/联合滑移验证；来源始终synthetic。3N扰动后μ0.9199701、Cx0=81933.694N/κ、Cα0=65009.493N/rad、pD=.8600270、pκ=.7507029、pα=.7798855；真值分别.92/82000/65000/.86/.75/.78。5次优化、秩6、条件数18.1967，保持固定形状/基准/弹性等。
- 仅将联合验证Fx改为一半，拟合参数逐值相同，但验证不通过；rejected没有候选文件。证明留出未参与拟合，而不是多调参数消除验证错误。
- 2750/4500N、纵/横共四个解析小滑移松弛核检查通过；已拟合刚度进入实际接触核，固定弹性/阻尼仍给出推导τ=(C/v+c)/k的离散响应。它是模型解析核对，**不是实测瞬态验证，也没有辨识k/c**。
- 同一100km/h参考车、相同μ=.9199701266和ABS、120Hz/两子步，原参数A=46.052306m/3.291667s，候选B=45.667117m/3.266667s；差异为六个物理字段（后轴刚度与前轴同部件联动），不是单参数A/B。不改变质量/惯量/执行器/碰撞或步长。源/原生指纹在各次运行前后相同，导出后加载信号/完整快照相同。
- 工程配置→唯一完整Simulation→实际力阶段刚度→记录→复算逐值相同；不依赖候选文件再次读取。来源副本不被调用方后续编辑改变。
- 720/1080公共文件导入接口、实际名称悬停/F1/Esc、参数与来源/条件读回、0.25s实际试验、车型菜单切换清除覆盖通过。每尺寸3图；已目视代表图，原生文件选择对话框未自动操作。

## 收据和复现

- T0：`tools/validate.py T0 --tests tests/test_tire_calibration.py tests/test_lab_records.py tests/test_vehicle_parameters.py --output logs/validation/SIM-TIRE-FIT-01-T0 --timeout 120`，16项/Ruff通过。
- T1：`tools/validate.py T1 --area lab --tests tests/test_vehicle_parameters.py tests/test_vehicle_designs.py --output logs/validation/SIM-TIRE-FIT-01-T1 --timeout 180`，48项/Ruff、0/17/23各1200拍通过。新增标定测试已进入lab映射。既有485项轮胎物理有效结果复用，不重复长测。
- T1后只增加来源深复制及其检查，final-T0 15项/Ruff通过；GUI有效范围复用，物理未变。
- 随后补完整数据范围及F1轮荷覆盖说明，系数逐值保持；domain-T0 14项/Ruff和两尺寸3图通过，完整车A/B复用、不重跑。accepted-domain为补范围后的当前候选；accepted为初始报告，vehicle-AB原始记录不回填字段。旧报告未保存范围时明确显示无法声明区间覆盖。数据范围文件边界校验也列入最终短检查。
- 最终scope-T0 15项/Ruff通过（增加损坏范围文件拒绝）；delivery-720/1080为最终三张图和GUI收据，包含未通过候选拒绝/原配置保留、实际F1/条件/轮荷范围/拟合来源和车型菜单清除覆盖。原生文件选择器未自动操作，使用公共文件导入接口。较早ui-*证据保留版本用途。
- 实际A/B：`tools/physics/tire_calibration_check.py --output logs/SIM-TIRE-FIT-01/probe`。accepted/rejected输入、条件、报告和预测CSV保存；vehicle-AB.zip保存完整两次原始记录。summary.json、calibration.png及图代码在tools/design/plot_tire_calibration.py。
- GUI：`tools/tire_calibration_ui_check.py --model logs/SIM-TIRE-FIT-01/probe/accepted/candidate-vehicle.json --output logs/SIM-TIRE-FIT-01/ui-final-720 --height 720`，1080同入口。source_kind及压力/温度/速度的说明均显示“合成算法恢复值，非实测”。
- 首次Ruff导入/条件表达/测试闭包绑定告警已修；首个独立检查脚本缺tools导入路径，在物理启动前失败，补路径后同命令通过。失败不记为通过。普通离屏帧缓冲告警保留。

没有实测轮胎台架/整车数据用于标定，现有曲线还不支持外倾推力/气胎回正力矩/独立簧下自由度。T2/T3、人工体验、主目录整合及总体仿真准确度Gate未完成。下一补足有受力/能量依据的回正/外倾与K&C机制，再处理簧下质量及径向柔性，沿[真实性路线](../../simulation-fidelity.md)继续。

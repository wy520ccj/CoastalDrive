# LAB-PARAMETER-05 工况参数适用性与启动逻辑

- 状态：awaiting_user；实现、相关自动回归与实际窗口短检完成，新工况参数体验待用户确认；基线main/2ad33f1，施工前工作区干净。
- 用户要求：继续修逻辑BUG，当前实验不允许/不使用的参数不可选中编辑。
- 范围：按真实command_at/path_command消费关系配置数值字段；禁用鼠标/Tab/写入、有效字段解析、工况说明、启动前置校验与执行器配置入口；保持物理方程/固定步/硬件不变。
- 主要验收：10工况适用矩阵、禁用字段真实输入不改变、重新启用可编辑、无关非法文本不阻止启动、有效刺激时间校验、缺工程模型时保留已有结果、初始执行器可配置、T0/T1与实际渲染。

## 适用规则与实现

源码消费依据：`LabExperiment.command_at`、构造时的硬件覆盖、`lab_maneuvers.path_command/target_point/bump_geometry`。规则位于`lab_inputs.MANEUVER_FIELDS`，配置界面、Tab、窗口输入和解析共用；物理仍从LabOptions/VehicleCommand读取，不依赖UI状态。

| 工况 | 通用字段以外可编辑项 |
|---|---|
| 直线制动、参考双移线 | 无；双移线路径固定并由驾驶员算法控制转向 |
| 对开附着制动 | 右侧附着 |
| 阶跃转向、固定转角、正弦转向 | 目标转角、输入起始；正弦频率固定0.5Hz |
| 执行器输入 | 目标转角、油门、制动、挡位、离合；无有限传动时挡位/离合禁用 |
| 定圆试验 | 定圆半径；目标车速用于初速与自动车速控制 |
| 单侧凸起/轮跳 | 凸起高度、长度、距离 |
| 单侧凸起/制动 | 凸起高度、长度、距离、输入起始 |

通用字段：初速（两种路径试验显示目标车速）、路面附着、时长、质心高度、轮胎基准载荷。ABS/ESC是实际硬件开关，仍允许选择；不能仅因驾驶员无制动请求就禁用ABS，ESC也可产生制动请求。

- 非适用字段原值保留供切回工况继续编辑，PGEntry直接禁用，不接收焦点、键入或Tab；标签/底色变灰并有当前工况说明。启动不解析这些字段，记录中的非适用值使用合法默认值；灰色非法残值不阻止其他试验。
- UI有效输入起始必须早于时长，否则定位输入起始并中文提示。该检查只约束新建UI试验，不改写既有记录或禁止后端用于无刺激对照的短记录。
- 缺少独立轮心模型时两种凸起试验的开始按钮禁用并标明原因；直接调用启动入口也在关闭旧世界前拦截，原B/A与图表保留。真正求解/初始化异常仍走原失败路径。
- 执行器入口在选择工况后即可打开并确认初值；尚无匹配活动试验时确认不创建世界、不改变已有结果。仅当前车型/工况匹配的活动执行器试验接受实时请求。非有限传动不解析无效挡位/离合并生成前进方向请求，修复此前仅传gear导致油门无驱动资格的情况。
- 目标转角通用数值范围在LabOptions验证；实际当前工程硬件上限在LabExperiment创建世界前验证，避免导入40°硬件仍受目录车型上限错误阻拦。
- A/B仅同工况且同为停车距离或同为行驶距离时显示差值；其余只并列展示，避免停车距离与总路径直接相减。

## 验证与边界

- Double T1：`.venv/Scripts/python.exe tools/physics/run_sim_double.py tools/validate.py T1 --area lab --tests tests/test_lab_ride.py tests/test_lab_ride_braking.py --output logs/validation/LAB-PARAMETER-05-T1 --timeout 300`，Ruff、176项、种子0/17/23各1200拍通过。该批在最后标签颜色同步前，功能代码相同；最终颜色调整后相关全选T0覆盖。
- 最终Double/普通T0：`tools/validate.py T0 --tests tests/test_lab_ui.py tests/test_lab_inputs.py tests/test_lab_experiment.py --output logs/validation/LAB-PARAMETER-05-T0-final|LAB-PARAMETER-05-T0-normal --timeout 300`，分别经双精度启动器/普通venv运行，各116项及Ruff通过。
- 原失败保留：T0-first为SIM102嵌套条件；T0-selected为共享UI测试输入准备漏重置离合；此前second/new误重复传`--tests`，仅执行最后9项，未计为UI覆盖，已由最终正确nargs命令替代。无失败改填成功。
- `tools/lab_input_check.py --output logs/lab-parameter-05/input-double`经Double运行通过：10工况各循环两遍，原生窗口输入设备验证可用字段数字/小数/负数、不可用字段不抢焦点且输入不改变、重置和重新启用；普通/执行器字段、退格/Tab/快捷键检查通过。
- `tools/lab_workflow_check.py --full --output logs/lab-parameter-05/workflow-double`经Double运行通过：5车型各6拍，8种普通工况各12拍，轮跳360拍、凸起制动185拍，138说明页与导出/载入/回放/A操作；这些短工况不等于每工况完整物理/性能验收。
- 最终20张渲染覆盖1280×720/1024×768各10工况，已查看制动/定圆/轮跳的适用项、禁用按钮、说明与间距；实际可见新窗口定圆目标转角点击后输入9保持3.0，未得到编辑焦点。普通窗口/最大化和用户A/B曲线已查看。代表图与summary在`docs/evidence/LAB-PARAMETER-05/`。
- 用户新一轮适用性体验待确认；未重跑全库、T2/T3或性能；未修改物理方程、阈值、机械120Hz、游戏操控、工程硬件或五扩展。

## 用户数据与交付

- 替换窗口前经真实UI导出用户当前定圆B及baseline-A至`C:/Users/15120/AppData/Local/CoastalDrive/experiments/20261017-024219-661184`；A/B各1681样本、14秒，原CSV/快照/报告/配置保留。旧窗口在新窗口确认载入后关闭，避免版本混淆。
- 新窗口“CoastalDrive · 车辆实验室 · 工况参数修正版”恢复A/B、参考FWD、目标70km/h、μ1.7、时长14s、半径60m；不把新默认值覆盖用户记录。`logs/manual-playtest/lab_parameters_fixed.py`；日志确认A/B 1681/1681样本，实际窗口已最大化。
- 当前基线2ad33f1，本任务独立本地提交保存，未推送。

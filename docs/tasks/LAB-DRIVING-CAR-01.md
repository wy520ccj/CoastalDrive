# LAB-DRIVING-CAR-01 明确载入当前驾驶车硬件

- 状态：done（本功能自动验收完成，人工体验待确认）；基线main/e17a85a1，开始前干净。上一前胎快捷配方为progress，持续目标active，本地无推送/发布。
- 功能/证据本地提交`34fa7ab7`；82份原始/压缩文件和5源码指纹均逐项核对索引/工作区，提交后干净，提交号由后续文档提交登记。
- 目标：游戏改装→返回保留的实验台→显式载入当前驾驶车→同工况新试验，旧结果不能被误认成新硬件曲线；不再要求手动找当前车辆JSON。
- 交互：记录菜单新增“载入驾驶车硬件”；只准备下一次实验，旧记录/原A/逐拍数据/游标/原报告/工坊或虚拟试车记录保持。运行中旧试验暂停，未关闭或冒充重跑；无驾驶车则禁用按钮并明确提示。
- 参数：完整车辆配置/参数元数据来自workspace_vehicle；切换车型选择但不触发默认覆盖。当前工况、速度、路面μ、时长、手动输入保持；清空质心/轮胎基准载荷两项硬件覆盖，ABS/ESC采用驾驶车配置，当前试验环境与驾驶条件不同须如实显示。参考积分/直接命令与游戏辅助仍独立。
- 不自动固定/替换A、不改游戏车辆或当前文件/方案/奖牌。新实验实际运行后才能作为新B，原旧B需要用户按“固定当前为A”才用于对照；已有A保持。
- 范围：VehicleLab直接方法、固定记录菜单按钮、相关测试与真实同窗/两库试验/渲染/证据/文档；无新状态框架、物理模型/阈值/默认车/SDK改动。原曲线与可见模型在新试验前仍显示旧试验。
- 验证：缺车、空结果、已有A/B与游标、运行暂停、重试/同窗交接、覆盖字段清理/其他草稿保持、实际新B配置和元数据/旧A字节保持；Normal/Double用游戏35→70配方与真实定圆A/B证实新硬件生效并保留取舍，导出后载回复核；宽屏/4:3。复用前胎道路7718拍与高速原规则证据，不重跑同一完整驾驶；相关T0/T1与三种子，原T2/实时/人工Gate开放。

## 实现与真实证据

- `VehicleLab.stage_driving_vehicle`直接读取当前驾驶车，设置下一次试验的完整配置/参数来源/车型，采用驾驶车ABS/ESC，清理两项硬件覆盖。旧运行只暂停，旧A/B、游标、模型回放、报告及工况/路面/手动输入保持；新试验开始时仍由原流程关闭旧世界并创建唯一权威参考世界。
- `ui/lab_workbench.py`固定记录菜单增加第5项“载入驾驶车硬件”，无驾驶车时禁用；没有弹出确认或自动开跑/替换A。旧结果存在时明确显示“显示旧试验 · 驾驶车将在下次开始生效”。
- 5项新实际UI/边界测试覆盖缺车、空结果跨车型、原A/B/游标/数值保持、运行暂停、ABS/ESC与环境分离、CG/载荷覆盖清理、实际下一次B硬件及游戏改装往返。未将规则或界面夹具称为驾驶通关。

两库各新跑原固定60km/h、40m半径、10秒参考定圆A/B。先用35k完成A并固定；去游戏快捷装70k，回实验台仍保留旧A/B与`.47`质心草稿，点新按钮后清理覆盖、保留原曲线，再真实运行新B。全程同一窗口，未改原配置/策略/积分/标准。

| SDK | A平均循迹误差 | B平均循迹误差 | B峰值侧偏 | B末窗最大速度误差 | 新参考拍数 |
| --- | --- | --- | --- | --- | --- |
| Normal | 3.175283m | 0.152581m | 5.793474° | 1.384535km/h | 2400 |
| Double | 3.175257m | 0.152588m | 5.793385° | 1.384497km/h | 2400 |

- 共4800新参考完成步，初始化快照不计步数；每份各1201完整快照和1200请求。导出A/B及B所带完整A，重新`load_record`快照相等；原`record_metrics/evaluate`从真实快照复核，新B因原侧偏/速度约束未通过，不授工坊奖牌。重复导出的baseline-A不是第三次试验。
- 新硬件确实生效，旧A快照保持；准备阶段旧指标/游标未改，当前驾驶车辆文件字节保持，同窗返回高速验车仍是70k。游戏道路结果明确复用`TIRE-TUNING-01`两库7718拍，非本批新跑完整课题；仅配方/往返流程是新执行。
- 现场工具直接完成步后手动刷新曲线，旧“试验已恢复”状态文字未走正常update完成分支；现场原图保留，数据/规则不受影响。最终`normal-preview/double-preview`用实际导出的A/B经原`import_record`重新载入并捕获“记录分析”/准备状态，模型与曲线仍是原真实记录，无新试验物理。已查看宽屏/4:3菜单、旧曲线保持和新B图；离屏渲染不能代替人工手感或实时Gate。

## 验证命令

- T0：`.venv/Scripts/python.exe tools/validate.py T0 --tests tests/test_lab_driving_car.py --output logs/validation/LAB-DRIVING-CAR-01-T0`，Ruff/5项通过。
- 新实际参考试验：`tools/lab_driving_car_check.py --output logs/validation/LAB-DRIVING-CAR-01-normal`；Double通过`tools/physics/run_sim_double.py tools/lab_driving_car_check.py --output logs/validation/LAB-DRIVING-CAR-01-double --size 1024 768`。两库passed，首末源码/SDK保持。
- 最终T1：`tools/validate.py T1 --tests tests/test_lab_driving_car.py tests/test_lab_ui.py tests/test_workshop_ui.py tests/test_design_loop_ui.py tests/test_workspace_transition.py tests/test_tire_tuning_ui.py tests/test_scheme_slalom.py tests/test_lab_records.py tests/test_lab_experiment.py`；Double同一范围经原启动器。两库Ruff、各87项及各seed0/17/23短测通过，pytest355.33/301.28秒。本批自动命令无失败；原现场工具状态文字区别见上条，不把复载图称为新试验。
- 归档`docs/evidence/LAB-DRIVING-CAR-01`，82份原始文件共38,460,164字节及最终5源码LF SHA；完整快照/JSON/CSV大文件按原字节gzip，清单同时记录归档与解压SHA，恢复原路径后可正常load_record。
- 本批无物理/默认硬件/原辅助/SDK/阈值改动，原机械模块SHA保持`c84bfb06cae9d51a46f5cdff69107f96e73c6757d2853ef46673d0710010e7a2`。T2/T3未重跑；原物理失败、实时、人工手感/趣味性Gate开放，持续目标active。

下一继续收敛“道路表现→试验取舍→下一次选择”的反馈，结合人工体验判断趣味性；不把更多参数入口当作游戏完成。

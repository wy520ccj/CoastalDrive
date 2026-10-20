# TIRE-TUNING-01 从课题直接选择前胎配方

- 状态：done（本功能自动验收完成，人工体验待确认）；基线main/b3c90eea，开始前干净。上轮高速验车功能为progress，持续目标active；本地施工，无推送/发布。
- 用户方向：不同改装影响挑战表现。本块让普通/高速过门说明页直接调整当前车前胎，预览→确认→同题驾驶→原实验台分析，不再要求先导入文件。
- 范围：现有35/45/50/70k教学前轴侧偏刚度四选一，其他完整硬件/道路μ/后胎/电子控制/驾驶输入不改。不是现实品牌轮胎、不保证越大越好。原课程规则/成绩/巡回与主菜单入口保持。
- 保存：预览不安装；确认前把完整原车按内容SHA保存在当前工作区旁tuning-backups/，不覆盖已有副本；候选用现有WorkspaceVehicle原子保存成功后才应用会话。清除当前原方案/试验成绩/标定报告关联，保留原文件和可恢复原车。相同刚度不变更关联或写盘。恢复严格核对副本名/SHA/格式/车型，失败保留当前车辆。
- 交互：一个固定前胎面板，鼠标/键盘选择与取消/保存失败提示；恢复上次安装前车辆，可跨程序重开。返回后仍在原普通/高速课题，启动沿用新车/原输入。原车库同车型换色保持改装、换车型按既有默认；同窗实验台保存原记录/草稿，无自动重跑或虚构收益。
- 验证：纯持久化/相同车/不改其他参数/关联失效/恢复/坏或缺副本/写失败，实际UI模式/模态/键盘/取消/原车库/同窗实验台；Normal/Double用新入口实际35k失败→70k高速过门成功，逐拍原规则复核、原方案与配置字节保持、独立进程恢复改装/恢复原车、宽屏/4:3实际图。复用高速题先前全规则/驾驶证据；本批相关T0/T1及三种子。
- 禁止：物理/默认调校/输入辅助/SDK/路面μ/原课题阈值，自动安装/隐藏写盘失败、让旧工程奖牌替新硬件背书、通用改装框架/页面注册器、并行agent。原T2失败/实时/人工Gate开放。

## 实现与新实际结果

- `src/tire_tuning.py`只替换前轴侧偏刚度；完整原车（含方案编号、原报告、标定元数据和工程成绩）按内容SHA放入`tuning-backups/`。旧副本校验后复用，损坏副本不覆盖；候选写入成功才交给菜单，原子写失败当前车与主文件保持。同配方不写文件、不解除关联。
- 固定`TireTuningPanel`在普通/高速说明页打开，预览与安装分开，键盘/鼠标/取消/文件失败提示；恢复引用只能是64位十六进制副本名，严格核对内容/车型后恢复原车。恢复完整车也恢复其电子开关，当前输入模式保持。主菜单/其他课题/原车库保持。
- 改装后的当前车清除原方案编号、工坊成绩、原标定/报告关联，显示“改装车”；旧方案库与原车副本保留。安装本身不授奖，不更新任何驾驶成绩。

两库用旧`DESIGN-SCHEMES-01`真实50k金牌方案作为输入（只复用方案/硬件，不重跑旧参考试验）：游戏面板先选35k并安装→高速验车失败→同页选70k安装→同一题金牌。全程原75km/h二值KeyboardController策略，不导入新工程文件，不改变其他硬件/μ/输入。

| SDK | 35k实际驾驶 | 70k实际驾驶 | 新记录拍数 |
| --- | --- | --- | --- |
| Normal | 1587拍，第3门失败 | 2272拍，11.402889秒金 | 3859 |
| Double | 1587拍，第3门失败 | 2272拍，11.402889秒金 | 3859 |

- 合计7718新真实驾驶记录拍，每拍原课题纯规则复核一致；首末源码/SDK保持，完整同窗。四种配方在其他条件下的收益不从此表推广；物理/原辅助/规则/默认车未改。
- 两库各另起实际独立`SessionProcess`，从保存的70k菜单先恢复35k，再恢复完整原50k与原方案/奖牌关联；当前车辆文件与原50k文件字节相等，驾驶成绩文件字节保持。恢复检查主动还原隔离目录的当前车，不是另一次完整驾驶。
- 旧方案库16份输入在两库均与旧归档原件或gzip解压内容字节相等，运行前后不变。`reused-scheme-inputs.json`引用旧源文件SHA、解压后的实际SHA；避免重复归档未修改的旧快照。
- 普通1280×720及Double1024×768已查看原方案、候选预览、已安装、重新打开与恢复原车实际图；它们是离屏预览，不代替人工手感/趣味性或实时性能。

## 验证与边界

- 核心T0：`tools/validate.py T0 --tests tests/test_tire_tuning.py --output logs/validation/TIRE-TUNING-01-core-T0`，初批16项/Ruff通过。后补合法工坊成绩关联格式夹具，原车恢复可带回原关联，不冒充执行了工程试验。
- UI T0：`--tests tests/test_tire_tuning.py tests/test_tire_tuning_ui.py tests/test_fast_slalom_ui.py tests/test_slalom_ui.py`，27过/1失败；唯一失败是旧说明页菜单数量仍期望3，已按新增配方按钮改为4，原切换/返回断言保持，失败原日志保留。
- 新实际流程：`.venv/Scripts/python.exe tools/tire_tuning_check.py --output logs/validation/TIRE-TUNING-01-normal`；Double经`tools/physics/run_sim_double.py tools/tire_tuning_check.py --output logs/validation/TIRE-TUNING-01-double --size 1024 768`；独立恢复追加`--restore`。两库均passed，恢复无新完整驾驶。
- 完整相关T1范围为`tests/test_tire_tuning.py tests/test_tire_tuning_ui.py tests/test_fast_slalom_ui.py tests/test_slalom_ui.py tests/test_vehicle_workspace.py tests/test_vehicle_design_entry.py tests/test_vehicle_schemes.py tests/test_driving_mode_ui.py tests/test_workspace_transition.py tests/test_driving_tour_ui.py tests/test_mode_lifecycle.py`；两库Ruff、各75项与各seed0/17/23短测通过，pytest223.81/194.05秒。
- 收尾新增“旧试验草稿不覆盖新驾驶车”实际同窗回归，单独T0节点`tests/test_tire_tuning_ui.py::test_previous_lab_draft_is_preserved_without_replacing_new_driving_car`，两库各1项/Ruff通过；仅新增测试，无生产改动，前面完整T1与新真实驾驶明确复用。
- 原工作区存在时实验台恢复旧参考配置/草稿；它们不是新配方试验。当前驾驶车仍保持新配方，来回不会被旧草稿替换。**下一任务补显式“载入当前驾驶车辆”入口，暂不自动替换原实验或改写旧曲线。**本批未声称旧工作区已自动装入新硬件。
- 归档`docs/evidence/TIRE-TUNING-01`，73份原始文件共8,938,554字节及最终8源码LF SHA；原始来源/字节数/SHA与明确复用的16份旧输入逐项可核对。旧物理T2失败/实时/人工Gate开放，本批T2/T3未跑，仅本地无推送。

# LAB-INPUT-SWITCH-04 工况切换输入与参数重置

- 状态：awaiting_user；实现与自动/实际窗口短检完成，UU连续切换待用户复测；基线main/80e6ae4，施工前工作区干净。
- 用户复测：单框12.5成功后，换实验再次无法输入；新增重置参数功能。
- 范围：数值输入生命周期、工况预设、当前工况参数重置及实际连续切换检查。不改物理、工程硬件或游戏操控。
- 先复现切换后的事件/焦点路径；上批单个UU输入用例通过不代表连续切换已修复。
- 重置应恢复当前车型/工况下的试验输入与执行器输入，保留导入工程模型、已有结果与基线A；明确提示需重新开始才生效。

## 排查与修正

- 实际有两个长期运行窗口：`Vehicle Dynamics Lab`仍运行上批1e0971f的代码，`UU 数值输入复测`运行80e6ae4。只改源码不会更新已运行的Python对象；上批为了保留数据而保留两个窗口，增加了测试版本混淆。本次分别通过真实UI导出结果后关闭旧窗口，只开一个“车辆实验室 · 参数修正版”。
- 在原UU窗口重新打开高级面板后，实际数字1可输入、退格可还原；未稳定复现用户描述的间歇性字符丢失，不能证明远程或切换是唯一根因。
- 可复现的切换缺口：旧`apply_preset`保留编辑焦点；菜单展开/取消也不释放旧焦点。`LabOptionMenu`现在在展开前释放焦点，选择工况和程序化载入配置也释放焦点。数值框每次点击都会准备窗口IME状态，覆盖已有焦点不会再次触发focusIn的分支；字符仍只由PGEntry原链路写入。
- 默认值集中于`default_options`；切换工况写入该工况的速度/时长/起始时间，修复轮跳3秒等数值残留到制动/转向的情况。载入记录的`set_options`不再误触发工况预设后再覆盖。
- 配置栏与高级参数页均提供“重置参数”：恢复当前车型/工况的全部试验字段、ABS/ESC及执行器初值，路面附着取当前工程/车型值，质心/轮胎载荷留空采用模型值；保留车型、工况、工程模型及元数据、已运行世界/记录/基线A，提示重新开始后生效。

## 验证

- Double T0：`tools/validate.py T0 --tests tests/test_lab_ui.py --output logs/validation/LAB-INPUT-SWITCH-04-T0 --timeout 300`，Ruff及20项通过。
- Double T1：`tools/validate.py T1 --area lab --output logs/validation/LAB-INPUT-SWITCH-04-T1 --timeout 300`，Ruff、148项及种子0/17/23各1200拍通过。以上均由`.venv/Scripts/python.exe tools/physics/run_sim_double.py`启动。
- 补强重置测试，使用真实单拍结果/记录/方案A验证保留；第一次测试准备漏显式生成`LabRecord`失败，导致后续基线污染，原失败`LAB-INPUT-SWITCH-04-T0-results`保留。补齐测试准备后`LAB-INPUT-SWITCH-04-T0-results-fixed`的20项及Ruff通过，生产代码未再更改，T1复用前次同生产版本结果。
- `.venv/Scripts/python.exe tools/physics/run_sim_double.py tools/lab_input_check.py --output logs/lab-input-switch-04/input-double`通过：原生输入设备→MouseWatcher→PGEntry，10工况循环两遍，共20次菜单/面板切换；每次10个高级字段的数字/小数/负数与重置校验通过，并检查普通2字段、执行器4字段、退格/Tab/快捷键。此入口注入窗口设备事件，不能替代UU/IME真实消息验收。
- 真实UI：新窗口经菜单从轮跳切至阶跃转向，时长12.0输入5后显示12.05且只写一次；点击高级页“重置参数”恢复12.0、转角3.0、凸起高度.01/长度.9，5秒记录曲线仍在。1280×720原生渲染与实际普通/最大化窗口均查看，重置按钮无重叠。代表证据`docs/evidence/LAB-INPUT-SWITCH-04/`。
- 用户UU连续切换/输入/重置结果已请求，待回复；未重跑全库/T2/T3/性能，不宣称间歇失效彻底消除。

## 交付窗口与数据

- 用户五秒凸起结果：`C:/Users/15120/AppData/Local/CoastalDrive/experiments/20261017-021508-083530`，600拍、22.88m；其他旧窗口结果`20261017-021549-479109`。含CSV、报告、实验JSON和快照，原三秒结果`20261017-003855-900578`保留。
- 新窗口载入五秒记录，只读分析可继续开始新实验；`logs/manual-playtest/lab_switch_fixed.py`，启动日志`switch-fixed.*.log`。已实际核对只剩一个实验室窗口。
- 物理/游戏/工程硬件与默认参数模型未改；本批独立本地提交保存，未推送。

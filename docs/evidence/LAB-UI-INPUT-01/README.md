# LAB-UI-INPUT-01 验证

2026-10-17，基线main/1560d86。仅试验台UI、显示状态与检查；不改物理和游戏。

## 已确认问题与复现边界

- 鼠标获取焦点后，`entry.guiItem.getFocus()`为真而`entry['focus']`仍为0；原快捷键依赖后者，允许小数点误触发单步。直接读取真实状态修复，并在编辑弹层中屏蔽试验快捷键。
- 关闭弹层显式释放所有输入焦点，背景PGItem激活阻挡下层鼠标命中；编辑框聚焦高亮，Tab/Shift+Tab只循环可见输入。
- 工程配置属于选定车型；重复选择当前车型不应清空，实际换车型须明确解除。左侧常驻显示配置/轮心状态。
- 初始化失败原保留上一B数值、计时、游标；现在清B并保留A。固定/清除A立即刷新，非法参数保留旧试验时说明结果归属。
- “全部数字无响应”未在新开原版窗口稳定复现。原版通过实际鼠标与数字行/小键盘输入；确认上述焦点错误，不唯一归因。修复版Windows输入复核`0`→`.`→`KP_4`→`5`显示`0.45`，Tab将焦点移到定圆半径。人工体验结论待用户。

## 命令与结果

以下均用项目`.venv/Scripts/python.exe`，Double用`tools/physics/run_sim_double.py`隔离SDK：

| 检查 | 命令尾部 | 结果与日志目录 |
|---|---|---|
| 普通T0最终 | `tools/validate.py T0 --tests tests/test_lab_ui.py --output logs/validation/LAB-UI-INPUT-01-T0-final` | 10项/Ruff通过（随后同车型保留增量由最终T1/Double T0覆盖） |
| 普通T1 | `tools/validate.py T1 --area lab --output logs/validation/LAB-UI-INPUT-01-T1 --timeout 300` | 64项/Ruff及三个种子各1200步通过 |
| Double T0最终 | `tools/physics/run_sim_double.py tools/validate.py T0 --tests tests/test_lab_ui.py --output logs/validation/LAB-UI-INPUT-01-T0-double` | 10项/Ruff通过 |
| Double可见窗口输入链路 | `tools/physics/run_sim_double.py tools/lab_input_check.py --output logs/lab-ui-input-01/keyboard-double` | 16项；`GraphicsWindowInputDevice → MouseWatcher → PGEntry`，数字/小数/负号/退格/快捷键隔离/隐藏焦点释放通过；3张渲染已目视检查 |

窗口输入链路工具通过Panda输入设备注入按键，非操作系统硬件输入；Windows鼠标/数字行/小键盘/Tab另用Computer Use实际复核，不能相互替代。修复版留在可见窗口供用户体验。

首次T0失败2项：候选`overflow=1`引发Panda替换短文本游标断言，撤回后通过；日志`logs/validation/LAB-UI-INPUT-01-T0/pytest.log`保留。没有放宽断言或屏蔽异常。

当前目录的[input-check.json](input-check.json)、[高级参数](advanced-input.png)、[执行器](manual-input.png)、[工程配置状态](engineering-ready.png)为实际检查产物。完整原始验证日志仍在上述logs路径。未跑T2/T3/新性能检查，不声明用户体验通过。

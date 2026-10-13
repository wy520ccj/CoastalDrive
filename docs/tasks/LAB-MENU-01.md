# LAB-MENU-01 下拉菜单与悬停闪烁

- 状态：done（实现、自动输入和实际渲染检查完成；人工体验待确认）
- 基线：main / 6704b9a。
- 范围：实验室五类下拉菜单、相关回归与证据；保留已认可字体、布局和车辆方程。
- 初始未提交：setup.py、vehicle_suspension.py、wheel_contact_kernels.c、suspension_prepare.h及两份悬架准备测试；未纳入本任务。

## 原因与修复

使用Panda3D VirtualMouse连接真实MouseWatcher/DirectGUI，旧工况菜单每行高0.240375；持续悬停16帧，高亮索引在2/None间逐帧切换。`highlightScale=(.038,.038)`被原控件同时用于文字大小和frameSize乘数，命中区缩小导致鼠标离开、恢复后重新进入。菜单项继承默认RAISED与0.1边框，产生巨大的立体效果。[官方控件源码](https://docs.panda3d.org/1.11/cpp/_modules/direct/gui/DirectOptionMenu)与本地1.10.16实现对应，实际行为以本地版本为准。

新增局部LabOptionMenu，仅覆盖悬停颜色与展开位置；原选项值、选择回调、点击外部关闭沿用DirectOptionMenu。每行固定宽度/0.08高度、FLAT/零立体边框、细轮廓；悬停不改文字尺寸或命中区域。列表从控件左边缘向下展开，空间不足向上展开，并约束在窗口范围内。

## 验证

- T0：相关Ruff通过；`python -m pytest tests/test_lab_ui.py -q`，3通过（含命中区/文字大小回归）。
- T1：`python tools/validate.py T1 --area lab --output logs/validation/LAB-MENU-01-T1 --timeout 180`，20项相关测试、Ruff、0/17/23三种子各1200步全部通过。
- GUI：`python tools/lab_menu_check.py --output docs/evidence/LAB/menu-720 --height 720`；1080同命令替换output/height。VirtualMouse通过真实GUI事件开启菜单、遍历所有24行的中心和靠右区域各12帧，随后每类菜单持续悬停120帧；高亮索引/点击区域/字形尺寸稳定。
- 两分辨率各验证车辆、工况、ABS、曲线组、ESC的鼠标点击选择及外部关闭；各生成5张悬停截图，边界检查通过。没有创建实验物理世界，不把此项当作人工驾驶证据。
- 已查看工况/车辆/ESC及底部向上展开的曲线组截图；用户原图保存在menu-before.png。图形初始化曾漏掉DirectGUI子类initialiseoptions，首次脚本报错；补齐后最终两个尺寸检查均通过。
- [1080p工况列表](../evidence/LAB/menu-1080/maneuver-hover.png)、[720p曲线列表](../evidence/LAB/menu-720/plot-hover.png)。T1收据见menu-T1-summary.json。

## 交接

本地提交仅包含本任务，未推送/更新公开包，原悬架准备未提交文件保留。重启launchers/vehicle-lab.cmd加载；最终画面/悬停体验待用户确认。

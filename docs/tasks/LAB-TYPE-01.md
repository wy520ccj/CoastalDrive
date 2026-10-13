# LAB-TYPE-01 实验室小字清晰度

- 状态：done（实现、短回归、离屏检查完成；人工体验待确认）
- 基线：main / a8dff882fa9986a4c32a7b62600fd34af01a6c85。
- 用户反馈：Regular正文偏瘦、模糊；认可黑色标题与橙色大数值。范围仅实验室字体、辅助文字颜色及对应资源/证据。
- 禁止修改：布局、共享游戏主题、标题/橙色大数值字形、车辆物理、开始时已有悬架准备工作。无推送/发布。

## 实现

对比Regular、Medium、Bold及160/48 pixels per unit真实字形渲染后，采用官方思源黑体Bold，正文48 pixels per unit；辅助文字改为深海蓝灰（43/64/74），按钮0.035、图表刻度/读数0.034。标题仍Heavy、品牌仍Chakra Petch，橙色主指标字形不变。字体原文件与OFL许可/来源/SHA登记完整。

## 验证

- T0：相关4文件Ruff通过；`python -m pytest tests/test_lab_ui.py -q` 2通过。
- T1：`python tools/validate.py T1 --area lab --output logs/validation/LAB-TYPE-01-T1 --timeout 180`，Ruff、实验室19项完整相关测试、0/17/23三种子各1200步headless均通过。完整收据留在logs。
- GUI：`python tools/lab_typography_check.py --record logs/LAB-02/ui-1080-release/records/20261013-094108-207576 --output docs/evidence/LAB/typography-720-final --height 720`；1080同命令替换height/output。
- 两尺寸共10张截图，主界面/高级参数/真实信号/执行器控件/记录菜单。只加载原记录，不重新计算物理；执行器控件直接展开做排版检查，不能当作手动驾驶证据。
- 已查看主界面和各类面板，未见截断/文字重叠。字重/清晰度的最终体验仍由用户确认。
- [字形对比](../evidence/LAB/typography-comparison.png)、[720p](../evidence/LAB/typography-720-final/01-workbench.png)、[1080p](../evidence/LAB/typography-1080-final/01-workbench.png)。

## 交接

重启`launchers/vehicle-lab.cmd`加载；不关闭用户已有窗口。原未提交文件仍归悬架施工。本地提交范围以Git实际记录为准，未推送。

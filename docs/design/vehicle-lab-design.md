# 车辆实验室设计记录

2026-10-13，用户认可imagegen生成的[布局参考](vehicle-lab-reference.png)并授权落实；随后要求提高最小字号并尽量沿用参考图字体比例。旧VI菜单截图已排除，不作为设计依据。

## 落地规范

- 奶白底、深海蓝文字、海蓝A曲线、橙色B曲线/主要操作，与当前游戏视觉身份一致。
- 配置卡、车辆视窗、结果卡与两张宽曲线共同构成主屏；优先突出开始试验、停车距离、A/B差值。
- 高级参数、记录操作、详细信号按需展开；不常驻完整仪表列表。
- 正文和坐标数字使用官方Source Han Sans SC Regular；标题保留Source Han Sans SC Heavy及Chakra Petch品牌字。常规文字按720p至少约12px的级别排版，图表最小字同步放大，不使用旧像素字体。
- 图表刻度采用整洁数值范围；曲线游标对应真实记录，A结束后的时刻不外推A数值。
- 圆角卡片与按钮为程序几何/纹理，控件和文字保持可编辑。参考图仅指导布局，运行界面不铺一张静态截图。
- 制动距离和计算数据由真实试验更新，不强行复制参考图中的示意数字。

布局借鉴[CarSim动画/曲线联动](https://www.carsim.com/products/supporting/view/index.php)；信息层级和分组参考[NN/g视觉层级](https://www.nngroup.com/articles/visual-hierarchy-ux-definition/)、[邻近原则](https://www.nngroup.com/articles/gestalt-proximity/)。字体来源、SHA和许可记录见assets/game/ui/fonts/lab-font-source.json及asset-register.csv。

## 生成工具与原始提示

使用内置image_gen工具，无CLI/API Key；参考输入为首版真实实验室截图和当前游戏coastal-menu背景。生成输出原件保存于Codex generated_images，选定图片复制到本目录。图片中的布局和数值是设计参考，不是新增物理证据。

```text
Use case: ui-mockup. Create a polished 16:9 desktop UI design reference for CoastalDrive Vehicle Dynamics Lab, NOT a final software screenshot. Input image 1 is the current implemented lab screenshot: keep its genuine features but completely improve the cluttered layout and hierarchy. Input image 2 is the current game's original coastal menu artwork and is STYLE REFERENCE ONLY: match the warm ivory paper, deep ocean navy, sea blue, restrained orange, relaxed sunny coastal motoring identity. Main request: a refined calm coherent vehicle simulation workbench that feels part of this game. Make the layout implementable in Panda3D DirectGUI with editable elements. NO dark engineering theme. No dense tiny text. No giant dense numeric lists. 16:9 flat screen, no laptop or monitor bezel. Clear 24px gutters, aligned baseline grid, soft card edges, 3 font sizes. Top header with small italic COASTAL DRIVE wordmark and Chinese title 车辆实验室, unobtrusive 返回驾驶 and 记录 buttons. Left sidebar 22% width: one white/ivory card titled 试验配置 with tidy vertical labels above inputs: 车辆 设计参考车 RWD; 工况 100 km/h 制动; 初速 100 km/h; 路面附着 μ 0.60; ABS 开启; collapsed 高级参数. One prominent orange 开始试验 button at bottom. Central upper panel 55% width: generous REAL 3D viewport of an orange classic coupe on an understated flat warm-gray gridded test pad, controlled side/rear view. Viewport caption 车辆视窗 and a small view selector. Below viewport one clean row of playback controls 暂停 单步 回放 and a thin scrub timeline, no controls overlapping plots. Right 23% width: spacious result card titled 试验结果 with a small status 已完成, one large primary metric 66.02 m 停车距离, two clean smaller comparison rows A 43.58 m and B 66.02 m and small Δ +22.44 m, then quiet secondary numeric items 仿真 4.76 s, 计算 1.36 s. A details link 查看轮胎信号 instead of displaying all 4-wheel values permanently. Bottom main area beside left sidebar: TWO wide elegant plots in equally sized ivory cards, titled 车速 / km/h and 纵向加速度 / m/s²; readable faint grid, proper axes with sparse tick labels, smooth navy A and orange B curves, one compact shared legend and selected time cursor. In a clean footer put 导出 CSV / 报告 as unobtrusive button and tiny design label 布局参考 · 示例数据. Content should breathe; emphasize viewport, primary action and comparison result. Keep every label legible and no overlapping or randomly placed text. The design image is an illustrative UI reference, not evidence of physics results. Avoid invented extra features, gradients/glows, thick black outlines, oversized boxed menus, dozens of equal-weight buttons.
```

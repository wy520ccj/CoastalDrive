# 菜单组件素材

本目录为 Visual Identity v1 的界面组件素材。所有 PNG 均由项目脚本 `tools/make_menu_assets.py` 使用 Panda3D `PNMImage` 按像素绘制生成；没有外部图像、字体、贴图或烘焙文字。颜色来自 VI-01 主题约定：海军蓝 `#102B3A`、奶油白 `#F3EFE3`、亮白 `#FEFCF5`、橙色 `#F47C24`、金色 `#FFBD3F`。透明边角和画布外区域保留 alpha。

按钮保持透明背景，采用窄深色双边框、细亮边和轻投影。普通按钮提供 normal、hover、pressed、disabled 四种状态；橙色主按钮提供 normal、hover、pressed。文字由 UI 字体在运行时绘制，PNG 中不含文字。组件按源尺寸作为 Panda3D GUI 图像使用；按钮可按布局需求缩放。

| 文件 | 原始尺寸 | 用途 |
|---|---:|---|
| `button-normal.png`、`button-hover.png`、`button-pressed.png`、`button-disabled.png` | 512×112 | 主要菜单入口的奶白按钮状态 |
| `button-small-normal.png` | 320×80 | 次级入口/短操作按钮 |
| `primary-normal.png`、`primary-hover.png`、`primary-pressed.png` | 512×112 | 橙色主操作状态 |
| `panel.png` | 768×768 | 奶白信息面板底图 |
| `speed-panel.png` | 512×176 | 深海蓝速度/状态面板底图 |
| `icon-*.png` | 64×64 | 单色透明图标：stopwatch、palm、highway、garage、speaker、exit、retry、home、trophy、pin、wheel、car |

重新生成：在仓库根目录执行 `..\CoastalDrive\.venv\Scripts\python.exe tools\make_menu_assets.py`。脚本是本目录图像资源的唯一源文件；可重复执行，生成结果确定。

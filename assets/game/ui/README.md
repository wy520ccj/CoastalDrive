# CoastalDrive UI 资产

当前实现：UI-02，参考原仓库 graphic_design。主菜单为独立插画背景加真实文字、按钮和回调；驾驶过程仍是实时 3D。

- 字体：思源黑体 SC Heavy 用于中文标题、按钮、说明；Chakra Petch Bold Italic 用于速度、转速、计时及拉丁读数。精确版本、SHA-256、官方来源和 OFL 许可见 fonts/typography-sources.json。标题用轻微斜体处理，按钮保持正体。无需系统字体。
- 字标：wordmark.png 是按用户设计图单独生成的透明品牌资产；中文副标题仍是实时文字，不把操作文案烘焙进图片。
- 背景：backgrounds/coastal-menu.png 为同一参考图生成的无文字菜单插画。仅用于主菜单，不在驾驶和车库中假扮实时场景。
- 控件：components/ 下 22 张无文字 PNG，含按钮状态、面板、速度框和图标；tools/make_menu_assets.py 可重生成。当前菜单有三主三次入口；悬停/选择/按下有明确状态。
- 历史：Fusion Pixel 和原 panel.png/button.png 保留为 VI-01 资产，不再作为这轮正文/控件。Ark 仍未采用。Icon 继续使用 VI-01 项目生成的道路海岸图标。
- 来源：插画与字标见 asset-sources.json；控件由项目生成；字体按自身 OFL 许可。没有整包复制 DS 实现。
- 视觉仍需用户在实际窗口/DPI 下确认；未实现参考图中的小地图、车辆性能条和插画级实时环境。

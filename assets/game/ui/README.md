# Visual Identity v1 基础资产

- 主字体：Fusion Pixel 12px proportional zh_hans；固定文件哈希与来源见 fonts/font-source.json，原样携带 fonts/OFL.txt。整个界面和品牌字使用同一字体，不依赖系统字体、不静默回退。
- DS Ark 2026.09.01 在当前文案中缺「刹、滚、窗、避」，不采用；Fusion 覆盖检查的283个字符。像素字在非整数缩放下仍需真实窗口确认，小字号的布局优化留给页面任务。
- Logo：现有菜单标题位置使用实时字标 COASTAL DRIVE（theme.BRAND_NAME），不插入新图层、不引入独立系统字体。正式字标采用深海蓝、原有细线改橙色；不使用 DS 插画或 Impact/微软雅黑生成的 PNG。
- Icon：本项目 tools/make_ui_brand.py 用海面、道路、太阳几何绘制；16/32/48/64/128/256各尺寸原生绘制，ICO内嵌这些PNG。窗口通过 icon-filename 加载；不是DS复杂插画的缩小版本。现有打包任务没有添加exe资源编辑流程。
- panel.png/button.png：保持稳定版尺寸，用 tools/make_ui_textures.py 和 ui/theme.py 的主题色重生成。不是DS九宫格/控件库。
- 配色：奶白 #F3EFE3、浅纸白 #FEFCF5、深海蓝 #102B3A、橙 #F47C24、海蓝 #247E96；成功深绿、失败砖红是独立语义色。
- 本目录图标与纹理由项目程序生成，无外部图像。字体保留自身许可；新增几何图案与生成代码按项目源代码方式提供。

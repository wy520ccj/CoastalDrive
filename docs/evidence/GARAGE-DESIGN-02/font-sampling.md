# 菜单字体缩小采样

2026-10-23，基线`fc114699`，单线本地施工，无推送。上回合完成实际改装流程和本地提交，属于progress；持续目标仍active。本块是既有12—19页面设计的文字渲染修正，没有重新设计构图、换字体或新生成页面图。

## 问题与最终更改

原字体160 pixels/unit、FreeType scale2、单层FTLinear缩小；小字号把高分辨率字形直接取样，笔画出现锯齿和漏采。隔离实际车库对照确认多级采样改善边缘后，仅在`ui/theme.py::load_font`统一设置FTLinearMipmapLinear、纹理留边16和几何留边4；放大仍FTLinear、字号/字距/字体源/颜色/位置/实际命中区保持。

参考Panda官方[动态字体说明](https://docs.panda3d.org/1.10/python/reference/panda3d.core.DynamicTextFont)：缩小过滤由字体图集控制，纹理留边防邻字串入，几何留边防抗锯齿边缘裁断。没有加锐化/后期滤镜，也没有扩大UI或更换既有原生文字为图片。所有调用该字体入口的首页/车库/声音/辅助/生涯/结果/驾驶文字统一受益；实验台另有独立字体，不声称本块修改它。

## 验证与失败

- `.venv/Scripts/python.exe tools/validate.py T0 --tests tests/test_ui_theme.py tests/test_countdown.py --output logs/validation/GARAGE-DESIGN-02-font-T0`：7项通过，初候选几何留边8。
- 首相关T1：`--tests tests/test_ui_theme.py tests/test_ui_assets.py tests/test_countdown.py tests/test_career_ui.py tests/test_results_keyboard.py tests/test_driving_mode_ui.py --output logs/validation/GARAGE-DESIGN-02-font-T1`，37过1失败；失败为4:3多项解锁文字的透明几何留边相交约.00118显示单位，没有称该批全绿，三种子按fail-fast未跑。
- 几何留边8→4后，相关完整生涯UI T1：`tools/validate.py T1 --tests tests/test_career_ui.py --output logs/validation/GARAGE-DESIGN-02-font-spacing-T1`，19项及0/17/23各1200步通过。其他19项复用首批有效结果，没有称最后一版重跑全部38项。生产更改仅少量字体参数；不新增镜像实现的测试、不重跑完整赛事或T2/T3。
- 846个UI源码字面字符的图集诊断：中文Heavy/Regular、Chakra显示字与五个Tabler图标的文本advance/行高与原入口相同。`compare_atlas.py`按字体支持的字符测量，避免把Chakra/图标字体用于中文导致缺字警告。首版诊断误用同一中文样句触发该警告，不是程序实际页面缺字；早期一次断言未留完整差值，最终支持字符诊断重跑通过，不以早期输出替代。
- 该全字集压力样本的图集底层内存Heavy约46.63→48.06MiB、Regular46.06→47.81MiB，完整mipmap额外理论约1/3，不能宣称内存无增加。它涵盖源码所有文字，并非正常运行同时显示的内存或性能验收。实际多奖励夹具所观测的四字体图集base合计约21.06MiB，尚不含mipmap/GPU分配/其他字体；未作正式长窗性能或总内存结论。
- 初探针把smoke默认加载状态命名为home，实际图是加载中的旧HUD，不能当首页验收；仅其upgrade同场景对照有效。最终首页用正常`back_to_menu→refresh_panel`流程，由既有采集工具检查键盘往返。没有修改游戏启动行为掩盖夹具问题。

## 实际页面

以下命令均使用`.venv/Scripts/python.exe`且通过：

```text
tools/main_menu_design_check.py --output logs/validation/GARAGE-DESIGN-02-font-final-1280 --size 1280 720 --only 01-home 04-upgrades-0 09-audio 10-assists 11-events
tools/main_menu_design_check.py --output logs/validation/GARAGE-DESIGN-02-font-final-1024 --size 1024 768 --only 01-home 04-upgrades-0 09-audio 10-assists 11-events
tools/garage_design_capture.py --output logs/validation/GARAGE-DESIGN-02-font-final-1920 --size 1920 1080 --car game-tuned --only upgrade-tires paint
```

两幅正常菜单各5张，1080p车库2张，另4:3多奖励结果1张，共13张最终实际图；归档精选7张加原线性采样车库1张。全部0新驾驶拍、Snapshot保持；菜单检查两轮车库/涂装/声音/辅助/赛事返回和显示窗口4个不累积。1080p9星及奖励结果5星为明确隔离夹具，不是本轮实际完赛。已查看宽屏首页、4:3首页/升级及多奖励结果、1080p改装大图，文字与控件分区保持。

`font-sampling/`保存原摘要、验证日志压缩字节、诊断脚本和JSON、8张原图；manifest固定最终theme及图片SHA，并核对20个布局/物理/业务/字体源文件相对基线保持。原资源来源/许可未变，本轮无需引入新字体或第三方资源。

总包仍in_progress：用户实际审美/驾驶趣味性、整体光照和道路细节仍待继续。自动/离屏检查不能代签体验。

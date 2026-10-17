# WORKSPACE-ART-02 自然、克制的菜单与加载画面

- 状态：done（素材接入及自动检查完成，审美体验待用户确认）；基线main/591a99a，开始前工作区干净，单条施工线。
- 用户反馈：上一版加载插画AI味重，相关画面可重做；不要求与游戏完全一致；自然不是写实。用户选定简洁手绘（形体清楚、少量笔触、柔和配色），明确保持原UI。
- 范围：只替换主菜单、加载背景及实验台页眉引用的背景图；原布局、字体、按钮、文案与进度条完全沿用591a99a；窗口切换、物理、玩法和驾驶场景不变。
- 方向：简洁手绘插画、柔和色块、少量明确笔触、海岸公路与朴素车辆；不堆叠巨型云团、金光、灯塔/村落/山峰等观光元素。保留清晰文字和真实阶段进度。
- 验收：真实主菜单、加载中、恢复实验台在1280×720及1600×900渲染；检查文字对比、画面裁切、原有操作回调及窗口保持；相关T0/T1。素材记录真实生成来源，画面是否去除AI观感由用户最终判断。

## 最终改动

- 以用户最后选择为准：简洁手绘、清楚形体、少量笔触、柔和配色；保持原UI。照片式尝试及侧栏/底栏/页眉结构调整全部撤回，不进入交付。
- 两张配套背景：菜单保留原左侧留白，车辆避开原实验室卡片；加载图保留原底部文字/进度位置。实验台原页眉继续使用同一菜单图的原裁切区域。
- `main_menu.py`、`workspace_loading.py`、`lab_workbench.py`各仅替换一个背景路径。对照591a99a，把三个新路径归一回旧路径后，三文件全文完全相同，证据`ui-preserved.json`。原字体、字号、控件、位置、文案、颜色、回调、进度行为均未修改。
- 源素材由内置image_gen生成并做构图编辑；没有将生成插画伪称为人工手绘或真实摄影。完整提示词、源文件名与哈希见`art/ui/workspace-handdrawn-v2.json`，素材账新增两张图。旧素材及历史证据保留。

## 验证

- 最终普通T0：`tools/validate.py T0 --tests tests/test_ui_theme.py::test_distribution_includes_font_license_and_icon --output logs/validation/WORKSPACE-ART-02-handdrawn-T0 --timeout 300`，Ruff与新素材打包检查通过。
- 最终Double T1：`tools/physics/run_sim_double.py tools/validate.py T1 --tests tests/test_ui_theme.py::test_distribution_includes_font_license_and_icon tests/test_driving_mode_ui.py tests/test_lab_ui.py tests/test_workspace_transition.py --output logs/validation/WORKSPACE-ART-02-handdrawn-T1 --timeout 300`，44项与0/17/23三种子各1200拍通过。
- 实际界面：`tools/workspace_art_check.py --output logs/WORKSPACE-ART-02/handdrawn-720-final`；Double隔离入口同工具`--output logs/WORKSPACE-ART-02/handdrawn-900-final --size 1600 900`；普通另`--output logs/WORKSPACE-ART-02/handdrawn-4x3-final --size 1024 768`。均检查主菜单→加载→实验台→返回，原窗口和尺寸不变，GUI数量不累积，截图查看通过。三份报告与代表图片入`docs/evidence/WORKSPACE-ART-02/`。
- 首次全字体静态扫描报缺`⁻`；已分别检查591a99a和当前源，均由参数说明中`replace("s⁻¹", "1/s")`的输入匹配字符串触发，不是本次新增显示字符。该既有检查失败保留在`logs/validation/WORKSPACE-ART-02-T0`，基线对照入证据；本次未改字体和该扫描检查，最终T1明确选择本次相关模块与素材打包检查。
- 手绘初次截图工具仍把原位图wordmark当作文字取紧包围盒，工具报None；已改为仅检查原生车型说明文字，保留失败目录，最终三种尺寸通过。此前照片方向的渲染/检查不作为最终手绘证据。
- 与本任务同期的9af5414海岸坡面修复独立提交；本批只提交素材、三处引用、打包验证、界面检查工具及本任务文档证据。游戏场景/物理与原UI不修改，用户现有窗口和记录不动。

## 交付

- 本地提交，不推送。重新打开原启动器加载新背景；旧窗口若有内存记录，先导出。
- 人工审美以用户体验为准，未代填“去AI化验收通过”。T2/T3未跑，本批为素材替换。

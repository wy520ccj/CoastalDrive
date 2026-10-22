# 生涯驾驶HUD与赛事预览统一

2026-10-22，基线 `0ea945bf`，单线本地施工，未推送。前一增量GR86替换是进展；本增量处理驾驶HUD与车库割裂，以及赛前预览仍含旧方盒车的问题。总目标仍in_progress。

## 设计和实现

- 实际在内置浏览器查看[Neowin的FH5实机截图](https://www.neowin.net/amp/forza-horizon-5-xbox-series-x-review-a-refined-open-world-racing-experience-2/)，学习赛程/计时、仪表靠边分组、中央道路留白。只作设计研究，未把第三方游戏图片当运行素材。
- 内置ImageGen以本项目GR86实际道路图及既有01升级设计为参考，先生成 `docs/design/garage-v2/11-driving-hud.png`；同名prompt保留。原始生成文件在 `.codex/generated_images/01a15f39-fd2e-7d80-9d42-bf337638fc9a/exec-7948b00f-7410-4404-aded-dd07d248c470.png`，项目内保存完整副本。实现坐标见layout-contract第11节。
- `src/ui/career_hud.py`为直接的生涯显示控件；左上状态/目标、左下提示与键帽、右下车速/挡位/转速/辅助指示、右上暂停。使用现有字体和原生控件，不将生成图贴作HUD，也不生成虚构名次或小地图。
- 只读Snapshot/CareerResult/EVENTS：冲刺百分比、停车误差与停稳时间、绕桩真实门数/下一门；三星目标来自既有目录。ABS/TCS/ESC只反映真实开关/介入，原输入/键绑定/引擎显示标尺保持。其他玩法仍使用原HUD，切换时清除生涯显示组。
- 生涯右上改为暂停，可进入既有暂停页并恢复同一Simulation；不再在驾驶画面重复放大“返回赛事”按钮。没有改变物理、120Hz、车型完整配置、评分/发奖或相机生产代码。
- 真实流程发现旧初驶预览仍是工程方盒车；改用明确game-tuned/BRZ Varis拍摄，六张道路/门位图同时按当前场景重新生成。源图直接复制、不改像素、不移动物理车。运行预览许可、作者链接、相机生成manifest和逐图SHA齐全。

## 自动检查

1. `T0 --tests tests/test_career_ui.py::test_driving_hud_reads_current_event_and_pause_button_keeps_the_world tests/test_career_ui.py::test_driving_hud_event_details_and_two_aspects_do_not_write_or_leave_old_panels`：初次Ruff未用变量失败；v2两个用例失败（未刷新父HUD可见性、用动态GUI几何界限代替明确控件矩形）。修正测试正常初始化/坐标测量后v3 **2项通过**。没有放宽视口界限或暂停保持条件。
2. `T1 --tests tests/test_career_ui.py tests/test_driving_mode_ui.py tests/test_career_process.py tests/test_ui_theme.py --output logs/validation/GARAGE-DESIGN-02-hud-T1`：**25过2失败**，两项失败来自旧菜单名称“高速与驾驶课题/海岸工坊”断言，尚未执行三种子。
3. 按当前已存在的“海岸生涯/7入口”更新旧断言后，只重跑完整驾驶模式模块：`T1 --tests tests/test_driving_mode_ui.py --output logs/validation/GARAGE-DESIGN-02-hud-mode-T1`，**5项及0/17/23各1200步通过**。其余25项结果复用，合计27个不同用例分批覆盖，非一次27项全绿。
4. 最后仅赛事预览和打包路径，`T0 --tests tests/test_ui_theme.py --output logs/validation/GARAGE-DESIGN-02-hud-package-T0`，**5项通过**；包含新Preview-License/preview-manifest及源图片。Scoped Ruff和diff检查通过。

## 实际流程与图片

- `tools/career_hud_check.py --drive` 两轮实际GR86全油门400米，每轮 **1948新驾驶拍 / 16.233333秒 / 3星 / 300积分**，合计3896拍。900拍通过真实HUD按钮暂停、恢复原Simulation和原Snapshot，结果由原规则生成。第二轮完整1948行Snapshot/键输入/结果保存在 `hud-actual/actual-drive.json.gz`。
- 两轮采集工具都在完赛之后的菜单采集中断：第一轮访问已关闭Scene，第二轮对菜单的None career调用asdict。实际完赛/暂停/奖励已完成，但命令不能算整体成功。当前工具按正常可空接口处理并在完赛后立即保存轨迹；没有重跑第三次物理。
- 后续1280×720和1024×768各7张：前四张为HUD排版夹具（冲刺/停车/绕桩/仿真键位），其余为**只读回放第二轮真实完赛数据**生成领奖/车库/简报页面；0新驾驶拍。初次错误把首次渲染前、道路和车库不同生命周期的窗口数作相等断言，修正为同一道路HUD换数据前后不增加窗口，两画幅proof均通过。菜单/车库生命周期原本允许窗口数变化。
- 稀疏离屏实际900拍图没有连续相机推进，车辆偏远，不当作正常追随相机证据。当前工具采图时仅重新对准当前Snapshot，不改变物理世界；本包没有相机行为变更或可见长时性能结论。
- HUD/流程实际图已检查；最后更新预览后，仅补采两画幅初驶简报（0新道路拍），淘汰含旧车照片的早期简报图。六张新源预览已逐张查看，初始化132拍/场共792拍，0道路驾驶拍。
- `hud-proof-1280 / hud-proof-1024` 保存最终HUD图和回放摘要；`hud-actual`保存第二轮实际240拍HUD/暂停/结算、完整轨迹及结果说明；`hud-brief-1280 / hud-brief-1024`为最后预览更新后的简报。未把夹具、回放或初始化算成新完赛。

## 尚未完成

本次统一驾驶信息与菜单视觉关系、清理陈旧预览，未重做道路环境。实际道路植被/材质精细度仍明显低于生成车库设计，车辆与背景融合和人工画面/趣味性体验仍需继续；T2/T3与严格实时Gate未执行。本地提交只含本增量，不代签人工验收。

# TUNING-CARDS-01 配方选择可视化

- 状态：done（自动部分，人工体验待确认）；基线main/1e7bc80f，接续DRIVING-CARDS-01。用户要求审查最近本地更新，补功能/修bug，尤其优化纯文字堆叠页面；追加不要过度检验边界。
- 目标：前胎/制动分配页四个配方采用定量示意卡，标明现装配方、候选和确认安装。制动同时看前后份额，轮胎条长度只表示侧偏刚度，不表示性能或推荐级别。原备份/成绩关联说明清楚保留。
- 修改仅限ui/tire_tuning.py、本页实际截图工具和文档；复用原8按钮的索引、回调、按键和原安装/恢复逻辑。物理、规则、存档、硬件值与默认选择保持。
- 验证：预览/取消/实际安装与同窗返回采用已有相关UI测试；宽屏/4:3原页及候选实际截图。短T0与相关T1，不扩充假设性边界，不重跑长驾驶/物理。人工体验单列，持续目标active，仅本地无推送。
## 实现与验证

- 四配方改为圆角卡，轮胎共用70k上限条，条长只表示刚度；制动共轴显示前后份额，标明原现装配方。当前→候选、安装提示与备份/成绩关联说明保持，确认安装独立橙色主按钮。原8按钮索引/按键/回调及安装/恢复逻辑不改，背景降暗。
- 实际发现候选预览后标题部分字形消失，等待更多绘制帧仍可复现；保留固定标题的字形几何引用后修复。最终前胎/制动的原页与预览标题区域逐像素一致。
- 初次4:3采集因为工具关闭drive-update后未显式调用主菜单缩放而裁切；修正工具采用正式resize，再按已用渲染方式推进6帧及两次renderFrame。该修正不改变游戏布局/物理。初图与等待后仍缺字的图保留，未当作通过。
- 短T0：`tools/validate.py T0 --tests tests/test_tire_tuning_ui.py::test_preview_cancel_and_keyboard_modal_preserve_current_car tests/test_short_braking_ui.py::test_rules_toggle_and_preview_install_preserve_other_hardware_and_course --output logs/validation/TUNING-CARDS-01-T0`，Ruff/2项通过，pytest42.1秒。
- 相关完整模块T1：`tools/validate.py T1 --tests tests/test_tire_tuning_ui.py --output logs/validation/TUNING-CARDS-01-T1`，Ruff/6项、三种子各1200拍通过，pytest88.3秒，含实际安装与同窗返回。制动共享UI原正常安装在本包T0通过，其完整模块在上一包T1已过，明确复用。
- 之后仅补标题字形引用，原动作未改；`TUNING-CARDS-01-title-T0`补验原预览/取消正常流程，Ruff/1项通过，16.8秒。最终`tools/tuning_cards_check.py`在`TUNING-CARDS-01-verified-wide`及`TUNING-CARDS-01-verified-4x3 --size 1024 768`各4张实际图、原车/Snapshot保持、两类标题逐像素一致通过；已查看最终宽屏前胎预览与4:3制动预览，无裁切/缺字。
- 原图、失败显示、中间采集、最终两画幅与原始检查日志见`docs/evidence/TUNING-CARDS-01`。没有新完整道路驾驶、物理或评分改变。T2/T3未跑，原物理T2/实时/人工Gate开放，持续目标active，仅本地无推送。

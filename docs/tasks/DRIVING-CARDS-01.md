# DRIVING-CARDS-01 驾驶选择与课题说明视觉整理

- 状态：done（自动部分，人工体验待确认）；基线main/e1bc03b，接续 ROAD-RETEST-01。目标来自用户本次审查本地更新、补功能、修bug，尤其改善纯堆文字界面的请求。用户追加“不要过度检验边界”，以正常流程和已发现问题为主。
- 目标：高速与驾驶课题入口、短途赛事选择、制动/过门课题说明采用清晰的卡片与示意图。突出路线、速度/距离目标、奖牌和开始动作，减少中间窄框长段文字。
- 允许：局部UI绘图组件、application既有菜单排版接入、受排版影响的旧UI断言、实际截图工具和文档。保持原动作/按键/选择索引、物理、道路、规则、评分、存档、默认调校。
- 方法：复用原按钮及回调；卡片标题/目标/路线示意由本地UI负责，不新建页面管理器或规则副本。示意图明确为示意。两种宽高比适配，返回原页面不残留卡片。
- 验证：修改前后1280×720及1024×768实际图；正常菜单导航/选择/开始/返回，沿用相关UI模块中的真实启动与同窗往返。短T0与相关完整T1/三种子，不重跑历史驾驶、物理长测或大量假设性边界。T2/T3和人工体验分别记账。
## 结果与验证

- 原短途页面三行奖牌标准与首个按钮贴合，规则、目标、七个按钮挤在窄框。现高速入口分成道路/车流、自由驾驶/5公里和三个课题入口；短途六卡分别显示路线示意、目标与奖牌。山谷卡保留250m≥60km/h及400–650m全段35–50km/h，原180秒上限与失败条件保持。
- 普通/高速过门和定点/短距制动四页为左侧场地图解、右侧奖牌标准、下方主要操作。超车/弯坡两页以车身与净距示意表达1m侧距、10m前后距，目标/到终点要求保持。共8页，图为明确示意，不改道路或积分。
- 新 `ui/driving_cards.py` 只排版/绘图；application原按钮、回调和选择索引继续使用，进入其他页清除卡片、恢复标题/按钮对齐和比例。没有新增页面管理器/注册器，物理、原规则和存档不变。
- 短T0：`tools/validate.py T0 --tests tests/test_fast_slalom_ui.py::test_keyboard_toggle_rules_preserves_car_and_old_entry tests/test_tire_tuning_ui.py::test_preview_cancel_and_keyboard_modal_preserve_current_car --output logs/validation/DRIVING-CARDS-01-T0`，Ruff/2项通过，26.7秒。
- 相关T1：`tools/validate.py T1 --tests tests/test_sprint_ui.py tests/test_fast_slalom_ui.py tests/test_short_braking_ui.py tests/test_overtake_ui.py tests/test_hill_traffic_ui.py --output logs/validation/DRIVING-CARDS-01-T1`，Ruff/10项与三种子各1200拍通过，pytest317.7秒。只调整两处旧“所有按钮竖排”的断言，原真实开始/同窗返回/改装/结算用例保持。
- `tools/driving_cards_check.py --output logs/validation/DRIVING-CARDS-01-final-wide` 及 `--output logs/validation/DRIVING-CARDS-01-final-4x3 --size 1024 768`，最终各8张实际静态图和正常返回通过，Snapshot保持。已查看宽屏高速/短途/短距/高速验车及4:3短途/弯坡页。最终山谷卡只补速度区间文字，其他功能未改；没有新完整驾驶或重复旧物理长测。
- 原图、最终两画幅、检查日志和源码SHA见`docs/evidence/DRIVING-CARDS-01`。T2/T3未跑，原物理T2失败、实时/人工Gate开放；仅本地不推送，整体持续目标active。下一TUNING-CARDS-01配方选择页。
- 本地功能提交`1e7bc80f`，36份原始文件及5份源码SHA；收尾文档由下一包补记，功能未改。

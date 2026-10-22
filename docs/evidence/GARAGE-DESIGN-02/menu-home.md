# 首页与设置统一

基线：`f7451658d7a85982fbed24237fb37a418d3d5bb5`。接续用户选择“菜单排版、控件样式和操作流程”，单线本地施工，无推送。总任务仍in_progress，人工审美/驾驶趣味性未验收。

## 参考、设计、实现

- 实际通过浏览器查看[William Emery的FH5 Garage UI原作品](https://williamemery.artstation.com/projects/lD1oL5)，观察完整调校页及换装页。借鉴同轴分组、车辆独立展示、底部操作提示；没有将其截图或品牌资产放入游戏。
- 先生成[12首页](../../design/garage-v2/12-main-menu.png)、[13声音](../../design/garage-v2/13-audio.png)、[14辅助](../../design/garage-v2/14-assists.png)，三份原提示词同目录；再实现原生DirectGUI。位置、字体、橙色主操作、顶底栏和两画幅规则见[布局契约](../../design/garage-v2/layout-contract.md)。
- 首页按视觉顺序聚合生涯/车库/自由驾驶/计时/专家台；默认生涯，设置集中底栏。上下沿左列移动，底栏左右移动，上键回左列；原动作编号0—6保持，驾驶辅助新增为7。旧设计循环采集工具改用明确的专家入口6。
- 首页进车库后Esc/底部按钮返回首页并保留车库焦点，底部文字相应为“返回首页”；赛事进车库仍按原赛事返回。未改其他旧工程页和记录。
- 声音三个通道纵向分组；上下按通道移动、左右调值，保留加减鼠标操作/电台/保存及暂停返回。辅助三行原生ABS/TCS/ESC开关，关闭有文字与滑钮位置。反复刷新销毁背景、焦点几何及滑钮，不留装饰GUI。
- 首页、车库、声音、辅助使用同一个WorkshopVehicle显示缓冲和真实玩家车/颜色，无第二个物理世界。换页停用对应显示，关闭时显式清理设置内容。生成图车色只是示例；实际渲染/光照、车身占比与设计图仍有差距，不以此宣称美术目标完成。
- Tabler官方npm `@tabler/icons-webfont@3.49.0`/MIT，保留原7,318,477字节包及SHA；不执行包代码，fontTools抽取五图标为2,428字节字体，保留原时间戳。源包/清单：`art/ui/menu-icons/`，处理工具`tools/prepare_menu_icons.py`，运行字体/许可/排版来源表及asset-register已登记。自由驾驶使用该套正式beach图标，未手绘替代。

## 验证

均使用项目`.venv/Scripts/python.exe`，验证摘要及日志归档于`menu-verification/`。

| 批次 | 命令（省略统一Python前缀与完整输出前缀） | 结果 |
|---|---|---|
| 首轮T0 | `tools/validate.py T0 --tests tests/test_ui_assets.py tests/test_driving_mode_ui.py tests/test_coastal_medals_ui.py --output logs/validation/GARAGE-DESIGN-02-menu-T0` | 14过1失败；新首页首次展示才分配一个GUI，旧计数基线在首次展示前。测试先刷新首页，再取计数 |
| 首页T1 | `tools/validate.py T1 --tests tests/test_ui_assets.py tests/test_driving_mode_ui.py tests/test_coastal_medals_ui.py tests/test_career_ui.py tests/test_results_keyboard.py tests/test_ui_theme.py --output logs/validation/GARAGE-DESIGN-02-menu-T1` | 40项通过；0/17/23各1200步通过 |
| 设置T0 | `tools/validate.py T0 --tests tests/test_driving_mode_ui.py::test_settings_cards_adjust_save_return_without_retaining_widgets --output logs/validation/GARAGE-DESIGN-02-menu-settings-T0` | 1项通过 |
| 设置T1 | `tools/validate.py T1 --tests tests/test_ui_assets.py tests/test_driving_mode_ui.py tests/test_ui_theme.py --output logs/validation/GARAGE-DESIGN-02-menu-settings-T1` | 最终12项通过；0/17/23各1200步通过，含音量键盘按行导航 |
| 最后返回文案 | `tools/validate.py T0 --tests tests/test_ui_assets.py::test_menu_navigation_and_overlay_lifecycle --output logs/validation/GARAGE-DESIGN-02-menu-back-label-T0` | 1项通过，明确检查按钮“返回首页”及实际往返 |
| 变画幅确认反馈 | 同一针对性用例，输出`...-menu-resize-cue-final-T0` | 1项通过；4:3→当前画幅重建后发送原生鼠标按下事件，确认反馈仍触发且正常往返保持 |

首页40项与末次12项有重叠，不能相加成52个不同用例；全批40项在新增设置页之前，未为设置/纯返回文字重跑全部40项。最终源SHA和七个核心文件与基线逐字节规范化保持证据见`menu-source-sha256.json`。Simulation/120Hz/硬件、成长评分与存档格式未改；旧完整驾驶明确复用，本轮未重跑T2/T3或完整赛事。

## 实际画面与正常流程

- `tools/main_menu_design_check.py --output logs/validation/GARAGE-DESIGN-02-menu-final-1280 --size 1280 720`；`...-menu-final-1024 --size 1024 768`：两画幅各16张、两次车库/升级/涂装/返回，底栏键盘与声音/辅助返回、赛事返回均通过。快照保持，显示窗口各4个且不累积，0新驾驶拍，隔离空进度，不读写玩家文件。
- 最后仅改车库返回文字，使用同工具`--only 03-garage-0 04-upgrades-0 05-paint-0`，输出`...-menu-back-final-1280 / ...-1024`；两次完整正常流程均通过，每幅仅补三张，初始Snapshot tick=0、0新驾驶拍。此处不宣称初始化内部诊断或T1测试也没有物理计算。
- 精选最终图片各10张归档于`menu-home-1280/`、`menu-home-1024/`；实际截图来源/SHA及省略图片说明见`menu-image-sources.json`。包含首页/焦点/车库/升级/颜色/设置/赛事/返回；三张车库页使用最后文案图。其余图在最后纯键盘行跳转前采集，视觉代码无差异；4:3字体子集早期文件只差后来保留的head时间戳，字形相同。
- 已实际查看两画幅首页、焦点、声音/辅助和最后车库升级/涂装图。宽屏与4:3采用各自宽度布局，按钮与车辆框互不覆盖；实际字体宽度及副标题边界检查通过。程序截图不替代用户审美评价。

## 失败与修正

- 早期图`...-menu-settings-1280`显示焦点底板覆盖第一个设置按钮文字/滑钮，已改为先绘制焦点边，再将按钮放入同一层；最终两画幅图已检查。
- 首个采集边界断言误用按钮文字节点参考坐标，其后又将DirectGUI的二维text_scale当标量，均为工具错误；改用实际字体宽度和二维缩放后两幅完整流程通过。初图/失败目录保留，不能当通过证据。
- 首次`--only`省图时错误跳过首帧渲染，窗口计数在旧场景延迟释放前取值，后续断言失败；保留`...-menu-back-label-1280 / ...-1024`，最终省图仍正常渲染每个检查点后再省写文件。`...-menu-back-final-*`均通过。
- GitHub main已无旧webfont路径、初选palm图标名不存在；改用官方npm固定版本中确实存在的beach图标，源包/许可完整。未靠手制资源或宽泛异常掩盖缺件。
- 最后把首页鼠标确认绑定移到每次创建原生按钮时，修复改画幅重建后丢失声音反馈；键盘确认原行为保持。初次测试未给Panda鼠标事件参数，测试失败留档`menu-resize-cue-T0`；补齐参数后针对性T0通过，不改变画面，未重拍或重复整批T1。

下一步仍是道路与车库实际材质/场景融合，以及用户实际菜单/趣味性评价。没有把本轮排版与自动验证记作总包完成。

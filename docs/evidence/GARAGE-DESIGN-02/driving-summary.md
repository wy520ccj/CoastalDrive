# 普通驾驶暂停与结算统一

基线`28ce9e23e2863f9c438426356da38aa94bdede41`，2026-10-23，单线本地施工，无推送。接续用户优先“菜单排版、控件样式和操作流程”，属于持续目标的一个功能块，总包仍in_progress。

## 设计和最终行为

- 在实际采集旧计时/暂停画面后，沿用上一块已实际查看的William Emery FH5菜单参考（本块未声称重新浏览新图），先用内置ImageGen生成[15结算](../../design/garage-v2/15-driving-result.png)与[16暂停](../../design/garage-v2/16-driving-pause.png)，原提示词同目录。然后按[布局契约](../../design/garage-v2/layout-contract.md)实现原生GUI。
- 普通计时、自由驾驶、五公里挑战使用同一海岸车库背景、顶底栏、字体和按钮；生涯页保持。专家驾驶课题仍保留自己的专项结果表，本块没有宣称全部旧工程页已统一。
- 暂停左列为继续/声音/重开/结束，专家台与首页为底栏次操作。键盘顺序按位置，原动作编号保持；声音返回原暂停焦点，Esc继续同一个物理世界，改画幅保留焦点。按钮有实际命中区域和聚焦边，不以整幅生成图代替控件。
- 结果左侧按本次结果→主要读数→同配置最佳/下次目标→原因/保存提示→重试阅读。分段独立在右下，与车辆区和底栏分开；复用`result_columns`的原始分段计算。负值标“更快”，无效差值为“—”，不把缺值当零。
- 保存失败保留原最佳，提示“尚未保存”；无效圈不显示新纪录，提前结束不记圈速。五公里用原快照的距离/用时/碰撞与原因；自由驾驶不凭空生成奖牌、积分或滨海里程。顶部生涯进度只读现有存档，不因普通模式结算发奖。
- 声音/辅助/暂停/结算按实际共用需求抽出`ui/menu_layout.py`的坐标/控件函数，业务内容分别直接绘制；无BasePage、页面注册器或第二套车辆状态。原八个业务按钮复用，刷新/隐藏清理背景、滑钮和显示缓冲。工程道路验证和返回动作仍在应用原逻辑中，本块显示层不重复保存或发奖。
- 复用现有WorkshopVehicle与车型/颜色，没有改变模型、材质、取景算法、权威物理/120Hz、车辆参数或成长规则。生成设计的车辆尺寸/精细光照与实际仍有差距，未以界面统一宣称场景融合或用户审美通过。

## 自动验证

使用`.venv/Scripts/python.exe`，原始日志字节以`.log.gz`归档在`driving-summary-verification/`，源日志仍在各`logs/validation/`目录。相同用例有重叠，不能把不同批次数量相加。

| 批次 | 输出目录后缀（均为logs/validation/GARAGE-DESIGN-02-） | 范围与结果 |
|---|---|---|
| 首T0 | `summary-T0` | `tests/test_results_keyboard.py tests/test_coastal_medals_ui.py tests/test_race_feedback_ui.py tests/test_driving_mode_ui.py`；15过8失败，见下方夹具修正 |
| 夹具修正T0 | `summary-fixtures-T0` | 暂停往返、计时6种结果、两种分段警告，共9项通过 |
| 相关T1 | `summary-T1` | 上述四模块，加`test_ui_assets.py test_career_ui.py test_ui_theme.py`；**46项通过**及0/17/23各1200步通过 |
| 缩放补验初T0 | `summary-final-T0` | 同一暂停往返用例新增画幅/缓冲检查，1失败；未等下一次渲染任务就检查simplepbr缓冲 |
| 最后T0 | `summary-resize-final-T0` | `tests/test_results_keyboard.py::test_pause_groups_follow_screen_and_sound_returns_to_pause`；3次正常渲染任务后检查，**1项通过**，含4:3→原比例、焦点保持、声音返回与原世界/快照保持 |

执行入口分别为`tools/validate.py T0/T1 --tests <上表路径> --output <上述完整目录>`。46项T1覆盖功能与共用布局；末次仅底栏次按钮色/分段负值文字与缩放补验不重跑全46项，用针对性T0和最终两画幅实图补验。没有T2/T3、完整驾驶、性能或人工验收结论。`driving-summary-source-sha256.json`记录最终源码及八个核心文件相对基线规范化字节保持；没有把旧版本的全套验证称为本次重跑。

## 正常流程与实际截图

最终命令：

```text
.venv/Scripts/python.exe tools/driving_summary_check.py --output logs/validation/GARAGE-DESIGN-02-summary-delivery-1280 --size 1280 720
.venv/Scripts/python.exe tools/driving_summary_check.py --output logs/validation/GARAGE-DESIGN-02-summary-delivery-1024 --size 1024 768
```

- 两命令均通过，各17张实际原生页面：暂停/声音/返回焦点、银/金/铜/未获牌/无效/保存失败/提前结束、首页回程、自由驾驶暂停与结束、无限高速自由驾驶、五公里失败/成功、最终首页。目录`driving-summary-1280/`与`driving-summary-1024/`包含所有34张、各自summary及总览；来源/SHA见`driving-summary-images.json`。
- 从实际首页动作进入计时与自由驾驶；暂停进入声音后回原焦点，Esc恢复相同Session.simulation和Snapshot；在暂停点击结束可到结果，结果回原首页/焦点正常。成绩/距离为隔离显示夹具，不是实际完成赛事，不读写玩家目录。
- 进入四个实际工况时各执行60拍装载稳定，最终每幅四次合计240初始化拍；两幅合计480初始化拍，**0新驾驶拍**。每次截图前后Snapshot逐字段相同；初始化拍不混称道路驾驶。各个总结/暂停检查点显示窗口5个、GUI160个稳定；结果重复刷新不累积。
- 旧完整驾驶与规则结果明确复用。本块不以合成银牌/5公里成功图证明可完赛。首轮和中间候选另有装载准备，不充当最终480拍或最终图；测试自身的物理短步由T1独立记账。
- 已查看两画幅完整总览，并放大检查暂停、银牌、无效/未保存、自由驾驶及失败等关键页。布局没有文字/按钮覆盖车身；4:3保持文字高度并调整栏宽。实际车身渲染与生成设计仍有差距，用户审美/趣味性未代签。

## 失败与定位

- 首T0八个失败来自旧显示夹具：计时结果只替换RaceSnapshot但Session.mode仍为自由驾驶；新增暂停测试在无驾驶更新任务时没有先刷新暂停页。补齐一致模式与正常刷新，9项针对性T0通过；未因此修改生产模式判断或物理。
- 首采集在切入自由驾驶暂停后没有刷新面板，截图仍是驾驶HUD；之后“结束”动作未绑定，命令失败。工具补齐每张图前正常refresh_panel，初轮`summary-1280`留存，不当最终证据。
- 第二采集已落盘17张但无最终summary，原进程句柄随后不可查询；检查当时源码发现末尾仍断言Snapshot.tick==0，实际装载后是60拍。最终工具逐截图验证冻结，独立记录四次装载Tick，不再把初始化误认为驾驶推进；`summary-delivery-*`有明确通过摘要和命令日志。
- 缩放补验发现渲染前缓冲isActive为False；独立探针分别打印暂停/声音/返回/4:3/16:9，三次正常渲染后True，确认simplepbr下一任务激活的行为。测试等待该正常任务并检查快照不变，最后T0通过；没有加生产延时/吞错或放宽物理门槛。

下一步仍是实际车辆/场景融合、道路细节及用户实际体验。当前只完成普通驾驶暂停/结算这一功能块，持续目标保持active。

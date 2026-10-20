# GAME-LINK-UI-01 游戏联动对照与导出恢复

- 状态：done（自动部分，人工体验待确认）；基线main/ec6001c2，工作区干净。持续目标为检查最近更新、补功能、修bug及优化纯文字界面；用户要求不要过度检验边界。
- 实际缺口：游戏积分对照完成后若export失败，update仍关闭/丢弃comparison，结果与报告入口丢失，无法只重试导出；旧页依靠长说明解释计算对照和保存车辆试驾。
- 目标：完成对照后立即释放物理世界，保留两份纯数据记录；导出失败可重试，不重算、不改原参考/车辆。关闭重开同一参考仍能查看报告/重试；换参考才清除旧结果。两张操作卡区分积分对照/保存试驾，A/B指标与进度清楚。
- 允许：lab_game_comparison.py导出职责分离、ui/lab_design_loop.py布局/状态、对应正常流程测试/渲染工具与文档。原GameComparison.export调用兼容；不改物理、参数、输入、积分、存档格式、奖励和旧记录。
- 验证：正常计算/导出、导出接口明确注入一次OSError后数据保持与只导出重试、关闭重开、已有保存试驾/同窗往返；1280×720/1024×768实际图。短T0与相关完整T1，不重复旧道路驾驶/物理T2和假设性边界。人工体验独立记账。
- 原PHYS-BRAKE-REFINE-01保持in_progress，原T2仍失败，拒绝候选不接入；本包不重跑该原物理。仅本地，无推送，整体目标active。

## 实现

- 原页实际短参考→游戏对照后，在export_record边界注入OSError；旧代码关闭世界并丢弃完成结果，report_path为空，无法只重试导出。原两张图和summary保留。
- `lab_game_comparison.export_comparison(reference, game, folder)`只处理两份纯数据记录；原`GameComparison.export(folder)`保持兼容并委托该函数。对照完成后先取LabRecord、关闭世界，再尝试导出。失败时保留完成记录，重试只写新目录，不新建/推进物理世界。
- 同一工作台中关闭/重开同一参考保持完成结果、报告或重试入口；切换参考记录才清除旧对照。原保存车辆并试驾、参考A/B/草稿/当前驾驶车辆逻辑保持。此保留为当前工作台面板状态，不新增磁盘存档格式。
- 界面改为计算配置对照/保存试驾两张操作卡、参考/游戏/差值三张指标卡及进度。距离未满足停车条件时明确显示记录行驶距离，不伪称停车距离；仍未设置对照合格线。文件错误直接显示在可点击的重试按钮上方；完整异常仍写日志，不用全局错误条挡住按钮。
- 实图发现成功后底栏仍显示旧导出失败、固定关闭文字偶发消失；成功时同步底栏，保留固定操作字形几何引用。PGItem采集不能用getTightBounds读按钮状态几何，工具改用frameSize换算实际屏幕区域，最终每张图均检出关闭按钮字形。

## 检查与证据

- 初两次T0因新导出函数缩进和导入排序失败（pytest未跑）；修正后`GAME-LINK-UI-01-export-T0` Ruff/新增完整失败恢复流程1项通过，pytest4.7秒。原失败日志保留。
- `tools/validate.py T1 --tests tests/test_lab_game_comparison.py tests/test_design_loop_ui.py --output logs/validation/GAME-LINK-UI-01-T1`：Ruff/15项/seed0、17、23各1200步通过，pytest50.9秒。包含原同车/命令对照与导出复算、保存试驾/恢复/同窗返回，以及新增导出重试；不扩展物理边界或重复完整道路驾驶。
- 其后仅补固定按钮字形引用与成功底栏提示，`GAME-LINK-UI-01-final-T0`补验新增正常恢复流程，Ruff/1项通过，3.8秒；未改模块的T1明确复用。
- 最终`tools/game_link_ui_check.py --output logs/validation/GAME-LINK-UI-01-verified-wide`及`--output logs/validation/GAME-LINK-UI-01-verified-4x3 --size 1024 768`：各4张实际准备/导出失败/重开/恢复图，短参考与实际游戏对照分别3拍；已查看宽屏恢复与4:3失败/恢复。关闭世界、完成记录/原参考/基线/驾驶车保持，重试期间禁止GameComparison构造，导出复载快照/命令精确相同。
- 原图、中间缺字/采集问题、最终两画幅与原始检查日志在`docs/evidence/GAME-LINK-UI-01`；源清单4文件。没有新完整道路驾驶、物理/评分/当前车辆参数改变，T2/T3未跑，原物理/实时/人工Gate开放，整体目标active，仅本地不推送。

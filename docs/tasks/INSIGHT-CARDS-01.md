# INSIGHT-CARDS-01 工坊试验解读卡片

- 状态：done（自动部分，人工体验待确认）；基线main/f0094dda，开始时工作区干净。
- 目标：把A/B解读的收益、预算、硬件改动和观察代价分别呈现，保留真实数值、建议、准备B/导出/返回链路。
- 修改：`src/ui/workshop_insights.py`、原工坊UI测试、独立静态采集工具及本包证据。原计算、物理、奖牌、报告格式和记录保持。
- 验收：短T0覆盖实际A/B显示与准备下一B；原制动/弯道UI完整模块T1。复用原真实解读数据，宽屏/4:3实际图检查通过、未达标与超预算；不追加边界矩阵或重跑旧完整道路。

## 结果与证据

- 收益卡显示实际A/B主指标与改善比例，预算独立三格刻度，超出标红并写明点数；改装项独立展示。观察指标改为A/B/差值表，制动三行、弯道四行切换清空余行，缺字段不冒充零。横摆rad/s显示五位小数，修复原三位舍入把非零差值显示成零的可读性问题。
- 原判定、建议与归因文字完整保留；“准备下一次B”、导出、返回、恢复工作区均调用原链路。固定保存文字/按钮引用，装饰只有普通几何，不新增GUI控件层或第二套状态。
- `tools/validate.py T0 --tests tests/test_workshop_ui.py::test_challenge_uses_real_trials_and_invalidates_unrun_selection tests/test_cornering_workshop_ui.py::test_sharp_recipe_is_rejected_and_changing_topic_cancels_an_active_trial --output logs/validation/INSIGHT-CARDS-01-T0`：Ruff/2项通过，pytest检查13.3秒。
- `tools/validate.py T1 --tests tests/test_workshop_ui.py tests/test_cornering_workshop_ui.py --output logs/validation/INSIGHT-CARDS-01-T1`：Ruff/原完整两模块6项/seed0、17、23各1200步通过，pytest检查35.4秒。实际工坊A/B、选择失效、准备B、报告、同窗恢复/返回与车辆保存由原正常测试覆盖，未追加边界矩阵。
- `tools/insight_cards_check.py --output logs/validation/INSIGHT-CARDS-01-final-wide`及`--size 1024 768 --output logs/validation/INSIGHT-CARDS-01-final-4x3`：每画幅4图，制动金牌/超预算、弯道侧偏失败/金牌；原真实A/B解读JSON静态复用，新增物理0拍，原JSON/当前参考/基线/驾驶车保持，实际图已查看。初宽屏为三位横摆显示，最终两画幅已提高精度；不把静态解读当新物理。
- 首次补丁因同文件删除/新增形式不支持而未应用，改为单一更新后正常实施；无运行失败。证据、源码清单与相关检查归档到`docs/evidence/INSIGHT-CARDS-01`。仅本地，无推送；原ABS精度、实时与人工阶段Gate继续单独保留。

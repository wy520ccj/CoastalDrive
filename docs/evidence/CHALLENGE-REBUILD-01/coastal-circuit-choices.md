# 滨海计时的完整圈比较与驾驶提示

2026-11-06，基线 `15c321f5`。旧版本的七个完整圈留在 `logs/challenge-rebuild-20261102/coastal-circuit-baseline` 和 `coastal-circuit-tuned`。本轮在当前正常预算会话、固定种子0和本机修正SDK，以目标105 km/h、预瞄曲率3.3 m/s²及90%转向余量策略比较六套配置。所有配置均采用同一免费调校（前制动份额65%、前防倾份额40%）。

| 方案 | 费用 | 用时 / s | 油耗 / L/100km |
| --- | ---: | ---: | ---: |
| 原车硬件加免费调校 | 0 | 55.290 | 21.164 |
| 前胎130% | 2000 | 54.324 | 21.142 |
| 动力115% | 3940 | 54.648 | 22.658 |
| 轻量低阻 | 4780 | 55.174 | 20.996 |
| 前胎130%加风阻面积93% | 4780 | 54.320 | 21.098 |
| 均衡 | 5000 | 54.572 | 22.200 |

单前胎比免费调校快0.967秒。与同价轻量低阻相比，前胎加低阻快0.854秒，多耗0.101 L/100km；和单前胎相比几乎同速，多花2780仅省0.044 L/100km。动力和均衡比单前胎更贵、更慢且更耗油。结果只支撑此驾驶策略下的取舍，省油幅度不足以冻结报价。

六次完整圈均无碰撞。按原始120Hz位置重跑同一个圈速裁判，四个检查点及终点、门线时刻和分段均一致。按已接受的原始机械子步复算耗油，终点同一步内插的油量与圈速一致。来源指纹与当前SDK匹配，六次均自动试车、未记分。原六份真人记录哈希未变。首次复算脚本把短途固定种子17误用于滨海，随后从原始记录确认滨海种子0，修正核对脚本后通过，未重跑完整圈。

预算版驾驶此前在原裁判已判无效后仍显示正常分段差值。现直接读取现有无效原因，显示“本圈无效”并停用分段差值。有效通过最后一个检查点后提醒驶过终点线，HUD按五个计量段计数，结算区分检查点和终点。沿用原HUD和结算布局。相关9项T0及全仓Ruff通过。实际应用经正常菜单发车，自动驱动通过第四个检查点，再用正常车辆复位入口触发无效。两张960×720 HUD实图已核对，首组因离屏采集器跨帧导致相机未跟车，调整采集器后复拍。完整圈数据与这组局部渲染分别保存。本轮无真人驾驶、实时性能或最终T2结论，未提交推送。

```powershell
$sdk=(Resolve-Path 'build/road-edge-sdk/panda/built-road-edge').Path
$env:PYTHONPATH="$sdk;$env:PYTHONPATH"
.venv/Scripts/python.exe tools/challenge_balance_check.py --output logs/challenge-takeover-20261106/coastal-circuit-current --routes time_trial --builds free-setup tuned-power-only tuned-efficiency tuned-front-tire130 --seconds 100 --target-kph 105 --curve-acceleration 3.3 --steering-reserve 0.9
.venv/Scripts/python.exe tools/challenge_balance_check.py --output logs/challenge-takeover-20261106/coastal-circuit-balanced --routes time_trial --builds tuned-balanced --seconds 100 --target-kph 105 --curve-acceleration 3.3 --steering-reserve 0.9
.venv/Scripts/python.exe -c "import sys; from pathlib import Path; sys.path.insert(0, 'tools'); from challenge_balance_check import BUILDS, BuildDraft, run; BUILDS['tuned-front-and-drag'] = BuildDraft(front_tire=1.3, drag=.93, brake_share=.65, antiroll_share=.4); run(Path('logs/challenge-takeover-20261106/coastal-circuit-front-drag').resolve(), ['time_trial'], ['tuned-front-and-drag'], 100, 105, 3.3, steering_reserve=.9)"
.venv/Scripts/python.exe logs/challenge-takeover-20261106/verify_coastal_circuit.py coastal-circuit-current coastal-circuit-balanced coastal-circuit-front-drag
.venv/Scripts/python.exe tools/validate.py T0 --tests tests/test_challenge_circuit.py tests/test_challenge_run.py::test_circuit_uses_geometric_crossing_time_for_both_time_and_fuel tests/test_challenge_ui.py::test_coastal_menu_budget_start_pause_retry_and_return_keep_original_vehicle tests/test_challenge_ui.py::test_budget_hud_uses_real_allowance_handles_missing_sensor_and_restores_coastal_layout tests/test_race_feedback_ui.py::test_hud_shows_sector_and_total_deltas_within_card_and_hides_for_cruise tests/test_coastal_medals_ui.py::test_compact_coastal_hud_keeps_state_warnings_controls_and_viewport --output logs/challenge-takeover-20261106/T0-coastal-lap-feedback --timeout 180
.venv/Scripts/python.exe logs/challenge-takeover-20261106/coastal-circuit-feedback-ui/capture.py
```

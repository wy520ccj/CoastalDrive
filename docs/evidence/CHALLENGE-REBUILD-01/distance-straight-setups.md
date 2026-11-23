# 五公里直线普通车流的两套参考改装

2026-11-07，基线 `15c321f5`。从无限高速选择直线、普通车流进入五公里，赛前沿用既有参考方案区，可套用低风阻或轻量低阻，再编辑、试车或正式发车。恢复原车仍可用。其它路况沿用各自门槛和共用草稿，参考改装按实际选择的道路和车流显示。

两套付费方案按现行车道边界规则实跑。固定种子 0、12 辆正常车流、同一目标车速 144 km/h，四段有效、零碰撞。实际 120 Hz 首次终点过线、燃油机械子步和来源哈希已复算。

| 方案 | 费用 | 用时 / s | L/100km |
| --- | ---: | ---: | ---: |
| 低风阻，风阻面积 −5% | 1780 | 188.998 | 9.961 |
| 轻量低阻，风阻面积 −5%、质量 −4% | 4780 | 172.645 | 10.459 |

两套均满足现有金牌线 194.8 秒及 10.8 L/100km。轻量低阻复现旧同策略完赛的时间与油耗。低风阻是首份完整样本。车流遇车时机可随车辆配置变化，16.35 秒是这两次完整驾驶的差值。原车仍可零费用发车，既有样本 189.079 秒、10.115 L/100km 来自旧车道规则，未补跑本组原车。

实际 960×720 方案页显示两套价格，选中低风阻后滑杆、费用和剩余预算联动。实跑、复算及截图在 `logs/challenge-distance-setups-20261107/`。奖牌门槛沿用既有值，试车未写正式成绩。本轮本地源码实施，未重打独立预览包。其余路况改装收益、重复性和整包 T2 开放。

相关 T1 通过三项入口与方案检查、全仓 Ruff 和三种子短启动。覆盖直线普通低风阻进入实际会话、切换弯坡繁忙后不展示直线方案、山脊版本隔离与原参考方案入口。

```powershell
$sdk=(Resolve-Path 'build/road-edge-sdk/panda/built-road-edge').Path
$env:PYTHONPATH="$sdk;$env:PYTHONPATH"
.venv/Scripts/python.exe tools/challenge_balance_check.py --output logs/challenge-distance-setups-20261107/straight-normal --routes distance_challenge --builds drag-only efficiency --seconds 230 --target-kph 144 --distance-shape straight --distance-density normal
.venv/Scripts/python.exe logs/challenge-distance-setups-20261107/review.py
.venv/Scripts/python.exe tools/validate.py T1 --tests tests/test_highway_entry.py::test_budget_distance_uses_highway_menu_conditions_on_start_and_retry tests/test_challenge_ui.py::test_road_reference_builds_replace_draft_and_feed_normal_start tests/test_challenge_ui.py::test_reference_builds_only_match_their_supported_road_geometry --output logs/challenge-distance-setups-20261107/T1 --timeout 150
```

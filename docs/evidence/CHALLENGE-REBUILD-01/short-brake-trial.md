# 短距制动的同速改装对照

2026-11-06，基线 HEAD 15c321f5。短距制动验车沿用[参考方案与自动试车母版](../../design/challenge-controls-v2/design.md)，加入两套可继续调整的方案。免费方案只把前制动份额调到 65%，升级方案保持同一份额并把制动扭矩提高 25%，费用 1840。原预算 2500、100 米测速门、80–85 km/h 入门、停稳一秒与奖牌线保持。

自动试车通过正常 Control 接口，以相同速度目标跑过 100 米门，过门后开始制动。前两次原车自动试跑在停稳附近失败，第二次松踏板后依然因踏板释放与轮胎卸力滞后越过倒车判线。逐拍位置显示失败仍在前进挡。最终试车策略在低速逐步松刹车，保留原车、车辆输入辅助及道路裁判。

| 实跑方案 | 费用 | 实测入门车速 | 过门后停车距离 |
| --- | ---: | ---: | ---: |
| 前制动份额 65% | 0 | 83.038 km/h | 32.352 m |
| 同份额加制动扭矩 25% | 1840 | 83.038 km/h | 28.217 m |

两次都通过原直行、入门和停稳判定，升级少用 4.135 米。按原阈值两套均满足金牌距离，实际自动试车不记分。完赛对照保存实际停车距离、完整方案和已通过的里程点。后次发车读取上次记录，结算显示差值并可套用旧方案。自动试车与玩家 A/B、正式成绩和草稿独立。

T1 通过 23 项相关检查、Ruff 和种子 0/17/23 离屏启动。T1 中的专项目标、对照存档和菜单检查沿用通过结果。低速控制最终版用上述两次正常入口实跑和 Ruff 验证。4:3 方案页与对照页已核对，最终文案和里程点用两份原始记录复用渲染。由原始 120 Hz 最大进度减去 100 米复算停车距离。证据在 `logs/challenge-short-brake-trial-20261106/` 的 `verified.json`、对应轨迹、`setup.png` 和 `comparison-final.png`。

```powershell
$sdk=(Resolve-Path 'build/road-edge-sdk/panda/built-road-edge').Path
$env:PYTHONPATH="$sdk;$env:PYTHONPATH"
.venv/Scripts/python.exe tools/validate.py T1 --tests tests/test_trial_references.py tests/test_short_braking.py tests/test_short_braking_ui.py tests/test_challenge_ui.py::test_automatic_comparison_uses_last_complete_trial_and_keeps_its_build --output logs/challenge-short-brake-trial-20261106/T1 --timeout 150
.venv/Scripts/python.exe logs/challenge-short-brake-trial-20261106/run.py
.venv/Scripts/python.exe logs/challenge-short-brake-trial-20261106/render.py
```

本轮只验收短距制动的可比较收益，其他路线平衡、价格及整包 T2 仍开放。改动留在本地。

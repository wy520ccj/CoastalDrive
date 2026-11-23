# 预算专项的个人最佳

2026-11-06，基线 HEAD 15c321f5。短距制动、定点刹停、生涯停车及两场计时过门在有效完赛和各奖牌档下新增专项最佳。分别以真实停车距离、绝对停车误差或计时段用时排名，保留该次完整方案、燃油与分段。全程用时、最低油耗、最低费用等已有纪录继续保存。并列保留已经保存的专项最佳。

发车时固定个人专项最佳，结算在已有三列表内显示本次与最佳的实测指标、差值及改装费。可直接套用最佳的方案。自动制动试车仍使用上次自动试车对照。旧存档仅从实际保留的完整成绩中找专项最佳，读取不改写文件，也无法补回旧版没有保存的驾驶。该次改动仅改变成绩索引与读取、参考选择和结算，兼容表续接已核对的分组，逐拍原始指纹继续记录实际版本。

T1 通过 32 项、全仓 Ruff 与种子 0/17/23 离屏启动。覆盖较慢且较贵的驾驶仍能凭更短停车距离更新专项最佳，原最快记录保持；无效驾驶不改写最佳；旧格式只读恢复；原道路和专项评级继续通过。

离屏游戏以既有两次制动试跑为结算夹具，从正常菜单加载不含专项最佳字段的隔离存档，显示本次 32.35 米与个人最佳 28.22 米，差 4.14 米。点“套用对照方案”恢复原完整改装，旧成绩文件逐字节一致。实际 960×720 结算已查看。夹具不计入正式实跑或玩家记录，本轮未重跑赛道。

```powershell
$sdk=(Resolve-Path 'build/road-edge-sdk/panda/built-road-edge').Path
$env:PYTHONPATH="$sdk;$env:PYTHONPATH"
.venv/Scripts/python.exe tools/validate.py T1 --tests tests/test_challenge_scores.py tests/test_challenge_specialist.py tests/test_challenge_run.py tests/test_short_braking_ui.py::test_budget_result_uses_actual_stopping_metric_and_save_notice --output logs/challenge-specialist-records-20261106/T1 --timeout 160
.venv/Scripts/python.exe logs/challenge-specialist-records-20261106/render.py
```

证据与截图在 `logs/challenge-specialist-records-20261106/`。本地改动未推送，整包 T2 与实际驾驶性能仍开放。

# 山谷制动结果与重试提示

2026-11-07，基线 `15c321f5`。预算版山谷结算沿用原分段表。前三行依次显示 375 米测速门速度、25 米减速区的平均制动踏板请求、400 米入带速度，右侧仍为对应整段用时及油耗。入口失败时在原反馈位按实际车速、判罚位置与踏板请求给出重试提示。保留原判罚原因，平均值只统计实际减速区内的完成步时间，跨边界步按位置比例取交集。

用原三份 120 Hz 控制输入和进度重新计算同口径平均踏板请求。免费调校 85.67%，制动升级 71.89%，轻量低阻 82.17%。通过正常赛前入口只补一趟制动升级，四门有效、零碰撞。过测速门 83.0 km/h、入带 45.7 km/h、平均踏板 71.89%，完赛 59.828 秒及 20.199 L/100km。新记录复算与裁判实际读数一致，制动升级两次完整实跑达到现行金牌线。自动试车独立存档，新增观测显示本趟数据。

960×720 结算图已查看。23 项 T1、Ruff、种子 0/17/23 短启动通过，覆盖跨边界加权及入带失败提示。首轮 Ruff 在测试导入格式处停止，修正后才执行相关测试。实际数据、复算、截图和日志在 `logs/challenge-valley-braking-feedback-20261107/`。原成绩分组沿用已核对映射，新增原始逐拍记录保留本版真实源码指纹。当前改动在源码，独立包尚未更新，轻量低阻的现行规则重复达标、整包 T2 继续开放。

```powershell
$sdk=(Resolve-Path 'build/road-edge-sdk/panda/built-road-edge').Path
$env:PYTHONPATH="$sdk;$env:PYTHONPATH"
.venv/Scripts/python.exe logs/challenge-valley-braking-feedback-20261107/drive.py
.venv/Scripts/python.exe tools/validate.py T1 --tests tests/test_valley_pace.py tests/test_challenge_ui.py::test_valley_result_compares_each_segment_and_keeps_partial_runs_unranked tests/test_challenge_balance_policy.py --output logs/challenge-valley-braking-feedback-20261107/T1-final --timeout 130
```

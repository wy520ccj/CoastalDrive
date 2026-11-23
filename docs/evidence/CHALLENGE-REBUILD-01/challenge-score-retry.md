# 正式挑战结算重试保存成绩

2026-11-07，基线 `15c321f5`。正式挑战的成绩文件写入失败后，结算沿用现有保存按钮区域，提供「重试保存成绩」。同一趟完赛的方案、奖牌、用时、油耗和分段由权威会话保留，重试读取磁盘最新纪录再比较。反复点击不会重复计分或推进物理。若生涯或巡回进度同时待保存，同一个按钮依次处理各自的待写状态。

滨海计时因成绩写入失败而暂未关联幽灵时，保留已完整采样的本圈轨迹。重试后成为最快纪录且运行版本一致时，继续关联本圈幽灵。等待重试的结果保存在当前结算会话中。原成绩分组沿用，逐拍记录的实际源码指纹仍更新。

验证使用隔离存档的合成完成状态。故障注入核对了正常结算回调、重复失败、同次成绩成功落盘、较新纪录不被覆盖、生涯与巡回原保存入口、滨海幽灵关联和独立会话命令回包。本轮没有重跑关卡标定。

T1 通过 24 项、Ruff 和三种子短启动。改动已进入源码，上一版独立试玩包未包含本功能，整包 T2 开放。

```powershell
$sdk=(Resolve-Path 'build/road-edge-sdk/panda/built-road-edge').Path
$env:PYTHONPATH="$sdk;$env:PYTHONPATH"
.venv/Scripts/python.exe tools/validate.py T1 --tests tests/test_challenge_run.py tests/test_challenge_scores.py tests/test_challenge_ui.py::test_budget_result_retries_same_completed_score_without_driving_again tests/test_challenge_ui.py::test_budget_career_save_failure_has_real_retry_without_minting_credits tests/test_driving_tour_ui.py::test_save_failure_has_retry_and_retains_old_saved_round tests/test_ghost_session.py::test_retry_budget_score_can_attach_ghost_from_the_completed_run tests/test_session_process.py::test_switching_back_to_shared_keyboard_keeps_the_authoritative_controller_and_clears_input --output logs/challenge-score-retry-20261107/T1 --timeout 155
```

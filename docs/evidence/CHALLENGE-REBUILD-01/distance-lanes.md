# 五公里挑战的车道边界

2026-11-06，基线 HEAD 15c321f5。预算五公里原先只检查碰撞、复位及终点。玩家可以让车身进入护栏内的路肩，绕过车道内的交通。现按实际道路坐标检查完整车身横向包络，左右边界为车道铺装半宽 6.75 米。弯坡用车身相对道路的偏角，碰撞与复位仍优先，越界即使与终点落在同一拍也不会取得完赛。道路、车辆、交通、奖牌数值和倒车调姿规则保持。赛前在原有高速菜单与目标区显示车道内完赛要求。

正式六组使用 `budget-distance-medals-v2`，其它种子的试跑使用 `budget-distance-lanes-v1`。玩家的旧改装草稿在新版本可读，旧成绩和试车文件保留原分组。当前源码指纹按项目既有方式包含共用会话及规则，其他采用该指纹的记录也会进入当前版本分组。

## 验证

- 相关 T1 合计 21 项。首轮 19 项通过，两项边线布置夹具因为直接重置车辆而清空了燃油采样。让发车流程在布置后初始化采样，只补验这两项，均通过。全仓 Ruff、种子 0/17/23 离屏启动通过。覆盖直线与弯坡真实完成步的越界结算、偏转车身、越界与终点同拍、倒车、复位和碰撞优先级、旧草稿与重试。
- 用本机道路 SDK 只完整实跑一组弯坡稀疏原车。通过新边界判定，四段完成，原始燃油子步、首次过终点及油耗复算为 **176.028 秒 / 10.766 L/100 km**，达到本组现有金牌数值，自动驾驶不记分。与旧版同组样本相符。
- 另核对七份旧标定实跑的 20 Hz 车身中心观测，最大横向偏差为 4.807–5.092 米。这些旧文件未保存完整 120 Hz 车身朝向，因此未据此宣称其余五组已通过新车身边界。保留原奖牌门槛。

```powershell
$sdk=(Resolve-Path 'build/road-edge-sdk/panda/built-road-edge').Path
$env:PYTHONPATH="$sdk;$env:PYTHONPATH"
.venv/Scripts/python.exe tools/validate.py T1 --tests tests/test_highway_run.py tests/test_challenge_plans.py tests/test_highway_entry.py::test_budget_distance_uses_highway_menu_conditions_on_start_and_retry --output logs/challenge-distance-lanes-20261106/T1 --timeout 180
.venv/Scripts/python.exe tools/validate.py T1 --tests tests/test_highway_run.py::test_budget_distance_boundary_uses_current_road_frame --output logs/challenge-distance-lanes-20261106/T1-boundary --timeout 100
.venv/Scripts/python.exe tools/challenge_balance_check.py --output logs/challenge-distance-lanes-20261106/hills-light --routes distance_challenge --builds stock --seconds 215 --target-kph 128 --distance-shape hills --distance-density light
.venv/Scripts/python.exe logs/challenge-distance-lanes-20261106/review.py
```

结果见 `logs/challenge-distance-lanes-20261106/verified.json`。本地改动未推送，整包 T2 及正式驾驶体验未验收。

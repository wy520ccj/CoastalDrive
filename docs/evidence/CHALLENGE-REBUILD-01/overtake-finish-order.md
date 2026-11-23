# 超车与冲线按实际先后裁定

2026-11-07，基线 `15c321f5`。预算直线安全超车和弯坡车流原来在同一完成步先处理超车，再判断是否冲线。最后一辆可能在冲线之后才达到整车领先 10 米，却被计入达标数量。若终点和赛事时限落在同一完成步，终点先到也可能被报超时。

预算裁判在完成步内插值终点和时限的位置，在较早的截止点检查整车净距。截止前已达标的超车按实际时刻记录，车辆事故仍按原扫掠安全裁判先处理。燃油和完赛时间继续使用原有终点插值。新版 `budget-overtake-finish-v1` 读取旧改装草稿，旧版比赛记录保留独立分组。

复用直线、弯坡各两份完整实跑核对金牌样本。最接近终点的最后一次超车也提前 4.51 秒，四份样本均在时限内，沿用既有金牌线。旧改装草稿从两项新版赛事条件读回。新增候选只留在本机实验日志，未接入游戏菜单。

初版 T1 通过 40 项、Ruff 与三种子短启动。完成步内的超车时间记录补齐后，最终 T0 通过 21 项，覆盖先超车、先冲线、先超时及事故边界。现有独立试玩包未包含此修复，整包 T2 开放。

```powershell
$sdk=(Resolve-Path 'build/road-edge-sdk/panda/built-road-edge').Path
$env:PYTHONPATH="$sdk;$env:PYTHONPATH"
.venv/Scripts/python.exe tools/validate.py T0 --tests tests/test_overtake_run.py --output logs/challenge-overtake-finish-20261107/T0-final --timeout 80
.venv/Scripts/python.exe logs/challenge-overtake-finish-20261107/review.py
```

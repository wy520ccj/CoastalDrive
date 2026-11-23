# 真人试玩发现的交通车转向崩溃

2026-11-02用户继续后，独立试玩目录已出现6份真实keyboard记录和12:13:25的`crash.log`。原“没有真人记录”的等待状态已发生变化，任务恢复in_progress。基线HEAD仍为15c321f5，全部既有未提交成果保持，本块未提交推送。

## 崩溃与最小修复

玩家实际堆栈为独立物理时钟→Simulation→TrafficVehicle.prepare_command→wheel_angles，计算转弯半径时除零。原日志没有保存当时具体转向角，不能把后续构造的标量冒称玩家冻结输入。

使用原SteeringRack从1度持续回正，8973拍（74.775仿真秒）复现同一异常：角度`1.33e-322`度仍非零，转弧度/切线已下溢为零。原函数只判断度数是否等于零，随后用零切线作除数。

`src/vehicle_steering.py`现在判断实际算出的切线是否为零；零时返回平行前轮，非零仍执行原半径与左右前轮公式。没有加近零容差、强行归零齿条、修改回正速度、操控参数或任何碰撞/车辆硬件。五个原生扩展未重编。

原源码、玩家日志副本、独立齿条复现及对照数据在`logs/challenge-rebuild-20261102/steering-underflow/`。修复后原齿条走完12000拍，前轮有限、最终平行；13661个正常/非下溢微小角度的两轮double字节与保存的原模块完全相同。此为函数/齿条对照，不是新增长程或真人驾驶验收。

## 相关检查

新增正负回正与真实TrafficVehicle命令进入Bullet转向口两类回归，直接覆盖实际异常路径。T0四项通过；最终T1仅`test_steering_geometry.py`及`test_npc_physics.py`完整两个相关模块，27项/Ruff/三种子启动通过。没有扩大模块或重启T2。

```powershell
.venv/Scripts/python.exe tools/validate.py T1 --tests tests/test_steering_geometry.py tests/test_npc_physics.py --output logs/challenge-rebuild-20261102/T1-steering-underflow
```

## 已收到的真人记录

6份原始文件全部只读保留，逐拍耗油复算通过，来源均匹配修复前版本。5次有效、1次过门碰撞失败：海岸初驶1次有效；停车3次有效（银/铜/银）；过门1次铜牌、1次失败。初驶的终点时间和油量另由真实120Hz记录复算通过。详细路径、哈希、参数及结果见`steering-underflow/player-record-review.json`。

目前平路连弯记录为0，初驶也只有一套方案一次；不能用这些初章记录填平路连弯金牌线。停车和过门已有专项指标，不混入道路时间/油耗标定。真实驾驶记录的存在也不等于用户已确认画面、流畅度或手感通过。

修复后的源码指纹另存`manual-ready-after-steering-fix.json`；旧版本说明、原玩家进度/奖牌和逐拍记录均不改写。仍使用同一个试玩启动器。整体价格/需求平衡、真人奖牌标定和最终体验/回归继续开放。

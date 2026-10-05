# 共同末状态轮端滚动阻力

2026-10-05；接续气动提交`8a3a78f`。施工线②继续，参考车标准标定与本块T1尚未完成。

每轮路面外部阻力矩为`τrr=Crr*Fn*r²*ω/max(|r*ω|,v_transition)`，SI单位N·m。Fn、有效滚动半径和ω均取共同末状态受力输入；路面资格及铺装/草地参数按真实轮接触。无支撑时为零，低速在1m/s轮缘速度内连续趋零。`wheel_rolling_resistance=false`保留旧车身中央阻力用于同配置A/B。

滚阻独立作用于轮转子，完整惯量矩阵自然把轮胎/传动耦合传到车身；不并入制动容量，不额外给车身中央阻力或制动反力。机械账包含路面的外部角冲量，耗散为`dt*τrr*ω`，与制动、轮胎和轴系耗散分别输出。Snapshot增加矩、120Hz累计角冲量、累计耗散及受力时刻有效半径；末姿态几何半径仍独立观测。

滚阻加入原共同状态方程。大轮荷低速分支固定点初迭代后采用带步长搜索的Newton修正，30次上限保持。停止条件逐坐标为`max(1e-14,ulp(q),ulp(mapped(q)))`：122rad/s处一个双精度间隔为1.42109e-14，原绝对门槛低于可表示间隔。能量、线/角动量独立断言阈值保持。

验证命令与结果：

```powershell
.venv/Scripts/python.exe tools/validate.py T0 --tests tests/test_rolling_resistance.py tests/test_guardrail_suspension.py tests/test_vehicle_tires.py::test_native_tangent_forces_disabled_with_suspension_and_collision --output logs/validation/PHYS-LOAD-01-rolling-T0-r4
.venv/Scripts/python.exe tools/validate.py T0 --tests tests/test_rolling_resistance.py tests/test_joint_suspension.py tests/test_tire_drivetrain.py tests/test_tire_shaft.py tests/test_traction_lifecycle.py tests/test_physics_config_io.py tests/test_world_substeps.py --output logs/validation/PHYS-LOAD-01-rolling-mechanics-T0
.venv/Scripts/python.exe tools/physics/export_reference.py --output docs/evidence/PHYS-LOAD-01/reference-v28.json
```

- r4：12通过，pytest20.95s，全Ruff通过；两模式/两碰撞支撑布置的实际护栏高载荷各30拍完成。
- mechanics：391通过，pytest20.29s，全Ruff通过。FWD/RWD/AWD、正向高速/反向低速、异轮荷/混合路面、离地、下游轴储能、SI悬架共同轮荷、制动及整车角动量/能量均覆盖。实际车身无重复中央力。
- reference-v28：完整96车辆字段、9输入字段及两模式真实240拍读回，包含轮端观测与源文件哈希。成绩game-controls-v25/reference-v28。

失败如实保留：r1为末观测半径与受力时刻半径混用，已分别输出；r2为护栏大轮荷固定点30次未收敛；r3为一浮点间隔残差无法小于绝对门槛，已采用逐坐标浮点分辨率。原测试物理因果和能量阈值保持。

未跑本块T1、机械T2、T3、实际窗口性能或人工驾驶。旧撞击音频断言待其功能收口。本增量仅本地提交，无远端推送。

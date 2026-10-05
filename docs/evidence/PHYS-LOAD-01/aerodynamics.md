# 三维相对空气载荷

2026-10-05，基线`a602910`。施工线②的首个实现增量；滚阻与参考车标定继续。

实际气动载荷改为`v_air=v_body-wind`、`F=-ρCdA/2*|v_air|*v_air`，包含竖向速度。完整三维向量直接作用于唯一Bullet车身；零相对空气速度自然为零，无原0.01m/s截断。通用CdA仍为标量设计模型。

不可变物理Snapshot新增相对空气速度、气动力向量和车身功率`F·v_body`，已有气动力标量保持为模长。顺风可以向车身做正功；耗散方向按相对空气速度判断。没有另加重力或坡度力，没有改轮胎/悬架硬件。

短T0：`logs/validation/PHYS-LOAD-01-aero-T0-r1/`，21项通过（pytest95.59s）及全Ruff通过，覆盖道路载荷、配置导出、版本/生命周期。命令：

```powershell
.venv/Scripts/python.exe tools/validate.py T0 --tests tests/test_road_loads.py tests/test_physics_config_io.py tests/test_traction_lifecycle.py --output logs/validation/PHYS-LOAD-01-aero-T0-r1
```

六条独立整数速度/风速案例覆盖相对静止、逆风/顺风/侧风和竖向运动；实际Bullet车身测试中，半ρCdA=1、速度(3,4,12)m/s产生力(-39,-52,-156)N，模长169N、车身功率−2197W；快照与真实车身受力一致。

成绩版本game-controls-v24/reference-v27；94车辆字段及新增载荷观测真实导出，见`reference-v27.json`。本增量未跑T1/T2/T3或人工驾驶，功能块②仍in_progress。

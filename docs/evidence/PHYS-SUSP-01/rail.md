# PHYS-SUSP-01：护栏大轮荷求解精度增量

2026-10-05，基线 `9f2c142`，本次只收口大反力下的共同求解精度。PHYS-SUSP-01仍施工中，护栏接触真实性没有验收；本地开发，不推送或打包。

## 改动与依据

原侧撞摆位 `(5.8,30,.55)`、初速度 `(8,12,0)m/s`、轮速按12m/s滚动初始化保持。冻结基线在两模式、两种车身Box布局的第15拍均因共同求解20轮用尽而失败。局部复现显示反力/几何残差仍在持续衰减；并非达到浮点极限。其来源是圆角大轮荷下的滞后几何迭代。

`tire_drivetrain.py`在切向已收敛而法向/几何未收敛时，直接对六维车身末速度作牛顿修正。每个候选仍通过原曲面、悬架硬件、转子/离合共同方程得到反力和末速度；线搜索只接受同一方程残差降低的步，外层20轮及所有最终门槛保持。求解器没有另一套兜底物理。

随后原生下一子步暴露小型线性消元的舍入误差。用40位Decimal解同一矩阵的只读实验能完成原轨迹，定位到线性算术；生产改为复用LU分解并作一次补偿求和的残差修正，不使用Decimal或新增依赖。SI参数、曲面/道路资格、实际碰撞、轮胎曲线、动力参数和120Hz时序保持。成绩版本为game-controls-v21/reference-v24，参考表仍完整91车辆字段。

## 原生证据与限制

|模式|基线完成外拍|当前完成外拍|当前峰值轮荷N|局部悬架能量残差峰值J|30拍末roll|
|---|---:|---:|---:|---:|---:|
|游戏|14/30|30/30|348173.83|1.4552e-11|−45.01°|
|仿真|14/30|30/30|350973.43|7.2760e-12|−45.02°|

两种Box布局均完成，原始逐拍Snapshot和来源哈希见 `rail-baseline-r1/`、`rail-native-r1/`。基线失败按非零退出保存，不能算通过；两次查询均在指定源码目录中加载并核对模块路径，运行前后源哈希一致。

当前约35万N反力和车身抬起没有裁掉。这是现有球形包络在横向伸出轮心0.33m，先于车身接触栏顶圆角后的机械响应；不能把求解器能完成轨迹称作护栏物理正确。两条旧车身撞击测试仍失败：原门槛要求第17拍1次撞击，当前30拍无车身撞击。原始摆位、冲量和事件断言未改，失败见 `validation-T0-rail-legacy-gates-r1/`。

基线旧刮擦的非有限分支最长连续接触11拍＜600；有限分支第718拍在近掠资格切换中不收敛，法向残差约35069N。本增量没有重跑这两条12秒刮擦，也没有宣称它们通过。首次四条原测试失败、实际故障状态见 `validation-T0-rail-r1/` 和 `rail-failure-state-baseline.json`。

关闭新耦合后两模式/两种Box布局共240外拍，完整Snapshot JSONL与冻结基线逐字节相同，包含真实第17拍车身撞击。见 `rail-compatibility.json`。这只证明关闭分支兼容，不替代当前SI机制验收。

## 验证记录

- T0-r2：首次六维修正的358项机械/几何/世界子步通过；早期局部调试曾因候选list/tuple拼接报TypeError，已直接修正。
- T0-r3：LU修正后122项通过，4项新原生测试失败。测试错误地要求陡护栏侧面的悬架轮荷也成为轮胎道路载荷；既有 `road_support` 要求法线z≥0.5，测试按真实资格修正，生产未改。
- T0-r4：上述四项及传动/子步合计310项通过，全Ruff通过。
- 功能增量T1-r1：选取受影响的完整悬架/传动/原生模块及配置/成绩版本节点，443项pytest通过；三种子各1200步启动全部通过；最终结果见 `validation-T1-rail-r1/summary.json` 与 `rail-receipt.json`。
- reference-v24实际两模式各240外拍导出91车辆/9输入字段，源码哈希与本增量来源核对；此处没有新增参数。
- 未运行T2/T3、前台性能、人工驾驶或音频验收。不将本次T1称作整个悬架包/物理阶段完成。

## 下一入口

继续PHYS-SUSP-01：先处理球形包络横向占用与实际胎宽不符的护栏接触几何，保留同一故障摆位和真实力/矩；再处理近掠支撑切换和刮擦。不得改碰撞掩码、裁轮荷、放宽旧事故/接触门槛或用瞬移收口。有限胎宽是本次测量指向的下一机制，完整簧下刚体、网格/Plane精度和整体Gate继续后续。

## 命令

```powershell
git archive --format=zip -o logs/physics/rail-baseline-9f2c142.zip 9f2c142 src
.venv/Scripts/python.exe -m zipfile -e logs/physics/rail-baseline-9f2c142.zip logs/physics/rail-baseline-9f2c142
.venv/Scripts/python.exe tools/physics/guardrail_support_probe.py --source logs/physics/rail-baseline-9f2c142/src --output docs/evidence/PHYS-SUSP-01/rail-baseline-r1
.venv/Scripts/python.exe tools/physics/guardrail_support_probe.py --output docs/evidence/PHYS-SUSP-01/rail-native-r1
.venv/Scripts/python.exe tools/physics/guardrail_support_probe.py --source logs/physics/rail-baseline-9f2c142/src --coupled-off --steps 60 --output docs/evidence/PHYS-SUSP-01/rail-disabled-baseline-r1
.venv/Scripts/python.exe tools/physics/guardrail_support_probe.py --coupled-off --steps 60 --output docs/evidence/PHYS-SUSP-01/rail-disabled-native-r1
.venv/Scripts/python.exe tools/physics/export_reference.py --output docs/evidence/PHYS-SUSP-01/reference-v24/parameters.json
```

精确T0/T1命令和工作区来源由各验证目录的summary.json保存；所有失败日志保留。

# 海岸道路有限轮胎距离精度

阶段T2-r2从干净`7fedb2a`运行：全Ruff通过，完整pytest首败停止，34通过/1失败，744.14s；后14项未跑。失败节点为`test_core.py::test_render_rates_use_identical_simulation`，海岸道路实际三角形边缘的轮胎凸体距离查询在96轮后未收敛。原始日志保存在`logs/validation/PHYS-DESIGN-01-stage-T2-r2/`，此轮不是阶段通过。

## 原因与修复

原式先将胎面偏移加到约−94m的世界坐标，再减道路见证点；小胎面偏移的低位在中间世界坐标中舍入。将报错中的两个道路边端点单独作为有限凸体即可快速复现：原版本在同一96轮上限失败，支持间隙为`2.36644e-13`，超过原门槛。修复在构造Minkowski相对坐标时对`center、−道路点、胎面偏移`直接使用`math.fsum`，避免中间舍入；几何、支持函数、96轮上限和`1e-13 * max(1, squared_distance)`门槛保持。

修复后同一边缘内核距离为`0.701711979458115m`。独立验证在轮轴截面上直接最小化道路边点至胎冠曲线实体的距离，不调用GJK或支持函数；同时平移场景1000m，距离仍满足原`2e-10m`验证精度。查询返回的见证点位于实际有限边上。[首个用例摘要](relative-geometry-summary.json)保存输入、旧失败及新结果，重现脚本在`logs/physics/PHYS-DESIGN-01-relative-geometry/`。

第一次原生复核仍失败（223.61s）：轨迹略变后，近似坐标下的另一个瘦长单纯形反复选回同一三角形，支持间隙`2.22156e-13`。保留实际失败单纯形作为初值即可快速复现。普通叉积将接近的两个乘积相减，舍入误差扭曲投影法线；改为用`math.fma`取回两个乘积的余量并补偿求差。保存的单纯形在原96轮和原间隙门槛内收敛，距离`0.7018921171915299m`。[单纯形摘要](simplex-geometry-summary.json)保留前后事实。

补充验证按实际双精度边向量定义平面，用70位十进制计算独立法线和原点投影，要求返回点绝对误差≤`1e-15m`；没有更改GJK判据或原生一致性测试。

## 验证

```powershell
.venv/Scripts/python.exe tools/validate.py T0 --tests tests/test_cylinder_suspension.py tests/test_triangle_support.py --output logs/validation/PHYS-DESIGN-01-relative-geometry-T0 --timeout 600
.venv/Scripts/python.exe tools/validate.py T0 --tests tests/test_core.py::test_render_rates_use_identical_simulation --output logs/validation/PHYS-DESIGN-01-render-rate-T0 --timeout 3600
.venv/Scripts/python.exe tools/validate.py T0 --tests tests/test_cylinder_suspension.py tests/test_triangle_support.py --output logs/validation/PHYS-DESIGN-01-relative-geometry-T0-r2 --timeout 600
.venv/Scripts/python.exe tools/validate.py T0 --tests tests/test_core.py::test_render_rates_use_identical_simulation --output logs/validation/PHYS-DESIGN-01-render-rate-T0-r2 --timeout 3600
.venv/Scripts/python.exe tools/validate.py T0 --tests tests/test_core.py::test_render_rates_use_identical_simulation --output logs/validation/PHYS-DESIGN-01-render-rate-T0-r3 --timeout 3600
```

相关有限胎宽/实际三角形短检查首轮19项及全Ruff通过（pytest .36s）；最终20项及全Ruff通过，实际命令和日志见r2目录。首次命令输出目录与旧记录重名，入口拒绝覆盖，未执行测试；已改用新的独立目录。事实脚本首次Git源码解码失败，改为明确UTF-8后完成，未修改物理。

原固定步一致性节点r2随会话中断退出（128.308s，0x40010004），未获得断言结论，runner原始状态保留并增加终止说明；进程已不存在后从独立r3目录恢复。r3已失败结束（108.37s）：传动/四轮共同求解20轮后几何共轭冲量残差3.68584e-10超限，轮胎距离查询没有报告此前错误。

## 实际跨面子步与法线精度

原生失败发生在完成第129拍之后。只在抛错时保存输入和最终候选值，原控制、碰撞、硬件和物理步均不变。四轮实际支撑物均为同一个道路网格；冻结完整512三角形及变换，在30组相同/扰动末速度查询中与原世界梯度逐项相等，单步离线重放得到同一失败。完整[硬件](coastal-step-config.json)、[机械输入与网格](coastal-step-input.json)保存为JSON；二进制临时捕获留在logs中，不作为测试入口。

第三轮轮胎正跨真实网格棱边。GJK的距离间隙已经满足要求，但近似法线的微小抖动使六维末状态的共轭冲量无法满足更严格的机械门槛。没有增加共同求解轮数或放宽门槛；对GJK已选中的实际角点/有限边投影到同一个胎冠内核，并再次核对原支持不等式。若投影指向其它物理特征，使用其分离向量和实际支持点继续原GJK，仍在96轮内。

内核截面为`r(q)=R−kq²`，`k=crown/H²`；点的轴向/径向坐标为`a、ρ`时，直接最小化`(q−a)² + max(ρ−r(q),0)²`，`q∈[−H,H]`。固定边上的参数驻点由分离向量与边方向点积为零确定；区间端点自然对应角点。肩部与道路margin继续由原扫掠合并，几何和硬件没有换型。原独立乘积几何检查同时核对法线方向。

同一失败输入修复后5轮收敛：法向残差`1.36424e-12N`、重新查询的几何共轭冲量残差`1.42488e-14Ns/Nms`、悬架能量残差`3.27528e-14J`；四轮保持实际正支撑。44次支持核对的最大间隙`1.11022e-16`，满足原门槛。完整前后数值及源码/输入SHA见[机器摘要](common-geometry-summary.json)。离线时间是单子步诊断，不能作为可见窗口性能Gate。

```powershell
.venv/Scripts/python.exe tools/validate.py T0 --tests tests/test_cylinder_suspension.py tests/test_triangle_support.py --output logs/validation/PHYS-DESIGN-01-edge-projection-T0 --timeout 600
.venv/Scripts/python.exe tools/validate.py T0 --tests tests/test_cylinder_suspension.py tests/test_triangle_support.py tests/test_coastal_contact_step.py --output logs/validation/PHYS-DESIGN-01-edge-step-T0 --timeout 600
.venv/Scripts/python.exe tools/validate.py T0 --tests tests/test_coastal_contact_step.py --output logs/validation/PHYS-DESIGN-01-edge-step-T0-r2 --timeout 600
.venv/Scripts/python.exe tools/validate.py T0 --tests tests/test_cylinder_suspension.py::test_axial_cylinder_distance_matches_independent_product_geometry --output logs/validation/PHYS-DESIGN-01-edge-normal-T0 --timeout 600
.venv/Scripts/python.exe tools/validate.py T1 --tests tests/test_core.py::test_render_rates_use_identical_simulation tests/test_guardrail_suspension.py --output logs/validation/PHYS-DESIGN-01-edge-native-T1 --timeout 3600
```

最终21项不同短检查有效通过及全Ruff：20项几何通过，新捕获节点首次因JSON梯度列表未恢复为元组失败，仅修复测试数据装配后节点通过；补强的4项独立法线检查通过，复用其余有效结果。相关T1运行中：原海岸场景、种子17、8辆NPC、控制、1200物理拍及30/60/144FPS完整Snapshot相等、四条两模式护栏及三种子启动。通过前不能用短检查代替原生集成结果。阶段T2、实车型及后续施工、T3/前台性能/用户两模式驾驶仍未完成。

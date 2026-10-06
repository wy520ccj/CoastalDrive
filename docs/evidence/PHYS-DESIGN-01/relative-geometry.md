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

## 有限面与轴向端面

上述增量保存为本地检查点`88b8e5c`，没有推送。相关T1已失败结束：4条两模式护栏通过/1完整驾驶节点失败（273.66s），三种子启动未跑。下一处为实际裁剪平面上的单纯形距离未收敛；只用保存的4个实际网格点即可复现同一失败。

增加有限三角面投影候选：轮胎支持点投影必须位于真实三角形内，并满足原全凸体支持判据才返回；不会把道路边外解释为无限平面。面积大的三角形优先，减少短边的法线舍入。独立70位静态面方程与胎冠最大高度核对距离/法线，绝对精度`1e-14`通过；测试首轮未将法线朝向轮胎一侧，修正该几何约定后通过，生产和门槛不变。有限面/原捕获子步/护栏等25项及Ruff通过；该新节点另行补测，不重复其余检查。

有限面版原生T1又失败（431.54s），三种子未跑：这次选到轴向角点时，支持函数生成的顶点竟超出真实轮胎内核。轮轴范数平方少一个舍入位，`direction − projection * axis`的轴向残差被当作径向并归一化，导致声明半宽`.1025m`却返回`.417402968m`的轴向外廓。改用补偿双叉积提取真实正交分量，并按轴长度计算轴向投影；点到内核的投影采用同一几何。没有添加小分量截断。角点/有限边投影提前用原支持判据核对，避免真实端面法线已知时仍迭代有误差的单纯形。

修复后轴向外廓`.1025m`，同一实际角点内核距离`.0823650399584991m`；该点位于端面径向范围内，距离/法线由独立轴向间隙解析式核对。正反轴向外廓和原有限面/边、网格过渡、完整跨面子步、两模式护栏共27项及全Ruff通过（5.91s）。[前后失败、输入、解析结果与源码SHA](finite-feature-summary.json)。96轮GJK、20轮共同求解、原支持间隙和机械残差门槛继续保持。

```powershell
.venv/Scripts/python.exe tools/validate.py T0 --tests tests/test_cylinder_suspension.py tests/test_triangle_support.py tests/test_coastal_contact_step.py tests/test_guardrail_suspension.py --output logs/validation/PHYS-DESIGN-01-finite-face-T0 --timeout 600
.venv/Scripts/python.exe tools/validate.py T0 --tests tests/test_cylinder_suspension.py::test_captured_finite_coastal_face_matches_high_precision_profile_extent --output logs/validation/PHYS-DESIGN-01-finite-face-T0-r3 --timeout 600
.venv/Scripts/python.exe tools/validate.py T1 --tests tests/test_core.py::test_render_rates_use_identical_simulation --output logs/validation/PHYS-DESIGN-01-finite-face-native-T1 --timeout 3600
.venv/Scripts/python.exe tools/validate.py T0 --tests tests/test_cylinder_suspension.py tests/test_triangle_support.py tests/test_coastal_contact_step.py tests/test_guardrail_suspension.py --output logs/validation/PHYS-DESIGN-01-axial-projection-T0 --timeout 600
.venv/Scripts/python.exe tools/validate.py T1 --tests tests/test_core.py::test_render_rates_use_identical_simulation --output logs/validation/PHYS-DESIGN-01-axial-native-T1 --timeout 3600
```

最终轴向修复版原生T1已通过：完整1200拍×30/60/144FPS Snapshot相同（pytest2869.71s），全Ruff及0/17/23各1200拍启动通过（41.0/40.9/40.6s）；与相关27项短检查合并28项不同检查。源码SHA与短检查一致，原门槛和控制不变。当前增量仅本地提交，未推送；旧失败和中断保留，机械/参数化阶段T2及总体Gate没有关闭。

## 一万步轨迹的低速跨面行程

干净`01694dc`的T2-r3实际结束：Ruff通过，pytest36通过/1失败（3881.02s），其余14检查未跑。一万步单车节点在完成9737拍后共同求解失败；轮胎、制动及法向已满足原合同，几何共轭冲量`1.4051563532922668e-11Ns/Nms`超出原`1e-12`。原失败和全部测试数量保持，未减少10000拍。

同一`Simulation(9)`、`Control(throttle=.5)`只在抛错时采集完整输入。四轮支持物为road/outer-shoulder/road/road，保存两份完整512三角形网格；30组末速度查询与原世界梯度最大差为0，离线重放得到相同20轮失败。[完整硬件](coastal-long-step-config.json)、[输入和真实网格](coastal-long-step-input.json)可直接由回归节点复现。

右前轮从一块真实三角面移入相邻面，前后法线分别为`(.0197416636,-.0464975520,.9987233072)`和`(.0197550125,-.0465289927,.9987215790)`；不是同一平面，也不是需要抹平的路面接缝。原Gonzalez修正直接减两个扫掠行程，再除以时间和六维速度平方，低速时行程舍入被放大为梯度抖动。

有限面查询现在同时返回真实面锚点和原margin，保持原有限面入射判据；面锚点相对本子步车身原点传递。设末面法线为n、锚点A、margin为m，支撑高度为H，末方向对齐a1=-n·d1。初始相对此末面的固定余量为`g0=n·(h0-A)-H(n,u0)-m+n·d0*l0`。直接计算

`Δl=(g0+n·Δh+l0*n·Δd-ΔH)/a1`。

使用原实际转动路径的共轭平均向量计算`Δh=dt*(v+Ω×h平均)`、`Δd=dt*Ω×d平均`和胎冠高度差商ΔH，把固定高度余量与小运动分开；不从两个近似相等的扫掠行程取得增量。真正的棱/角曲面继续原几何分支，共同求解仍为20轮、GJK96轮，原支持间隙/机械门槛不变。

同一保存输入5轮收敛：重新查询的共轭冲量残差`4.4047312351375086e-15`，法向`1.8189894035458565e-12N`，悬架能量`-2.3670301829703533e-14J`，四轮实际正支撑。[机器摘要与源码SHA](cross-face-summary.json)。相关107项短检查及全Ruff通过，包含旧棱/角子步、新9737拍子步、实际网格/护栏/转动路径与独立60位平面交点。原9737拍共同求解输入明确复现旧失败并验证修复。

```powershell
.venv/Scripts/python.exe tools/validate.py T0 --tests tests/test_cylinder_suspension.py tests/test_triangle_support.py tests/test_coastal_contact_step.py tests/test_guardrail_suspension.py --output logs/validation/PHYS-DESIGN-01-face-secant-T0 --timeout 600
.venv/Scripts/python.exe tools/validate.py T0 --tests tests/test_finite_suspension.py tests/test_curved_suspension.py tests/test_suspension_contacts.py --output logs/validation/PHYS-DESIGN-01-face-interface-T0 --timeout 600
.venv/Scripts/python.exe tools/validate.py T1 --tests tests/test_core.py::test_headless_ten_thousand_steps_without_renderer_imports --output logs/validation/PHYS-DESIGN-01-face-secant-native-T1 --timeout 3600
```

一万拍原生T1实际通过（pytest924.08s）：完成10000拍且未导入显示应用；全Ruff及0/17/23各1200拍启动通过（41.8/41.4/41.6s）。331份源码／测试／工具前后SHA相同，与107项短检查合并108项不同pytest检查。机械/参数化T2、实车型与后续功能、总体T3/前台性能/用户两模式驾驶继续待办。局部重放耗时只作诊断，不作性能Gate。

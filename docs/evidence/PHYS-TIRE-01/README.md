# 轮胎迁移的单轮积分研究

当前整车仍是PHYS-04；本文件记录独立一维研究组件，未接入Bullet整车，也未替换原轮胎力。

`tools/physics/wheel_integration_lab.py`把车轮角速度与平动速度耦合隐式求解。300kg单轮等效平动质量、1.8kg·m²轮惯量、0.33m半径、3000N法向力、μ=1.1、纵向刚度60000N均是明确的研究输入，不是车辆标定。实际整车需使用刚体质量/惯量与轮接点的有效动力学，不能把300kg直接作为每轮独立车体。

给定Fx后，v_next=v+dt Fx/m，ω_free=ω+dt(Td−rFx)/I；制动以干摩擦软阈值求ω_next，允许保持ω=0，反力矩由变化量反算。Fx用μFz*tanh[Cκ(rω_next−v_next)/(μFz max(|v_next|,1m/s))]，在±μFz内固定32次二分解一致性方程。

后向离散的能量恒等式为：

`ΔE = dt Td ω_next − dt Tb_used ω_next − dt Fx(rω_next−v_next) − m(Δv)²/2 − I(Δω)²/2`。

四工况（自由滚动2s、起步驱动2s、20m/s制动3s、仅轮自转衰减2s）×1/120、1/480s两个步长均通过：最大力方程残差约1.4e−5N，最大能量恒等式残差约2.22e−11J；无外功工况耗散，制动无反转。原始component-lab.json记录全部参数、实际转矩、动能变化与检查条件。

命令：`.venv/Scripts/python.exe tools/physics/wheel_integration_lab.py --output docs/evidence/PHYS-TIRE-01/component-lab.json`。输出须为新文件；复跑使用另一路径。新增工具Ruff通过。本结果只证明这一组件的耦合/制动与能量账正确，下一实现仍须处理三维联合滑移、实际接触/轮荷、旋转反力矩与完整A/B。

该单调tanh曲线用于积分研究；ABS所需的峰值滑移与滑动段行为尚未选择/验证，不把此曲线冒充最终ABS轮胎模型。后续滑移与低速模型可核对[MathWorks Tire-Road Interaction](https://www.mathworks.com/help/sdl/ref/tireroadinteractionmagicformula.html)的实际滑移定义及平滑低速分母，再由同条件试验验证所选游戏模型。

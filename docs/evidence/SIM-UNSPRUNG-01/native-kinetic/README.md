# 原生动能分量与导向误差定位

2026-10-14，基线f2df8d0，独立仿真树。只读诊断工具增加独立分量；本节点没有修改生产物理、参数、阈值或任何车辆状态。整体目标active，SIM-UNSPRUNG-01仍in_progress。

## 全车实际账

同一18km/h、10mm单侧实体凸起、2.4s、8子步/2304机械步，正常time_limit。整车残差峰0.005229577J/累计+0.723039918J，与前一工具版本逐项一致。每步另核对实际末状态与共同预测末状态的五个动能分量，总差重构1e−8J检查全部通过：

| 分量 | 累计差/J |
|---|---:|
| 簧上平动 | −9.057531145 |
| 四轮端平动 | +9.853314624 |
| 簧上角速度 | −0.050500030 |
| 惯量方向输运 | −0.000000002 |
| 自旋/传动轴 | 0 |
| 合计原生动能差 | +0.745283447 |

末解平动速度单次转为float32所得参照差累计−0.060438034J；实际平动总差相对该参照仍+0.856221513J。它排除了“仅把末速度舍入一次就能解释差額”的假设；不排除原生顺序施力、多次舍入及约束求解误差。车身/轮端大量相消不能当成独立分量均已正确。

保存的t=1.182291667s实际状态，前轮横向位置偏移约−25.4/−25.9µm、后轮约−5.74/−4.73µm；扣除车身平动和角运动后的横向相对速度约0.004394/0.004394/0.001465/0.001465m/s。比较位置误差乘−0.2/h，其数量级接近该速度。`guide-observation.json`中的0.2仅是参考计算，并非读取到的实际求解行或已确认唯一根因。

[Bullet2.84原始6DOF实现](https://raw.githubusercontent.com/bulletphysics/bullet3/2.84/src/BulletDynamics/ConstraintSolver/btGeneric6DofConstraint.cpp)包含位置误差/步长的速度修正；[原生顺序冲量实现](https://raw.githubusercontent.com/bulletphysics/bullet3/2.84/src/BulletDynamics/ConstraintSolver/btSequentialImpulseConstraintSolver.cpp)在约束行中加入外力/力矩速度增量。结合本项目数据，下一应核对实际导向框架、位置修正目标和反力功，而非继续调轮胎径向系数。源实现解释算法，不能替代本项目约束行实测。

## 独立恒力解析对照

`native_force_rounding_check`用1040kg/5m/s无重力自由刚体、恒力−.02/−20/−300N各1秒及2/4/8子步，解析末速度为5+F/1040。比较提前冲量再加剩余力与全部连续力；单世界、无约束，不冒充整车改进。

−.02N的18种组合中的6个结果均仍5m/s，丢失应有1.9231e−5m/s变化。−20N在4子步，分开提交误差−2.2419e−4m/s，全连续力4.6950e−6m/s；−300N全连续力仍非单调。这证明当前原生累加有精度底限及提交顺序影响，**不证明把所有力换一种提交就足以修复全车**。没有据此修改生产接口或添加补偿力。

## 证据与下一入口

`components.json`提取原始result；raw-evidence.zip含全部2304步CSV、峰值输入、原result/执行工具、恒力18组及相关源文件。当前执行source SHA逐一匹配，manifest保留真实字节；未回填上一版本。运行命令：

```
.venv/Scripts/python.exe tools/physics/lab_energy_check.py --output logs/SIM-UNSPRUNG-01/native-kinetic-parts-8-r1 --maneuver ride_bump --duration 2.4 --substeps 8
.venv/Scripts/python.exe tools/physics/native_force_rounding_check.py --output logs/SIM-UNSPRUNG-01/native-force-rounding-r1
.venv/Scripts/python.exe -m ruff check src tests tools
```

Ruff与diff检查通过；生产代码未变，复用上一节点有效T0/T1/GUI，未再次跑完整套件，不把原失败T1改为绿色。实际诊断重跑是为了取得此前缺少的分量，结果与旧总账相同。恒力检查是故障诊断完成，精度门槛未通过。导向精度、全车能量、真实制动A/B、实测与人工Gate均开放；main未改、未推送。

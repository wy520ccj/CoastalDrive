# 20Hz直接控制与确定性重放

DrivingExperiment直接拥有一个Simulation；每个VehicleCommand固定执行六个120Hz物理步，得到20Hz只读观测。执行器请求绕过键盘和输入辅助；同硬件下两种模式直接请求完全一致。可选SensingRun在这六拍逐拍采样，保留原始测量与每拍独立估计。六拍事件/冲击全部累积，不只读取最后一拍。碰撞、真实reset/恢复和控制步数上限分别产生明确终止/超时；结束后须reset，reset保留配置并按种子重建唯一世界。初始位姿和沿车身forward的初速是声明的实验初值，只在reset边界施加；运行中没有轮速目标、瞬移或状态修正。

工具按新目录保存完整vehicle.json与experiment.json。记录完整硬件、种子/地图/初值/模式、传感器配置、120/20Hz与六拍协议、代码SHA和每个实际请求/完整观测摘要。重放需已完成且同版本冻结记录，核对保存车辆文件SHA，并逐个比较所有物理/轮胎/轴/悬架、六帧测量与估计。只排除运行实例contact_epoch与ImpactEvent.epoch；物理碰撞、姿态和冲击事实都保留。参数A/B使用基线实际执行的同一命令序列，保存候选完整配置和变化字段；候选提前终止时其步数/原因独立记账，不称同硬件重放。

首次T0为3通过/1非零初速观察错误：reset前原悬架接触为空，直接观察得到空轮状态。修复为读取实际原生四轮初始接触后刷新已有观察，未改物理、未添加默认轮状态；真实20m/s墙撞节点补测通过，原失败保持。六拍采样/reset一致、两模式/超时、真实墙撞事件完整收集、记录重放与质量参数A/B共4项不同T0有效。最终T1为17项pytest/全Ruff及三种子各1200拍启动，pytest22.04s，启动75.6/67.6/71.5s；当前同时计算标准实验，墙钟耗时不作性能结论。[凭据](completion-receipt.json)。

GR86实际120个请求/720个物理步，含IMU/轮速/GNSS与独立估计。[命令](commands.json)、[完整记录压缩存档](baseline/experiment.json.gz)与[完整配置](baseline/vehicle.json)。同硬件第二次运行120个完整观测摘要逐项相同，[重放比较](replay/comparison.json)通过；原始记录SHA在凭据中。低附着只改road_friction1.1→.9，其余硬件与请求不变；两组均120请求，末位置分别(97.526,26.704,.450)/(97.745,27.508,.450)m，末小正/负速度原样保存，不解释为运行修正。[参数A/B](low-mu-ab/comparison.json)。

```powershell
.venv/Scripts/python.exe tools/validate.py T0 --area research --output logs/validation/PHYS-RESEARCH-01-interface-T0 --timeout 600
.venv/Scripts/python.exe tools/validate.py T1 --area research --tests tests/test_validation_runner.py --output logs/validation/PHYS-RESEARCH-01-completion-T1 --timeout 900
.venv/Scripts/python.exe tools/physics/experiment.py record --commands logs/physics/PHYS-RESEARCH-01/commands.json --vehicle-config assets/game/vehicle-configs/gr86-2022-premium-6mt.json --sensors --seed 23 --output logs/physics/PHYS-RESEARCH-01/gr86-record-r1
.venv/Scripts/python.exe tools/physics/experiment.py replay --record logs/physics/PHYS-RESEARCH-01/gr86-record-r1/experiment.json --output logs/physics/PHYS-RESEARCH-01/gr86-replay-r1
.venv/Scripts/python.exe tools/physics/experiment.py ab --record logs/physics/PHYS-RESEARCH-01/gr86-record-r1/experiment.json --vehicle-config logs/physics/PHYS-RESEARCH-01/mu-09.json --output logs/physics/PHYS-RESEARCH-01/gr86-low-mu-ab-r1
```

存档experiment.json.gz仅压缩包装，解压到同目录experiment.json并保留vehicle.json后按同版本代码重放；没有改写原始记录。自动功能块完成，隔离源码尚未合并主目录。机械T2、GR86最终12工况/报告、产品与性能/总体T3和用户两模式驾驶继续。实际AI训练与奖励设计不在本期。

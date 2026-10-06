# 独立传感器与15维误差状态EKF

隔离开发版从389b056接入，唯一物理世界120Hz不变。Snapshot补body→world真实四元数，传感器/估计/延迟回放全部位于Snapshot之后；Simulation、轮胎、传动和ABS/TCS/ESC不导入这些模块。仅reset的已知初始位姿/速度用作初始化，运行滤波从IMU、四轮编码器与GNSS更新，不读取真值kappa、力或姿态替代观测。

IMU位于CG，每个完成物理区间采样平均角增量与速度增量，中点姿态给出比力。体轴/世界轴均沿Panda的X右/Y前/Z上；Hamilton标量在前，误差为右乘局部旋转。名义位置/速度/四元数/双偏置对应15维误差协方差，重力固定(0,0,-9.81)。中点预测的解析雅可比包括陀螺误差到速度/位置的交叉项，Joseph观测更新和右雅可比reset保持同一误差定义。理论采用[Solà第5/6节](https://arxiv.org/abs/1711.02508)的局部误差结构，本项目固定重力。

明确工程噪声：IMU120Hz，轮速60Hz、GNSS10Hz和100ms延迟；白噪声为每采样标准差，偏置游走单位/√s。GNSS位置使用localY+origin_y，传感器三个随机源与物理/交通独立；配置声明失联窗口。短历史只保存估计和实际测量；迟到GNSS回到采样tick更新，重放已有IMU/轮速/其它GNSS到当前。reset清空历史/延迟队列，真正世界rebase不重置估计。轮观测使用声明轮径和测得转角，采用4维创新门槛16及.25m/s模型标准差；失联、轮滑不填真值或重置车身。

解析240拍三维恒转率/恒世界加速度误差在1e-15量级；15维雅可比独立差分最大差1.94e-11。100ms延迟与即时融合最终完整状态/协方差逐项相等。带偏置/噪声/GNSS3秒失联和后轮滑转的960拍解析实验，位置/速度分量RMSE .279m/.115m/s，原GNSS位置1.370m，60次轮滑观测全部因创新拒绝，协方差正定。[解析凭据](analytic-summary.json)。

三个原生工况各960拍、逐拍120Hz轨迹保存，GNSS每组实际交付49条：

| 工况 | 位置分量RMSE m | 速度分量RMSE m/s | 末姿态误差 deg | 轮观测拒绝 |
|---|---:|---:|---:|---:|
| 直线加速/制动 | .3166 | .1527 | 2.6223 | 17 |
| 转向/制动 | .3119 | .1258 | .7291 | 15 |
| 实际弯坡 | .3317 | .1770 | 2.3805 | 17 |

姿态误差和弱激励可观性原样保存，未把短数据当作真实设备标定或全工况稳定证明。[配置、源SHA、详细结果](native-summary.json)。传感器开启/关闭原生120拍完整Snapshot逐拍相同；静止倾斜比力、解析导数、延迟、失联/轮滑、实际重定位/reset和只读插值共10项不同T0通过。相关完整T1含27项pytest/全Ruff及0/17/23各1200拍启动，pytest23.34s、三种子42.1/43.1/51.7s。[收口凭据](completion-receipt.json)。

```powershell
.venv/Scripts/python.exe tools/validate.py T0 --area estimation --tests tests/test_core.py::test_snapshot_has_no_mutable_state_and_interpolation_does_not_write_back --output logs/validation/PHYS-EST-01-native-interface-T0 --timeout 600
.venv/Scripts/python.exe tools/physics/estimation_probe.py --output logs/physics/PHYS-EST-01/native-r1
.venv/Scripts/python.exe tools/validate.py T1 --area estimation --tests tests/test_gr86.py tests/test_validation_runner.py tests/test_core.py::test_snapshot_has_no_mutable_state_and_interpolation_does_not_write_back --output logs/validation/PHYS-EST-01-combined-T1 --timeout 900
```

自动功能块完成，尚未合并主目录。主目录机械T2、GR86高速度定圆/12工况标定、研究20Hz协议、产品/性能/总体T3及用户两模式驾驶继续。估计反馈控制不在本期。

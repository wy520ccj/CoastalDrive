# CTRL-02 后驱滑转反馈TCS

基线 `bd0f9e4213a10e0eecdfe9bb21446410996d34ad`，承接CTRL-01。本功能块的自动部分已完成，T1与专项结果在本页末尾记录；整个物理目标、人工驾驶与可见性能仍未完成。

## 机制与边界

独立vehicle_traction读取上一完整步四轮真值，后驱轮以`direction × (rω−vx) / max(|vx|, 1m/s)`形成驱动方向滑转反馈。预测时域0.12s对应当前发动机响应期，目标0.12与触发余量0.015为通用设计值，未按真实轮胎标定，也没有宣称所有μ下都在最优峰值。可用驱动比例以有限变化率削减/恢复，进入Powertrain的目标转矩，真实轮端转矩仍经原有0.12s响应。过度空转轮可请求不超过0.25的归一化制动；与驾驶者请求取较大值后，由原有25ms四轮压力执行器与ABS形成实际转矩。

[Bosch](https://www.bosch-mobility.com/en/solutions/driving-safety/electronic-stability-program/)说明驱动防滑属于电子稳定系统的功能，发动机调节与单轮制动是实际执行器路径。这里实现可解释的通用反馈控制，并非复刻产品控制器。保留后驱等分转矩和简化发动机制动；单轮制动没有把额外转矩转给另一轮，差速器未完成。轮速/轮心速度取仿真真值，传感器和速度估计另立任务。

前轴没有TCS制动。松油、驾驶者制动、空挡或全部驱动轮无支撑时撤销控制请求；已有压力和驱动转矩继续按真实执行器衰减。离地轮保留转动动力学且不产生路面力，再接触由真实反馈恢复控制。ABS负责制动滑移，TCS负责驱动滑转，两者通过同一制动执行器及唯一轮胎力作用。没有直接赋车速/轮速/姿态，没有提高附着或增加人工稳定力。

两模式默认开启ABS/TCS；主菜单F2页与CLI的`--abs on|off`、`--tcs on|off`分别可选。设置、开始时重建、同配置重开、NPC配置、reset/回收、坐标重定位及显示插值已贯通。成绩按game-controls-v2/reference-v3和两个开关分区；完整参数表为55车辆、8制动、10防滑、9输入字段，见[reference-parameters.json](reference-parameters.json)。

## 同条件A/B

独立水平Bullet平面、120Hz。除离地工况外静置240tick，零初速度，A/B只改TCS开关，默认运行6秒。低附着μ0.3；split-μ左侧铺装1.1、右侧草地0.2并保留草地滚阻；倒车使用明确R请求。离地工况从原始spawn上移2m一次，随后重力落地，前后轮均实际出现两次接触进入。松油和驾驶者制动从2秒后的首步开始切换，后者故意同时给油门1/制动1检验优先级。

逐tick完整快照见[tcs-ab](tcs-ab/summary.json)。表中超限滑转积分为两后轮有支撑时`∫max(|κ|−0.2,0)dt`之和，含无量纲滑移乘秒；不是空转持续时间。不同初期加速造成松油/制动时初速度不同，不把这两行当作同初速度制动距离比较。

| 工况 | A末速度m/s | B末速度m/s | A后轮超限滑转积分s | B后轮超限滑转积分s | A路径m | B路径m |
|---|---:|---:|---:|---:|---:|---:|
| asphalt | 20.562 | 20.560 | 0.000 | 0.000 | 64.169 | 64.156 |
| low-mu | 1.253 | 7.751 | 596.264 | 0.110 | 4.699 | 22.673 |
| split-mu | 0.328 | 1.733 | 603.611 | 0.095 | 3.868 | 7.074 |
| reverse | 19.699 | 19.709 | 0.531 | 0.000 | 60.357 | 60.482 |
| airborne-recontact | 18.150 | 17.107 | 11.307 | 7.127 | 47.659 | 41.304 |
| lift-off | 0.902 | 0.449 | 254.393 | 0.110 | 4.694 | 7.385 |
| driver-brake | 0.000 | 0.000 | 138.435 | 0.740 | 0.982 | 3.460 |

低附着和split-μ的过度空转显著下降，真实车速/位移提高；两后轮实际转矩、右低附着轮压力与制动力在CSV中可检验。铺装仅短暂削矩，末速度变化约0.002m/s。离地再接触的瞬态滑转积分仍为7.127s，且B末速度较低，原始数据完整保留；没有用控制器钳轮速消除落地响应。TCS起步工况不能替代CTRL-01尚失稳的split-μ制动，下一任务是[CTRL-03](../../tasks/CTRL-03.md)。

## 冻结机械对照

[tcs_mechanical_check.py](../../../tools/physics/tcs_mechanical_check.py)从Git导出上述基线源码，在独立进程运行旧A/关闭TCS的新B。test/coastal/endless-hills三场景各1200tick，seed23，固定油门/转向/松油/制动时序。2,073,665个既有字段比较、几何/其余数值实际最大差异均为0。新增TCS配置/诊断单独列出，原有碰撞/接触身份字段沿用既有比较器的明确排除规则。完整轨迹和源码哈希见[mechanical-off](mechanical-off/summary.json)。默认TCS开启分支允许由控制机制改变轨迹。

## 开发失败与保存

- `exploratory/tcs-initial`：初次运行完成前四工况后，离地工况调用本机不支持的makePosQuat失败，原始CSV压缩保留；此目录没有成功summary。
- `exploratory/tcs-second`：修正原生API后，初始空contact列表与后续真实接触字段导致固定CSV表头导出失败。改为工具自身按所有行字段并集导出，保留空值/矢量字段，不删动态观测；另加入真正落地后的CSV测试。原半成品CSV保留。
- `exploratory/tcs-third`：七工况完整试跑；介入阈值请求一致性及字段注解随后收尾，该目录不替代最终冻结证据。
- 首次integration要求split-μ左后轮制动介入而失败：实际为右侧低附着轮空转。现测试验证右轮实际压力/转矩、左轮压力为零，控制器未改以迎合断言。
- 轻度代理设置测试的NPC夹具使用了刚体上不存在的setY，改用显式reset定位、TractionControl.advance生成介入记忆，然后触发实际回收。该fixture只证明生命周期；整车受力另由integration/A/B证明。
- 首次[CTRL-02-t0](CTRL-02-t0/summary.json)Ruff失败，pytest未运行；[CTRL-02-t0-v2](CTRL-02-t0-v2/summary.json)Ruff和43项完整相关短测通过。

## 命令与验收

```powershell
.venv/Scripts/python.exe tools/physics/tcs_probe.py --output docs/evidence/CTRL-02/tcs-ab --duration 6
.venv/Scripts/python.exe tools/physics/tcs_mechanical_check.py --output logs/physics/CTRL-02-mechanical
.venv/Scripts/python.exe tools/validate.py T1 --area vehicle --area gameplay --area appearance --area traffic --area road --output docs/evidence/CTRL-02/t1
.venv/Scripts/python.exe tools/driving_mode_ui_check.py --output docs/evidence/CTRL-02/ui-720 --height 720
.venv/Scripts/python.exe tools/driving_mode_ui_check.py --output docs/evidence/CTRL-02/ui-1080 --height 1080
```

720p/1080p设置页、独立关闭TCS与真实ABS/TCS介入HUD实际渲染检查通过，主代理已查看截图，没有文字遮挡或按钮重叠。此处离屏只证明布局与真实状态接线，不替代人类驾驶和可见窗口性能。

最终[T1](t1/summary.json)：327项pytest与Ruff通过，0/17/23三种子1200tick启动、0/23两种子十二车弯坡30秒检查全部通过。[源码完整性](source-integrity.json)记录238个Python文件在T1、正式A/B、参数导出、双分辨率渲染及8种CLI启动期间SHA-256完全一致。[CLI](cli/summary.json)验证两个模式与ABS/TCS开关全部8种组合；启动只证明接线，不替代真实受力验证。T2在ABS/TCS/ESC功能组收口时统一执行；T3、可见性能及用户驾驶结论在完整阶段分别验收。

T1后仅修正省略电子开关参数的save(mode)沿用已选ABS/TCS（保持旧API语义），并增加该边界断言。[final-settings-t0](final-settings-t0/summary.json)的Ruff/12项设置、生命周期和配置I/O通过。T1与专项区间的238文件哈希不变结论保持；这两处后续源文件差异另列[final-source.json](final-source.json)，不把最终源码与T1区间源码说成完全相同。机械控制、参数与界面布局未变，无须重复整轮T1。最终14份逐tickCSV已无损gzip归档，[archive-manifest](tcs-ab/archive-manifest.json)保存原字节和归档SHA-256，解压核验逐字节一致。

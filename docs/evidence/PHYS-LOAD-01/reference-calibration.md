# 通用参考车道路载荷与标准基准

2026-10-06；机械基线`ca8d286`，物理版本reference-v28。参数仍为完整设计参考车，采用现有硬件建立解释明确的基准；没有用实车型数据给它背书。本轮不调整已一致的硬件与电子增益。

## 按硬件顺序核对设计目标

1. 几何/静载：1200kg，轴距2.2m、轮距1.68m、50%前静载。水平四轮各2943N；实际静置读回2943.00145N。弹簧48000N/m对应61.3125mm压缩；实际61.31216mm。共同几何预测质心高度0.4186875m，实际0.41868785m。0.42m是车辆设计坐标的质心参数，实际离地高度随悬架支撑变化。
2. 悬架：四角等载小振幅设计推导，垂向2.013Hz、俯仰1.751Hz、含防倾杆侧倾2.847Hz；压缩/伸张阻尼比0.696/0.364。这里是硬件线性推导值，非本轮道路振动频谱测量；完整止挡、离地/再接触与实际防倾功能见上一接触功能块证据。
3. 动力/传动：参考扭矩曲线峰值200N·m/3200rpm，分段线性功率峰值约94.34kW/5812.5rpm；五挡、主减速3.7、效率0.88、有限离合及各轴实体惯量沿当前机械实现。12s全油门末速108.905km/h，0–60为5.200s、0–100为10.483s，都是当前模型结果。
4. 轮胎：半径0.33m、宽0.205m，实际有限胎宽/胎冠接触；单轮转动惯量1.8kg·m²。标称纵/侧偏刚度60000N与50000N/rad，铺装/草地μ=1.1/0.45，载荷敏感指数0.90/0.90/0.85、柔性接触区150000N/m与1000N·s/m。三种定圆末段拟合结果见下表。
5. 电子：ABS/TCS/ESC保持现有硬件配置，真值反馈。标称单轮曲线网格计算，ABS目标κ=0.12处铺装/草地纵向力为各自峰值的97.86%/98.78%；这是当前轮胎模型属性。实际执行器时间常数、压力调节及横摆分配由完整标准轨迹读回，不声称实车控制标定。

完整96车辆字段、9输入字段的单位/定义、真实两模式读回及源哈希见[reference-v28.json](reference-v28.json)；标准基准、完整配置、每条120Hz轨迹路径/哈希、初始静态Snapshot及推导结果见[reference-baseline.json](reference-baseline.json)。游戏专用配置继续独立，参考车不含游戏轮惯量扭矩补偿或速度裁剪。

## 物理因果与标准结果

空挡平路近似等效质量`m_eff=m+(4Iw+(Jout+Jrear)*i_final²)/r²=1272.401kg`；实际下游轴保持随驱动轮转动。载荷`R=160N`、`b=ρCdA/2=0.42kg/m`。积分`m_eff*dv/dt=-(R+b*v²)`，100km/h滑行6s预测25.613137m/s，实测25.614054m/s，差0.000917m/s。该近似用于低侧滑平路支撑对照；全机械账仍以各轮/转子/悬架的独立动量和能量检查为准。

| 试验 | 当前结果 |
|---|---|
| 平路全油门12s | 末速108.905km/h；0–100为10.483s |
| 100km/h空挡滑行6s | 末速92.211km/h；160.057m；轮端滚阻耗散25594.83J |
| 100km/h平路全制动 | 3.250s、45.549m；最大减速度8.924m/s² |
| 100km/h +5°上坡全制动 | 2.967s、41.261m；最大减速度9.740m/s² |
| 100km/h −5°下坡全制动 | 3.558s、49.481m；最大减速度8.132m/s² |
| 阶跃齿条2°，40km/h初速 | 3.5s累计航向−22.298°；最大侧偏0.489° |
| 弯中制动，同初速及齿条 | 3.133s首次达到停车判据；完整3.5s路径22.699m；最大侧偏1.030° |
| 对开附着100km/h全制动 | 6.500s、90.762m；累计航向−6.554°；最大侧偏1.158° |
| 定圆目标20m/40m/60m | 末2s位置拟合20.0737/40.0967/60.1303m；误差0.369%/0.242%/0.217% |

停车判据为水平速度模长<0.1m/s；距离为每拍真实三维位置增量的累积，包含坡路位移。齿条通过实际转向响应推进，不直接旋转车身。定圆速度使用现有踏板反馈，末速度约19.8km/h，不强设20km/h。弯中制动在完整观察窗口末出现−0.0507m/s小反向速度，原样保留。气动功为末世界子步功率的120Hz积分诊断；轮端滚阻耗散是真实所有机械子步累积，两者定义分别记录。

对开附着的左右资格按真实轮接触点x重新计算；转弯后可能跨越边界，不能解释为全程强制两轮低附着。初轮6s未停车，原CSV/摘要保留。仅把标准观察上限延长到10s，补跑此项；实际6.5s停车，前720拍与初轮逐行字节一致。

旧车身中央滚阻与新轮端滚阻仅切换`wheel_rolling_resistance`，同车/空挡/同路/同控制/6s：末速25.612598→25.614054m/s，路程160.051300→160.057114m。差异较小但保留；新路径的矩/热、轮速及外部角动量按实际轮端产生，不用中央力再补一次。

## 命令、原始结果与验证

```powershell
.venv/Scripts/python.exe tools/physics/testbed.py --driving-mode simulation --actuator-input --stride 1 --cases static_load flat_coast flat_braking uphill_braking downhill_braking flat_acceleration steering_step corner_braking split_mu_braking circle_20m circle_40m circle_60m --label reference-v28-roadloads --output logs/physics/PHYS-LOAD-01/reference-v28-standard
.venv/Scripts/python.exe tools/physics/testbed.py --driving-mode simulation --actuator-input --stride 1 --cases split_mu_braking --label reference-v28-split-to-stop --output logs/physics/PHYS-LOAD-01/split-to-stop
.venv/Scripts/python.exe tools/physics/testbed.py --driving-mode simulation --actuator-input --stride 1 --cases flat_coast --vehicle-config logs/physics/PHYS-LOAD-01/legacy-central-rolling.json --label reference-v28-legacy-central-rolling --output logs/physics/PHYS-LOAD-01/legacy-rolling-coast
.venv/Scripts/python.exe tools/validate.py T1 --tests tests/test_physics_testbed.py tests/test_road_loads.py tests/test_driving_modes.py --output logs/validation/PHYS-LOAD-01-final-T1
```

输出目录要求新目录。标准工具现在与游戏复用`advance_world`、外部120Hz/两个机械与世界子步；历史外部源码缺少world_step时明确保留历史单步协议。默认CSV20Hz，`--stride 1`完整120Hz。原始初轮摘要的全局平面描述仍写“horizontal”，但每个坡路工况的grade及真实法线/三维位移已正确保存；合并基准修正描述并记录初轮工具哈希，未改动原始证据。当前工具已正确记录各工况平面。

T0：轮端机械391项、护栏/原生12项通过；工具确定性/条件对照2项通过（88.87s）。最终T1：相关23项pytest通过（315.44s）、全Ruff通过、0/17/23三种子各1200步通过（57.47/62.94/78.85s），同车同执行器两种输入模式的真值逐拍一致。391项有效机械账复用。元数据测试只运行其实际核对的阶跃/对开附着，完整12工况使用独立标定命令，避免为元数据重复整套长试验。机械T2、旧音频接触断言收口、最终T3/前台性能/人工驾驶继续保留为未完成。

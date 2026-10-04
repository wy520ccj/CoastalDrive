# PHYS-DRIVE-03 有限粘性限滑自动功能块

基线为DRIVE-02收口39b3f52，核心实施提交b3a446e。自动功能块完成；整体阶段与人工驾驶验收另列。

有限粘性限滑已接入三轴端口、共同接触/离合/制动末状态、接触导数、真实逐轮矩及壳体反力。Powertrain新增三端口滑差、转矩和完整固定步热；默认关闭，不改游戏/参考车参数。定义与依据见[机械定义](mechanical-definition.md)。

T0-r2：389项通过，pytest17.23s，包含解析粘性/饱和极限、三布局正反挡/空挡、柔性/刚性独立机械账及原机制。端口容量、3e−9J能量、1e−10Nms角动量与.001N力残差保持。初两条入口Ruff失败，pytest未跑，原日志保留。

相关控制/JSON/参数164项通过（64.65s），原生split-μ及限滑模块45项通过（17.76s），各有独立T0日志。原生三布局/两模式各180拍，有实际限滑转矩与正热，reset清空累计热、shift保持实体状态；并非完整低附着标准A/B或性能验收。

off-compatibility.py从实际39b3f52 Git源码独立运行；默认后驱两模式240拍全部既有快照字段字节一致，新增字段仅三端口转矩/滑差/热。新转矩/热为零，滑差保留实际观测。首次比较仅LF/CRLF包装差异，逐字段差异为0；修正投影文件行尾后字节核对通过，初失败记录保留。源码执行前后一致，完整新旧轨迹与回执均保留。

reference-v12已实际导出两模式，77车辆字段。当前收口见[回执](completion-receipt.json)。

本块标准A/B为两模式×三布局×五工况×开/关，共60条，每条4s/480个真实120Hz步，逐拍完整输入/快照存于[汇总](limited-standard-r1/summary.json)对应gzip轨迹。工况为分离附着起步、阶跃转向、单轮异步再接触、倒车及发动机制动；仅改变粘性限滑，驱动轴及四驱中差设计阻尼20N·m·s/rad、容量80N·m，TCS双方关闭，ABS/ESC保持。全部完成，力残差最大0.000999577445738N＜.001N。287份源码/测试/工具前后SHA一致；T1在本轮A/B期间运行，之后源码未改变。这里不宣称重跑DRIVE-02的6秒/11工况协议。

| 模式 | 布局 | 分离附着末速 off → on（m/s） |
|---|---|---|
| game | RWD | 0.7235 → 1.4192 |
| game | FWD | 0.6907 → 1.1985 |
| game | AWD | 1.5947 → 4.0791 |
| simulation | RWD | 0.6733 → 1.4253 |
| simulation | FWD | 0.6261 → 1.1803 |
| simulation | AWD | 1.6322 → 4.1371 |

转向与再接触结果并非全面改善，负变化原样保留于回执和轨迹。12条单轮再接触均存在真实单轮不支撑时段，四轮分别重获接触；没有运行中重设车姿或轮速。

真实NPC生命周期6项T0通过（pytest5.17s）：两模式/三布局产生真实热，重定位保持机械状态，原生回收与玩家reset清空限滑累计热和端口矩。日志见validation-T0-lifecycle。相关完整T1为790项通过（pytest143.44s），Ruff及三种子1200步启动全部通过，见validation-T1-r1/summary.json；不再重复全套T2。

研究工具drivetrain_probe支持完整车辆设计JSON，限滑A/B入口为tools/physics/differential_ab.py。执行命令和测试模块记录在对应summary.json；A/B命令：`.venv/Scripts/python.exe tools/physics/differential_ab.py --output docs/evidence/PHYS-DRIVE-03/limited-standard-r1 --duration 4`。

下一PHYS-DRIVE-04实体输入轴惯量/有限换挡同步。DRIVE-01护栏音频失败、SI悬架/防倾、估计器、实车型、研究协议及T2/T3/前台性能/人工驾驶、整体goal继续未完成；本块仅本地提交，未作新推送。

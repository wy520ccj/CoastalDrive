# PHYS-TIRE-04 当前证据

2026-10-03已修正CG扩展工况：旧四Box共同平面接点位于几何底面中心，60%前载时首次接点y=-.22000003m、J6786.65Ns、omegaX=-.777816rad/s，首碰pitch=-.371380°。[旧全轨迹](cg-plane-impact/summary.json)保留。生产现沿CG投影分区，质心投影在车体外则不增加虚构支撑。[生产8条轨迹](cg-production-impact/summary.json)中两模式40/50/60%前载的峰值pitch均小于1e-6°，roll小于4e-6°；外CG工况为两块Box、真实边缘y=-.25m、首碰omegaX约-.87638rad/s并真实倾倒。裸车身试验隔离轮胎与驾驶输入，未设角阻尼。[54项相关T0](../../../logs/validation/PHYS-TIRE-04-cg-partition-T0-v2/summary.json)通过；[新完整T1](validation-T1-cg-receipt.json)7项检查全部通过（696项pytest、Ruff、3条headless、2条hills），[新T2回执](validation-T2-cg-receipt.json)确认全部16项检查通过（811项pytest），266文件SHA一致。

基线为已推送`f2c1450`，冻结src/tools归档`baseline-src.zip`，提取目录不提交。下文矩阵属于修正前分区候选；新默认两模式的完整配置、实际原生形状/半尺寸/margin/transform、惯量、静置位置与轮读数逐项严格相同，见[兼容性回执](cg-default-native-equivalence.json)。该回执支持默认工况复用，不把旧源码SHA改写成新版本；一般CG仍由新增实际轨迹与测试单独覆盖。可见性能和人工驾驶未形成阶段结论。

原CG分区原型的首轮摘要被子代理后续重跑覆盖，无法恢复。覆盖后的文件与明确标记的旧公式重建另存于[重建记录](cg-support-partition-reconstruction/README.md)，不作首轮原始证据。正式修正前基准使用独立保留的`cg-plane-impact/summary.json`，修正后使用新的生产8轨迹、54项T0及原生兼容回执。

## 当前主线：四块原生Box

完整Hull候选T1为674通过、4失败：追尾roll超10°、护栏接点、持续摩擦及声音回归，见`logs/validation/PHYS-TIRE-04-T1-final`。下文带`production-*-final`的Hull矩阵属于该候选历史，不是当前验收结果。[六种原生表示追尾](rear-impact-support/summary.json)显示Box首次正冲量有3个接点、Hull只有1个，之后运动明显分叉；同外廓不等于同碰撞算法。`hull-production-rejected.py`保存被拒绝的实现。

当前采用同一刚体上的零margin原生Box，沿车身局部CG投影切分；默认四块，CG在外廓外时仅切实际经过内部的轴。指定符号旋转使平落地等值支持角点靠近CG投影；仍保留原生Box多点车车/护栏接触。分区的理论并集覆盖完整名义外廓(1.05,2.15,.42)m，无内部圆角凹槽；Panda原生浮点transform读回的微小角误差与接缝SAT穿透保留实测值，不称严格零交叠，原2e-5m几何门槛保持。真实倾斜保留外侧接点与角运动。原Box自动惯量与参考车显式惯量保持，全部碰撞由Bullet求解。通用GJK历史0.04m圆角外边缘改为尖角，属于明确几何迁移。完整63字段/reference-v8与各子体原生transform见[当前参考表](reference-parameters-cg-partition.json)；旧[几何中心分区读回](reference-parameters-box-partition.json)保留。

[几何中心分区短原型](centered-box-prototype/summary.json)为修正前记录：四种子步航向峰值小于9e−6°；追尾roll峰值0.000649°、首次间距4.284645m；持续擦栏662tick、1次撞击，原门槛保持。旧45项T0与新54项T0均保留，外侧实际接触距离2e−5m及分区体积/边界门槛保持。初次内部球探针与超出球半径的探针错误保留。新参数导出按原生Box体积加权中心和真实角点边界读取整体，不用等权平均子体位置，也不以迭代射线误差放宽1e-6m配置测试门槛；[初次失败与命令范围记录](cg-partition-first-checks.json)保存。

音频原Box 8m/s工况继续保留原全部断言。新分区8m/s真实持续接触仍超过600tick，但连续两tick起播压力不足；另用[16m/s真实压力](scrape-pressure-16/summary.json)检验音频，起播实际接触283.007Ns、切向速度14.758m/s。两种表示均要求实际压力连续达到原25Ns/1.6m/s起播门槛、一个hit和一个scrape、真实制动后off；没有改音频阈值。分区对栏产生8点、原Box为4点，两组都逐点验证同一实际17tick冲击、原冲量/速度门槛和一次聚合事件。

## 当前四Box最终矩阵与验收进度

以下仅报告当前四块零margin原生Box及同方程求解优化。旧Hull候选矩阵单列为已拒绝历史，其指标不并入当前矩阵。

- [碰撞A/B](box-partition-collision-ab/summary.json)含44条轨迹、22对同输入比较；[综合审计](box-partition-audit.json)确认20对常规工况所有CSV单元严格0差。两对空中再接触是预期几何差异，游戏首次分叉在tick81，困难仿真在tick80。6秒轨迹由旧Box A到当前四Box B：游戏路径64.122573→64.320160m、峰值航向0.802154→0.00000265°；困难仿真63.493586→64.423920m、0.429362→0.00000873°，当前几何下确有路径变化，并非全矩阵严格0差。审计共49,028行、16,745,574个有限数值，最大记录力残差0.000999143808N；源码各矩阵运行前后SHA一致。
- [再接触矩阵](box-partition-recontact/summary.json)覆盖两模式2/4/8/16子步；[常规子步矩阵](box-partition-tire-substeps/summary.json)覆盖16条2/8子步轨迹。下表同时列出6秒全过程路径与“停止时路径”，后者按首次水平速度低于0.1m/s记录；峰值航向为全过程绝对未绕回航向峰值。

| 模式 | 轮胎子步 | 6秒路径 (m) | 首次低于0.1m/s时路径 (m) | 峰值航向 (°) | 首次低于0.1m/s时刻 (s) |
|---|---:|---:|---:|---:|---:|
| 游戏 | 2 | 64.320160 | 64.259361 | 0.00000265 | 3.94167 |
| 游戏 | 4 | 64.442337 | 64.371788 | 0.00000025 | 3.95000 |
| 游戏 | 8 | 64.510490 | 64.433807 | 0.00000369 | 3.95000 |
| 游戏 | 16 | 64.546425 | 64.466118 | 0.00000372 | 3.95000 |
| 困难仿真 | 2 | 64.423920 | 64.362907 | 0.00000873 | 3.95833 |
| 困难仿真 | 4 | 64.543732 | 64.473167 | 0.00000534 | 3.95833 |
| 困难仿真 | 8 | 64.629845 | 64.553284 | 0.00000574 | 3.96667 |
| 困难仿真 | 16 | 64.668098 | 64.587868 | 0.00000276 | 3.96667 |

2到16子步的6秒全过程路径差为游戏0.22626495m、困难仿真0.24417877m；首次低于0.1m/s时的路径差分别0.2067566m和0.2249603m。两种口径均保留，不将小航向误差解释为严格收敛。
- [功边界与观察器审计](box-partition-recontact-work/summary.json)共172,800轮胎子步。按0.001N力残差推导的逐子步和macro功界越界均为0；负路面功保留，最小−3.0031240e−6J。观察器返回原WheelStep，并对每个既有CSV逐单元核对；8条记录均为`same_unobserved_trace_every_cell=true`，故观察器未改轨迹。
- [刚性关闭对照](box-partition-mechanical-closed/summary.json)以冻结`f2c1450` Box基线为参照，test/coastal/endless各1200tick合计2,871,049个既有值，差异0、最大数值差0。

修正前四Box [T1回执](validation-T1-receipt.json)及[原始summary](../../../logs/validation/PHYS-TIRE-04-box-partition-T1/summary.json)确认7项检查全部通过：Ruff、682项pytest（951.94s）、3条1200步headless及两条30秒hills检查（各109.299/109.664s）。旧T2通过797项pytest与其他12项检查，随后因CG修正停止：hills-17中断、straight-23/hills-23未跑，见[中断回执](validation-T2-box-interruption-receipt.json)。旧原始summary的running状态原样保留，不作通过依据。新CG分区冻结266个Python文件，完整T1的7项检查全部通过（696项pytest）；新完整T2的16项检查全部通过（811项pytest），266文件SHA一致；T3、可见性能及人工驾驶尚未完成。

## 同方程求解效率

局部初值只在同一子步四轮Gauss–Seidel内复用已有Fx/Fy，没有跨tick缓存。原刚性关闭分支仍使用零初值及原差分Newton。暖初值[对照](warm-start-profile-comparison.json)三工况残差评估减少47.5%–52.0%；150项相关T0通过。

解析导数推导见[方程与失败记录](solver-derivation.md)，滚动MF、低速Coulomb与干式制动投影仍为原残差；仅以原方程的解析Jacobian代替四次力差分。首次独立导数检查21通过/1失败，修正静止制动消元符号后22项独立差分及相关142项T0通过。原日志分别保留`jacobian-derivative-t0.log`与`analytic-corrected-t0.log`，不放宽门槛。

[解析导数profile](analytic-profile-comparison.json)保留冷启动、暖初值及解析导数三个版本的独立SHA和实际pstats。相对冷启动三种工况残差评估减少约80%，相对暖初值再减少约60%。源码各运行内稳定、运行间确实有改变；终态差异逐字段记录，不称新旧轨迹严格相同或凭调用数推断FPS。无profile同工况耗时另在`solver-timing/`记录。

[无profile耗时对照](solver-timing/summary.json)三工况各按A B B A顺序运行，每次独立子进程、240tick中性静置后720tick测量。仅计入`_step`，配置与输入一致、源码运行前后稳定。加速/定转/制动的720tick总耗时中位数分别5063.373→3331.427ms、4783.633→3089.703ms、4271.626→3086.074ms，下降34.21%/35.41%/27.75%；两重复范围和所有逐字段差异保留。逐tick最大位置差7.629e−6m、速度差3.815e−6m/s、航向差4.196e−5°，不是严格零差。这是headless物理步耗时，不是可见窗口FPS或性能Gate。

[关闭柔性机械对照](mechanical-closed/summary.json)同冻结f2c1450在test/coastal/endless各1200tick，分别412592、1228773、1229684个既有值，总2,871,049值，数值差与差异数均0。由于冻结基线也已默认启用柔性，本次旧/新两组都显式False，三个电子开关及轮荷特性保持。不同于TIRE-03旧字段数，当前对照包含此前新增的完整变形诊断。

## 再接触定位与当前实现

[既有轨迹审计](recontact-existing-audit.json)与[时点说明](findings.md)把首次大扰动定位到tick80的Bullet完成步；此前左右轮胎与ESC请求对称。[实际manifold与几何对照](findings-manifold.md)保存无限plane、有限box和mesh原始失败及短诊断，全部导入冻结基线，没有调整当前生产几何。plane的右侧单点实际冲量与角运动量级相符；迭代10→80无效。大box有射线法线噪声和单侧miss，不能拿其替代旧工况宣称改善。

[mesh完整6秒](recontact-mesh-full/analysis.json)即使轮射线法线全严格up，也有明显新分支：2/4/8/16子步航向−0.113/−5.243/−10.759/−0.028°，路径65.192/83.659/64.612/65.114m；4/8子步分别出现明显较长后轮离地/偏航。不能用2与16接近跳过中间分支，旧plane限制仍保留。

后续[同世界积分细分](coupled-time-v2/summary.json)首先证明1细分与旧轨迹严格0差，但2/4/8仍不收敛。[原Box精确矩阵旋转](box-support-exact-matrix/summary.json)保持全部角点严格相同，第一次接点与角扰动却反向，确认等值支撑点的表示偏向。[二块](box-halves-full/summary.json)、[四块](box-partition-full/summary.json)、[四块高迭代](box-partition-solver80/summary.json)与[组合细分](coupled-partition/summary.json)均保留，未推广到生产。

被拒绝的Hull候选采用原Box内核与原0.04m margin的26点Hull，冗余面/边中点先于角点；通用GJK支撑函数和圆角实体体积保持，平面等值支撑不再预选一侧。创建时先读原Box自动惯量再保留，两模式实际惯量未变；63字段/reference-v7见[候选历史导出](reference-parameters-final.json)。完整T1实际回归证明还不能作为生产验收结论。

[零margin Hull原型](hull-support-full/summary.json)已弃用；两次射线几何核对失败日志`collision-ray-first-failure.log`、`collision-rounded-ray-failure.log`保留。默认Bullet凸体射线以dist²=1e−4停止，不适合20微米几何核对，当前测试改用原生接触距离对独立圆角Box SDF，原2e−5m门槛保持。[保留margin的冻结源诊断](rounded-support-cache-v2/summary.json)完成全部2/4/8/16；前次`rounded-support-full`在序列化原生射线缓存NaN时失败并保留。后继观察器仅将无接触缓存非有限值保存为原值文字，有效接触仍报错；该次独立重跑实际未再次出现非有限缓存，不声称复现了原NaN。

首次生产Hull自动惯量读回额外增大约4%，因此前两组`production-collision-ab`/`production-recontact`为修正前记录，首次T1被停止。最终结论只用带`final`的矩阵。54项相关T0含三组惯量严格一致、独立真实接触几何、倾斜冲量、生命周期及四子步对称落地，见`logs/validation/PHYS-TIRE-04-inertia-T0`；未用射线精度放宽替代验收。

## 被拒绝的历史Hull候选矩阵（T1拒绝；数值不属于当前结果）

[44条碰撞A/B](production-collision-ab-final/summary.json)完整配置只改变`centered_collision_support`；[只读审计](production-audit.json)确认22对全过程输入一致，其中20对常规试验CSV全部单元严格0差。离地再接触：正常游戏累计航向峰值0.802154→0.000001412°、路径64.122573→65.107414m；困难仿真0.429362→0.000002653°、63.493586→64.287003m。停距增加原样保留。

[两模式8条2/4/8/16](production-recontact-final/summary.json)全部ESC介入为零，航向峰值均小于3e−6°。困难仿真路径64.287003/64.391609/64.467712/64.502174m，游戏65.107414/65.255486/65.337883/65.383644m；相邻差递减，最后两档停车时间一致，保留默认2档与16档约0.215/0.276m路径差，不称严格收敛到相同轨迹。52条CSV共37,492行，12,802,332个数值全部有限，最大所记接触残差0.000999892419N，原门槛0.001N未变。

[最终历史机械分支](mechanical-closed-final-v2/summary.json)显式柔性False、原Box，与f2c1450三场景共2,871,049既有值严格0差。[16条常规2/8子步](production-tire-substeps/summary.json)另存完整轨迹。该Hull候选因T1失败而拒绝；当前四Box的T1/T2状态见上节，可见性能与人工驾驶仍属于整体Gate。

[最终再接触完整子步功审计](production-recontact-work/summary.json)保留172,800个轮胎子步。两模式全部2/4/8/16在原0.001N接触残差对应的滚动/静摩擦功误差界内，逐子步及macro求和均0越界；最大所记残差0.000999892419N，负功未钳制。每条观察器CSV与`production-recontact-final`全部单元严格一致，运行前后源码稳定。

停止首次T1的[独立记录](t1-interruption.json)说明其原summary未执行结束器而保留running，不是完成或通过。最终验收使用后继目录，原日志不覆盖。

## 接手期间的下一机制准备

当前T2源码冻结期间新增[机械轮轴与联合反力推导](rotor-joint-findings.md)：20组共同末状态机械核对、45组接触点虚功和12条实际无外力Bullet轨迹均保存原始数据与各版本源码。生产/测试/工具266文件SHA未变。这些结果是[PHYS-ROT-01](../../tasks/PHYS-ROT-01.md)准备，不算当前04新增驾驶功能或下一块生产验收；发动机/离合/差速器在轮轴与反力接入后继续推进。

## 算法依据

本机Panda3D1.10.16/Bullet2.84。对应[Panda世界构造](https://raw.githubusercontent.com/panda3d/panda3d/v1.10.16/panda/src/bullet/bulletWorld.cxx)在构造时读取solver iterations与split impulse配置；当前值为10/False。诊断使用独立子进程设置80，没有修改全局生产默认。

[Bullet2.84凸体-平面算法](https://raw.githubusercontent.com/bulletphysics/bullet3/2.84/src/BulletCollision/CollisionDispatch/btConvexPlaneCollisionAlgorithm.cpp)以支持顶点生成接触，可通过额外扰动生成多点；这与首帧单点观测相符。[刚体步顺序](https://raw.githubusercontent.com/bulletphysics/bullet3/2.84/src/BulletDynamics/Dynamics/btDiscreteDynamicsWorld.cpp)先处理约束、积分变换，再更新vehicle action；[射线车辆](https://raw.githubusercontent.com/bulletphysics/bullet3/2.84/src/BulletDynamics/Vehicle/btRaycastVehicle.cpp)在action中施加悬架冲量。源码结构支持把微小轮胎差异、真实车身冲量和后续接触反馈分开分析；最终因果与精度结论仍须对应原始实际轨迹。

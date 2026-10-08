# PHYS-PERF-01 真实物理性能收口

## 2026-10-08持续低帧优化施工

- 用户授权全力优化，并明确允许微小浮点差异；物理方程、硬件参数、120Hz、原20/30轮上限与全部收敛精度保持。现行验收以轨迹、能量和碰撞为准，不再强制所有浮点字段逐位相同。
- 基线main `cf1316dbd5db59c67e48fb809b4af16b40033158`；当前未提交修改，仅主目录单线施工，未推送。源码/原DLL已冻结在`logs/performance/optimize-20261008/baseline-src`。
- 已实施：连续GJK原生循环；良态双列补偿投影/近共线SVD；同advance相同末速度与法向投影复用；真实静态几何变更检测及原生分区数组；覆盖盒内静态查询直接返回数值接点；有限边解析导数/保守区间Newton；停滞端口的提前解析Newton；四轮法向响应整块计算。候选/形状顺序、有限网格、动态外部变换读取及唯一世界保持。
- 1024组初版几何逐值一致。2048组独立旧DLL边投影对照：正距离最大距离/法线/见证点差为6.66e-16m/1.11e-12/5.55e-16m，局部ABBA约0.030/0.008/0.010/0.030s。零距离内部见证点和法线并非唯一，初版不加区分的比较失败保留。九车128拍加速/转向/制动对照仅6个浮点字段改变，最大2.36e-16，全部位置/速度/姿态及事件相同；不把短测墙钟当FPS。
- 较早的共同Newton、暖GJK、Anderson试验未保留，没有稳定整车收益；文件/失败/计时留在上述logs目录。基线既有prepare观测包装三/四参数TypeError仅修包装，原全部1e-4几何门槛保持；完整vehicle回归的超时、旧细化失败和后续相关T1结果见下方检查点。当前没有实时性能通过结论。

2026-10-08已验证检查点：追加静态三角法线、边角扫掠与四轮机械基的批量C计算；同不可变几何包内持久候选复用，真实变更/越界即重查；末子步不再做无人使用的外推，试探反力不再重复能量报告；共同端口暖索引仍每次校验真实可行性。P核旧/新ABBA物理100.05→59.46ms，最终单次九车57.38ms、单车6.80ms，不能作FPS。四场景各128拍位置/速度/姿态/事件相同；参考车最大字段差1.46e-11。1024反力、2048机械几何逐值hex相同。最终514项相关T1/Ruff/三种子通过，较早605/452项不相加。

完整车辆T1-r1在600s超时，1315通过/1旧观测接口失败；修正该接口后1节点通过；剩余427节点426通过/1旧对称断言失败。补齐全部轴的对称设置后偏航/ESC/停车通过，但细化单调仍失败，独立旧源码相同；原门槛保持。最终碰撞模块28通过/上述1节点明确排除，整个车辆T1不记通过。两次测试路径错误/pytest未执行、超时及旧失败均留档。此前有效前台1080p/GR86+8车30秒实测1.768显示FPS，测量段丢时23.842秒，未达实时预算；该窗口测量在最后三个小块之前，声音关闭。暖法向、滞后几何和共同解memo也未保留，没有稳定大收益。

剩余重点是完整数值求解入口和串行车辆计算。下一范围：先将有限轮胎推进拆成读取、纯数值、按原顺序提交，再验证同世界冻结几何的数值序列并行；唯一Bullet世界、120Hz、全部车辆/机制和原精度必须保持，不用普通线程绕过GIL、不降低NPC精度。尚未实施并行。当前改动不能宣称游戏已经流畅，任务in_progress，产品包/T3/人工待办。[检查点源/证据](../evidence/PHYS-PERF-01/optimize-r1/README.md)。

- 状态：in_progress；当前主施工目录为main，本批五个关联原生数值块、窗口车型选择及r10候选包自动检查完成。
- 本批基线：6d58e9a；验证/建包时是其上的未提交修改，实现提交4639cf8；2026-10-08用户授权提交并推送当前main累计成果，远端发布以Git核对为准。现行证据为joint-native-r1、brake-correction-r1及package-r10；完整T2/T3、前台性能与人工驾驶仍未完成。
- 范围：减少同一机械子步内重复的几何与代数计算，再接产品/试玩包和最终Gate。

2026-10-08连续施工批次：loaded_wheel_force_solution直接读取当前轮荷后调用原局部求根；wheel_residuals合并四轮同末状态残差；suspension_residuals合并反力与六维几何冲量残差；原生二维norm使用CPython 3.14.2 vector_norm的缩放、补偿平方与微分校正；wheel_brake_correction合并当前端口分区导数、四轮矩阵和制动增量消元。旧八维物理机制保持。norm原始来源为[CPython官方源码](https://github.com/python/cpython/blob/v3.14.2/Modules/mathmodule.c)，许可沿用licenses/CPython-LICENSE.txt。

相关验收按功能组执行：前三块548项T0通过；最终norm100196组IEEE/随机探针与math.hypot hex相同。独立6d58e9a Python/旧DLL先后完成804完整推进（36台架、真实落地、海岸玩家+8NPC），最终所有字段hex/世界引用一致，11024局部入口、2805轮端残差、2709悬架残差；追加制动块3111次每调用与原Python端口/矩阵/消元hex相同。最终合并T1首轮699通过/1旧shared_solution观测入口AttributeError，三seed未跑；只把Jacobian测试接到实际wheel_map/shared_load_solution，原16样本和2e-6门槛保持。r2只跑失败节点（1通过）、Ruff及0/17/23各1200拍启动通过，其余699复用。原None回调TypeError、窗口车型CLI初轮11通过/2旧限制失败和两节点修正通过均归档，不抹掉失败。

本批只做了一次合并热点诊断：海岸GR86+8NPC预热8/采样16拍，完整完成、源SHA前后相同；带profiler2.6033秒用于定位，不能当FPS。主要余项为同世界真实静态shape变换读取、有限支持面射线与边/角查询。制动修正迁移由此继续推进，未再为该块重复profile/48拍/种子。

产品接通：窗口--vehicle-design明确选择对应可选车型，同硬件保留当前外观；没有改变玩家保存文件。r9已验证后继续加入制动块并构建r10，29.451秒成功，构建输入前后相同、两原生模块逐字节一致。仓库外GR86 Game/Simulation各120拍成功；test track零交通离屏渲染及各20次节点/task/event重启稳定，截图已目视。入口见[正常游戏](../../launchers/physics-r10-game.cmd)、[困难仿真](../../launchers/physics-r10-simulation.cmd)，构建包不替换根试玩.cmd。机械/测试、格式字节链及首次失败见[joint-native-r1](../evidence/PHYS-PERF-01/joint-native-r1/receipt.json)、[制动/T1](../evidence/PHYS-PERF-01/brake-correction-r1/receipt.json)；当前包见[package-r10](../evidence/PHYS-PERF-01/package-r10/receipt.json)。r9仅代表制动前版本，保留其原证据。

下一沿有限支持面真实几何读取/对象装配继续推进，按关联功能组统一对照和收口。T2旧落地失败的长阶段及11专项仍未完整复跑，T3、前台性能和两模式人工驾驶仍待完成。

Simulation保持唯一权威世界、120Hz和现有物理子步。硬件参数、本构律、20/30轮上限和原残差要求保持；NPC执行共同物理。优化按实际profile定位，不以改变碰撞、控制请求或更新频率换取性能。

首份诊断为logs/physics/PHYS-PERF-01/profile-r1：GR86玩家与8辆NPC、coastal、种子17，无窗口/估计器，8拍预热与16拍cProfile。源码前后SHA一致、24拍完整执行；预热2.001s，带profiler91.559s。采样短且与主目录T2同时运行，只用于定位调用，不能当作FPS或前台Gate。热点是shared重复端口分区求解、known重复四轮力投影，以及TriangleSupport真实有限面查询。

先保存相同输入的完整Snapshot与局部矩/能量账。按2026-10-08用户指示，后续按功能组做一次必要旧/新对照和相关短检查；不为每个小块重复完整T1/种子/48拍/profile，已有有效证据按版本与范围复用。最终前台1080p中画质8车，30秒预热/5分钟采样、平均≥60FPS且P95≤25ms；T3、试玩包、两模式人工驾驶保持待办。

2026-10-08按用户授权正常推送origin/main；历史段落的未推送描述保留对应施工时点。当前没有前台性能通过结论。

首个复用功能块完成：同一shared求根保存四轮/法向常量投影，道路生成时保存原三角面AABB，端口容量/损失条件提前排除，WorldSurface只在当前prepare子步缓存完全相同射线。下一prepare对象重新创建，真实移动支持面回归通过。120Hz/子步/20和30轮/全部精度保持，98硬件字段未改。

基线0afe6b1的单车/玩家加8辆NPC，各48拍完整Snapshot与最终复用版逐字段相同。耗时4.644→3.074s、50.961→34.143s，短测分别下降33.81/33.00%，与主目录T2并行，只作诊断；不是FPS结论。相关172/161/76项T0及最终479项T1/Ruff、三种子1200拍38.6/38.4/38.0s通过。[原始快照、SHA、profile和T1凭据](../evidence/PHYS-PERF-01/reuse-r1/receipt.json)。

解析导数准备：第一版只覆盖无TBR实体轴，48拍未触发适用Newton分支，临时报表空列表max失败保留，不作导数通过结论。扩展负载偏置的11维内存试验，64个实际Newton点与独立中心差分最大相对差1.15e-10，同两条完整Snapshot仍相同，九车短测28.018s；当前尚未接入生产。下一接解析导数并检查有限轴/正倒挡/同步/限滑的机械账，随后继续性能优化及产品收口。

解析导数功能块完成：实体轴共同状态使用当前机械活动分区的精确导数，包含S(q)×Ω、低速滚阻斜率、输出/前后轴储能反力及负载TBR容量；旧八维对照仍用原差分。只替换Newton矩阵计算，原方程、步长搜索、30轮与角速/端口精度保持。新原生16点独立差分回归通过；467项机械T0和最终495项T1/Ruff、三种子1200拍37.0/37.4/37.0s通过，包含传感器与直接实验生命周期。顺便修正新增TBR外部配置的维数检查次序，错误长度返回ValueError而非IndexError，合法98字段不变。

与0afe6b1的48拍完整快照仍逐字段相同，单车4.644→2.407s、九车50.961→27.258s，分别短测下降48.16/46.51%。[完整输入/快照/导数/T1/SHA](../evidence/PHYS-PERF-01/jacobian-r1/receipt.json)。首轮复用已本地aa4368c，GR86标定归档a0c644e，未推送。下一原生小矩阵探针只在logs内编译并比较，尚未改生产依赖；前台/T3/试玩包/人工Gate仍未完成。

原生加速归档（2026-10-07）：[native-r1报告](../evidence/PHYS-PERF-01/native-r1/native-report.md)、[原始/压缩件清单](../evidence/PHYS-PERF-01/native-r1/archive-manifest.json)及[源码哈希链](../evidence/PHYS-PERF-01/native-r1/source-hash-chain.json)记录48拍全Snapshot逐字段相同，单车/8车短测分别下降64.17%/61.27%。原生T0-r1/r2的Ruff失败及未运行测试、r3的510项通过、projection T0的546项、最终T1的511项和三种子结果、旧版920项边界均保留。Profile墙钟仅作诊断；包r3仅为projection前headless证据，渲染未通过/超时，未重跑。源码SHA捕获从70d8b94工作树的未提交状态开始，`.c`/`.pyd`及所有`src` Python哈希的开始/结束值见链文件；本次未运行测试、模拟或渲染。前台性能、最终产品包、T3和人工驾驶Gate仍待完成。

静态候选表面复用归档（2026-10-07）：[报告](../evidence/PHYS-PERF-01/candidates-r1/candidate-report.md)、[逐件SHA与gzip校验收据](../evidence/PHYS-PERF-01/candidates-r1/receipt.json)、[源码SHA](../evidence/PHYS-PERF-01/candidates-r1/source-hashes.json)。基于7850870未提交工作树，单车/九车48拍完整Snapshot与之前native projection逐字段相同，短测1.664→1.558s/19.738→17.981s（6.35%/8.90%，非FPS）。5cm候选覆盖范围外重查、同射线缓存及每prepare失效，最终仍做实际表面求交；T0 27项通过，首轮T1路径错误未收集测试且种子未运行，T1-r2 442项/Ruff/三种子通过。主目录T2-r11运行中，尚未合并/推送；前台、T3、产品包及人工体验待完成。本次仅归档，无测试/模拟/构建/渲染。

轮胎支撑面原生内核归档（2026-10-07）：[报告](../evidence/PHYS-PERF-01/wheel-native-r1/wheel-native-report.md)、[文件与payload校验收据](../evidence/PHYS-PERF-01/wheel-native-r1/receipt.json)、[PY/C/PYD哈希及许可证来源](../evidence/PHYS-PERF-01/wheel-native-r1/source-hashes.json)。基线15457d7加未提交轮胎内核；正式48拍全Snapshot与0afe6b1、候选缓存版、face内存版均相同。生产版单车/8车1.47169/16.16178s仅短测非FPS。归档保留完整production/Python/setup/许可证点时源码、2058 exact探针、face与production快照、profile和T0/T1证据；对应face/production的原型明确为冻结support-kernel-r2.c（SHA-256 566843f68519b4d3c1b235321ce63604823f320ed1c6f36bee88b997707e9db0），不包含后续r3点/边实验；T0初次Ruff失败/pytest未跑及后续通过边界均照summary记录。未合并/推送；最终包、T3、前台和人工Gate待完成。本次未运行构建、测试、模拟或渲染。

点/边驻点原生内核归档（2026-10-07）：[报告](../evidence/PHYS-PERF-01/edge-native-r1/edge-native-report.md)、[逐件SHA与包/验证收据](../evidence/PHYS-PERF-01/edge-native-r1/receipt.json)、[源码哈希与工作树捕获](../evidence/PHYS-PERF-01/edge-native-r1/source-hashes.json)。基线8be0a50加未提交轮胎内核；r3原型已冻结，SHA abf34ff96a3d1a1b65e0e6e308c3b1e3925eb2912bd981a2a4edfd843b8dd7b2，点/边1024次exact。正式48拍全Snapshot与0afe、wheel及edge内存版一致；单车1.4763s（略慢于wheel 1.4717s），九车14.1951s（wheel 16.1618s），均仅短测非FPS。edge T0 94项、T1 460项及三种子通过；独立r4包两模式120拍headless通过但非render/性能/人工Gate。主目录T2-r11仍运行18,000拍节点；未合并/推送。此次仅归档，未运行构建/测试/模拟/渲染。


2026-10-07后续状态：主目录T2-r11已实际32通过/1高速车流求解失败（2436.80s），原后14检查未跑，阶段未关闭；正在保存最小失败子步。上述edge归档“仍在跑”描述为捕获时点，不能当作当前状态。下一性能LU仅在logs内试验，512矩阵与19,798个真实8/11维求解调用逐值相同，两条完整Snapshot相同；尚未接入正式源。先处理实际物理失败，再继续产品/性能收口。

静态形状边界候选复用归档（2026-10-07）：[报告](../evidence/PHYS-PERF-01/bounds-r1/bounds-report.md)、[SHA/payload收据](../evidence/PHYS-PERF-01/bounds-r1/receipt.json)、[源码哈希与状态](../evidence/PHYS-PERF-01/bounds-r1/source-audit.json)。HEAD 983e978加未提交修改。健康48拍快照一致；九车edge→全扫描→cache→shared→window为14.195→42.162→32.879→28.317→16.536s，单车window 1.7867s仍慢于edge 1.4763s，均短测非FPS。最终474项T1及种子23.299/22.973/23.116s通过；50项cache T1是历史中间版，非额外最终覆盖。profile来自shared阶段，不代表window。主目录失败根因证据仅链接至 [shape-bounds-r1](<B:/AI agent/暑期计算机程序设计/CoastalDrive/docs/evidence/PHYS-DESIGN-01/shape-bounds-r1/shape-bounds-report.md>)。无新包/前台/T3/人工Gate；完整T2尚未恢复，本次仅归档，未运行测试/模拟/构建。

2026-10-07精度保持的小矩阵LU已原生化，基线b2501d2；512组合成矩阵和此前19,798真实调用逐值相同，健康两条48拍完整Snapshot相同。最终474项T1/Ruff及三种子通过；初轮Ruff失败、测试未跑保留。九车16.536→15.998s仅短测约3.26%收益，非FPS。最新profile候选查询2.69s，下一复用同查询内重复变换。[证据](../evidence/PHYS-PERF-01/lu-r4/README.md)。主目录已本地33657dc整合至b2501d2，当前隔离LU尚未合并，T2/包/T3/前台/人工继续。

候选旋转投影复用功能块完成：覆盖盒相同frame的中心和半宽只算一次，实际平移/边界/精确求交保持。31项T0、474项T1/Ruff、三种子通过，单/九车完整48拍快照相同；1.721→1.565s、15.998→14.424s仅短测9%左右收益，非FPS。[归档](../evidence/PHYS-PERF-01/projections-r1/README.md)。主目录33657dc新版T2复用474同源码节点，补1656节点/14专项，首先重跑真实高速18000拍失败；隔离继续精度保持的几何内核优化。

支持面几何循环原生块完成：坐标变换、包围盒区间、有限转动共轭路径共3584组与原函数逐值相同；相关100项T0、最终474项T1/Ruff/三种子通过。健康48拍完整快照相同，九车14.424→13.030s仅短测。未减少子步/机械迭代或精度。[证据](../evidence/PHYS-PERF-01/geometry-r1/README.md)。主目录T2仍独立33657dc，隔离继续原顺序三角面候选遍历优化。

三角面索引C遍历试验未保留：1024候选原引用/顺序相同，100项T0/474项T1通过，但真实九车历史21.196s及同进程交替18.212/18.538/20.766/21.988s没有稳定整车收益。初两次快照差异仅新Simulation根生命周期编号，物理48拍相同，完整失败及第三次对照归档。已只将自己本次改的两个生产文件还原586bdf8并重新编译，不把试验通过项记当前新增覆盖。[试验档案](../evidence/PHYS-PERF-01/triangle-traversal-experiment/README.md)。下一机械逆惯量/转子与力投影热点。


机械小矩阵块归档（2026-10-07）：[报告](../evidence/PHYS-PERF-01/mechanical-block-r1/mechanical-block-report.md)、[清单与快照/T1收据](../evidence/PHYS-PERF-01/mechanical-block-r1/receipt.json)、[PY/C/PYD源码起止哈希](../evidence/PHYS-PERF-01/mechanical-block-r1/source-hashes.json)。基线 e79af19 + 未提交 `src/mechanical_kernels.c`/`src/tire_drivetrain.py`；2304 mass_response、768 rotor_spin、1280 wheel_load_terms exact 调用通过。48拍单/8车快照与先前机械块/geometry逐字段相同；同进程ABBA四条物理快照相同，contact_epoch复位为0。短测wall/CPU四条按原顺序保存，存在漂移，不称FPS。机械块T0 339项、mass-spin T0 583项及T1 Ruff/722 pytest/三种子均通过；原始summary、日志和gzip(mtime=0)快照均归档。本次只存既有证据，没有重跑。主目录33657dc另行记账；最终T2、产品包、T3、前台和人工Gate未完成。


系数Capsule缓存块归档（2026-10-07）：[报告](../evidence/PHYS-PERF-01/coefficients-r1/coefficients-report.md)、[快照/验证SHA收据](../evidence/PHYS-PERF-01/coefficients-r1/receipt.json)、[354项PY/C/PYD起止哈希](../evidence/PHYS-PERF-01/coefficients-r1/source-hashes.json)。基线fe8bcd3 + 未提交 `src/mechanical_kernels.c`/`src/tire_drivetrain.py`。最终系数块单/8车48拍完整物理快照与机械块一致；最终短测1.2528664/12.0986585s，历史机械块1.4912125/21.2201878s有条件漂移，不称稳定比例/FPS；mass-only中间版独立保留且不作最终值。三类Capsule仅缓存advance数值系数并逐子步重建，动态输入按次传入，单次/缓存共享内核。最终T0 372项、T1 722项/Ruff及三种子通过；初次T0 Ruff失败/pytest未跑与T0-r2通过原样保留。package-r5尚在构建，未归档。主目录33657dc T2独立记账，最终包/T3/前台/人工未完成。本次仅归档，无验证运行。


2026-10-07当前收口：LU5154805、覆盖盒投影11c7c07、局部几何586bdf8、机械投影fe8bcd3与固定系数16a7c4a已本地提交。三角遍历C实验未保留，源码已恢复，失败和不利计时见e79af19。固定系数最终722项T1/三种子通过，单/九车48拍1.2529/12.0987s，完整快照与此前正确几何版本一致；同机短测波动明显，不作FPS推断。r5两模式仓库外headless各120拍通过，见[包证据](../evidence/PHYS-PERF-01/package-r5/receipt.json)。

端口有序活动分区构造已迁入同一原生模块：1,152组矩阵/容量/效率的所有值、顺序和逆矩阵对象复用关系一致；单/九车48拍完整快照一致；同进程Python/C/C/Python四条物理快照一致但整车计时没有稳定收益。最新实际profile同4320次构造1.0232→0.0286s，带profiler总13.6184→12.4856s仅定位证据。最终相关626项T1、Ruff与三种子1200步通过；先前错误测试路径以及重复--tests使T0-r2/T1分别只覆盖末模块1/4项的有限结果保留，不能累计作完整覆盖。下一处理实际形状覆盖盒的批量筛选，保持原三角面窗口、求交、步频与精度。主目录18,000拍旧失败长轨迹已通过，完整阶段仍运行；T3/前台/人工Gate待完成。



批量实际形状覆盖盒筛选自动功能块完成：保留每分组/每形状原顺序，原三项补偿投影、平移、真实bounds比较直接进入轮胎原生模块；有界形状、无限平面、支持面/其他原生凸体资格保持，三角面窗口与实际求交仍走原方法，不保留C三角遍历实验。512查询×240分区全部投影/候选一致，原微测Python/C约0.116/0.013s，仅核验计算块。单/九车48拍完整Snapshot相同，短测1.1914/13.3207s；时序波动保留，不作稳定FPS或整车改善结论。最终474项T1(57.89s)、Ruff及三种子1200步18.3/18.3/19.3s通过，profile16拍计数保持、prepare1.83→0.76s。下一将原转子陀螺、逆质量响应、滚阻与法向加载的共同自由状态组合在一次原生调用中，仍使用原公式与相同舍入次序。


共同自由状态组合功能块完成：原mass_response与rotor_spin只提取一个数值函数，既有接口及新组合调用共用；分别保留陀螺、当前轮端力、滚阻、法向加载的原加法次序，实际平动速度对象直接沿用loads。768种组合覆盖8/9维、转子、实体轴、悬架、滚阻、不同量级逐值/hex一致；2304质量响应/768转子调用仍与e79原Python公式一致。单/九车48拍全部Snapshot一致，短测1.0784/12.1305s；新版16拍带profiler10.6488s只能定位，不作FPS结论。最终626项T1(91.70s)、Ruff及三种子17.5/17.6/16.3s通过。下一完整活动分区映射：将原9/11维mapped中的滚阻/TBR容量、限滑投影与离合/齿轮端口作为一块数值计算；原30轮/解析Jacobian/线搜索/ULP与1e-11端口阈值保持，8维旧对照机制保留。系数只属于当前advance_drivetrain，结果仍直接写回原唯一末状态。


完整活动分区映射与解析导数自动功能块完成：本advance的固定数值分区保存于只读原生系数中，状态、当前轮荷/支撑及法向载荷逐次传入；原滚阻/TBR轴载、限滑投影、离合/齿轮/同步可行性与分区顺序直接移植，旧端口入口与共同映射共用同一shaft判据；8维旧对照保留原机制。30轮、线搜索8次、ULP角速与1e-11端口精度不变。实际83项台架/原生探针逐值对照160,010个mapped和9,289个Jacobian，含156,276挂挡/3,734同步、156,776九维/3,234十一维；末状态与分区索引/滚阻/容量完全相同。初探针漏旧函数导入导致44失败/39通过，修的是测量脚本，记录保留；生产T0两版各418通过。最终单/九车48拍快照与f4a5ae0一致，短测0.9849/11.4810s；profile总体10.6488→11.0005s略慢，shared本函数2.4390→1.2023s，不作整车稳定收益/FPS结论。最终626项T1(90.97s)、Ruff/三种子16.0/15.2/16.4s通过。证据[shared-map-r1](../evidence/PHYS-PERF-01/shared-map-r1/receipt.json)。下一实际有限三角面整条查询的数据转换/遍历/首个接点归约，保留原边/角凸体距离回调，不恢复此前独立C遍历实验。主目录完整T2仍在原33657dc运行，未修改其冻结源码。


完整有限三角面查询自动功能块完成：原box_interval与triangle_face提取一个数值函数，公开入口及完整查询共用；原候选索引顺序、先有限面后边角、首接点及动态ceiling保持，边角仍回原triangle_entry/64扫掠/96GJK。13项台架及真实九车24拍审计54,821次查询、15,774次接点与f44旧完整入口逐值相同。单/九车48拍Snapshot一致，短测0.9656/10.4589s，profile16拍9.1704s仍仅诊断。31项T0、474项T1(69.01s)、Ruff/三种子19.5/18.4/16.6s通过，见[完整证据](../evidence/PHYS-PERF-01/triangle-query-r1/receipt.json)。验证源曾多一个EOF空行，档案保留原样；提交前只移除该空行，strip后完整C源码字节相同，哈希链单独记录，未改变已测内核或重跑测试。下一有限面裁剪与几何差量的原数值内核。主目录33657dc完整T2继续运行；阶段/实时性能/人工Gate未完成。


有限面裁剪/几何差量自动功能块完成：原六个平面、裁剪顶点顺序、未变顶点对象及fma交点保持；差量仍逐元素使用原数值类型，并保持zip左/右取值和提前结束，不强行转换成double。1,024裁剪值/hex/对象身份与128差量值/类型/剩余迭代器一致；单/九车48拍Snapshot一致，短测0.9281/9.6941s。初T0只报Ruff导入格式错误/pytest未跑；修正后31项T0与474项T1(55.33s)、Ruff及三种子17.1/16.6/16.6s通过，见[证据](../evidence/PHYS-PERF-01/clipped-geometry-r1/receipt.json)。profile16拍7.6380s仍只定位。下一九维轮胎局部末状态：同一轮力试探、限滑分区、真实离合/同步/制动端口、平动末速度作为一块数值计算，保留每个尝试分区的暖模式更新与原阈值。主目录T2当前仍在endless八车3600拍变换缓存检查，已越过其2,497拍；阶段未完成。


轮胎局部末状态自动功能块完成：本子步保存固定轮力/制动端口系数，共同与局部映射共用原限滑投影、端口可行性与分区判据；试探力、当前TBR容量和真实末方向逐次传入。每次尝试仍直接更新原暖模式list，旧八维对照机制保留；没有改20/30轮或任何残差阈值。实际83项台架审计217,053次局部映射（挂挡210,407、同步6,646），末状态/制动/全部暖模式相同，含7,721次多分区尝试。最终626项T1(73.2s)、Ruff及三种子13.9/13.6/15.0s通过；T0-r2因移除旧分支后的未用导入/变量Ruff失败、pytest未跑，r3已通过。单/九车48拍Snapshot与105d849相同，短测0.8346/8.1024s；快照后只调整C helper缩进并重建，最终T1/profile对重建版，哈希差别单列。profile16拍6.5905s仅诊断。[完整证据](../evidence/PHYS-PERF-01/wheel-map-r1/receipt.json)。主目录T2仍保持33657dc；下一真实支持面射线变换/有序接点装配，原Triangle/Box/Plane与原生其他形状求交保持。


支持面射线变换/接点装配自动功能块完成：CylinderSurface和RayContact仍为原对象，实际entry、Triangle/Box/Plane、其他形状原生扫掠、候选/首hit顺序不变；原reach平方和仍由Python计算，只合并三维变换与装配，公开变换与新块共用一份数值函数。40项台架及真实九车24拍审计15,148条射线、59,361支持面、15,894接点（mesh54,820/plane59/box4,482），全部字段及node/triangles引用相同。40项T0和最终474项T1(51.0s)、Ruff/三种子15.9/14.5/14.8s通过；源初构建的list接口宏在任何运行前已修，不记未验证版通过。两48拍Snapshot与轮胎局部块相同，短测0.8262/8.1057s，九车略慢于8.1024s；profile16拍6.5905→6.0972s、cylinder_rays1.8343→1.3904s只作热点证据。[归档](../evidence/PHYS-PERF-01/surface-ray-r1/receipt.json)。下一实际圆柱末接点与有限运动功共轭计算，查询仍回原唯一世界；主项目33657dc完整T2继续，阶段/实时/人工Gate未完成。


有限圆柱末接点数值块完成：原真实世界relative_entry和跨有限面face_extension_difference仍回原函数；同平面/Gonzalez公式、胎冠割线与有限转动直接复用一个C数值实现。4,096割线hex、20,792实际末接点、256无接触/反向/跨面分支逐值相同；89项T0、474项T1/Ruff/三种子14.5/13.2/13.7s通过。首移植脚本名错误在写源前失败，首T0未用导入Ruff失败/pytest未跑均保留。单/九车48拍全部Snapshot相同，短测0.7980/7.1059s，profile16拍5.5928s只定位。证据[endpoint-r1](../evidence/PHYS-PERF-01/endpoint-r1/receipt.json)。main33657dc完整T2已523通过/1检查点初始子步失败，14专项未跑，完整阶段未通过；该失败由主施工线复现处理，性能块不冒充修复。最终包/T3/前台/人工仍待完成。


主目录第二批整合到a2e6975：784项T1/Ruff/三seed通过，主/隔离两48拍全部Snapshot相同，短测0.8272/6.3367s仅诊断。r6候选包本地构建35.249s、源前后SHA一致，仓库外GR86两模式各120拍2.066/1.694s通过；未替代默认包。1080p/GR86+8NPC实际30秒短测31.169s墙钟、丢仿真25.225s、行进0.349m/0碰撞；后段foregroundFalse，整段.7085FPS/P95 1832ms不能作为有效前台测值，未通过实时性能。截图实际已目视核验，非人工驾驶Gate。[整合/包/可见诊断](../evidence/PHYS-PERF-01/integration-r2/receipt.json)。完整T2目前25通过/1中心完全重叠NPC计数夹具失败，后11未跑；夹具修正生产源保持，阶段继续。

联合14变量Newton及子步内Broyden雅可比试验仅在logs独立进程进行：48拍两场景完成但Snapshot不逐字段相同，短测Newton1.357/17.475s、Broyden1.552/19.037s，比正式0.798/7.106s更慢；不接入生产，不记理论/性能/机械Gate通过。首Broyden生成脚本缩进使未收集完14列时构造矩阵而IndexError，修正后第二次才有有效速度样本，原失败保留。下一从实际profile处理有限支持面查询与数值对象装配，不靠缩减物理步频或残差要求换帧率。
拒绝的两项候选算法实验（2026-10-07）：[子步14变量联合Newton / Broyden实验](../evidence/PHYS-PERF-01/coupled-correction-experiment/receipt.json)均未接入生产；单/8车48拍完整Snapshot不与端点基线逐字段相同，短测Newton为1.3569/17.4754s、Broyden为1.5520/19.0373s，显著慢于基线0.7980/7.1059s；Broyden首轮IndexError及修正后r2均保留。[支持面root AABB提前筛选实验](../evidence/PHYS-PERF-01/surface-prefilter-experiment/receipt.json)标准快照与基线相同，但短测0.9699/11.6376s更慢；同进程old/new/new/old完整Snapshot断言失败，原快照未保存，原因未知。正式T0为31项通过（调用审计日志另有独立40项记录）；无T1或机械/能量Gate，两项均拒绝且未进入生产。


悬架活动集状态块（2026-10-07）：[证据与收据](../evidence/PHYS-PERF-01/suspension-state-r1/receipt.json)。原64轮/1e-10接触间隙/1e-7反力门槛、LU与能量账保持；d3859f8基线5,757次完整SuspensionStep字段一致，另以独立512次LU探针补足基线审计调用当前LU的边界。单/8车各48拍Snapshot与端点基线相同，短测0.7375/6.4815s仅诊断。T0-r1/r2 Ruff未用导入失败，r3为411 passed；T1为496 passed、Ruff及三种子通过。无FPS或前台Gate结论。


圆柱查询前置数值实验（2026-10-07，拒绝）：[证据与收据](../evidence/PHYS-PERF-01/cylinder-query-experiment/receipt.json)。8,518次调用/10,012条射线的数值与输入别名一致，T0为31项/Ruff通过；标准单/8车48拍Snapshot与悬架基线相同。ABBA四条完整Snapshot均相同且epoch归零，但新旧CPU时间分别为6.609/6.219与5.953/6.672s，无稳定节省，未运行T1。无性能Gate结论；生产源码恢复至e5765ed字节。


主目录整合 r3（2026-10-07，`127c1d0`）：接入 map160 共同接触修正与隔离悬架活动集数值块，严格重建两扩展。T1 528 passed/Ruff/三种子通过；r7候选包 build 哈希前后相同，独立包 game/simulation 各120拍通过，包产物哈希与当前目录相符；reader 首轮日志追加假设错误、simulation未运行已单独保留，r7-r2两模式复核通过。48拍全快照字段与整合基线相同（耗时仅诊断）。复用957节点，余1173与11专项；T2起始摘要标记running，未归档进行中的pytest日志，阶段未过。源码差异清单、旧轨迹失效边界和包/源SHA见[整合 r3 证据](../evidence/PHYS-PERF-01/integration-r3/report.md)。实时前台、T3、人工驾驶验收未完成。


主目录T2-r2失败归档（2026-10-08）：[报告](../evidence/PHYS-PERF-01/stage-collision-r1/report.md)、[summary及收据](../evidence/PHYS-PERF-01/stage-collision-r1/receipt.json)、[355项源码SHA与归档清单](../evidence/PHYS-PERF-01/stage-collision-r1/manifest.json)。固定主目录结果为Ruff通过、pytest 267通过/1失败/957 deselected（3740.66s），后续11项未运行；失败输出只记碰撞墙测试的共同末状态超过30轮，误差1.02141e-14，待原输入最小复现，不推测根因。阶段未通过。
隔离 shared-solution 数值块（2026-10-08，未并入main）：[证据与收据](../evidence/PHYS-PERF-01/shared-solution-r1/receipt.json)。严格保留30轮、原角更新/端口容差、8次线搜索、fsum及暖分区更新，旧8维Python求解保留。T0 373 passed/Ruff；T1 645 passed/81.36s、Ruff及三种子10.293/10.465/10.266s通过。独立旧127 C基线审计r4为10,661次映射/Jacobian/LU调用全字段/暖态一致；r1 Keycross、r2旧LU零调用、independent-r1 wrapper scope错误及后续修正日志均保留，属观测范围问题。两模式48拍Snapshot逐字段同主127/map160基线，短时0.8265/5.5733秒仅诊断。测试观测接到真实shared_solution系数包，16样本/2e-6门槛未变；tire_drivetrain同步的map160三行来自主线已验证修复。当前T2等主线继续，尚无profile/实时性能Gate。


Tire constitutive 本构块（2026-10-08，隔离未并入main）：[证据与收据](../evidence/PHYS-PERF-01/tire-constitutive-r1/receipt.json)。CPython math.hypot、能量/Frame传递及原阈值保持；combined/force/Jacobian/rolling/sticking/sliding六类审计逐值相同。初始T1为750 pass/2 timestamp probe fail，原Python同样复现241==241，与本构提取无关；phase T0 56通过后，组合T1去重782项通过并补齐三种子。两组48拍Snapshot同shared基线，短时仅诊断。close脚本空plan初始ValueError未运行checks，未伪造CLI日志。[详细归档](../evidence/PHYS-PERF-01/tire-constitutive-r1/report.md)。

四轮接点数值块归档（2026-10-08）：[报告](../evidence/PHYS-PERF-01/contact-system-r1/report.md)、[逐件清单/载荷SHA](../evidence/PHYS-PERF-01/contact-system-r1/manifest.json)、[收据](../evidence/PHYS-PERF-01/contact-system-r1/receipt.json)。以ab204a9旧DLL为独立基线；5,753次调用的梯度与对齐值hex全部相同，标准2×48拍完整Snapshot逐字段一致。T0 Ruff导入排序失败、pytest未跑；最终T1 552 passed/27.89s、Ruff与三种子通过。单/九车0.719/5.175s仅短测，不是FPS。354项PY/C/PYD源哈希起止一致；本次只归档既有证据，未跑物理或测试。

轮端解析导数原生块归档（2026-10-08）：[报告](../evidence/PHYS-PERF-01/wheel-derivatives-r1/report.md)、[SHA收据](../evidence/PHYS-PERF-01/wheel-derivatives-r1/receipt.json)、[原件与压缩载荷清单](../evidence/PHYS-PERF-01/wheel-derivatives-r1/manifest.json)。冻结源为 `mechanical_kernels.c`/`tire_drivetrain.py`，354项PY/C/PYD哈希前后相同。独立旧Python解析导数8,840次输出hex逐值相同；两组48拍Snapshot字段相同，0.6835/4.8669s仅诊断。T0 RUF059失败、pytest未跑；最终T1 752通过/148.96s、Ruff和三种子通过。无性能Gate结论。

主线整合与撞墙数值精度修复（2026-10-08）：性能分区已合入dff36ee。实际1145拍撞墙输入独立重放原30轮失败；输入轴上离合/齿轮反力相消，乘积低位保留后补偿求和、fma重建末速度。100位独立Decimal核对，保存输入轴误差由5.67168e-15降至9.54201e-18；原30轮/ULP角速/1e-14/1e-11端口等门槛均不变，独立保存系统7轮收敛。仅四项求和虽能收敛但精度更差，拒绝；统一线搜索误差尺度仍失败，未实施。原生异常中文格式的PyUnicode限制也已修正，保持ArithmeticError语义；新保存输入回归在数值修复前确实失败1.02141e-14。相关74项T0（13.85s），整合767项T1（189.65s）/Ruff/三个seed通过。单/九车48拍完整轨迹与差异已存，53,218个数值字段不同、最大2.91038e-11、没有非数值差异，0.7201/5.1067s仅诊断。命令：`logs/physics/PHYS-DESIGN-01-wall/run-T1.py`；收据`logs/validation/PHYS-INTEGRATE-04-wall-T1/summary.json`，数值复现/Decimal/完整Snapshot位于`logs/physics/PHYS-DESIGN-01-wall`，待不可变归档。阶段重审811节点复用、余1320/11专项待续跑；旧机械长轨迹因精度修复失效，不复用为当前证据。实时/T3/用户体验未过，未推送。


主线r8候选包归档（2026-10-08）：[报告](../evidence/PHYS-PERF-01/package-r8/report.md)、[构建/上下文/PYD/产物SHA收据](../evidence/PHYS-PERF-01/package-r8/receipt.json)、[逐件载荷清单](../evidence/PHYS-PERF-01/package-r8/manifest.json)。初次build因复制上下文缺requirements失败，修正后build_apps耗时30.3511912s通过；360项主源码构建前后与T2起始哈希一致，101文件副本指纹与上下文审计相同，两个原生模块在main/副本/包内字节一致。仓库外Game与Simulation各120拍headless成功（1.5338705/1.2547401s），不是render/FPS/体验Gate。初始reader路径错误且运行0项保留；T2 summary快照记录启动fa037c4和运行中状态，pytest日志未归档。


主fa T2（2026-10-08）已结束：783 passed/1轮胎落地求解失败/811 deselected，4650.59s，Ruff通过，11专项未跑。[完整失败与360源码核对](../evidence/PHYS-DESIGN-01/recontact-stage-r1/receipt.json)。阶段未通过；真实落地输入最小复现仅0.74s，不再重跑长测来查根因。后续正在修同一隐式力方程，精度不放宽。
三角面查询不变量归档（2026-10-08）：[报告](../evidence/PHYS-PERF-01/triangle-invariants-r1/report.md)、[逐项与载荷SHA](../evidence/PHYS-PERF-01/triangle-invariants-r1/manifest.json)、[收据](../evidence/PHYS-PERF-01/triangle-invariants-r1/receipt.json)。复用首轮plane fraction，并把同query padding传入edge回调；独立入口/候选顺序/64 sweep/96 GJK/精度保持。旧Python+ab204 DLL实测39,672 query/9,685 hits，hex逐值一致。两版2×48快照与主线墙端精度快照相同。初轮审计JSON被r2同counts覆盖，只保留原始log，不重建；最终T1-r2为560 passed/27.01s、Ruff和三种子通过。性能只作短测诊断。


隔离进程内初始化试验（2026-10-08，均拒绝）：[证据与收据](../evidence/PHYS-PERF-01/coupled-initialization-experiment/receipt.json)。法向载荷暖初值与提前联立Newton各89项T0通过，但两场景完整Snapshot均非逐字段相同；样本耗时分别为0.6988/4.8570s、0.9870/8.1486s，当前参考为0.7044/4.8658s。暖初值两项单次耗时均略低于参考，但差幅很小且快照不一致，无稳定收益证据；提前Newton更慢；均未接入生产、无T1或性能/机械Gate结论。目标 `tire_drivetrain.py` 与HEAD字节一致；其余并行工作区改动未纳入冻结。


悬架 prescribed closed partition（2026-10-08，隔离块）：[报告](../evidence/PHYS-PERF-01/suspension-prescribed-r1/report.md)、[SHA/载荷清单](../evidence/PHYS-PERF-01/suspension-prescribed-r1/manifest.json)、[收据](../evidence/PHYS-PERF-01/suspension-prescribed-r1/receipt.json)。仅 `mechanical_kernels.c` 新增已指定末行程直接式；零法向逆质量且四轮非负反力，硬件反力保留FMA，其余完整64轮活动集和原门槛不变。独立127 DLL的16,081次调用输出hex一致；T0 172 passed、T1 601 passed/Ruff/三seed通过。2×48拍Snapshot与主线fa037c4 wall-port基线逐字段相同；0.7078/4.7718s仅诊断。\n

悬架能量与完整步数值块（2026-10-08）：[报告/收据](../evidence/PHYS-PERF-01/suspension-energy-r1/receipt.json)。独立da6539c Python公式及旧127 DLL对照16,081个完整步、6,298次势能计算全部字段hex相同；64活动集/20与30轮/全部精度保持。172项T0、601项T1/Ruff/三种子通过；两组48拍Snapshot同main fa，0.6321/4.3398s与profile3.0445s仅诊断。360项源及全部归档载荷独立核对。suspension_contacts.py仅换行标记、无实际差异，不入提交；实时、T3、人工Gate未完成。


轮荷数据流（2026-10-08）：[收据](../evidence/PHYS-PERF-01/load-state-r1/receipt.json)。接点几何保持，只刷新四个实际轮荷；旧八维滚阻路径同步。328项T0/Ruff通过；首次审计因asdict深拷贝BulletWorld出现9观测错误，未比较输出；只改审计器并做一次九车24拍，432个完整输出全部hex/对象引用一致，消除13,504次接点重建。按用户新指示不再为小块重复T1/种子，主4067649已有876项T1仅记复用、不冒充本块重跑。阶段/实时/人工继续。


轮荷本构参数与滚动根控制流功能组（2026-10-08）：[收据](../evidence/PHYS-PERF-01/load-root-group-r1/receipt.json)。本构参数随真实轮荷刷新一次，严格C复用原20/20括根循环与CPython hypot；没有改物理或精度。一次A/B落体+九车24拍对照1,392完整推进全字段hex/引用相同，16,888次原生括根；Ruff通过。未重复pytest/T1/种子/48拍/profile；360项完成后源SHA保存。无新增FPS结论。下一真实有限网格的几何数组复用，整体阶段/实时/人工继续。


有限网格数值数组（2026-10-08）：[证据](../evidence/PHYS-PERF-01/triangle-packet-r1/receipt.json)。源三角面/候选顺序/边角和64/96迭代精度保持；数组仅缓存固定几何并明确持有元组及子packet。一次11项相关短检查+九车24拍，独立旧DLL39,663查询/9,674 hits全部hex相同；Ruff通过，首导入排序失败保留。未重跑T1/种子/48拍/profile。下一支持面无命中路径的对象装配与相同原生纯几何入口。


支持面纯几何与命中装配（2026-10-08）：[证据](../evidence/PHYS-PERF-01/surface-entry-r1/receipt.json)。同一entry供公开CylinderSurface和射线查询使用，静态translation直接沿用；未命中不再构造Surface对象。一次旧C+旧Python对照90直接入口及9,643射线，所有字段hex/引用一致，构造39,603→9,643。Ruff通过；未再次pytest/T1/种子/48拍/profile，不宣称FPS。下一完整九维局部轮端力/Jacobian的原生求解，避免每次残差往返Python。


Wheel solver 功能块证据收口（2026-10-08）：[逐件 SHA 与冻结源码 SHA](../evidence/PHYS-PERF-01/wheel-solver-r1/receipt.json)。基线 `8deb721` 原 Python + 独立旧 C DLL；已有对照 1,413 次完整调用、24,696 次原生力计算（滚动 17,076、静态 7,620）、21 个基准案例，完整输出 hex 与世界引用一致，Ruff 通过。本次只归档，未运行测试/模拟/profile/构建；不重复 T1/种子/48 拍/profile。876 项 T1 是 `4067649` 既有证据复用，不是本块重跑。主目录 `main`，未推送；完整 T2/T3/前台性能/人工未完成。下一步继续轮端数值入口、本构与能量装配。

轮端完整入口/末速度本构/胎体能量功能组（2026-10-08）：[报告与源码/验证收据](../evidence/PHYS-PERF-01/wheel-endpoint-r1/receipt.json)。九维实体轴提前进入原生轮力入口，同一调用完成原首轮切线预测、局部力/Jacobian求根与最终制动反力；避免建立原Python局部残差闭包和反复装配末状态。共同末速度接点、本构与轮力共用相同速度数值函数，energy_terms和advance_wheel共用原储能/耗散公式。八维旧机制继续保留；硬件、120Hz、共同20轮/端口30轮、滚动20×20括根及原1e-4N/整体精度保持。

一次独立8deb721原Python/旧DLL对照：1,413个完整推进、24,696次局部轮力、33,804次共同末速度本构、5,652次能量账，完整字段hex和世界引用一致；512组独立旧Python能量公式逐值一致。21条台架含FWD/RWD/AWD、正倒挡、挂挡/空挡/同步和低速；另含两条真实落体再接地与九车24拍。命令：`.venv/Scripts/python.exe logs/physics/PHYS-PERF-01/audit-wheel-endpoint.py`。原生扩展按setup.py的`/fp:strict`重建。

相关短检查命令：`.venv/Scripts/python.exe tools/validate.py T0 --tests tests/test_tire_compliance.py tests/test_tire_drivetrain.py --output logs/validation/PHYS-PERF-01-wheel-endpoint-T0 --timeout 180`，357 passed in 2.00s、Ruff通过。初轮Ruff仅有未使用contact_force导入F401，移除该导入后上述T0通过；未运行失败版本pytest。不追加完整T1/种子/48拍/profile/长轨迹，不把旧876项T1写成本轮重跑；本轮无FPS结论。代码与不可变证据归档本地提交，未推送；主fa T2的783/1失败及11未跑仍保留，最终T2/T3/产品包/前台/人工Gate继续。下一共同状态和跨轮载荷装配的实际热点，再收产品与阶段。

跨轮载荷与共同状态入口（2026-10-08）：[源码/独立DLL/验证收据](../evidence/PHYS-PERF-01/shared-load-r1/receipt.json)。wheel_load_prepared与新共同/局部入口共用同一个载荷数值函数；shared_solution与新入口共用原30轮求根、解析Jacobian、8次线搜索和逐坐标ULP/1e-11端口要求。固定矩阵沿用本advance的原WheelMap，当前四轮力、法向力/响应、接点梯度每次读取；仅省去角向/法向载荷的Python元组装配和再次读回。局部求解依原顺序排除本轮切向力，仍包含全部真实法向载荷。八维旧机制与旧公开入口保留；不缓存动态世界状态，不引入回退或新架构，120Hz/硬件/本构/20轮与原精度保持。

独立b5c35c5原Python+严格旧DLL一次对照：804个完整推进、14,823次共同载荷入口、11,220次局部自由状态入口、36条台架，全部字段hex与世界引用相同；C/PY/PYD起止SHA相同。台架含FWD/RWD/AWD、柔性开/关、正倒挡、挂挡/空挡/同步；实际轨迹含2s落体再接地和九车16拍。命令：`.venv/Scripts/python.exe logs/physics/PHYS-PERF-01/shared-load-r1/audit.py`，exit0。

相关短检查：`.venv/Scripts/python.exe tools/validate.py T0 --tests tests/test_tire_shaft.py tests/test_joint_suspension.py tests/test_rolling_resistance.py --output logs/validation/PHYS-PERF-01-shared-load-T0 --timeout 180`，77 passed in 1.32s、Ruff通过。原生扩展按setup.py的/fp:strict重建。没有本轮失败，也未重复完整T1/种子/48拍/profile/长轨迹，不作FPS结论。Luna仅复制既有证据并写逐件SHA，不跑物理或测试；归档日志采用.txt、目录-text，独立旧/新PYD各一份。仅本地提交，未推送；主fa T2的783/1失败及11未跑保留，T2/T3/产品/前台/两模式人工仍未关闭。下一局部自由状态与轮力求根直接连通，再收产品和阶段。

# PHYS-PERF-01 真实物理性能收口

- 状态：in_progress；施工线⑦，在codex/phys-real-01隔离工作树实施。
- 基线：0afe6b1；主目录33657dc已整合b2501d2，冻结源码T2继续运行；后续性能块在隔离线本地推进，未推送。
- 范围：减少同一机械子步内重复的几何与代数计算，再接产品/试玩包和最终Gate。

Simulation保持唯一权威世界、120Hz和现有物理子步。硬件参数、本构律、20/30轮上限和原残差要求保持；NPC执行共同物理。优化按实际profile定位，不以改变碰撞、控制请求或更新频率换取性能。

首份诊断为logs/physics/PHYS-PERF-01/profile-r1：GR86玩家与8辆NPC、coastal、种子17，无窗口/估计器，8拍预热与16拍cProfile。源码前后SHA一致、24拍完整执行；预热2.001s，带profiler91.559s。采样短且与主目录T2同时运行，只用于定位调用，不能当作FPS或前台Gate。热点是shared重复端口分区求解、known重复四轮力投影，以及TriangleSupport真实有限面查询。

先保存相同输入的完整Snapshot与局部矩/能量账；每次优化做相关T0和短原生对照。功能块完成跑T1，已有不受影响证据复用。最终前台1080p中画质8车，30秒预热/5分钟采样、平均≥60FPS且P95≤25ms；T3、试玩包、两模式人工驾驶保持待办。

仅本地提交，未推送。当前没有前台性能通过结论。

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

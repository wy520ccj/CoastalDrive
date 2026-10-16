# LAB-PERF-25 真实接触候选遍历

- 状态：done（本功能块）；基线53d3fa8，main；持续目标active。
- 完整凸起RadialRoads.query自身约.169s，保留原几何回调/缓存/顺序，将轮心与表面候选遍历、坡度/距离判定及命中收集移入现有严格浮点C。
- 缓存仅完整候选成功或空结果后写入；原异常/表面顺序/严格距离比较/坡度>=.5/返回数组和命中标量类型保持。真实查询/证明/细化、完整模型/120Hz/双子步/求解与门槛不减。
- 完整旧查询参照和实际缓存/异常/布局核对；同批完整步CPU/墙钟/P95/P99及payload验证后采用。普通/Double相关T0、完整试验台专项与真实记录复算；既有方程证据按相同payload明确复用。
- 仅试验台，本地提交，原精度/能量/人工/实时/EPA Gate开放，持续目标active。

## 已交付

- 原轮心/表面/候选顺序、生成器与完整缓存写入语义、原数值比较类型/相同距离先取、命中字段与数组保持；C路径直接调用原真实几何。最终复用命中元组/方法vectorcall，旧C段和非遍历Python全文AST保持，三个src文件，只有wheel重编，两候选各一次，游戏未改。
- 首候选凸起仅快.59%/转向慢1.35%的原数据/源码/扩展/完整剖析保留；最终转向/凸起整步−3.06/1.65%，CPU−9.26/5.42%，两次新运行均快于两次旧运行。制动不足1%不作收益，CPU慢3.45%和转向P99差1.30%保留；初始化单列，仍未实时。
- 两候选3456子步完整输出及24块正式B逐字节相同；432子步原方程/能量证据明确复用，长工况/细化未重跑。
- 新增70项顺序/类型/布局/缓存/异常/引用释放/门槛ULP与边界检查，普通/Double最终T0各139项，Double48模块972项/Ruff/真实记录与旧检查点复算通过。旧float16警告保留，无测试数值失败。
- 原查询26842/Box3394/细化2703/残差3486/Jacobian8保持；新原生遍历4960次。剖析中最终Python准备约.057s+C遍历自身约.068s，不用单函数速度代替整步。
- 命令：项目Python setup.py build_ext --inplace --build-temp builds/lab-perf-25/native；Double包装interleaved.py/profile_worker.py/lab_regression.py；tools/validate.py T0 --tests tests/test_lab_query_native.py tests/test_lab_surface_cache.py tests/test_radial_geometry.py tests/test_lab_radial_native.py tests/test_finite_radial_contact.py（普通/Double）。[完整证据](../evidence/LAB-PERF-25/README.md)含实际来源/两候选/全部原值/归档脚本。
- 通用T1/T2/T3、游戏seed/window及人工未跑。下一同子步初始/目标几何准备重复量；持续目标active，不结束目标。

# LAB-PERF-24 接触几何小向量范数

- 状态：done（本功能块）；基线0cf9585，main；持续目标active。
- 当前完整凸起中，Box/径向表面及其平面/曲率常量共68772次二维/三维范数（剖析诊断）。先核对原NumPy点积/平方根路径，再严格浮点C执行这些固定维度范数；不减少真实查询/全局证明/候选/细化次数。
- 保留双精度原运算顺序/类型与低精度NumPy语义；完整模型、120Hz/双机械子步、34维残差、原求解和门槛保持。只有完整步输出逐字节相同且同批性能有效才采用。
- 仅试验台，普通/Double相关T0与完整试验台专项/真实记录复算；已有效的原方程证据按相同payload明确复用，不重复长工况/细化。
- 本地提交，原精度/能量/实时/人工/EPA Gate开放，持续目标active。

## 已交付

- 原点积开方/NumPy标量类型保持，四棱长度/临界值/投影界限批量准备；低精度曲率平方沿原NumPy类型。旧C段全文、还原后的完整Python模块AST相同，原模型/求解/门槛/真实查询保持。五个src文件，只重编wheel两候选各一次，其他四扩展及SDK保持，游戏未改。
- 首候选凸起减2.95%、制动慢3.57%/转向慢.39%原数据/源码/二进制保留；最终凸起1.940795→1.824949s（−5.97%），CPU−10.28%，P95/P99下降。制动/转向变化不足1%不作明确收益；转向P95变差3.95%保留。初始化单列，仍未实时。
- 两批3456子步完整输出/能量账逐字节相同且等于23块正式B；432子步原方程证据明确复用，长工况/细化未重跑。新增76项，最终普通/Double T0各124项（Double复用second-fixed），Double47模块902项专项/Ruff及真实记录/旧检查点复算通过；两次仅Ruff失败已修复，原float16溢出警告保留。
- 完整剖析np.linalg.norm83346→14574，新C小范数34832、四棱批次3394；原残差3486/Jacobian8/查询26842/Box3394/细化2703保持。
- 命令：项目Python setup.py build_ext --inplace --build-temp builds/lab-perf-24/native；Double包装运行interleaved.py/profile_worker.py/lab_regression.py；tools/validate.py T0 --tests tests/test_lab_small_norm.py tests/test_radial_geometry.py tests/test_box_radial_geometry.py tests/test_lab_box_axis_cache.py（普通与Double）。[完整证据](../evidence/LAB-PERF-24/README.md)含两候选实际来源、CPU/墙钟/尾延迟/初始化及归档脚本。
- 通用T1/T2/T3、游戏seed/window及人工未跑。下一真实几何/固定读取，持续目标active，不结束目标。

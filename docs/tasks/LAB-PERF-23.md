# LAB-PERF-23 三维叉积与完成步观测准备

- 状态：done（本功能块）；基线1a32677，main，持续目标active。
- 当前完整剖析8496次np.cross约.299s，完成步观测144次约.291s、read_mechanics432次约.258s。先将独立轮心路径普通叉积移入现有严格浮点C，再去掉观测未使用的完整质量/端口装配，读取仍来自真实原生世界。
- 原普通叉积乘减/零符号/类型、NumPy矩阵布局和乘法顺序、全部观察字段/真实接触/120Hz/双机械子步/求解与门槛保持；低精度输入按原NumPy行为。
- 实际旧新原始数值/布局/完成步全字段、完整步输出与耗时验证后采用；同一物理功能块跑相关T0及完整试验台专项/记录复算，既有精度扩展不无故重复。
- 只处理试验台，本地提交，原精度/能量/人工/实时/EPA Gate继续开放，持续目标不因本功能块完成结束。

## 已交付

- 严格浮点C普通叉积替换原独立轮心np.cross，完成步观测直接读取原生状态/轮轴/同序世界惯量，去掉未使用的完整力学装配。五个src文件，旧C段/物理方程/求解与阈值不变；只重编wheel，其他四扩展SHA相同，游戏未改。
- 三工况四世界逐拍ABBA完整步墙钟减8.44/8.23/6.02%，P95/P99均降；制动CPU增3.57%原值保留，转向/凸起CPU减3.64/1.19%。凸起1.2模拟秒仍需1.924墙钟秒。初始化单列，不跨批次相乘。
- 12份1728子步完整输出逐字节相同，且与22块正式B文件相同；独立原方程/能量432子步仅按相同payload明确复用，较长工况和细化未重跑。
- 新增55项通过；最终普通/Double T0各78项，Double46模块826项完整试验台专项/Ruff和真实记录/旧检查点复算通过。完整剖析中原残差3486/Jacobian8/真实查询26842/Box3394/细化2703保持，np.cross8496转原生，完整装配432→288。
- 命令：项目Python setup.py build_ext --inplace --build-temp builds/lab-perf-23/native；Double包装运行interleaved.py、profile_worker.py、lab_regression.py；tools/validate.py T0 --tests tests/test_lab_observation_native.py tests/test_unsprung_body.py tests/test_vehicle_unsprung.py tests/test_lab_jacobian_hint.py（普通与Double各一次）。原日志/源码/真实扩展/旧版本来源见[证据](../evidence/LAB-PERF-23/README.md)。
- 本轮没跑通用T1/T2/T3或游戏seed/window，人工体验未验收。下一实际读取/真实接触成本；持续目标active。

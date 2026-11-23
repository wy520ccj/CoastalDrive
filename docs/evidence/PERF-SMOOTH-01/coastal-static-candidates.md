# 滨海物理步热点与两项未采用实验

2026-10-28。继续原卡顿目标，采用完整步、同配置、快照和正反顺序对照。本轮未修改生产物理源码/原生模块；180份顶层源码/原生文件与实验前逐字节一致。全部B盘，无提交/推送。

## 对准正常入口的诊断

扩展tools/performance/benchmark_physics.py，可显式选择game-tuned车型、原ViewDriver、正常settle_initial及检查点框开关；原默认车型/输入序列保持。自由8交通车、计时0交通车，完整配置与正常HUD40入口一致。预热120步，正式240步：自由完整步均值10.041/P95 14.584ms，计时3.980/P95 5.164ms；均0碰撞。这是无窗口计算诊断，不含前台/进程调度，不代替正常120Hz性能门。

另120步cProfile中static_support_read约250.95ms，即每步2.09ms；机械求解与接触仍为主要成本。累计时间互相包含，不能相加。当前512个内外栏杆BulletConvexHullShape令joint_supported=False，不能为进入原生联合几何路径漏掉它们。碰撞、子步、精度和120Hz保持。

## 隔离候选与拒绝理由

候选分别在logs/visual-extend-20261028/static-transform-candidate和static-method-candidate编译，未覆盖src头文件/pyd。前者用不可变TransformState识别形状姿态变化，后者按body复用getShapeTransform绑定方法，均保留每形状读取/失效条件。各自既有静态读取/缓存/查询生命周期13项检查在终端通过，不冒称完整T1或前台验收。

| 自由360步实验 | A1原版均值 | B1候选均值 | B2候选均值 | A2原版均值 |
| --- | ---: | ---: | ---: | ---: |
| TransformState | 9.507ms | 9.461ms | 7.697ms | 7.735ms |
| 绑定方法复用 | 9.847ms | 9.575ms | 8.314ms | 7.853ms |

两组ABBA各360个完整Snapshot负载哈希全部相同、配置相同、0碰撞；前后原版也明显变化，收益不稳定。TransformState另计时360步原4.032/候选3.996ms、负载哈希相同，同样不足以采用。**两个候选均拒绝，生产内核保持。**不将静态读取热点当作唯一根因。

原始report.json、snapshot-hashes.json与profile在同名logs目录，摘要见[完整步与等价记录](coastal-static-candidates.json)。本轮未新增前台驾驶；HUD40自由/计时中位57.73/34.95ms的严重卡顿结论保持。后续继续测完整查询/失效成本与正常权威步，不删形状或按最佳样本宣布成功。

## 实际落地的资源完整性修复

setup.py漏收海浪wave-normals.txo.pz和地表ground-material.glsl。已增加对应压缩纹理/环境glsl模式，扩展既有测试核对海岸/地表/实验台资源。T1-regional-package：Ruff、tests/test_ui_theme.py全部5项及0/17/23各1200步种子通过；验证规则覆盖，未构建/安装或发布安装器。

当前PERF72/视觉91指纹；旧PERF69项全保持，旧视觉88项仅显式候选采集工具变化。新增setup/对应测试/基准与烘焙工具登记，见[保持记录](../VISUAL-EXTEND-01/native-meadow-preserved.json)。动态水面、原8K天空、3.2m镜位保持，整体目标active。

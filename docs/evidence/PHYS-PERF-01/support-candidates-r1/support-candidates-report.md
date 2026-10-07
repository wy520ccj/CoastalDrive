# PHYS-PERF-01 support candidate bounds evidence

基线 `4635006`，归档时HEAD `c1938b2`，生产改动为 `src/wheel_contact_kernels.c` 与 `src/suspension_contacts.py` 的批量原形状覆盖盒筛选。两份源已先行复制冻结，`source-hashes.json` 记录354项 `src/tests/tools` Python/C/PYD 起止SHA。

512个query×240个parts的探针验证投影、part对象身份、遍历顺序及最终候选集合逐项一致。Python/C/Python/C四次微测墙钟为 `0.1163/0.0131/0.1131/0.0124s`，只代表微基准。48拍单车与8 NPC完整Snapshot逐字段均与shaft-plans版相同；最终样本耗时 `1.19144/13.32071s`，前版 `1.34825/14.57333s`，保留为短测记录，不据此宣称稳定整车收益。

现有profile均为8步预热、16步、288个physical calls：带profiler窗口总时间 `12.4856→11.2088s`，`prepare` 累积时间 `1.8334→0.7639s`，`cylinder_suspension_rays` `4.7465→3.5808s`。这些是离屏诊断定位数据，不是FPS或前台性能Gate。完整JSON与prof文件已保留。

验证：T0 38项/Ruff通过；T1 474项/Ruff、三个1200步seed（0/17/23）通过。源快照和完整日志已归档，gzip均用mtime=0且payload SHA核验。此次仅归档，不跑测试/模拟/构建；不修改shaft-plans或package-r5历史归档。

# PHYS-PERF-01 耦合修正算法试验

本目录只保存两项进程内算法试验，均未进入生产源码，也没有运行机械或能量 Gate。捕获时隔离工作树 HEAD 为 `d3859f8`、生产工作区干净，`src/tests/tools` 的 354 项 `.py/.c/.pyd` 哈希首尾一致。

联合 14 变量 Newton 仅在当前子步内共同修正六维末速度与八个轮胎力；仍使用原 20 轮外循环、8 次线搜索、所有门槛，并逐次执行实际有限面与本构计算。Broyden 试验只在当前子步复用 Jacobian。两者均通过独立进程内 `exec` 探针运行，没有接入生产路径。

两种试验都完成了单车和 8 车各 48 拍，但完整 Snapshot 并不逐字段等同基线。与 `endpoint-production.json` 比较，所有序列化 Snapshot 标量叶项的差异数量及最大绝对数值差异列在 `snapshot-difference-diagnostic.json`；统计包含 solver residual 和其他诊断字段，只作描述，不解释为物理误差。

基线单车/8 车耗时为 0.7980/7.1059 秒；Newton 为 1.3569/17.4754 秒，Broyden 为 1.5520/19.0373 秒，均明显更慢，因此拒绝。时间是短测诊断，不是 FPS。

Broyden 首次探针的生成脚本把矩阵赋值缩进到了列收集循环内，未收集完 14 列就触发 `IndexError`；首轮失败日志保留。修正生成器后才有有效 r2 结果。所有原 `.log` 以相同字节保存为 `.txt`，快照采用 `mtime=0` gzip，payload SHA 已校验。

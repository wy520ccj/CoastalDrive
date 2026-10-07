# PHYS-PERF-01 surface-prefilter experiment

该实验只在原三角面支持查询前应用 root AABB 判据，跳过不可能命中的临时对象；entry 公式和候选顺序保持。40 台架与 9 车 24 拍的独立调用审计日志记录 15,148 射线、59,361 支持面及 15,894 命中（mesh 54,820、plane 59、box 4,482）。正式 T0 summary/pytest.log 实际为 Ruff 通过、31 项 pytest 通过；另一个调用审计日志中的 `40 passed in 6.69s` 是其独立输出，不计作正式 T0。

保存的标准 0/8 车各 48 拍 Snapshot 数组与 `endpoint-production.json` 基线逐字段相同。试验短测为 0.96988/11.63759 秒，较基线 0.7980/7.1059 秒慢。它没有 T1，也没有进入生产。标准对照和独立局部审计是各自的证据，不能替代交替轨迹断言失败。

同进程 old/new/new/old 的墙钟记录为 10.89805/12.72489/12.79591/12.66793 秒，CPU 时间为 10.703125/12.5625/12.515625/12.4375 秒。该试验在完整 Snapshot 相等断言处失败；脚本在断言后才写 JSON，因此四条原始快照没有保存。失败原因未知，生命周期 epoch 仅是待查假设；本档案不补造快照或差异统计。

冻结的实验 C 与当前恢复源码分开记录：实验源 SHA 见收据；当前 C 的字节与 `d3859f8:src/wheel_contact_kernels.c` 相同，但 Git status 仍报告该文件 `M`，两种事实均保留。生产 PYD 当前哈希也单独记录。严格重建日志和之前基线模块的源、改名副本、setup、receipt、manifest、构建日志一并归档；不复制原基线 PYD/OBJ。所有新 `.log` 以同字节 `.txt` 保存，快照以 `mtime=0` gzip，并核验 payload SHA。

短测不是 FPS 或前台 Gate；没有机械/能量 Gate 结论。主目录阶段 T2 仍在继续，相关性能与人工 Gate 未完成。

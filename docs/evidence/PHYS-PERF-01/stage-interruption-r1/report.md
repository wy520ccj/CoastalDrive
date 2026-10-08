# PHYS-INTEGRATE-03 T2 中断与续跑记录

原 T2-r1 摘要保留 `running`，但进程已不存在、unified session `35815` 状态未知，pytest 日志为0字节且没有完成输出。中断原因未知，不计为通过。原始零字节 pytest 文件、Ruff日志、摘要及中断观察均已留档。

同一冻结主源码的 T2-r2 已重新启动。启动摘要显示复用957节点、剩1173节点和11项专项；任务交接时 root 实际确认进程 PID 存在并持续消耗CPU，默认顺序首个18,000拍 highway 节点已通过，pytest日志约29个通过标记且未见失败。这只是运行中观察，不代表最终计数、T2 Gate或阶段通过。为避免复制仍在写入的数据，归档仅保留r2摘要快照、启动脚本、复用审核与节点清单，不含活动 pytest 日志。

源码捕获范围为 `src/tests/tools` 的354个 `.py/.c/.pyd` 加根 `setup.py`，r1/r2 summary中的358项哈希清单彼此相同，且代码部分与当前捕获相符。main提交 `01b99f3` 源冻结。隔离 shared-solution 已在 `12ea82b` 本地提交并有645项T1，但尚未整合回主线。实时前台性能、T3及人工驾驶Gate未完成。

大 JSON 使用 `mtime=0` gzip，归档 SHA 与载荷 SHA 见 `manifest.json`；r2进行中的pytest日志没有归档。

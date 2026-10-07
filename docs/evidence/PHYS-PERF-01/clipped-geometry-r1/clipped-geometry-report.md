# PHYS-PERF-01 clipped geometry evidence

HEAD `7055a13`，三份当前源副本与354项 `src/tests/tools` Python/C/PYD起止哈希见 `source-hashes.json`。该块将6平面裁剪及逐元素差量提取为C helper，保留FMA数值、zip迭代提前结束及原数值类型；底层初版 `clipped-geometry-body.c` 记录subtract序列方案，最终正式源以归档中的 `src/` 点时副本为准。

探针1024组裁剪结果（含hex、顺序、原vertex身份）一致；128组subtract结果、类型与剩余迭代器一致。两个构建日志均保留。最终48拍单车/9车Snapshot与triangle-query版逐字段相同；当前 `0.9280588/9.6940992 s`，旧版 `0.9656480/10.4588775 s`，只是短测，不作FPS结论。Profile窗口 `7.6379917 vs 9.1704193 s`，仅作为相邻版本调用定位，不能消除负载波动或推出稳定收益。

验证记录：首轮T0因Ruff I001失败而未运行pytest；T0-r2 31项通过；T1 474项通过（55.33s）、Ruff通过，三种子1200步17.061/16.600/16.554s通过。完整摘要和日志均保留。快照及prof数据以gzip `mtime=0` 保存，payload SHA已核对。此次仅归档，不运行测试/模拟/构建。

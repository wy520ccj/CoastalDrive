# PHYS-PERF-01 静态候选表面复用

本归档保存现有候选缓存对照、全量48拍快照及验证摘要；本次没有运行测试、模拟、构建或渲染。逐项原件/归档 SHA-256 与确定性压缩校验见 [`receipt.json`](receipt.json)。当前源码 PY/C/PYD 哈希、HEAD 与未提交状态见 [`source-hashes.json`](source-hashes.json)。

## 结果

基于 `7850870` 的未提交工作树，候选缓存版与此前 native projection 结果单车、九车各48拍完整 Snapshot 均逐字段相同。短测单车 1.664→1.558 s（下降 6.35%），九车 19.738→17.981 s（下降 8.90%）；这些墙钟结果仅为短时对照，不代表 FPS 或前台性能。

## 保守性与生命周期

`src/suspension_contacts.py` 的 `cylinder_suspension_rays` 为候选查询包围盒按每轴 5 cm 扩展；只有新查询范围完整位于缓存盒内才复用候选表面，否则重新从 Bullet 世界查询。命中仍由 `CylinderSurface.entry` 对实际射线路径/轮轴做精确求交，候选集合只缩小查询对象，不近似最终接触。`WorldSurface.relative_entry` 以完全相同的 `(start,end,axis)` 缓存结果；`Suspension.prepare` 每个物理子步创建新的表面对象，因此候选和射线缓存随 prepare 失效。

`tests/test_suspension_query_lifetime.py` 覆盖同射线复用、prepare 后缓存清空，以及路径跨出覆盖范围后重新查询；测试比较缓存路径与独立 Bullet 查询的接触结果，并检查移动支持面与无命中情况。相关实现和测试原始行号分别是 suspension_contacts.py:122-133、vehicle_suspension.py:36-44/56、test_suspension_query_lifetime.py:21-54。

## 验证边界

- candidates T0：Ruff 与 27 项通过。
- T1 首次尝试：Ruff 通过；pytest 因路径错误退出码 4、未收集到测试；三种子均未运行。失败记录原样保留，不将其计作通过。
- T1-r2：Ruff、442 项通过；三个 1200 拍 headless 种子 0/17/23 分别约 23.7/23.7/23.9 s 通过。

主目录 T2-r11 正在运行；本工作树尚未合并或推送。前台性能、T3、最终产品包和人工体验仍未完成。

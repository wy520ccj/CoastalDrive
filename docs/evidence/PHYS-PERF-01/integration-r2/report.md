# PHYS-PERF-01 integration-r2

本档案记录主目录 `a2e6975` 集成检查。捕获时 `src/tests/tools` 的 354 个 `.py/.c/.pyd` 首尾哈希稳定；唯一未提交文件是 `tests/test_highway_run.py`，此次事故计数摆位修正由主任务单独归档。源码审计记录主/隔离版本为 `a2e6975` / `d3859f8`，355 项归一化文件相同，唯一差异为 `test_h3_review`。T1 与 T2 使用当前捕获版本；T2 的 354 项哈希与捕获完全相同。r6 包构建前后哈希一致；与当前捕获相比只差 `tests/test_highway_run.py`，因为本次未提交的测试计数修正发生在构建之后，生产源码哈希相同。

集成快照和隔离端点快照的单车、8车两个 48 拍 `snapshots` 数组逐项相同。主目录短测为 0.8271799 秒和 6.3367065 秒，仅为离屏诊断，不代表 FPS。

r6 包在仓库外以 game 与 simulation 模式各运行 120 ticks，两个模式都报告完整 98 项硬件字段；实际 exe、机械内核与轮接触内核 pyd、GR86 配置和 CPython license 的 SHA 已针对包目录核对。它是 headless 核验，不代表渲染、FPS 或人工验收。

T1 的 Ruff、784 项 pytest 和三个种子检查通过；checkpoint T0 的 Ruff 与 2 项检查通过。stage T2-r1 没有通过：`tests/test_highway_run.py::test_contact_episode_counts_traffic_and_guardrail_but_not_floor` 失败，pytest 记录 25 项通过、1 项失败、1172 项未选择，耗时 985.59 秒；外层验证摘要记 986.209 秒。失败为非线性求解残差 61267.6 N，之后 11 项均未运行，958 个节点尚待执行。三个 headless 结果来自同源 T1 复用。

30秒 1080p GR86/8车窗口观测原样保留：报告记墙钟 31.169 秒、平均 0.7088 FPS、display-draw P95 1832.2 ms，但报告同时标记 `window_sampling_valid=false`，记录到 25.225 秒模拟时间丢失；窗口样本从 18 秒起 `foreground=false`，因此不能作为有效 FPS 或前台 Gate。图像为实际窗口截图，且未声称人工验收。

所有 `.log` 以同字节 `.txt` 保存并记录原文件名；大型快照使用 `mtime=0` gzip 并核验 payload SHA。此集成证据不改变 T2 失败状态，也不替代完整阶段、渲染或人工验收。

# PHYS-PERF-01 known state native evidence

基线 `67f43e3`，隔离工作树有未提交 `src/mechanical_kernels.c` / `src/tire_drivetrain.py` 联合已知自由状态、陀螺、逆质量、滚阻与法向自由速度的组合。当前源副本及354项 `src/tests/tools` Python/C/PYD起止SHA已在父任务开始下一源块前捕获，见 `source-hashes.json`。旧C mass/rotor公式作为 numeric helper 提取，组合实现没有重复公式。

`known-state-probe.json` 记录768个组合case精确通过，含十六进制数值与原velocity对象身份；`mass-spin-exact.json` 是已有的旧基线记录（2304 mass_response、768 rotor_spin）。日志目录中没有名为 `mass-spin-probe.json` 的文件，因此本归档不伪造该文件，也未重跑探针。`check-mass-spin.py`、`check-known-state.py` 和 promotion输入脚本按现有版本保存。

最终与 support-candidates 版的单车/8 NPC各48拍快照逐字段相同。短样本 `1.078446/12.130549 s`，上一版 `1.191437/13.320713 s`；保留原值但不作为稳定性能/FPS结论。Profile为8步预热、16步采样，前后源哈希不变；总窗口 `11.208753→10.648763 s`，只作诊断。

T0全量相关pytest实际466项通过，T1 626项通过（91.70s）、Ruff通过，三个1200步seed分别17.490/17.615/16.277s通过。摘要及全部原始日志均归档。快照和cProfile使用gzip `mtime=0`，payload SHA已核验。本次仅归档，没有运行测试/模拟/构建。

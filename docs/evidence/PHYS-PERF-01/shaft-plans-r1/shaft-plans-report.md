# PHYS-PERF-01 shaft plans native evidence

基线 `16a7c4a`，该版已有未提交的 native shaft-plans 接入。捕获时生产源 `src/mechanical_kernels.c`、`src/shaft_transmission.py` 原样复制到 `source/`；354项 `src/tests/tools` Python/C/PYD 起止SHA及关键文件哈希见 `source-hashes.json`。捕获已先完成并通知主任务可继续下一源修改。

`shaft-plans-probe.json` 中1152个矩阵的数值与缓存对象身份均逐值一致，顺序为 Python/C/Python/C。48拍单车及8 NPC最终快照与 `coefficients-final-snapshots` 全字段相同。ABBA单进程对照顺序为 Python/native/native/Python；对照脚本每拍显式将生命周期标识 `contact_epoch` 置0后比较，四条物理快照均相同。

同进程ABBA原始结果按运行顺序保留：wall `15.5076/16.0165/16.2727/15.6917 s`，CPU `15.1094/15.7031/16.0625/15.4375 s`，整车没有稳定收益。profile中 `shaft_brake_plans` 的4320次同函数成本由 `1.02317 s` 降至原生 `0.02861 s`；16拍cProfile窗口总时间 `13.6184→12.4856 s`。这只是短样本诊断，不是FPS。

验证边界如实保留：首轮T0引用不存在的 `tests/test_drivetrain_inertia.py`，pytest未收集；T0-r2实际只运行 `test_drivetrain_jacobian.py`，1项通过。T1首轮实际只运行 `test_world_substeps.py` 4项，重复 `--tests` 参数覆盖了先前列表；其三个smoke通过但不构成完整T1。最终T1-r2用单一完整列表，626项通过、Ruff通过，三个1200步seed分别17.762/17.956/17.244 s。完整summary与日志见 `validation/`。

profile JSON与cProfile二进制、输入探针和大快照均保留；快照/`.prof` 以 gzip `mtime=0` 保存并核验payload SHA。此次仅归档，不运行测试或模拟。

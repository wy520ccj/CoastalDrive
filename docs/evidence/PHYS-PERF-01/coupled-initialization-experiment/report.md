# Coupled initialization experiment

两项候选仅通过独立进程加载试验源码，未接入 `src`。两者各自的 T0 为 89 passed；试验后单车与八车完整快照均未逐字段相同，均无 T1 或性能/机械 Gate 结论。

- 法向初值暖启动：0/8 车样本耗时 0.6987553/4.8570163 s，两个 `all_snapshots_equal` 均为 false。结果不支持稳定收益，拒绝。
- 提前联立 Newton：0/8 车样本耗时 0.9869737/8.1485709 s，两个 `all_snapshots_equal` 均为 false；比当前参考短测更慢，拒绝。
- 参考是归档的当前 `triangle-bound-snapshots.json`：0/8 车 0.7043968/4.8658481 s，原报告 `all_fields_equal: true`。暖初值两项单次耗时都略低于参考，但幅度很小且完整Snapshot不相同，不能据此认定有稳定收益。短测时间仅诊断，不代表 FPS。

源码身份只记录目标 `src/tire_drivetrain.py`：当前字节与 HEAD `756d26258fa9522a2ec9f7921f93215c77b10627` 的 blob 完全相同（SHA-256 `6ca34d6b3fd24514dae215f93e50235ad383be24cc039136d9ea3e0263d07e4a`）。不冻结其它正在工作的源文件。

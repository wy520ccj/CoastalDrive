# PHYS-PERF-01 shared map evidence

基线 `f4a5ae0`，捕获时未提交更改位于 `src/mechanical_kernels.c` 和 `src/tire_drivetrain.py`：9/11维活动分区映射与解析Jacobian。原30轮求解和阈值保持。两源副本和354项 `src/tests/tools` Python/C/PYD起止哈希见 `source-hashes.json`。

真实调用审计的首轮44失败/39通过由审计脚本未导入 `rotor_known_state` 导致NameError，审计计数为零；这不是生产T0失败或物理回归。修正脚本后的r2审计83项通过、34.98s，统计到160010次mapped、9289次Jacobian，其中hard gear 156276、synchronizing 3734；9维156776次、11维3234次。逐值与f4a5ae0原实现及全部分区元信息相同。

最终版和中间mapped-only版分别与known-state版的单车/9车48拍全Snapshot逐字段一致。最终耗时 `0.984879/11.480951s`；中间版 `1.110262/12.669515s` 独立保留，不作FPS或稳定整车提速结论。

Profile对照窗口带profiler总时长 `10.6487635→11.0004777s`，新版反而略慢，照实保留。通过现有cProfile文件核验，旧版 `shared`累计约 `2.43898s`、新版 `1.20230s`；新版还记录24642次C映射0.104857s、1346次Jacobian 0.016755s、288次系数构造0.011378s。其他geometry热点也有波动，不能把总profile差异归因到单一改动。所有profile为16拍诊断，不是FPS。

生产T0两版各418项通过。最终T1 626项通过（90.97s）、Ruff通过，三个1200步seed（0/17/23）15.982/15.203/16.374s通过。所有summary与完整日志保留。快照和prof使用gzip `mtime=0`，payload SHA校验通过。此次只归档，不跑测试/模拟/构建。

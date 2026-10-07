# PHYS-PERF-01 triangle query evidence

基线 `f44aeb1`，捕获时新增源为 `src/wheel_contact_kernels.c` 与 `src/triangle_support.py`。对应测试时点的源字节原样保存在 `source/`，包含C文件EOF多一个空行；采集记录 `git diff --check` 返回2并报告 `601: new blank line at EOF`。该后续清理未覆盖本归档源快照。354项Python/C/PYD哈希起止、两源及当前wheel PYD哈希见 `source-hashes.json`。

查询实现将原 `box_interval` 与 `triangle_face` 计算提取到helper；公开入口和整条查询共用这些helper，64次sweep、96次GJK及各既有门槛保持。13项原生真实调用审计通过，2.44s；真实九车24拍记录54821次query、15774次hit，逐值与f44aeb1的原始 `TriangleSupport.entry`、候选生成器和边角求解器一致。

最终单车/9车48拍完整Snapshot与shared-map版逐字段相同。当前短测 `0.965648/10.458878 s`，上一版 `0.984879/11.480951 s`，均为短样本，不是FPS结论。Profile均16拍且计数未变，带profiler窗口 `11.000478→9.170419 s`；相邻运行存在负载波动，仅作为定位记录。

T0 31项/Ruff通过；T1 474项（69.01s）/Ruff及三个1200步seed（0/17/23：19.488/18.358/16.627s）通过。构建日志、完整profile及快照已保存；大文件gzip `mtime=0`，payload SHA经核验。此次仅归档，不运行测试/模拟/构建。

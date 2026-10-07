# PHYS-PERF-01 suspension-state-r1

本块把悬架活动集状态计算提取为共享原生 helper；原64轮活动集、1e-10接触间隙、1e-7反力门槛、LU、`fsum`/`fma` 顺序及能量账保持。生产源副本和354项源码哈希已保存；捕获期间哈希首尾相同。`wheel_contact_kernels.c` 在 Git status 中仍显示 M，但字节与 `d3859f8` 完全一致，不属于本块变更。

原 `d3859f8` 基线审计对 5,757 次调用的完整 `SuspensionStep` 字段逐项相同：zero mobility 3,860、nonzero mobility 1,897、free wheels 178、stop 输入 2。需要区分的是，审计路径本身调用当前 LU helper；因此另存 512 次独立 LU 探针，结果与原探针逐值相同。

单车与 8 车各 48 拍完整 Snapshot 数组均与 `endpoint-production.json` 相同；短测为 0.7375/6.4815 秒。16 拍 profile 为 4.8444 秒，只作为诊断，不作为 FPS。

T0-r1 和 r2 的 Ruff 分别因未使用导入失败，pytest 未运行；r3 Ruff 与 411 项 pytest 通过。T1 的 Ruff、496 项 pytest（43.18 秒）和三个种子（12.6/11.6/11.3 秒）通过。当前归档未重跑验证；首轮失败日志原样保留。

所有 `.log` 以同字节 `.txt` 保存，快照及 profile 使用 `mtime=0` gzip，并记录原文件名、来源 SHA 和压缩 payload SHA。短测不是 FPS、前台或人工 Gate；主目录 T2 不属于本次证据。

# PHYS-PERF-01 wheel-map-r1

本归档记录轮端本地状态共享映射。共同映射与 wheel-map 复用原有端口/分区函数；旧 8 维机制保留，每次尝试中的暖模式更新仍直接写回原列表。真实调用审计记为 217,053 次：hard 210,407、synchronizing 6,646、warm updates 85,725、multiple attempts 7,721。

基线 `clipped-geometry-snapshots.json` 与最终 `wheel-map-production.json` 的单车和 8 车各 48 拍快照逐字段相同。记录墙钟分别为 0.8345694 秒和 8.1023865 秒，仅为短测，不代表 FPS 或前台性能。16 拍 profile 窗口为 6.5905 秒，`local_state` 成本下降；调用次数保持。该 profile 用于定位，不作为 FPS 证据。

源码捕获基于 HEAD `105d849` 加未提交的 `src/mechanical_kernels.c`、`src/tire_drivetrain.py`。快照生成后，C helper 仅发生缩进调整并重建；`wheel-map-check-receipt.json` 记录了对应实际 SHA 差别。因此快照、最终 T1 与 profile 分别按各自源码时点解释，不能笼统声称 SHA 完全一致。

T0-r1 与 T0-r3 通过；T0-r2 的 Ruff 因未使用导入/变量失败，pytest 未运行。最终 T1 的 Ruff、626 项 pytest（约 73.2 秒）及三个种子 13.9/13.6/15.0 秒均通过。初次收据脚本的 `Path.relative_to` 错误已修复，属于归档脚本错误，不是物理失败。

这组离屏短测不构成 FPS 或前台 Gate。主目录 `33657dc` 的 T2 独立运行仍未完成；产品包、实时前台和人工 Gate 也未完成。

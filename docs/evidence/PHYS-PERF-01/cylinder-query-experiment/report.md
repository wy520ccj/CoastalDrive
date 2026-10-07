# PHYS-PERF-01 cylinder-query experiment

该候选只改圆柱表面查询的前置数值路径。本归档不包含二进制产物；恢复后的生产 `wheel_contact_kernels.c` 与 `suspension_contacts.py` 均与 `e5765ed` 字节一致，哈希和 354 项源码首尾捕获见收据。

调用审计记录 8,518 次调用、10,012 条射线，relative 8,007、world 511；全部数值和输入别名一致。正式 T0 的 Ruff 与 31 项 pytest 通过。单车、8 车各 48 拍快照数组与悬架基线相同，短测为 0.7491/6.3854 秒；16 拍 profile 为 4.7406 秒，仅作诊断。

同进程 ABBA 四条完整 48 拍轨迹的全部快照数组相同，global/player/traffic 的 contact_epoch 均为零。旧组 CPU 时间为 5.953125/6.671875 秒，新组为 6.609375/6.21875 秒，没有稳定节省，故拒绝该试验且未运行 T1。墙钟和profile时间都是诊断数据，不代表 FPS 或前台 Gate。

所有 `cylinder-query-*` 原始材料、完整 T0、profile 目录及悬架快照基线均已保存。大型 JSON 与 profile 使用 `mtime=0` gzip，`.log` 原样转为 `.txt` 并保留原名和 SHA。

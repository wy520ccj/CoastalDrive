# 四轮接点数值块归档

基线为 `ab204a9`。独立旧DLL来自该提交的 `wheel_contact_kernels.c`，模块另名为 `_contact_system_old`；只改模块定义名与初始化符号，MSVC 使用 `/fp:strict /utf-8`。原源、重命名源、setup、构建日志、DLL及中间构建件均保存在 `baseline/`。

独立审计核对 5,753 次调用：圆柱 5,268、混合 283、无运动学 202；所有输出梯度和对齐值的十六进制表示一致。标准 2×48 拍完整 Snapshot 与基线逐字段相同。单/九车短测为 0.7191207/5.1751292 秒，仅诊断数据，不代表 FPS 或前台性能。

T0 首次 Ruff 因 `suspension_kinematics.py` 导入排序 I001 失败，pytest 未运行。最终 T1 Ruff 通过，pytest 552 项通过（27.89 秒），三个固定种子分别 9.5/9.4/9.5 秒通过。profile 覆盖 16 个物理步，仅用于热点诊断。此次归档未运行物理或测试。

`contact-system-snapshots.py` 是否存在见 `receipt.json`。`manifest.json` 记录原始/归档 SHA 与压缩载荷 SHA；gzip 使用 mtime=0。

# 轮端解析导数原生化归档

在 `3693771` 基线上归档了 `mechanical_kernels.c` 与 `tire_drivetrain.py` 的未提交冻结状态。354项 `src/tests/tools` PY/C/PYD 哈希首尾一致。另有既存 `src/suspension_contacts.py` 修改保持原样，不在本次暂存范围。

独立旧Python解析导数对照实际8,840次调用，输出hex逐值相同：硬挡位8,676次、同步164次。快照证据显示单车/8车两个48拍完整Snapshot全部字段与 `contact-system-r1` 相同，短测0.6834875/4.8669462秒仅诊断，不是FPS。

审计试跑首轮37失败/303通过，原因是试验删掉了仍由 `correct_brakes` 使用的导入；r2为340通过并精确核对8,600次硬挡位调用，r3为377通过并核对完整8,840次。最终T0 Ruff报RUF059未使用局部变量 `local_response`，pytest未运行。最终T1 Ruff通过，pytest 752通过（148.96秒），三种子8.486/8.500/8.476秒通过。各轮原日志都已保留。

此次只归档已有记录，不运行测试、构建或物理。gzip快照使用mtime=0；`manifest.json`包含原件、归档件和解压载荷SHA。

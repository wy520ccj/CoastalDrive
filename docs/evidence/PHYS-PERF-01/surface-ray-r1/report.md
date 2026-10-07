# PHYS-PERF-01 surface-ray-r1

本版本将原射线查询的坐标变换和有序命中装配接入 C 数值 helper；reach 仍由 Python 原式 `sqrt(sum(square)) - radius` 计算。世界/native 的其他凸体扫掠和首个 hit 仍走原方法。审计为 40 个台架工况和 9 车 24 拍：15,148 射线、59,361 个支持面、15,894 个命中，其中 mesh 54,820、plane 59、box 4,482。结果中的 node 与 triangle 对象身份保持一致。

最终快照与 wheel-map 基线的单车、8 车各 48 拍字段一致，耗时分别为 0.8262243 秒与 8.1056910 秒；九车结果略慢于基线 8.1024 秒。该短测不支持稳定整车收益或 FPS 结论。16 拍 profile 为 6.0972 秒，基线为 6.5905 秒；`cylinder_suspension_rays` 为 1.3904 秒，基线为 1.8343 秒。profile 只用于定位。

T0 的 Ruff 与 40 项 pytest 通过。T1 的 Ruff、474 项 pytest（50.49 秒）和三个种子 headless 检查（15.87、14.53、14.81 秒）通过。首轮构建将 surfaces 宏按 tuple 处理，与真实 list 接口不符；在运行前已修正并重建，因此没有由该问题产生的运行失败。

本归档记录 HEAD `155aa87` 和未提交的 `suspension_contacts.py`、`wheel_contact_kernels.c`，源码哈希捕获稳定。原始 `.log` 以同字节 `.txt` 保存，并在收据中保留来源文件名。短时离屏数据不代表 FPS、前台 Gate 或人工验收；主目录 `33657dc` 的独立 T2 仍未完成。

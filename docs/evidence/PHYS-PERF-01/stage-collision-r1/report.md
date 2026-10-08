# PHYS-PERF-01 主目录 T2-r2 失败归档

归档保留主目录当前 `cb15abb` 的 355 项源码指纹（`src/tests/tools` 下 PY/C/PYD 与根 `setup.py`），起止SHA一致。T2-r2原summary记录启动指纹HEAD为 `01b99f3`、358项哈希；其中354项与当前捕获相重合的PY/C/PYD哈希一致。其余4项是该历史指纹中的JSON文件，根 `setup.py` 是当前额外捕获项。原summary、pytest/Ruff日志、r2启动器、pytest执行脚本、复用审核和节点列表均保存，见 `manifest.json`。

已有结果：Ruff通过；剩余pytest失败，日志末尾列出 `test_h1_vehicle.py::test_collision_wall_stops_car_without_tunneling`，267 passed、957 deselected，pytest报告3740.66秒；summary中的该检查计时3741.516秒。后续11项均为 `not_run`。失败输出记录共同末状态超过30次迭代，误差 `1.02141e-14`。归档只记载实际输出，不判断夹具或根因。

归档期间未运行测试或物理；T2-r2未通过阶段。

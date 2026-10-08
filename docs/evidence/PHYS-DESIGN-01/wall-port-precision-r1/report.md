# 主线墙端口精度修复归档

基线为 fa037c4。360项 `src/tests/tools` Python/C/PYD/JSON/GZ 与根 `setup.py` 指纹已在启动时捕获；当前指纹与运行中 PHYS-INTEGRATE-04-stage-T2 初始summary中的360项哈希逐项相同。此次仅复制T2初始summary和launcher/复用审核，不归档仍在写入的pytest日志。

归档完整的 `logs/physics/PHYS-DESIGN-01-wall`，包括stable-map、accurate-map与map-terms试验源码、setup、构建件/产物、错误构建和失败探针；原日志转换为同字节txt，快照及pyd/obj/lib/exp使用mtime=0 gzip。T0为74 passed/13.85s及Ruff通过。T1为767 passed/189.65s、Ruff通过，headless三种seed分别8.724/8.780/8.980s通过；T1 summary启动HEAD为dff36ee，运行时包含未提交源码与fixture，不能标作fa037c4启动。

数值证据：原四项简单求和虽7轮收敛，但100位Decimal比较误差为−1.89e−14，差于原始+5.67e−15，故未采纳。最终乘积低位fma、补偿及末次fma保持同一方程与原阈值，残差9.54e−18并在7轮收敛；试探线搜索尺度方案仍失败，未采用。保存输入在数值修复前以1.02141e−14失败，另一个早期构建错误将PyErr_Format格式用错并导致ValueError，原日志均保留。

两条48拍Snapshot比较记录53,218个数值差异，最大绝对差2.91e−11，非数值差异0；不得称逐字段相同。归档期间未运行物理或验证。`manifest.json`提供原件、归档和解压载荷SHA。

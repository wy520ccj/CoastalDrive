# Highway T2-r11 shape-bounds repair evidence

本目录归档主目录 `a7649d4` 加未提交边界修复这一版本的失败诊断、原始重放、候选遗漏证明、验证摘要和源码快照。逐件 SHA-256 与 gzip payload 校验见 [`receipt.json`](receipt.json)；源码哈希及工作区状态见 [`source-audit.json`](source-audit.json)。本次未运行测试、模拟或构建。

## 失败与定位证据

T2-r11 的原始 failure 位于 highway traffic-6，第3333拍，车辆位置约 `(-4.4999876, 1382.7055664, 0.4286962)`。原Python方程单子步重放复现20轮共同求解失败：2.08274 N、0 Nm、0.102191 N、12.2837 Ns/Nms。只对算术/几何/LU做进程内C替换的诊断捕获耗时758.891 s；它不是相同源码版本的T2续跑，不能作为Gate证据。

候选查询证明显示旧 `contactTest` 查询盒只返回 `highway-ground`，漏掉真实 `highway-road`（位置 `(0,1400,-0.10000000149)`）。独立有限网格精确求交命中比例为0.72485524/0.72485525。`contactTest` 是接触查询，不能充当候选包围盒判据。candidate-prefetch 重放通过4轮，但禁用缓存或仅保留同射线缓存都会重现原失败，说明这一轮不以缓存本身作为修复。

## 边界修复和验证范围

当前主目录从 Box、Plane、mesh 等原始形状的保守 bounds 直接筛选候选；随后仍做精确表面求交，不扩5cm覆盖、不依赖缓存。原方程重放4轮通过，法向残差 `1.82e-12 N`、悬架能量残差 `-1.85e-14 J`。原物理参数、20/30/64/96轮次及阈值保持。当前实现、两项测试、三个固定输入 fixture 和 `tools/validate.py` 映射均有点时副本。

修复前 `regression-before.log` 记录两个新增测试均失败；边界 T0 的 Ruff 与38项通过，T1 的 Ruff 与456项通过，headless种子0/17/23耗时44.063/44.385/42.965 s。该局部修复验证不等于完整T2 Gate：T2-r11失败项及其余1468个selected节点、14项后续check仍待恢复；隔离工作树后续 `static_shapes` 优化未纳入本证据。

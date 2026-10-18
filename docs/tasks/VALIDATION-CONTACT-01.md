# VALIDATION-CONTACT-01 当前悬架的静止接地验收

- 状态：done（当前采样/自动验收完成）；基线main/860b897，开始前干净。
- 触发：整批T2原667通过后GR86来源修复，续跑9通过后首败test_h1_vehicle静止接地。该测试及h1_benchmark仍直接读取原生射线；当前耦合悬架的实际接触在CarState.wheel_contacts。
- 范围：tests/test_h1_vehicle.py的静止接触采样，tools/h1_benchmark.py同一采样，必要证据/任务/续跑脚本；禁止改物理/参数/起步制动范围。
- 验收：先实测同一状态原生射线/权威四轮接触/法向力/接地点/悬架长度，保留旧失败；更新只读验收来源，原位置/长度/起步约束保持，补全四轮与静载核对；完整H1模块、实际benchmark与三种子。
- 后续：独立目录续跑尚未执行部分，明确前667+9复用；所有原失败保留，整批/人工Gate继续开放。

## 结果与接续

- 同一1800拍静止状态：原生射线四轮false，权威快照四轮true/各2943.000517N，静载总量/车重1.00000017567，悬架长0.33868785m，原位置0.41868785m保持；原测试/物理与250be45一致。证据contact-before.json。
- 测试与benchmark只改静止接触读取，保持原位置、接地点、悬架长度和所有起步/加减速/转弯/碰撞阈值；补四轮数量/静载±0.2%，未放宽条件。无生产物理改动。
- 普通T1完整H1 10项及0/17/23三种子通过；Double接地起步1项通过。命令`tools/validate.py T1 --tests tests/test_h1_vehicle.py --output logs/validation/VALIDATION-CONTACT-01-T1 --timeout 300`，Double通过run_sim_double执行指定静止节点。
- 实际`tools/h1_benchmark.py --output logs/VALIDATION-CONTACT-01/handling`通过：0–100 9.641667s、100–停46.234375m、22秒153.664439km/h、墙碰后原上界保持；完整json已归档。不是性能/人工驾驶结论。
- 原T2续跑的9通过/1首败保留；下一续跑明确复用667+9+本包10项=686项，以及同物理三种子/handling，2830项与未跑交通道路检查继续执行。证据[目录](../evidence/VALIDATION-CONTACT-01/)。仅本地提交。

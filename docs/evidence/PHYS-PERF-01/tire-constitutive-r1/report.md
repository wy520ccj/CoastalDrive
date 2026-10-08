# Tire constitutive 本构块归档

## 实现与兼容边界

本轮实质改动为 `src/mechanical_kernels.c`、`src/tire_compliance.py`、`src/tire_forces.py`；时间戳探针测试两项和两个工具中的 phase 协议文字随后调整。CPython `math.hypot` 继续调用原函数，不替换为 `libhypot`；能量核算与 Frame 传递保留原实现，所有能量、控制与误差阈值不变。两个假 M 文件 `src/suspension_contacts.py`、`src/wheel_contact_kernels.c` 原字节与 HEAD 一致，未计入修改。

本构审计对 combined/contact/Jacobian/rolling/sticking/sliding 六类调用分别为17,772 / 37,152 / 7,681 / 12,166 / 21,892 / 3,094，全部逐值相同。统计与审计输入保留在 `physics/tire-constitutive-audit.json`。

## 时间戳失败与复现

初始整合 T1 为750 passed、2 failed（pytest 170.16秒），三个 seed 当时均 not_run。两个失败来自 acceleration 与 constant-turn 探针：两处均断言 `force_contact_tick < sample_tick`，实际为 `241 == 241`。原 Python 基线进程重放得到相同失败，所以这不是本构提取造成的物理差异。

四个工况的实际外层接触tick、SI force与 post-Bullet sample 观测保留在 `compliance-timestamp-observations.json`：tick 240 是首个基线行，之后每个工况都记录241到252这12个样本行，四轮时戳均精确等于 `state.contact_tick`。因此测试按真实同tick协议改为精确相等；没有放宽数值容差。

主构成源码与首次 T1/快照时的 src 哈希一致；后续修复只涉及两项时间戳断言和两处phase协议文字，因此750个旧通过节点没有重跑。phase T0 的56项/Ruff通过；组合 T1 completion 去重后为782个不同通过节点（750旧通过加56新通过，扣除重复），补跑的三种子10.103、9.892、9.726秒均通过。初始T1失败、原 Python 重放、phase T0与completion摘要均保留。

## 完整快照与性能边界

0车和8车各48拍完整Snapshot与shared-solution基线逐字段相同。0.7526315/5.3735288秒以及16步profile数据仅为诊断，不是FPS或前台性能Gate。当前归档没有实时性能结论。

`close-tire-constitutive.py` 的首次调用因 `make_plan` 空 `areas/tests` 输入抛出 `ValueError`，检查项未运行。所给来源中未找到单独保存的CLI转录，因此只归档脚本并记录该执行边界，不补造日志。

## 来源与状态

基线HEAD为 `12ea82b`。354个 `src/tests/tools` `.py/.c/.pyd` 文件捕获起止哈希一致；当前 `src` 哈希也与首轮本构快照相符。大JSON以 `mtime=0` gzip封存，`.log`原字节改扩展名保存；`manifest.json`记录来源/归档/载荷SHA，`receipt.json`保存核验与版本边界。该功能块尚未并入main；当前只暂存本构三源码、探针测试、两工具协议文本及本证据和任务页，等待root确认提交。未运行新测试或模拟。

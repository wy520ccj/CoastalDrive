# PHYS-ROT-01 最终关闭分支轨迹核对

状态：**通过：正常游戏配置显式关闭转子输运时，冻结A全部既有Snapshot值逐单元精确相同。** 这是范围明确的兼容性核对，不替代PHYS-ROT-01其他工况验收。

冻结A来自 `PHYS-TIRE-04/final-validation-source-cg.zip`（SHA-256 `05e4947a55580d6f20949cc490903a9bb76e2a22fd709e16eb50a2666d1891d6`），使用此前相同A运行保留的原始轨迹 `frozen-a.json`。B由 `run_trace_explicit_off.py` 在当前源码运行。脚本直接执行 `config = dataclasses.replace(CAR, wheel_rotor_transport=False)`，并把这个配置传给 `Vehicle(..., config=config)`；结果也序列化这个明确关闭的 `config`。接口采用直接字段访问，没有 `hasattr` / `getattr` 或默认值探测。之前的 `run_trace.py` 保持原样，首次失败记录仍在 `compat-off-initial/`。

两边使用正常游戏模式完整默认车辆参数、Z-up Bullet平面与120Hz固定步。加速、转向、倒车各运行120 tick，保存tick 0初态和每tick的完整 `vehicle.snapshot()`。转向从tick 12开始输入。比较器对A每个tick实际存在的全部递归叶字段与B对应字段进行精确相等比较；接触及车轮姿态字段会随轨迹产生，计数按每tick实际A字段数量累加，允许B新增字段。

| 工况 | 快照数 | 对比旧字段单元 | 不同单元 | 首差 |
|---|---:|---:|---:|---|
| 加速 | 121 | 40,872 | 0 | 无 |
| 转向 | 121 | 40,880 | 0 | 无 |
| 倒车 | 121 | 40,880 | 0 | 无 |
| **总计** | **363** | **122,632** | **0** | **无** |

冻结A初始Snapshot有288个递归叶字段；B对应初始Snapshot有356个，其中新增字段不会缩小A字段的比较范围。所有公共车辆配置值一致。比较明细与字段表见 `comparison.json`，B实际配置与两组逐tick轨迹分别见 `current-b-explicit-off.json` 和 `frozen-a.json`。

开始时Git HEAD为 `ec469b7626bc211f29969da3c07b3c1e59d730af`。运行前后均有75个 `src/**/*.py` 文件；所有文件SHA-256逐项一致，开始/结束清单SHA-256均为 `4566E104C9D4A6405CD325EE497F6D26375E22424FCA18F46542E833B677C872`，清单为 `source-start-files.json` 与 `source-end-files.json`。本轮没有修改 `src/`、`tests/` 或 `tools/`，没有执行T1，也没有提交或推送。

# PHYS-ROT-01 关闭转子输运兼容性初检

状态：**首次严格对照失败；临时结果**。只读运行，未修改 `src/`、`tests/` 或 `tools/`，未提交/推送，也未执行 T1。

## 方法

- A 使用 `docs/evidence/PHYS-TIRE-04/final-validation-source-cg.zip` 解压到独立临时目录运行；归档 SHA-256：`05e4947a55580d6f20949cc490903a9bb76e2a22fd709e16eb50a2666d1891d6`。
- B 使用运行时主工作树。两边采用各自冻结/当前默认 `CAR` 的正常游戏配置、同一120Hz Bullet平面世界及同一120 tick输入；转向在tick 12开始输入。每个工况保留tick 0初始状态和每tick完整 `asdict(vehicle.snapshot())`。命令见 `run_trace.py`，原始轨迹为 `frozen-a.json`、`current-b.json`。
- 对比器以A每个tick的全部递归快照叶字段为准，逐值精确相等比较；不因B新增字段而减少A字段范围。A/B公共车辆配置逐值检查。命令：

  ```powershell
  .venv/Scripts/python.exe -X utf8 docs/evidence/PHYS-ROT-01/compat-off-initial/run_trace.py --source <冻结A临时目录>/src --output docs/evidence/PHYS-ROT-01/compat-off-initial/frozen-a.json
  .venv/Scripts/python.exe -X utf8 docs/evidence/PHYS-ROT-01/compat-off-initial/run_trace.py --source src --output docs/evidence/PHYS-ROT-01/compat-off-initial/current-b.json
  .venv/Scripts/python.exe -X utf8 docs/evidence/PHYS-ROT-01/compat-off-initial/compare_traces.py docs/evidence/PHYS-ROT-01/compat-off-initial
  ```

## 结果

冻结A与当前B共有的车辆参数完全相同，B默认 `wheel_rotor_transport=False`。A有288个递归快照叶字段；这些旧字段在B中全部存在。B额外提供44个叶字段。三条轨迹均有121个快照（初始状态加120 tick）。

| 工况 | 首次不同位置 | 首次差异 A → B | 不同单元 | 最大绝对差 |
|---|---|---|---:|---:|
| 加速 | tick 8，`wheel_dynamics.0.relative_omega` | 0.012006881646811962 → 0.012006881215498422 | 16 | 4.31313651461096e-10 |
| 转向 | tick 11，`wheel_dynamics.0.relative_omega` | 0.007268450688570738 → 0.007268450623714895 | 430 | 1.4071240284074804e-9 |
| 倒车 | tick 10，`wheel_dynamics.0.relative_omega` | -0.008905880153179169 → -0.008905880283520129 | 84 | 4.400928510506219e-10 |

全部不等单元只出现在四轮 `wheel_dynamics[*].relative_omega`。严格浮点零差异条件未满足。对照详情、每字段计数及所有首次差异保存在 `comparison.json`。首次失败轨迹没有覆盖。

## 首差分析与建议

冻结A在 `Tires.observe()` 中计算 `relative_omega` 的表达式为 `self.omega[index] + angular.dot(axle)`；B在关闭开关时仍走同一 Panda `Vec3.dot` 表达式。公共配置逐值相同，A旧字段齐全，而其他旧快照字段保持相等。当前证据因此只证明相对轮速诊断读数存在约1e-9量级差异，不能据此认定宏观车辆轨迹已分叉，也不能从现有快照判断它来自车身未暴露的横滚/俯仰角速度还是其接触轴向量。

建议下一步在证据专用runner中临时追加Bullet原始角速度XYZ、四轮 `axle` 和 `angular.dot(axle)` 的逐tick旁路读数，先定位首差来源。若变化来自转子接入后的共享 `advance_coupled` 路径，则在 `wheel_rotor_transport=False` 下保留冻结A原有求解/运算路径；不要把比较容差放宽，也不要先用量化 `relative_omega` 掩盖差异。此建议尚未实施。

## 源码与时序限制

- 起始时记录的 Git HEAD：`ec469b7626bc211f29969da3c07b3c1e59d730af`；当时 `src/vehicle.py` SHA-256：`23FF55921CF2A51DE50102A86594D95CFBF7635530F0BD793E8C7DE502150911`。
- 本任务开始状态显示 `tools/validate.py` 无改动、没有 `tests/test_rotor_transport.py`；轨迹运行后观察到该测试新增且 `tools/validate.py` 已改动，说明主线与本只读验证并行变化。当前B轨迹不得视为主线稳定版本结果。
- 由于启动时未保存完整 `src/` 文件树哈希清单，无法给出可信的完整开始哈希。结束时逐文件 SHA-256 保存在 `source-end-files.json`；结束 Git HEAD 仍为上列值。结束哈希只描述收尾时工作树，不能反推轨迹运行瞬间源码。
- `frozen-a-temp-path.txt` 指向本机临时目录中的冻结A解压路径。命令日志保存在 `frozen-a.log`、`current-b.log`。

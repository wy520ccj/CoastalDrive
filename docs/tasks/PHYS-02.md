# PHYS-02 四轮接触诊断

- 状态：done（本功能自动验证完成；小阶段T2未通过旧基线护栏项）
- 基线：6fbcd36 上的 PHYS-01，见 PHYS-01/standard-B
- 目标：只读记录四轮动态支撑与悬架，保持驾驶受力模型。
- 实施：GPT-6.1-Sol low 完成数据类型、读取函数和真实 Bullet 测试；主代理接入生命周期、快照插值和重定位。

## 范围与结果

新增 `vehicle_contacts.py` 与 `WheelContactState`，Vehicle 在每次 `after_step` 缓存四轮诊断。初建/reset 的空 tuple 表示尚未采样，物理步后空中轮的法线/接触点/skid/材料为 None，法向支撑为零。重定位平移接触点，插值保留最新完整测量而不插值接触标志或支撑力。

`suspension_force` 为 Bullet 原始悬架力 N；`normal_load` 是受最大悬架力限制、沿接触法线实际施加的力 N，其世界竖直分量为 `normal_load * contact_normal[2]`。长度与压缩单位 m。`skid` 是 Bullet 的无量纲摩擦冲量缩减系数，不能作为物理滑转率 κ。

诊断未替代原准静态轴荷纵向限力，也未修改悬架参数。正式快照携带四轮诊断与自上次 reset 起的 `contact_tick`；只读车身感知快照省略轮数据。

## 验证

- 静置四轮法向支撑各约 2943 N，总和与 1200×9.81 一致。
- 真实斜面横向载荷差、离地、原始悬架力超限与实际截断、reset、新测量、插值与原点平移共 7 项针对测试通过。
- 与 PHYS-01 对照，七工况汇总全部相同，1167个20 Hz记录样本的64个共同物理/控制字段逐值相同。新 `contact_tick` 单列是新增采样元数据，不作为旧车动力学对照。
- `sample-equivalence.json` 保存了误把旧版默认 contact_tick=0 纳入比较的首次检查；`sample-equivalence-final.json` 为排除该元数据后的正式结论。物理读数未改动。
- T1：vehicle/core/traffic/road/appearance/gameplay/audio，253项通过；三种子1200tick和0/23弯坡各30s通过。证据：`docs/evidence/PHYS-02/t1/`。

不扩展UI和音频。此项为观测功能，诊断接口的自动部分已确认；整体物理手感仍需用户实际驾驶。

提交范围：基线6fbcd36至本任务实施提交（Git提交包含这三个任务包与接触/标准试验代码，未推送）。

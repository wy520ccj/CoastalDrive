# SIM-UNSPRUNG-01 质量/法向块节点

基线ce0bf71，独立树codex/simulation-fidelity。**任务in_progress，新自由度未进入Simulation**；本证据仅是全车接入所需的机械节点，不是整车新悬架验收。

- `mass-T0`：`.venv/Scripts/python.exe tools/validate.py T0 --tests tests/test_unsprung_dynamics.py tests/test_unsprung_contact.py tests/test_unsprung_modes.py --output logs/validation/SIM-UNSPRUNG-01-mass-T0 --timeout 120`，21项/Ruff通过。覆盖独立质量/CG/惯量重组、锁止动能、实际点速度/虚功、自由落体、科氏/离心能量与平动/角动量、质量导数、静载/离地/止挡/非对称阻尼/径向正压缩力及两质量模态解析对照。
- `mass-reference`：`tools/physics/unsprung_mass_check.py --output logs/SIM-UNSPRUNG-01/mass-reference-r1`，从真实参考车初始化读取已有配置与轮心快照，然后进行25/40/65kg假设质量和200000N/m假设径向刚度的算子分析。source-snapshot.json、原配置/来源完整指纹在报告；没有让新算子偷偷修改默认车。
- 相同1200kg总量分出的簧上质量1100/1040/940kg；四个高频模态约15.87～16.27 / 12.56～12.90 / 9.87～10.19Hz。频率来自冻结构型线性化，非实车测量、非实际新世界轮跳轨迹，不能推断完整颠簸制动结果。
- 首次质量节点3/10失败：两项内部力相加/减的末位浮点功残差，改成解析相消；一项极小中心差分的惯量相减舍入，改为五点差分，原误差门槛保持。之后10/10、法向7/7、模态4/4及最终21项T0通过。没有降低原生产求解阈值。

未运行/未实现：有限姿态全车联合迭代、真实路面新接点、独立轮心状态的120Hz推进、曲轴/输入轴/四轮/从动轴端口扩展、原生一致、重开/记录/GUI、实际颠簸和制动、T1/T2/T3及人工/实测Gate。任务包继续列出完整要求，不能用本节点替代。[推导与接入问题](../../unsprung-dynamics.md)。

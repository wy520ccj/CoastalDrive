# SIM-UNSPRUNG-01 质量/法向块节点

基线ce0bf71，独立树codex/simulation-fidelity。**任务in_progress，新自由度未进入Simulation**；本证据仅是全车接入所需的机械节点，不是整车新悬架验收。

- `mass-T0`：`.venv/Scripts/python.exe tools/validate.py T0 --tests tests/test_unsprung_dynamics.py tests/test_unsprung_contact.py tests/test_unsprung_modes.py --output logs/validation/SIM-UNSPRUNG-01-mass-T0 --timeout 120`，21项/Ruff通过。覆盖独立质量/CG/惯量重组、锁止动能、实际点速度/虚功、自由落体、科氏/离心能量与平动/角动量、质量导数、静载/离地/止挡/非对称阻尼/径向正压缩力及两质量模态解析对照。
- `mass-reference`：`tools/physics/unsprung_mass_check.py --output logs/SIM-UNSPRUNG-01/mass-reference-r1`，从真实参考车初始化读取已有配置与轮心快照，然后进行25/40/65kg假设质量和200000N/m假设径向刚度的算子分析。source-snapshot.json、原配置/来源完整指纹在报告；没有让新算子偷偷修改默认车。
- 相同1200kg总量分出的簧上质量1100/1040/940kg；四个高频模态约15.87～16.27 / 12.56～12.90 / 9.87～10.19Hz。频率来自冻结构型线性化，非实车测量、非实际新世界轮跳轨迹，不能推断完整颠簸制动结果。
- 首次质量节点3/10失败：两项内部力相加/减的末位浮点功残差，改成解析相消；一项极小中心差分的惯量相减舍入，改为五点差分，原误差门槛保持。之后10/10、法向7/7、模态4/4及最终21项T0通过。没有降低原生产求解阈值。

未运行/未实现：有限姿态全车联合迭代、真实路面新接点、独立轮心状态的120Hz推进、曲轴/输入轴/四轮/从动轴端口扩展、原生一致、重开/记录/GUI、实际颠簸和制动、T1/T2/T3及人工/实测Gate。任务包继续列出完整要求，不能用本节点替代。[推导与接入问题](../../unsprung-dynamics.md)。

## 2026-10-14共同机械节点

十六维惯量/真实表面点力学端口与34未知量的共同残差已实现；上文的传动/切向端口扩展已完成**冻结构型部分**，生产世界与有限姿态仍未接入。

- `joint-T0`：`.venv/Scripts/python.exe tools/validate.py T0 --tests tests/test_unsprung_dynamics.py tests/test_unsprung_contact.py tests/test_unsprung_modes.py tests/test_unsprung_joint.py --output logs/validation/SIM-UNSPRUNG-01-joint-T0 --timeout 120`，35项/Ruff通过。原法向材料抽为共享函数后11项先通过；新共同节点最初9项通过、Ruff两未用测试变量已修复；随后13项边界/独立能量通过，最终加入完整输入复算。生产C内核未修改/重建。
- `joint-powered-complete`：`tools/physics/unsprung_joint_check.py --output logs/SIM-UNSPRUNG-01/joint-powered-complete-r3`。真实准备输入、假设参数全部数字、旧预载/动力状态、预测及来源保存；4轮求解，力9.51e−10N/端口2.32e−13N·m、冻结能量误差1.68e−11J，当前测试可直接读完整JSON复算。不是实际新世界行驶试验。
- `joint-powered`早期预测与数值相同，但source-input未完整保存新假设数组；保留原记录。补齐独立复算输入后生成完整新版本，没有修改/回填早期文件。最早空挡节点在logs/SIM-UNSPRUNG-01/joint-real-input-r1，只用于接口探索，不作为有限传动验收。
- `native-gyro-observation.json`：本地Panda1.10.16、1/240s、零重力/外矩/阻尼、I=(2,3,4)自由转动，Ω变化与gyro方向一致。该观察证实原生已处理刚体gyro，不证明新有限姿态积分完成。

新的共同块仍冻结构型，known中的惯性偏置功不是物理外界功。相对轮心初速零、40kg/200000N/m/500Ns/m假设及旧预载不构成实测标定或新静平衡。下一CG/主轴/有限姿态与真实几何接入；任务in_progress，整体目标active。

## 2026-10-14后续原生世界

质量/CG/主轴/真实四轮心与道路已进入独立的五刚体Bullet验证世界，43项T0及实际实体凸起轨迹、有限原生精度的开放项、完整输入/执行源码/图表见[native-world](native-world/README.md)。该节点使用新的实际轮心动量与静平衡初态，上面的冻结/旧预载节点保持原版本证据。生产Vehicle/Simulation/Snapshot/记录/UI仍未安装，不提升任务或整体Gate。

## 后续正式链施工

在上述原生节点之后，已初步接入正式Simulation/Vehicle/120Hz/执行器/Snapshot数值包、生命周期及Lab保存载入精确复算，66项T0通过；新参数数学说明与显式开发预览配置见[production](production/README.md)。旧节点保留其时点结论，新机制默认关闭，完整能量/工程信号/颠簸制动/T1及实测/人工Gate仍开放。

# SIM-UNSPRUNG-01 原生机械世界节点

基线de56ab8，codex/simulation-fidelity独立树；任务in_progress。**生产Vehicle/Simulation/Snapshot/记录/UI尚未安装**；这是完整质量/导向与实体道路的实际运行节点，不是新工作台默认物理或完整有限姿态Gate。

`T0`：`.venv/Scripts/python.exe tools/validate.py T0 --tests tests/test_unsprung_dynamics.py tests/test_unsprung_contact.py tests/test_unsprung_modes.py tests/test_unsprung_joint.py tests/test_unsprung_body.py tests/test_unsprung_geometry.py --output logs/validation/SIM-UNSPRUNG-01-native-T0 --timeout 120`。43项/Ruff通过；新质量/形状/惯量映射、真实四轮质量与自由导向、静态支撑、首拍侧向传力、行程力臂角动量、外墙碰撞、实际路面压缩/加载半径及非一致轮心初速独立能量纳入。414项旧生产T1不重跑/不移作新世界验收；新T1/T2/T3/GUI未跑。

实际源命令：`.venv/Scripts/python.exe tools/physics/unsprung_world_check.py --output logs/SIM-UNSPRUNG-01/native-physical-step2 --duration .8 --substeps 2`；其余分别使用`--substeps 4/8`或`--mass 25/65`，不同输出目录。每个算例重新创建自己的实际原生世界，真实Plane和10mm高左侧Box凸起；5m/s、1200kg总量、40kg或25/65kg轮端。径向刚度200000N/m、阻尼500Ns/m为假设。空挡/零离合、零滚阻/风载/转向/拖距隔离垂向机制，初始实际从动轴转速与机械约束一致；运行中没有手设轮心/车身速度或位置。

| 轮端质量 / kg | 最小轮荷 / N | 最大轮荷 / N | 轮心相对速度峰值 / m/s | 簧上垂向加速度RMS / m/s² |
|---|---:|---:|---:|---:|
| 25 | 898.966 | 4771.684 | 0.334775 | 0.390045 |
| 40 | 765.607 | 4844.571 | 0.279863 | 0.406875 |
| 65 | 634.148 | 4921.748 | 0.230522 | 0.438071 |

簧上质量、CG与静态车高随相同总量的质量分配变化；未对车高重新调弹簧预载。表格仅用于完整机制的设计A/B，参数不是实测，不宣称65kg比25kg更真实或更好。

| 40kg子步 | 局部冻结能量误差峰值 / J | 原生十维机械动能增量与冻结预测差 / J | 原生末速度差 / m/s或rad/s | 轮心横向位置差 / m |
|---|---:|---:|---:|---:|
| 2 | 1.28e−11 | 0.007227 | 2.92e−6 | 5.98e−7 |
| 4 | 1.50e−11 | 0.004538 | 6.75e−6 | 7.01e−7 |
| 8 | 1.49e−11 | 0.003521 | 2.15e−5 | 1.25e−6 |

后面三列是原生提交/有限姿态的诊断差，不能替代外界功、全部势能/转子/耗散的全车能量账。个别差不单调；未声明有限姿态/收敛Gate通过。接触本构残差保持<1e−5N，动量/端口原门槛1e−9未降。五组世界均无外界车身碰撞参与颠簸支撑，关闭后0体/0导向。

完整输入、轨迹、摘要、执行源码副本及原生DLL指纹见`manifest.json`；所有input.json中的执行源码SHA与source副本一致。`native-mass-comparison.png`由`tools/physics/unsprung_plot.py`读取保存CSV绘制，实际看图确认字与注释无遮挡。不是实验台GUI验收。

`raw-node-evidence.zip`保留运行时原始字节、源码与manifest，防止Git的Windows换行转换改变文件SHA；校验以压缩包内字节为准，旁边文本/CSV用于阅读。打包后再次核对五组input.json的全部执行源码SHA，均匹配包内source。压缩包不含事后撰写的此README，也不覆盖运行输入。

中间失败/修正记录：

- 首次原生4项测试2失败：不等轮端质量/非对角主轴、10m自由落体的个别轮心初速误差约5.92e−6m/s，未满足5e−7；另一次首拍横向冲量完全未传给父体，通用导向零误差时缺限位行。后者通过零目标速度的双边导向修正，阈值不变。自由落体严格解析检查改为对称参考极限，非对角映射另外核对，**不等质量失败仍开放**并单独保留`native-unequal-freefall.json`。
- 行程变化下的反力矩使用实际轮心力臂，连接原点沿自由轴更新；独立角动量2e−7门槛通过，没有移动刚体或关闭外界碰撞。
- 增加实际轮心初速后，3个新动能增量断言曾受到大数相减的约5～9e−11舍入影响。生产共同块与独立验证均改为各质量/轴的Δv·(v1+v0)增量，原4e−11断言和3e−8能量门槛保持，最终通过。
- 早期contactTest返回父体/轮心几何重叠4个，不能视为真实外界求解接触；诊断改读原生manifold外界对，外墙真实碰撞另测。早期logs中的body_contacts/actual_energy_defect仅作探索，保存后没有改写；此处使用重新运行的physical节点。
- 初期空挡测试从动轴初速零，不是无跳变滚动初态；初始化修正为同一机械约束实际值。源输入旧版本与新版本分开，表格仅取完整physical节点。原生动能增量对照也使用实际旧轮心动能作为基线，没有把不一致初速投影后丢失的储能当成物理输入。

下一：有限姿态/导向精度与完整功/能量；生产Vehicle/120Hz状态/重开/记录/UI接入，完整颠簸/制动/原生Python/T1及用户体验。总体目标active；main另一AI游戏施工保持，未推送。

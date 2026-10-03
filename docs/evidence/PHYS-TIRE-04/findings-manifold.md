# 冻结源码车身平面接触诊断

独立子进程只导入`mechanical-rigid/baseline-source`中归档f2c1450的src/tools。成功四条为轮胎2/8子步×Bullet solver10/80，每条132tick(1.1s)，原初始化与方程时序不变。ConfigVariableInt在World构造前设置，保存PRC值/说明及实际模块路径。10iter两条ESC CSV前133行、393个共享字段与旧轨迹逐单元严格相同，各0差；冻结源码前后SHA一致。80iter仅诊断，不是生产默认建议。

原始逐tick pre/post姿态、速度、世界/车身up角速、施力状态与contact、manifold normal/distance/normal及两切向冲量，连同完整ESC CSV/config，保存于`recontact-manifold-v2/`。API成员与运行时docstring已核对并保存。首轮观测器错误把离地工况当成240tick静置，产生空观测IndexError；失败及not_run保留在`recontact-manifold/`，随后纠正观测计数，无物理方程变更。

tick80首次出现有正求解冲量的车身plane接点。on2/solver10唯一点位于车身右侧前下角附近，world A位置(1.04999995,20.33933449,0.03466368)m，normal=(0,0,1)，normal impulse436.773254Ns，lateral1方向近+Y、impulse−109.193314Ns。distance为正0.034664m，但有实际求解冲量，不能因正distance排除该接触约束。nodeA是车身、nodeB是平面，因此报告法线/切向冲量直接作用于车身。

| tick80 on2/10量 | x | y | z |
|---|---:|---:|---:|
| 实际Δp Ns | 约0 | −113.156891 | 438.673218 |
| manifold ΣJ Ns | 约0 | −109.193306 | 436.773254 |
| 实际ΔL Nms | 991.270203 | −458.156128 | −111.386261 |
| manifold Σr×J Nms，pre-CG臂 | 884.737915 | −458.611908 | −114.652969 |
| 悬架ΣJ Ns | 0 | 0 | 100 |
| 悬架Σr×J Nms，post-CG臂 | 105.495644 | −0.197229 | 0 |

完成raycast前轮Fn各6000N、后轮0，按Fn×dt重建悬架向上100Ns；重力−98.1Ns、原外力y冲量−3.963722Ns。加manifold后，线动量剩余约(0,+0.000138,−0.0000366)Ns。角动量剩余约(+1.036644,+0.653009,+3.266708)Nms；单精度、陀螺/积分姿态变化、碰撞pre臂/悬架post臂时序及原外力预测不能完全从manifold拆开，不能把剩余全称碰撞或用它宣称新门槛通过。

接点正normal冲量在world z不直接产生z角冲量，却在右侧产生显著world y角冲量；切向负Y冲量在右侧产生负world z角冲量，符号与重建ΔL方向一致。完成world angular.z由0变+0.062769rad/s，而body-up yaw由0变−0.084082rad/s；大俯仰和侧倾下不能只靠world angular.z符号判断接触角动量的符号。

solver80未改善首次扰动：tick80与10iter完全相同；两种轮胎步数均从tick81开始出现solver10/80微差，tick132 world yaw(on2)为−0.042449255/−0.042449158，on8为−0.043249533/−0.043249551rad/s。即早期2/8差仍约0.0008003rad/s，80iter没有消除。现有短诊断定位到真实单点车身平面冲量触发的角扰动，与先前仅轮胎/轮荷表相互印证；不从132tick结果推断6秒全部闭环已验收，也不改全局solver配置。

逐点冲量、重建原始量、既有轨迹等同性与10/80比较均保留原数据。悬架重建可由输出目录中的`reconstruct_impulses.py`只读重复计算；Bullet2.84悬架更新确切顺序仍由主线按对应源码复核。

## 有限box短几何对照

`recontact-box-short/`新增仅2/8子步各132tick、solver10的冻结子进程。唯一创建差异是ground由无限plane变为half-extents(1000,1000,.5)m的厚box，ground位置z=−.5，顶面仍z=0；mask、重力、车体、配置、输入和初值相同。冻结源码前后SHA一致。

box首次车身正冲量manifold出现在tick82，tick80没有车身manifold。box n8 tick80 world yaw约5.22e−7rad/s、两前轮完成Fn均6000N；n2为+0.0105818rad/s，完成左前raycast丢接触Fn0、右前6000N，body-up yaw−0.0030861rad/s。n2的该处角运动已不能解释成车身plane单点冲量，说明射线悬架本身的几何/数值差异需要一起看。

tick82 box车身manifold有左右两个接点。n8两点normal impulse1121.934/1121.901Ns，近左右对称；n2因已有侧倾，两点为1201.871/1122.859Ns。box的raycast法线xy分量约1e−4，非plane的严格(0,0,1)，且tick80–83出现单侧轮raycast接触缺失。因此该有限大box不是纯“保持完全相同轮射线的多点车身plane接触”实验，不能凭首帧横摆变小声称fixture或生产已修复。

两条最大车体中心|x|/|y|为28.91/28.83m，远在±1000m范围内。现有首车身接点法线向上、B接点在上表面附近，无边界/底面接触证据；有限厚度与无限plane的几何和碰撞/射线算法差异仍明确保留。未跑box完整6秒矩阵，此阶段短结果仅用于主线判断追加试验价值。

## 静态平三角mesh与实际射线补证

新增`recontact-mesh-short/`仅n2/n8各132tick。两片+Z绕向的静态三角形覆盖[−1000,1000]²，顶点z全0，共边为x=y；原冻结车辆/输入/初值/重力/mask及solver10不变。`bullet-split-impulse`原默认False的值与说明另行读取核对。运行前后冻结源码SHA一致，无长矩阵或生产配置修改。

mesh中全部有效wheel raycast normal严格为(0,0,1)，没有大convex box的约1e−4水平法线噪声。tick78–80两前轮hardpoint.z分别约0.514059/0.461412/0.409209m，均双侧有效、轮荷相同、完成yaw0；后轮尚在射线可达范围外。首车身正冲量manifold改为tick81，在triangle index1只有一接点，位置近车身中线：n2 x≈+9.88e−5m、normal impulse2204.248Ns；n8 x≈−3.47e−5m、normal impulse2202.905Ns。完成world yaw分别−0.00157818/−0.00161767rad/s；仍有微小角扰动，没有宣称严格零横摆。mesh全部正冲量车身接点距共享对角线最小13.526/12.808m，不在共边附近；无两片三角重复正冲量接触证据。凸box返回的index整数没有三角形含义，未用于共边判断。

为补实射线数据，独立目录`recontact-box-rays-short/`明确重跑旧box n2/n8各132tick；完整ESC CSV与`recontact-box-short/`逐行逐字段严格一致，原数据未覆盖。保存实际hardPointWs、directionWs、contactPointWs/normal、悬架length、rest length、radius及contact flag，全部按经核对的BulletWheelRaycastInfo接口直接读取。

box n2 tick80左前失接触时hardpoint.z=0.423500m，direction.z≈−0.985736，rest+radius=0.73m，实际最大射线终点z≈−0.296m；tick81左前仍丢接触，hardpoint.z=0.373227m。n8 tick82右前丢接触时hardpoint.z=0.363746m。原点均明显位于顶面上方，射线跨过z=0、横向也远在box范围内，排除“射线原点已经真实沉入地面”的解释。这些缺失指向大convex box射线数值/算法路径，不能用该fixture替代原plane证据。

mesh n2/n8 tick78–84所有应可触前轮都保持接触；后轮tick82双侧开始接触，法线严格水平。mesh的最初接触/射线证据比大box可信，但132tick末累计航向n2约−0.005988°、n8约−0.180338°，尚不能用短窗断言完整闭环收敛或生产已修复。没有跑6秒矩阵；仅保留几何隔离的事实供主线决定。

`geometry-ray-audit.json`保留四条关键tick78–84表、射线终点重建、rawSHA及box补跑等同性。contactFlag=False时Bullet normal/point为缓存/备用方向，不能作为有效表面法线统计；“严格水平”只统计有效接触法线。

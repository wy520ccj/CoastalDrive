# CG投影支撑分区原型：重建记录

本目录保存以当时 `vehicle_collision.py` SHA-256 `2e6d2438f825be5884199dda21b02e6858cfac666642a60a9af7411d396a1a59` 为依据的中心分区基线重跑，以及新的CG投影分区比较。这里的 `summary.json` 是明确标记的重建运行，不是原首轮运行的恢复件。原 `cg-support-partition-prototype/summary.json` 在共享生产源码切换期间被后一次运行覆盖，首轮全量原始摘要无法恢复；覆盖后的文件已原样另存为 [post-production-change-rerun.json](post-production-change-rerun.json)，没有将其冒充首轮证据。

独立的原型重建脚本 [cg-support-partition-reconstruction.py](cg-support-partition-reconstruction.py) 按任务公式生成分区：轴边界是 `center±half_extent`，仅在 `low<0<high` 时于0处分段；子体半尺寸与中心由区间端点的半差、均值计算；中心小于0取符号−1，否则+1。变换使用 `Mat4 diag(-sx,-sy,sx*sy)`，平移到子体中心、`z=body_center.z`，margin为0。车身先读wholeBox惯量，随后保持 `REFERENCE_CAR.body_inertia`。台架没有姿态夹紧或步后修正。

四种配置各比较旧中心四Box基线和CG投影原型，均使用同一无限水平面、初始CG `(0,0,2.5)m`、重力 `−9.81m/s²` 与240个 `1/120s` Bullet步；完整每tick的position、HPR、角速度、线速度、manifold接点、法向/切向冲量及配置与几何数据见 [summary.json](summary.json)。

| 前轴份额 / 轴距 | 改动前中心分区首次冲击：接点y / J / ωx / pitch | CG分区原型首次冲击：接点y / J / ωx / pitch | 子体数：旧/原型 |
|---|---|---|---:|
| 50% / 2.2m | 0 / 6991.996Ns / 0 / 0° | 0 / 6991.996Ns / 0 / 0° | 4 / 4 |
| 60% / 2.2m | −0.2200m / 6786.652Ns / −0.77782rad/s / −0.37138° | 约0m / 6991.996Ns / 约0 / 约0° | 4 / 4 |
| 40% / 2.2m | +0.2200m / 6786.652Ns / +0.77782rad/s / +0.37138° | 约0m / 6991.996Ns / 约0 / 约0° | 4 / 4 |
| 90% / 6.0m，CG在外廓外 | −2.4000m / 1519.726Ns / −1.90009rad/s / −0.90723° | −0.25m外侧边缘 / 6729.082Ns / −0.87638rad/s / −0.41844° | 4 / 2 |

每条first-impact数据取首次正法向冲量tick86。50%原型与改动前基线的BulletBox类型、半尺寸、零margin、精确变换矩阵、显式惯量逐项一致；另外的默认当前生产核对见 [cg-default-native-equivalence.json](../cg-default-native-equivalence.json) 与 [reference-parameters-cg-partition.json](../reference-parameters-cg-partition.json)，完整配置、形状读回、惯量、静置位置和轮读数与旧参考导出逐项一致。

40%、50%、60%时CG投影位于外廓内，原型首个 `ωx` 与pitch均近零。90%/6m时body中心y为−2.4m、名义外廓y范围`[−4.55,−0.25]m`，CG不在外廓内；原型不夹紧或添加CG切面，使用较近的真实外侧边缘 `y=−0.25m`，首撞仍产生可测倾转。主代理后续的 [当前生产垂直冲击矩阵](../cg-production-impact/summary.json)显示新生产算法在40/50/60%均保持近零pitch（<1e−6°）和小roll（<4e−6°），90%/6m仍在y=−0.25m实际边缘冲击并产生 `ωx≈−0.87638rad/s`。这些是限定台架证据，不构成T1/T2结论。

几何审计逐个变换实际八个外角点，比较总AABB和体积，并以OBB SAT检查接缝。数学区间构造没有正体积交叠；Panda `TransformState` 的浮点四元数往返在实际读回变换留下微小接缝误差：SAT正穿透最大 `4.59e−8m`，整体AABB误差最大 `1.91e−7m`，长度误差均小于现有 `2e−5m`几何阈值。保守AABB交叠候选体积最大 `4.75e−7m³`；子体体积和与名义体积最大差 `8.76e−7m³`，相对名义体积约1.16e−7，低于既有1e−6体积相对误差门槛。体积与长度分别核对，原生浮点变换不称严格零正体积交叠；逐试验数值保留在摘要内。

运行命令、行数、source SHA前后核对及文件SHA见 [run-receipt.json](run-receipt.json)。

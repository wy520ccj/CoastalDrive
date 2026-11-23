# 山脊内部边修正候选

2026-11-06，基线HEAD `15c321f5`。新增 [Panda3D 源码补丁](../../../tools/physics/panda-road-internal-edges.patch)，先在隔离 SDK 和试车进程验证，随后接入本机游戏与试玩启动器。任务继续 in_progress。

补丁沿用 [Bullet 2.84 的内部边接口](https://raw.githubusercontent.com/bulletphysics/bullet3/2.84/src/BulletCollision/CollisionDispatch/btInternalEdgeUtility.h)。单形状的静态铺装网格显式建立三角形邻接，Bullet 在求解前调整落在共享边附近的法线。邻接随形状释放，复制形状时重建。护栏和真实外边保持原碰撞，网格顶点、车辆、控制、判罚和120Hz均沿用现有实现。各流送块之间的边界不共享邻接，本轮验证范围为同一块铺装的内部边。

| 对照 | 关闭修正 | 开启修正 |
| --- | --- | --- |
| 冻结单子步，真实几何重建 | 10799.89 N·s，59.62 km/h | 0 N·s，91.66 km/h |
| 同一隔离 SDK，原输入第3611拍 | 14907.66 N·s，13.63 km/h | 0 N·s，91.58 km/h |
| 520—565米固定输入 | 最低5.13 km/h，最大绝对俯仰36.60° | 最低86.78 km/h，最大绝对俯仰2.10° |

独立 Bullet 对照将故障边改为单三角形真实外边，开启修正前后的接触编号、距离、法线、冲量和速度输出一致。游戏回放通过 `Session` 装载相同候选几何、原车和已记录输入，观测窗内首个开关差异出现在原故障拍。证据为 `logs/challenge-takeover-20261106/road-edge-sdk/` 的 `probe-result.txt`、`panda-probe.json`、`replay-comparison.json`。

修正后三套方案均四门有效，原始油耗和终点复算通过。按相同驾驶策略跑原车、前胎加免费调校、同调校加软簧各一次，分别得到 72.771 秒 / 22.102 L/100km、71.096 秒 / 23.452 L/100km、70.753 秒 / 23.637 L/100km。后两组预算2000及3500，软簧在本组快约0.34秒但多耗约0.18 L/100km，起伏段接地不足观察点28→24，俯仰跨度3.50°→3.12°。这是单次策略下的速度、油耗和费用取舍，正式报价和奖牌仍待验收。输出为 `logs/challenge-takeover-20261106/ridge-30-012-edge-adjusted/`。

隔离 SDK 使用官方 Panda3D 1.10.16 源和工具包，在 `build/road-edge-sdk/panda/built-road-edge` 编译单精度。早期两次绑定生成因 Bullet 原生头进入 Interrogate 解析失败，最终将原生头限定在 C++ 编译阶段后构建通过。记录为 `build/road-edge-sdk/panda-build*.log`。补丁已核对与隔离源码差异一致，`libpandabullet.dll` SHA256 为 `ad4477e1290a738d8fcc53e6712a9a34349fb05e2d470dc18d52616f88296dfa`。

原隔离 SDK 加载旧冻结大路面 BAM 崩溃。原因是 Panda3D 在 `BulletTriangleMesh::fillin` 将两个文件读取调用放进 `nassertv`，优化构建移除断言后，网格计数及索引字段错位。补丁保留两处读取及校验，重新编译后，同一旧 BAM 可读，冻结单子步复现相同错误基线及修正结果，见 `old-bam-fixed-probe.json`。新版 `libpandabullet.dll` SHA256 为 `1ab52868ceb4ec46542f7704dc837ef1683e66b22e65c462703dcc8c633c1740`。

本机游戏、试玩和控制台启动器优先加载通过构建检查的 SDK。通过 `StreamedRoad` 为 `CareerCourse` 的铺装启用内部边信息及求解前回调。轨迹和成绩沿用既有实际 SDK 指纹分组。六份原试玩记录按历史 SHA256 校验一致。可使用 `.venv/Scripts/python.exe tools/physics/build_road_edge_runtime.py` 从固定版本源码和工具包重建。

接入后原故障输入经生产 `StreamedRoad` 重新通过，520—565米最低86.78 km/h、最大绝对俯仰2.10°、异常冲量为零。独立物理进程确认与窗口使用相同 SDK，铺装启用修正，暂停保留油耗、重试归零、自动成绩未写。当前本地游戏入口离屏启动通过，路网、会话、计量和成绩相关56项通过。补充铺装标记及网格复用检查在官方 SDK 与修正 SDK 下均通过。Ruff通过。日志均在 `logs/challenge-takeover-20261106/road-edge-sdk/`。

另在相同12厘米候选使用116 km/h局部目标补做一对试跑，实测起伏段峰值均约114.35 km/h。原悬架71.098秒 / 21.789 L/100km，软簧71.309秒 / 21.949 L/100km。软簧接地不足观察点21→14，俯仰跨度3.50°→3.12°，但较高目标下的计时优势反转。两次均有效完赛并通过原始燃油与终点复算，见 `ridge-30-012-integrated-116/review.json`。保留候选路线，价格与真人体验仍需核对。打包版接入、人工驾驶和最终 T2 尚未执行。

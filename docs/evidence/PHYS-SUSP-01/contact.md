# PHYS-SUSP-01：细长Box的真实射线交点

2026-10-05，基线为已推送的`f7c971f`。本轮修实际查询，不调弹簧、轮胎、输入或电子增益；整个悬架任务仍在施工。

原单侧翻覆轨迹的接点不在平台上。仿真第34拍，Box真实顶面z=0，原生射线却返回z=0.220803m、近似朝上的法线，随后产生136688N假轮荷。把同一射线放入只有这个固定Box的Bullet世界仍能复现；不是车辆自身命中、移动地面或另一套物理世界。旧完整轨迹中的最坏表面偏离游戏0.416164m、仿真0.486179m。

本机Bullet 2.84默认凸体射线使用SubsimplexConvexCast，Panda3D 1.10.16未暴露该查询的GJK选择标志。Box的支持函数采用含margin外廓。依据实际Box半边长和当前刚体/子形状变换，直接做三轴有限区间求入射交点；不信任原生是否把Box列为候选，所以也覆盖原生漏报。没有复制道路参数、添加查询世界或改变原生刚体碰撞。纯固定Box使用此精确查询，其他形状和动态遮挡继续用同世界原生结果；内部起点不伪造新入射面。

实现按职责分区：`src/suspension_contacts.py`处理接点；`src/vehicle_suspension.py`继续负责唯一轮荷和冲量。四条射线共用当拍静态Box清单，清单每拍直接读世界，不保留另一份道路生命周期状态。完整参考表/研究哈希包含新实现；成绩及参考表更新为game-controls-v15/reference-v18。

依据：[Bullet 2.84查询分支](https://github.com/bulletphysics/bullet3/blob/2.84/src/BulletCollision/CollisionDispatch/btCollisionWorld.cpp)、[默认凸体射线实现](https://github.com/bulletphysics/bullet3/blob/2.84/src/BulletCollision/NarrowPhaseCollision/btSubSimplexConvexCast.cpp)、[Box支持函数和margin](https://github.com/bulletphysics/bullet3/blob/2.84/src/BulletCollision/CollisionShapes/btBoxShape.h)、[Panda3D查询接口](https://github.com/panda3d/panda3d/blob/v1.10.16/panda/src/bullet/bulletWorld.h)。上游源码用于解释机制，结论由本机实际轨迹核对。

## 本轮验证

- T0共27项通过，pytest5.46s：独立Box面交点、真实漏报工况、正反射线/内部/平行/有限长度、旋转复合Box及margin、当前变换、屏蔽和动态遮挡；原生SI冲量/质量/生命周期、完整配置和研究哈希短检查。
- 新诊断工具初次Ruff因gzip未用上下文管理器失败，日志`contact-ruff-r1.log`保留；只修文件读取边界。最终全src/tests/tools Ruff通过。验证模块映射已补新接点测试；未重复27项。
- 原单侧工况/姿态/控制未改，两模式各360拍，原轮胎0.001N残差和局部能量1e−7J门槛保持。306源在运行前后相同；之后只改诊断文件读取和验证模块映射，生产/测试源保持。当前所有有效接点距真实Box面不超过1.24e−7m。
- reference-v18完整91车辆字段、两模式真实240拍读回已导出，包含接点实现哈希。

## 仍待修复的物理问题

|原单侧工况|旧/新累计接触偏移功J|旧/新最大法向力N|新法向机械小计逐拍回增峰值J|
|---|---|---|---|
|游戏|11090.19 / 23232.27|57748.72 / 83695.85|3536.37|
|仿真|71771.10 / 13553.78|136688.17 / 63918.05|2442.85|

游戏模式的不利变化原样保留。精确查询消除了假表面，但没有消除全部正功。当前仿真第83拍是真实平台侧面x=−0.44、法线(1,0,0)，射线刚扫入侧面，约束压缩从材料约0.083m突然绑定到几何约0.189m。这次约束切换产生约13.55kJ偏移功；它不是原生查询假命中，轮胎在竖直侧面也没有道路支撑力。

下一施工处理有限轮半径的连续接触激活，避免点射线越过边缘后才把已经进入实体的轮坐标绑定到新面；随后法向与轮胎/传动共享车身末速度。不能把正偏移改名为外功、钳制能量或关闭碰撞来宣布被动。整车能量、完整功能T1、T2/T3、实际窗口性能和人工驾驶仍未完成。本次静态Box遍历的实际道路性能也尚未验证。

命令、源码差异和证据哈希见[回执](contact-receipt.json)。原始新旧轨迹分别保留在`contact-native-r1`及`passive-native-r2`。

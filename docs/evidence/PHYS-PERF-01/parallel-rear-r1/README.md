# 完整数值多核与车尾修复检查点

2026-10-09，主目录 `main`，上一个检查点 `1efa3f3`，本轮无推送。用户允许微小浮点差异，保留方程、参数、120Hz和原精度。本批实际完整快照仍相同；实时物理与人工驾驶没有通过。

已完成完整车辆数值读入/并行/原序冲量提交，持久进程和直接管道、共享真实静态几何、原Bullet 2.84凸体扫掠，以及独立会话时钟。静态几何在每个120Hz拍读取，车辆姿态和接点在原两个子步分别读取；世界积分与相机查询互斥，纯数值等待不占世界锁。绘制只插值两个已经完成的快照，不外推或修改模拟时间。GUI默认最多9个数值进程；无窗口实验保留串行默认值。

[完整收据](receipt.json)及[文件SHA清单](manifest.json)包含海岸、坡道、参考车、单车各128拍与海岸seed23恒定油门640拍的完整快照SHA核对。旧/新JSON字节相同，只保存一份XZ压缩载荷和两份独立计时。640拍对照45.869→15.215秒；不同CPU配置的128拍耗时只作诊断，不当性能A/B或FPS。

最终相关T1为542项、Ruff和三个种子启动通过；新增入口另8项T0通过。此前误选含上万步旧core检查的T0在180秒超时，不记通过；两次SIM211 Ruff失败保留。原旧车辆细化失败、T2/T3和整体Gate继续待办。

1080p海岸GR86加8车、seed23、油门0.3、声音关闭、原 `/Draw` 管线的有效前台30秒短测：最后直行82.713绘制帧/秒、P95 18.291毫秒，但仅1168拍，约9.73秒物理进度。采样段丢时18.133秒，实时目标失败；不能据绘制速度宣称游戏已流畅。转向画面诊断另记，不用作严格性能比较。

车尾闪烁已在真实连续画面复现：车牌和扩散器外表面与车身只差10微米，排气口与扩散器也近共面。运行GLB及Blender源六个位置字段已修复，制作脚本同步；第一版仍残留排气边缘闪断，复核后排气钢圈与扩散器分开3毫米、内片与钢圈约1毫米。源文件只读回DNA位置，未运行Blender重建/源编辑器渲染。第二版直行和第三版转向截帧见[车尾原样](rear/before.png)、[转向帧1](rear/after-turn-1.png)、[转向帧2](rear/after-turn-2.png)；人工外观验收仍待完成。

独立包 `builds/physics-native-candidate-parallel-r1b` 已在仓库外两模式海岸8车各120拍通过，每模式9个进程、2160次完整数值求解、零原生世界回查；三个PYD与构建输入字节相同。两模式离屏渲染及各20次重启通过、截图目视；它们不替代前台物理速度或人工体验。首个包探针误用了海岸默认0车，未覆盖多进程、完整要求失败，原记录保留。[正常入口](../../../../launchers/physics-parallel-r1-game.cmd)、[困难仿真入口](../../../../launchers/physics-parallel-r1-simulation.cmd)。

采用的成熟经验：[PhysX读取/并行计算/写回](https://nvidia-omniverse.github.io/PhysX/physx/5.6.1/docs/Vehicles.html#snippetvehiclemultithreading)、[Panda真实线程](https://docs.panda3d.org/1.10/python/programming/tasks-and-events/threading)、[原Bullet 2.84扫掠](https://github.com/bulletphysics/bullet3/blob/2.84/src/BulletCollision/CollisionDispatch/btCollisionWorld.cpp)、[Panda矩阵到Bullet转换](https://github.com/panda3d/panda3d/blob/master/panda/src/bullet/bullet_utils.cxx)、[共面深度争抢](https://wikis.khronos.org/opengl/Basics_Of_Polygon_Offset)。

下一继续消除进程内重建只读候选、Python接点回调和主线程观测装配；保持真实几何/机械账，达到8.33毫秒物理预算后再安排前台完整Gate和两模式人工驾驶。

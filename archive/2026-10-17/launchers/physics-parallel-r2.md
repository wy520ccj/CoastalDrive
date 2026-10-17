# 加载与起步收口候选包

2026-10-09本地候选，产物为 `builds/physics-native-candidate-parallel-r1d`。正常游戏和困难仿真入口分别是同目录的 `physics-parallel-r2-game.cmd`、`physics-parallel-r2-simulation.cmd`。

继承多核物理与GR86车尾深度修复；新增固定几何缓存、四轮观测批量计算及原生数值包传输。加载阶段启动全部数值进程、准备固定硬件并执行前60拍真实落地计算，余下悬架稳定过程分摊到中央3、2、1动画中。当前GR86在第181拍稳定，GO前完成落地，比赛计时从GO开始。首个场景绘制仍覆盖Loading遮罩，随后开始三秒倒计时。

实时物理门槛仍未通过，绘制帧率不能代表驾驶速度恢复正常。整体T2/T3与两模式用户体验待验。按用户要求收口、提交推送后暂停优化；根目录公开试玩入口保持原包。验证范围和失败记录见 [收口证据](../docs/evidence/PHYS-PERF-01/loading-wire-r1/README.md)。

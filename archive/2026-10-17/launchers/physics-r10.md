# GR86物理候选包 r10

双击 `physics-r10-game.cmd` 进入正常游戏模式，双击 `physics-r10-simulation.cmd` 进入困难仿真模式。两者使用相同GR86实体硬件，进入现有主菜单后选择路线开始驾驶；困难仿真用Q/E换挡。

窗口入口的 `--vehicle-design gr86-2022-premium-6mt` 直接选择对应车型。该启动选择只写入本次运行的外观状态，玩家在车库保存时仍按原设置流程处理。

包位于 `builds/physics-native-candidate-r10/win_amd64`。独立包不纳入Git；它的构建输入、原生模块指纹及验证结果保存在 `docs/evidence/PHYS-PERF-01/package-r10`。当前包用于物理开发试玩；实际前台性能与两模式人工驾驶仍待验收。

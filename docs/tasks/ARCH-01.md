# ARCH-01 输入辅助、动力总成与转向职责

- 状态：done（自动验收完成，默认驾驶数值保持）
- 基线：`4f62401`；标准操稳A在PHYS-COLL-01/standard-B
- 用户授权：物理系统按功能分区，同一核心供游戏和研究使用，避免防御式层叠

## 功能

移除合并的VehicleResponse。DriverAssist负责输入踏板平滑、速度转向包络、停稳后刹车转倒车的便利行为；SteeringRack负责实际角度/角速度、机械角度范围和速率；Powertrain负责发动机、自动换挡和驱动响应。VehicleCommand以实际角度、两踏板与明确方向请求执行器；Simulation.step可以接收原Control或VehicleCommand，走同一Vehicle和Bullet固定步。

默认模式保持运算顺序和参数。研究请求可以绕过驾驶辅助，仍保留齿条速率/限位、驱动力响应和轮胎μFz限制。该任务不宣称新增真实车轮角速度、轮胎模型或ABS。

## 验证

七标准工况1168×117单元一致；直接请求新增油门、100km/h转向角与机械限位、持续刹车不触发倒车、明确倒挡/reset四项真实物理检查。保留原玩家短点、倒车、转向连续性、动力与交通测试。历史源码加载仅在试验工具的文件边界明确选择模块布局，不加游戏运行时兼容外壳。

T0两次停止于route_driver import排序，最终t0-verified通过；T1 vehicle/core/traffic及三种子/双弯坡见证据包。收口后PHYS-04 Ackermann，再运行本批T2。

结果：T0 10通过，T1 111通过，三种子1200tick与双弯坡30秒通过，旧源码独立进程加载成功。[详细记录](../evidence/ARCH-01/README.md)。

# VEH-01 — 经典双门主车美术

基线 c887822（ENV-02灯塔整体放大20%）；visual-identity-v1独立工作树。状态：实现与相关回归完成，性能Gate未通过，用户视觉验收未通过，等待修正后的体验确认。

## 产品与边界

以用户最终确认的红色经典美式双门车为参考，完成一件可编辑、可复现的Blender→GLB主车资产。旧sports设置ID保留，显示名为经典双门。只替换玩家与车库中的该车型，sedan/NPC仍使用旧资产。

源码分工：vehicle_visual只装载/挂载资源并设置主车材质反射和局部填光；skins负责车漆；scene只有NPC显式使用旧模型的一处调用变化。art/vehicles保存源文件与来源，assets/game/vehicles保存运行资产，tools/blender离线制作，tools/vehicles制作反射和截图。没有运行时程序拼车、车型系统框架或目录大迁移。

本任务未改变物理/碰撞、轮心、Snapshot、交通、Session、UI布局、环境、相机或音频。用户新许可：后续不同车型可使用不同物理参数，但共用Simulation及物理实现；此轮只记录许可，没有接入或臆测参数，详见vehicle-physics.md。

## 实际成果

连续车身和轮拱、经典硬顶座舱、细窗框、圆前灯/横格栅、三段尾灯、贴车身曲线的闭合镀铬保险杠、短镜架、门把手、贴合侧片、深色轮罩、轮盖/白边胎、底盘与内收排气。最终网格31760三角形，预算32000。四轮从GLB独立挂载并直接接受Snapshot世界轮姿。

针对用户反馈重做过大尾灯/尖角保险杠/突出的杆件、侧片/门把手/镜架位置；早期截图不代表当前结果。发白修正：主车显示色转线性反射率，非金属车漆，分离玻璃/橡胶/镀铬属性，反射图区分低亮度地面和窄亮区；主车均匀填光降为28%，全局灯光和NPC不变。玻璃没有内饰透视，灯没有动态逻辑，仍是风格化经典车，不是真实车型复刻。

## 验证入口

- T0：tools/validate.py T0 --area appearance --tests tests/test_vehicle_visual_asset.py
- T1：appearance/core + vehicle_visual_asset/ui/ui_assets/ui_theme/traffic_impacts。
- tests/test_h3_review.py -k 'side_collision or side_approach'：6项通过，碰撞参数未改。
- tools/garage_check.py：两车型×五色，冻结世界/应用/取消/按键/保存错误/驾驶。
- tools/vehicles/capture_vehicle.py --output <新目录>：1920×1080车库、五色、前/后/侧/轮胎/追尾机位。
- tools/environment/drive_slice.py --onscreen --output <新目录>：既有控制器实际驶过365m，8车，截图是实际渲染。
- 同工具加 --benchmark：预热30秒+独立采样300秒，不并行构建或截屏；平均60FPS/P95≤25ms。
- setup.py build_apps --build-base builds/0.8.3-veh01；包从仓库外启动并核对资源哈希。

完整结果和最新图片写入 docs/evidence/VEH-01；不能把离屏/自动驾驶当作人工画面验收。未拓展第二车型、高速或FX。

## 最新验证记录

T1-material：55项通过、seed 0/17/23通过；garage-material：10外观全部流程通过。材质前T0初次因两处import排序失败，已修复；相关短测11项亦通过。侧碰6项通过。独立包从TEMP启动退出0并通过20次重启稳定检查，GLB/反射/清单哈希与源一致。构建仍报告原有系统DLL警告，未做干净机器验收。

修正后的材质与部件图见 docs/evidence/VEH-01。玻璃/轮毂/轮拱近景仍存在风格化简化，不能标记为人工验收通过。

1080p/8车/30秒预热+300秒独立采样：平均58.15FPS，P95 20.34ms；平均帧率未达60FPS，性能Gate未通过。正式采样丢时0.016667秒，预热丢时2.308333秒。不得把路线passed=true当成performance_gate_passed=true。

# 阶段 6A：主菜单车库与外观

状态：完成（0.8.0）。阶段 6B 的画面与声音仍在进行中。

## 已完成

- 主菜单车库可旋转预览两种车型：运动轿跑和经典轿车；每款有五种车漆，共十种外观组合。
- 车漆只应用到模型的 `paint` 部件，不改变驾驶参数或碰撞尺寸。NPC车型与颜色可按种子选择。
- 应用的车型和颜色保存在 `%LOCALAPPDATA%/CoastalDrive/appearance.json`，下次启动时恢复。取消不会覆盖已保存外观；设置不可读或保存失败时会显示提示。
- 车库预览不推进仿真。玩家、NPC和预览共用车辆外观装配逻辑。

## 资源与许可

车体模型来自 [Kenney Car Kit](https://kenney.nl/assets/car-kit)。随项目保留的 `assets/game/License.txt` 标明资源采用 CC0 1.0。原始 GLB 与运行用 BAM 位于 `assets/game/`；`tools/prepare_vehicle_paint.py` 是车漆部件准备工具。五种颜色由项目代码应用，没有新增第三方车漆纹理。

## 验收记录

`logs/phase6a/garage-check.json` 记录通过。`tools/garage_check.py` 覆盖十种外观预览、仿真冻结、应用/取消、重复按键保护、保存失败提示，以及保存外观重新进入驾驶。独立版位于 `builds/0.8.0/win_amd64/coastaldrive.exe`。

## 后续打磨

车库仍使用原型级低多边形车辆和简洁灯光；贴花、更多车型、轮毂细节和更精细的预览场景可在后续美术工作中完善。6A完成不代表正式美术完成，6B的画面和声音仍在开发。

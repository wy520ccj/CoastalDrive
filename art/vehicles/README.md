# 经典双门主车美术源文件

`classic_coupe_v1.blend` 是可编辑源文件。车壳、门缝、窗框、圆灯、格栅、保险杠、轮罩和轮毂是独立命名部件；四轮有独立根节点。运行资产在 `assets/game/vehicles/`，制作工具在 `tools/blender/`，验证在 `tools/vehicles/`。不把制作脚本或源文件打进游戏。

## 复现与手工修改

用 Blender 5.2.2 LTS 后台运行 `tools/blender/build_classic_coupe.py` 可以重新制作源文件及 GLB。此命令会覆盖同名源文件；手工美术修改后请先另存文件，不要直接重跑生成器。源文件保存于运行网格合并之前，可逐部件继续编辑。导出时保留 paint、四个 wheel-* 根节点和米制原点；`vehicle_visual.py` 直接读取导出坐标，不再对新车做旧模型缩放。

项目 Python 运行 `tools/vehicles/bake_reflection_probe.py` 可重建 `reflection-probe.env`。它是原创的 64 像素中性日光立方体图，提前过滤多个粗糙度层级。只给主车车漆/玻璃/金属提供静态反射，不改变场景灯光（主车单独压低均匀环境填光，保留主灯与阴影），不代表动态场景倒影。`.env` 是 simplepbr 的已过滤环境文件格式，不是普通模型 BAM。

## 设计与尺寸

最终参考为用户确认的红色经典美式双门车照片；早先运动轿跑方案未采用。保留长机盖、后移硬顶座舱、圆前灯、窄镀铬保险杠、轮盖/白边胎、侧面装饰及三段尾灯。使用自有 COASTAL 字标，无第三方品牌模型或徽标。照片仅用于参考，哈希在 source-manifest.json，未随游戏分发。

模型为适配现有驾驶参数的风格化经典双门车，并非真实车型的尺寸复刻。+Y 前进、Z 向上，单位米；轮心 X=±0.84、Y=±1.10、Z=-0.12，半径0.33。满舵/旋转的全部车轮顶点与车体顶点都受现有 XY 碰撞外廓检查。玻璃采用不透明深蓝灰材质；当前没有内饰、动态车灯或车损。

五种车漆保留颜色名称与设置 ID；新主车使用专门的显示色板并转成线性反射率，旧车型保留原色值；新车继续使用 sports ID 以兼容已保存设置，界面名称为经典双门。旧 sedan 与交通车辆模型不替换。

## VEH-02 交通车辆族

`traffic_compact_v1.blend`、`traffic_sedan_v1.blend`、`traffic_wagon_v1.blend` 是三款原创可编辑源文件；对应 GLB 位于 `assets/game/vehicles/`。运行时只读取 GLB。用 Blender 5.2.2 LTS 后台执行 `tools/blender/build_traffic_family.py` 可重建这三套源文件与运行资产；重跑会覆盖同名文件，手工修改应先另存。

三车共用车漆、深蓝灰玻璃、橡胶、轮毂、灯罩等基础材质与轮子做法，外廓分别强调短尾 hatch、低顶三厢 sedan 和高顶带行李架 wagon。车身采用低面数连续壳和轮拱，轮胎独立挂载到四个 `wheel-*` 根节点，直接接收交通 Snapshot 世界轮姿。轮心为 X ±0.84 m、Y ±1.10 m、Z -0.12 m，半径 0.33 m。三个车身加外露车轮均按现有 X ±1.05 m、Y ±2.15 m 的碰撞外廓验证；物理尺寸和碰撞没有修改。

`traffic-family-manifest.json` 记录单车三角面数和设计尺寸。车漆继续使用现有五色；车型选择仅影响显示，不改变交通生成、操控和碰撞。证据图与验证边界见 `docs/tasks/VEH-02.md`。

## 材质约定

车漆为非金属有色漆面（metallic=0、roughness=0.32）；金属属性用于裸露镀铬件，不直接把车漆设为金属。玻璃为深蓝灰不透明近似，橡胶低反射率且粗糙。主车仅使用原环境填光的28%，太阳/车库主灯及阴影原样保留，避免均匀环境项让镀铬和漆面蒙白。反射仍是离线中性日光，未声称实时镜面反射或写实内饰。

## PHYS-REAL-01 GR86 外观草稿

`gr86_2022_premium.blend` 是项目原创程序网格生成的近似低模可编辑源，运行网格为 `assets/game/vehicles/gr86_2022_premium.glb`，由 `tools/blender/build_gr86.py` 制作。模型尚未完成游戏装配或最终外观验收；重跑脚本会覆盖对应模型文件，离线预览写入 `logs/physics/PHYS-REAL-01-appearance/`。文件 SHA、生成来源和来源边界见 `gr86-source-manifest.json`。

Toyota 2022 GR86 手册仅作尺寸、比例和外形参考，不是官方 CAD 或授权 Toyota 模型。该近似低模由本项目脚本生成；不声称 Toyota 对模型提供授权或认可。

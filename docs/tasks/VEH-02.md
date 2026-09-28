# VEH-02 — 统一车型目录与交通车辆视觉族

- 状态：accepted with known visual debt（用户于2026-09-28接受）。
- 基线：`7906dd3bfe1a4eb44ccfa0cb24bb7e05e5c3e66e`（SCENE-01 后的 `visual-identity-v1`）。

## 目标与边界

用三款原创、轻量且风格统一的 GLB 替换旧 NPC 显示车：compact/hatch、sedan、SUV/wagon。全部车型现由 `skins.py` 中的 `VehicleDefinition` 统一描述，车库按 `player_selectable` 筛选，交通按 `traffic_allowed` 筛选，并共用 `load_vehicle()` 与 `apply_skin()`。Classic Coupe 标记为 Hero 质量；三款新车保持 Traffic 质量且暂不进入车库。没有增加 Manager、Factory、Registry 或 LOD 系统。

交通车随后完成一次窄范围风格统一：PBR 车漆使用与 Hero 相同的线性色彩流程，玻璃、轮胎、黑色塑料、轮毂金属和灯组材质向 Hero 的材质语言靠齐，并给连续车身壳补充加权法线。车型轮廓、三角数、车身尺寸和四轮中心均未变化。Hero Vehicle、Simulation、交通/碰撞规则、UI、海岸环境、Scene 生命周期均未修改。

Blender 5.2.2 LTS 生成的三款资产分别为 4234、4138、4354 三角形，每款低于 8500 上限，明显轻于 31760 三角形 Hero。三车共享四轮半径与轮心、材质语言和五色车漆，但各有不同车顶、尾部、玻璃比例和细节。种子 23 的八车集合含三种车型，车型和车漆分配均确定性。轮姿继续由原交通 Snapshot 驱动。

## 验证

| 项目 | 结果 |
|---|---|
| 资产外廓与轮姿 | 三车车身在现有碰撞外廓内；四轮半径、轮心和 Snapshot 姿态定向测试通过；未修改物理尺寸 |
| 回归 | `test_vehicle_visual_asset.py`、`test_appearance.py`、`test_traffic_behavior.py`、`test_traffic_impacts.py`、`test_scene_lifecycle.py` 共 23 项通过；相关 Ruff 通过 |
| 滨海窗口 | 1920×1080、种子 23、八车短程实际驾驶通过，驶过 365 m；报告在 `logs/VEH-02-drive/`。短程样本采集于车身壳最终精修前，只作流程 sanity，不当成最终性能结论 |
| 高速装配 | `src/main.py --smoke --track endless` 离屏运行通过；12 车、20 次重开节点/任务/事件稳定 |
| 最终实景渲染 | `docs/evidence/VEH-02/traffic-in-game.png` 使用当前种子下真实交通 Snapshot 和滨海场景；另外两张为滨海场景内的三车摆拍，用于对比轮廓和轮位 |
| 人工视觉 | 用户已接受现阶段Traffic质量；交通车比Hero更方、更高、细节等级较低，后续Vehicle Polish再统一 |
| 独立包 | `builds/0.8.3-veh02-catalog/win_amd64/coastaldrive.exe` 从仓库外启动 smoke 通过；8 辆交通车正常，20 次重开节点、任务和事件稳定。SHA-256：`94AD885928A9E917F456890581D62C8AC029520DB21F0EF7EBA2E5DB96967E67` |

没有运行 300 秒基准，也不宣称满足 60 FPS Gate。短程 sanity 的平均帧率约 47.4 FPS，仅证明没有启动或渲染灾难，采样窗口和中途资产版本都不足以用于性能比较。本任务到此停止，不扩展性能分析。

## 交接

- 制作入口：`tools/blender/build_traffic_family.py`；源文件与尺寸约定见 `art/vehicles/README.md`。
- 渲染入口：`tools/vehicles/capture_traffic_family.py --output <新目录>`。
- 证据：`assets/game/vehicles/traffic-family-manifest.json`、`docs/evidence/VEH-02/`、本机 Git 忽略的 `logs/VEH-02-drive/`、`logs/VEH-02-highway-smoke/` 与 `logs/VEH-02-catalog-package-smoke/`。
- 下一步：进入 HWY-01；停止继续精修这三辆NPC，不插入第二Hero。已知视觉债务：交通车比Hero更方、更高、细节等级较低，后续Vehicle Polish再统一。

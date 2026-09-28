# VEH-02 — 交通车辆视觉族

- 状态：自动实施与验证完成；人工视觉评审待用户确认。
- 基线：`7906dd3bfe1a4eb44ccfa0cb24bb7e05e5c3e66e`（SCENE-01 后的 `visual-identity-v1`）。

## 目标与边界

用三款原创、轻量且风格统一的 GLB 替换旧 NPC 显示车：compact/hatch、sedan、SUV/wagon。只改美术源文件、运行资产、NPC 车型选择与装配、对应测试和文档。Hero Vehicle、Simulation、交通/碰撞规则、UI、海岸环境、Scene 生命周期均未修改；没有 LOD、FX、异步或管理器。

Blender 5.2.2 LTS 生成的三款资产分别为 4234、4138、4354 三角形，每款低于 8500 上限，明显轻于 31760 三角形 Hero。三车共享四轮半径与轮心、材质语言和五色车漆，但各有不同车顶、尾部、玻璃比例和细节。种子 23 的八车集合含三种车型，车型和车漆分配均确定性。轮姿继续由原交通 Snapshot 驱动。

## 验证

| 项目 | 结果 |
|---|---|
| 资产外廓与轮姿 | 三车车身在现有碰撞外廓内；四轮半径、轮心和 Snapshot 姿态定向测试通过；未修改物理尺寸 |
| 回归 | `test_vehicle_visual_asset.py`、`test_appearance.py`、`test_traffic_behavior.py`、`test_traffic_impacts.py`、`test_scene_lifecycle.py` 共 22 项通过；相关 Ruff 通过 |
| 滨海窗口 | 1920×1080、种子 23、八车短程实际驾驶通过，驶过 365 m；报告在 `logs/VEH-02-drive/`。短程样本采集于车身壳最终精修前，只作流程 sanity，不当成最终性能结论 |
| 高速装配 | `src/main.py --smoke --track endless` 离屏运行通过；12 车、20 次重开节点/任务/事件稳定 |
| 最终实景渲染 | `docs/evidence/VEH-02/traffic-in-game.png` 使用当前种子下真实交通 Snapshot 和滨海场景；另外两张为滨海场景内的三车摆拍，用于对比轮廓和轮位 |
| 人工视觉 | 待用户审图/试玩；自动检查不代替接受 |

没有运行 300 秒基准，也不宣称满足 60 FPS Gate。短程 sanity 的平均帧率约 47.4 FPS，仅证明没有启动或渲染灾难，采样窗口和中途资产版本都不足以用于性能比较。本任务到此停止，不扩展性能分析。

## 交接

- 制作入口：`tools/blender/build_traffic_family.py`；源文件与尺寸约定见 `art/vehicles/README.md`。
- 渲染入口：`tools/vehicles/capture_traffic_family.py --output <新目录>`。
- 证据：`assets/game/vehicles/traffic-family-manifest.json`、`docs/evidence/VEH-02/`、本机 Git 忽略的 `logs/VEH-02-drive/` 与 `logs/VEH-02-highway-smoke/`。
- 下一步：等待人工视觉评审；通过后按既定顺序进入 HWY-01。

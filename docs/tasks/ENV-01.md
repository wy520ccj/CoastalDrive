# ENV-01 / Coastal Slice

状态：实施与自动验证完成；人工画面验收 pending，整体性能 Gate 未完成。起点 7588527（保留侧向碰撞修复）。用户确认当前 UI 满意，本轮冻结 src/ui、application、UI 资产与全部控制/仿真/车辆/交通/规则。

范围：仅滨海赛道的环境光色基底、少量 Blender 可编辑环境资产、沿现有道路 0–360 m 的视觉示范段。全图仅统一海岸环境材质/天空，不全图铺道具。保持道路网格与碰撞位置不变，新增装饰摆在护栏之外，不生成碰撞或改变路面。

分区：src/environment/foundation.py 管配色/光照参数/材质，water.py 管海面 shader 装配，coastal_slice.py 管资产加载与示范段布局；assets/game/environment 按 models/materials/sky/shaders 分成运行资源；art/coastal 保存可编辑 Blender；tools/blender 是导出生产工具；tools/environment 是纹理与留证工具。scene.py 只改必要装配。完整边界见 [environment-art.md](../environment-art.md)。禁止新框架。

验证：修改前后同相机截图、实际游戏窗口和固定种子驾驶、UI/核心/表现与碰撞回归、资源边界/导出测试。性能只记录本轮有证据的采样，不代签完整 1080p8车阶段 Gate。

## 实际交付

- 暖色光照、独立天空全景、带远处采样衰减的动态蓝绿海面、路/草/石岸材质；既有 Kenney 树石只改滨海实例材质，原模型与碰撞尺寸未变。
- 本机 Blender 5.2.2 LTS 制作并导出 12 件 GLB，共 9410 三角形；保留可编辑 `.blend`，没有新第三方模型，也没有复制 DS 实现。
- 现有道路 0–360 m 的花草、树、石、路灯、弯道方向牌、小屋；海上灯塔和少量远景岩岛。道路网格、护栏位置和岛面物理没有修改。
- 使用真实导出包围圆验证整个景物外廓在护栏外至少 0.2 m；路牌随既有弯道方向选择左右箭头。灯塔基座与岩岛顶面交叠 2 cm。
- `application.py`、`src/ui`、车辆、交通、Session、Simulation 和地图源码相对 7588527 无差异。没有新增车辆模型、小地图、玩法、AI 或驾驶 FX。

## 命令与结果

Python 统一使用 `../CoastalDrive/.venv/Scripts/python.exe`，下表省略解释器前缀。

| 检查 | 命令/证据 | 结果 |
|---|---|---|
| T0 | `tools/validate.py T0 --tests tests/test_environment.py --output logs/ENV-01/T0` | Ruff + 当时 17 项通过；随后增加路牌方向测试 |
| T1 | `tools/validate.py T1 --area environment --area appearance --area core --tests tests/test_ui.py tests/test_ui_assets.py tests/test_ui_theme.py tests/test_traffic_impacts.py --output logs/ENV-01/T1` | 68 项通过；种子 0/17/23 各 1200 步启动通过 |
| 固定镜头 | `tools/environment/capture_coastal.py --output logs/ENV-01/final-views` | 5 个 1080p 视点；基线在 logs/ENV-01/baseline；均为真实场景渲染 |
| 可见窗口 | `tools/environment/drive_slice.py --onscreen --output logs/ENV-01/drive-final` | 种子 23、8 车、实际物理驶过 365 m；无瞬移，保存 5 个驾驶截图 |
| 短程性能 | `logs/ENV-01/drive-final/report.json` | RTX 4060 Laptop，1080p，约 28 秒；平均 58.74 FPS，P95 20.34 ms，P99 22.38 ms；累计丢弃仿真时间 0.925 s。未达到平均 60 FPS 门槛，也没有执行预热后 5 分钟标准采样。同期 T1 与截图读取有额外负荷，不能据此量化环境开销 |
| 其他赛道 | `src/main.py --smoke --track test/highway/endless --output logs/ENV-01/track-<track>` | 各独立进程启动、渲染与 20 次重启稳定检查通过 |
| 打包 | `setup.py build_apps --build-base builds/0.8.3-env01` | 构建成功；模型、纹理、天空及 shader 进入包 |
| 独立包 | 从系统临时目录运行 `coastaldrive.exe --smoke --output <绝对证据目录>` | 渲染与 20 次重启通过，见 logs/ENV-01/package-smoke；非干净机器证明 |

构建仍提示缺少 `api-ms-win-core-path-l1-1-0.dll`、`PROPSYS.dll` 依赖，以及若干平台专属模块；本机包可运行，保留既有干净机器验收门槛。

## 留证与未完成项

可移交的代表截图、T0/T1 摘要、窗口/打包/其他赛道报告和文件哈希见 `docs/evidence/ENV-01/`。全部本机中间日志在 `logs/ENV-01/`，不覆盖旧证据。第一轮固定相机未执行渲染任务初始化导致 camera_world_position 缺失；修复留证工具后基线成功，失败日志仍保留。模型初稿原点错误与突出的岩层已重导修正，并用 GLB 实测测试覆盖。

本轮是环境基底与示范段初版，不是设计图最终复刻。树冠仍偏几何化、远景岩岛简化明显、天空清晰度有限；新增装饰没有碰撞，不能宣称可交互。用户需实际驾驶确认色彩、景物比例、连续行驶观感；平均帧率与启动/截图卡顿仍需独立性能采样定位，不在本任务暗改仿真补偿。

下一步先评审这段路的实际观感，再决定针对资产质量迭代；不自动全图铺设，不开始车辆或 FX。

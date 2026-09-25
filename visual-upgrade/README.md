# CoastalDrive

> **实验归档：DS 新工作目录（2026-09-24）**。这是单独保存的实验副本，画面有所提升，但已知 bug 很多，未完成系统回归或人工验收。它用于公开留档和后续排查，不代表稳定版；运行和修改前请先阅读本目录的 [实验状态](EXPERIMENTAL-STATUS.md)。本目录保留 DS 工作目录结构，里面另有一份 `visual-upgrade/` 子目录。

本地开发版本：**0.8.3**。阶段 6B 已接入真实 Bullet 碰撞事件、分层汽车撞击声与持续擦碰；实际驾驶音色校准、完整画面和性能验收仍待进行。进度见[当前进度](docs/current-progress.md)，环境增量见[环境与声音记录](docs/phase6b-atmosphere.md)，分阶段路线见[开发计划](docs/development-plan.md)。

CoastalDrive 是使用 Python 和 Panda3D 开发的驾驶游戏，包含滨海计时挑战、滨海自由驾驶，以及可选直路/弯坡和三档车流的无限高速。玩家可在高速自由驾驶或 5 公里无碰撞挑战中驾驶；倒车可用于调整姿态。

## 运行

使用项目 `.venv` 中的 Python 3.14.2。原本的 `B:\python.exe`（3.12）无法正常启动，原因记录在 [docs/phase0-environment.md](docs/phase0-environment.md)。不要安装到全局 Python。

```powershell
.\.venv\Scripts\python.exe src/main.py
```

PyCharm 打开本项目，解释器选择 `.venv\Scripts\python.exe`，入口为 `src/main.py`。资源路径不依赖启动时的工作目录。

## 菜单与操作

主菜单可进入计时挑战、滨海自由驾驶、无限高速或车库。无限高速可选道路类型与稀疏/普通/繁忙车流；挑战模式目标为无碰撞行驶 5 公里。

车库可预览两款车型和五种车漆。点击车型/颜色按钮切换，按 Enter 应用并返回，按 Esc 取消；应用的选择会保存到 `%LOCALAPPDATA%\CoastalDrive\appearance.json`。外观选择不改变车辆性能。

| 操作 | 按键 |
|---|---|
| 开始/继续驾驶 | Enter |
| 油门 | W / 上方向键 |
| 刹车，停车后保持进入倒车 | S / 下方向键 |
| 左右转向 | A / D / 左右方向键 |
| 回到当前路段中心并扶正 | R |
| 切换远近摄像机 | C |
| 暂停/继续 | Esc |
| 诊断信息 | F3 |

窗口失焦会自动暂停。检查点不切换相机；倒车可用于调姿。界面使用本机 Windows 微软雅黑，不把系统字体复制进素材包。

## 当前画面与声音

当前 6B 增量包括 Poly Haven 天空、路面和草地贴图，滨海程序生成的海面纹理、路边标杆、弯坡路边松树/灌木、HUD 半透明底板、发动机与路噪录音，以及新的汽车撞击素材池。撞击声按真实物理事件分层播放，护栏持续摩擦使用独立循环。音色与动态仍需实际驾驶试听，完整视觉验收和性能测量尚未完成。音频设计与诊断入口见 [docs/vehicle-impact-audio.md](docs/vehicle-impact-audio.md)。

## 检查

开发默认按范围执行短检查。工作规则见 [AGENTS.md](AGENTS.md)，任务包、T0–T3及人工Gate见 [任务入口](docs/tasks/README.md)。碰撞音频的下一步是 [6B-05 实驾校准](docs/tasks/6B-05-impact-calibration.md)。

```powershell
.\.venv\Scripts\python.exe tools/validate.py T0 --area traffic
.\.venv\Scripts\python.exe tools/validate.py T1 --area traffic
.\.venv\Scripts\python.exe tools/validate.py T2 --dry-run
```

验证入口将详细输出和JSON摘要放到独立的 `logs/validation/` 目录；失败即停。完整回归留给小阶段收口，长测留给阶段Gate；画面、声音和驾驶体验仍需实际验收。下面是按需使用的原有专项入口，不是每次修改都要执行的清单。

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check src tests tools
.\.venv\Scripts\python.exe src/main.py --headless --steps 10000 --seed 17
.\.venv\Scripts\python.exe src/main.py --smoke --output logs/h0-offscreen
.\.venv\Scripts\python.exe src/main.py --smoke --track highway --output logs/stage4-highway-smoke
.\.venv\Scripts\python.exe src/main.py --window-smoke --output logs/h0-window
.\.venv\Scripts\python.exe tools/h0_ui_check.py
.\.venv\Scripts\python.exe tools/h1_ui_check.py
.\.venv\Scripts\python.exe tools/h1_benchmark.py
.\.venv\Scripts\python.exe tools/phase3_route_check.py
.\.venv\Scripts\python.exe tools/h2_render_check.py
.\.venv\Scripts\python.exe tools/stage4_ui_check.py
.\.venv\Scripts\python.exe tools/h3_ui_check.py
.\.venv\Scripts\python.exe tools/h2_render_check.py --output logs/h3-review/render
```

headless 不创建窗口或加载渲染模块；offscreen smoke 创建实际离屏渲染上下文，两者用途不同。

## 打包

```powershell
.\.venv\Scripts\python.exe setup.py build_apps
```

打包命令默认输出 `build/win_amd64/coastaldrive.exe` 和同目录资源。当前 0.8.3 独立版位于 `builds/0.8.3/win_amd64/coastaldrive.exe`；运行时请保留并启动完整文件夹，不要只复制 exe。应用设置和日志保存在 `%LOCALAPPDATA%\CoastalDrive`。

## 素材准备

素材来源、许可和本地路径登记在 [docs/asset-register.csv](docs/asset-register.csv)。当前车辆与自然资源来自 Kenney CC0 素材包；天空、路面和草地贴图来自 Poly Haven CC0 资源。滨海海面纹理由项目脚本生成；驾驶循环声和新碰撞层的录音来源及加工方法分别见 `tools/prepare_audio.py`、`tools/prepare_impact_audio.py` 与 `assets/game/audio/License.txt`。原始素材压缩包、虚拟环境和构建目录不一定随源码目录分发；处理许可与原始资源时以素材登记表和随资源保留的许可证文件为准。

## 代码边界

- `simulation`：唯一权威状态、固定步长运动、种子、只读快照。
- `controls`：统一 Control 的键盘与脚本来源。
- `session`：120 Hz 调度、插值与菜单/暂停/重开生命周期。
- `tracks`：地图目录、玩法可切换入口、车道中心和行驶方向。
- `coastal_map` / `highway_map`：路线、路面/路肩/护栏/道路分段信息，供物理和显示共用。
- `race`：计时挑战、检查点、逆行/复位判定和分地图版本的最佳成绩保存。
- `world_props`：树、岩石、检查点框架的共同摆放与碰撞尺寸。
- `vehicle_config` / `vehicle_dynamics`：车辆参数、道路阻力、轴载荷估计和动力学诊断。
- `skins` / `garage` / `settings`：车型、外观预览与本地选择保存；外观不参与车辆受力。
- `scene` / `application` / `soundscape`：模型、界面、相机、窗口与声音；渲染和声音消费仿真状态。
- `tests`：正式实现的行为检查。

原 MFC 工程保持只读，旧工程说明见 [legacy/README.md](legacy/README.md)。

# CoastalDrive

当前开发版本（2026-10-17）：**main，游戏实时操控 + 车辆动力学实验台**。两个方向共用权威 Simulation；游戏使用120 Hz单次机械求解，实验台保留每拍两次机械子步和精确执行器。游戏操控与整体流畅已获用户验收，偶发绘制短停已披露并接受；实验台自动功能/渲染通过，人工体验待确认。

[当前进度](docs/current-progress.md) · [真实新版合并](docs/tasks/INTEGRATE-NEW-LAB-01.md) · [实验台说明](docs/vehicle-lab.md) · [入口与历史版本](launchers/README.md)

双击根目录 **试玩.cmd** 或 `launchers/game-current.cmd` 启动当前源码游戏；双击 `launchers/vehicle-lab.cmd` 进入实验台，游戏主菜单也可进入。首次克隆须完成下文环境安装和原生编译。`试玩-物理开发.cmd` 是显式重新编译源码的开发入口，会包含本地未提交改动。

游戏会把当前工程车带入实验室。完成试验后点顶部 **游戏联动**，可运行同命令的游戏积分对照，或 **保存车辆并试驾**；重启后保留已应用车辆。见[车辆设计闭环](docs/vehicle-design-loop.md)。

新版试验台真实来源为 `codex/simulation-fidelity` 的 `0944541`，包含参数悬停/F1数学公式、工程指标、轮胎标定、独立轮心与部件台架。`launchers/vehicle-lab-double-preview.cmd` 打开显式工程预览，`vehicle-lab-double.cmd` 使用双精度普通实验室；先恢复隔离SDK：`.venv/Scripts/python.exe tools/physics/restore_sim_double_runtime.py`，详见[双精度说明](docs/sim-double-runtime.md)。新机制按工程配置启用，游戏默认参数保持。

旧版构建包、历史启动器、旧工程、过期日志和独立工作树统一见[归档目录](archive/README.md)。其中 RADIO-02、r9/r10/parallel 没有当前游戏与新版试验台成果；原路径映射、分支提交和恢复说明随归档保存。整体物理、实车标定及长期性能Gate仍按[物理路线](docs/physics-roadmap.md)和各任务记录推进。

## 运行

开发使用 Python 3.14 和项目虚拟环境。首次从源码克隆后：

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe setup.py build_ext --inplace --build-temp builds/native-temp
.\.venv\Scripts\python.exe src/main.py
```

PyCharm 选择 `.venv/Scripts/python.exe`，入口 `src/main.py`。Git仓库包含运行素材；虚拟环境、构建包和离线原始素材不纳入Git。当前源码入口不需要先构建独立包；`.pyd`必须由当前源码编译，不能从旧包或其他工作树复制。

物理开发版的机械向量、有限轴端口小矩阵与轮胎有限面支持函数使用项目内C内核，分别按机械和接触几何组织；Windows源码构建需要Visual Studio C++工具。构建保持严格浮点与补偿求和，部分和算法的来源与许可见 `licenses/CPython-LICENSE.txt`。独立试玩包携带编译内核，运行不需要编译器。硬件/本构/120Hz与原精度不因本地内核改变。

## 玩法与操作

支持滨海计时挑战、滨海自由驾驶，以及直路/弯坡、三档车流的无限高速；高速可选自由驾驶或5公里无碰撞挑战。车库提供两款可选车型与五种车漆，Enter应用、Esc取消。

| 操作 | 按键 |
|---|---|
| 开始/确认 | Enter |
| 油门 | W / 上方向键 |
| 刹车、停车后保持进入倒车 | S / 下方向键 |
| 左右转向 | A / D / 左右方向键 |
| 回到当前路段中心并扶正 | R |
| 切换远近摄像机 | C |
| 切换驾驶电台 | N |
| 开关驾驶电台 | M |
| 暂停/继续 | Esc |
| 诊断信息 | F3 |

窗口失焦自动暂停。暂停页可进入设置，调整主音量、效果音量、音乐音量及电台；返回设置后仍保持暂停。首页播放保留的原创海岸曲，驾驶两台分别播放吉他Bossa Nova《Bossa Antigua》和暗色电子《Future Gladiator》，设置页可试听所选电台。作者Kevin MacLeod，CC BY 4.0，完整署名见 [音频许可证](assets/game/audio/License.txt)。

设置、成绩和运行日志保存在 `%LOCALAPPDATA%/CoastalDrive`。资源路径不依赖启动时的工作目录。

## 文件分区

| 路径 | 内容 |
|---|---|
| `src/` | 物理、玩法、表现；`audio/`声音分区、`ui/`界面、`environment/`环境 |
| `assets/game/` | 随游戏运行的模型、贴图、字体、声音与许可 |
| `art/` | 可编辑Blender美术源文件 |
| `tools/` | 按音频、环境、车辆、性能等职责组织的制作和验证工具 |
| `tests/` | 行为回归 |
| `docs/` | 当前状态、设计、任务包与验证证据 |
| `launchers/` | 当前源码游戏/实验台入口；历史包见入口说明 |
| `builds/` | 当前新构建的输出位置；既有历史包已归档 |
| `logs/` | 当前验证与窗口日志；已结束阶段的旧输出已归档 |
| `assets/source/` | 离线原始素材与缓存，不随Git提交 |
| `archive/` | 统一历史归档；旧包、旧入口、旧工程、日志、旧工作树和恢复索引 |

`CoastalDrive` 的 `main` 为统一主目录；`simulation-fidelity` 是本次新版试验台的真实开发来源，已纳入当前合并；VI-v1/gr86-physics是历史/辅助工作树。上轮6ca4cb4误将simulation-fidelity归为历史、只发布主目录8个提交，本次纠正并合入其25个提交。旧main另有本地备份和Git历史。当前事实从 `docs/current-progress.md` 进入，旧任务/证据仅支持其记录的源码版本。

## 检查与构建

按修改范围执行相关短检查，任务与等级说明见 [验证入口](docs/tasks/README.md)。真实新版合并与证据复用边界见[当前任务](docs/tasks/INTEGRATE-NEW-LAB-01.md)；旧独立包的声音/资源smoke不能代替当前源码验收。完整能量、实车标定、T2/T3和长期性能Gate分别保留。

```powershell
.\.venv\Scripts\python.exe tools/validate.py T0 --area audio
.\.venv\Scripts\python.exe tools/validate.py T1 --area audio
.\.venv\Scripts\python.exe setup.py build_ext --inplace --build-temp builds/native-temp
.\.venv\Scripts\python.exe setup.py build_apps --build-base builds/0.8.3-current
```

运行独立包时保留完整 `win_amd64` 文件夹。旧阶段入口及恢复说明见[统一归档](archive/README.md)。

## 素材与实现

素材来源登记在 [素材表](docs/asset-register.csv)。Kenney、Poly Haven与实录声源许可随资源保留；当前车型与植被还有项目原创Blender资源。当前引擎/碰撞离线制作见 `tools/audio/prepare_recorded.py`，授权电台见 `tools/audio/prepare_music.py`，首页原创曲与提示见 `tools/audio/prepare_upgrade.py`。

Controller → Control → Simulation → Snapshot → 玩法/表现/UI。Simulation是唯一物理权威，120Hz固定步；声音、界面和相机消费快照，不维护第二套物理状态。按功能职责直接组织模块，工作规则见 [AGENTS.md](AGENTS.md)。

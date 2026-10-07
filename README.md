# CoastalDrive

当前主版本：**0.8.3 RADIO-02**，以 `main` 为发布源码。包含新版海岸/无限高速、经典双门主车、Visual Identity v1 界面、实录引擎与车体碰撞、双电台，以及动态UI和提示底板修订。当前独立包位于 `builds/0.8.3-radio02/win_amd64/`，本地双击根目录 **试玩.cmd** 启动。

[当前进度](docs/current-progress.md) · [音频设计与素材许可](docs/audio-design.md) · [电台试听与验证](docs/evidence/RADIO-02/README.md) · [提示底板检查](docs/evidence/UI-NOTICE-FIX/README.md)

2026-10-01物理开发已接入道路坡度/四轮诊断、标准A/B、护栏接触修复、输入辅助与执行器功能分区及直接研究请求；源码体验双击 **试玩-物理开发.cmd**，记录见 [物理路线](docs/physics-roadmap.md)。整体物理阶段仍进行中，独立包暂未更新。

## 运行

开发使用 Python 3.14 和项目虚拟环境。首次从源码克隆后：

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe setup.py build_ext --inplace --build-temp builds/native-temp
.\.venv\Scripts\python.exe src/main.py
```

PyCharm 选择 `.venv/Scripts/python.exe`，入口 `src/main.py`。Git仓库包含运行素材；虚拟环境、构建包和离线原始素材不纳入Git。仅克隆源码时先按下文构建独立包，再使用试玩入口。

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
| `launchers/archive/` | 阶段试玩入口，根目录仅保留当前试玩入口 |
| `builds/` | 本地独立包；历史默认构建移至 `builds/archive/` |
| `logs/` | 本地日志与临时验证输出，早期smoke目录归入 `logs/archive/` |
| `assets/source/` | 离线原始素材与缓存，不随Git提交 |
| `legacy/` | 只读旧工程 |

`CoastalDrive` 为主工作目录；相邻 `CoastalDrive-VI-v1` 保留开发线工作树，同步本次主版本内容。旧main另有本地备份和Git历史。

## 检查与构建

按修改范围执行相关短检查，任务与等级说明见 [验证入口](docs/tasks/README.md)。当前游戏版本已完成音频/UI相关T1、三种子、真实OpenAL和切台回录、连续窗口帧检查及独立包smoke，记录在上述证据目录；听感、驾驶和完整性能结果以各任务记录为准。

```powershell
.\.venv\Scripts\python.exe tools/validate.py T0 --area audio
.\.venv\Scripts\python.exe tools/validate.py T1 --area audio
.\.venv\Scripts\python.exe setup.py build_ext --inplace --build-temp builds/native-temp
.\.venv\Scripts\python.exe setup.py build_apps --build-base builds/0.8.3-radio02
```

运行时保留完整 `win_amd64` 文件夹。旧阶段入口归档说明见 [launchers/archive/README.md](launchers/archive/README.md)。

## 素材与实现

素材来源登记在 [素材表](docs/asset-register.csv)。Kenney、Poly Haven与实录声源许可随资源保留；当前车型与植被还有项目原创Blender资源。当前引擎/碰撞离线制作见 `tools/audio/prepare_recorded.py`，授权电台见 `tools/audio/prepare_music.py`，首页原创曲与提示见 `tools/audio/prepare_upgrade.py`。

Controller → Control → Simulation → Snapshot → 玩法/表现/UI。Simulation是唯一物理权威，120Hz固定步；声音、界面和相机消费快照，不维护第二套物理状态。按功能职责直接组织模块，工作规则见 [AGENTS.md](AGENTS.md)。

# 启动入口与版本

2026-10-17：当前源码入口统一放在此目录，根目录两个重复的试玩脚本已移除；历史入口记录见[统一归档](../archive/README.md)。直接玩游戏请使用[下载安装版或免安装包](../docs/download.md)。

| 入口 | 内容 |
|---|---|
| `game-current.cmd` | 当前源码游戏；本机存在 KCD2 资源时启用本地植被表现，缺失时自动回退至生产资产版本 |
| `vehicle-lab.cmd` | 当前源码专家试验台 |

2026-10-24：[ENV-REAL-01](../docs/tasks/ENV-REAL-01.md)将本机默认启动器接入本地资源表现；读取已确认的KCD2安装，衍生缓存只写ignored logs。原有玩家和实验台记录目录保持。`src/main.py`、可分发游戏资产和打包入口不含KCD二进制；若当前机器无本地 KCD2 资源，`game-current.cmd` 会自动回退到 `src/main.py --driving-mode game` 生产资产版本。直接运行 `.venv/Scripts/python.exe src/main.py --driving-mode game` 也可显式启动生产资产版本。

本机的 `game-current.cmd` 会优先加载已构建的路面修正 SDK，独立物理进程继承同一版本。新工作区可在仓库根目录执行 `.venv/Scripts/python.exe tools/physics/build_road_edge_runtime.py`，需要 Visual Studio 2022 C++ 工具链和 Windows SDK。构建完成前启动器仍可使用虚拟环境内原版 Panda3D。

需要从源码重新编译原生扩展时，在仓库根目录执行，再运行上表入口：

```powershell
.venv/Scripts/python.exe setup.py build_ext --inplace --build-temp builds/native-temp
```

运行素材、`.venv`、`src`原生扩展和`build/sim-double-runtime`留在主目录；包内运行依赖不从归档动态查找。历史物理/radio启动器仍与各自历史包按原相对布局保存在`archive/2026-10-17/launchers`和同批`builds`中。

历史源码、构建、日志与工作树的原位置、提交和恢复方式见归档索引；失败记录保留原结论，归档不代表重新验收。

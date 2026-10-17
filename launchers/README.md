# 启动入口与版本

2026-10-17：这里只保留当前源码入口，旧版入口已归入[统一归档](../archive/README.md)。

| 入口 | 内容 |
|---|---|
| 根目录 `试玩.cmd` / `game-current.cmd` | 当前源码游戏 |
| `vehicle-lab.cmd` | 当前源码实验台 |
| `vehicle-lab-double.cmd` | 当前源码双精度实验台，使用隔离SDK |
| `vehicle-lab-double-preview.cmd` | 当前源码双精度独立轮心工程预览 |
| 根目录 `试玩-物理开发.cmd` | 先重新编译当前源码的原生扩展，再进入游戏 |

运行素材、`.venv`、`src`原生扩展和`build/sim-double-runtime`留在主目录；包内运行依赖不从归档动态查找。历史物理/radio启动器仍与各自历史包按原相对布局保存在`archive/2026-10-17/launchers`和同批`builds`中。

历史源码、构建、日志与工作树的原位置、提交和恢复方式见归档索引；失败记录保留原结论，归档不代表重新验收。

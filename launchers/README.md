# 启动入口与版本

2026-10-17：当前源码入口统一放在此目录，根目录两个重复的试玩脚本已移除；历史入口记录见[统一归档](../archive/README.md)。直接玩游戏请使用[下载安装版或免安装包](../docs/download.md)。

| 入口 | 内容 |
|---|---|
| `game-current.cmd` | 当前源码游戏 |
| `vehicle-lab.cmd` | 当前源码实验台 |
| `vehicle-lab-double.cmd` | 当前源码双精度实验台，使用隔离SDK |
| `vehicle-lab-double-preview.cmd` | 当前源码双精度独立轮心工程预览 |

需要从源码重新编译原生扩展时，在仓库根目录执行，再运行上表入口：

```powershell
.venv/Scripts/python.exe setup.py build_ext --inplace --build-temp builds/native-temp
```

运行素材、`.venv`、`src`原生扩展和`build/sim-double-runtime`留在主目录；包内运行依赖不从归档动态查找。历史物理/radio启动器仍与各自历史包按原相对布局保存在`archive/2026-10-17/launchers`和同批`builds`中。

历史源码、构建、日志与工作树的原位置、提交和恢复方式见归档索引；失败记录保留原结论，归档不代表重新验收。

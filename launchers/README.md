# 启动入口与版本

2026-10-15：当前成果以主目录main的源码和对应任务证据为准。

| 入口 | 实际内容 |
|---|---|
| 根目录 `试玩.cmd` / `game-current.cmd` | 当前源码游戏，明确选择game；需项目虚拟环境及当前源码编译的原生扩展 |
| `vehicle-lab.cmd` | 当前源码实验台；也可从游戏菜单进入并返回 |
| `vehicle-lab-double.cmd` | 新版试验台双精度普通入口；先从归档恢复隔离SDK |
| `vehicle-lab-double-preview.cmd` | 新版试验台独立轮心工程预览，来自simulation-fidelity/0944541 |
| 根目录 `试玩-物理开发.cmd` | 先编译当前工作区再启动；包含未提交源码，不能用作已提交版本的独立验收 |
| `archive/试玩-RADIO-02.cmd` 及同目录其他阶段名称 | 历史0.8.3 RADIO-02独立包，没有当前游戏/实验台更新 |
| `physics-native-traffic-*.cmd` | 历史r9独立包 |
| `physics-r10-*.cmd` | 历史candidate-r10独立包 |
| `physics-parallel-r1-*.cmd` | 历史candidate-parallel-r1b独立包 |
| `physics-parallel-r2-*.cmd` | 历史candidate-parallel-r1d独立包 |

历史入口保留以便追溯；文件名中的game/simulation不表示当前两条开发方向。`builds/`、`logs/`、`legacy/`及相邻工作树均不参加当前源码自动发现；pytest从`tests/`收集，标准验证只检查`src/tests/tools`。根目录Ruff扫描也排除构建、日志、旧工程和第三方源码。

本次合入simulation-fidelity的25个真实新版提交，不迁移DS/历史工程，也不重建历史独立包。克隆源码后按[README](../README.md)安装项目环境并编译5个原生扩展；双精度SDK由归档及成员SHA恢复到本地build，不覆盖共享.venv。不要把历史包DLL复制到当前`src/`。

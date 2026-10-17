# 当前主版本

2026-10-17：主目录 `CoastalDrive`、分支 `main`，整理前代码基线 `b31f420`。游戏与新版车辆实验台已合并在同一源码树；当前开发与验收事实见[进度页](current-progress.md)。

- 游戏：根目录 `试玩.cmd` 或 `launchers/game-current.cmd`。
- 实验台：`launchers/vehicle-lab.cmd`；双精度用 `vehicle-lab-double.cmd` 或显式工程预览 `vehicle-lab-double-preview.cmd`。
- 环境：项目 `.venv`、`src` 内5个当前原生扩展、`build/sim-double-runtime`；整理不替换这些文件。
- RADIO-02、r9/r10、parallel等独立包均为历史版，统一见[归档入口](../archive/README.md)。旧发布说明保存在[2026-09-30记录](../archive/2026-10-17/docs/release-main-20260930.md)。

历史工作树分支和未合入提交保留，不能把旧包或旧工作树当作当前主版本。用户实验记录仍位于 `%LOCALAPPDATA%/CoastalDrive/experiments`。

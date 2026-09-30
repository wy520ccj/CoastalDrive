# 阶段入口归档

2026-09-30整理。根目录 `试玩.cmd` 是当前唯一默认入口，指向 `builds/0.8.3-radio02/win_amd64/coastaldrive.exe`。

本目录保留阶段入口的原名称，作为兼容入口统一指向根目录试玩.cmd使用的当前独立包，避免旧路径或旧解释器造成版本混淆。固定历史阶段行为以 `docs/tasks/` 和 `docs/evidence/` 中的包路径与commit为准。独立包只保存在本地 `builds/`，源码克隆后先构建。

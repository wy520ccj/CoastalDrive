# 2026-10-17 项目归档

整理前主版本：`main/b31f420`。本批只改变文件组织与版本说明，不改当前运行源码、素材、原生扩展、虚拟环境和双精度SDK。

## 文件在哪里

| 原位置 | 归档位置/处理 |
|---|---|
| `builds/*` | 本目录 `builds/*`，旧独立包保持完整运行文件夹 |
| `build/lib.*`、`build/temp.*` | 可再生编译中间产物，校验后精简；当前SDK留在原位 |
| `launchers/physics-*`、`launchers/archive` | 本目录对应的 `launchers/`，与旧包的相对位置保持一致 |
| `legacy/` | 本目录 `legacy/`；旧MFC源码内部不改 |
| 已结束阶段的 `logs/`、旧验证日志 | 本目录同相对路径 `logs/`；失败/中断原始证据保留 |
| `../CoastalDrive-VI-v1` | `worktrees/visual-identity-v1`，分支 `visual-identity-v1/7dcf30a`；34个未合入main提交保留 |
| `../backups/CoastalDrive-before-AUDIO-01-20260930` | `backups/CoastalDrive-before-AUDIO-01-20260930` |
| Codex `gr86-physics/CoastalDrive` | `worktrees/gr86-physics`，分支 `codex/phys-real-01/8deb721` |
| Codex `simulation-fidelity/CoastalDrive` | `worktrees/simulation-fidelity`，分支 `codex/simulation-fidelity/0944541`；本次新版实验台的来源，不是被丢弃的另一套实现 |

`moves.json`记录主目录954个精确原路径，`external.json`记录外部4个根目录与Git状态。用原路径在清单中搜索即可找到新位置。历史文档中的原路径不批量改写，以保留当时证据的版本口径。

## 校验与精简

- `files.jsonl.gz`、`external-files.jsonl.gz`：迁移前逐文件大小/SHA256清单，本地保存。
- `protected.json`：当前源码/素材/原生扩展/SDK等受保护文件的迁移前指纹。
- `verification.json`、`external-verification.json`：迁移核验结果。
- `prune.json`、`pruned-files.jsonl.gz`：缓存/中间文件精简依据与明细；只有用户授权的可再生内容或已校验压缩副本被删除。
- `repository.bundle`：整理前全部Git分支和完整可达历史；已用 `git bundle verify` 检查，未合入分支没有删除。SHA256见最终总结。

当前 `.venv`、`src/*.pyd`、`assets/game`、`build/sim-double-runtime`及用户 `%LOCALAPPDATA%/CoastalDrive/experiments`不在精简范围。旧工作树中的 `.venv`仍是指向主环境的链接，归档时不遍历或复制共享环境。原 `../ADAS`、`../ADAS.zip`、非项目的imagegen输出等不改动。

## 恢复

1. 在项目根目录运行 `.venv/Scripts/python.exe archive/2026-10-17/check_archive.py verify` 和 `check_external.py verify`检查归档。精简后的最终核验会按保留清单检查。
2. `pwsh -File archive/2026-10-17/restore.ps1`只预览主目录恢复；加 `-Apply` 执行。原位置已有内容会停止，避免覆盖最新文件。被精简的缓存无需恢复；已保留gzip/zip的内容按`prune.json`解压到对应原路径。
3. 外部工作树已注册在新位置，直接使用 `git -C archive/2026-10-17/worktrees/<名称> status`检查；`git worktree list`可查看当前路径。不要直接复制 `.git`文件来新建工作树。需要恢复原位置时用 `git worktree move`；跨盘迁移需复制并校验，随后 `git worktree repair <目标路径>`，再核验分支/提交/状态。
4. 若只需某版源码，不需要整目录恢复：`git worktree add <新目录> <分支或commit>`。若仓库丢失，可用 `git clone archive/2026-10-17/repository.bundle <新目录>`恢复整理前历史；本地二进制和实验日志另外从本归档取回。

本目录内的旧源码可能已不适配当前工具链。保持原版内容用于查阅/恢复，不把旧包DLL或旧源码覆盖到当前主版本。

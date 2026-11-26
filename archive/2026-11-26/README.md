# 2026-11-26 工作区架构整理归档

整理前基线：`main/b5a68cb2`。本批次将历史证据、过时文档、已完成任务包、无引用的单次排查脚本、早期原型文件、旧打包产物与历史运行日志统一归入本目录，保持主干目录结构清晰轻量，同时保留全部文件以供追溯与恢复。

## 归档内容索引

| 原位置 | 归档位置 | 说明 |
|---|---|---|
| `src/phase0_app.py` | `src/phase0_app.py` | 早期 Phase 0 遗留孤立脚本（零引用） |
| `docs/evidence/*` | `docs/evidence/` | 历史阶段验收证据（12,517 文件 / ~5.68 GB）；测试依赖的 21.8 MB 最小夹具已沉淀至 `tests/data/fixtures/`，README 展示图已移至 `docs/screenshots/` |
| `docs/design/*`（旧截图/草图目录） | `docs/design/` | 历史视觉原型与过程截图目录（~180 MB）；轻量化现行设计文档保留在主干 `docs/design/` |
| `docs/tasks/*`（已完成历史任务包） | `docs/tasks/` | ~180 份已完成/封存任务包；当前活跃任务包及模板保留在 `docs/tasks/` |
| `docs/*.md` / `*.txt`（过时阶段评审与旧流水账） | `docs/` | 早期 H0–H4B 评审、Phase 0–5A 清单、旧 SHA256 记录与旧进度归档 |
| `tools/**`（零引用历史检查脚本） | `tools/` | 345 个无引用的单次排查/历史验证脚本及旧辅助文件；72 个活跃工具与构建/验证链路保留在 `tools/` |
| `builds/*` | `builds/` | 历史发布与预览构建目录（~18.9 GB） |
| `build/phys-brake-refine-01`、`road-edge-bullet`、`temp.*` | `build/` | 历史构建中间目录；当前运行时 SDK（`build/road-edge-sdk`、`build/sim-double-runtime`）保留原位 |
| `logs/*`（历史验证与实验日志） | `logs/` | ~64 GB 历史运行日志；本机 KCD2/HD2 渲染运行缓存（`local-kcd-*`、`visual-upgrade-20261024/daylight-29`、`visual-upgrade-20261026/hd2-rock-turing`）保留原位 |

完整精确原路径与目标路径映射记录在本目录 `moves.json`（本地保存，不随普通代码提交推送）。本目录默认由 `.gitignore` 忽略，仅本说明文档显式纳入 Git 索引。

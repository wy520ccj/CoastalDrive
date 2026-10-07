# PHYS-PERF-01 原生加速证据归档

本目录只归档既有产物；此次未启动测试、模拟、构建或渲染。归档清单及每件原件/副本 SHA-256 见 [`archive-manifest.json`](archive-manifest.json)。原始日志仍保留在 `logs/physics/PHYS-PERF-01/` 与 `logs/validation/`。

## 48 拍精度与短测

最终 production comparison 对 0afe6b1 基线比较单车与 8 辆交通车，各 48 个 120 Hz 拍。完整 Snapshot 均逐字段相同：单车 4.644→1.664 s（下降 64.17%），8 车 50.961→19.738 s（下降 61.27%）。这是短时原生诊断，不是 FPS 或前台性能 Gate。

原生端口试验 256 次调用与 Python 逐值精确一致；内存原生向量/T0 子集 510 项通过。向量阶段 48 拍 Snapshot 相同，单车/8车为 1.746/19.986 s；端口增量相对 Python 投影版 2.407/27.258 s 分别快 10.00%/8.59%。

## 验证边界

| 阶段 | 结果 | 运行边界 |
|---|---|---|
| 原生 T0-r1 | Ruff 失败；pytest 未运行 | import 排序/别名规则 I001、PLC0414 |
| 原生 T0-r2 | Ruff 失败；pytest 未运行 | 同类 import lint 问题；原始 summary/log 保留 |
| 原生 T0-r3 | Ruff 通过；510 passed | 修复导入后实际原生内存模块 T0 |
| projection T0 | Ruff 通过；546 passed | 最终投影实现相关机械 T0 |
| native final T1 | Ruff 通过；511 passed；三个 headless 种子 27.3/26.9/27.0s 通过 | 不是新版完整 920 项 |
| earlier native T1 | 920 passed；旧三种子约 28.786/27.889/27.852s | 有效历史结果，但不包含新 projection；不能当作新版完整 920 项 |

本机为 CPython 3.14.2。原生实现需保持 Python 3.14 浮点 `sum()` 补偿求和结果、严格浮点运算与既有 `PORT_TOLERANCE` 约束；MSVC 编译记录使用 `/fp:strict`、`/utf-8`。prototype 的 256 次 exact 对照和 510 项 T0 记录均随本归档保存。

## Profile 与源码身份

当前 16 拍 cProfile 窗口 18.354 s，早期 r1 同协议窗口 91.559 s；几何射线/支持面查询累计约 8.853 s，约占当前窗口 48%。两个 profiler 只用于诊断，墙钟不等于 FPS。

原始 `profile-current/profile.json` 的 `head` 字段仍写为 0afe6b1；旁边原始 `metadata-correction.json` 将实际基线更正为 70d8b94，并说明当时源码有未提交修改。原件未改写；profile 的 before/after Python/C/PYD SHA 映射、归档开始与结束的 98 个 `src` `.py`/`.c`/`.pyd` 哈希及中途变化单列于 [`source-hash-chain.json`](source-hash-chain.json)。其中新增内核是 `src/mechanical_kernels.c`；对应编译产物 `.pyd` 是本地构建结果，不提交到 Git。下一查询优化若改变哈希，应以此处的时间点为参照，不覆盖已记录值。

## 包验证与未通过项

独立包 `builds/physics-native-candidate-r3` 是 projection 前版本。Headless 运行在仓库外的临时目录，game 与 simulation 模式各 120 拍通过，摘要确认完整 98 字段硬件和 tick 报告。更早的 r1/r2 headless 失败，原临时 crash.log 已复制；不把 r3 旧包结果当作最终 projection 包验收。

Render r1/r2 因缺少 `numpy._core._exceptions` 失败；Panda `include_modules` 配置须使用字典形式以隐藏相关 NumPy 子模块。r3 首个 endless-hills 条目 90 s 超时，后两个 not_run；runtime.log 记录约 5 s/frame，未生成截图。原错误日志及临时 crash/runtime 文件已保留；未重跑渲染。

原生扩展 `.pyd` 是生成物，不入 Git；开发源启动通过本地构建机制编译加载。产品包最终验证、前台性能 Gate、T3 与人工体验仍未完成。

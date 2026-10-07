# PHYS-PERF-01 mechanical block evidence

基线 e79af19，隔离工作树 `C:/Users/15120/.codex/worktrees/gr86-physics/CoastalDrive`。本块只覆盖 `mass_response`、`rotor_spin` 与 `wheel_load_terms` 原生函数接入；生产改动在 `src/mechanical_kernels.c` 和 `src/tire_drivetrain.py`，SHA 与完整 `src/tests/tools` Python/C/PYD 哈希见 `source-hashes.json`。捕获期间开始/结束哈希相同。

独立逐值核对通过：`mass_response` 2304 次、`rotor_spin` 768 次；`wheel_load_terms` 1280 次。完整48拍快照在 mass-spin、机械块及 geometry 参考之间单车与8车均逐字段一致。ABBA 在同一进程下先复位 root `contact_epoch` 后，Python/native/native/Python 四条48拍物理字段逐值相同（比较时剔除诊断标识 `contact_epoch`），四组捕获中的该标识全部为0。

同一进程 ABBA 记录：Python 24.1851s/23.7500 CPU s，native 16.2517s/16.0625 CPU s，native 14.3331s/14.1250 CPU s，Python 14.8130s/14.78125 CPU s。保留四次原始墙钟与CPU数据；此短样本存在明显时序漂移，只作为诊断对照，不是FPS或前台性能Gate。快照以 gzip mtime=0保存，payload SHA与原JSON核对。

验证：mass-spin T0 583项、机械块 T0 339项；机械块 T1 的 Ruff、722项 pytest 及三个1200步 headless seed（0/17/23）均通过；机械块 T0为339项，mass-spin T0为583项。实际命令和运行时间见 `validation/*-summary.json`，原日志以 `.txt` 形式保存。T1只代表本隔离版功能块，不等于主目录T2、性能阶段Gate或用户体验验收。

最终T2、独立产品包、T3、前台1080p性能和人工驾驶Gate仍未完成；主目录33657dc与本隔离工作树分开记账。本次只归档已有证据，未重跑测试、模拟或构建。

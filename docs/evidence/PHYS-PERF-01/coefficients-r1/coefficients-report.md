# PHYS-PERF-01 coefficients cache evidence

基线 `fe8bcd3`，隔离工作树 `C:/Users/15120/.codex/worktrees/gr86-physics/CoastalDrive`；未提交改动仅为 `src/mechanical_kernels.c` 与 `src/tire_drivetrain.py` 的系数缓存功能块。全 `src/tests/tools` 下354个 Python/C/PYD 文件的捕获起止SHA相同，状态与关键文件SHA见 `source-hashes.json`。

本次 advance 的三类 Capsule 仅保存数值系数，每个物理子步重新构建；当前载荷、试探速度及法向响应/梯度由每次调用传入。单次接口与缓存接口共用同一内核。2304次 mass_response、768次 rotor_spin、1280次 wheel_load_terms 精确调用记录随输入归档。最终版本与 mechanical-block 基线的单车及8车各48拍完整物理Snapshot字段相同。

最终短样本为单车 `1.2528664 s`、8辆NPC `12.0986585 s`。机械块历史短样本 `1.4912125/21.2201878 s`，运行条件有漂移，不据此声称稳定百分比或FPS。mass-only中间版 `1.2628619/11.4301204 s` 单独归档并明确标为非最终。三个快照均以 gzip `mtime=0` 保存，payload SHA经核对。

最终T0 Ruff与372项pytest通过；T1 Ruff、722项pytest及三个1200步headless seed（0/17/23）通过。早期T0的Ruff失败和pytest未运行、后续T0-r2通过也保留。完整命令、summary和日志见 `validation/`。

本次仅归档现有证据，没有改生产/测试或运行验证。package-r5仍在独立构建中，不纳入本次归档；主目录33657dc T2独立记账。最终包、T3、前台性能和人工Gate尚未完成。

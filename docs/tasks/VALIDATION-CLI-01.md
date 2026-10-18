# VALIDATION-CLI-01 两种积分模式的实际CLI进程覆盖

- 状态：done（两模式实际CLI验收完成）；基线main/fc6c43c，工作区干净。
- 触发：整批T2-after-lab-ui在105通过后首败physics_cli，旧默认Game预期2工作进程，但现Game每拍单机械步不创建无任务进程。
- 范围：tests/test_physics_cli.py的实际外部工作目录短启动，证据及续跑；生产CLI/两种模式积分/进程策略不得改。
- 验收：同一测试分别实跑game/simulation：tick3/2辆交通、Game零进程零远程任务，Simulation2进程18远程任务，均world_required0；完整CLI模块T1/三种子。原失败保留。

- 完整CLI T1 4项/三种子通过，game/simulation均由外部临时工作目录实际进程执行。原0进程不是错误，Game不创建无数值任务进程；Simulation仍确证2进程/18远程求解。生产完全未改。
- 命令`tools/validate.py T1 --tests tests/test_physics_cli.py --output logs/validation/VALIDATION-CLI-01-T1 --timeout 300`；[证据](../evidence/VALIDATION-CLI-01/)。
- 续跑1897项有据覆盖、1619项继续；同一批重复收口改用显式previous/supplement清单脚本，严格节点集合/首败/完整补验计数/改动白名单；不反复增加模式分支，不改通用validate默认fail-fast。

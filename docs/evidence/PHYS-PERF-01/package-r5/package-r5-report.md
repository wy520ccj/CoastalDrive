# PHYS-PERF-01 package r5 evidence

`builds/physics-native-candidate-r5/win_amd64` 的 r5 构建产物与仓库外 headless 记录已归档。HEAD为 `16a7c4a6a665ff69948a5247339394951a1ea4c7`。`package-build-r5.log.gz` 保留完整构建日志和告警；`headless-summary.json`、两个运行日志和检查脚本也原样保存。

构建摘要中的 `coastaldrive.exe`、`mechanical_kernels.pyd`、`wheel_contact_kernels.pyd`、CPython license 与 GR86 配置 SHA，均与当前 `win_amd64` 目录实件逐一匹配。摘要记录 game 与 simulation 两种模式各运行120步、seed17、return code 0，且报告tick及完整硬件字段存在。命令、墙钟和摘要哈希见 `receipt.json`。

当前源码/PYD哈希另存于 `current-source-hashes.json`，代表归档时当前工作树状态；提供的构建日志及headless摘要未包含构建时源码哈希文件，故不把当前哈希表冒充构建时点证据。构建日志中的依赖/DLL/模块警告原样保留在压缩日志中。

该仓库外 headless 结果只证明两种模式的短步运行和配置可读，不构成render、FPS或人工验收。此次仅整理既有证据；未运行构建、测试、模拟或渲染。主目录33657dc完整T2继续独立运行，本归档不与其混计。

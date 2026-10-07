# PHYS-PERF-01 轮胎支撑面原生内核归档

本目录只归档现有对照、profile、源码快照与验证凭据；本次未运行构建、测试、模拟或渲染。每件文件 SHA-256 与压缩 payload 校验见 [`receipt.json`](receipt.json)，源码捕获见 [`source-hashes.json`](source-hashes.json)。

## 实现与数值边界

正式内核为 `src/wheel_contact_kernels.c`，由 `src/wheel_envelope.py` 与 `src/triangle_support.py` 接入；`setup.py` 增加构建及打包隐藏模块配置。支持平面/有限面阶段计算移入 C，轮胎边角仍用原 GJK；原容差及 64/96/20/30 限制保持。面/生产对应的原型归档为冻结的 `support-kernel-r2.c`（SHA-256 `566843f68519b4d3c1b235321ce63604823f320ed1c6f36bee88b997707e9db0`），与2058次exact探针及face pilot源一致；后续r3点/边实验不纳入本归档。正式源码点时快照及构建日志均归档。CPython 3.14.2 许可证副本来源为 [CPython v3.14.2 LICENSE](https://raw.githubusercontent.com/python/cpython/v3.14.2/LICENSE)，部分和算法对应 [CPython mathmodule.c](https://raw.githubusercontent.com/python/cpython/v3.14.2/Modules/mathmodule.c)。

内存探针记录 2058 次精确对照，有限面 pilot 27 项通过。production comparison 的单车/8车各48拍完整 Snapshot 与 0afe6b1、候选缓存版及有限面内存版都逐字段相同。生产版短测单车 1.47169 s、8车 16.16178 s，仅作短时诊断，不代表 FPS 或前台性能。

## 验证与 profile

- wheel T0 初次 Ruff 导入排序失败、pytest 未运行；summary/log 已保留。
- wheel T0-r2 的 Ruff 与 pytest 通过；具体入口与计时见 summary。
- wheel T1 的 Ruff、460 项通过；三个1200拍headless种子约24.2/23.8/23.5 s通过。
- 正式 profile 以 `profile-wheel/profile.json` 为准：seed 17、coastal、8辆交通车、GR86_DESIGN、GAME输入、throttle .3；8拍预热、profile 16拍，窗口 15.476 s，总至测量完成 16.549 s，源码前后 SHA 一致。墙钟仅诊断，不是 FPS。

捕获 HEAD `15457d7` 加未提交轮胎内核改动；哈希链含全体 `src` Python/C/PYD，正式 `.c`、Python接入、setup、许可证另作字节级快照。未合并、未推送；最终产品包、T3、前台性能与人工体验未完成。

# r8 原生候选包归档

主线HEAD为 `7ba4d8a`，性能源码仍冻结在 `fa037c4`。360项源码/数据（PY/C/PYD/JSON/GZ和根setup.py）与运行中 PHYS-INTEGRATE-04-stage-T2 起始summary逐项一致，主源在构建前后未变；归档该次运行的summary快照，不复制运行中的pytest日志。首次构建因源码副本缺少 `requirements.txt` 失败，耗时0.531s；第二次补入实际requirements后成功，build_apps耗时30.3511912s，主360项仍不变。构建副本101项源码/配置SHA和上下文审计一致；两个原生扩展在主源码目录、构建副本、包产物三份字节相同。`assets` 是读取主目录资源的junction，未复制或归档大资源。

候选包的5项实际产物SHA见 `package-artifact-sha256.json`。仓库外Game模式和Simulation模式各运行120拍，退出码均为0、完整硬件字段存在，耗时1.5338705s/1.2547401s。两模式headless不是render、FPS、前台性能或人工驾驶验收。

首次reader入口尝试错误引用证据目录脚本，`parents[3]`导致输出目录创建失败；当时包检查运行0次，原失败收据保留。随后改为从 `logs` 正确入口执行并产生上述两模式结果。仅将原日志与summary归档，未复制整个包或assets junction。

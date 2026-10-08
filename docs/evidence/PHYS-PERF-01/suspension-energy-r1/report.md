# Suspension energy and full-step numerical block

本块修改冻结在 `src/mechanical_kernels.c` 与 `src/suspension.py`。数值account保留原计算顺序，公共势能入口输出不变；完整步仅发布原13个字段。64轮活动集、20/30次迭代上限及原能量门槛均未调整。

独立da6539c Python + 127 DLL基线对比：完整SuspensionStep 16,081次全部字段hex相同，其中zero mobility 10,744；外部6298次elastic调用全部值一致。当前审计JSON只对应最终完整步审计；早期仅能量C阶段的JSON已被后续同counts审计覆盖，原始能量阶段日志仍保留，没有重建JSON。最终完整步audit log为172 passed in 6.57s；较早仅能量阶段log为172 passed in 6.63s。独立T0原pytest为 `172 passed in 5.74s`，Ruff通过；T1原pytest为 `601 passed in 27.01s`，Ruff通过，三种headless种子分别7.8/7.7/7.7s通过。T0/T1 summary的包装耗时按原文件保存。

标准0车/8车各48拍Snapshot与main-fa wall-port基线逐字段相同，耗时0.632112/4.339838s仅诊断，不代表FPS或性能Gate。16步profile为3.0445475s，报告src前后稳定；只用于热点诊断。主fa基线原件、旧127 DLL的源/重命名源/setup/build/manifest及PYD SHA元数据均作为reference保留，不复制二进制。

360项源文件哈希按HEAD `da6539c6c57746a90c75a6379cb97a0f41c0aa1f` 前后相同，aggregate SHA-256 `9e587c619306c5811a60f0d6dd015f848efb1ad7e542f0199700fafdb88f26ef`。目标源码SHA-256：`mechanical_kernels.c` `fde65f7c160413206b49dd74cebe0f18ffda2c5613b916c906aacd8b7f48af6a`；`suspension.py` `26179560fa9ffb9ae05f550f5115ae9b002272a91aaa99ea6f1bd580f10b50eb`。另有既存 `suspension_contacts.py` 工作区修改纳入完整点时清单、未归因于本块。

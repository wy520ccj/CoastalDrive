# PHYS-PERF-01 静态形状边界候选复用归档

本目录归档隔离工作树 `983e978` 加未提交边界/静态几何优化的现有证据。逐件 SHA 与压缩 payload 校验见 [`receipt.json`](receipt.json)，全 PY/C/PYD 捕获与状态见 [`source-audit.json`](source-audit.json)。主目录根因与原失败单子步档案仅[链接](<B:/AI agent/暑期计算机程序设计/CoastalDrive/docs/evidence/PHYS-DESIGN-01/shape-bounds-r1/shape-bounds-report.md>)，不在本目录复制。

## 数据流和性能边界

每个 `world_step` 物理子步从真实世界读取一次静态几何，供本子步所有车辆使用；同一 prepare 中初始四轮查询与末姿态使用相同候选数据，Bullet 推进后下一子步重新读取。Bounds 是只读候选计算数据，不创建第二物理世界或第二车辆状态。护栏 Hull bounds 取自构造 Hull 的同一局部顶点并加相同 margin，不改 Hull；三角形按原索引顺序筛入候选盒，再做原精确求交。门槛、物理频率、参数及64/96/20/30限制保持。

健康车辆48拍完整 Snapshot 对照逐字段相同。九车短测演进：edge 14.195→全扫描42.162→静态缓存32.879→shared 28.317→最终window 16.536 s；最终比0afe旧基准50.961 s低约67.55%，但单车最终1.7867 s，仍慢于edge版1.4763 s。性能保留这项单车回退；所有时间均为短诊断，不是FPS或前台Gate。主目录保存的失败轨迹修复与这些健康车辆性能样本分开陈述。

## 验证历史

- 初始bounds T0/T0-r2：105/40项；bounds T1：462项通过。cache T0/T1：40/50项通过；50项是中间版本，不能算作最终474项的额外覆盖。
- shared T0：39通过、1旧缓存初始化断言失败；r2通过40项。Hull T0 44项、world T0 52项通过。
- window T0与r2的Ruff失败、pytest未运行；r3通过52项。
- 最终bounds T1：Ruff、474项通过，三个1200拍 headless 种子23.299/22.973/23.116 s通过。旧 T1/中间日志均保留。

profile-bounds 来自 shared 阶段而非最终 window 版本，单列归档，仅为诊断。r4包是此 bounds 修复之前的 edge 版；尚无新产品包或前台性能/T3/人工验收。完整T2轨迹、原失败项、剩余1468节点和14项后续检查仍待恢复；不宣称阶段Gate通过。

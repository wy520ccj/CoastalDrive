# CoastalDrive 试验台长期打磨调研档案总索引（2026-11-26）

本目录沉淀了 2026-11-26 围绕“如何将 CoastalDrive 试验台打磨为有实际工程与学术意义的工具”开展的 **5 路并行实证调研**产物。全部结论基于一手开源代码仓/PyPI/Crossref/arXiv/政府法规公报核验，严守不绕过付费墙、不违反数据许可、不编造引文的原则。

## 一、核心成果文件

| 文档 | 内容范围 | 台账分片 | 本地开放资料目录 |
|---|---|---|---|
| **[长期打磨总规划（主纲）](../../lab-long-term-roadmap.md)** | 交叉评审拍板、防重造轮子宪法、统一接口契约、6 阶段 18 个月路线图与首期任务包蓝图 | [总溯源表 sources-register.csv](sources-register.csv)（155 条，全量校验 0 错） | `logs/research/lab-roadmap-2026/downloads/`（44 份原件，103.18 MB，均已校验魔数与 SHA-256） |
| [01-oss-ecosystem.md](01-oss-ecosystem.md) | 10 大开源/商业车辆仿真器与 12 个 Python 控制/优化/IO 轮子横向对比、生态位与许可边界 | [sources-01-oss.csv](sources-01-oss.csv)（35 条） | `downloads/01-oss/`（8 份） |
| [02-standards-and-benchmarks.md](02-standards-and-benchmarks.md) | FMVSS 126 / UN R140 / ISO 3888-2 / 4138 / 7401 / 7975 / Fishhook、16 项 ISO 8855 坐标映射、ISO 19364/22140/19365/18571 V&V 体系 | [sources-02-standards.csv](sources-02-standards.csv)（31 条） | `downloads/02-standards/`（14 份） |
| [03-xbw-control-estimation.md](03-xbw-control-estimation.md) | 2018–2026 顶刊综述（4WID/复合制动/ARS/半主动悬架/估计与 TRFC/容错控制）、34 维零扩维端口与 `CoastalBench-XBW` | [sources-03-control.csv](sources-03-control.csv)（44 条） | `downloads/03-control/`（8 份） |
| [04-data-formats-and-calibration.md](04-data-formats-and-calibration.md) | FMI 2.0/3.0、MDF4、`.tir`、OpenCRG、OpenDRIVE、MCAP/Lichtblick、NHTSA 惯量库/EPA/Stanford/AMZ FSAE 公开数据集与合规红线 | [sources-04-data.csv](sources-04-data.csv)（28 条） | `downloads/04-data/`（8 份） |
| [05-academic-packaging-and-impact.md](05-academic-packaging-and-impact.md) | JOSS 2025/2026 / SoftwareX / 顶刊 Benchmark 发表门槛、高校《汽车理论》6 讲与 FSAE 切入点、Core/GUI/Game 四层拆包与跨平台构建 | [sources-05-academic.csv](sources-05-academic.csv)（17 条） | `downloads/05-academic/`（6 份） |

## 二、资料归档与存储边界说明

- **Git 追踪内容**：全部调研报告（`.md`）与可溯源台账（`.csv`）位于 `docs/research/lab-roadmap-2026/`，轻量纯文本，完整记录每条来源的标题、作者/机构、年份、DOI/URL、实查许可证、获取状态、SHA-256 与决策归类。
- **本地缓存原件（不入 Git）**：44 份合法开放获取的原始 PDF、公有法规、BSD/Apache/MIT 样例文件与开源 README 存放于 `logs/research/lab-roadmap-2026/downloads/`（由 `.gitignore` 忽略，留在 B 盘不膨胀仓库体积）。
- **不可直接下载的受限文献/标准**：所有 ISO/SAE 付费标准、IEEE/Elsevier 付费论文及返回 HTTP 403/TLS 拒绝的站点（如 `nhtsa.gov`/`rosap.ntl.bts.gov` 命令行抓取）均未绕过任何访问控制，在 `sources-register.csv` 中如实标记 `metadata_only` / `download_blocked_403` / `download_failed_tls`，保留官方标准号、DOI 与原始入口链接以保证 100% 可溯源。

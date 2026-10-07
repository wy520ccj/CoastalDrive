# PHYS-PERF-01 点/边驻点内核归档

本目录只归档既有原型、完整快照、验证与独立包证据；此次没有运行构建、测试、模拟或渲染。逐件 SHA-256 与确定性 gzip payload 校验见 [`receipt.json`](receipt.json)，捕获时点、工作树状态和全体 `src` Python/C/PYD 哈希见 [`source-hashes.json`](source-hashes.json)。

## 数值与性能对照

冻结的原型 `support-kernel-r3.c`（SHA-256 `abf34ff96a3d1a1b65e0e6e308c3b1e3925eb2912bd981a2a4edfd843b8dd7b2`）与点/边各1024次exact探针对照一致；正式内核仍保留64次循环。production 48拍全Snapshot与0afe基线、wheel生产版及edge内存版均逐字段相同。

正式生产短测：单车1.4763s，比上一wheel版1.4717s略慢；九车由16.1618s降至14.1951s，相对原50.9606s也记录在对照文件中。单车回退如实保留；所有墙钟数据仅为短时诊断，不是FPS或前台 Gate。

## 验证与包边界

- edge T0：Ruff通过、94项通过；pilot专项27项通过。
- edge T1：Ruff通过、460项通过；3个1200拍 headless种子0/17/23分别24.88/24.903/24.999s通过。
- 独立包r4仓库外 game/simulation 各120拍，分别3.8951/3.6656s通过，summary含完整硬件和tick报告；记录的包内 SHA 包含 `mechanical_kernels.pyd`、`wheel_contact_kernels.pyd`、CPython license与GR配置。此项不是 render、FPS 或人工Gate。

当前工作树捕获基线 `8be0a50` 加未提交 `src/wheel_contact_kernels.c` 与 `src/wheel_envelope.py`；哈希捕获期间源文件无变化。包r4是当前edge版，未包含LU。尚未合并/推送；最终产品验收、实际render、前台性能、T3与人工驾驶均未完成。主目录T2-r11仍在跑18,000拍高速贴地/回收节点。

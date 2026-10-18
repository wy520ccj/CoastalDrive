# 逐门道路复盘证据

基线main/e37d81e。方案库→虚拟试车员A/B→逐门复盘：按首次向前到达的同一位置读完成步，默认漏门或最窄门；滑块/六道门/轨迹与请求响应/载回原B参考试验。复盘不创建Simulation、不推进物理、不覆盖原试验或玩家成绩。

- `normal/`、`double/`：复用上一批真实普通/Double记录的最终宽屏/4:3实际界面、321位置读取和退出结果。第4门原配速度约59.58km/h、余量−0.340m，50k同速、该门余量+0.827m（全程最小+0.793m另计）。终点图中失败A显示未到达，原轨迹截止实际终止步。图两轴比例不同，t为起步后仿真时刻，控制请求为该完成步保持比例、响应是前轴等效角。
- `normal/report/`、`double/report/`为新生成的逐门HTML/JSON摘要；原始完成步、控制请求和完整试验配置位于上一批`../VIRTUAL-DRIVER-01/{normal,double}/report/{A,B}/`，gzip恢复原内容。`record-source-index.json`逐一指向8份原始文件及压缩/解压SHA；本批不重复保存32MB完整快照。工具实际导出目录仍包含完整A/B二进制/CSV/JSON，本证据目录只存新增分析。
- 原物理来源是旧记录中的源码/SDK首末摘要。本次新增只读分析的来源由`source-manifest.json`单独记录9项源码的归一LF指纹，不把新分析代码冒充原驾驶时已存在。`archive-manifest.json`记录36份本批原样输出SHA。
- `checks/ROAD-REVIEW-01-initial`：12项两SDK原始数据/纯读取+5项旧UI，共17项通过。`...-ui`保留2过1失败：测试误用50k全程最小余量0.793m作为第4门期望，原始记录/显示为0.827m正确；随后`...-final-core-ui`20项通过。
- 普通完整相关T1 **87 passed**（153.45s）与0/17/23各1200步启动通过；Double **32 passed**（57.25s）。含原道路真实Simulation完成/新导出、同车确定性/世界释放、参考方案与工作区回归。此处真实物理仅作为功能回归，不把它称为本复盘工具重新驾驶了旧记录。
- 原生guiItem→DirectSlider.commandFunc回调、321位置读数、零步/单侧/未判门、朝向跨±180°、倒车后首次前向对齐、原整车几何/时刻/请求逐项核对、坏判门记录、载回原B参考快照均覆盖。未实际操作系统鼠标拖动或人工驾驶。
- `initial-slider-oversized.png`保留第一版默认滑块遮挡；已改用实验台同类显式尺寸/颜色，最终图已查看。原导出复用工具曾把controls/rows再次放入metadata，导致工具报告详情重复；恢复生产记录结构后12项两SDK原始读取/报告检查补验（1.68s），最终HTML约206KB，未重跑物理。
- HTML导出内容/完整性通过，浏览器渲染仍**not_run**；上一批本地file预览被浏览器安全策略拒绝，本批没有绕过或重复尝试。游戏内实际两分辨率已查看，人工趣味性pending。

复现：`.venv/Scripts/python.exe tools/road_review_check.py --output <新目录> --archive-sdk normal --size 1280 720`；Double经现有`tools/physics/run_sim_double.py`运行同工具、`--archive-sdk double --size 1024 768`。该工具只读已归档真实完成步，界面数据用明确结束记录注入；不是另一轮驾驶、性能基准或真人体验。

物理、默认车辆、策略/道路阈值、SDK/原生模块、玩家进度未改。原T2精度失败、实时与人工趣味性Gate仍开放，T2/T3本批未跑。

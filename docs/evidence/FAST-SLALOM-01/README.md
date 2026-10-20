# FAST-SLALOM-01 高速验车证据

命令、范围与限制见[任务包](../../tasks/FAST-SLALOM-01.md)。新题保留原六门/4米门宽和物理/输入，要求入口至终点全段道路前向速度70–80km/h，成绩与普通练习隔离。

- `normal`/`double`：新真实35/50/70k同策略驾驶，每库5676拍；在原实验台导入下一配方、完成12拍短参考试验并保存，再接回高速题。各段gzip为实际完成步/二值键盘/控制请求/原结果，`recheck.json`为当前纯规则逐拍复核。完整驾驶首末源/SDK均保持；70k约11.403秒金，其他两车漏门。
- `measurement60`/`measurement75`：本轮改题前Normal四种前胎的18043拍探索测量及当时脚本。`ordinary-recheck/summary.json`逐拍核对当前普通规则的全部原字段保持，是原记录重放，不是第二次物理驾驶。
- `restore-summary.json`：最终源码另起实际独立物理进程读取完整最佳及六门参考，成绩文件字节不变；无新完整驾驶。
- `before-final-display`：完整驾驶时两处UI源文件、SHA及最终倒计时提示差异；完整驾驶在纯显示补丁后明确复用。`full-drive-tool.py`按两库当时工具SHA恢复，与完整驾驶摘要指纹逐字节对应。
- `normal-layout-final`/`double-layout-final`：最终空结果/倒计时HUD图及首末源码/SDK；实际驾驶成功/失败/规则图在两库根目录。`layout-old`为漏刷面板旧图、`layout-intermediate`漏右上按钮布局，不作最终验收。已查看宽屏/4:3，仍是离屏图，不能证明人工手感或实时性能。
- `corrected-metrics.json`：原完整驾驶工具对已为度的侧偏误做degrees；原始gzip/summary保持，本文件仅反换算单位，后续工具已修正。各指标截止自身失败/终点，不把不同窗口的峰值作整程收益比较。
- `checks`：T0 44项，最终两库T1各111项及各三种子；`failed-start`与`tool-failures.json`保留失败与观察说明。工具错误不视为驾驶/恢复通过。

`archive-manifest.json`记录138份原始文件的来源、字节数与SHA；`source-manifest.json`记录最终12源码LF SHA。说明和清单不计原始文件数。没有改物理/默认车/旧课题/旧评分/原生模块，原T2失败、实时与人工趣味性Gate保持开放。

# 工程方案库证据

基线main/58fb9b8。本批保存独立工程方案、关联原始试验/奖牌、同条件比较与同车驾驶；物理/默认车辆/原生扩展/SDK未改。人工驾驶/趣味性pending，T2/T3未跑，原精度真实失败继续保留。

- `normal/`、`double/`：实际面板分别运行45k铜牌、50k金牌并保存两套方案；完整B及其工坊原A的experiment.json、snapshots.bin、vehicle.json以gzip保存。方案目录同时保留scheme.json、车辆元数据，解压还原原文件名即可经现有导入读取；HTML/CSV可由完整LabRecord再导出。已保存车辆report_path是当时原始本地路径，不将其冒充可跨机器绝对路径；方案库加载时按方案所在目录重建关联。
- 两SDK的50k实际滨海圈为53.86330077009692/53.86329830494923s，由RouteDriver(60)真实控制请求完成，只有该编号方案更新道路完成；45k仍待验证。保留实际道路成绩/幽灵、当前车辆和流程摘要；这不是人工手感或实时性能结论。
- `restarted/`：最终版本另起进程恢复同一方案库，自动选中当前驾驶方案，恢复原始配置/试验/奖牌和分开的道路进度。宽屏/4:3实际截图均查看；截图冻结更新，仅作布局证据。两方案曲线A/B不覆盖工坊原车A。
- 真实首次流程的`scheme-curves.png`保留当时底部提示与新增按钮重叠的问题；收尾只调该处提示起点/字号/换行，最终排布以`restarted/restarted-trial.png`为准，未覆盖旧图或重复道路圈。
- `checks/`：T0/T1/Double/最终补测完整子命令与终态。首次相关T1为153 passed/1 failed（生命周期替身缺schemes），最终普通26项/三种子补覆盖保存路径与该替身；原未变路径结果明确复用，不称完整154项重新执行。Double原25项后补最终3项；普通最终选中状态1项另记。
- 首次Double实际保存因WinError5拒绝目录改名终止，原失败见task与failure-notes，未进入道路圈，未覆盖旧数据。最终改为记录完成后原子提交scheme.json清单，Double真实流程r2通过。失败外部句柄来源未确定，未加重试/静默吞错。
- `archive-manifest.json`保存复制来源、原始SHA与归档SHA；`source-manifest.json`记录施工源文件归一LF的SHA。原始标准导出及失败残留继续保留于logs/DESIGN-SCHEMES-01，不删除或覆盖用户方案。
- 本目录JSON/TXT原样保留Windows换行，Git按CR行尾检查；pytest原始输出包含自身生成的行尾空格，单独免空白检查，不为通过检查而改写原始日志或哈希。源码仍按仓库正常规则检查。

实际流程工具：`tools/vehicle_schemes_check.py --output <新目录>`；恢复用`--restore <既有流程目录> --output <新目录>`。Double经现有`tools/physics/run_sim_double.py`启动，检查隔离LOCALAPPDATA和方案库，不写用户存档。

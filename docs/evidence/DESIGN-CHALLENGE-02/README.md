# 操稳工坊证据

基线main/ada5e35。本批仅规则/控件/成绩传递与验证，未改物理核心、默认车辆、原生扩展或SDK。人工驾驶与趣味性pending，T2/T3未重跑；原落地制动细化失败保留。

- `preflight-normal/matrix.json`：先验16配方实测结果。每组`score-inputs.json.gz`保留1201个评分完成步的原始标量、元数据和原始完整导出SHA；`manifest.json`核对压缩档与原文件。它不包含完整轮胎内部矩阵/动画，不能替代完整物理复算。完整原始导出仍在项目logs对应路径。
- `preflight-normal/final-rules-recheck.json`：最终规则读取原始完整16组记录，结果与矩阵全部一致；未重跑物理。
- `normal/`、`double/`：实际面板完成的金牌A/B，各`A/`和`B/`有完整`experiment.json.gz`及`snapshots.bin.gz`，解压成原文件名可按现有导入方式读取。保存车辆、实际道路成绩/幽灵、流程摘要和曲线/道路结算图保留；摘要含真实SDK指纹。原路圈普通53.8633007701s/Double53.8632983049s，由现有RouteDriver真实控制请求推进。
- 两库`restored/`：最终版本另起进程从上述保存车辆及原始报告恢复，确认选题/硬件/金牌与保存道路状态；两分辨率中文控件实际图。面板重新复算参考奖牌的`road_validated=false`不覆盖车辆文件已有的道路true；道路与参考试验分开记账。截图期间冻结更新，仅作布局检查。
- `checks/`：原T0/T1/最终补测完整命令与终态；`.log`以`.txt`归档。T1 127项/三种子，后加协议边界普通33项、Double获奖/恢复及20次切题2项。早期Double34项早于下拉字体修复，最终控件与重启图已覆盖修复，不把旧测试作为字体修复证据。
- `archive-manifest.json`：上述复制文件的原始/归档SHA256。`source-manifest.json`为最终施工源文件归一LF指纹，不将Windows换行转换误认为逻辑变化。

实际流程工具：`tools/cornering_workshop_check.py --output <新目录>`；独立恢复用`--restore <保存车辆.json> --output <新目录>`，Double通过现有SDK隔离启动方式执行。工具隔离LOCALAPPDATA并使用新目录，不覆盖用户工程车或成绩。

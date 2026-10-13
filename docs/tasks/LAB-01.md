# LAB-01 车辆动力学实验室

- 状态：done（实现与自动功能完成；人工操作/画面反馈待确认）
- 基线 commit：396084acbf22bc510b399387bd31966c8c63ffe8
- 前置：既有 DrivingExperiment / VehicleCommand / Snapshot；PHYS-PERF-01 实时 Gate 仍开放。

## 目标与范围

同一车辆物理内核提供自由驾驶与实验室入口。首先完成零交通制动试验：车辆、初速、附着、ABS、离线固定步、暂停/单步、真实曲线、A/B、时间轴及 CSV/参数/报告导出；随后扩展精确输入与操纵工况。

- 允许修改：新增 lab_* 与 ui/lab_*、main.py/application.py/main_menu.py 的入口接线、Simulation新增纯平面lab场地（沿用全部车辆方程）、工程参数导出字段补齐、相关测试/验证工具、实验室说明和开发路线。
- 只读：Simulation、DrivingExperiment、VehicleCommand、车辆设计/资源与工程证据。
- 不得修改：车辆方程/机械子步/已认可游戏驾驶参数、悬架准备未提交成果、既有性能证据、公开试玩包。
- 2026-10-13 设计依据锁定为用户认可的生成图 docs/design/vehicle-lab-reference.png；不采用旧VI菜单截图。正文使用Source Han Sans SC Bold，小字号统一提高；默认两张曲线，高级参数/详细信号折叠。
- 初始工作区：setup.py、vehicle_suspension.py、wheel_contact_kernels.c，以及 suspension_prepare.h 和两份对应测试；不归本任务。

## 验收

- [x] GUI 完成初速制动、修改 μ 再运行、固定 A 与 B 曲线比较、导出。
- [x] 完整 120 Hz 信号来自真实 Snapshot；缺失接触信号保持未定义，单位/字段来源可查。
- [x] 暂停不推进物理；单步恰为一拍；回放只读取记录；离线不丢步。
- [x] 输入请求和执行器响应分开显示；模型依据、估计参数和计算/仿真时间清晰。
- [x] T0/T1 与实际离屏渲染通过。
- [ ] 人工操作/画面体验结论。

## 验证与交接

- T0：tools/validate.py T0 --area lab
- T1：tools/validate.py T1 --area lab --area research
- UI：tools/lab_ui_check.py；720p/1080p 真实计算和时间轴截图。
- 本功能不重复性能优化长测；实验室不能替代 PHYS-PERF-01 的实时/人工 Gate。
- T2：实验室小阶段收口执行一次，遇既有失败保留并停止；T3 属整个产品阶段。
- 本地提交仅包含本任务；不推送、不改公开包。

## 交接

代码、数据导出及GUI完成；19项T0、43项最终T1/三种子通过，720/1080p真实截图已看，往返世界/控件/PBR任务释放通过。证据见docs/evidence/LAB/README.md。T2 70通过/1旧海岸长跑求解失败，其余not_run；四模块恢复基线后同残差复现，不声称阶段通过。已有悬架准备工作不归本任务且保留未提交。当前只本地提交，提交SHA以Git实际记录为准。下一步为用户操作反馈，以及原物理施工线处理既有T2/实时Gate。

- 实现提交：396084acbf22bc510b399387bd31966c8c63ffe8..24dbdc2；元数据收尾另见Git日志。未提交仅为开始时已有悬架准备文件。

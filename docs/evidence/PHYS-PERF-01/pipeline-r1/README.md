# 共享数值槽与连续有限几何候选：开发检查点

2026-10-11，主目录 main，基线 `6b4ea7f9726ebcdae757e32796c2ee12fe4ff7b4`。**in_progress，实时与体验目标失败。** 相邻 VI-v1 / gr86-physics 工作树没有参与本批修改。未推送、未更新公开包、未进行人工驾驶验收。

每个车辆进程使用四个有界双向共享槽，直接写原数值包/从共享视图解码，允许同进程排队；原车辆顺序提交给唯一 Bullet 世界。处理编码失败归还槽位、进程退出、取消未完成工作和长菜单暂停；零超时轮询真正非阻塞。

连续有限接触离开预取覆盖盒时，从本子步完整真实几何重新筛选候选，并在覆盖范围内复用。保守球形包络覆盖轮胎全部朝向，舍入边界只向外扩；有限面/边/角求交、形状原顺序、实际末姿态和接触门槛保持。120 Hz、两次真实子步、全部车辆共同物理、硬件/本构/20和30轮/残差不变。全车辆准备、观测和快照尚未原生化。

## 实测

固定种子23、GR86、无限坡道、12辆交通车、困难玩家/game交通输入。

| 测量 | 基线 | 改动 | 结论 |
| --- | ---: | ---: | --- |
| 共享槽早段ABBA完整步，四次各600拍 | 12.393 ms | 11.690 ms | −5.67%，四条SHA相同 |
| 后段完整步，预热1200/采样600拍 | 24.951 ms | 20.349 ms | 单A/B −18.44%，600拍SHA相同；超8.333ms |
| 后段完整单车数值子步，26真实输入×20次 | 2.179 ms | 1.454 ms | 520结果包相同；固定输入串行，非实时/FPS |
| 有效1080p前台物理频率，30秒短测 | 37.832 Hz | 43.488 Hz | 仍慢动作 |
| 同上绘制频率 | 43.303 FPS | 46.205 FPS | 流畅目标失败 |

前台丢时18.325→17.275秒，当前绘制P95 31.461ms。不拼接不同时段测量的收益；单A/B不作为稳定尾延迟或长阶段结论。报告中的passed可能仅表示测量完成，须读compute_budget_met/物理频率/丢时判断性能。

current-late-trace.json带profiler/trace，仅用于定位。静态形状扫描、控制准备、观测、快照及结果收集仍有显著主线程成本；九个求解进程耗时接近，不据此扩展自适应调度。

## 验证与未采用试验

最终相关T1：103项、全Ruff、种子0/17/23各1200拍启动通过；另2项共享槽最终T0通过。31秒菜单暂停/验证入口的16项T0复用。覆盖完整世界候选越界、有限几何、实际静态变更、共同悬架、世界子步、进程生命周期、协议和时钟，阈值未改。实际命令/日志见t1-complete-final.json及同名前缀日志。

失败和原型保存在logs/performance/pipeline-r1：无类型Cython、替代Newton/Anderson、重复坐标变换重构、同步世界进程和自主Session进程均未保留。原生构建首轮诊断入口次序错误已修复，原失败日志保留。T2/T3/长前台和人工Gate未跑或待验。

正常输入NPC改用Bullet原生车辆仅在npc-bullet隔离目录，未整合/未获降低精度授权。仍同世界/真实车身碰撞/120Hz，玩家完整，但NPC机械和辅助被简化，须用户明确选择。最新有效前台91.275Hz物理/81.150绘制FPS/丢时6.442秒，仍未达标，不能用绘制帧率宣称流畅。

## 复现

```powershell
.venv/Scripts/python.exe setup.py build_ext --inplace
.venv/Scripts/python.exe tools/performance/benchmark_physics.py --source src --output logs/performance/<new-name> --workers 9 --traffic 12 --mode simulation --traffic-input-mode game --track endless --shape hills --driver endurance --seed 23 --warmup 1200 --steps 600 --capture-hashes
.venv/Scripts/python.exe tools/performance/trace_presentation.py --source src --output logs/performance/<new-window-name> --track endless --shape hills --seconds 30 --vehicle-design gr86-2022-premium-6mt --driving-mode simulation --independent-clock --physics-workers 9 --traffic-count 12
```

旧source为冻结logs/performance/pipeline-r1/baseline。全部原输入/快照与未保留原型仍在日志目录；源码/DLL SHA与快照相等判据见receipt.json。本轮只本地检查点，无远端授权。下一继续整车准备/主线程观测装配的大块优化，总体任务不关闭。

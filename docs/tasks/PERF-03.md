# PERF-03 — 性能优化统筹与持续卡顿修复

状态：done，2026-09-30用户明确确认“这次性能优化很到位，可以验收了”。验收版本为088ab4a / 0.8.3-perf03，性能优化自动验证与用户体验验收完成。用户此前指令恢复实施，随后追加解决远景突现及优先修复左路肩一暗一亮；基线75413c0及交接成果保留。

此前暂停交接见[问题记录](../evidence/PERF-03/PAUSED-NOTES.md)，行业资料整理见[性能优化研究](../performance-research.md)。本轮允许场景分段生成与合批的按帧预算修复；物理streaming不改。

目标：减少持续帧耗时与运行中分段装配峰值，保持1080p、12车、120Hz物理与全部现有玩法。先测量、保持物理行为，再验证窗口短测及独立体验包。每次30–60秒短测；这轮不安排300秒实验。

本聊天施工范围：application.py、ui/hud.py、vehicle.py、simulation.py、highway_curve.py的精确路面查询、性能工具及对应测试。用户已暂停另一聊天并授权本聊天完整接手；环境与阴影文件已交接。原main/DS、驾驶参数、碰撞、交通决策、UI设计保持。

测量方法：三种路形/固定种子23/12车，2400步快照对比；窗口前景状态逐秒留证，前三秒预热单独记录，采样期不截屏，截屏在测量结束后。CPU剖析运行不作FPS证据。正式性能门槛和人工体验单列。

已学习：[Panda3D局部批次优化](https://docs.panda3d.org/1.10/python/optimization/performance-issues/too-many-meshes)、[PStats](https://docs.panda3d.org/1.10/python/optimization/pstats/index)、[多线程渲染管线](https://docs.panda3d.org/1.10/python/programming/rendering-process/multithreaded-render-pipeline)。保留空间裁剪；只尝试有测量收益的调整，多线程要验证截图、清理和输入延迟代价。

运行证据保存至logs/PERF-03，最终关键报告转存docs/evidence/PERF-03。

## 本轮成果

最终追加路肩修复：用户拒绝只做覆盖边缘渐退，改为固定护栏的连续道路遮蔽，近远保持一致，保留其他动态投影。[HWY-03连续遮蔽](../evidence/HWY-03/continuous-shadow/README.md)记录原因、真实像素对照和51项环境T1。最终弯坡1080p/12车/45秒实际绘制86.12FPS、P95 16.77ms、最长39.73ms、无>50ms帧/采样丢时。新包0.8.3-perf03仓库外三个场景启动及各20次重开、44件高速资源哈希通过；两个试玩入口已更新。下面三路形FPS属于此前远景版，不能当作全部路线的最新材质复测。

采用每帧预算分段步骤和20m原生合批、/Draw引擎管线；只在重开的加载阶段同步补齐场景。按追加反馈接入高速空气透视及草木/远端的距离渐隐，近景颜色和玩法保持。资料：[Factorio作者复盘](https://factorio.com/blog/post/fff-421)、[SuperTuxKart几何对照](https://github.com/supertuxkart/stk-code/issues/3101)、Epic流送预算及Unity距离过渡，具体适用性见研究文档。

245项pytest、Ruff、三种子headless、两种子30秒弯坡物理、三路形Scene复用/菜单/车库检查通过。最终1080p/12车/45秒窗口绘制：直道92.07FPS，弯道81.32FPS，弯坡81.90FPS；显示最长帧30.70–34.08ms，均无>50ms帧/采样丢时/近景未完成节点。恢复基线弯坡58.65FPS/334.08ms/4次>50ms/0.892秒采样丢时。

远景加载边界和树木渐隐经过像素渲染检查，覆盖率随距离递减。任务最终说明、已知边界和复现入口见[证据记录](../evidence/PERF-03/README.md)。本轮性能优化已获用户验收；正式300秒性能Gate未运行，保留为独立测量记录。HWY-03专项画面反馈仍见其任务包。原main/DS、物理参数、碰撞和交通数量保留；本地成果不推送。

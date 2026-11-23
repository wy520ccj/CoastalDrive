# 已成功的优化与RenderPipeline参考

2026-10-28。用户要求回看本项目已成功的优化、别人的经验，并查看发给另一个聊天的项目。已读取“分析 RenderPipeline 汽车画面效果”的原用户链接，确认是[tobspr/RenderPipeline](https://github.com/tobspr/RenderPipeline)，本轮只读代码，不替换渲染管线或画面。

## 本项目实际成功过的做法

[PERF-03原证据](../PERF-03/README.md)记录2026-09-30用户明确验收088ab4a。1080p/12车/45秒旧场景的恢复基线存在334ms长帧；分段预算、20m局部合批、精确查询复用、跳过重复UI写入和/Draw后，最终弯坡86.12FPS、P9516.77ms、最长39.73ms、无>50ms采样帧。该版资产、物理架构与当前不同，这些数字不能作为当前目标或直接速度对照。

可继续复用的是方法：精确复用重复计算，固定资源共享存储，驾驶帧内及时归还装配预算。不能照搬的尝试也有证据：[PERF-04-FIX](../../tasks/PERF-04-FIX.md)曾因Cull/Draw动态HUD闪烁而恢复/Draw；当前继续保持/Draw和120Hz独立权威物理。

## RenderPipeline实际代码

只读版本固定为`f858d071d54902e7d00eb0046dd5730eac9e4678`，通过GitHub连接读取目录树及下列源码，而非依据截图猜测性能。

| 实现 | 代码事实 | 对当前任务的用途 |
| --- | --- | --- |
| [task-scheduler.yaml](https://github.com/tobspr/RenderPipeline/blob/f858d071d54902e7d00eb0046dd5730eac9e4678/config/task-scheduler.yaml) / [TaskScheduler](https://github.com/tobspr/RenderPipeline/blob/f858d071d54902e7d00eb0046dd5730eac9e4678/rpcore/util/task_scheduler.py) | 环境探针选取、6面采集、过滤及远影步骤分在7帧周期执行 | 昂贵视觉维护按步骤错开；物理/驾驶输入不套用分频 |
| [GroupedInputBlock](https://github.com/tobspr/RenderPipeline/blob/f858d071d54902e7d00eb0046dd5730eac9e4678/rpcore/util/shader_input_blocks.py) | 注册PTA存储，绑定输入后用`pta[0]`更新值 | 与已实测有效的分帧相机输入方向一致；保留当前在途帧独立存储，不能直接照搬单份PTA到/Draw |
| [ProbeManager](https://github.com/tobspr/RenderPipeline/blob/f858d071d54902e7d00eb0046dd5730eac9e4678/rpplugins/env_probes/probe_manager.py) / [插件更新](https://github.com/tobspr/RenderPipeline/blob/f858d071d54902e7d00eb0046dd5730eac9e4678/rpplugins/env_probes/plugin.py) | 根据视锥和上次更新挑选探针；只在调度帧执行选取 | 视觉资源维护优先当前需要的工作，避免每帧全量刷新 |
| [配置](https://github.com/tobspr/RenderPipeline/blob/f858d071d54902e7d00eb0046dd5730eac9e4678/config/panda3d-config.prc) / [加载器](https://github.com/tobspr/RenderPipeline/blob/f858d071d54902e7d00eb0046dd5730eac9e4678/rpcore/loader.py) | 仍有同步加载与调试配置，并非全部加载天然异步；配置含本项目不适用的单线程/无MSAA等取舍 | 不整包替换配置，不把精美展示图当成当前驾驶性能证明 |

这里只确认代码方法。未安装、运行或测量RenderPipeline汽车样例，不能声称它在本机更快，也未引入其资源或源代码。

## 其他原作者的有效经验

- [Factorio FFF-421](https://factorio.com/blog/post/fff-421)：空闲机器不做无用更新、重叠覆盖共享登记；机器人站点分项平均1ms降到0.025ms。也记录电网多线程因内存吞吐限制而失败。对应本轮先去掉重复道路查询，不为加线程而改权威物理。
- [Panda3D维护者的实际诊断](https://discourse.panda3d.org/t/project-on-youtube-video-linked-is-very-slow-on-my-computer/30379/12)：降低状态清理份额只移动问题，独立节点过多时仍要处理Cull/几何组织。当前0.1积压已撤回，0.5仅作为有样本证据的分项改进。
- [SuperTuxKart作者同几何对照](https://github.com/supertuxkart/stk-code/issues/3101)：独立对象、全场合并、空间分块及分块LOD结果不同，整场合并反而受到阴影/裁剪代价影响；本项目保留局部边界与原投影，不据其旧硬件FPS作承诺。
- [Panda3D首次出现卡顿的完整讨论](https://discourse.panda3d.org/t/chug-caused-by-render-setshaderauto/29198)：提前准备须覆盖真实模型及其额外状态；该帖有作者确认修复的具体例子。当前树木GPU提前准备实验收益未证明，继续不接入；后续只对有证据的首次准备停顿做对应实验。

## 已落地的一项复用

当前1m道路和两侧路肩共享边线，但每段原来重复投影402个点。按完全相同的局部顶点复用同段结果，查询1206→804；不近似坐标、不跨段积累缓存、不动碰撞路网。真实本机太阳方向下，0/2/4/9四段原/新/新/原的顶点数组、Primitive索引、格式和相对材质状态精确一致。原相同版本计算结果可以复用；画面和120Hz保持。

冷启动首项1.6秒单列，热态原约35–60ms、新约27–43ms是三块表面合计离场构建耗时，不是单帧收益；分帧边界保持，仍需正常驾驶复测。对照检查器首三轮没有同步本机实际太阳公式，附加阴影坐标比较失败，修正后精确一致，没有放宽断言。原值与最终运行另见[投影证据](shared-surface-projection.json)及本任务README。

# CoastalDrive性能优化：行业资料与适用性

整理于2026-09-30。用户本次要求恢复优化，并先学习行业游戏与开发者经验；恢复后重新读取Factorio原作者复盘、SuperTuxKart同几何对照、Panda3D合批及多线程文档和Epic流送时间预算说明。旧暂停记录仍保留为历史。

## 应先改变的判断方式

持续低帧率、偶发长帧和关卡加载是不同问题，应各自测量。Godot官方指南明确区分这三类，并建议先改善算法与设计，再优化细节。[官方指南](https://docs.godotengine.org/en/stable/tutorials/performance/general_optimization.html)

平均FPS不能说明卡顿已修复。Unity区分CPU实际工作、GPU工作和等待刷新/等待命令；把`renderFrame`全部记作GPU渲染成本会误判。[Profiler指标](https://docs.unity3d.com/cn/6000.0/Manual/ProfilerHighlights.html) 对本项目的推论：需要实际帧时间线，尤其对齐新分段的生成、合批、首次上传和阴影绘制；现有cProfile只能定位部分CPU成本。

## 公开引擎和游戏如何处理

| 来源 | 已核实方法 | 本项目可借鉴的内容 | 适用边界 |
|---|---|---|---|
| Unity | 静态物体优先在构建时合批，运行时合批需要生成网格并付出CPU/内存成本 | 对固定工程模块预处理，避免驾驶途中重新烘焙大量重复草木 | 无限道路的种子/里程几何仍需生成，不能整条道路离线固定 |
| Unity | 异步资源上传有每帧时间片，并复用缓冲区 | 为CPU生成和GPU准备分别设置预算，记录队列和超时 | Unity具体上传API不是Panda3D可直接使用的接口 |
| Unreal | 流送、Actor初始化和卸载都可设每帧时间上限及处理粒度 | 拆分重工作并及时归还主线程；回收也需要预算 | 仅在函数之间yield仍可能留下百毫秒原子步骤 |
| SuperTuxKart | 公开草地对照比较独立对象、整图合并、分块及分块LOD；结果表明合并范围影响裁剪和阴影成本 | 保留空间分块和LOD，用窗口对照评估批次大小 | 2018年旧硬件/特定版本结果，不搬用其FPS或阈值 |
| Panda3D | 局部flatten可以减批次；整世界flatten会破坏裁剪 | 使用引擎原生机制，明确保留可裁剪边界 | 运行时flatten本身也要测量；本项目已观察到明显成本 |

来源：[Unity静态合批](https://docs.unity3d.com/cn/2023.2/Manual/static-batching.html)、[Unity上传时间片](https://docs.unity3d.com/6000.0/Documentation/ScriptReference/QualitySettings-asyncUploadTimeSlice.html)、[Unreal流送设置](https://dev.epicgames.com/documentation/unreal-engine/streaming-settings-of-the-unreal-engine-project-settings)、[SuperTuxKart草木对照](https://github.com/supertuxkart/stk-code/issues/3101)、[Panda3D批次指南](https://docs.panda3d.org/1.10/python/optimization/performance-issues/too-many-meshes)。

## 重复树木与实例化

NVIDIA的几何实例化资料说明，重复模型可以共享几何并把实例属性单独提交，从而减少重复数据或绘制提交成本；静态合批则会烘焙并复制顶点。[GPU Gems实例化](https://developer.nvidia.com/gpugems/gpugems2/part-i-geometric-complexity/chapter-3-inside-geometry-instancing)

SuperTuxKart的公开实现分别维护网格缓冲和实例属性缓冲，可作为阅读实例，而非直接移植其渲染系统。[公开源码](https://github.com/supertuxkart/stk-code/blob/master/src/graphics/sp/sp_mesh_buffer.cpp)

Panda3D的场景图`instanceTo()`节约共享存储/动画，却仍逐实例遍历和绘制，不能自动宣称一次绘制全部树木。[Panda实例化说明](https://docs.panda3d.org/1.10/python/programming/scene-graph/instancing) 对本项目的推论：真正的GPU实例绘制还需处理实例变换、边界、材质和阴影着色器；在现有simplepbr管线上直接引入，范围和回归风险显著，当前只列候选。

## 首次资源准备与着色器

Epic通过PSO缓存/预准备降低首次出现某种GPU状态时的卡顿。[PSO缓存](https://dev.epicgames.com/documentation/en-us/unreal-engine/optimizing-rendering-with-pso-caches-in-unreal-engine) 本项目使用Panda3D/OpenGL，这只提供“首次准备要提前”的经验，不能证明当前分段卡顿来自PSO。当前已测到大量CPU装配成本，应先对齐证据。

Panda提供`prepareScene`以提前进行渲染资源初始化。[PandaNode接口](https://docs.panda3d.org/1.10/python/reference/panda3d.core.PandaNode) 是否适用本项目、会不会集中阻塞，尚未测试。简单增加预热渲染帧不等于解决运行期装配停顿。

## 暂停时的建议顺序（历史）

1. 收紧测量：标记每次分段、分清CPU工作与等待，测P99/最慢帧/长帧次数/采样期丢时；窗口测试中不插入截屏读回。
2. 固定模块先预处理，验证源模型、碰撞树、材质和阴影一致；不用大范围重写引擎换取未经验证的收益。
3. 对运行中的生成、合批、准备、挂入和回收分别设预算，先证明最大不可打断步骤足够短，再决定具体实现。普通Python线程不能默认解决计算受GIL限制的问题。
4. 在引擎原生合批、较小空间批次、共享模型和GPU实例化之间做同路线对照。当前20m分桶只有单桶时间较短，总耗时和网格数上升，尚不应接入。
5. 持续渲染成本仍超预算时，再依据GPU与阴影通道证据决定LOD或阴影范围；维持已接受的近景外观与驾驶参数，并让人工画面验收单独完成。

## 本次恢复新增学习与决策

[Factorio FFF-421原作者复盘](https://factorio.com/blog/post/fff-421)记录了缓存、数据布局、机器人调度的成功与电网多线程的失败。电网受内存吞吐限制，线程增加没有让整个存档更快。本项目据此先定位重复查询和分段峰值，不把Python线程或全局多线程当作自动解法；交通/碰撞仍保持原120Hz。

[Epic流送设置](https://dev.epicgames.com/documentation/unreal-engine/streaming-settings-of-the-unreal-engine-project-settings)把加载、组件注册和卸载分别限制每帧时间，并设定检查预算的批次粒度。对应本项目：地形和山体按行计算、设施逐项装配、原生合批限制到20m草木块；Scene在驾驶帧以3ms软预算消费步骤，完整路段才进入渲染树。单次原生操作不可中断，因此同时记录最大步骤和实际总耗时，不宣称硬3ms保证。物理分段仍提前1200m加载，视觉沿用同一存活窗口。

[Panda3D多线程管线](https://docs.panda3d.org/1.10/python/programming/rendering-process/multithreaded-render-pipeline)可分离App/Cull/Draw，提升吞吐但不保证输入延迟改善，并有场景状态复制成本。本轮窗口对照、渲染和生命周期验证后采用/Draw，性能证据以实际Draw回调计数；没有把主线程更新频率当作绘制FPS，端到端输入延迟仍需实际体验。

## 远景过渡

连续护栏的投影不适合只按阴影距离渐退：用户要求近远一致。[Unity Shadowmask](https://docs.unity.com/en-us/engine/6000.0/script-reference/unityengine/shadowmaskmode/shadowmask)把静态遮蔽保留在实时阴影范围之外。本项目太阳方向固定，按0.8m护栏与现有道路坡向计算连续遮蔽坐标，写入额外顶点通道；与动态阴影取较暗值。几何/原UV不改，避免共面叠层和全局关闭投影。排水盖也接入同一坐标，近远都不跟车切换。最终静态镜头移动覆盖探针确认普通路肩颜色不再变化，说明渐退边缘与一致的静态遮蔽是两项不同要求。

用户追加指出远景刷新整块突现。[Unity的LOD CrossFade](https://docs.unity3d.com/cn/6000.0/ScriptReference/LODFadeMode.CrossFade.html)在距离区间内计算混合因子，[LOD Group说明](https://docs.unity3d.com/es/current/Manual/class-LODGroup.html)介绍屏幕覆盖渐变/透明混合。项目使用固定4×4覆盖图样，无随机时间噪声，维持不透明深度写入；草木430–560m渐隐，700m才按原生LOD裁剪整组。山体/地形/海面350–850m混入同一高速天空地平线雾色，850–1050m逐渐退到实际天空，先完成过渡再到1200m物理窗口装卸边界。近350m原有材质色彩保持。

第一次试验直接采样对应天空像素，会把云纹混进山面，已撤回；最终只使用地平线雾色，远端通过覆盖渐隐露出真实背景。窗口短测单独记录，渲染回读用于覆盖率和加载边界验证，不计入FPS证据。

## PERF-04：保留实际后台负载的新版优化

新版HWY-04的低模资产并未比旧资产增加几何负担，不能仅从“新修复后掉帧”推断树木是唯一原因。用户明确要求保留两份阴阳师与动态壁纸，以该使用场景优化。测量保留后台进程，实际Draw回调计数，窗口始终前台且未最小化；切出窗口或同时运行其他诊断的样本不作性能结论。

再次核对[Panda3D官方多线程管线](https://docs.panda3d.org/1.10/python/programming/rendering-process/multithreaded-render-pipeline)：/Draw仍把App/Cull放在一起，Cull/Draw可独立推进原生场景裁剪。本轮先做单因素短测，再在Scene重用、返回菜单、车库和三路形真实渲染验证后采用Cull/Draw。它提高吞吐，不宣称改善端到端输入延迟；物理仍在主线程按120Hz更新。

CPU热点中的车轮临时TransformState会进入全局状态缓存。Bullet车轮矩阵只有刚体变换，直接读取平移及旋转，省去临时状态；q与-q代表相同旋转，既有插值已处理符号。三路形各2400tick对照，所有非车轮旋转字段完全相同，轮转对齐符号后的最大分量差2.38e-7。

沿用Epic流送预算的批次粒度思路：排水盖324个展开顶点按36顶点Geom交还预算，并按完全相同的XY坐标复用道路投影。地形按行预筛原算法必然不生效的群落，种植布局使用32项纯数据缓存。保留同一几何、植被、阴影与远景过渡，不降低交通数量或物理频率。

核对Scene和Garage的实际灯光：每个表面只有一束直射光，环境光另行累计。PBR着色器从8个槽精简为1个，保留有效光源及2048阴影图、4xMSAA和原后处理。实际画面对照与相关回归见[PERF-04证据](evidence/PERF-04/README.md)。

## PERF-04-FIX：动态画面验证修正

用户反馈HUD闪烁后，真实窗口持续更新文字的对照复现了Cull/Draw下动态数字缺失；/Draw同条件正常。Panda3D[动态文字与多线程问题1070](https://github.com/panda3d/panda3d/issues/1070)有类似报告，作为排查依据；本项目以当前1.10.16实际复现为准，不从历史问题的关闭状态推断本机已修复。尝试TextNode.getInternalGeom预生成与Cull合并线程仍不解决当前探针，因此恢复App/Cull同线程的/Draw，不修改引擎依赖或加入逐帧强制同步。先前静态截图和生命周期检查无法证明动态HUD稳定，此后使用OS窗口录像和每帧像素检查。

实时阴影覆盖边缘的混合应覆盖草地/山面/树木等接收表面，不能仅修路面。新增shadow-transition.glsl按阴影UV边缘混合原采样，0.20的归一化宽度形成渐入区，中心区保持原阴影强度；路面现有PCF和固定护栏遮蔽继续独立保持。同一个实际树影探针，单步0.5m的最大亮度变化64.33→2.33/255，完整亮暗差不变。此次是补齐过渡覆盖范围，没有扩大阴影图或改变地图/物理。

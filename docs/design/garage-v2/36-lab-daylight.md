# 36 试验台车辆视窗与跨模式统一

2026-10-28，VISUAL-EXTEND-01。用户要求深入借鉴RenderPipeline，将生涯画面和性能经验扩展到其它UI、模式与试验台。先读取实际实现、浏览完整参考画面，再制作本图；本文件初稿记录事前研究与制作规格，不是成品验收。

## 实际案例与采用关系

原仓库版本固定[f858d071](https://github.com/tobspr/RenderPipeline/tree/f858d071d54902e7d00eb0046dd5730eac9e4678)。浏览器实际显示README汽车图、SSR材质球与插件/昼夜编辑器，非仅搜索摘要。汽车图采用低机位三分之四构图，亮暗条带沿车身曲面形成连续反射，轮胎接地阴影清楚；地面粗糙变化使倒影破碎，避免统一镜面地板。材质球图在同一光照里并列粗糙/光滑/金属，适合检查跨入口一致性。编辑器将功能分组与场景回看相邻组织；本项目试验台已有清楚分区，保留原布局，不搬运调试面板。

| 核对的实现 | 源码事实 | 本项目采用/评估 |
| --- | --- | --- |
| [环境探针](https://github.com/tobspr/RenderPipeline/blob/f858d071d54902e7d00eb0046dd5730eac9e4678/rpcore/shader/includes/envprobes.inc.glsl) | 探针盒视差修正、粗糙度控制反射mip、按空间权重混合 | 优先让试验台与驾驶使用同一已离线过滤的晴空环境；封闭车库仍用本地棚拍反射，不把室内外硬套同一张图 |
| [场景装配](https://github.com/tobspr/RenderPipeline/blob/f858d071d54902e7d00eb0046dd5730eac9e4678/rpcore/render_pipeline.py) | prepare_scene识别灯、ENVPROBE和透明材质，并保留创建对象句柄 | 每个入口显式设置/恢复环境状态；不要把上个模式的反射、遮罩或灯残留到下一个模式 |
| [稳定阴影](https://github.com/tobspr/RenderPipeline/blob/f858d071d54902e7d00eb0046dd5730eac9e4678/rpplugins/pssm/plugin.py) | 启用stable CSM和固定film size，分近远投影；[Python实现](https://github.com/tobspr/RenderPipeline/blob/f858d071d54902e7d00eb0046dd5730eac9e4678/rpcore/pynative/pssm_camera_rig.py)按像素格对齐 | 试验台有限视窗先稳定单灯投影中心，保持轮胎接触；不默认引入多级投影和额外Draw负担 |
| [曝光](https://github.com/tobspr/RenderPipeline/blob/f858d071d54902e7d00eb0046dd5730eac9e4678/rpplugins/color_correction/auto_exposure_stage.py) / [配置](https://github.com/tobspr/RenderPipeline/blob/f858d071d54902e7d00eb0046dd5730eac9e4678/rpplugins/color_correction/config.yaml) | 缩小亮度、在GPU保存曝光、有明暗适应速率和上下限；也支持手动模式 | 试验比较需要同状态同亮度，先统一固定曝光；不因自动曝光导致A/B曲线旁车辆忽明忽暗，也不改变已接受生涯色调 |
| [SSR](https://github.com/tobspr/RenderPipeline/blob/f858d071d54902e7d00eb0046dd5730eac9e4678/rpplugins/ssr/ssr_stage.py) | 半分辨率追踪，另外含速度、历史重投影、上采样和resolve多个目标 | 可评估车库地面局部反射，但当前卡顿目标仍开，先保留现有低成本遮挡反射；不先把全屏SSR铺到所有模式 |
| [加载页](https://github.com/tobspr/RenderPipeline/blob/f858d071d54902e7d00eb0046dd5730eac9e4678/rpcore/gui/loading_screen.py) | loading图创建后手动render_frame两次，源代码不提供后台加载保证 | 沿用当前真实分阶段加载，绘出封面不等于系统一直响应；按最慢不可分步骤检查 |
| [06-Car入口](https://github.com/tobspr/RenderPipeline-Samples/blob/master/06-Car/main.py) | 加载场景BAM、prepare_scene、特定昼夜时间及固定展示镜位 | 画面质量由场景/材质/灯共同决定；不能只替换渲染器就承诺同等效果 |

RenderPipeline代码为MIT；[汽车样例模型说明](https://github.com/tobspr/RenderPipeline-Samples/blob/master/06-Car/MODEL-LICENSE.txt)仅列第三方来源，不能推断模型有同样许可。这里只读研究，不导入对方汽车、贴图或配置。原文和blob SHA保存于B盘logs/visual-extend-20261028/reference/manifest.json。

## 当前实际输入

本轮重新启动实际实验台离屏采图：`logs/visual-extend-20261028/lab-baseline/ready.png`，已查看。保留原1280×720配置/车辆/结果/两张曲线分区和当前默认参考后驱车。当前纯色地面、无天空反射的车漆和细网格使车辆缺少材质与接地层次；不把空图表伪装成已有试验结果。

## 生成规格

- 延续已认可的暖白、海蓝、橙色字体与控件；同一真实页面全部文字、位置、结果空态和操作保持。
- 只改善车辆视窗：同一辆橙色参考车、同一尺寸/轮位/镜位；中性偏深的试验沥青地面，低对比十米网格，淡色定距标线；不增加碰撞障碍、装饰树或建筑。
- 车辆的车漆、玻璃与轮胎能读出不同粗糙度，天空反射与单一太阳方向协调；轮底有清楚接触阴影，阴面仍有细节。
- 试验地面由原生网格/已有CC0沥青资源制作，贴图是视觉米制UV，不改变附着系数；原轨迹、对开路面/凸起等试验标记优先可见。
- 不加镜头光斑、景深、运动模糊、色差、装饰数据或新控制；不在两张空曲线中伪造线条。
- 独立启动和主窗口内实验台都要实际检查；返回驾驶恢复原环境，保留相同物理与120Hz。

生成图已使用内置ImageGen、以上真实截图为编辑参考完成，保存为[36-lab-daylight.png](36-lab-daylight.png)。图中数据保持空态，车辆仍为原橙色参考车，地面/车漆/接地关系可制作；生成器略重画车身曲面与UI字形，这些不作为改模型或改字形的依据。它是制作目标，不能当已实现运行画面。

第一版实际实现已开始：复用已接受48d晴空过滤环境，仅把3.0MiB原环境/metadata/CC0许可保存为独立运行资源，不再读整张20MiB HDR；保留旧模式现用天空。实验台原相机/轮位/模型/布局保持，地面使用现有Asphalt03三贴图，太阳方向按同一源图、投影按像素格对齐；独立启动改用已有ScenePipeline。实际r1仅底色地面缺少灰色与粗糙变化，r2接入同一道路法线/粗糙度公式后灰度更中性，两图均保留；最终效果仍比设计图平，未宣称人工通过。下一检查共享窗口/回放/原生渲染和资源退出。

# 海岸草地材质增量

2026-10-28，继续设计38完整海岸样板。原8K天空、动态水面、道路/树石位置及3.2米镜位保持。总体视觉与性能均未验收，本次不将表面细节当成完整草层或全场景升级。

## 研究、规格与实现

施工前补充设计38的草地规格，复用其短草连续地表与暖受光/冷阴影方向。实看已登记CC0 Leafy Grass完整底色，核对RenderPipeline固定f858d071的rpcore/shader/includes/material.inc.glsl，将basecolor/normal/roughness分别表达于现有PBR，不搬整包管线。

原ground-detail纹理确实参与底色计算；最初判断其完全无效不准确，已纠正。实际问题是仅有底色细节，缺少同源法线/粗糙度。现在只对原inland地形绑定已登记2K Leafy Grass三贴图，按原2.5米尺度铺设。底色以源图sRGB解码后的线性均值归一化，保留原顶点色的草/土宏观分区，避免二次乘暗。法线用屏幕导数建立切线空间，仍接受原环境/单太阳3×3阴影，不增加灯、透明叠地、阴影图或绘制通道。

这只改表面。四份地形Geom的全部顶点数组/索引/相对变换逐字节一致，源GLB未改，见ground-geometry.json。摄影源像素未改，不新增重复资源；三张2K纹理理论RGB字节加完整mip共48MiB，驱动实际显存未测，不能将其当作实际VRAM结论。

## 实际画面对照

1920×1080原/新0、90、225米同镜位采集均完成并实看。草地现在有连续细纹和法线明暗，近处仍像平地毯，缺设计38中的短草立体感，树石/整体照明也未完成，不能称美术通过。三个镜位右半幅及顶部80行像素均完全相同，修改集中在岛内草地；完整像素比较见ground-pixel-regions.json。

[修改前](ground-before.png)、[当前固定镜头](ground-after.png)、[90米](ground-after-090.png)、[自由追车](ground-free-120m.png)、[计时追车](ground-time-120m.png)均来自实际运行，非设计图。固定镜头45帧的renderFrame+sync均值原11.98/8.09/7.62ms，新10.09/6.16/6.94ms，非严格负载交叉试验，不能据此称提速，更不能代替驾驶性能。

## 检查与正常驾驶

T0原地形检查1项/Ruff通过；最终T1环境/滨海/模式生命周期/工作台往返42项、Ruff及0/17/23三个1200步种子全部通过。新增断言检查仅inland使用草地材质、合批后实际Geom保留三贴图和正确色彩空间，原水面时间回归也在同次通过。

正常独立120Hz、默认Draw/1280×720，自由365帧/计时805帧，各静止循线190米、0碰撞/丢时；自由全前台，计时804/805前台，无最小化。模式切换后因失焦暂停，原Esc恢复；不是人工驾驶。中位58.86/16.62ms，P95 93.07/59.74ms，最大134.42/119.32ms，341/95帧超过33.33ms，**性能不合格**，未弱化任何物理阈值或隐藏长帧。对照上一当前负载原材质同样严重卡顿，不能据两轮差值归因或排除材质开销。当前真实摘要见ground-normal.json。

```text
.venv/Scripts/python.exe tools/environment/capture_coastal.py --width 1920 --distances 0 90 225 --output logs/visual-extend-20261028/coastal-ground-r1
.venv/Scripts/python.exe tools/validate.py T1 --tests tests/test_environment.py tests/test_coastal_medals_ui.py tests/test_mode_lifecycle.py tests/test_workspace_transition.py --output logs/visual-extend-20261028/T1-coastal-ground
.venv/Scripts/python.exe tools/performance/check_coastal_modes.py --output logs/visual-extend-20261028/coastal-ground-normal
```

当前PERF69/视觉83份指纹。原登记中仅foundation/coastal_slice及两个对应测试变化；其余物理/镜位/默认天空/水面等均保持，旧登记另存B盘logs。原生复测窗口已结束，不声称留窗。HEAD仍15c321f，无提交/推送，旧工作保持，全部新输出B盘。下一滨海HUD的旧大面板需对照生涯层级重新研究/设计后落地；海岸整体照明/草层、其它地区与用途推广及性能目标仍开放。

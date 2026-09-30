# HWY-04：路牌稳定性、国内标志和林缘布局

2026-09-30，基线 `c427041`。先复现、查阅资料，再修改资产与表现。道路采样、碰撞、交通、120Hz物理和UI没有改动。

## 查阅与应用

- [Panda3D透视镜头](https://docs.panda3d.org/1.11/cpp/programming/camera-control/perspective-lenses)：远处的深度精度受近裁面影响。项目为0.15–1500m、24位深度；本次不改变全局相机，直接消除路牌重复正面。
- [Panda3D三维文字](https://docs.panda3d.org/1.11/python/programming/gui/rendering-text)：三维文字与底板可能闪烁，可使用decal。这里选择离线合并文字、边框、底色与箭头，减少深度层和绘制状态。
- [纹理过滤](https://docs.panda3d.org/1.10/python/programming/texturing/texture-filter-types)：三线性mipmap改善缩小取样。牌面使用sRGB、三线性mipmap和4倍各向异性；单层不透明正面保留正常深度遮挡。
- [现行标志标准查询](https://openstd.samr.gov.cn/bzgk/gb/newGbInfo?hcno=15B1FC09EE1AE92F1A9EC97BA3C9E451&refer=outter)、[湖北省高速公路交通标志和标线设置指南](https://jtt.hubei.gov.cn/glj/glj_zfxxgk/glj_zc/glj_qtzdgkwj/202309/P020230908558139356691.pdf)：高速指路采用绿底白字白边，汉字为主要信息，地名辅以拼音；指引信息应与路网一致。
- [Ubisoft《Far Cry 5》世界生成分享](https://www.gdcvault.com/play/1025557/Procedural-World-Gen)、[GDC植被分布示例](https://media.gdcvault.com/gdc2026/Slides/Wenya_He_Mastering_Massive_Worldbuilding.pdf)：区分生长区域与群内变化，树、灌丛、岩地使用相应群落。应用为全局斑块、林下植被、海湾开口与实际坡面接地，没有引入通用生成框架。

## 原因与实现

旧门架白底板、绿面、文字和箭头相距仅毫米到厘米；文字距绿面约15mm。`check_sign_faces.py`关闭阴影、固定牌子、微移相机，仍在350/480m复现整块绿面变白，说明主体问题是深度竞争；文字远景取样和430–560m细节点阵渐隐还会加重碎裂。

正面现在只有一个纹理面，薄板只保留背面与周边；文字不再作为贴近底板的几何。标志独立使用1200m组裁剪和全场空气透视，不使用草木的430–560m点阵淡出。公里数由预制数字图集直接拼入牌面，沿绝对里程变化，不再用几何文字遮盖旧数字。

门架为14.4×2.7m的一块直行指路牌，最低边5.75m；三个下箭头对齐横向-4.5、0、4.5m的车道。道路统一为游戏设定S18海滨高速，目的地为海滨、临海，没有不存在的出口或600m桥梁倒计时。桥名牌在跨线桥前18m，采用较高支撑避开声屏障。弯道牌仅在前方方向确实变化时出现；下坡警告对应前方下降坡度；限速保留100。字形使用已有思源黑体Heavy，是游戏近似字形；没有把虚拟道路或建模尺寸称作真实公路测绘成果。

旧植被按15/22/27m步长逐株重复，远山还直接摆放无树干树冠。新版用160m全局区域形成有长短、疏密、横向深度的群落，配合树下灌丛和低草；山脚灌丛避开陡坡并插值实际12×10m山体三角面。近景以5m道路地形三角面落地，林下色斑直接写入唯一地形的顶点颜色，不增加贴地重叠层。原碰撞树干的位置、网格、尺度与朝向仍由原segment定义。

阔叶树每款从6400三角附近降至1220，独立树冠540、灌木簇400三角；新的连续叶冠替代枝端小叶球与尖锐叶片。运行资产、Blender源、离线制作和布局代码分别存放。

## 功能位置

| 文件 | 职责 |
|---|---|
| `src/environment/expressway_signs.py` | 单层牌面、纹理过滤、动态公里数 |
| `src/environment/expressway_vegetation.py` | 群落分布、林下颜色、草簇、坡面接地 |
| `src/environment/expressway_route.py` | 设施里程、道路组装与既有逐帧预算 |
| `tools/environment/make_expressway_sign_faces.py` | Pillow离线绘制牌面，不进入运行依赖 |
| `tools/environment/build_expressway_signs.py` | 尺寸化支撑、薄板、门架及BAM导出 |
| `tools/blender/build_expressway_landscape.py` | 树冠/灌丛模型和可编辑Blender源 |

证据、验证和性能边界见[HWY-04任务包](tasks/HWY-04.md)。

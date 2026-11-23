# 33 随车视角的树冠受光体积

2026-10-26，接续31/32。先核对当前真实HD2沿海120m图、已有作者研究，再内置imagegen生成33，随后才制作受光候选。

## 研究

沿用26实际查看的[Petr Sušanka KCD2林路](https://petrsusanka.artstation.com/projects/6LxVJw)与[Stefan Williams HD2岩体](https://stefanwilliamsc.artstation.com/projects/nJEX9X)完整作品；本轮重新打开作者页面。树冠、林下、石脚要形成连贯体积，细节服从主次。本轮ArtStation JSON重新下载返回403，未谎称取得新原图。

本轮读[Gaijin原作者工具说明](https://gaijinentertainment.github.io/DagorEngine/dagor-tools/addons/3ds-max/dagor-maxscript-toolbox/editing_normals_tool.html)，下载并实际查看01/04/07示例：树冠中心影响整体受光方向，强度允许与旧法线混合；树皮与根系须排除。它不是本机KCD2的原引擎算法，也不保证当前原树采用后有效。

## 施工规格（候选前）

- 原追车相机、路形、车辆、HUD、天空29与曝光保持。复用原树、草、岩壁，不新解无关资源，不改物理。
- 先诊断原树叶法线正背面的处理。原几何面法线与用于树冠大形的着色法线分别考虑，避免直接翻转已弯曲的大形法线造成叶卡跳变；候选必须排除树皮。
- 若仍碎，试原树冠中心与局部枝簇尺度的混合法线，保留原叶纹细节、透光、天空遮蔽与自阴影。先0/中等/强三个幅度对照，强幅度仅作诊断。原顶点、UV、面序、LOD、alpha、太阳深度保持；不能以闭合球冠替代原轮廓。
- 以实际沿海120m完整画面选型，再正常山脊行驶与六镜位核对，另记帧耗。0遮罩树皮与草不受新项影响，阴影保持需实际GPU证明。
- 33中石脚植被仅为连接目标；本块先完成树冠材质，不额外随机加树。超出当前岩体尺度的生成变化不照搬。

## 设计检查

33把碎叶亮暗收束成较大枝簇，保留林中空隙；仍稍偏黄且改变了车/HUD/牌架/路形，因此只采用树冠体积与阴面层次关系，不复制这些偏移。图为设计目标，不能冒充运行结果或用户接受。

原生成文件：C:/Users/15120/.codex/generated_images/01a176ae-d7d8-7c32-b8b8-dd960f672321/exec-561919c7-c11f-44e4-ba13-548fb975a345.png。完整提示词另存。本轮基线副本和新实验放logs/visual-upgrade-20261026-canopy（junction至C盘），避免继续占满B盘；原文件保留。

## 实机选型与收敛

r01宏观法线候选错误地在赋值前读v_texcoord，编译器报未初始化；该部分无效，修正后r02重采。只保留原叶片朝向、或40%/70%树冠椭球法线混合，仍不能明显改善整体，因此均不采用，不改变源法线。另核对原树解析器已排除material2的shadow_proxy，没有发现误绘代理。

r03参考[NVIDIA原作者的阴影抗锯齿](https://developer.nvidia.com/gpugems/gpugems/part-ii-lighting-and-shadows/chapter-11-shadow-map-antialiasing)，实际比较原读取、3×3帐篷权重/1或2纹素步幅、混合法线+过滤。选择2纹素步幅的单纯过滤，只接木本tree_shader（包括幼树/矮木），草沿原路径。9次硬件深度比较采样，权重总和16；原太阳深度、分辨率、偏移、密度和源alpha保持，不是移除自阴影或复原原引擎光照。320m/4096²下最大单轴采样偏移约15.6cm。该项只缓解碎影，仍须实测开销，不能称已达到33。

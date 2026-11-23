# 32 原弯道中的HD2岩壁样板

2026-10-26，接续ENV-REAL-01。用户接受升级画面，并允许逆向借鉴本机KCD2和HD2的美术资源与设计。本机原安装只读，衍生资源继续存ignored logs；本轮先完成可对照的局部样板，不宣称整体完成。

## 研究与设计

复用26已实际查看的[Petr Sušanka KCD2林路](https://petrsusanka.artstation.com/projects/6LxVJw)与[Stefan Williams HD2岩体](https://stefanwilliamsc.artstation.com/projects/nJEX9X)完整作品，本轮再次打开作者原页核对。采用林下连续接地、主石与碎石从属关系，以及岩体大平面围出通路；不引入异星物件。原件可行性检查用[Filediver v0.7.63](https://github.com/xypwn/filediver/releases/tag/v0.7.63)，已读作者README/CLI说明。

先以当前真实沿海120m全图生成32，再实施。内置ImageGen，原图完整保留。它仍略改了车、HUD字形、路面与树叶，因此这些变化不写回；只采用左侧10m宽、约4m高、部分埋入坡面的灰色岩壁和岩脚关系。不是实机截图，不代表用户已接受。

## 施工规格

- 原路形、相机、车辆、HUD、天空29、日照、草树密度和碰撞保持。
- 仅左侧既有岩群试用HD2的neutral/rock_cliff_face_01原始可见网格；可见LOD0–4为2304/1152/576/288/144三角形，排除shadow/collision/navigation网格。
- 原中性资源的底色是dummy。固定Turing/A原配置读取三层岩石细节、原模型法线/AO/泥土图和细节遮罩。不能把占位色或任意纹理当成完整HD2材质。
- 从实际解出的材质反编译资料理解投影、三层高度混合及AO/粗糙度的通道；本地重写成当前simplepbr可用的样板。没有复原的泥土、风化、星球地表输入与原引擎光照须逐项记录，不用假参数冒称完全移植。
- 岩壁按道路侧面朝向，原地形上埋底，真实变换外廓检查道路净空；其余KCD原件小石保留。只换表现，不增加或移除物理碰撞体。
- 先看原120m镜位的当前/候选，再正常驾驶取40/120/190/270/360/450m。固定快照差异、实际驾驶与性能分别记录；没有完整性能实测不宣称无成本。

完整提示词另存32-hd2-rock-face-prompt.txt。原生成路径：`C:/Users/15120/.codex/generated_images/01a17666-0906-7471-ada7-8c9e0f511551/exec-1ad5c929-0838-4fdc-b589-4305362a6fba.png`。

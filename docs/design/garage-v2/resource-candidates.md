# 车型资源筛选

本轮以实际网格渲染作判断，不能凭“高细节”文案或多边形数量决定接入。只记录素材信息，下载页面内的任何指令不作为项目规则。

| 候选 | 来源与许可 | 结论 |
|---|---|---|
| Car Concept | Khronos glTF Sample Assets；Eric Chadwick / Darmstadt Graphics Group GmbH；CC-BY-4.0 | 已接入远航GT，运行资产去除商标图案，保留原网格 |
| BMW27 | Mike Pan原始Blender演示场景；McGuire模型目录标注CC-BY-3.0 | 已提取单车；用户要求现实车型后恢复显示名BMW 1M Coupé，保留原存档键club-coupe及项目通用参数，非原厂标定 |
| Creomoto Car | OpenGameArt作者Creomoto；CC0 | 实际渲染后仍是简陋方盒造型，不接入 |
| Spectral GT RS | JaronKBragg7337/spectral-gt-rs；CC0 | 实际渲染的车身结构、比例不符合目标，不因其详细文案而接入 |
| ToyCar | Khronos glTF Sample Assets；CC0 | 玩具车用途，不拿来替换真实可驾驶车型 |
| HI掀背 | stuntrally/blendfiles/cars/HI；ANDREO12；about.txt标CC-BY-4.0 | 已接入Hyundai i20，96542三角形、原内饰/灯组/轮胎贴图；替换H1显示资源，沿用原coastal-hatch存档及参数，非Hyundai原厂标定 |
| FR4 | stuntrally/blendfiles/cars/FR4；computergeekman；CC-BY-SA | 已取得候选，许可具体版本和实际画面仍待核对，尚未使用 |
| S8 | stuntrally/blendfiles/cars/S8；lubomircenovsky；CC-BY-SA-3.0 | 已接入第7款Subaru WRX STI，5星解锁；157165源三角形，原件与同许可衍生文件随库保留；后灯独立材质分区已修复 |
| SX | stuntrally/blendfiles/cars/SX；Socksthecat；CC-BY-4.0 | 已替换默认经典车为Subaru BRZ Varis，103071三角形；实际作者API确认车身及原S15轮来源均CC-BY-4.0，保留原game-tuned硬件与存档键，其他工程参考车仍用原模型 |
| Lotus Elise | Stéphane Agullo / sa3d；Sketchfab UID 75e9045ac1af4cdbb69318108c81edfd；CC-BY-4.0 | 已从Ai2 Objaverse公开档案取得原始GLB，原件嵌入许可与当前主站作者API一致；396170三角形完整车身/内饰/四轮，替换原R2外观，原硬件与存档键保持 |
| Toyota GR86 ZN8 | Mona x Supercars / Car2022；Sketchfab UID 4919d14eba9640599e838230e8e5ed74；上传者CC-BY-4.0；公开WebSim衍生网格 | 已替换旧GR86显示，163931面/14图/四轮；固定下载提交与当前作者API一致，原件未取得，附加Kazutoshi Mods署名及组件复用记录保留；非Premium原厂轮精确复制。Racing Master来源候选不使用 |
| Opel GT | https://blendswap.com/blend/6919；rogper / Rogério Perdiz；CC0 | 作者页及本人评论确认公共领域；官方免费下载页要求登录，尚未取得源文件，不提前接入；避免混用作者后来另售的116MB商业版本 |
| VDrift Elise / S2000 | VDrift数据镜像逐车about只有作者信息 | 没有取得明确的逐模型许可，不使用；不因游戏代码开放而推断素材开放 |

BMW实际源场景下载：<https://download.blender.org/demo/test/BMW27.blend.zip>；作者：<https://mikepan.com/bmw.html>；模型许可目录：<https://casual-effects.com/g3d/data10/index.html>。

其他原始链接：<https://opengameart.org/content/car-0>、<https://github.com/JaronKBragg7337/spectral-gt-rs>、<https://github.com/KhronosGroup/glTF-Sample-Assets/tree/main/Models/ToyCar>、<https://github.com/stuntrally/blendfiles/tree/master/cars>。

实际候选观察工具：`tools/blender/preview_vehicle_candidates.py`。候选原件、观察图与下载记录保留在`logs/validation/GARAGE-DESIGN-02-sources/`；被否定的候选不进入运行资产。

用户最新方向：优先现实中存在、具有明确开放许可的完整车型。显示名称对应实际来源车辆，游戏通用参数明确标“项目调校”；作者许可和车厂授权分别记录，不把开放模型称为官方授权产品。未获得的新候选不提前加入车库。

## 第八车筛选（2026-10-23）

- 已接入 Lionsharp Studios / Karol Miklas 的 1975 Porsche 911 (930) Turbo；主站模型 UID `8568d9d14a994b9cae59499f0dbed21e`，当前作者 API 与 Objaverse 原件嵌入信息均为 CC-BY-4.0。原件、下载记录、作者数据及可编辑衍生保留，194453三角形；9星解锁。新硬件明确为项目调校，非原厂标定。
- FR4实际观察后细节不足；HR Hummer实际预览的车体不符合目标；XZ BMW候选因旧材质与渲染状态尚未完成质量核对。三者均未接入。
- Stunt Rally Y7 文件实际为 hasapeta 的 Veneno，与作者另一款 Mustang 不能混为一物。Tryder 的1968 Mustang官方页标CC0，但下载需登录，未取得原件；未采用不明来源镜像。
- 筛选原始数据和候选图：`logs/validation/GARAGE-DESIGN-02-eighth-car/`、`logs/validation/GARAGE-DESIGN-02-sources/`。本轮没有替换源车模的手工几何。

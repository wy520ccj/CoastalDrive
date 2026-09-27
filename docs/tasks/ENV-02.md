# ENV-02：海岸示范段地貌与接地精修

基线 5667ff1；状态：实施、T1与打包验证完成；本机标准性能采样通过，人工视觉验收 pending。用户认为 ENV-01 仍有随机摆放、地表单薄、树石与地面/海水脱节的问题，本轮针对这些问题实施，不将样板称为已验收场景。

范围：既有 0–360 m。去掉孤立巨大岩岛、均匀花石阵列及没有道路可达关系的小屋；设计起点草坡、松林岩坡、开阔海湾与灯塔礁四段节奏。视觉地貌、顶点颜色/材质过渡、树根与埋岩、岸线浅水/水线同步设计。精修已有资产，允许减少实例。

白名单：src/environment、必要 scene 装配、assets/game/environment、art/coastal、tools/blender、tools/environment、对应 tests 与文档。冻结 application、ui、vehicle、simulation、session、traffic、coastal_map/world_props 碰撞定义和原 main/DS。新增地貌仅在护栏外；既有碰撞物的视觉不得消失形成隐形障碍。

分区沿用 environment-art.md；地貌采样放 terrain.py，海水接触资源独立生产。宏观位置明确列出，随机只用于簇内微变化。不建立 WorldGrammarEngine，不扩图，不加玩法、车辆或驾驶 FX。

验收：多视点/驾驶截图无悬浮根部、裸露岩石底面、硬圆盘接地和无依据的房屋；坡脚草土石有连续过渡；浅水与泡沫沿实际视觉岸线；保留道路完整净空；T0/T1 与资源导入、接地、边界测试。单独性能采样，不与测试/构建并发，记录节点/几何数量与帧耗时；人工视觉接受仍由用户确认。

## 实际交付

地貌GLB覆盖现有岛面和岸坡，以统一接缝与材质；新增隆起、景物重排和旧树冠替换限于0–360m。范围外保留原高度/景物布局，但整片岛面共用新的细节贴图，海岸共用湿岩/水色规则。这不是新增全图布景。

- 地貌按起点草坡、三组松林岩坡、留白海湾、灯塔礁组织。移除示范段原先均匀散布的道具、没有通路的小屋和重复巨型崖岛实例，保留源资产。
- 增加 `terrain.py`：护栏外视觉坡面与岸坡、土/草/露岩顶点色、原树根接地约束；`coastal_slice.py` 从最终三角面采样，树和岩石按根脚周围的最低支撑点埋入。原道路边缘逐点一致，既有碰撞树位置、树干网格和变换保留；原岩石接地误差小于6cm。
- 12件原有Blender资产库精修为11278三角形，树冠改为六层展开的枝簇，岩石成为连续岩体，灯塔补窗/入口和开放式灯廊。示范段原锥形树冠替换为同套枝簇；不是全地图换树。
- 独立可编辑 `coastal_terrain.blend` 导出24790三角形GLB，其中1800片双面草叶；512px地表微纹理以实际导入的 `texcoord.0` 绑定。所有制作发生在离线工具，游戏加载资源。
- 海水使用768px岸线距离贴图，来自最终岸坡和礁石三角面与海平面的真实交线；浅水色、湿岩与窄泡沫带沿同一岸线连接。未建立水体物理或动态岸浪系统。
- UI、Application、车辆/物理、Simulation、Session、交通、地图与世界碰撞定义相对5667ff1无差异。原main工作区保持干净，DS未读取为实现来源。

## 验证与证据

Python为 `../CoastalDrive/.venv/Scripts/python.exe`。离线岸线烘焙另外使用本机已存在、带NumPy/Pillow的Python，不改变游戏依赖。

| 检查 | 命令 / 结果 |
|---|---|
| T0 | `tools/validate.py T0 --area environment --output logs/ENV-02/T0`：Ruff及当时24项通过；之后新增原岩石接地测试由T1覆盖 |
| 最终T1 | `tools/validate.py T1 --area environment --area appearance --area core --tests tests/test_ui.py tests/test_ui_assets.py tests/test_ui_theme.py tests/test_traffic_impacts.py --output logs/ENV-02/T1`：75项通过，0/17/23三种子各1200步通过 |
| 固定视点 | `tools/environment/capture_coastal.py --output logs/ENV-02/accepted-views`：5个1080p实际渲染；目录名不表示用户接受 |
| 窗口驾驶 | `tools/environment/drive_slice.py --onscreen --output logs/ENV-02/drive-final`：8车、种子23、365.10m实际物理驾驶通过，保存5帧；短测58.09FPS/P95 20.24ms，截图样本不作性能Gate |
| 其他赛道 | `src/main.py --smoke --track highway --output logs/ENV-02/highway-smoke`：渲染及20次重启节点/任务/事件稳定通过 |
| 构建 | `setup.py build_apps --build-base builds/0.8.3-env02`：完成，运行模型/纹理/GLSL均打包，Blender文件不打包 |
| 独立包 | 从系统临时目录执行 `coastaldrive.exe --smoke --output <本轮绝对日志目录>`：渲染与20次重启通过；见package-smoke.json |
| 性能长采样 | `tools/environment/drive_slice.py --onscreen --benchmark --output logs/ENV-02/performance-clean`：预热30秒、采样300秒；单独运行，不截屏、不与测试/Blender/构建并发。RTX 4060 Laptop：平均60.35FPS，P95 20.03ms，P99 22.47ms；18105帧/300.002秒，实际总里程4715.64m，达到60FPS/25ms门槛 |

代表截图、测试摘要和最终文件哈希保存在 `docs/evidence/ENV-02/`。模型来源和当前哈希见 `assets/game/environment/source-manifest.json`；长期分区见 `docs/environment-art.md`；离线重建步骤在 `art/coastal/README.md`。

## 已暴露并修复的问题

- 首轮地表细节未生效：glTF加载后的UV名是 `texcoord.0`，不是默认纹理坐标；改接入并新增实际导出/绑定测试。
- 中心点接地不能保证背坡根脚接地：改周边最低支撑值，测试覆盖实际导出地貌。
- 初版近岸扩宽会盖住既有碰撞岩石：近路斜率保留，增加旧岩接地回归。
- 初版距离图重复首尾点使零长线段生成NaN：最终直接由三角面交线烘焙；检验岸线近零距离与远海饱和值。
- 草叶正反重复面在glTF导出时去重：改为单三角形+双面材质，导出三角形计数与源数据一致。
- Blender本地撤销备份 `.blend1` 保留在磁盘并忽略，不当作源交付，也未删除既有备份。

## 保留的限制

- 这是针对接地与景观组织的第二轮迭代，树冠低模感、灯塔礁宏观轮廓、纹理重复和远景丰富度仍与设计图有差距。尚不能宣称“Golden Slice视觉验收通过”。
- 物理地面冻结，新增地貌只在护栏外展示；新装饰没有新增碰撞。任何越过护栏后的新可交互地形需另立任务。
- 构建继续提示既有缺失DLL依赖（api-ms-win-core-path-l1-1-0.dll、PROPSYS.dll）与平台模块；本机包启动通过不代替干净机器验证。运行日志还有既有窗口Icon路径警告，本轮不动UI资源加载。
- 人工仍需来回驾驶确认树石比例、坡面连续性、灯塔构图、水线运动及视觉舒适度。下一轮依反馈继续精修这段路，不自动扩全图、不做车辆/FX/AI。

## 性能结论与收尾

正式采样期间丢弃仿真时间为0；启动/预热阶段累计2.267秒，不能写成全程零丢帧。应用update任务CPU平均4.46ms、P95 5.89ms；它不包含全部渲染开销，GPU耗时未测。整场景545节点、270 GeomNode、1457 Geom、266410三角形，均非当帧可见量或draw calls。

这次是单台RTX4060 Laptop、种子23的标准窗口采样通过，不是跨设备或全设置性能证明。没有为达标改控制、交通、车辆或仿真补偿，也没有放宽门槛。

75项T1之后，仅给原树冠替换测试增加护栏净空断言；2个对应参数化案例再次通过，最终Ruff通过。发布资产逐文件与源码树SHA-256核对一致。独立包README/来源哈希在构建后同步，未修改产品代码。工作区成果作为一个ENV-02本地提交，未推送；旧main与DS保留。

## 人工接受与尺度收尾

用户在c166498后明确表示ENV-02基本人工验收通过，只反馈灯塔尺度偏小。采用整体1.2倍实例缩放（标称14m变为16.8m），位置、礁石、地形、岸线及碰撞均未改。基座下缘仍埋入原平台约5cm，缩放后的底座保持在礁台内；140m/225m固定相机构图已查看。T0环境25项通过。证据在 `docs/evidence/ENV-02-polish/`。此为独立小提交，海岸环境冻结，进入VEH-01；更新后的组合体验包随VEH-01交付。

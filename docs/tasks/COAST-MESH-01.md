# COAST-MESH-01 海岸坡面反向造成的缺面与尖片

- 状态：done（实现与自动检查完成，人工体验待确认）；基线main/591a99a，开始前工作区干净；单条施工线。
- 用户目标：修复截图中弯道外侧路基在海面上出现尖三角、坡面缺失的同类问题。
- 已复现：生成器与实际GLB的coast对象均6144个面朝向地下；开启背面剔除后从道路上看不到应有坡面，弯道侧视露出反面尖片。
- 范围：`src/environment/terrain.py`、对应GLB/Blender源、必要环境回归、固定镜头工具与本任务文档。不得修改道路/碰撞/物理/驾驶参数或其他环境布局。
- 验收：整个环路坡面正面朝外；道路接缝、树石接地保持；真实导出资产的面朝向正确；全环固定视角前后渲染检查。
- T0：`.venv/Scripts/python.exe tools/validate.py T0 --tests tests/test_environment.py --output logs/validation/COAST-MESH-01-T0 --timeout 300`。
- T1：`.venv/Scripts/python.exe tools/validate.py T1 --area environment --output logs/validation/COAST-MESH-01-T1 --timeout 300`。
- T2/T3不适用本次局部视觉修复；自动渲染与人工驾驶分别记账，用户视觉体验待确认。
- 交付：完成后记录实际命令/证据及本地提交；不推送。

## 实现与证据

- 仅反转coast对象6144个三角形的绕序，同步重导出`coastal-terrain.glb`和`coastal_terrain.blend`。未增加双面渲染、未改坡面形状或道路/物理。
- 加入生成器及真实导出GLB的全部坡面朝向回归；旧版本该检查明确失败。原25项环境检查保留，接缝/碰撞岩石/树根/泡沫距离检查通过。
- `.venv/Scripts/python.exe tools/environment/export_terrain_data.py --output logs/COAST-MESH-01/terrain-input.json`；Blender 5.2.2以`--background --python tools/blender/build_coastal_terrain.py -- logs/COAST-MESH-01/terrain-input.json`重建。
- `.venv/Scripts/python.exe tools/environment/bake_shore_distance.py`重烘焙后PNG SHA256仍为`a4634ab1a2afde0075dcc86e3b8cf4f7f09d81d492ee96da9fa02f122ee340dd`，没有贴图差异。
- `.venv/Scripts/python.exe docs/evidence/COAST-MESH-01/check_geometry.py`核对591a99a：生成器全部顶点/颜色精确相同，仅坡面绕序反转；导出全部24790个三角形的位置/颜色/UV按无向顶点记录精确相同。内陆、礁石、草丛布局保持。
- 固定镜头工具增加`--distances`，保留默认原五镜头及整数文件名。前后各用`--width 1280 --distances 0 40 80 120 160 200 240 280 320 360 400 420 440 460 480 520 560 600 640 680`采集20个视角，输出分别为`logs/COAST-MESH-01/before`和`after`。320/360米复现截图中的反面尖片，修复后呈连续岸坡；两套总览及360米原图已查看。
- [持久证据](../evidence/COAST-MESH-01/README.md)：前后360米、修复后全环20图总览、镜头报告、几何比较器及结果。静态镜头不证明人工驾驶或性能。

## 自动检查与失败记录

- T0：上述命令，Ruff及26项通过，日志`logs/validation/COAST-MESH-01-T0`。
- T1最终：`.venv/Scripts/python.exe tools/validate.py T1 --area environment --output logs/validation/COAST-MESH-01-T1-r4 --timeout 300`，Ruff、53项及0/17/23各1200拍通过。
- 首次T1的8项高速测试在`Scene.close()`失败：旧手工装配对象遗漏WORKSPACE-01新增的`sun_path`，只补齐4处测试对象，不改Scene。首补将测试灯放到render下使“半段不得挂接”计数多1，r3的1项失败保留；最终测试灯独立于被测路段树，原断言不放宽。r2被同期其他界面施工的临时未用导入阻断Ruff，未改其文件，r4已通过。
- 开始时工作区干净，执行期间出现另一批WORKSPACE-ART-02界面/背景/工具修改；本任务不覆盖、不纳入提交。T1 metadata如实记录同期状态。
- T2/T3、可见窗口长测和人工驾驶未跑；本包只完成局部视觉修复，不扩大为阶段验收。

## 交付

- 本地提交范围：本任务源码、地形GLB/Blender源、3个环境测试、固定镜头工具、资产/制作说明、任务/进度与证据。提交以Git历史中本任务标题为准；不推送。
- 重开现有游戏启动器即可加载修复资产。用户实际驾驶画面待确认；若仍有其他位置异常，以新截图和里程另定位。

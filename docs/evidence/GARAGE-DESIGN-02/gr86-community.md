# GR86 ZN8社区模型替换

基线 `0f2e6872`，2026-10-22，单线本地施工。只替换原GR86简易显示资源，保留车库既有设计布局、5星解锁、存档键和全部硬件；总包继续in_progress。

## 资源与实际修改

- 主作者：Mona x Supercars / Car2022，[Sketchfab原页](https://sketchfab.com/3d-models/toyota-gr86-zn8-4919d14eba9640599e838230e8e5ed74)，作者API当前标注CC BY 4.0。模型是二代ZN8社区外观，配ADVAN改装轮，并非Premium原厂轮/饰件精确复制。
- 本项目实际下载的是[公开WebSim衍生数据](https://github.com/prozac0401/WebSim/blob/3d00ddc9665f0ae7efcaf00cad11e4064d7e7345/evolving_vehicles_2/assets/models/gr86-runtime.js)，固定提交 `3d00ddc9665f0ae7efcaf00cad11e4064d7e7345`。原始payload、上游来源/署名/转换记录、当前作者API和下载SHA保存在 `art/vehicles/sources/gr86-community/`。没有取得原始Sketchfab GLB，不把上游下载声明当成本项目操作。
- 源轮贴图含Kazutoshi Mods附加署名，原文件还记录了组件复用与Roblox导出工具信息；这些记录完整保留，不声称上传者独立创作全部组件，也不声称Toyota官方授权。另一个注明来自Racing Master的非商业候选未使用。
- 下载JS仅作为数据保存，用正则提取gzip/base64后读取数值，不执行外部代码。主网格166669面中有2738个相同顶点索引的重合面：Ln3 314、Ln4 2422、前轮2；显式去重后163931面进入GLB/BAM。不是替换源几何或阈值简化。
- 保留所有14张源基色图、UV、源法线、完整车身/灯组/内饰和独立四轮；轴向/面序转换，车漆与玻璃PBR修正。可编辑打包场景 `art/vehicles/gr86_community.blend`；两段转换工具分别在 `tools/blender/prepare_gr86_community.py`、`tools/vehicles/prepare_gr86_community.py`。运行资产/许可在 `assets/game/vehicles/`。
- 真实模型渲染目录缩略图及接地阴影；现有车漆面层、显示世界、Snapshot轮姿和道路批处理直接复用。原GR86完整硬件/碰撞外廓保持，源车漆曲面宽度与旧简单壳有差异，对应测试改查真实源车身宽度范围，未放宽任何驾驶/物理评分门槛。

## 验证与界限

- `tools/validate.py T0 --tests tests/test_gr86.py::test_imported_appearance_preserves_nominal_body_and_actual_axle_tracks tests/test_career_garage.py tests/test_ui_theme.py --output logs/validation/GARAGE-DESIGN-02-gr86-community-T0`：23过1失败。失败为测试把重复使用的纹理实例数当成唯一图像数，修正为14个源纹理名的完整集合；并非生产纹理缺失。
- 最终 `tools/validate.py T1 --tests tests/test_gr86.py tests/test_career_garage.py tests/test_ui_theme.py tests/test_vehicle_designs.py tests/test_vehicle_visual_parameters.py tests/test_design_spawn.py --output logs/validation/GARAGE-DESIGN-02-gr86-community-T1`：Ruff、37项测试、0/17/23各1200步启动全部通过。新增测试核对作者API/源与运行SHA、实际三角面/纹理、四轮和打包许可。
- 旧源有重合面，初次打包166669断言失败；去重后163931面明确记账。初次独立Ruff漏Loader导入、早期玻璃/贴图因子转换偏白，均已修正；早期图不当最终证据。
- `gr86-baseline/summary.json` 逐字段对比基线模块与当前10个完整设计配置，全部相同。不改Simulation、120Hz、原GR86资料账本或驾驶调校。
- `garage_design_check.py --car gr86-2022-premium-6mt --output logs/validation/GARAGE-DESIGN-02-gr86-flow --size 1280 720`：正常锁定/换车/购件/安装/恢复/涂装取消保存/返回原赛事及显示资源不累积通过。12张实图已逐张检查，240新道路拍仅验证新资源正常显示，没有新完整赛事驾驶。
- `garage_design_capture.py`：最终1024×768五页和1280×720后向一页已检查，0新道路拍。隔离星级/积分为界面夹具，不读写玩家文件、不代表本轮完赛成绩。
- 已有GR86动力学/静载测试本次重新执行；先前完整驾驶结论仅复用。没有T2/T3、可见长时性能或人工试玩结论。

## 归档

- `gr86-flow/`：12张实际正常流程图与摘要。
- `gr86-final-1024/`：4:3五页及摘要。
- `gr86-rear/`：尾部实图及摘要。
- `gr86-verification/`：T0/T1摘要、pytest简报与10套完整配置比较；`gr86-source-sha256.json`记录本增量执行源码/资源SHA。

当前车库7个槽位均使用有来源的细节网格，其中6款是现实车型；GT仍为开放概念车，不伪称现实车型。道路环境精细度、生成设计与实际渲染差距和用户画面/趣味性体验仍开放。本增量本地提交，不推送。

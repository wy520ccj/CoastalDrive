# 默认BRZ与WRX后灯分区

基线`174567c4`；本地施工，未推送。默认`game-tuned`/`sports`外观替换为真实Subaru BRZ Varis，仍是项目原1200kg/约99kW/2.2m轴距调校，非Subaru原厂标定。车库数量仍7辆，旧逐车配置、颜色、改装键不变；三款工程参考车保留原外观及几何契约。

来源与转换：

- [Socksthecat BRZ](https://sketchfab.com/3d-models/subaru-brz-varis-8fecd93279644ada9111c5bfa2226327)、[同作者S15车轮来源](https://sketchfab.com/3d-models/nissan-silvia-s15-custom-2c3481e502c24d818d23a5eb2be8dac9)的公开API均确认CC-BY-4.0，原JSON在`art/vehicles/sources/subaru-brz/`。原始场景来自[Stunt Rally可编辑源库](https://github.com/stuntrally/blendfiles/tree/master/cars/SX)，CryHam的分组/UV/AO移植和纹理署名保留。
- 提取`SX_body`、`SX_interior`、`SX_glass`及完整`SX_wheel`；排除未合并源备份、额外`SX_glass2`玻璃组和无关场景。最终103071三角形，不以新建几何体代替车身/车轮。可编辑衍生文件打包纹理、只保留本车场景。
- 离线按原2.2m轴距移动轮拱、适配旧碰撞外廓；内外饰两套原贴图保留。源红图提取红通道遮蔽供改色，明确重新加载中性图。原自定义法线不适合变形后曲面，实图诊断后重建车身法线/40度折边；仅合并重合点，源三角面保留。
- WRX原转换清空材质槽时，Blender会把面编号全部归零；3550个后灯源面因此误用内饰贴图。本轮按源编号恢复后灯材质，几何三角形仍157165；补充真实加载检查，要求运行资产存在`Rear lamps`分区。新BRZ内外饰转换同样显式恢复面编号。
- 两款实际车缩略图和接地阴影同步。原始来源、工具、衍生与运行资源SHA见`brz-wrx-source-sha256.json`；当前设计资源清单已更新，上一轮`subaru-source-sha256.json`保留为旧版本证据。

验证：

- T0：`tools/validate.py T0 --tests tests/test_vehicle_visual_asset.py tests/test_career_garage.py`，15项通过；此后法线微调与排除额外玻璃由完整T1覆盖。
- T1：完整`test_career_garage`、`test_appearance`、`test_career`、`test_career_ui`、`test_vehicle_visual_parameters`、`test_vehicle_visual_asset`，39项及0/17/23各1200步通过。日志`logs/validation/GARAGE-DESIGN-02-brz-T1/`。
- 参数：基线`174567c4`原10套完整配置逐字段相同，设计数量也相同，`brz-baseline-summary.json`。无Simulation/评分/阈值变更。
- `garage_design_check.py --car game-tuned`正常选车/锁定分支、购买/恢复、涂装预览取消保存、返回赛事、键盘、资源生命周期及真实道路显示240拍通过；最终12图为`brz-1280/`。与旧完整赛事分别记账，本轮没有新跑完整赛事。
- `brz-1024/`最终四页静态实图；`wrx-rear-material/`为后向145度输入后的真实后灯图。全部隔离9星夹具，静态采集0道路拍；不是人工审美验收。源日志前缀`logs/validation/GARAGE-DESIGN-02-`。
- 初次素材探测误取顶点法线对象名产生KeyError、SX.car初始目录404、BlendSwap匿名页面首次403，后续分别按实际对象名/数据目录/标准公开下载页查明；未改变用户运行程序去掩盖这些离线工具失败。初版法线和轮面图保留，不充当最终画面。

敞篷候选[rogper Opel GT](https://blendswap.com/blend/6919)已核实CC0，但其官方免费[下载页](https://blendswap.com/blend/6919/download)要求登录；当前没有源文件，不声称已接入，也不混用后来另售商业版本。R2/GR86简易资源、材质光照与道路精细度仍开放；总任务in_progress，人工画面/趣味性待体验。

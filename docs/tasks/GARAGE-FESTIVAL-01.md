# GARAGE-FESTIVAL-01 车库、收藏与车型

- 状态：in_progress；基线`5633869c`，起始工作区干净；单条施工线。
- 本地实现/资产/证据提交`0be4629a`，范围`5633869c..0be4629a`；116文件均属于本包。新布局的人工画面/手感未验，不推送。
- 用户目标：继续改善过于简陋的表现，改装集中到车库，参考地平线系列，并丰富车型。
- 实现范围：真实3D车库展示；我的车辆/升级改装/涂装直接导航；可查看并驾驶的不同车型；每车型配置保存/切回恢复；赛事与车库前后衔接。
- 参考：[FH5 Upgrade Heroes](https://forza.net/news/forza-horizon-5-upgrade-heroes)的改装、试驾、保存或放弃；[官方车辆目录说明](https://forza.net/news/forza-horizon-5-confirmed-car-list)的收藏与已获得车辆展示。采用交互结构，不复制美术或虚构官方车型授权。
- 新增三款原创通用车型：轻型前驱掀背、轻量后驱敞篷、四驱GT；现有经典双门/GR86继续可用。新增车辆具有独立配置，不修改原车配置或权威物理机制。
- 车库里预览/取消不写入当前车辆；明确选择驾驶/应用涂装时保存；旧工程草稿、A/B、方案和成绩不迁移或覆盖。
- 不修改：Simulation、120Hz、旧车辆参数、旧记录；不推送。
- 验证：车型资产实际渲染与尺寸、真实起步/制动/转向；换车→改装→换回→复载；预览取消；宽屏/4:3真实页面；相关T0/T1。人工画面/手感单列，不由自动测试代签。

## 实现与验证记录

- 车库统一“我的车辆 / 升级改装 / 车身颜色”，主菜单改为同一入口。逐车配置和涂装独立保存，预览不覆盖当前车；保留原工程车辆列表与完整元数据。0星掀背、3星敞篷、5星现有GR86、9星四驱GT；已保存工程车不因换车消失。
- 用户再次指出强行堆叠后，停止采用叠层方案，阅读NN/G分组/视觉层级与Xbox XAG112并重新划分空间；来源和落实规则见`docs/design/garage-layout-study.md`。左车、右操作、车下选择带、页尾返回互不遮挡。标签简化为文字/下划线，实际网格部件外廓控制镜头留边，方向键按画面位置移焦。
- 新资产由原创Blender源文件导出，四组原文件可编辑；旧五种车辆配置对比基线全部相同。新车参数为通用设计值，非OEM实测。
- 原静止起步、真实二值键盘及唯一权威物理：三款各起步/停车/绕桩共9次、25881新驾驶拍，全部成功。道路显示另在实际应用三款各240拍×两画幅=1440新拍；最终纯布局改动复用这些道路图/轨迹，不重复跑物理。

| 车型 | 赛事 | 新拍 | 实际用时 | 结果 |
|---|---|---:|---:|---|
| coastal-hatch | first-drive | 2246 | 18.717s | 3星 |
| coastal-hatch | parking | 2346 | 19.550s | 3星 |
| coastal-hatch | slalom | 4267 | 35.558s | 3星 |
| coastal-roadster | first-drive | 2045 | 17.042s | 3星 |
| coastal-roadster | parking | 2272 | 18.933s | 2星 |
| coastal-roadster | slalom | 4210 | 35.083s | 3星 |
| coastal-gt | first-drive | 1975 | 16.458s | 3星 |
| coastal-gt | parking | 2323 | 19.358s | 3星 |
| coastal-gt | slalom | 4197 | 34.975s | 3星 |

- 初T0 9过/1失败：旧工程车换出后无法从列表选回；修复实际保留列表，独立节点通过。主T1 43过/5失败：1项旧目录断言、4项旧Scene替身缺少规则标识接口；更新相关测试夹具，三个完整模块T1 16项及种子0/17/23各1200步通过，原其余32项不重跑。新布局完整UI T0 6项、末次部件取景/车库视角T0各1项通过；合并49不同用例，非一次完整绿T1。
- 命令：`.venv/Scripts/python.exe tools/validate.py T1 --tests tests/test_career_garage.py tests/test_career_ui.py tests/test_appearance.py tests/test_vehicle_designs.py tests/test_vehicle_visual_asset.py tests/test_vehicle_visual_parameters.py tests/test_tire_tuning.py --output logs/validation/GARAGE-FESTIVAL-01-T1 --timeout 240`。失败重验`--tests tests/test_appearance.py tests/test_vehicle_visual_asset.py tests/test_vehicle_visual_parameters.py`；后续UI按`layout-T0 / framing-T0`摘要记账。
- 真实UI命令：`tools/garage_festival_check.py --output logs/validation/GARAGE-FESTIVAL-01-layout-v4-1280 --reuse-road logs/validation/GARAGE-FESTIVAL-01-final-v2-1280`；4:3另加`--size 1024 768`及对应目录。每画幅13张新静态页面+3张已完成道路图；界面星级为夹具，不能当新驾驶成绩。v3及更早摘要scope旧文案含“240新拍”，以0新拍/720复用和来源字段为准；最终v4已明确复用，旧日志不重写。
- 预览取消、购件/安装、换车/换回、逐车涂装、完整配置文件复载和返回原赛事实际操作通过；新布局检查所有按钮不与展示区相交、真实部件外廓投影留边和方向焦点。两画幅最终32张已查看，首版/叠层旧图保留并明确废弃。
- 最终源码/资产与证据SHA、失败及修正摘要/日志、9份原始轨迹、道路显示原轨迹、工具快照在`docs/evidence/GARAGE-FESTIVAL-01/`。Ruff/diff检查；没有T2/T3、可见性能或人工观感/趣味性通过结论。
- 状态：自动功能块完成；用户已否定此前叠层风格，新版人工画面与手感仍待反馈，目标保持active。仅本地，不推送。

- 末次联系表发现145°后视被车库墙挡住，旧空白图保留；车库预览改用70°镜头并重新按部件外廓构图，镜头留在室内，前后视实图和相关T0已确认。驾驶相机/FOV不变，无新增物理拍。

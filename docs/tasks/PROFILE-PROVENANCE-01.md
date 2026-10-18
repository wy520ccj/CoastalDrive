# PROFILE-PROVENANCE-01 GR86新增机制字段来源闭合

- 状态：done（来源/数值一致性及自动/渲染完成，人工体验待确认）；基线main/15e083e，开始前工作区干净。
- 触发：GAME-GHOST-01-T2在667通过后首败`test_gr86::test_source_fields_and_exact_rating_anchors`，后续not_run。10个新增字段已由当前导入语义赋默认值，但原GR86来源表没声明。
- 目标：逐项说明默认开关/参数/曲线空值的含义、单位与设计来源，保持整份实际VehicleConfig和原参数分区完全不变；不能把工程初值称为实测。
- 范围：该GR86 JSON的metadata、现有F1中的来源说明/分类显示、相关来源/同硬件测试、生成工具同一句型/验证映射及证据/任务/进度；不新增参数编辑能力，不改物理、数值、公开来源或任何实车标定结论。
- 验收：来源表完整覆盖实际配置，每个value与实际导入值一致；原参数JSON与前后配置SHA相同；未启用机制明确标注；相关普通/Double检查与T1短种子。
- 先记录基线文件内容一致性与原失败，再改metadata；先跑完整GR86节点，若触发既有输入模式旧断言，按当前Game单子步/Reference双子步保留硬件一致性要求，不改生产数值来迁就。
- T2失败记录保留；修复后从未执行范围有证据续跑，避免把已通过667项全部重跑。源配置改变或原失败复现不一致时重新界定复用范围。

## 结果

- 100→110项来源表，value逐项与实际配置匹配；明确关闭的独立轮心/回正/螺旋弹簧，通用径向参数、40kg与0.08m、空曲线/预载含义。原参数/导入配置完整SHA均保持，见[证据](../evidence/PROFILE-PROVENANCE-01/README.md)。
- F1显示具体basis；原厂manufacturer正常译为原厂，改值不沿用原分类。原滚动面板、同一个工程配置，没有新参数编辑或状态模型。
- 原首败T0留证；第二个旧模式断言按当前积分策略更新，只归一tire_substeps仍比较其余完整硬件。未改物理/车型数值。
- 普通T1：`tools/validate.py T1 --tests tests/test_gr86.py tests/test_parameter_help.py tests/test_physics_config_io.py tests/test_vehicle_designs.py tests/test_vehicle_parameters.py --output logs/validation/PROFILE-PROVENANCE-01-T1 --timeout 300`，22项和三种子通过；Double相关T0 9项通过。渲染工具最后修改只修截图同名覆盖/滚动位置，Ruff补验通过。
- 下一步接续GAME-GHOST-01整批T2未执行部分；不把本包通过称为整批通过。仅本地提交，不推送。

# VALIDATION-COMPLIANCE-01 玩家与原生交通的弹性配置边界

- 状态：done（两模式配置/重建验收完成）；基线main/1f15e18，工作区干净。
- 触发：T2-after-surface在554通过后首败旧Game交通config身份断言。正常交通TrafficVehicle本来就关闭胎体弹性/完整传动，不应被配置测试改回完整车。
- 范围：tests/test_tire_compliance_config.py的Game/Simulation交通预期，证据/续跑；禁止改生产模式、参数、原生策略。
- 验收：玩家始终保留用户选择，Simulation交通同一完整配置/选择；Game交通保持原生与禁用弹性，同时保留输入刚度/阻尼数值；reset/rebuild不丢选择。完整模块T1/三种子，原失败保留。

- 完整10项/三种子T1通过；只修测试预期。Game交通禁用弹性但刚度130000/阻尼850仍保存；Simulation保持配置对象身份和用户弹性选择；玩家完全不变。原554通过/1首败及补验在[证据](../evidence/VALIDATION-COMPLIANCE-01/)。
- 命令`tools/validate.py T1 --tests tests/test_tire_compliance_config.py --output logs/validation/VALIDATION-COMPLIANCE-01-T1 --timeout 300`。
- 累计2471项有据覆盖，余1045项继续，原T2与人工Gate未通过。仅本地提交。

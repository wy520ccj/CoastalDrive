# VALIDATION-LIFECYCLE-01 工坊关闭生命周期测试夹具

- 状态：done（自动验收完成）；基线main/114fc8f；只增加DRIVING-STOP-01规划草稿，未改生产代码。
- 触发：整批T2-after-impact在958通过后首败实验台关闭测试，旧SimpleNamespace没提供新增工坊对象。
- 范围：tests/test_lab_ui.py该夹具与关闭顺序断言、证据；禁止生产fallback掩盖内部接口缺失。
- 验收：完整lab_ui模块T1，显式工坊停止→旧实验世界释放→窗口关闭且重复关闭无副作用；原失败保留，接续未跑范围。

## 结果

- 只补测试替身workshop.hide和调用顺序/仅一次断言，生产close_game保持不变。完整tests/test_lab_ui.py的36项与三种子通过，原958通过/1首败与T1日志在[证据](../evidence/VALIDATION-LIFECYCLE-01/)。
- 命令`tools/validate.py T1 --tests tests/test_lab_ui.py --output logs/validation/VALIDATION-LIFECYCLE-01-T1 --timeout 300`。
- 续跑同脚本`--after-lab-ui`，1788项明确复用（含该模块前3项去重），余1728项与T2未跑长测实际执行；原失败/人工Gate保持，未改物理。

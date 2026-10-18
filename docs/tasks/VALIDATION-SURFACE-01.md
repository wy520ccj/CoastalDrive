# VALIDATION-SURFACE-01 对开附着报告读取实际轮接触

- 状态：done（真实标签/报告验收完成）；基线main/fc90d7f；工作区只有续跑脚本Ruff集合写法修正，测试/生产干净。
- 触发：T2-after-cli的6通过后，physics_testbed对开附着轮面标签全为grass；工具仍从停用的原生射线坐标x=0推断，实际快照为左右各2轮。
- 范围：tools/physics/testbed.py的表面标签读取和相关报告测试；不得改表面函数/摩擦系数/物理/命令。该标签用于报告，不承担轮胎施力。
- 验收：真实四轮快照标签逐项一致、2 asphalt/2 grass，完整physics_testbed T1及三种子，Double该真实节点；原报告失败保留，阶段未通过。

- _wheel_surface_types只改为读取实际完成快照；测试新增逐轮完全相同，保留2/2要求；不改轮胎实际表面函数。完整physics_testbed T1 6项/三种子、Double真实对开附着1项通过，[证据](../evidence/VALIDATION-SURFACE-01/)。
- 命令`tools/validate.py T1 --tests tests/test_physics_testbed.py --output logs/validation/VALIDATION-SURFACE-01-T1 --timeout 300`。原6通过/1失败保留；续跑累计1907项复用、1609项未执行继续。仅本地提交。

# VALIDATION-CONTACT-02 路线回归的当前接触读数

- 状态：done（自动验收完成）；基线main/3109a1a，开始前干净。
- 触发：T2-after-h1两项通过后首败H2路肩，仍直接读原生射线。针对剩余pytest入口检索同类用法，另找到H3交通、phase3道路采样及其check_route依赖。
- 范围：tests/test_h2_map.py、tests/test_phase3_map.py、tools/phase3_route_check.py的接触只读采样，证据/任务及后续续跑；不改控制器、物理、路线/速度/翻滚/碰撞/离地门槛。
- 独立原生悬架探针继续读原生状态；不趁机迁移未纳入当前T2的历史可见工具。
- TrafficVehicle专用原生轮胎/悬架快照不提供wheel_contacts。初次将H3交通也换成普通车读数不适用，完整测试53通过/1失败后已恢复原断言；该节点单独补验，不能把空元组视为接地。
- 验证：相关完整模块T1与三种子；Double新路肩节点短T0。原失败保留，已通过686项及本次前2项有据复用，整批/人工Gate开放。

## 结果

- H2路肩与phase3沿线/路线离地统计改读普通车辆完成步接触，显式四轮数量；原摆位、路肩高度/翻滚、路线速度/横偏/离地与恢复判据均保持。
- 首次完整3模块54项：53通过/交通1失败，147.79秒。误把专用TrafficVehicle当完整Vehicle导致空诊断；已恢复H3原生断言，单独该节点40.89秒通过，并完成三种子。H3最终无源码差异；原失败保留。
- Double路肩左右2项通过；原T2-after-h1的2通过/1首败也保留。普通T1命令`tools/validate.py T1 --tests tests/test_h2_map.py tests/test_h3_review.py tests/test_phase3_map.py --output logs/validation/VALIDATION-CONTACT-02-T1 --timeout 300`；补验同入口指定交通节点，目录后缀-supplement。证据[目录](../evidence/VALIDATION-CONTACT-02/)。
- 本包没有物理/控制变化。续跑清单740项显式复用、2776项实际执行，前后日志独立保存；人工/阶段Gate仍开放，仅本地提交。

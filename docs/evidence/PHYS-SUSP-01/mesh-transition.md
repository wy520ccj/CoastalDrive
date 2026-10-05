# 有限胎宽道路网格与支撑切换

2026-10-05，接续有限胎宽提交`ed374b3`。本增量完成施工线①的静态接触与四轮悬架功能；整体物理阶段继续。

## 实现与物理结果

- Box、Plane及道路实际三角面统一采用有限胎宽/胎肩/胎冠。道路生成时保存同一份三角面索引，跟随实际刚体变换及道路重定位；没有新增权威世界或关闭碰撞。
- 末姿态查询当前冻结Bullet世界的静态支持面，允许一个子步内跨道路物体。共同法向方程使用真实末接点和功共轭梯度；平行不同高度的路面不再误用同一平面化简式。近掠支撑要求实际正入射，删除实际圆柱路径的旧0.1截断；冻结球形台架接口保留。
- 用未注册查询盒筛选局部静态物体，Box/Plane/带道路数据的网格走解析几何，其他形状保留原生凸包查询。原生离散凸包只用于这些其他形状，不替代道路三角面。
- 三角面先检查有限平面，再求棱边接触；BVH按真实支持函数外廓扩展。边缘距离只在扫掠可能触及的原三角面范围内计算。SVD检查单纯形维数，平面法线直接给出最近投影，避免长边重心相消。NumPy进入运行依赖，venv的`pip check`通过。
- 起点几何保留双精度；给定末速度的本构力使用融合乘加，避免大止挡刚度放大舍入后的行程末位。接触块后刷新硬件反力并同步末速度。原实际法向1e-10N、几何1e-12Ns/Nms及能量3e-9J门槛保持；线性台架法向门槛从1e-8N收紧为1e-10N，转子内部迭代从1e-12收紧为1e-14。

四条固定侧撞，各30外拍的实际结果（不裁剪轮荷）：

| 工况 | 峰值轮荷N | 最大局部能量残差J | 末侧倾° |
|---|---:|---:|---:|
| game / Box | 15929.99 | 1.92e-13 | -2.42 |
| game / 分区Box | 24697.07 | 4.83e-13 | -5.01 |
| simulation / Box | 15887.71 | 1.78e-13 | -2.38 |
| simulation / 分区Box | 24724.58 | 4.55e-13 | -4.72 |

旧球体对应工况约35万N，见历史`rail.md`。本次完整120Hz Snapshot及碰撞冲量保存在`logs/physics/PHYS-CONTACT-03-rail/`；源码运行前后相同。数值说明此固定摆位的假抬升已消除，不是任意碰撞工况的峰值限制。

## 验证与命令

- 最终T1：`logs/validation/PHYS-CONTACT-03-final-T1-r1/`，431项全部通过（pytest96.53s），全Ruff及0/17/23各1200步启动通过（43.0/42.0/44.1s）。包含独立圆柱距离/滚动力臂、真实有限网格接缝/边缘、近掠、同高及4cm异高跨物体末接点、静载/防倾/生命周期、共同悬架/完整转子机械账与世界子步。
- 命令：`.venv/Scripts/python.exe tools/validate.py T1 --tests tests/test_triangle_support.py tests/test_cylinder_suspension.py tests/test_suspension_native.py tests/test_guardrail_suspension.py tests/test_curved_suspension.py tests/test_joint_suspension.py tests/test_suspension_coupling.py tests/test_vehicle_tires.py tests/test_physics_config_io.py tests/test_traction_lifecycle.py tests/test_tire_drivetrain.py tests/test_world_substeps.py --output logs/validation/PHYS-CONTACT-03-final-T1-r1`。
- 实际轨迹：`.venv/Scripts/python.exe tools/physics/guardrail_support_probe.py --steps 30 --output logs/physics/PHYS-CONTACT-03-rail`。
- 完整94车辆字段及源码哈希真实导出`reference-v26.json`；成绩game-controls-v23/reference-v26。导出命令`.venv/Scripts/python.exe tools/physics/export_reference.py --output docs/evidence/PHYS-SUSP-01/reference-v26.json`。
- 早期网格T1为211项通过，但后续改了世界切换与本构精度，因此最终相关431项重新验证。既有未受影响的几何/配置结果继续复用，未重跑整套T2/T3。

## 失败及未关闭项

`PHYS-CONTACT-03-transition-T1-r1`曾104通过/6失败：近掠独立期望未归一化原生轮轴，退化单纯形出现第五顶点，穿地摆位出现本构末位反力循环。短复现/修复日志`transition-T0-*`、`projection-T0-r1`、`constitutive-T0-r1..r6`保留；首轮命令含错误测试文件名，未执行测试也保留。最终431项包括这些复现及原数值门槛。

音频路径`PHYS-CONTACT-03-impact-T0-r1/r2`曾暴露网格距离失败；修复后`PHYS-CONTACT-03-clipped-T0-r1`为8通过/3旧音频断言失败。两条持续刮擦各完成840拍并满足实际连续压力门槛，但实际有声撞击0/2次，旧断言要求1；高速度墙撞的严重度/分层通过，旧尾部抑制断言失败。原生产音频、阈值及这些断言没有修改。该运行在最后本构收紧前开始，不当作最终音频通过结论。

T2机械阶段、T3、实际窗口性能及用户两模式驾驶未完成；已知音频断言待产品收口按实际接触事实处理。动态路面和完整簧下多体不在本期。下一功能块为②轮端滚阻、相对风速气动和参考车标定。

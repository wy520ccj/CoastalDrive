# PHYS-SUSP-01：SI硬件第一增量

当前第四增量见[细长Box真实交点](contact.md)；假表面已修，平台边缘的接触激活与整车能量仍待完善。

2026-10-05，第一增量基线c95b5f1，实现提交6be5f54。本页保存逐轮工程单位硬件接入时的证据；后续为[第二增量：法向共同求解](coupled.md)与[当前第三增量：势能一致反力](passive.md)，任务仍为in_progress。提交号以Git为准。

Vehicle直接把实际k、压缩c和伸张c除以真实刚体质量，交给既有Bullet射线轮。默认1200kg保持旧硬件；1800kg不再随质量把48kN/m弹簧自动变为72kN/m。力上限、行程、原生几何项和轮胎力通路保留。

## 本轮有效验证

以下命令均已结束、退出码0；不追加重复测试。

```powershell
.venv/Scripts/python.exe tools/validate.py T0 --tests tests/test_suspension_si.py tests/test_physics_config_io.py tests/test_traction_lifecycle.py::test_mode_abs_tcs_variants_get_distinct_score_keys --output docs/evidence/PHYS-SUSP-01/validation-T0-si-r1
.venv/Scripts/python.exe tools/physics/suspension_probe.py --output docs/evidence/PHYS-SUSP-01/si-mass-r1
.venv/Scripts/python.exe tools/physics/export_reference.py --output docs/evidence/PHYS-SUSP-01/reference-v15.json
.venv/Scripts/python.exe docs/evidence/PHYS-SUSP-01/off-compatibility.py
```

- T0：11项通过，pytest1.80s，全src/tests/tools Ruff通过。初次Ruff的未使用math导入已删除，保留失败事实。
- 质量对照：两模式×1200/1800kg×旧/SI，共8条240拍轨迹，1920原生120Hz拍；无运行中速度重设。参考车车身惯量随质量同比变化，游戏车由原生碰撞体质量决定惯量。298Python文件运行前后哈希一致；总执行约6.5s。
- 兼容性：关闭SI后，分别120拍加速/制动/倒车，与实际Git基线c95b5f1导出的源码在独立进程运行。全部CarState序列化字节一致，无删字段投影。报告文件沿用模板名`rwd-compatibility.json`，验证对象为完整旧单位悬架分支。
- 完整参考表：reference-v15，88车辆/8制动/10TCS/10稳定/9输入字段，两模式各真实240拍原生读回。

两模式质量结果相同；表中为末60拍平均压缩，仍含衰减瞬态。

|质量|硬件分支|末段压缩mm|理论静态压缩mm|末段总轮荷N|
|---|---|---:|---:|---:|
|1200kg|旧|61.3126|61.3125|11771.998|
|1200kg|SI|61.3126|61.3125|11771.998|
|1800kg|旧|61.2912|61.3125|17663.766|
|1800kg|SI|91.7476|91.9688|17667.178|

原生弹簧/阻尼独立公式最大残差0.00114155N，沿用既有SI预检0.01N门槛；末段压缩误差门槛0.001m、总轮荷1%mg。此为原生悬架公式诊断，未改变轮胎0.001N残差门槛。

## 第一增量时尚未完成（历史记录）

当前c是原生法向力对射线行程速率的系数，平路与轴向阻尼相等。斜接触下须按法线/悬架方向的虚功修正，近掠截断和力限须进入实际观测。左右防倾储能、共轭反力及轮胎实际轮荷尚未接入。下一步直接施工这些机制，随后完成自由振动/单侧起伏/离地再接触与两模式操稳短对照、一次功能T1。

本增量没有任务完成回执，也未运行T1/T2/T3、前台性能或人工驾驶。旧护栏音频失败保持；实车型来源/标定、估计器及完整研究协议继续单列。[硬件回执](hardware-receipt.json)记录本次源码和证据哈希。

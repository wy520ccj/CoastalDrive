# PHYS-SHARED-ROUNDING-01 数值修复证据

基线main/9eb7bf9，修复真实Double低速共同求根的舍入循环。物理方程/约束/默认硬件/辅助/120Hz/SDK保持；原精度/实时/人工与两项Double旧字节基线Gate仍开放，不称阶段通过，无推送。

- `checks/original`新实际低速回归在原生产模块失败，`fixed`最终生产模块通过；测试没有瞬移、强制速度或改变参数。
- `trace.log`是隔离原C只加末6轮输出，原第275次调用同样失败：转轴残差2/3ULP而门槛1ULP。`candidate.log`仅相邻试探越过275但624失败；`merit.log`全程改择步可行；`local.log`末期先收微小下降仍失败；`best.log`最终末期择最优候选完成三圈。失败日志/摘要保留，不把可行但未采用方案当正式修复。
- `diagnostic/*.patch`为相对`production-before.c`的候选派生差异；`diagnostic/*capture.json`保存原始摘要/运行库指纹。原型去世界pkl独立重放不等价，未采用为验收载荷，未归档；实际固定种子重现及新增真实回归才是依据。
- 最终只在原线搜索耗尽、最后6轮且残差到舍入量级时比较原Newton候选与相邻表示，按原容差归一平方残差择最优严格下降。`criteria-check.json`逐字核对原angular_tolerance、收敛/端口/分支可行性及30轮原循环保持；1e-10仅是探索触发条件，原停止门槛未变。
- 旧/新实际机械扩展均归档，SHA6ca08643…→c84bfb06…，构建脚本/日志及前后全部扩展SHA证明只重编机械核，严格/fp:strict。`compare_production.py`在相同ABI布局的真实同一输入上原/新调用，每SDK各940次完整输出pickle字节相同，0差异/异常；原结果仍负责测试后续推进。
- 普通完整六模块589项通过；Double同一组587过2失败。`checks/double-fixture-baseline`在未修复旧生产模块也出现同样2项失败，`double-final`保留最终完整输出；这些是旧Normal完整载荷字节参考在Double下不一致，未改夹具、未放宽字节要求、未声称Double全套通过。原/新对照日志的pytest_exit=1如实保留，与940对同输入一致分开计账。
- 最终普通合并T1 661项/三种子在[滨海目录](../COASTAL-MEDALS-01/checks/final-T1/summary.json)；两库最终真实三圈/重启/44005步规则复核也在那里。`normal-record-comparison.json`及滨海共享记录索引证明普通3圈22011拍已记录JSON字段与改前完全一致，不称完整内部状态等价。性能/尾延迟未单独验收，T2/T3未跑。

`archive-manifest.json`记录37份730610字节原样输出/旧C/两份实际扩展，另有4份派生候选patch；3项最终源码归一LF指纹见`source-manifest.json`。完整背景与下一步见[任务包](../../tasks/PHYS-SHARED-ROUNDING-01.md)。旧/新扩展仅供可信本地诊断，Python3.14/本机SDK环境；不用于用户文件导入。

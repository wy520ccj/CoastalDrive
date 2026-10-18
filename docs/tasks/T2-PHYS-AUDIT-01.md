# T2-PHYS-AUDIT-01 落地制动细化失败归档

- 状态：done（只读审计完成，精度Gate失败保留）；基线main/92297e5，开始前干净。
- 触发：T2-after-font在117通过后首败test_vehicle_collision的对称落地制动子步细化；对称/不误触ESC/停车先验均通过，路径差不单调。
- 范围：只读复算普通/Double的2/4/8/16子步摘要、输入/源码基线一致性和阶段失败归档；禁止放宽阈值、改物理、隐藏失败或宣称T2通过。
- 目的：把真实精度Gate与已修复的旧测试入口分账。完整物理/实时Gate原本开放；该问题保留给专门的精度任务，不用改玩家认可参数给本批功能背书。
- 验收：实际四组摘要/停止时间/距离差、当前运行库指纹、src仅来源说明显示变化/test与探针未变的Git证据，原T2失败/not_run原样保存。
- 后续：本批T2明确failed，人工Gate pending；持续目标转入DRIVING-STOP-01可玩短课题，相关短T0/T1正常执行，不称整个阶段已通过。

## 审计结果

- 普通路径差0.16730499 / 0.25041580 / 0.29999161m；Double0.16675769 / 0.24997542 / 0.30305680m，均不满足严格逐级缩小。不是单精度独有现象，也不能仅凭两库一致称物理精确。完整4组summary/runtime见[证据](../evidence/T2-PHYS-AUDIT-01/)。
- 对照功能提交250be45，src只改ui/parameter_help来源文字；碰撞测试、esc_probe与全部物理源码未变。当前既有精度失败，不归咎于新增幽灵/分段，也不豁免阶段Gate。
- 原3516项中3356项按明示复用/实际执行覆盖，1项失败，159项未执行；所有后续11条T2道路/交通检查not_run。Ruff/三种子/handling已有各自证据，不能抵销未跑范围。coverage.json逐节点存账，不称整批通过。
- 复算命令`.venv/Scripts/python.exe logs/t2_physics_audit.py logs/T2-PHYS-AUDIT-01/normal.json`，Double前置run_sim_double；探针另存audit.py并按归档位置解析项目根，可直接从docs/evidence目录复算。没有改生产文件/参数，没有重启已终止T2。
- 下一步DRIVING-STOP-01独立任务；新增玩法按自身T0/T1/真实渲染/物理流程验证，原物理收敛Gate留待后续专门处理。阶段失败/人工待确认继续保留。

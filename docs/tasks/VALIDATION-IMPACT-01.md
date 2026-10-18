# VALIDATION-IMPACT-01 挑战真实碰撞的终帧交付

- 状态：done（实际碰撞时序与终帧交付验证通过）；基线main/f4e16cf，开始前干净。
- 触发：整批T2-after-routes在56通过后首败impact_delivery真实护栏测试，预设首拍结束但仍在DRIVING。
- 目标：确认真实接触/冲量/碰撞事件/结束帧的时序，保留固定seed11与无穿透摆位；准确验证挑战碰撞终帧仅交付一次。
- 范围：该碰撞交付测试和必要证据，若确有交付bug再改session实现；不改物理、碰撞阈值、固定步、原有调校。
- 验证：先记录首若干真实步的流形/冲量与阶段；再选最小修复，impact_delivery完整模块T1与Double真实节点。T2原失败保留，不把首拍未碰撞直接判成事件丢失。

## 结果

- seed11原姿态/速度实测：首拍闭合间隙但未解算碰撞冲量；第2拍11135.27Ns真实冲量、1次碰撞、RESULTS与唯一金属护栏事件；后续请求不推进物理、不重复事件，完整8请求证据before.json。
- 仅修测试等待真实终帧（至多4拍，约33ms），检查前帧零碰撞/零事件、事件累计恰等于终帧唯一事件、事件tick等于实际完成tick；原无穿透摆位、seed、速度、碰撞次数/材质/不重复约束保持。生产源码未改。
- 普通完整impact_delivery T1 4项/三种子、Double真实碰撞节点1项通过，日志与原56通过/1失败在[证据](../evidence/VALIDATION-IMPACT-01/)。
- 续跑`docs/evidence/GAME-GHOST-01/t2_continue_after_routes.py --after-impact`，显式复用797项、余2719项/未跑交通道路检查实际执行。原失败与人工Gate保留，仅本地提交。

# 6B-04 分层播放、擦碰与生命周期

- 状态：done（实现/自动部分）；音频专项 T0/T1 与全量 T2 通过，实际驾驶试听归 6B-05。设计基线 `34cec49231391c769ef38db1ee2e22363863c20b`。
- 实施：Astra；`src/impact_audio.py` 与 `src/soundscape.py` 已接入 6B-02 Snapshot 事件。

## 目标与范围

将新物理事件接入分层系统，删除旧速度差分类与 700 ms 全局冷却，保持主音量×效果音量和暂停/菜单/结果静音语义。

- 允许：`src/impact_audio.py`（新增）、`src/soundscape.py`、`src/application.py` 仅音频 dt/可选诊断传递；`tests/test_soundscape.py`、`tests/test_impact_audio.py`（新增）；`tools/impact_audio_check.py` 添加 --drive/--audition 与决策记录；`tools/validate.py` 音频映射；impact-bank.json 的音频参数；切换后清理旧四个 WAV 及对应准备脚本/素材登记状态；本包和进度。
- 只读：Simulation/Session 已交接口、Vehicle/CAR.mass、交通/道路/比赛、settings.py/音量 UI；已完成两级音量语义不变。
- 不得通过改动物理门槛掩盖播放错误；若 6B-02 合同存在实际缺陷，给最小复现交接口修复，不在声音层反推速度。

## 施工合同与验收

按设计实现连续 severity（q 使用只读 CAR.mass 归一化）、100 ms 同源窗、强击升级、同帧升级合并、采样洗牌、最多 11 碰撞 voice、一个 scrape、约 3 dB 短 duck。配方参数均初始可调，不表示用户已接受。

- [ ] 每个获准 impact 同次 update 起 transient/body；中重层连续加入，重撞不靠单 WAV。
- [ ] 80–150 ms 小脉冲抑制、明显更强立即升级、200–500 ms 真第二击可响；不同 NPC 身份不互相抑制。
- [ ] 多层独立 AudioSound，预加载池；停止/抢占/预约 debris 有界，复杂事故最多 14 个总活动声音（含现有3循环），无持续累积。
- [ ] 多 variant 不连续重复；独立 RNG、不影响交通；pitch/volume 变化有硬限。
- [ ] scrape 只在进入时 play 一次，速度/载荷调制平滑，退出 fade，跨接缝不重新打一串 impact；单主源切换无抖动。
- [ ] 重撞 duck 不累乘、最后一击后及时恢复，零音量立即停，包括所有已响/待响尾音；暂停/菜单/结果/reset/close 清理。
- [ ] application 使用真实帧 dt 推进包络；Event ID 去重包含 epoch；静音事件消费不补播；倒计时只维持既有引擎行为，不消费旧事故。
- [ ] 真 OpenAL 验证多个实例并发、左右声像、loop 连续性。不得只 mock setBalance；该后端方法未实现。
- [ ] 旧分类与旧冷却单测用新合同测试替换，音量和生命周期测试保持/加强；未变的发动机/路噪行为仍通过。
- [ ] JSONL 能连接物理 event_id 与实际 layer/variant/抑制原因、scrape/voice/duck；默认不开日志。

## 验证

T0：`tools/validate.py T0 --area audio`；T1：`tools/validate.py T1 --area audio --area core --area gameplay`，均用项目解释器。声音专项用真实 OpenAL，不使用 application.smoke 的禁音结果替代。

6B-02–04 集成完后小阶段收口执行一次 `tools/validate.py T2`，之前先 dry-run 检查范围；不自动跑 T3/长时可见 Gate。专项真实声音和用户试听分别记录，自动通过后 6B 仍待 6B-05。

## 交接

- 实现：每个事件按连续 severity 触发瞬态/车身并渐进加入结构变形与碎片；约 100 ms 同源聚类、强击升级、独立擦碰、短时 duck，撞击最多 10 声加单一 scrape 和 3 条驾驶循环。诊断 JSONL 包含真实物理事件 ID、原始冲量、速度分量、区域、severity、层/variant、抑制原因和 scrape 状态。
- 最后专项检查发现高强度墙撞后仍会播放约 18 N·s 的微小求解尾脉冲，而实际低速连续擦栏首击约 338 N·s。音频配置新增 provisional `audible_floor=0.04`：前者静音且记诊断，后者仍播放；不改变物理事件和玩法事故计数。
- 2026-09-23 音频 T0、音频+核心+玩法 T1 通过；全量 T2 通过 Ruff、243 项 pytest、3 种子 headless、handling/surface/traffic 及直路/弯坡长程检查，摘要 `logs/validation/20260923-094112-766203Z-T2/summary.json`。真实 Panda3D/OpenAL 已加载 52/52 独立句柄并验证多层并发、擦碰循环与关闭释放。`tests/test_impact_integration.py` 用实际 Bullet 墙、NPC 与护栏接触跑穿播放器决策；赛道玩法碰撞仍为一次事故计数。T2 首轮旧护栏测试失败，用修改前 HEAD 的 Simulation 原样复现相同失败；旧测试把真实护栏事故错误预期为无碰撞事件，现改为断言连续接触恰好计一次，并重跑通过。
- OpenAL 复核记录 `logs/impact-openal-check-20260923.json`：52/52 READY，瞬态/车身/crunch 三层同时播放、单一 scrape loop 运行、关闭后声音归零。实际扬声器延迟、左右声像强度与汽车音色仍需用户在正常音频设备驾驶确认。
- 6B-02–04 与 6B-05 校准入口已本地提交，未推送；正常听感仍以 6B-05 用户实驾结论为准。
- 实际声卡延迟与游戏音色：待人工，不能由 play 调用时刻推断。
- 下一步 6B-05；不逐票要求 Astra 重做设计。两轮实质修复仍失败带最短重放日志和参数差异升级。

# 完整快照原生传输与去重 r1

2026-10-11，主目录main，基线 `a84a9b1`。本功能块已接入实际可见会话，独立r5包可试玩；**困难实时120Hz和总体流畅/人工Gate仍未通过**。仅本地保存，不推送，不替换公开0.8.3/根试玩入口。

## 改造与边界

独立物理进程仍持有原Session、唯一Bullet世界及规则。完成步Snapshot、所有CarState及轮端/悬架/传动/电子控制、碰撞事件/接触，通过现有严格浮点原生数值包编码；固定类型及字段布局由实际dataclass定义生成并有签名。规则、枚举和异常保留原类型，小头用pickle，完整数值状态用native codec；没有缩减遥测、精度或IPC错误回传。

每个快照对象只在窗口未收到时编码，帧头用该进程对象身份引用。发送端强引用/接收端完成步表各最多16项，与12拍历史分工明确；两端按同一顺序淘汰。同拍不同对象仍独立发送，重开/换epoch也不合并。重复领取已完成物理拍时只传状态头与新事件；完整车型快照不再每帧重复解码。清空/关闭回收引用；无预测/第二积分器，不改原4拍显示缓冲、相机常数或输入策略。

## 实际验证

- 最终相关T1 **27项、全Ruff、0/17/23各1200拍启动**通过，含实际双模式远程/本地完成拍相同、暂停/重开/输入/原异常/相机查询以及事件送达。首轮非跨帧缓存26项通过，跨帧缓存接入后重新验证受影响范围；没有重复物理核心T2/T3。
- Codec逐记录重编码保持完整字段及原float位型，覆盖符号零、NaN、epoch、真实双模式坡道快照、规则/碰撞/接触、同包重复引用、同拍不同快照、40拍缓存淘汰及重开。原生编码不保持无关嵌套对象的别名关系，因此不把pickle载荷SHA当数值等价证明；完整快照类型/值、float位型及真实物理结果有对应检查。
- 冻结两拍、13车完整会话装配/解码：正常pickle约.491ms→native首次.236ms；困难约2.178ms→1.129ms。困难帧载荷160041→139199字节；重复相同完成拍载荷600字节、约.015ms。此为无IPC固定输入测量，不等于120Hz通过。
- **有效困难前台30秒短对照**，1080p/GR86/无限坡道/12完整NPC/seed23/9数值进程：旧65.5994Hz物理、66.3499绘制FPS、丢时12.2167秒；新66.7048Hz、71.4519FPS、丢时11.9667秒，两次窗口/工作进程来源有效、碰撞0。只有一对短样本，记录实际变化，不认定稳定整体收益；两者都未达到120Hz/性能Gate。
- 第一轮旧窗口与本轮pytest重叠，已明确排除，原报告保留；后续比较与最终正常测量没有同时跑其他测试/构建。未关闭用户应用、调整优先级或亲和性。
- **最终有效正常前台60秒**，相同1080p坡道/GR86/12NPC/seed23：物理119.9928Hz，绘制82.5977FPS，P95 16.9328ms，丢时0、碰撞0；两次>50ms绘制长帧、最大124.4405ms，short_performance_passed=false。正常物理实时通过仍不能升级为总体流畅；困难慢动作仍在。
- r5包四原生模块SHA与当前src构建一致，仓库外双模式可见启动（实际会话子进程）/8车120拍headless/离屏与各20重开通过，困难实际截图已检查。包入口已更新；启动与离屏不代替手感/性能验收。

## 复现

```powershell
.venv/Scripts/python.exe tools/validate.py T1 --tests tests/test_snapshot_wire.py tests/test_session_process.py tests/test_session_clock.py tests/test_keyboard_steering.py tests/test_impact_delivery.py tests/test_driving_mode_ui.py --output <新目录>
.venv/Scripts/python.exe tools/performance/benchmark_runtime.py --output <新目录> --seconds 60 --track endless --shape hills --vehicle-design gr86-2022-premium-6mt --driving-mode game --traffic-count 12 --independent-clock
.venv/Scripts/python.exe setup.py build_apps --build-base <新目录>
```

完整原始报告位于 `logs/performance/snapshot-wire-r1/`；归档JSON只省略逐帧GC数组，保留原路径/SHA和实际源码来源。固定输入测量脚本与正式回归、短窗口、包收据均在本目录。未改物理核心，复用上一版有效完整物理数值结果；T2/T3、长时间/声音/人工待办。下一继续完整车辆读取/准备/观测装配的连续数值边界，同时定位正常两次长帧；不通过降低困难NPC精度、关闭碰撞或时间倍率掩盖欠账。

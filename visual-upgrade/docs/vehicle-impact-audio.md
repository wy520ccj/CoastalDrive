# Vehicle Impact Audio System v1

状态：物理事件、素材池、分层播放和诊断已在 0.8.3 实现；severity 曲线与音色仍待实驾校准。2026-09-23；设计核验基线 `34cec49231391c769ef38db1ee2e22363863c20b`。本文替代 6B-01 的碰撞分型方案，不修改其音量设置语义。接口核验记录见 [实测依据](vehicle-impact-audio-evidence.md)。

## 1. 问题与决定

现有声音用玩法 `collisions` 增量触发，以两个渲染快照的玩家速度差猜类型，再施加 700 ms 全局冷却。玩法计数本来就将持续接触合并为事故；渲染速度差混入加速、制动、转弯，丢失碰撞前的接近速度和 NPC 运动；同一事故的真实二次撞击因此可能完全没有声音。`scrape` 目前是一次性 WAV，不是持续状态。每类只有一个采样，重撞也只有一个整段录音。

本地 Panda3D 1.10.16 的求解后 manifold 提供真实冲量、接触位置、法线和寿命。护栏探针中求解冲量合计 8091.012 N·s，同帧 `contactTest()` 查询的冲量全为零，后者不能作为音频强度来源。当前侧撞/重撞 WAV 的显著起音代理指标分别为 141/170 ms，素材本身也需处理。

决定：物理事实 → 不丢失的帧事件批次 → 感知强度与小型分层混音。保持 120 Hz、Vehicle、驾驶参数、交通 AI、道路和比赛判断不变；保留 `_count_player_collisions()` 与 `collision_count` 的现有逻辑。声音不能读取 `collisions` 来触发。

## 2. 数据流与模块

```text
Simulation.step
  apply_control 后、doPhysics 前：复制活动刚体 v / ω / 刚体原点
  原样 doPhysics(1/120, 4, 1/120)
  紧接求解后：只读 getManifolds → 复制接触值 → 聚合/提取物理脉冲
  原有 after_step、玩法计数、tick、rebase/recovery 继续原样运行
       ↓
Snapshot：本 tick impacts + 当前 contacts（不可变值，无音频资源）
       ↓
Session.frame：汇集实际推进的所有 tick 的 impacts，contacts 取最终状态
       ↓
Soundscape.update：去重/强度/短时聚类 → transient + body + crunch + debris
                                      → 独立 scrape 循环与短时 duck
```

新增两个小模块足够：`src/impact_events.py` 保存不可变数据类和接触聚合/脉冲跟踪；`src/impact_audio.py` 保存曲线、配方、采样池和有界声音槽。Simulation 持有物理跟踪器；Soundscape 持有音频播放器，继续管理已有发动机/路噪/主效果音量。新增 `assets/game/audio/impact-bank.json` 只保存音频配方、校准参数和 variant 元数据；不用事件总线、线程或音频中间件。

## 3. 只读接口

`Snapshot` 在现有字段后追加默认值：`contact_epoch=0`、`impacts=()`、`contacts=()`，保护现有构造调用。所有坐标/向量均为浮点 tuple，不把 Bullet 对象、可变 Vec3 或音频名字带入快照。

`ImpactEvent(frozen=True)` 表示已观测到的离散接触脉冲，字段合同：

| 字段 | 含义 |
|---|---|
| `epoch, tick, index` | 事件标识；tick 是刚完成的物理步，与 Snapshot.tick 一致 |
| `sources: tuple[int, ...]` | 参与此局部接触簇的刚体身份；不是节点名称 |
| `material: str` | `vehicle / metal_barrier / hard_solid` |
| `raw_impulse: float` | 该 tick 簇内有效法向求解冲量之和，N·s |
| `excess_impulse: float` | raw 减去此前持续接触的缓慢载荷基线，下限 0，N·s |
| `normal_speed: float` | 碰撞前接触点的相对接近速度，m/s，下限 0 |
| `tangential_speed: float` | 碰撞前相对切向速度，m/s |
| `local_position, local_normal` | 当时玩家车体坐标系中的接触中心/向车体的单位法线 |
| `zone: str` | front / rear / left / right / roof / underbody |
| `contact_age_ticks: int` | 自建接触跟踪年龄，用于诊断，非 Bullet 单点寿命 |

`ContactState(frozen=True)` 保存持续接触事实：`sources, material, tick, raw_impulse, normal_speed, tangential_speed, local_position, local_normal, zone, contact_age_ticks`。其中两项速度取求解后值，供擦碰连续调制；`normal_speed` 仍为接近分量。无接触时 `contacts=()`。无“是否播放擦碰”或感知 severity 字段。

severity 是声音解释，不是物理量，只在音频决策与诊断记录里出现。法向冲量与法向速度分别命名并标明单位，不能将 friction impulse 当切向速度。原始单点 `lifeTime`、最大单点冲量和点数只进入开发日志，不膨胀公开接口。

`contact_epoch` 用模块内递增整数分配器分配进程内唯一值；新世界、完整 reset、成功的 player reset 都换值，清空接触历史与事件；失败 reset 不换值。它不参与物理随机数。事件 ID 在不同 Simulation 实例也不会撞号，不需要 UUID 或墙钟。rebase 不换 epoch，因为局部接触值对平移不变。

## 4. 物理采集与聚合

1. 在固定步开始时复制玩家与活动 NPC 的线速度、角速度、刚体原点；静态对象速度为零。在 `doPhysics` 后、rebase/recycle/recovery 之前读取 persistent manifolds，只取包含玩家底盘的 pair，并将数值立即复制出来。绝不持有 manifold wrapper 跨步使用，不改 contact 属性，不使用 contact-added 回调中的未求解冲量。
2. 有效点为 `distance <= 0`，或距离略正但本步 `appliedImpulse > 0` 的求解接触；记录距离以观察 margin/CCD 情形，不能用随意放大的距离阈值制造接触。零冲量的真实贴合可进入 contacts，但不自动形成 Impact。
3. 令 n 始终指向玩家：玩家是 node0 时用 `normalWorldOnB`，是 node1 时取反。分别在 A/B 实际接触点计算 `v_contact = v_linear + ω × (point - body_origin)`，`v_rel = v_player - v_other`；`vn = max(0, -dot(v_rel,n))`，`vt = length(v_rel - dot(v_rel,n)*n)`。Impact 用步前刚体状态，ContactState 用步后状态。步前状态配本步接触点是一个固定步内的近似；不用声称获得了精确求解器内部 TOI 速度。它包括旋转与 NPC 运动，不是相邻快照速度差。
4. 先按真实刚体 pair 聚合所有 manifold 的点，再按法线方向分局部接触簇（初始夹角 45°）。同一面四点是一个簇，不按 front/side 角点重复分声；完全相反的面不合并。正常冲量各求解点求和，禁止把跨 tick 累积载荷当作撞击能量。位置/法线/速度按正冲量加权；总冲量为零时均匀加权。用稳定顺序处理，顺序变化不改变结果。
5. 相邻护栏分块可跨 body 合并：同一护栏逻辑侧、相近法线、接触中心距离不超过一个车身长度，且同 tick。保留所有 `sources`。不同车辆/不同材质不合并。后续短时跟踪允许同一护栏侧的相邻分块接替，避免接缝被当成新事故。节点名只识别类别/护栏侧；身份来自 Simulation 内单调编号登记，NPC 加 generation，卸载/退休对象清理登记，不能使用 Python wrapper 的 `id()`。
6. 跟踪每个局部簇的接触年龄、上一载荷基线、脉冲峰值与是否已重新就绪。Bullet 的单点 lifetime 仅辅助诊断：点会被替换，实测滑动时多次为 1，不能用 `lifeTime==1` 直接播声音。
7. 离散脉冲需有真实求解冲量和法向接近：新接触，或持续接触中再次出现明显的动态冲量上升。持续载荷基线使用约 80 ms EWMA，先计算 excess 再更新基线；法向运动/动态载荷落回退出区连续 2 tick，或接触消失 2 tick，才重新就绪。已触发的脉冲中若冲量显著升级，仍输出新的上升事件供音频升级判断。面方向改变不单独触发，必须同时出现新的法向冲击证据。

`J_noise / v_enter / v_exit / excess_enter / excess_exit` 等物理检测参数集中在跟踪器配置中，通过开发记录的静止接触、持续擦碰、低速真实轻碰分布确定。6B-02 先交记录与短物理夹具，再冻结初始参数；不把本文探针的单次 J 值当通用阈值。音频 JSON 只存感知曲线和音频聚类参数，不让物理模块读取 WAV 清单。支持力可能有明显 J（1200 kg 静置探针约 98.1 N·s/tick），因此绝不能“J>0 就播放”。

位置由接触中心经完整逆刚体变换获得；玩家碰撞盒的中心偏移为 `(0,0,0.42)`，半尺寸 `(0.78,2.05,0.42)`。比较归一化局部位置判面，角点以局部法线主轴解平局，并对持续接触的 zone 使用滞回。完整姿态也适用于侧翻；roof/underbody 成本很小，v1 保留。

## 5. 材质规则

只用一张有序规则表，未知实体回退 `hard_solid` 并在开发模式记录名称。

| 实际对象命名 | 类别 / 特殊处理 |
|---|---|
| `traffic-*` | vehicle；同名 NPC 回收代数必须区分 |
| `inner-rail / outer-rail / highway-rail--1 / highway-rail-1 / segment-<整数>-rail-left/right` | metal_barrier；规范化护栏侧以跨分块跟踪；segment 可能为负数 |
| `tree-* / rock-* / segment-<整数>-tree-* / end-wall / slalom-*` | hard_solid；树作为硬障碍，首版不虚构木材损伤 |
| `checkpoint-* / checkpoint-beam-*` | hard_solid；目前几何/素材无可靠材质细分，选保守结构配方；自由驾驶关闭碰撞时自然无事件 |
| road、shoulder、ground、test-ground、island、cliff、ramp 及其 highway/segment 形式 | hard_solid；只认底盘实体接触，不把轮胎射线/正常悬架落地当底盘撞击 |

不添加不存在的 soft 物体。由此 v1 支持真实底盘/车顶落地、翻滚撞地；四轮悬架吸收的普通落地没有 manifold，属于未来悬架声音，不在此轮伪造重撞。

## 6. Session 传递与生命周期

Simulation.snapshot 每次读取返回相同的该 tick 事实，绝不在 snapshot() 中 drain。Session.frame 在局部列表收集本帧实际推进的每个 tick 的 impacts（现有 FixedStepper 最多 8 步）；只有物理步编号实际增加时才收集，倒计时的 Session.tick 不算物理步。返回插值 Snapshot 时用该列表替换 impacts，contacts 保留最新一步。物理事件不插值。零物理步的下一帧 impacts 为空，不能重播；直接调用 Simulation.step/Session.tick 的测试仍能读取本 tick Snapshot。实现收集器只在 frame 期间存活，不让 headless 直接 tick 造成无界队列。

frame 内若发生 reset/epoch 改变，丢弃旧 epoch 待播事件，避免复位后响上一地点事故。若进入 RESULTS/MENU/PAUSED，同帧待播事件消费并丢弃，所有驾驶声音停止；包含导致结果页的末次撞击，v1 优先保持结果页静音语义。正常驾驶中的事件在同一 application update、绘图之前提交给音频，不等插值追上或聚类窗结束。

Soundscape 记录 `(epoch,tick,index)` 消费水位；重复 update、暂停快照或车库路径不重放。换 epoch 清除声音尾音、去重、scrape、duck 和随机池状态。暂停/菜单/结果/关闭即停全部单次声及循环，清空待发尾音；恢复只从当前有效接触重建 scrape，不补播 Impact。静音仍消费事件与推进水位，解除静音只恢复当前循环。两级音量仍相乘，任何一级为零立即停止所有音频；close 幂等。

音频包络用 application 的真实帧 dt（显式新增可选 `audio_dt` 参数），不借 Snapshot.time 是否增长来判断 reset。这样零物理步帧仍能完成 fade，暂停直接停止，无需复杂调度器。事件重触发间隔用物理 tick，音频尾音/包络用音频时钟。

## 7. severity 与短时重复触发

物理 J 经玩家质量归一化得到 `q = excess_impulse / mass`（m/s 的冲量等效量，不宣称真实车速损失）。用 `x=log1p(q)`，通过采集到的轻/中/重代表区间建立单调分段曲线，输出连续 `severity ∈ [0,1]`。曲线节点是数据，不是 light/side/heavy 枚举；禁止线性把 J 直接当音量。动态峰值的 raw/excess 两值都保留以检查载荷扣除是否误削第二次重撞。

用同一曲线跨材质/方向表达重量；法向速度参与真实性门槛，切向速度主要驱动 scrape，防止高速贴擦被误判为重撞。第一批代表点来自实际物理夹具，最终参数来自八项人工驾驶数据；没有证据的配置必须标为 provisional，不声称已校准。

音频按物理 tick 顺序处理事件，首事件立即播放：

- 同 tick、同源同面的 contact 已在 Simulation 聚合。不同物体的独立撞击保留，由声音预算处理，不将整 tick 一刀切成一声。
- 同源局部簇使用初始 12 tick（100 ms）的 retrigger 窗，调节范围 10–18 tick。它是首响后的抑制窗，不是等待窗口。区间内小幅脉冲只记日志；若新事件 `severity >= 上次+0.15` 且 `excess >= 上次×1.6`，立即升级，替换较弱尾音。两项均属可调音频参数。
- 过窗也必须有新的物理脉冲；不能让持续摩擦每 100 ms 打一次。接触中心/方向改变后 200–500 ms 的真实二次重撞可再次播放。翻滚触地依赖每次分离/接近产生的脉冲，不受一次事故计数限制。
- 同一渲染帧内因赶帧同时送达、且已被判为同一局部事故升级的事件，预先选最强一次配方，避免同一次 update 连续起音；不同来源事件保留。长帧造成的真实时间丢弃沿用 FixedStepper，不补造事件或排队播放过时事故。

正常 60 FPS 下目标为“求解后本帧提交 + 无等待 + transient 起音 ≤5 ms”；实际声卡/OS 输出延迟另测，不能以 Python `play()` 调用时间宣称端到端零延迟。

## 8. Layer、variant 和混音预算

| 层 | 初始配方 | 同时活动上限 |
|---|---|---:|
| transient | 每个获准 Impact 必有，5 ms 内起音，约 40–120 ms；材质影响干脆/金属质感 | 3 |
| body | 每次都有但轻碰权重低，约 150–650 ms；共享车身共振池，front/rear 稍加低频重量 | 3 |
| crunch | severity 约 0.4 后连续淡入，0.2–0.6 s；表达变形，不能替代 body | 2 |
| debris | 约 0.7 以上才有，概率随强度升至约 0.6，低音量；允许 20–60 ms 尾部起音 | 2 |
| scrape | 独立、无首撞的无缝循环；同时只保留一个主接触源 | 1 |

上限是 11 个碰撞声，含现有 3 个发动机/路噪循环合计最多 14。debris 延后只用短小 pending 列表，预约时占预算，最多 2 个，并在静音/暂停/reset 清空。先保证新重撞的 transient/body；预算满时淘汰最弱、最老尾音，crunch/debris 优先降配。保护刚开始约 30 ms 的关键瞬态，但更强撞击可抢占最弱槽，不能为保护旧尾音延迟重撞。空闲时可短 fade 抢占；硬上限时直接停最弱尾音并记录，不临时超预算。

每个槽是独立 AudioSound 实例，启动前预加载资源；不能对同一个正在播放的 AudioSound 反复 play（它会从头重启）。variant 以各池洗牌袋选择，跨袋边界也不能连续相同，且用音频独立 seeded RNG，不能消耗 traffic/simulation RNG。pitch 初始 0.97–1.03，音量 ±0.5 dB；各 variant 先离线匹配感知响度。强弱体现在总体包络、层数、采样范围和低频结构，不通过巨大随机增益或所有素材归一化到满幅实现。

音频素材与配方保留混音余量。按样本测得峰值×当前层增益预算，碰撞层总预计峰值不超过约 0.60，给已有循环留余量；超预算先削旧弱尾音和细节，不把首瞬态全部压平。这是简单增益分配，不是 DSP 压缩器。合成压力样本再检峰值，实际听感检查无噪声墙/泵动。

重撞（初始 severity≥0.7）发动机/路噪最多降低约 3 dB，5–10 ms 进入、约 60 ms 保持、约 180 ms 恢复。重触发只延长/取最大 duck，不累计相乘；控制连续事故中的最大保持时间，最后一击后 300 ms 内回到正常增益。用户的 master/effects 乘积在最后应用，不改存储含义。

左右声像限于轻度偏移。**1.10.16 OpenAL 的 setBalance 未实现**，不能依靠该函数。单声道用非 positional 的听者相对 source，调用 `set3dAttributes(小幅左右偏移, 1, 0, 0, 0, 0)`，参考距离包住此近场范围，零速度不引入多普勒。front/rear 近中置；音色配方仅作小幅权重变化。必须在真实 OpenAL 上以左右录音/试听验证，不以 fake sound 接到参数算完成。不复制四套位置素材，不引入全场 3D 声学系统。

## 9. Scrape 生命周期

`OFF → ATTACK → SUSTAIN → RELEASE → OFF`。当前 ContactState 中切向速度与平滑接触载荷超过各自进入门槛，持续 2 tick 即成立，约 25 ms 淡入；用较低退出门槛防抖。正常结束约 70 ms 淡出，接触短失联最多容忍 3 tick。允许 impact 与 scrape 同帧开始并自然衔接，scrape 不借 impact 次数启动。

音量由切向速度的饱和曲线×接触载荷的平滑权重决定；pitch 随速度小范围变化（如 0.9–1.1），不追逐每步冲量噪声。只有一个主 scrape：选最高摩擦驱动力代理 `平滑 J × vt`，原主源有约 20% 滞回优势；材质换源先短淡出再换素材淡入，不为交叉淡化增加第二个长期循环。恢复到同源可接回 fade，不能每帧 stop/play。

接触已结束的最终 Snapshot 必须推动 RELEASE，即使同帧更早还有接触。静音/暂停/菜单/reset 不做尾部淡出，立即停止并清状态；重新驾驶时只根据新的有效接触淡入。

## 10. 素材计划

当前 engine/idle/road 保持。四个旧 impact 都按仓库登记为 Pól 的 CC0 录音；登记不是本轮重新审查线上许可。候选用途：light 最多作轻塑料细节；side 可试切短金属 transient；heavy 可评估硬表面短瞬态，**不再单独承担重撞**；scrape 只能回到原始录音重剪稳定段，目前长 fade 尾端不适合直接循环。候选均需实际试听，用户已拒绝当前整段使用方式。

最小素材池：transient 两个池（硬质/金属）各 3；车身 body 轻/重两个范围各 3；crunch 3；debris 3；scrape 金属/粗糙硬面各 2，共约 22 个短文件，可由许可合适的长录音拆出，但相邻几毫秒不能伪装成多个 variant。vehicle 使用硬质 transient + 车身 body/crunch，metal_barrier 选金属 transient + 金属 scrape，hard_solid 选硬质 transient + 粗糙 scrape；不用材质两两组合矩阵。

必须补充真正有低频质量感的车体共振、钣金屈曲、独立小塑料/灯罩碎片、无撞击头的稳定擦碰循环；不足时替换，不能靠大幅降 pitch 或增大音量把箱子声包装成汽车。transient 起音目标 ≤5 ms，去掉录音静音/刹车前奏；body/crunch 快速进入但不抢瞬态，debris 可以自然稍晚。环缝需重剪/交叉淡化后检查，无周期性起伏或嵌入式重复撞击。

采购/搜集交付要求：优先可随公开仓库与游戏分发的 CC0；CC BY 可用但保留作者、来源页、许可版本、修改说明和署名。拒绝无明确许可、不能分发素材、NC/ND 或仅“试听预览可播放”而无资源使用依据的文件。每项保存来源 URL、许可证据、原文件 SHA-256、截取/处理参数、派生输出 hash，更新登记与 License；付费素材只有确认允许当前公开分发方式才用。音色、分层与许可必须分别验收。

## 11. 诊断、校准与验收

开发入口建议 `tools/impact_audio_check.py`：默认无声物理探针；`--drive` 才启动正常设备人工驾驶；`--audition` 单独试听配方。不需要改生产 main 参数，工具通过可选诊断 sink 接入 Simulation/Soundscape，默认关闭。

JSONL 行类型固定为 header/contact/pulse/decision/scrape/summary：带 HEAD、dirty、Panda 版本、种子、场景、配置/素材 hash；关键字段至少有 epoch/tick/event_id、material/sources、raw/excess impulse、vn/vt（标明 pre/post）、zone、point_count/lifetime、severity、实际获准 layers/variant、各层 gain/pitch、抑制/抢占原因、voice_count、scrape 状态、duck。记录 physics 采集和 play 提交的单调时钟，以测应用内部延迟。contact 连续数据默认 20 Hz，所有脉冲/状态变化全记；原始 120 Hz 模式只限短诊断。缓冲分批写入，不在每个 contact 上 flush，退出写 summary，限定时长/行数，不能无界占内存。

校准顺序：静置/常规行驶负样本 → 物理碰撞样本 → 冻结脉冲检测门槛 → J/m 非线性曲线 → 分层响度/预算 → 用户正常设备驾驶。保留 raw 数据重放音频决策，可在不重跑物理的情况下对比曲线。独立音频 RNG 种子相同应重现 variant/layer 选择。

| 自动验证 | 核心判据 |
|---|---|
| 真 Bullet 护栏、墙、运动 NPC、旋转箱/底盘落地 | 求解 J 非零、n 正负一致、相对速度包含 ω 与 NPC；静置支持力不触发 |
| 多 manifold、四接触点、护栏接缝、相反方向 | 同面合并，独立物体身份正确；持续接触不变成撞击串 |
| 30/60/144 FPS、0/1/8 步帧、重复读取、赶帧 | 相同物理事件不丢、不重播；声音不插值；无无界积压 |
| 100 ms 小脉冲、窗内更强、200–500 ms 第二击、翻滚脉冲 | 小型同源抑制，强击升级、第二击通过，scrape 不触发 impact |
| reset/rebase/NPC recycle、暂停/静音/车库/结果/close | 无旧 epoch 尾音或补播；rebase 不造撞击；统计原逻辑通过 |
| 采样池和预算 | 不连续重复，随机幅度受限，各类/总 voice 有界，预加载可独立叠加 |
| 真实 OpenAL、素材检查 | 无 BAD 声音，独立句柄并发、实际左右差异、循环连续；素材起音/响度/合成峰值报告 |

人工八项每项保留速度区间、对象、日志 event_id、感受和“通过/待改/物理不可复现”：①低速轻碰护栏；②中速正面撞护栏；③高速重撞；④高速侧擦；⑤撞 NPC；⑥旋转后第二击；⑦连续擦碰 ≥5 s；⑧物理允许的连续翻滚/落地。前 3 项需听到明确但不刺耳的强弱阶梯；4/7 是连续摩擦；5 有车身质感；6/8 多个真实撞击有节奏且不成噪声墙。另听同类 ≥10 次检查重复感、暂停/静音/恢复、轻碰后重撞的动态对比。不能用测试通过或波形合格代填人工结论。

## 12. 文件范围与施工顺序

仅涉及 `simulation.py`、`session.py`、`soundscape.py`、`application.py` 的数据/音频接口，新增上述两个小模块；必要的音频测试、诊断工具、音频素材/清单/准备脚本与文档。`Vehicle`、动力学、traffic/road、race/highway_run、settings 存储语义均只读。应用初始化可增加可选诊断参数，不改玩法/UI流程。

按单条施工线交 Luna，不逐票重复架构 review：

1. [6B-02 物理事实与事件传递](tasks/6B-02-impact-events.md)：包含无声诊断，先证实事件正确。
2. [6B-03 分层素材池](tasks/6B-03-impact-assets.md)：音色与许可，交可试听配方候选。
3. [6B-04 分层播放与声音生命周期](tasks/6B-04-impact-mixer.md)：按固定合同实施、自动验收。
4. [6B-05 驾驶校准与试听验收](tasks/6B-05-impact-calibration.md)：真实数据定参数，用户试听定通过。

本轮只新增设计/施工文档和核验事实，不声称新系统已实现。Luna 探索子代理启动时因额度限制失败，未产出修改；不由架构模型接管全部素材搜集和编码。未提交、未推送、未重新打包；6B 仍未通过。

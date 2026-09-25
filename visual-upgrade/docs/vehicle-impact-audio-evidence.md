# Impact Audio 接口核验记录

2026-09-23；基线 `34cec49231391c769ef38db1ee2e22363863c20b`；项目 `.venv/Scripts/python.exe`，Panda3D **1.10.16**。本轮仅做接口与短探针，不是整项目 review，也不是新系统 T0/T1 或听感验收。

## 代码事实

- `simulation.py`：`step()` 唯一调用 doPhysics；`_count_player_collisions()` 检查命名对象接触，距上次接触满 120 tick 才增加事故计数，持续接触持续刷新时间。`snapshot()` 返回该计数；`interpolate()` 用 replace 保留 current 的非插值字段。
- `soundscape.py`：以计数增加触发，`collision_sound_kind()` 用前后渲染快照速度变化，`impact_ready = now + 0.7`；一个 kind 一个声音实例；scrape 同样是一次性 play。
- `session.py`：FixedStepper 每帧最多 8 步；current/previous 每 tick 被覆盖，frame 返回插值状态。倒计时没有推进物理。start 可能替换 Simulation；pause/menu/reset/finish 会 sync_snapshots。
- `application.py`：在 session.frame 后调用声音、再绘制；车库路径直接传 session.current；smoke 模式不创建 Soundscape，不能把普通 smoke 当真实音频验证。
- `vehicle.py`：玩家和 NPC 均为 BulletVehicle；底盘 mass=1200 kg，盒半尺寸 `(0.78,2.05,0.42)`、形状偏移 `(0,0,0.42)`，读线/角速度与 transform 不必修改 Vehicle。
- highway 同名护栏有多段不同刚体；streamed 名称含全局 segment 整数；NPC 回收复用节点并增加 generation。节点名不能作为唯一碰撞身份。

## API 与来源

本地 `dir()` 确认以下方法存在，官方 1.10 API 与版本源代码交叉核对：

- [BulletWorld](https://docs.panda3d.org/1.10/python/reference/panda3d.bullet.BulletWorld)：`getManifolds()`。
- [BulletManifoldPoint](https://docs.panda3d.org/1.10/python/reference/panda3d.bullet.BulletManifoldPoint)：`getAppliedImpulse()`、两个 lateral impulse、`getNormalWorldOnB()`、`getPositionWorldOnA/B()`、`getDistance()`、`getLifeTime()`。
- [AudioSound](https://docs.panda3d.org/1.10/python/reference/panda3d.core.AudioSound)：同一个实例重复 play 会从头开始，应使用多个实例；音量/速率/状态接口可用。
- [1.10.16 OpenAL 源码](https://raw.githubusercontent.com/panda3d/panda3d/v1.10.16/panda/src/audiotraits/openalAudioSound.cxx)：`set_balance` 未实现；非 positional source 设置为 listener-relative；`set_3d_attributes` 可写位置。需真设备验证最终声像。

## 短物理探针

探针通过 Python stdin 运行，未修改产品源码、参数或现有测试。夹具初始设置只影响独立 Simulation 实例，最后 close。

1. 护栏：`Simulation(track='highway', traffic_count=0)`；reset_player `(5.8,30,0.55)`，初速度 `(8,12,0)`，90 次 `step(Control())`。每步后遍历含玩家的 manifolds，取 distance≤0 的点，同时对照 contactTest。
   - tick 21，碰撞前线速度约 `(6.732,11.963,-0.512)`，碰撞后约 `(-0.096,10.253,-0.394)`。
   - `highway-rail-1` 同一面 4 点法向冲量约 `0 / 1088.518 / 3345.833 / 3656.661`，合计 **8091.012 N·s**。
   - 同帧 contactTest 返回两点，冲量均 **0**。该事实支持改用求解 manifold，不声称所有版本/所有查询永远为零。
   - tick 42–47 出现约 41、106、34、31、27、24 N·s 小脉冲；多个点 lifetime 为 1。单点寿命不足以可靠定义“新事故”。
2. 墙：`Simulation(track='test', traffic_count=0)`；reset_player `(95,716.8,0.55)`，初速度 `(0,speed,0)`，100 步；只累计 end-wall、distance≤0 的接触点。

| 初速度 m/s | 首次/峰值 tick | 冲量和 N·s | 碰撞前 y 速度 m/s | 点数 |
|---:|---:|---:|---:|---:|
| 2 | 35 | 2348.585 | 1.860 | 4 |
| 8 | 10 | 11033.899 | 7.998 | 4 |
| 20 | 5 | 27350.419 | 19.995 | 4 |

这些值只证明现有求解数据可区分这三种夹具，不能直接充当游戏统一轻/中/重阈值。没有模拟运动 NPC、二次撞击或翻滚验收。

3. 支持力：独立 BulletWorld，gravity `(0,0,-9.81)`；静态地盒半尺寸 `(10,10,.5)` 位于 z=-.5；1200 kg 动态盒半尺寸 `(1,2,.5)` 位于 z=.51，禁止休眠；80 个 1/120 步。tick 80 稳定总冲量 **98.100 N·s**、各点 lifetime=75。每步执行/不执行 contactTest 两组结果相同。不能把支持力或 positive J 自动当撞击；本次无证据表明 contactTest 会重置真实 manifold 寿命。

复现核心循环（完整夹具参数见上述各项）：

```python
sim.step(Control())
for manifold in sim._world.getManifolds():
    if sim._chassis not in (manifold.getNode0(), manifold.getNode1()):
        continue
    for point in manifold.getManifoldPoints():
        if point.getDistance() <= 0:
            print(sim.snapshot().tick, point.getAppliedImpulse(),
                  point.getLifeTime(), point.getNormalWorldOnB())
```

正式采集应紧接 doPhysics 且在 rebase/recovery 之前。本次探针在 step 返回后读取，因场景未发生 rebase/recovery，足以核验接口，不代表已经实现生产采集时序。

## 当前 WAV 测量

标准库 wave + array 读取 mono PCM16，定义“起音代理”为首个 `abs(sample) > max(32, 0.1 * peak)` 的采样时间。该量不是静音长度，也不证明人耳起音或音色。

| 文件 | 时长 s | 采样峰值 dBFS（四舍五入） | 起音代理 ms |
|---|---:|---:|---:|
| impact_light.wav | 1.00 | 0.00 | 23.76 |
| impact_side.wav | 1.50 | -5.00 | 141.38 |
| impact_scrape.wav | 1.45 | -2.63 | 21.68 |
| impact_heavy.wav | 0.75 | 0.00 | 170.43 |

`prepare_audio.py` 的 heavy/light 使用 limiter，side 降 5 dB；scrape 截取原录音 0.2 s 后的 1.45 s，开头淡入 30 ms、尾部淡出 250 ms，未做循环接缝。现有 0 dBFS 峰值也不能直接拿去多层满音量叠放。

来源/许可结论只依据当前 License.txt、asset-register.csv、准备脚本：四项分别为 S022 Plastic Impact / S021 Metal Impact / S023 Metal Rail Scrape / S020 Rock Impact，登记 CC0，使用 HQ preview，原文件 hash 已在脚本。此次未重新线上核验这四项许可，也未试听批准复用。

## OpenAL 静音加载探针与限制

实际创建 p3openal_audio AudioManager，对同一 side.wav 调用两次 getSound，两个独立句柄均状态 READY；volume=0、未调用 play。setBalance(.2) 后 getBalance() 返回 0，符合版本源码；set3dAttributes(.2,1,0,0,0,0) 调用成功。

第一版探针错误调用未暴露给 Python 的 get3dAttributes，出现 AttributeError；更正为仅检查已暴露 setter 和状态后通过。尚未验证真实输出的左右声像、并发声数、回放延迟和音色，这些列入 6B-04/05。

本轮未运行 T0/T1/T2/T3，因为没有修改产品行为；上述仅为有明确输入的接口探针。Luna 素材审计子代理因额度不足启动失败，没有产出；由主会话补做上述限域读取与 WAV 测量，素材搜集仍留给实施包。

## 6B-02 求解后事件链实测

施工日期 2026-09-23；代码基线 `34cec49231391c769ef38db1ee2e22363863c20b`。`Simulation.step()` 在 `doPhysics(1/120, 4, 1/120)` 返回后立即读取 `getManifolds()`，先复制接触点和步前刚体运动，再按接触簇生成只读事件。新增 epoch 随 Simulation reset/player reset 更新；rebase 保持 epoch。Session 在一次 `frame()` 内逐 tick 收集实际前进步骤的事件，最多 8 tick，下一渲染帧返回空批次。

可复现探针：`.venv/Scripts/python.exe tools/impact_audio_check.py --probe --output logs/impact-probe-self-drive-20260923 --seed 23`。Panda3D 1.10.16，JSONL 共记录 11 个离散脉冲；原始输出在该目录 `impacts.jsonl`，配置/统计在 `summary.json`。日志会在接触开始/结束、pulse 与 epoch 切换时立即写行，稳定接触按 20 Hz 采样。

| 隔离夹具 | tick | raw impulse N·s | pre-solve normal m/s | pre-solve tangent m/s | contact points |
|---|---:|---:|---:|---:|---:|
| 斜向护栏接触（8,12）m/s | 21 | 8091.012 | 6.737 | 11.976 | 4 点聚合为 1 event |
| end-wall，初始 2 m/s | 35 | 2348.585 | 1.860 | 0.082 | 4 点 |
| end-wall，初始 8 m/s | 10 | 11033.899 | 7.998 | 0.736 | 4 点 |
| end-wall，初始 20 m/s | 5 | 27350.419 | 19.995 | 0.327 | 4 点 |
| 运动 NPC 相向碰撞 | 53 | 5293.278 | 7.931 | 0.035 | 车辆碰撞 |
| NPC 同一事故后续脉冲 | 98 | 327.257 | 0.747 | 0.028 | 独立第二 event |

探针的 20 m/s 隔离撞墙后还记录到多个低载荷 roof manifold 脉冲，最低 raw impulse 18.156 N·s；日志可用于判断它们是否是期望的翻滚/二次接触。斜擦护栏后记录的持续接触行包括约 41、20、5 N·s 等载荷，normal 分量衰减接近零，切向速度保持约 10 m/s；持续接触没有逐 tick 发事件。静态支持力负样本来自前述独立 1200 kg Bullet 盒探针（约 98.1 N·s/tick）。

后续固定输入补测把车头对准 `highway-rail-1`，初速度 2/8/20 m/s，其他物理设置不变：首次 front event 分别为 raw impulse 2125.820 / 10673.962 / 27998.267 N·s，normal component 1.647 / 7.983 / 19.992 m/s，切向分量 0.075 / 0.808 / 0.572 m/s，呈现单调正面碰撞趋势。840 tick、持续转向靠住护栏的擦碰夹具产生一次起始 event（tick 108：J=338.009 N·s、vn=0.873 m/s、vt=6.513 m/s）；之后有 658 个连续 tick（5.48 s）仍保持护栏 ContactState，没有重复 ImpactEvent。固定输入数据和诊断行保存在 `logs/impact-probe-self-drive-20260923/`；该结果是自动物理夹具，不是玩家人工驾驶的手感验收。

20 m/s 正面护栏夹具的 tick 21 还同时记录了两个不同刚体的 roof 接触，分别为 `highway-road`（J=653.826 N·s）与 `right-shoulder`（J=952.385 N·s）。这是不同真实对象，因此在 Simulation 保留为两个事件；后续音频预算需要决定如何混合，不应合并成一个伪物体事件。

当前 `ImpactDetectionConfig` 初值为 raw 噪声底 8 N·s、normal enter 0.65 m/s、excess enter 18 N·s、80 ms EWMA、连续 2 tick 退出。它们只用于驱动诊断夹具和后续人工采样；20 m/s 后低载荷 manifold 仍出现 pulse，需用真实驾驶日志核对，不能视为最终阈值。未测量运动 NPC 的多车型/接触角分布、连续翻滚/落地分布、护栏分块接缝的真实驾驶轨迹，也未进行声卡延迟、音色或人工体验验收。

T0/T1 最终结果均为 Ruff 与 96 项测试通过；T1 的 seed 0/17/23 各 1200 步 headless 检查通过。结果分别见 `logs/validation/20260923-085323-631582Z-T0/summary.json` 和 `logs/validation/20260923-085358-658732Z-T1/summary.json`。此次仅建立事实链，未实现 severity、声音选择、分层混音或最终 scrape loop。

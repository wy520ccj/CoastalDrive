# 6B-02 真实碰撞事件与帧传递

- 状态：完成；施工基线 `34cec49231391c769ef38db1ee2e22363863c20b`，实施时仅有预先存在的 6B 设计/任务文档未提交改动；源码开工干净。
- 阶段：6B；前置：读 AGENTS、current-progress、[设计](../vehicle-impact-audio.md) 第 1–7、11 节和 [接口证据](../vehicle-impact-audio-evidence.md)。无需重读全项目。
- 实施：单条施工线完成。本文批准的 Snapshot/Session 接口已接入；保留 6B-01 的碰撞声实现，未调整 `collision_sound_kind`。

## 目标与范围

交付可记录、不会丢失/重播的真实 ImpactEvent 与持续 ContactState，现有驾驶声音暂时保留至 6B-04 切换。

- 允许：`src/impact_events.py`（新增）、`src/simulation.py`、`src/session.py`；`tests/test_impact_events.py`、`tests/test_impact_delivery.py`（新增）；`tools/impact_audio_check.py`（先实现无声探针/记录）、`tools/validate.py` 的 audio 测试映射；本包、设计的校准记录、当前进度。
- 只读：Vehicle/vehicle_config、streamed_road/highway_segments（仅命名识别）、race/highway_run、现有声音/设置实现与相关回归测试。
- 禁止：动力学/道路/AI/120 Hz、两项原碰撞计数、比赛结果、音量设置；不搜集素材、不接新播放、不改旧枚举阈值。

## 顺序与验收

1. 先将证据中的墙/护栏/静置探针变成可重复短工具，追加运动 NPC、旋转接触、真实底盘落地与持续擦碰，保存原始 J/vn/vt/寿命/点数。设置初始位置/速度仅限隔离测试夹具，不得变更产品物理。物理检测门槛收敛为一份 `ImpactDetectionConfig`，用记录说明噪声/真实轻碰边界。
2. 实现不可变数据合同、求解后提取、同面聚合、护栏接缝身份、接触脉冲跟踪。registry 单调 ID + NPC generation，清理离开世界的对象；支持力/滑动单点换代不产生撞击串。禁止将音频 JSON 耦合进 Simulation。
3. 接入 Snapshot 默认字段与 Session 每帧批次；新世界/成功 reset 的 epoch 唯一，rebase 不清事件；不持有 Bullet 引用。

- [x] 同面四点合为一事件；相邻护栏 body 接缝按逻辑侧合并，不同车辆/不同法线簇保留身份。
- [x] 碰撞前相对速度包含玩家/NPC 线速度与角速度；node0/node1 法线统一指向玩家；墙/护栏及静置负样本可区分。
- [x] 持续接触不逐 tick 发 Impact；退出连续两 tick 后允许新接近脉冲；移动 NPC 夹具得到同事故多个事件而 `player_collisions` 仍为 1。
- [x] 30/60/144 FPS 原有回归、零步帧、单帧 8 tick 收集、重复 frame 不重播；直接 Simulation tick 不建待消费队列。
- [x] player reset、world restart 换 epoch 并清接触；rebase 保持 epoch；源注册在交通回收/道路流式卸载时清理。
- [x] 同种子 headless 原回归通过；Manifold 读取在求解后只复制数据，不写 Bullet 接触值。

## 验证

加入 audio 测试映射后：

```powershell
.venv\Scripts\python.exe tools/validate.py T0 --area audio --area core --area gameplay
.venv\Scripts\python.exe tools/validate.py T1 --area audio --area core --area gameplay
```

专项工具接口由本包实现为 `tools/impact_audio_check.py --probe --output <新目录>`，默认无声；输出原始 JSONL、场景参数、检测配置和摘要。自动运行只限短夹具；不升级长测。输出格式与退出码明确，失败保留证据。正式 T2 留到 6B-04 集成收口。此包不做听感验收。

## 交接

- 修改文件：`src/impact_events.py`（新）、`src/simulation.py`、`src/session.py`、`tests/test_impact_events.py`（新）、`tests/test_impact_delivery.py`（新）、`tools/impact_audio_check.py`（新）、`tools/validate.py`、本任务包、`docs/current-progress.md`、`docs/vehicle-impact-audio-evidence.md`。
- T0：`.venv\\Scripts\\python.exe tools/validate.py T0 --area audio --area core --area gameplay`，Ruff 通过、96 项通过。结果 `logs/validation/20260923-085323-631582Z-T0/summary.json`。
- T1：同范围 T1，Ruff 通过、96 项通过、headless seed 0/17/23 各 1200 步通过。结果 `logs/validation/20260923-085358-658732Z-T1/summary.json`。
- 无声探针：`logs/impact-probe-self-drive-20260923/impacts.jsonl` 与 `summary.json`；Panda3D 1.10.16，seed 23，11 个脉冲，包含斜擦护栏、2/8/20 m/s 墙碰、运动 NPC 与 840 tick 持续擦护栏夹具。正面护栏 2/8/20 m/s 原始冲量分别为 2125.820 / 10673.962 / 27998.267 N·s；840 tick 擦碰中最长接触连续 658 tick（5.48 s），只产生 1 个 ImpactEvent。探针是控制输入的自动物理测量，不是人工听感验收。
- 阈值 `8 N·s / 0.65 m·s⁻¹ / 18 N·s`、80 ms EWMA 和两 tick 退出均为 provisional；probe 中 20 m/s 翻滚后出现多次低载荷 roof 接触，须由 6B-05 对真实驾驶日志判定其节奏与边界。
- 当前尚未做 6B-03/04/05、T2、人工驾驶或听感验收。下一步进入 6B-03 素材池工作包；事件数据链不构成 6B 整体通过。
- 0.8.2 Windows x64 文件夹版由工作区源码重新构建，位于 `builds/0.8.2/win_amd64/`。从系统临时目录启动包内 `coastaldrive.exe --headless --track test --steps 1200 --seed 23` 返回 0；`--smoke --track highway` 离屏检查通过，284 tick、8 辆交通车，20 次重开节点/任务/事件稳定。报告和截图：`logs/package-0.8.2-smoke/`。打包保留已有的 `api-ms-win-core-path-l1-1-0.dll` 查找警告；尚未在干净 Windows 机器验收。EXE SHA-256：`7E5C16B01D0E8CFA2C0A10E07DD78D2433B9B683076E933F7A4D482E580DE401`。

## 人工采集入口

使用新目录启动真实游戏并写入诊断：

```powershell
.venv\\Scripts\\python.exe tools/impact_audio_check.py --drive --track highway --output logs\\impact-manual-20260923
```

开始自由驾驶后记录低速/中速/高速正面护栏碰撞、高速小角度擦碰、NPC 碰撞、一次分离后的二次冲击和持续擦碰。每轮独立输出目录；保留 `impacts.jsonl` 和对应驾驶条件/主观感受。碰撞行包含 event ID/group、tick、来源/材质、raw/excess impulse、碰撞前 normal/tangential component、contact zone/age、Bullet 点数/lifetime 及新 impact/持续接触标记。当前日志用于物理事实采集，severity 和播放决策尚未接入。

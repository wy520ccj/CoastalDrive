# 6B-01 音量设置与驾驶声音生命周期

- 状态：音量设置自动检查完成；碰撞音效人工试听未通过，暂停本轮音效修改
- 施工基线：`ee6a1d567f6e883c304ef28896146d0a8dbb6531`；开工时 `main` 与 `origin/main` 同步，工作区干净。任务定义中的 0.8.1 commit 是历史版本基线，不是本轮 HEAD。
- 阶段：6B；接续现有发动机/路噪/碰撞原型。
- 实施：Luna；不需要逐票 Astra 复核。若必须修改仿真快照或碰撞事件接口，先交出具体接口问题。

## 目标与范围

玩家可在主菜单调节并保存主音量/效果音量，重新启动恢复设置。零音量可靠静音；暂停、返回菜单、重开和退出正确处理声音。

- 允许修改：`src/soundscape.py`、`src/settings.py`、`src/application.py`；新增相关音频/设置测试及专项检查工具；`tools/validate.py` 增加音频测试映射；本任务包、当前进度、必要的README操作说明。用户首轮试听后另授权寻找真实声音素材，补充了音频 WAV、素材登记和处理脚本。
- 只读参考：`src/paths.py`、`src/session.py`、`src/garage.py`、`docs/phase6b-atmosphere.md`，以及开发计划第8节声音要求。
- 不得修改：车辆/交通/道路物理、120 Hz、比赛判定、现有皮肤存储含义；不重做整个HUD、不新增素材下载、不同时做NPC声音/胎滑/换挡合成。

## 验收

- [x] 主菜单加入声音设置入口；按钮调整两级音量，显示百分比，Esc 和返回按钮可返回。
- [x] 主音量与效果音量独立存入 `audio.json`；默认100%，缺失/损坏回退、越界限制并提示，保存失败保留本次运行的设置并提示。
- [x] 两级音量乘积作用于发动机、路噪、碰撞；任一级为零会立即停止循环声和正在播放的碰撞声。菜单/暂停/结果页停止驾驶循环，恢复驾驶复用现有循环对象，close 幂等停止所有声音。
- [x] 每帧消费碰撞计数，静音期间不补播；外观存储行为未改变。
- [ ] 正常设备人工复听起步、加速、路噪、碰撞、暂停与恢复；最新碰撞音效试听未通过，其余项目仍待确认。

## 首轮试听与录音替换

- 用户实际反馈：旧路噪过吵且不像真实路噪，发动机音色不佳，碰撞声偏软。效果音量为0而主音量仍为100%时全静音；三类驾驶声均属于效果音，因此这是两级音量乘积的预期行为。
- 源码声音已换为录音：真实怠速和提速发动机两层按转速混合，车内行驶录音提取道路质感并压低混音量。首次替换的 squareal 碰撞录音含用户指出的刹车/玻璃前奏，已移除，不再用于游戏。
- 最新碰撞素材改用同一组拉力赛车 CC0 录音，分别用于轻碰（塑料护栏）、侧向金属撞击、金属护栏擦碰、重度正面撞击（岩面）。制作命令：`.venv\Scripts\python.exe tools/prepare_audio.py`；准备素材需 ffmpeg、tar 和网络，游戏运行直接读取随项目保存的 WAV。完整来源、许可和加工记录见 `docs/asset-register.csv` 与 `assets/game/audio/License.txt`。
- 碰撞计数只给出接触事件，不含碰撞对象或接触法线。本实现不修改仿真接口，按相邻渲染帧的速度变化在车头/车侧坐标系估算强弱与方向，再选择上述声音；高速且较轻的侧向变化近似当作擦碰。实际接触物类型不可由现有数据确认，用户试听仍是最终听感验收。
- 旧0.8.1独立版未包含这些声音；本轮未重新打包。

## 最新人工试听反馈（未通过）

- 用户反馈：当前碰撞音效仍无法清楚区分撞击情况，也未能及时播放适配音效；实际驾驶中通常只听到一个类似盒子掉地上的软弱声音，不像撞车。
- 自动分类单测和 WAV 加载通过不等于碰撞体验通过。当前根据相邻渲染帧速度变化作事后估算，未使用碰撞发生时的接触方向、冲量或对象信息；这不足以保证即时、合适地选择音效。
- 按用户要求，暂不继续修改。后续恢复时先重新核对可用的碰撞事件信息，并单独确定是否允许扩大仿真接口范围；不得把本轮自动检查结果写成碰撞音效验收通过。

## 验证

- 音量初版的 T0/T1 已通过，证据分别在 `logs/validation/20260923-030217-540640Z-T0/summary.json` 和 `logs/validation/20260923-030225-090864Z-T1/summary.json`；声音替换后以本轮检查为准。
- 碰撞分类修改后的 T0：`.venv\Scripts\python.exe tools/validate.py T0 --area audio`，Ruff 与12项音频测试通过。证据：`logs/validation/20260923-061037-343947Z-T0/summary.json`。
- 碰撞分类修改后的 T1：`.venv\Scripts\python.exe tools/validate.py T1 --area audio --area appearance --area core`，Ruff、49项相关测试及 seed 0/17/23 headless 检查通过。证据：`logs/validation/20260923-061233-759093Z-T1/summary.json`。未运行 T2/T3。
- 七段当前 PCM WAV 经真实 Panda3D/OpenAL 加载 smoke。碰撞测试覆盖两级音量乘积、静音不积压、音量分级、四种分类、碰撞冷却及生命周期。自动结果不证明最终音色。
- 人工复听：待用户确认；使用正常窗口启动当前源码并试听。

## 交接

- 修改文件：`src/application.py`、`src/settings.py`、`src/soundscape.py`、`tests/test_audio_settings.py`、`tests/test_soundscape.py`、`tests/test_validation_runner.py`、`tools/validate.py`、`tools/prepare_audio.py`、`assets/game/audio/engine.wav`、`engine_idle.wav`、`road.wav`、`impact.wav`（删除）、`impact_light.wav`、`impact_side.wav`、`impact_scrape.wav`、`impact_heavy.wav`、`License.txt`、`docs/asset-register.csv`、`docs/phase6b-atmosphere.md`、本任务包、`docs/current-progress.md`。
- T0 首轮发现的导入排序和保存失败测试夹具问题均已修复；录音替换及碰撞分型后的最终 T0/T1 均通过。
- 未解决问题：用户实际试听不接受碰撞音效；当前声音仍过弱且缺少及时、可靠的情形区分。暂停本轮碰撞声音迭代，等待后续重新设计。其他人工试听项也未全部确认。
- 本任务包及相关代码/素材已按用户要求提交并推送至公开仓库，提交 `0c8377c`；本次不运行 T2/T3。6B整体仍未通过。

## 后续设计入口（2026-09-23）

用户已授权重新设计真实物理碰撞音频接口。后续采用 [Vehicle Impact Audio v1](../vehicle-impact-audio.md)，从 [6B-02](6B-02-impact-events.md) 开始实施；本包的音量语义保留，旧速度差分类/700 ms 冷却将在新播放器接入时移除。本轮设计未修改声音源码或素材，不改变本包“碰撞人工不通过”的结论。

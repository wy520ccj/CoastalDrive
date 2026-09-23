# 当前进度

更新：2026-09-23。游戏版本 **0.8.1 / 6B 环境与声音增量**；6B尚未通过。开工时 `main` 与 GitHub `origin/main` 同步；本轮待提交工作按用户要求发布至公开仓库。

## 已有能力

- 120 Hz真实四轮物理；保留玩家认可的油门/转向/刹车参数与倒车调姿规则。滨海计时赛无交通、单圈4检查点；自由驾驶8车且隐藏比赛框架并移除其碰撞，检查点不改变相机。
- 无限高速：直路/弯坡、分段加载、实体接缝、坐标重定位、交通生成回收；稀疏/普通/繁忙为6/12/18车。NPC有驾驶风格、变速跟车、打灯变道、超车回归与后方逼近让行。见 [traffic-v2-review.md](traffic-v2-review.md)。
- 5C自由驾驶统计与5公里无碰撞挑战已接入；倒车不重复累计里程，碰撞/复位使挑战失败；持续接触去重，暂停/倒计时不计时。见 [phase5c-gameplay.md](phase5c-gameplay.md)。
- 有限事故恢复只接入无限高速 `HighwayDriver`：刹停、观察间隙、低速物理回正与双闪；受阻重新等待。复杂翻车救援/事故抢道待做，详见 [traffic-recovery.md](traffic-recovery.md)。
- 6A车库完成两款车型、五种车漆预览与保存，见 [phase6a-garage.md](phase6a-garage.md)。6B已接入天空、路面/草地、植被、路边标杆和HUD底板；驾驶声音换成许可明确的录音。碰撞声已替换为四类录音并按速度变化估算分型，但用户最新试听结论为不通过：通常只触发一种类似盒子落地、软弱且不像撞车的声音，情形区分和播放时机仍不合格。按要求暂停继续修改，见 [6B-01任务包](tasks/6B-01-audio-settings.md)。

## 当前缺口

- 6B：6B-01音量设置自动检查通过；碰撞声音人工试听不通过。当前速度变化估算未能满足及时、明显区分撞击类型的要求，后续重做时须先检查碰撞事件可用信息及接口范围。其他车灯/环境层次、正式HUD/小地图、实际画面/录像、1080p帧耗时及整体体验验收仍待完成。
- H4B/H4C：严格连续可见窗口、内存平台、人工驾驶、繁忙交通长程、复杂恢复未完整验收。历史30分钟记录因中途最小化未通过严格可见要求，见 [H4B-endurance-review.md](H4B-endurance-review.md)。长测集中到7B交付批次。
- 三圈/幽灵回放延后4R；进一步物理7A和学习AI尚未开始。长期路线与各Gate阈值见 [development-plan.md](development-plan.md)。

## 本次工作流基底

- 根 [AGENTS.md](../AGENTS.md) 保存短规则；[任务入口](tasks/README.md) 定义单条施工线、交接及T0–T3；[模板](tasks/TEMPLATE.md) 用于独立功能包。代码简洁直白、按作用分块、中文注释，默认相关短测。
- [验证工具](../tools/validate.py) 已接入：显式选范围、独立日志、结果文件核验、失败停止、用户设置隔离；工具不替人工体验下结论。
- 前一工作流批次的工具自身13项短检查、交通20项相关测试、3种子headless启动及0/23种子各30秒弯坡物理检查均通过；证据：[工具T1](../logs/validation/foundation-workflow/summary.json)、[交通T1](../logs/validation/foundation-traffic/summary.json)。
- 碰撞分型修改后，T0通过Ruff和12项音频测试；T1通过Ruff、49项音频/外观/核心测试及3种子headless检查；7段WAV经真实Panda3D/OpenAL加载。命令和日志见 [6B-01任务包](tasks/6B-01-audio-settings.md)。未运行T2/T3、全套游戏回归或长测。
- 较早工作流验证基线为 `1e1bddec6ea16f01e02520566cd39a5a39be7d28`，其日志只代表当时版本。本轮6B-01以实际 HEAD `ee6a1d567f6e883c304ef28896146d0a8dbb6531` 为基底，开工时工作区干净；T0/T1记录了对应测试时未提交的源码差异。
- 历史175项回归、10种子各600秒与100公里结果属于当时H4B版本，见 [H4B-stability-review.md](H4B-stability-review.md)，不是本轮重跑结论。旧review按需查阅。

## 下一入口

- 当前施工包：[6B-01 音量设置与声音生命周期](tasks/6B-01-audio-settings.md)，音量功能自动验收通过，碰撞音效人工验收不通过且本轮已暂停修改。T0/T1结果、问题记录和修改文件见任务包；未运行T2/T3。
- 游戏独立版：`builds/0.8.1/win_amd64/coastaldrive.exe`，仍是替换前的声音；试听新声音须运行当前源码 `src/main.py`，解释器 `.venv/Scripts/python.exe`。本次没有重新打包。

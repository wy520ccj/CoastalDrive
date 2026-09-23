# 当前进度

更新：2026-09-23。游戏版本 **0.8.1 / 6B 环境与声音增量**；6B尚未通过。当前仅本地推进，暂不处理GitHub。

## 已有能力

- 120 Hz真实四轮物理；保留玩家认可的油门/转向/刹车参数与倒车调姿规则。滨海计时赛无交通、单圈4检查点；自由驾驶8车且隐藏比赛框架并移除其碰撞，检查点不改变相机。
- 无限高速：直路/弯坡、分段加载、实体接缝、坐标重定位、交通生成回收；稀疏/普通/繁忙为6/12/18车。NPC有驾驶风格、变速跟车、打灯变道、超车回归与后方逼近让行。见 [traffic-v2-review.md](traffic-v2-review.md)。
- 5C自由驾驶统计与5公里无碰撞挑战已接入；倒车不重复累计里程，碰撞/复位使挑战失败；持续接触去重，暂停/倒计时不计时。见 [phase5c-gameplay.md](phase5c-gameplay.md)。
- 有限事故恢复只接入无限高速 `HighwayDriver`：刹停、观察间隙、低速物理回正与双闪；受阻重新等待。复杂翻车救援/事故抢道待做，详见 [traffic-recovery.md](traffic-recovery.md)。
- 6A车库完成两款车型、五种车漆预览与保存，见 [phase6a-garage.md](phase6a-garage.md)。6B已接入天空、路面/草地、植被、路边标杆、基础驾驶声音和HUD底板，仍为原型，见 [phase6b-atmosphere.md](phase6b-atmosphere.md)。

## 当前缺口

- 6B：音量设置与真实试听、车灯/环境层次、正式HUD/小地图、实际画面/录像、1080p帧耗时及用户体验验收。
- H4B/H4C：严格连续可见窗口、内存平台、人工驾驶、繁忙交通长程、复杂恢复未完整验收。历史30分钟记录因中途最小化未通过严格可见要求，见 [H4B-endurance-review.md](H4B-endurance-review.md)。长测集中到7B交付批次。
- 三圈/幽灵回放延后4R；进一步物理7A和学习AI尚未开始。长期路线与各Gate阈值见 [development-plan.md](development-plan.md)。

## 本次工作流基底

- 根 [AGENTS.md](../AGENTS.md) 保存短规则；[任务入口](tasks/README.md) 定义单条施工线、交接及T0–T3；[模板](tasks/TEMPLATE.md) 用于独立功能包。代码简洁直白、按作用分块、中文注释，默认相关短测。
- [验证工具](../tools/validate.py) 已接入：显式选范围、独立日志、结果文件核验、失败停止、用户设置隔离；工具不替人工体验下结论。
- 本轮验证：工具自身13项短检查通过；交通20项相关测试、3种子headless启动、0/23种子各30秒弯坡物理检查通过，Ruff通过。证据：[工具T1](../logs/validation/foundation-workflow/summary.json)、[交通T1](../logs/validation/foundation-traffic/summary.json)。未运行T2/T3、全套游戏回归或长测。
- 验证基线 `1e1bddec6ea16f01e02520566cd39a5a39be7d28` 加本次工作区修改；基底修改为本地提交。日志记录测试当时的工作区状态，后续文档整理不改变已测代码。
- 历史175项回归、10种子各600秒与100公里结果属于当时H4B版本，见 [H4B-stability-review.md](H4B-stability-review.md)，不是本轮重跑结论。旧review按需查阅。

## 下一入口

- 下一施工包：[6B-01 音量设置与声音生命周期](tasks/6B-01-audio-settings.md)，状态 **ready / 未实施**。先完成一个功能块的T0/T1；6B一批任务完成后再T2和阶段复核。
- 游戏独立版：`builds/0.8.1/win_amd64/coastaldrive.exe`；源码入口：`src/main.py`，解释器 `.venv/Scripts/python.exe`。0.8.1随包资源、滨海离屏启动与20次重开已有历史记录；本次没有重新打包或改游戏行为。

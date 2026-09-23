# 当前进度

更新：2026-09-24。开发版本 **0.8.3 / Vehicle Impact Audio System v1**；碰撞音效已获玩家实驾试听通过，6B 整体画面与性能 Gate 仍未通过。0.8.3 碰撞音频系统及玩家验收记录已推送，远端 `main` HEAD 为 `6f546fe0b82a5646fff7e2e39e13c2121f40284c`。

## 已有能力

- 120 Hz真实四轮物理；保留玩家认可的油门/转向/刹车参数与倒车调姿规则。滨海计时赛无交通、单圈4检查点；自由驾驶8车且隐藏比赛框架并移除其碰撞，检查点不改变相机。
- 无限高速：直路/弯坡、分段加载、实体接缝、坐标重定位、交通生成回收；稀疏/普通/繁忙为6/12/18车。NPC有驾驶风格、变速跟车、打灯变道、超车回归与后方逼近让行。见 [traffic-v2-review.md](traffic-v2-review.md)。
- 5C自由驾驶统计与5公里无碰撞挑战已接入；倒车不重复累计里程，碰撞/复位使挑战失败；持续接触去重，暂停/倒计时不计时。见 [phase5c-gameplay.md](phase5c-gameplay.md)。
- 有限事故恢复只接入无限高速 `HighwayDriver`：刹停、观察间隙、低速物理回正与双闪；受阻重新等待。复杂翻车救援/事故抢道待做，详见 [traffic-recovery.md](traffic-recovery.md)。
- 6A车库完成两款车型、五种车漆预览与保存，见 [phase6a-garage.md](phase6a-garage.md)。6B已接入天空、路面/草地、植被、路边标杆和HUD底板；驾驶声音换成许可明确的录音。用户试听判定 6B-01 旧碰撞声不合格；0.8.3 用真实 Bullet 接触事件与 22 个新素材重建分层撞击和持续擦碰，玩家已实驾试听并判定新碰撞音效通过。

## 当前缺口

- [6B-06 繁忙车流空档诊断](tasks/6B-06-busy-traffic-gap-diagnostic.md)：在基线 `51ba3b2` 上以 seed 0/23 完成各 5 km 弯坡 18 车只读采样，保留实际画面重放。最长前后 150 m 合计至多 2 车区间为 seed 0 的 139–155 s；seed 23 的 186–192 s 前方 150 m 无车，但前方约 288 m 有车、后方 150 m 有 3 车。未见回收等待或生成异常；只增加诊断工具、测试和证据，不修改交通。详见 [证据](6B-06-traffic-gap-evidence.md)。
- 6B：6B-01 音量设置语义保持不变，旧碰撞声人工不通过。[6B-02](tasks/6B-02-impact-events.md) Bullet 事件与帧传递、[6B-03](tasks/6B-03-impact-assets.md) 分层素材池、[6B-04](tasks/6B-04-impact-mixer.md) 播放/擦碰/诊断已实现；轻/中/重 Bullet 夹具、NPC 事故、持续护栏接触和玩法碰撞去重集成测试通过。[6B-05](tasks/6B-05-impact-calibration.md) 的 v1 主观验收已由用户实驾判定通过；八项场景未逐项留证、severity 曲线未定量校准。其他车灯/环境层次、正式 HUD/小地图、实际画面/录像、1080p 帧耗时和整体体验验收仍待完成。
- H4B/H4C：严格连续可见窗口、内存平台、人工驾驶、繁忙交通长程、复杂恢复未完整验收。历史30分钟记录因中途最小化未通过严格可见要求，见 [H4B-endurance-review.md](H4B-endurance-review.md)。长测集中到7B交付批次。
- 三圈/幽灵回放延后4R；进一步物理7A和学习AI尚未开始。长期路线与各Gate阈值见 [development-plan.md](development-plan.md)。

## 本次工作流基底

- 根 [AGENTS.md](../AGENTS.md) 保存短规则；[任务入口](tasks/README.md) 定义单条施工线、交接及T0–T3；[模板](tasks/TEMPLATE.md) 用于独立功能包。代码简洁直白、按作用分块、中文注释，默认相关短测。
- [验证工具](../tools/validate.py) 已接入：显式选范围、独立日志、结果文件核验、失败停止、用户设置隔离；工具不替人工体验下结论。
- 前一工作流批次的工具自身13项短检查、交通20项相关测试、3种子headless启动及0/23种子各30秒弯坡物理检查均通过；证据：[工具T1](../logs/validation/foundation-workflow/summary.json)、[交通T1](../logs/validation/foundation-traffic/summary.json)。
- 碰撞分型修改后，T0通过Ruff和12项音频测试；T1通过Ruff、49项音频/外观/核心测试及3种子headless检查；7段WAV经真实Panda3D/OpenAL加载。命令和日志见 [6B-01任务包](tasks/6B-01-audio-settings.md)。未运行T2/T3、全套游戏回归或长测。
- 较早工作流验证基线为 `1e1bddec6ea16f01e02520566cd39a5a39be7d28`，其日志只代表当时版本。本轮6B-01以实际 HEAD `ee6a1d567f6e883c304ef28896146d0a8dbb6531` 为基底，开工时工作区干净；T0/T1记录了对应测试时未提交的源码差异。
- 历史175项回归、10种子各600秒与100公里结果属于当时H4B版本，见 [H4B-stability-review.md](H4B-stability-review.md)，不是本轮重跑结论。旧review按需查阅。
- 0.8.3 音频专项 T0、音频+核心+玩法 T1、全量 T2 均通过；T2 含 243 项 pytest、3 种子 headless 和直路/弯坡长程检查，摘要位于 `logs/validation/20260923-094112-766203Z-T2/summary.json`。原护栏回归测试期待碰实体护栏时无事故，修改前 Simulation 原样复现失败；现断言事故只计一次，保持物理轨迹/翻滚约束。
- 生命周期收尾：距离挑战结束的同 tick Bullet 护栏撞击保留在返回帧并仅消费一次；RESULTS 后停止驾驶循环/擦碰并拒收新撞击，倒计时也不接收碰撞声。真实物理回归与音频消费回归通过；T0/T1 摘要分别为 `logs/validation/20260923-103106-188109Z-T0/summary.json` 和 `logs/validation/20260923-103135-023455Z-T1/summary.json`，未重跑 T2。

## 下一入口

- 下一工作：转入 6B 画面与正式界面。先对当前 0.8.3 在主菜单/车库、滨海道路、高速车流、近景车轮及结算等真实视角做一次可见审查，再按问题收窄车灯、环境层次、HUD/小地图的施工范围；随后录制至少 3 分钟驾驶画面并测 1080p 帧耗时。当前游戏主菜单显示中文“计时挑战”“滨海自由驾驶”“无限高速”；此前建议点击英文 Start driving、寻找 DRIVING 是错误提示，DRIVING 只是内部会话状态。音频诊断工具仍可在将来出现具体退化时使用，见 [6B-05](tasks/6B-05-impact-calibration.md)。
- [6B-01](tasks/6B-01-audio-settings.md) 保留为历史任务：音量自动验收通过，旧碰撞声人工不通过；旧速度差分型与 700 ms 全局冷却已退出代码。0.8.2 独立版是旧声音基线，不用于新系统试听。
- 0.8.3 独立版：`builds/0.8.3/win_amd64/coastaldrive.exe`，随包核查 `impact-bank.json` 与 22 条新 WAV 均存在、旧四个碰撞 WAV 不在包内；最终包外离屏 highway 启动报告 `logs/package-0.8.3-final-smoke/h0-render-smoke.json` 显示通过、8 辆 NPC、20 次重启节点/任务稳定。该 smoke 使用 null 音频后端，声音本身另用开发环境真 OpenAL 核验；本机打包仍报告系统 DLL 查找警告，未在干净 Windows 安装环境验收。

# Visual Identity v1：工程与视觉约定

## 冻结起点

- 工程基线：`2185410ec1db1b390c4e89eac820e768ca88c5b9`。
- 开发分支：`visual-identity-v1`，独立工作树 `../CoastalDrive-VI-v1`。
- 原仓库 main 在 `73a466f`；归档提交 `702f956` 含根源码实验增量，不是正式起点。main、`../CoastalDrive/visual-upgrade/`（含内层副本）和 `graphic_design/` 只读。
- 基线之后没有需要补挑的独立正式修复。终止撞击音频、交通只读诊断、起跑格/护栏修复已包含在起点中。
- 只按任务选择素材或小实现，不整包迁入 DS，不复制实验 Session、双 UI 路径或程序造车代码。

## 数据流与业务边界

Controller → Control → Simulation → Snapshot → Game / Presentation / UI / 后续 AI。

Simulation 唯一维护物理世界；Session 调度固定步、暂停与流程；RaceTracker/HighwayRun 权威维护规则和结果。渲染插值仅供表现，后续 AI 读取固定步原始快照，不另建物理、不模拟 KeyboardController。

UI 只持有界面节点、焦点、可见性和必要临时选择；通过命名回调表达用户意图，由 Application 调用 Session 现有操作。不得从页面直接 step/reset Simulation，不复制车辆状态或计算游戏结果。

| 现有职责 | 保留位置与边界 |
|---|---|
| 物理与车辆 | simulation、vehicle、vehicle_dynamics、vehicle_response、vehicle_state 原位保留；不得依赖 Scene/UI/Audio |
| 地图道路与交通 | 现有 world/tracks/road/traffic 相关文件原位保留；表现只读已有地图、分段和姿态 |
| 游戏规则 | session、race、highway_run 原位保留 |
| 3D 表现 | scene、garage、vehicle_visual；不写物理世界，不改规则 |
| 声音 | soundscape、impact_audio 消费状态与接触事实，不回控物理 |
| 应用装配 | application 保留窗口、输入路由、子系统装配、生命周期 |
| UI | VI-01 只建 ui/theme.py；HUD 随 VI-04、菜单随 VI-05A、结果随 VI-05B、车库 UI 随 VI-06B 分离 |
| AI | 以后作为 Controller 接入；本阶段不创建目录、基类或 Gymnasium 接口 |

只在正在开发的职责已清晰分离时局部拆分，不机械按行数或统一目录迁文件。主题模块不能持有应用、会话、物理或页面状态；不预建 BasePage、PageManager、注册器或通用框架。

Scene 穿透读取应用状态、声音内部兼容式 getattr 等已知债务暂留；只有对应职责正式修改时局部处理。真实文件/字体/资源/设备边界应给明确错误；项目内部约定错误直接暴露。

## 视觉方向与不变项

采用已审计的明亮海岸方向：暖阳、蓝绿海面、奶白 UI、深海蓝文字、少量橙色强调。3D 保持清晰低模；像素 UI 的字体与数字可读性优先。DS `logs/ui-preview/compare-menu.png` 上半为设计参考，下半为实验渲染，不得互相充当验收。

六个入口固定为计时挑战、滨海自由驾驶、无限高速、车库、声音设置、退出。VI-01 可选择字体、Palette、品牌与基础纹理，但不移动/改变 HUD、菜单、结果、车库布局或回调。

驾驶参数、车体轮心轮径、交通、道路/碰撞、比赛/成绩、设置格式、Session 和声音语义冻结。小地图、玩法、AI 与渲染框架不在本轮。窗口图标与品牌素材也需记录生成方式和来源，不因 DS 已有便自动采用。

## 证据与验收

VI-00 新证据：`logs/VI-00/`；代表图、报告与源/资产 SHA-256 清单存入 `docs/evidence/VI-00/`。原仓库 `logs/6B-08/ui/` 已混入后续画面，不作为该起点的原始截图。

每包使用新的日志目录，记录准确基线与未提交差异。测试用独立用户目录；本工作树复用 `../CoastalDrive/.venv/Scripts/python.exe`，源码与资源来自本工作树，不从 DS 导入。

T0/T1、真实离屏画面、用户实际体验分别记账。VI-00 只确认起点和方向，不将旧画面评价为最终合格。6B-07 远景护栏残余沿用此前阶段接受决定，整体可见窗口/性能 Gate 仍未通过。

后续 VI-GATE 沿用 1080p 中档、8车、预热30秒后采样5分钟，平均≥60 FPS、P95≤25ms，以及至少3分钟正常驾驶录像。VI-00/01 不执行此整体 Gate。

## VI-01 已固定的主题

单一主字体为 Fusion Pixel 12px proportional zh_hans；字体及 OFL 许可按 assets/game/ui/fonts/font-source.json 固定哈希。Ark 因当前文案缺字未采用。主色为 PAPER #F3EFE3、INK #102B3A、ORANGE #F47C24，辅色 SEA #247E96；成功/失败采用独立语义颜色。品牌保持同字体的 COASTAL DRIVE 文本；窗口图标由 tools/make_ui_brand.py 生成，不采用 DS 插画。ui/theme.py 不持有页面或游戏状态。具体证据和人工待验项见 tasks/VI-01.md。

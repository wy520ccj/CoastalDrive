# 困难模式键盘、倒挡说明与高速慢动作

2026-10-11，主目录 main，基线 `a7e13b2ca86c1b54715d0895cf0519fb699d7574`。用户确认倒挡反馈指“按 S 没有自动倒车”。本功能块修正困难模式键盘满舵输入和操作说明；**高速实时性能及完整仿真/人工阶段仍未通过**。正常 NPC 简化、玩家和困难所有车辆完整物理的授权保持。

## 已进入生产

困难模式原键盘短按直接请求 ±1，即方向盘打满；真实齿条虽有限速，100 ms 输入仍会引起明显转向。现在键盘表示持续转动方向盘，归一化行程每秒 .4，松键主动回正，长按仍达到原完整机械转角。该值是键盘接口选择，不是 OEM 实测驾驶员手速；车辆、齿条、轮胎、力学参数及研究用 VehicleCommand 不变。正常键盘策略保持原行为。

同一完整 GR86、平面世界、100 km/h 滚动初始条件，右键短按 .1 秒后观察一秒：旧输入真实齿条峰值 5.23847°、末航向变化 −15.30830°；新输入 .307073°、−.897894°。仅试验通过 initialize_rolling 设置共同初始轮速，不用于生产恢复或瞬移。完整逐拍原始记录留在 `logs/performance/hard-drive-r1/keyboard-tap.json`，可复算脚本及摘要已归档。

困难模式 S 保持只刹车；Q 选择 R，W 加油后真实后退，E 回前进挡。自动换挡仍适用于前进挡位。已验证真实 SessionProcess 选 R/加油链路，未添加 S 自动倒车；HUD/模式说明写明操作，空挡显示 N。困难成绩隔离为 `reference-keyboard-v29`，物理参考配置版本不变。

模型实际执行有限传动、四轮轮胎/悬架、三维刚体及电子控制，但机制完整不等于已完成实车标定。既有 GR86 标准实验含明确的原厂/测量/推导/工程先验边界；当前版本未新增实车操稳标定，界面已明确“尚未完成实车标定”。

## 真实验证与未解决项

- T0 11 项通过；最终相关 T1 **22 项、全 Ruff、0/17/23 各 1200 拍**通过。真实会话倒挡、短按、长按、跨采样频率及两种模式生命周期包括在内；复用相同版本结果，不重跑大阶段。
- 有效 1080p 前台困难 GR86/无限坡道/12 个完整 NPC/seed23/30 秒：物理 **59.9599 Hz**、绘制 **63.0514 FPS**、丢时 **13.4833 秒**。这是世界推进不足造成的实际慢动作；不通过时间倍率、减少 NPC 精度或插值补偿掩盖。窗口有效，但里程/性能 Gate 失败。
- 当前主进程 profile 定位完整几何扫描、车辆读取/准备、数值结果装配、轮端观测和快照的成本；profile 耗时不作为性能收益证明。
- 完整车辆线程隔离原型保持 480 拍解码后全部 JSON 数值相同；原始 pickle SHA 因对象别名关系不同不能作为相同字节证明。原型均值 29.657 ms、当时基线 25.266 ms，未采用；不跨日期/负载拼接收益。
- 子进程关闭 TransformState 缓存的窗口样本不满足前台有效性，未采用。首次线程接口/完整轮端入口错误及后续修复均留在 logs，错误/无效样本不冒充成功。
- 车辆固定进程/分别保存轮胎道路缓存的隔离原型 480 拍完整 SHA 相同。当前短 ABBA 基线均值 28.781 ms、候选 29.114 ms，无稳定收益，未采用。
- 无限道路几何修订号隔离原型 480 拍完整 SHA 相同；独立完整步均值 24.309 ms，但当前有效前台仅 45.356 Hz / 47.223 绘制 FPS、丢时 16.783 秒，实时仍失败，未采用。首次窗口因隔离资源根错误退出，修正后才产生这一有效样本；与较早 59.960 Hz 不作固定负载收益比较。原始代码和失败在 logs，修订号不是生产接口。

## 包与复现

独立输入修正包 r3：`builds/physics-native-traffic-r3/win_amd64`；四原生模块 SHA 一致。两个 physics-native-traffic 入口已指向 r3。仓库外正常/困难真实会话可见启动、各 8 车 120 拍 headless 和各 20 次重开离屏均通过。实际困难驾驶截图已检查，包含选挡后 W 加油与 S 只刹车说明；这些是启动/生命周期/渲染证据，不是 FPS 或用户驾驶验收。

```powershell
.venv/Scripts/python.exe tools/validate.py T1 --tests tests/test_keyboard_steering.py tests/test_driving_modes.py tests/test_driving_mode_ui.py tests/test_mode_lifecycle.py tests/test_session_process.py tests/test_traction_lifecycle.py --output <新目录>
.venv/Scripts/python.exe tools/performance/benchmark_runtime.py --output <新目录> --seconds 30 --track endless --shape hills --vehicle-design gr86-2022-premium-6mt --driving-mode simulation --traffic-count 12 --independent-clock
.venv/Scripts/python.exe setup.py build_apps --build-base <新目录>
```

原始测量/失败记录：`logs/performance/hard-drive-r1/`。本目录收据保留源码/模块 SHA、实际命令和测试结果；大体积完整轨迹留在 logs 并记录 SHA。本轮仅本地保存，不推送；公开 0.8.3 和根试玩入口不换版。高速实时性能、T2/T3、声音/长时间和用户实际驾驶 Gate 继续待办。下一实施块应覆盖完整车辆读取、观测、结果装配的连续数值边界；不继续扩展进程数量、线程切换或缓存开关试验。

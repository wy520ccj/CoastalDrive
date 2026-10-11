# 输入直达与完整轮端记录装配 r1

2026-10-11，主目录 main，基线 `e021eac87fcb010800170b41985463997b4d50bc`。本功能块已整合，可试玩；**困难高速仍慢，120 Hz/流畅及人工 Gate 未完成**。不推送，不替换公开0.8.3/根试玩.cmd。

## 实际改造

窗口按键直接发布到一个带锁的32位共享输入值，保存前后/左右/挡向；物理控制器在下一120 Hz拍读取，原 Control→Simulation 链路保持。输入不再等待帧请求的往返和旧快照领取；暂停、重开、失焦与控制器切换仍清空输入。共享内容只有驾驶请求，没有车辆状态或第二套积分；AI仍直接产生Control。显式切回本机键盘由持有者选择其原键盘，不通过RPC复制共享输入对象。

上版困难键盘 .4行程/s 需2.5秒打满，过于迟缓。改为1.2行程/s，约.833秒模拟时间打满；松键同速回正，短按仍是渐进请求。真实齿条、完整满舵转角、轮胎/悬架/传动、正常输入及相机常数不改；不补偿仿真欠账。困难成绩隔离为 `reference-keyboard-v30`。该速率为键盘接口选择，不是实车驾驶员手速标定；低于120 Hz时实际操作仍受慢动作影响。

完整轮端的施力和完成步观测记录，通过原生字典复制/已有字段更新装配，不再逐次执行51字段冻结构造器及generic replace。保持完整字段、力学账与原类型/冻结行为，旧记录不修改；不是省略遥测或降低物理精度。仅分配无变长载荷的普通Python记录，未知字段/类型错误明确报告；没有新增世界、管理层或降精度路径。

## 测量与验证

- 输入隔离对照：完整GR86、无交通、60 Hz绘制请求/120 Hz物理、16个均匀按键相位。从按键发布到真实 Controller.sample 的中位延迟 **14.9489→4.35665 ms**，最大23.4675→8.2513 ms。仅诊断副本给原Session添加采样时间戳；不是OS输入到最终像素，不代表12NPC重载下也有该延迟。`measure_input_latency.py`可复算。
- 完整困难GR86+12NPC/seed23/无限坡道、9数值进程，120拍预热/480拍正式，短ABBA四次源码稳定；全部480拍完整Snapshot SHA相同。完整步A平均28.467886 ms、B27.106189 ms，**−4.7833%**，仍大于8.333 ms。该对照在最终原生输入类型检查收紧前完成；有效记录分支不变，最终DLL另480拍与基线SHA相同，独立完整步33.238964 ms，不与早段ABBA拼接收益。
- 首轮相关T0输入9项、轮端/子步13项通过；最后输入类型边界/完整数值包8项通过，全Ruff通过。T1首轮60通过/4旧模式预期失败；基线原模块及原DLL实际重现相同4失败，校正测试为困难NPC完整机制、正常NPC明确无此遥测，以及正常完整玩家→困难全车重建。保留困难原阈值。修复后两生命周期/正常NPC共9项、Ruff、三种子各1200拍通过；其余有效60项按未改范围复用，不重复跑全套，不相加为新覆盖量。
- 初始旧/新窗口都未持续前台，均无效，不用其28 Hz数据作驾驶或FPS收益结论。工具启动时只挂接一次Windows前台输入队列以激活自身窗口并立即解除，仍逐秒核对真实焦点，未修改应用/系统优先级或亲和性、未关闭用户应用。
- **最终有效1080p前台、困难、无限坡道、12完整NPC、30秒**：物理32.250881 Hz，绘制33.409202 FPS，丢时19.758333秒，碰撞0。采样/工作进程来源有效，但性能/里程Gate失败；与上轮59.96 Hz的负载/时点不同，不作为版本退化或收益对照。没有关碰撞、删NPC机制或加速时间。
- r4独立包四原生模块SHA与当前构建一致，仓库外正常/困难真实会话可见启动、各8车120拍headless、离屏/各20次重开通过，实际困难截图已检查。渲染/启动验证不代替性能或人工手感。

## 复现及后续

```powershell
.venv/Scripts/python.exe tools/performance/benchmark_physics.py --output <新目录> --workers 9 --traffic 12 --mode simulation --traffic-input-mode game --track endless --shape hills --driver endurance --seed 23 --warmup 120 --steps 480 --capture-hashes
.venv/Scripts/python.exe tools/performance/benchmark_runtime.py --output <新目录> --seconds 30 --track endless --shape hills --vehicle-design gr86-2022-premium-6mt --driving-mode simulation --traffic-count 12 --independent-clock
.venv/Scripts/python.exe setup.py build_apps --build-base <新目录>
```

实际命令、模块SHA、无效/失败结果及最终480拍SHA见收据。大体积原始信息保存在 `logs/performance/input-latency-r1/`；本目录只去掉逐帧GC列表，保存原报告SHA/位置。r4包路径 `builds/physics-native-traffic-r4/win_amd64`；两个 physics-native-traffic 入口已更新。下一整车准备/观测/快照的连续数值边界，停止继续扩展进程/线程切换与缓存开关试验。T2/T3、声音/长时间、用户实际驾驶待办；整体优化不能标done。

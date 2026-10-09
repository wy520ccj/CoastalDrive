# 数值传输、加载与起步收口

2026-10-09，主目录main，施工基线 `e21315432757e560e31a66b47cae3d407110aab1`。用户要求收口最近任务、暂停优化并提交推送；本批自动功能块收口，实时物理目标和阶段/人工Gate保持未完成。累计未推送检查点cef1f4b、1efa3f3、e213154与本批一同正常推送origin/main，实际结果以Git远端核对为准。[收据](receipt.json)、[文件SHA清单](manifest.json)。

本目录用局部Git属性保留原始证据字节，不自动转换换行；pytest/Panda原始日志的行尾空格保持原样。SHA清单可直接核对Git载荷。

## 实施范围

工作进程按真实几何版本和硬件配置保存只读候选，不再每子步重建；四轮机械轴、接触几何、支撑点及滑移/抓地观测合并为严格double原生计算。新增固定七类记录的数值包传输，保留浮点原始位、整数和实际Panda姿态精度；格式/布局版本、截断和外部错误明确返回异常。静态几何/不可变配置在初始化时传输，实际当前状态仍逐子步读取，求解结果按原顺序写回唯一Bullet世界。120Hz、两个子步、方程、硬件参数、迭代上限和收敛精度保持。

加载画面负责启动全部进程、导入内核、准备静态几何与轮胎硬件、上传场景/文字资源，并执行前60拍真实落地计算。剩余悬架稳定过程分摊到三秒倒计时；两模式当前GR86都在第181拍稳定，GO后24拍的高度变化短测小于0.5毫米。使用真实重力、接触和制动命令，不瞬移、不重置车身速度。稳定判断为全车线速/角速各不超过0.001且连续24拍，最多360拍；这是初始状态等待条件，求解精度没有放宽。未稳定或资源未完成时不显示假GO。圈速/距离挑战从GO开始，模拟自身的真实tick保留；无窗口研究默认没有这段初始化。

中央3、2、1及GO预先生成，沿用现有斜体显示字体、浅色数字/橙色GO和薄阴影；短促放大回落，不再使用首版大色块/星形底牌。独立倒计时按真实经过时间计数，不受驾驶物理追帧丢时影响，暂停保留剩余时间。连续重开回归根因是手动renderFrame抢在正常PBR任务前绘制；已移除手动绘制，首次正常场景帧仍由Loading遮罩覆盖，下一帧开始倒计时。

参考：[NFS官方起跑实录](https://www.youtube.com/watch?v=CBPZapIh4MQ&t=40s)、[Nintendo起跑节拍说明](https://www.nintendo.com/jp/ichikara/aabpa/index_en.html)、[Panda异步加载说明](https://docs.panda3d.org/1.10/python/programming/advanced-loading/async)、[prepareScene资源准备接口](https://docs.panda3d.org/1.10/python/reference/panda3d.core.NodePath)。动态碰撞和驾驶状态仍在游戏内实时求解，预加载只提前完成与当前操作无关的固定工作。

## 验证与证据复用

- 1024组四轮观测（4096轮）与独立原公式逐值hex相同；数值包4096随机double含NaN/Inf/负零位级往返、实际刚体与完整推进、截断/版本/布局/类型/溢出/循环错误检查通过。几何缓存、批量观测和数值包三个版本的海岸8车128拍完整快照载荷SHA均为 `50c86491ade70d63cd74dde1980ad1539d1119082685aae6428886a43e01b1ac`，归档时重新解压核对，复用 [已存完整轨迹](../parallel-rear-r1/trajectories/coastal.json.xz)，不重复存储大载荷。
- 广覆盖T1-r1为683通过/1连续重开失败；r2为43通过/同一失败，三种子均未跑。数值求解相关实现此后未改，已有有效节点按范围复用，不把历史数目相加。修复后目标T0-r2三节点通过；最终相关T1-r3为44项、全Ruff及0/17/23各1200拍启动通过。[最终T1](validation/PHYS-PERF-01-loading-wire-T1-r3/summary.json)。初始化及比赛计时T0为15项通过。
- 当前正常 `start_game → Loading → Countdown` 路径，1080p海岸GR86+8车、9进程、无截图读回，两模式所有倒计时采样均在前台且未最小化。加载结束tick60/1080次远程，稳定tick181，GO为3.091/3.121秒；倒计时比赛时钟保持0。绘制约150.98/148.03FPS、P95为10.60/10.41ms，**最大间隔132.39/155.76ms仍保留**。[正常模式](countdown/PHYS-PERF-01-countdown-loading-final-game/report.json)、[困难仿真](countdown/PHYS-PERF-01-countdown-loading-final-simulation/report.json)。只是三秒启动检查，不替代驾驶阶段性能Gate。
- [3](countdown/visual-r7/3.png)、[2](countdown/visual-r7/2.png)、[1](countdown/visual-r7/1.png)、[GO](countdown/visual-r7/go.png)为同一最终数字表现的r7离屏截图，已目视；捕获时仍是完整落地放在加载前的版本。当前分摊加载路径以最新窗口报告及测试为证，不混称截图证明分摊行为。r7使用单线程绘制避免离屏读回死锁，非FPS/人工结论。

## 性能与剩余边界

三组128拍短诊断用来定位，无严格A/B。批量观测13.694ms/拍，数值包13.711ms/拍，**不能声称新数值包带来稳定无窗口收益**。有调用计时的30秒窗口诊断达到102.12绘制FPS/P95约15.03ms，却仅完成1521拍、约12.675秒模拟；采样段丢时15.767秒，实时120Hz仍未通过。线程CPU逐调用在Windows上量化为15.625ms，应看聚合均值；主循环GC频率与Python线程切换间隔保持原值，试验没有稳定收益。[窗口诊断](window/window-numeric-packet-phase-r1.json)。

失败原样保留：最初数值包错误消息用了不支持的非ASCII PyErr_Format格式，已修为明确SetString；首轮倒计时4.098秒及数字索引问题已修。手动PBR更新的渲染顺序T0-r1仍失败，最终移除手动render后T0-r2通过。r4/r6离屏Draw管线截图读回挂起、中断并结束对应进程，没有完整报告，不记通过。早期600拍静止制动探针出现倒车请求/共同求解异常，不能当作长时间驻车已通过；当前真实初始化在181拍完成，长驻车边界未在本批展开。旧车辆细化/阶段T2失败仍见任务包，未重跑或放宽门槛。

最终候选 `parallel-r1d` 输入前后冻结且与收口源码相同，四个PYD逐字节相同；仓库外两模式海岸8车各120拍、9进程/2160数值包/远程求解及零世界回查通过，两模式离屏渲染和各20次重启通过，截图已目视。[构建收据](package/PHYS-PERF-01-package-parallel-r1d/summary.json)、[仓库外检查](package/PHYS-PERF-01-package-parallel-r1d/package-check.json)、[渲染/重启](package/PHYS-PERF-01-package-parallel-r1d-render/summary.json)。r1c是修复渲染顺序前的历史包，已被r1d取代，原文件保留。入口：[正常游戏](../../../../launchers/physics-parallel-r2-game.cmd)、[困难仿真](../../../../launchers/physics-parallel-r2-simulation.cmd)；根目录公开试玩不变。

按用户指示暂停优化，不再安排新的热点试验。后续只有在用户恢复工作后，才继续实时物理预算、初始化单帧长间隔、T2/T3及两模式实际驾驶/视觉验收；本次提交不是整个物理目标完成声明。

## 可复查命令

仓库Python下运行 `tools/validate.py T1 --tests tests/test_physics_workers.py tests/test_physics_wire.py tests/test_wheel_observations.py tests/test_session_clock.py tests/test_impact_delivery.py tests/test_mode_lifecycle.py tests/test_countdown.py tests/test_ui_assets.py tests/test_ui.py tests/test_results_keyboard.py tests/test_driving_mode_ui.py tests/test_core.py::test_countdown_freezes_car_and_pauses tests/test_stage4.py::test_time_trial_timer_starts_after_countdown --output <新目录> --timeout 240`。

起步检查为 `tools/performance/check_countdown.py --onscreen --no-images --mode game|simulation --output <新目录>`。已有有效结果不需要为了查看证据重复执行。构建、外部检查、渲染包装脚本和实际完整命令保存在本目录package与对应JSON中；构建脚本保留旧产物，不能覆盖原目录。

# 完整四轮接点准备与末状态装配 r9

2026-10-12，main基线 `b26175c`。**慢动作/整体运行流畅目标保持in_progress；正常模式短测通过，困难模式实时仍失败。** r9独立包和两个launchers入口已更新，公开0.8.3/根试玩.cmd保持；仅本地保存，不推送。

## 实现与边界

实际Panda接点/车身读取保持，四轮双精度正交基、惯量响应及完整ContactFrame/Mobility在一个原生入口准备。去掉随后被双精度结果覆盖的三次逐轮单精度矩阵变换。完整有限传动的四轮末状态以一个原生入口装配：实际冲量、旋转角、世界变形、滑移/力/支撑/抓地/刚度、耗散、陀螺/转向/接触角冲量和完整51字段记录，删除该路径无用的逐项累加数组。

物理冲量的float转换只发生在原Panda Vec3边界，原乘加次序及点/轴/陀螺冲量顺序保持；调用方仍向唯一Bullet车身提交。历史非有限路径继续原机制，不是求解失败回退。保留120Hz、两个真实子步、全部机械机制、困难NPC完整物理、原迭代/残差/碰撞与输入。法向系统在各子步末仍刷新，实际越界有限接点查询未削弱。

**不是整车所有准备/装配已原生化。** 悬架初始接点准备、传动输入/结果外层、Panda边界及部分材料/法向账仍在Python；当前没有新原生线程池或第二物理世界。

## 一致性和整步

- 原生接点准备256组×4轮，与原双精度计算全部字段类型/float位型相同；退化法向/切向仍报告原ZeroDivisionError。
- 16组合（陀螺/胎体开关、累加、正反序）各80组，共1280次完整四轮发布，冻结b26175c旧装配的所有字段、浮点位型和实际Panda冲量相同；覆盖空中/支撑、旧历史、整型转角、不同后轮硬件和None滑移字段。5120个完整轮端记录，未放宽物理阈值。
- 最终13车/GR86/困难无限坡道/12完整NPC/9工作进程/seed23，预热120、采样480，A/B/B/A四次**全部完整Snapshot SHA逐拍相同**。整步分别11.409662/11.233252/11.077084/11.500588ms，组均值11.455125→11.155168ms（−2.6185%），仍超8.333ms。早期publish单对照和frames单样本只是施工诊断，不与最终组拼接收益。
- T1 Ruff、662项相关测试与0/17/23各1200拍启动通过；之后19项完整记录/退化数学错误T0通过，662有效范围复用。真实输入fixture、工作进程/查询锁、各车先读后解、两子步外力/碰撞、有限传动/轴/悬架/轮端、会话与传输覆盖。原空中制动细化失败未修改/删除，T2/T3与人工仍待。

## 前台与包

- 有效1080p正常坡道12NPC/60秒：**120.000176Hz物理、85.486642FPS、P95 16.0106ms、P99 17.7695ms、最坏39.6778ms、>50ms为0、丢时0，short Gate true/退出0**。这是本版独立短样本，未与旧窗口配对，不能宣称长期长帧/人工手感已关闭。
- 有效1080p困难坡道12完整NPC/30秒：**66.364308Hz物理、75.036771FPS、P95 18.0709ms、最坏44.244ms、>50ms为0、丢时12.05秒，Gate false/退出1**。父/权威/工作进程来源和前台有效，玩家碰撞0。绘制顺畅不代表仿真速度正常；不将前一版本不同时间样本的71Hz拼接为收益/回退结论。
- r9四DLL与主源码当前构建SHA一致，仓库外双模式真实会话可见启动、8车120拍、离屏及各20次重开通过，双模式截图已目视。入口指r9；公开包未换。重编未改physics_packet源码，PE .text/.data/.pdata/.rsrc/.reloc与冻结DLL相同、.rdata构建身份不同；没有把撤回的键缓存混入生产。

## 失败与下一块

首次T0 Ruff导入格式失败；随后原生分支continue遗漏末法向系统发布，11失败/187通过/5夹具错误，修正末子步系统更新后138项通过；合并准备193项通过。新参考导入排序Ruff失败后修正、17项通过，再加退化数学错误后19项通过。首次包验证helper将r8替换为r9时误伤GR86为GR96，参数解析退出2；修正helper，原包无需重建，六项实际检查通过。失败收据及原日志保留，不计为包成功。

当前一次9车9进程worker-profile只是诊断：4320请求累计solve 9.052秒，其中joint_solve自身3.182秒、悬架prepare inclusive1.655秒；advance_drivetrain inclusive4.902秒含joint_solve，不能相加/作为吞吐。新tire_publish自身.066秒。下一覆盖**悬架准备、传动输入/结果的剩余整段Python计算**，使整车数值边界具备连续原生并行条件；继续保留完整模型，不靠改显示时间或降困难精度制造实时表象。

## 命令

```powershell
.venv/Scripts/python.exe setup.py build_ext --inplace
.venv/Scripts/python.exe tools/validate.py T1 --tests tests/test_native_tire_records.py tests/test_continuous_solver.py tests/test_vehicle_tires.py tests/test_rotor_transport.py tests/test_world_substeps.py tests/test_physics_workers.py tests/test_tire_compliance_substeps.py tests/test_finite_powertrain.py tests/test_wheel_observations.py tests/test_tire_shaft.py tests/test_tire_drivetrain.py tests/test_suspension_coupling.py tests/test_session_process.py tests/test_snapshot_wire.py --output logs/performance/complete-tire-native-r1/t1-final
.venv/Scripts/python.exe tools/performance/benchmark_physics.py --source src --output logs/performance/complete-tire-native-r1/final-b1 --workers 9 --traffic 12 --mode simulation --traffic-input-mode game --track endless --shape hills --driver endurance --seed 23 --warmup 120 --steps 480 --capture-hashes
# A源为logs/performance/complete-tire-native-r1/baseline/src；最终顺序A1/B1/B2/A2，独立输出。
.venv/Scripts/python.exe tools/performance/benchmark_runtime.py --source src --output logs/performance/complete-tire-native-r1/window-hard --shape hills --seconds 30 --track endless --vehicle-design gr86-2022-premium-6mt --driving-mode simulation --traffic-count 12 --independent-clock
# 正常使用game/60秒，输出window-game；所有窗口与测试/打包串行。
.venv/Scripts/python.exe setup.py build_apps --build-base builds/physics-native-traffic-r9
.venv/Scripts/python.exe logs/verify_complete_tire_package_r2.py
```

本目录收据保留原报告路径/SHA，只省略python_gc_pauses大列表。原始日志、源码冻结/四DLL、逐拍SHA、打包记录、profile及截图均在 `logs/performance/complete-tire-native-r1/`；新轮姿装配源码检查点亦随r9包带入。

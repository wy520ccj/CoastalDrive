# 权威轮姿装配检查点

2026-10-12，主目录main，基线 `a0a8ee7`。**仅源码检查点；困难高速慢动作仍未解决，目标保持in_progress。** 独立试玩入口仍指已验证r8，公开包未更新；本轮不单独重建包，后续完整车辆推进管线功能块一起交付。只本地保存，不推送。

完整悬架先给出实际四轮位置，随后一次创建WheelState，去掉读取无用原生轮位再覆盖的重复装配。绘制轮姿按Panda行向量约定 `roll * steer * body` 直接合成四元数，代替逐轮9次向量转换与矩阵往返。机械转角、齿条、悬架位置、车身、120Hz/两个子步及困难NPC模型保持。绘制四元数有单精度舍入/符号表示差异，不声称完整原始Snapshot SHA相同。

## 证据

- 1024组随机车身/齿条/轮角，逐轮三个单位轴与旧Mat3方法比较；位置相同，实际推进120拍后snapshot不修改机械状态。
- 13车困难无限坡道/GR86/12完整NPC/9工作进程/seed23，预热120、采样480拍。完整JSON快照逐字段类型和值比较，浮点用hex位型；只将 `wheels[].orientation` 改为三轴旋转等价检查。**3,821,280个其余叶字段精确相同、24,960个轮姿对比，最大轴误差5.495326149684843e-7。** 接触、动力学、传动、悬架、电子和事件字段均未排除。JSON不记录Python内部共享对象身份。
- A/B/B/A整步均值分别11.611780/11.331524/11.103005/11.601889ms。组均值11.606835→11.217264ms，减少3.356%；前一对含计时外完整快照装配/保存，后一对无capture，两对分别减少2.414%/4.300%。仍超8.333ms预算，不和环境负载不同的历史13ms拼接收益。
- T1 Ruff、37项相关完整模块测试、0/17/23各1200拍启动通过，含真实绘制节点、完整快照传输、会话/显示时间轴。首融合T0 22项与旋转专项1项通过。未重复T2/T3，原空中制动细化失败保持待处理；自动通过不替代人工手感。
- 本版独立1080p困难坡道前台30秒短样本，父/权威/9工作进程来源及前台有效：70.962453Hz物理、78.117713FPS、P95 17.2061ms、P99 19.0032ms、最坏39.683ms、>50ms为0、丢时11.008333秒，**Gate false、退出1**。不是旧/新前台配对，不宣称稳定整体收益；截图已目视，静态截图不证明运动连续或手感。

## 撤回与下一步

数值包字典键缓存候选：52实际包、10400次解码，0.0141307→0.0147584ms变慢；13车480拍SHA相同但整步13.178847→13.274419ms同样变慢，已恢复源码/测试/原DLL。首次UTF错误测试破坏长度字段而失败，修正夹具后通过；失败/候选保留logs，不混入当前成果。

本次trace仅定位：快照1.285ms/拍，工作结果收取含等待、解码和提交，inclusive阶段不得相加。已有 `whole-step-r1/worker-profile` 的480请求剖析：joint_solve自身.227秒、整车solve累计.954秒；这是较早版本诊断，不将profile时间作为当前吞吐或精确比例。下一覆盖完整车辆输入准备、有限接触、求解及结果装配连续边界，再决定原生并行组织；不降低困难精度。

## 复现

```powershell
.venv/Scripts/python.exe tools/performance/benchmark_physics.py --source logs/performance/observation-native-r1/baseline/src --output logs/performance/observation-native-r1/pose-a1 --workers 9 --traffic 12 --mode simulation --traffic-input-mode game --track endless --shape hills --driver endurance --seed 23 --warmup 120 --steps 480 --capture
# B1 source=src；B2/A2同参去掉capture，顺序B2再A2；各用独立输出目录。
.venv/Scripts/python.exe logs/compare_wheel_pose_snapshots.py logs/performance/observation-native-r1/pose-a1/snapshots.json.xz logs/performance/observation-native-r1/pose-b1/snapshots.json.xz --output logs/performance/observation-native-r1/pose-equivalence.json
.venv/Scripts/python.exe tools/validate.py T1 --tests tests/test_wheel_pose_composition.py tests/test_vehicle_tires.py tests/test_wheel_observations.py tests/test_vehicle_visual_parameters.py tests/test_snapshot_wire.py tests/test_session_clock.py tests/test_session_process.py --output logs/performance/observation-native-r1/t1-pose
.venv/Scripts/python.exe tools/performance/benchmark_runtime.py --source src --output logs/performance/observation-native-r1/window-pose --shape hills --seconds 30 --track endless --vehicle-design gr86-2022-premium-6mt --driving-mode simulation --traffic-count 12 --independent-clock
```

本目录收据保留原报告路径/SHA，只删大列表python_gc_pauses。原日志、逐拍压缩文件、trace、失败及截图在 `logs/performance/observation-native-r1/`。冻结baseline含起点全部源码/四DLL；benchmark父进程仅将资源路径指向共同主目录，不改物理。四DLL未修改。源码末次docstring改写在采样后，不影响执行行为。

# 正常交通与连续表现 r1 / 独立包 r2

2026-10-11，主目录main，基线`a5761250d800691f14b69592f3cf4e8e54b3e9ff`。用户明确授权“正常模式交通车简化，玩家和困难仿真保持完整”。**本功能块已整合、可试玩；总体任务仍in_progress，长帧和人工体验Gate尚未通过。** 本轮只本地提交，不推送；公开0.8.3和根试玩.cmd未换版。

## 实际改造

正常NPC采用同一Bullet世界里的动态车身和原生射线悬架/轮胎，两子步、质量、车身碰撞与CCD保留；保留执行器、制动压力和油门/换挡响应，简化有限机械、柔性/陀螺和轮端电子控制。静止制动采用真实Bullet休眠，可被碰撞和输入唤醒。玩家以及困难模式所有车辆继续完整模型和原精度；正常成绩版本game-native-traffic-v26隔离，困难reference-v28不变。

窗口使用SessionProcess，把原Session、Simulation和游戏规则完整移到唯一会话子进程；绘制只读已完成Snapshot、地图描述和规则快照。控制器在持有者中产生Control，不模拟按键。每次仅传新增真实快照，接收端有界12拍历史，无预测/第二物理世界。暂停、退出、重开、原错误传回和同世界相机扫掠都有明确请求；同步/离屏入口仍用原Session。

表现以整帧共同时间戳沿120Hz仿真轴延迟四拍（33.33ms），相机用显示时间差、精确连续目标积分，保持原0.08s跟随常数和相机检查点/碰撞行为。C纯数值求解期间只释放世界查询锁，实际Bullet准备和提交仍互斥。Windows等待改用高分辨率sleep，绘制采用原90Hz目标的显式等待。关闭Panda TransformState全局缓存，RenderState缓存和回收保持；静态物理缓存按真实矩阵识别，不依赖TransformState对象身份。

## 自动与运行证据

- 最终T1：26项完整相关测试、全Ruff、0/17/23各1200拍通过。随后元数据T0四项、最终关闭/交通T0十六项通过。初轮Ruff、旧完整NPC假设、旧测试接口和模式测试工况失败保留；没有放宽原断言。
- 完整困难GR86+2NPC、种子23坡道，基线和改后480拍完整SHA相同。会话进程双模式暂停后真实完成拍也与原本地世界逐拍推进的完整Snapshot相同；错误仍返回原ValueError，失败请求关闭无残留。
- 正常GR86+12NPC，0/23种子各30秒弯坡检查通过，真实高度/横移/碰撞/跳变要求不变。该结果对应恢复后的原20Hz交通批次，分摊决策试验已撤销；此范围有效结果复用。
- **最终有效前台60秒**：1080p、无限坡道、GR86、12NPC、seed23、音频按smoke禁用、保留用户应用。物理120.0058Hz、绘制81.9259FPS、P95 17.5934ms、丢时0、碰撞0；出现两次>50ms帧（93.89/124.28ms），所以`short_performance_passed=false`。`passed=true`只表示窗口/里程/碰撞有效，不是性能Gate。
- 渲染诊断：车辆相对相机距离变化P95从244.981mm到1.560mm；显示速度比例P5/P95约0.950/1.057，超±10%的比例6.65%，显示时间无回退。该数据是程序表现/Draw回调，排除两长帧与低速段；回调不等于操作系统最终呈现，也不代替用户体验。
- 隔离整会话12拍重复传输119.52Hz/66.56FPS，增量真实快照120.007Hz/82.898FPS；生产已接后者。早期两次协议失败、受自身残留进程干扰而中断的一次记录保留；仅clean/delta及最终生产样本可用。
- 独立包`builds/physics-native-traffic-r2/win_amd64`成功构建，四个原生模块SHA与源码构建一致。仓库外双模式可见主菜单→8车驾驶启动、120拍/8车真实headless和离屏各20次重开均通过，实际截图已检查。可见启动使用真实会话子进程；离屏使用原本地会话，分别记账。此前r1包已过时，两个新launchers指向r2。

## 复现

```powershell
.venv/Scripts/python.exe tools/validate.py T1 --tests tests/test_session_process.py tests/test_session_clock.py tests/test_chase_camera.py tests/test_npc_physics.py tests/test_world_substeps.py --output <新目录>
.venv/Scripts/python.exe tools/performance/trace_presentation.py --output <新目录> --seconds 60 --track endless --shape hills --vehicle-design gr86-2022-premium-6mt --driving-mode game --traffic-count 12 --independent-clock --trace-draw-poses
.venv/Scripts/python.exe setup.py build_apps --build-base <新构建目录>
```

完整测量与命令见归档JSON，原始位置是`logs/performance/traffic-native-r1/`；大体积逐拍JSON不进Git，receipt保存源码/模块SHA，完整模型480拍SHA清单已归档。T2/T3、困难前台性能、声音和用户双模式实际驾驶未跑或待验。下一步定位两次绘制长帧；不可把物理120Hz和离屏启动当成流畅阶段完成。

依据：[Panda TransformState源码](https://raw.githubusercontent.com/panda3d/panda3d/v1.10.16/panda/src/pgraph/transformState.cxx)、[Bullet原生车辆与子步制动](https://raw.githubusercontent.com/bulletphysics/bullet3/2.84/src/BulletDynamics/Vehicle/btRaycastVehicle.cpp)、[CPython Windows sleep](https://docs.python.org/3.14/library/time.html#time.sleep)、[Panda时钟源码](https://raw.githubusercontent.com/panda3d/panda3d/v1.10.16/panda/src/putil/clockObject.cxx)。

# 山脊穿行快跑的接触求解修复

2026-11-06，基线 `15c321f5`。本机带路面接缝修正的 SDK，原车、种子0、目标105 km/h、曲率预瞄3.8 m/s²。在约196米处复现上一轮错误，失败前第1739拍状态及控制记录一致。冻结机械输入并缩小到原有两段铺装后，旧扩展三次均报相同残差，20轮末几何误差为0.0816849544。

诊断显示右前轮始终接地。相邻两个有限三角面被交替选作末态支撑，法线相差约1.00°。稳定交替阶段的两次首接触入射分数相差约7.7e-8。其余三轮的梯度变化远小于右前轮，单纯继续迭代不能消除这组来回切换。

原生末态接触保留最早真实入射分数。只有同一网格中共享整条边、法线有浅折差且入射分数差小于8倍单精度机器精度的两个面，才连续分配它们的接触方向与力臂。多面反力仍用通用功共轭离散梯度。平面、实际棱角、跨物体、较大折角、初始接触查询以及原共同求解接受门槛沿用现有实现。生产只替换轮胎接触扩展，路面几何、车辆参数、驾驶控制、120 Hz和奖牌线保持。

冻结夹具在最终算法上6轮通过，三次物理结果一致，法向残差9.095e-13、轮胎最大残差4.837e-5。26 KB压缩夹具及源指纹位于 `tests/data/challenge-ridge-face-tie/`。隔离候选和本机正式入口各按原失败策略完成一次。本机正式结果为55.453秒、22.303 L/100km，零碰撞、四段、原始燃油与终点过线复算通过，按现有规则落在银牌范围。自动实跑不写玩家成绩，原六份玩家逐拍记录哈希一致。故障前20 Hz观察记录的最大车速差约0.000014 km/h，轨迹存在微小数值变化。

普通SDK相关T1 55项、Ruff及三个种子各1200步通过。本机修正SDK的同批首轮53过2失败，两项均为跨Box夹具初始坐标断言，旧轮胎扩展在同SDK也得到同一偏差。调整夹具的单精度初始坐标舍入范围至2^-22米，实际过缝高度与物理容差保持，定向补验2项通过。整包T2、实时性能和玩家手感仍待验收。

证据保存在 `logs/challenge-ridge-solve-20261106/`，包含原失败及诊断、两版扩展、复放、完整试跑及复算。生产轮胎接触扩展 SHA256 为 `591b67790108835b7c2873702603ce1b59ef0fec0d5ac6084ad5bba060ea6537`。未提交推送。

```powershell
$sdk=(Resolve-Path 'build/road-edge-sdk/panda/built-road-edge').Path
$env:PYTHONPATH="$sdk;$env:PYTHONPATH"
.venv/Scripts/python.exe tools/physics/challenge_course_failure.py --output logs/challenge-ridge-solve-20261106/replay --replay logs/challenge-ridge-solve-20261106/failed-input.pkl
.venv/Scripts/python.exe tools/challenge_balance_check.py --output logs/challenge-ridge-solve-20261106/fast-release --routes ridge-run --builds stock --seconds 150 --target-kph 105 --curve-acceleration 3.8
```

重放目录中的原失败报告使用旧扩展，最终扩展证据见 `replay-native-final/summary.json`。完整验证命令在 `T1-ordinary/summary.json`、`T1-release/summary.json` 和 `T0-sdk-box/summary.json`。

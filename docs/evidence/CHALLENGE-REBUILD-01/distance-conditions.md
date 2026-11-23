# 五公里无碰撞挑战的路况与完赛对照

2026-11-06，基线 `15c321f5`。高速菜单原来允许选直线或弯坡、三档车流。接入预算后，发车把所选弯坡覆盖成直线，却继续使用所选密度，导致不同车流共用最快完赛。现在统一的预算发车路径读取所选道路与车流，重试和实验返回也走同一入口。预算五公里默认使用种子0，同一组不会随上一场赛事改变。最快等完赛纪录与原始标定样本按实际道路、车数和生成范围区分。此前数据保留在原分组，自由驾驶及旧非预算调用保持原行为。

赛前参数页沿用原布局，直接显示选定路况、无碰撞完成五公里的要求和复位规则。HUD计量点标为分段，结算显示1250、2500、3750米及终点。碰撞或复位仍优先于完成判定，倒车调姿不会重复累计里程。

| 道路和车流 | 自动策略目标 / km/h | 方案 | 费用 | 用时 / s | L/100km |
| --- | ---: | --- | ---: | ---: | ---: |
| 直线普通 · 12辆 | 144 | 原车 | 0 | 189.079 | 10.115 |
| 直线普通 · 12辆 | 144 | 动力115% | 3940 | 202.133 | 10.306 |
| 直线普通 · 12辆 | 144 | 轻量低阻 | 4780 | 172.645 | 10.459 |
| 弯坡繁忙 · 18辆 | 128 | 原车 | 0 | 221.918 | 8.993 |

四次均使用当前本机修正SDK及实际车辆控制，零碰撞到达五公里。逐拍首次终点、终点步内时间和实际燃油子步复算通过。直线普通组原车油耗最低，轻量低阻快16.434秒、油耗增加0.344 L/100km，动力单项更贵且较慢。改变配置会改变车流遭遇，这里比较完整试跑，尚不能从用时差独立估计动力或风阻贡献。弯坡组采用不同目标速度，用于证明选定路况可完赛。四次均为自动试车、无记分或授奖，原六份真人记录哈希未变。

相关T0首轮10过1失败，新UI测试错误地假设高速菜单默认直线。将测试明确设为从直线切换到弯坡，最终该项通过，其余10项结果复用。最终全仓Ruff通过。独立物理进程核对弯坡繁忙、18辆、种子0和原始记录分组。960×720方案、实际短驾驶及实跑数字结算图均已查看，结算为显示夹具。首张驾驶图未调用正常按钮布局刷新，补上采集器调用后复拍。未重启长回归、未作真人奖牌或性能验收，未提交推送。

```powershell
$sdk=(Resolve-Path 'build/road-edge-sdk/panda/built-road-edge').Path
$env:PYTHONPATH="$sdk;$env:PYTHONPATH"
.venv/Scripts/python.exe tools/challenge_balance_check.py --output logs/challenge-takeover-20261106/distance-main-choices --routes distance_challenge --builds stock power-only efficiency --seconds 230 --target-kph 144
.venv/Scripts/python.exe tools/challenge_balance_check.py --output logs/challenge-takeover-20261106/distance-hills-busy --routes distance_challenge --builds stock --seconds 300 --target-kph 128 --distance-shape hills --distance-density busy
.venv/Scripts/python.exe logs/challenge-takeover-20261106/verify_distance.py distance-main-choices
.venv/Scripts/python.exe logs/challenge-takeover-20261106/verify_distance.py distance-hills-busy
.venv/Scripts/python.exe logs/challenge-takeover-20261106/distance-conditions-ui/verify_process.py
.venv/Scripts/python.exe logs/challenge-takeover-20261106/distance-conditions-ui/capture.py
```

# HILL-TRAFFIC-01 弯坡车流证据

基线main/662f8ff3；[任务包](../../tasks/HILL-TRAFFIC-01.md)。新增seed23原hills道路、原普通12车的2.4公里全程，至少3次安全超车并保持安全到终点；侧距1米/前后10米不变。按权威道路局部标架读取世界快照，未更改物理/道路算法/NPC/原参数/SDK。

| 新实际记录 | 完成步 | 结果 |
|---|---:|---|
| normal-planned | 11128 | 92.733333秒金牌，3/3、2400.001米；81.95秒先达超车目标，仍继续到终点 |
| double-planned | 11128 | 92.733333秒金牌，3/3、2400.209米；81.941667秒先达目标 |
| normal-unsafe / double-unsafe | 各1036 | 8.633333秒、约120米，在碰撞前以间距不足失败；无成绩 |
| normal-follow | 15200 | 126.666667秒跑完2.4公里，0/3失败；无成绩 |

五份39528拍保存真实世界位置/朝向/速度、active/generation、origin、Control和全部规则结果，由同一道路重新投影后逐拍复算一致。三次长程均实际发生1次2000米重定位，规则里程与安全检查连续；最窄成功并排净距约2.22米。合理驾驶为测试工具HighwayDriver输出普通Control，追近对照为原KeyboardController二值请求；没有人工驾驶或实时性能结论。

两库另经正常菜单/真实独立SessionProcess重开，完整最佳、3次超车时刻与终点时刻共4个分段恢复，文件字节保持。恢复只推进初始少量完成步，不算新完整挑战；轮询句柄已释放后按完整落盘summary核实终态，无重复启动。

Normal/Double相关完整T1各47过及0/17/23各1200步启动通过，覆盖新规则、原直线、会话/进程、菜单/终点几何、同窗实验台返回、原短途及场景/模式生命周期。T0首次Ruff因工具局部变量遮蔽参数失败，修正后30项通过。原直线四份历史22169拍的全部旧规则字段精确保持，只新增route_id；是历史复算，非新Double物理。首旧记录读取因Windows清单反斜杠KeyError失败，原失败说明保留。

两种子预跑/完整记录与临时纯规则间距分析单独归档，999次临时目标只用于检查预跑全程间距，不作正式赛事通过。正式路线在测量后冻结为3次+全程，金110/银140/铜180秒。

用户随后指出2050米警示牌穿入隔音屏；对应修正与真实同视角前后图见[ENV-SIGN-CLEARANCE-01](../ENV-SIGN-CLEARANCE-01/README.md)。本包道路运行图为修复前实际记录，不称整体人工画面通过。最终仅嵌套环境小牌横坐标变化，根层全部生产者与原捕获完全相同，见`producer-source-check.json`；参考完整驾驶，未为外观重跑物理。

主要命令（输出目录首次捕获时须不存在）：

```powershell
.venv/Scripts/python.exe tools/overtake_probe.py --output logs/validation/HILL-TRAFFIC-01-probe-23 --shape hills --seed 23 --distance 2400 --seconds 180
.venv/Scripts/python.exe tools/overtake_check.py --output logs/validation/HILL-TRAFFIC-01-normal-planned --mode hill_traffic
.venv/Scripts/python.exe tools/physics/run_sim_double.py tools/overtake_check.py --output logs/validation/HILL-TRAFFIC-01-double-planned --mode hill_traffic --size 1024 768
.venv/Scripts/python.exe tools/overtake_check.py --output logs/validation/HILL-TRAFFIC-01-normal-unsafe --mode hill_traffic --unsafe
.venv/Scripts/python.exe tools/physics/run_sim_double.py tools/overtake_check.py --output logs/validation/HILL-TRAFFIC-01-double-unsafe --mode hill_traffic --size 1024 768 --unsafe
.venv/Scripts/python.exe tools/overtake_check.py --output logs/validation/HILL-TRAFFIC-01-normal-follow --mode hill_traffic --follow
.venv/Scripts/python.exe tools/overtake_check.py --output logs/validation/HILL-TRAFFIC-01-normal-planned --mode hill_traffic --restore
.venv/Scripts/python.exe tools/physics/run_sim_double.py tools/overtake_check.py --output logs/validation/HILL-TRAFFIC-01-double-planned --mode hill_traffic --size 1024 768 --restore
.venv/Scripts/python.exe tools/overtake_legacy_check.py --output logs/validation/HILL-TRAFFIC-01-legacy.json
.venv/Scripts/python.exe tools/validate.py T1 --tests tests/test_hill_traffic.py tests/test_hill_traffic_ui.py tests/test_overtake_run.py tests/test_overtake_session.py tests/test_overtake_ui.py tests/test_highway_run.py tests/test_sprint_ui.py tests/test_mode_lifecycle.py tests/test_scene_lifecycle.py --output logs/validation/HILL-TRAFFIC-01-T1
.venv/Scripts/python.exe tools/physics/run_sim_double.py tools/validate.py T1 --tests tests/test_hill_traffic.py tests/test_hill_traffic_ui.py tests/test_overtake_run.py tests/test_overtake_session.py tests/test_overtake_ui.py tests/test_highway_run.py tests/test_sprint_ui.py tests/test_mode_lifecycle.py tests/test_scene_lifecycle.py --output logs/validation/HILL-TRAFFIC-01-double-T1
```

`archive-manifest.json`固定96份原始文件/85761603字节，`source-manifest.json`固定28份最终源码LF SHA（包含后续环境修正）；目录禁用自动换行转换。仅本地，不推送。原T2/实时/人工Gate继续开放，持续目标active。

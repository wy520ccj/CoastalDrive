# VALLEY-PACE-01

2026-10-19；基线main/dce0fcc5。新增“山谷节奏”：原hills道路seed17，1公里下谷再爬坡，250米门至少60km/h；400–650米全段35–50km/h，1000米终点。金/银/铜70/85/105秒，全程180秒。依据实际约61秒完成保留这组初拟目标。原两项路线的规则、时间标准和成绩保持。

## 实际驾驶对照

| SDK | 驾驶请求 | 结果 | 时间/s | 完成步 |
|---|---|---|---:|---:|
| Normal | 持续90km/h目标 | 400米入带约90.94km/h，违规失败，无奖牌/有效最佳 | 19.666667 | 2360 |
| Normal | 加速→提前制动→控速→再加速 | 金牌，有效最佳；带内42.84–44.16km/h | 60.94505808442285 | 7314 |
| Double | 持续90km/h目标 | 400米入带超速失败，无奖牌/有效最佳 | 19.666667 | 2360 |
| Double | 加速→提前制动→控速→再加速 | 金牌，有效最佳；带内42.84–44.21km/h | 61.14021817812366 | 7337 |

4份原始gzip共19371拍，均无碰撞。每拍保存真实位置/速度/朝向/原点/碰撞/事件、二值按键与原Controller请求，以及完整规则快照。验证驾驶员只通过正常KeyboardController请求；没有修改车身位姿、碰撞、道路、物理、硬件、辅助或SDK。持续快开的“挑战失败”是本次对照的预期结果，验证报告明确passed，不是被隐藏的测试失败。

四份`recheck.json`从实际位置/速度独立重建道路前向速度与门位，再逐拍复算所有规则字段，包括进入/退出边界插值、违规位置、全段极值、门速度/时间、奖牌和保存。各SDK分别执行，不是跨库套用数值。重试保存完整原最佳参考；失败未创建成绩文件。两库另起真实独立物理进程，经实际菜单读回山谷最佳/四段，文件字节保持；这两次恢复没有新增完整道路驾驶。

规则在完成步上检查与限速带交集的两个插值端点；区外速度不误入带内，跨区大步不能跳过判断，静止/逆向在带内不能避过最低速度。门线仍核对整车余量。蓝色路边控速带、预告/入口/出口文字只显示，不参与物理。Normal1280×720、Double1024×768实际规则页/制动接近/带内/出带/失败与成功结算已看；同窗山谷→实验台→同一山谷由真实UI生命周期测试覆盖，人工驾驶与趣味性仍待确认。

## 原两项保持与场景缓存修复

`legacy-recheck.json`读取[前批固定原始证据](../SPRINT-ROUTES-01/archive-manifest.json)，按保存位置/速度在新规则下复算Normal/Double两项历史数据，共32288拍。原有全部字段逐拍完全相同；只新增速度/限速带观测字段，旧路线没有速度要求。这是旧轨迹的规则复算，没有重跑旧物理或生成新驾驶。旧BestTimes总时长/四段格式无需迁移，新赛事按独立mode/seed/硬件/输入键保存。

同为hills但seed0/17不同的赛事直接切换时，原Application只按道路类型缓存Scene，可能留用上一道路的局部展示几何。`checks/seed-original-T0`真实复现“同一Scene仍被复用”，1项failed保留。只新增4行实际道路种子缓存判据/赋值；原形状算法/物理不变。修复后`seed-fixed-T0` 1过，最终Normal/Double完整相关UI/场景生命周期/模式模块各6过、各三种子启动通过。相同种子的重开仍复用Scene，旧场景关闭规则保持。

`cache-guard-only.json`及`diagnostics/application-before-seed.py`固定最后4行差异；删除这4行后Application其余全文按LF完全相同。四次真实驾驶的首末源码/SDK摘要一致，最终恢复版与其生产root/附加UI/驾驶工具摘要只有Application这一项不同。完整驾驶明确复用修复前初次直接进入的有效记录；没有把缓存补验冒充新跑圈。

## 检查分批记账

- `core-T0`：Normal31过，限速带上下边界/插值/整带跨越/停车/逆向/首门/旧模式/保存及实际会话。
- `ui-T0` 1过；后将往返目标从旧山脊明确改为山谷，`return-ui-T0` 1过。两者是实际Panda生命周期及明示结算夹具，不冒充完整驾驶。
- 主批`T1` Normal50过42.46s，`double-T1` Double50过41.22s；各Ruff与0/17/23种子各1200步通过。
- 缓存修复后的`final-T1` Normal6过61.12s，`final-double-T1` Double6过52.09s，各Ruff/三种子通过。它们是相关完整模块补验，不和主批重叠项合并为一个虚构的大套件数。
- 原T2落地制动失败、实时及人工Gate保持；本批未跑T2/T3、未做新性能结论，无远端推送。

## 命令

```powershell
.venv/Scripts/python.exe tools/validate.py T0 --tests tests/test_valley_pace.py tests/test_sprint_run.py tests/test_sprint_session.py --output logs/validation/VALLEY-PACE-01-core-T0
.venv/Scripts/python.exe tools/sprint_routes_check.py --output logs/validation/VALLEY-PACE-01-normal-fast --modes valley_pace --constant-speed --size 1280 720
.venv/Scripts/python.exe tools/sprint_routes_check.py --output logs/validation/VALLEY-PACE-01-normal-planned --modes valley_pace --size 1280 720
.venv/Scripts/python.exe tools/physics/run_sim_double.py tools/sprint_routes_check.py --output logs/validation/VALLEY-PACE-01-double-fast --modes valley_pace --constant-speed --size 1024 768
.venv/Scripts/python.exe tools/physics/run_sim_double.py tools/sprint_routes_check.py --output logs/validation/VALLEY-PACE-01-double-planned --modes valley_pace --size 1024 768
.venv/Scripts/python.exe tools/validate.py T1 --tests tests/test_valley_pace.py tests/test_sprint_run.py tests/test_sprint_session.py tests/test_sprint_ui.py tests/test_highway_run.py tests/test_session_process.py tests/test_mode_lifecycle.py --output logs/validation/VALLEY-PACE-01-T1
.venv/Scripts/python.exe tools/physics/run_sim_double.py tools/validate.py T1 --tests tests/test_valley_pace.py tests/test_sprint_run.py tests/test_sprint_session.py tests/test_sprint_ui.py tests/test_highway_run.py tests/test_session_process.py tests/test_mode_lifecycle.py --output logs/validation/VALLEY-PACE-01-double-T1
.venv/Scripts/python.exe tools/sprint_legacy_check.py --output logs/validation/VALLEY-PACE-01-legacy-recheck.json
.venv/Scripts/python.exe tools/validate.py T0 --tests tests/test_sprint_ui.py::test_same_shape_different_seed_rebuilds_road_presentation --output logs/validation/VALLEY-PACE-01-seed-original-T0
.venv/Scripts/python.exe tools/validate.py T0 --tests tests/test_sprint_ui.py::test_same_shape_different_seed_rebuilds_road_presentation --output logs/validation/VALLEY-PACE-01-seed-fixed-T0
.venv/Scripts/python.exe tools/validate.py T1 --tests tests/test_sprint_ui.py tests/test_scene_lifecycle.py tests/test_mode_lifecycle.py --output logs/validation/VALLEY-PACE-01-final-T1
.venv/Scripts/python.exe tools/physics/run_sim_double.py tools/validate.py T1 --tests tests/test_sprint_ui.py tests/test_scene_lifecycle.py tests/test_mode_lifecycle.py --output logs/validation/VALLEY-PACE-01-final-double-T1
.venv/Scripts/python.exe tools/sprint_routes_check.py --output logs/validation/VALLEY-PACE-01-normal-planned --modes valley_pace --size 1280 720 --restore
.venv/Scripts/python.exe tools/physics/run_sim_double.py tools/sprint_routes_check.py --output logs/validation/VALLEY-PACE-01-double-planned --modes valley_pace --size 1024 768 --restore
```

`archive-manifest.json`固定109份原始文件/19585695字节，`source-manifest.json`固定28份最终相关源码LF归一SHA。捕获工具在建世界前保存首摘要，在finally保存末摘要，单次case结束即保存case文件；不再因后续断言丢失全部上下文。`--verify`复算保存记录，必须先核对相应规则/道路/配置来源，不能自动给未来版本背书。整体持续目标active。

# SAFE-OVERTAKE-01 证据

基线main/1443a9bb；最终功能、命令和边界见[任务包](../../tasks/SAFE-OVERTAKE-01.md)。用户选择真实车流安全超车。本批无推送/发布，原T2/实时/人工趣味性Gate开放。

## 实际交通与恢复

固定原直路seed17、普通12车/540米分布，原NPC策略/速度/出生位置保持；玩家从正常出生/沉降/倒计时起步。工具试车员通过Control择道，失败对照使用原KeyboardController二值直行请求；均非人工驾驶。

| 最终记录 | 完成步 | 结果 |
|---|---:|---|
| normal-final | 9592 | 79.933333s / 1864.7m，2次安全超车金牌，最窄并排净侧距2.512m |
| double-planned | 9589 | 79.908333s / 1864.1m，2次安全超车金牌，最窄并排净侧距2.512m |
| normal-unsafe | 1494 | 12.45s / 232.8m，1次后因前后净距不足10m失败，零碰撞、无最佳 |
| double-unsafe | 1494 | 同规则/同失败位置，零碰撞、无最佳 |

四份22169拍均从保存的真实位置、朝向、速度、active/generation及origin重算规则，逐拍结果完全一致；没有重跑物理来冒充复算。`--verify`在最终脚本再次通过。每份捕获首末生产源码/实际SDK摘要一致；最佳按当前完整车/输入隔离，逐辆时刻属于同一次成功驾驶。

normal-final和double-planned另以真实独立SessionProcess从正常菜单重开，恢复原最佳与完整两次超车时刻，最佳文件字节保持；恢复只推进加载/初始少量真实完成步，不称为新完整挑战。宽屏1280×720和4:3的1024×768规则/HUD/成功/失败/恢复图均检查。

## 短检查与旧问题

- T0：首批16过/1项进程测试漏传driving_mode失败；修正后19过。
- Normal主T1：54过/1项UI夹具失败（HUD祖先仍隐藏，未刷新实际DRIVING面板）；修正夹具后整个新UI模块1过及0/17/23三种子通过，其他54项明确复用。最终生产行为没有因此改变，不冒充单批55全过。
- Double最终同一相关范围完整55过（72.94s），0/17/23各1200步启动通过；两库Ruff通过。
- 最初规则页文字压按钮已修。首次Normal快进后只调用一次3ms美术构建预算，远处道路没有完整显示，该旧图不验收。捕获工具补全同一真实段后Normal再跑一次9592拍；`capture-repeat.json`证明两个完整保存记录载荷SHA完全相同，未新增规则覆盖。全部旧记录/失败/旧图保留。
- 4:3首图漏调右上返回按钮锚点；只改捕获工具两行，最终独立恢复图补齐。`capture-source-comparison.json`确认四份最终驾驶与现源码的唯一差异为捕获脚本；首Normal还差规则页排版。物理/道路/交通/原参数/辅助/SDK均未改。
- 初测两份summary归档；原巡航0次、主动择道2次只是测量，非最终挑战。115MB级初测完整遥测不加入Git，原始文件保留本地logs，SHA/大小见`preliminary-local-records.json`；正式全部记录已经归档。
- 归档首轮比较因Windows反斜杠路径形式断言失败；只归一比较路径后94份原始文件SHA核对通过，没有改写驾驶记录。

## 命令与清单

```powershell
.venv/Scripts/python.exe tools/validate.py T0 --tests tests/test_overtake_run.py tests/test_overtake_session.py tests/test_overtake_ui.py --output logs/validation/SAFE-OVERTAKE-01-fixed-T0
.venv/Scripts/python.exe tools/validate.py T1 --tests tests/test_overtake_run.py tests/test_overtake_session.py tests/test_overtake_ui.py tests/test_highway_run.py tests/test_sprint_run.py tests/test_sprint_session.py tests/test_sprint_ui.py tests/test_mode_lifecycle.py tests/test_scene_lifecycle.py --output logs/validation/SAFE-OVERTAKE-01-T1
.venv/Scripts/python.exe tools/validate.py T1 --tests tests/test_overtake_ui.py --output logs/validation/SAFE-OVERTAKE-01-ui-fixed-T1
.venv/Scripts/python.exe tools/physics/run_sim_double.py tools/validate.py T1 --tests tests/test_overtake_run.py tests/test_overtake_session.py tests/test_overtake_ui.py tests/test_highway_run.py tests/test_sprint_run.py tests/test_sprint_session.py tests/test_sprint_ui.py tests/test_mode_lifecycle.py tests/test_scene_lifecycle.py --output logs/validation/SAFE-OVERTAKE-01-double-T1
.venv/Scripts/python.exe tools/overtake_check.py --output logs/validation/SAFE-OVERTAKE-01-normal-final
.venv/Scripts/python.exe tools/overtake_check.py --output logs/validation/SAFE-OVERTAKE-01-normal-unsafe --unsafe
.venv/Scripts/python.exe tools/physics/run_sim_double.py tools/overtake_check.py --output logs/validation/SAFE-OVERTAKE-01-double-planned --size 1024 768
.venv/Scripts/python.exe tools/physics/run_sim_double.py tools/overtake_check.py --output logs/validation/SAFE-OVERTAKE-01-double-unsafe --size 1024 768 --unsafe
.venv/Scripts/python.exe tools/overtake_check.py --output logs/validation/SAFE-OVERTAKE-01-normal-final --restore
.venv/Scripts/python.exe tools/physics/run_sim_double.py tools/overtake_check.py --output logs/validation/SAFE-OVERTAKE-01-double-planned --size 1024 768 --restore
```

相应目录加`--verify`复算保存记录。`archive-manifest.json`固定94份原始文件/48160819字节，`source-manifest.json`固定24份最终相关源码LF归一SHA。源码与SDK信息均包含未提交内容；提交后另核对Git对象，原T2失败、实时和人工Gate不在本次短验收中闭合。

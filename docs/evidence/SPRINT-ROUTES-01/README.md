# SPRINT-ROUTES-01

2026-10-19；基线main/d648d1f。新增固定道路短途赛事：平路连弯（seed17、curve、1800m、450m间隔4门）与山脊冲刺（seed0、hills、1400m、350m间隔4门）。复用既有道路形状和环境，车辆/辅助/物理模型/120Hz/碰撞/SDK/原生扩展不变；无车流是这两项赛事的明确条件。金银铜目标分别80/110/155秒、65/90/125秒；180秒内完成但未达铜牌仍保存有效最佳。

## 实际驾驶和保存

| SDK | 路线 | 有效时间/s | 逐拍数 | 碰撞 | 奖牌 |
|---|---|---:|---:|---:|---|
| Normal 32bit | 平路连弯 | 75.14218030228935 | 9018 | 0 | 金 |
| Normal 32bit | 山脊冲刺 | 59.37527428193858 | 7126 | 0 | 金 |
| Double 64bit | 平路连弯 | 75.14193691151378 | 9018 | 0 | 金 |
| Double 64bit | 山脊冲刺 | 59.375632979855 | 7126 | 0 | 金 |

每份`*.json.gz`保存实际120Hz完成步的位置/速度/朝向/道路原点/碰撞/事件/二值按键、原Controller请求和赛事结果。正常键盘控制器、原车速辅助与唯一Simulation执行驾驶，没有写回车身位姿。重试读取同一次完整最佳的四门时间；`sprint-best.json`按完整硬件/输入/路线/固定种子分组，使用原BestTimes事务写入。坏存储不冒充新最佳，原工坊/刹停/过门/滨海成绩不合并。

两个`recheck.json`各16144拍：从保存的真实世界位置/朝向重新投影同一道路，逐拍重算门序、车身余量、插值时间、奖牌与保存结果。它是规则复算，不重跑物理。两库各另起真正独立物理进程、通过实际菜单启动两条路线，恢复各自最佳和完整分段，保存文件字节保持；`restore-summary.json`明确没有新完整驾驶。

Normal 1280×720与Double 1024×768实际菜单、驾驶、结算和恢复图已查看。截图冻结真实完成步，只重置显示相机，不改变物理位置。门线读取真实道路中心/朝向/坡度，不生成碰撞；实际UI测试同时核对前后快照/刚体数保持。两路线同窗实验台往返由真实生命周期测试覆盖，不以此冒充人工鼠标操作或趣味性验收。

## 测试和失败记录

- `checks/rules-T0`：23过/1失败，测试样本漏了谷底，未改道路算法。补0/1000m采样后`core-T0` 27过。
- `checks/ui-T0`：16过/2失败；新增测试在倒计时未结束时读取规则、旧过门菜单仍断言7项。修正为完成倒计时再读、菜单8项；相关完整模块在后续T1闭合。原失败日志保留。
- `checks/T1`：8个完整相关模块46过（pytest73.92s），Ruff及0/17/23种子各1200步通过。`checks/double-T1`：同46过（57.86s）及三种子通过。前批未改生产物理的验证证据不重复跑；这不表示T2/T3通过。
- 截图发现8项高速菜单相邻按钮边界重叠，最终只将该页按钮半高.055改为.05。`layout-only.json`核对原/最终Application SHA与其余全文相同；全部其他root源码与真实驾驶版本相同。最终UI测试新增真实边界不相交断言，普通1过33.26s、Double1过28.77s，包含原两路线/门线/HUD/结算/同窗往返。两库独立恢复与最终菜单截图另在最终源码执行。T1和完整驾驶明确复用前版，未把补验说成重复新跑圈。
- `initial-probe/`保留6组先测记录，90/65/45km/h：平路约75.142/101.033/143.008秒，山脊约59.375/79.204/111.677秒，均无碰撞。但当时新增赛事源码触发首末一致性断言，未生成原summary，`audit.json`明确failed；从原始位置/时间复算只供初步定标，不作为最终版本通过。没有补造缺失的首末源码摘要。后续测量器会先写完整上下文再拒绝变化。
- `diagnostics/sprint-process-menu-original-2.log`实际复现独立进程返回菜单缺`race.scores`；补明确只读路径、复用权威`score_variant`后，同一脚本`fixed.log`无异常。新增真实进程测试和两库实际完整菜单/恢复覆盖这个修复，不创建第二物理世界。

## 命令

```powershell
.venv/Scripts/python.exe tools/sprint_route_probe.py --output logs/validation/SPRINT-ROUTES-01-probe --speeds 90 65 45
.venv/Scripts/python.exe tools/validate.py T1 --tests tests/test_sprint_run.py tests/test_sprint_session.py tests/test_sprint_ui.py tests/test_highway_run.py tests/test_slalom_ui.py tests/test_session_process.py tests/test_mode_lifecycle.py tests/test_session_clock.py --output logs/validation/SPRINT-ROUTES-01-T1
.venv/Scripts/python.exe tools/physics/run_sim_double.py tools/validate.py T1 --tests tests/test_sprint_run.py tests/test_sprint_session.py tests/test_sprint_ui.py tests/test_highway_run.py tests/test_slalom_ui.py tests/test_session_process.py tests/test_mode_lifecycle.py tests/test_session_clock.py --output logs/validation/SPRINT-ROUTES-01-double-T1
.venv/Scripts/python.exe tools/sprint_routes_check.py --output logs/validation/SPRINT-ROUTES-01-normal-drive --size 1280 720
.venv/Scripts/python.exe tools/physics/run_sim_double.py tools/sprint_routes_check.py --output logs/validation/SPRINT-ROUTES-01-double-drive --size 1024 768
.venv/Scripts/python.exe tools/validate.py T0 --tests tests/test_sprint_ui.py --output logs/validation/SPRINT-ROUTES-01-final-ui-T0
.venv/Scripts/python.exe tools/physics/run_sim_double.py tools/validate.py T0 --tests tests/test_sprint_ui.py --output logs/validation/SPRINT-ROUTES-01-final-double-ui-T0
.venv/Scripts/python.exe tools/sprint_routes_check.py --output logs/validation/SPRINT-ROUTES-01-normal-drive --size 1280 720 --restore
.venv/Scripts/python.exe tools/physics/run_sim_double.py tools/sprint_routes_check.py --output logs/validation/SPRINT-ROUTES-01-double-drive --size 1024 768 --restore
```

逐拍复算入口为`tools/sprint_routes_check.py --verify --output <记录文件夹>`，须先核对`source-manifest.json`中的规则/道路/配置依赖；未来源码变动不能沿用本版通过结论。`archive-manifest.json`固定90份原始文件26319887字节；`source-manifest.json`固定27源码的LF归一SHA，包括实际二值按键工具。源数据复制逐份SHA一致。

仅本地开发，无远端推送。原落地制动T2失败、实时与人工趣味性Gate保留；本批新增挑战可试玩，整体持续目标仍active。

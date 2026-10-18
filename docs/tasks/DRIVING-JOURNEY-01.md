# DRIVING-JOURNEY-01 短课题进阶目标

- 状态：done（自动功能完成，人工体验pending）；基线main/ee455b7，开始前干净；上轮逐门反馈完成，用户明确下一轮优先驾驶挑战与成长。前轮为progress。
- 目标：当前车的刹停/连续过门从独立成绩变成六档可见目标，按两项铜→两项银→两项金推荐下一课题，直接进入既有课题并在返回/重启后看到进度。
- 范围：独立固定“驾驶进阶”面板，从项目进度Tab/按钮进入，保留初章原5步和主菜单8入口；各课题显示现有最佳、铜银金达成、下一标准/差距，双金完成反馈。读取既有完整硬件/驾驶输入分组成绩，不增加第二份进度存储，不重复授奖/拼车分组。
- 导航：鼠标和键盘均可进/退/继续下一目标，两课题随时可选；旧高速/自由驾驶/专家实验保持开放。失败/写入失败只按已保存成绩计入；坏文件提示且另一项可继续，虚拟试车不计入成长。
- 禁止：改物理/硬件/输入辅助/120Hz/原门位/奖牌标准/SDK，奖励不改车辆性能，不推送、不新增通用页面框架。
- 验证：先纯数据目标/边界/分组/损坏与UI相关T0，再相关T1/三种子；两库新实际键盘从进阶进入课题→成功→返回/独立重启读回，宽屏/4:3图；错误/分级边界可用明确夹具，已有效物理证据不重复扩跑。人工趣味性和原T2/实时Gate开放。

## 实现与结果

- 独立固定驾驶进阶面板，从初章右上按钮或已注册Tab进入；方向键/WASD/Enter、Tab回初章、Esc回菜单。两项已有铜/银/金目标共6档，推荐档位较低者；单项直接金牌可补另一项铜牌，双金显示完成，可继续刷新。卡片显示最佳、已达标准与下一档差距，不更改原规则。
- 只读取原BrakingScores/SlalomScores的当前完整硬件SHA/驾驶输入分组；没有成长文件或第二套分数。旧总用时兼容、逐门详情坏而总成绩好仍计入；某课题坏文件只影响该项并提示。分组切换/恢复不改写其他组，未保存/失败/虚拟试车不增加成长。初章原5步/主菜单8入口保持。
- 从进阶打开课题后，结算第三按钮变为“查看驾驶进阶”，直接读回已保存成果；旧入口仍为返回主菜单，重试/同窗实验台往返保留明确进阶意图，取消说明页或进入其他模式清除。初章与进阶打开时F2不在后面打开配置页，避免界面仍显示旧分组。
- 普通1280×720、Double1024×768各新实际KeyboardController两课题：刹停1986拍、−0.8798828125 / −0.8799031984530927m金牌；过门2585拍、14.214632943560819 / 14.214750521562149s金牌。按真实成功记录显示0→3→6，零碰撞、配置保持；两库再各独立启动进程只读恢复6/6，原成绩字节保持。真实图/重启图已查看，不是人工驾驶/趣味性验收。
- 两库9142个保存完成步全字段规则复算、两份原成绩、0→3→6派生数据和独立重启结果一致；复算不重跑物理。首次复核工具在普通刹停第1443条误用带符号player.speed作停稳速度，已按Session实际接口改用hypot(vx,vy)并完整重算通过；产品规则未改，真实短暂负向速度保留。
- 普通纯数据T0 10项；新UI6项+初章原UI7项共13项通过（89.92s），Double纯数据+新UI16项通过（35.60s）。最后新增F2模态与同窗返回两个边界，每库各1+1项通过；这是补验，不称整个新UI7项全部重跑。失败显示/差距/旧奖牌与分级边界采用明确成绩/结算夹具，与真实物理分开。
- 相关T1首批37项：34过/3失败（160.39s）；两份旧测试还断言7入口/“无限高速”，用git show基线ee455b7确认实际8入口/“高速与驾驶课题”已存在。更新这两处旧断言后完整两模块8项通过（37.26s），0/17/23各1200步启动通过；未重复首批其余通过模块，按两批闭合，不称最终37项整套重跑。Ruff通过。
- 真实驾驶/重启先于最后F2守卫：两库源码/SDK首末一致，原application.py与最后仅导航守卫的差异均归档，物理/其他根源码逐项SHA相同；最后导航守卫两库补验通过，布局未变，不重跑物理。最终仅渲染另查看两分辨率初章进阶按钮，未跑课题；60份原样输出/6.37MB及10项最终施工源码指纹见[证据](../evidence/DRIVING-JOURNEY-01/README.md)。
- 物理/默认参数/辅助/原课题标准/120Hz/SDK与原生模块未改，未添加性能奖励；本批T2/T3未跑，原精度失败、实时与人工Gate开放，持续目标active，无推送。

## 命令

```powershell
.venv/Scripts/python.exe tools/validate.py T0 --tests tests/test_driving_journey.py --output logs/validation/DRIVING-JOURNEY-01-core
.venv/Scripts/python.exe tools/validate.py T0 --tests tests/test_driving_journey_ui.py tests/test_workshop_journey_ui.py --output logs/validation/DRIVING-JOURNEY-01-ui
.venv/Scripts/python.exe tools/validate.py T1 --tests tests/test_driving_journey.py tests/test_braking_lesson_ui.py tests/test_slalom_ui.py tests/test_results_keyboard.py tests/test_ui.py tests/test_mode_lifecycle.py tests/test_workspace_transition.py tests/test_driving_mode_ui.py --output logs/validation/DRIVING-JOURNEY-01-T1
.venv/Scripts/python.exe tools/validate.py T1 --tests tests/test_ui.py tests/test_driving_mode_ui.py --output logs/validation/DRIVING-JOURNEY-01-T1-repair
.venv/Scripts/python.exe tools/driving_journey_check.py --output logs/validation/DRIVING-JOURNEY-01-normal-drive --size 1280 720
.venv/Scripts/python.exe tools/physics/run_sim_double.py tools/driving_journey_check.py --output logs/validation/DRIVING-JOURNEY-01-double-drive --size 1024 768
.venv/Scripts/python.exe tools/driving_journey_check.py --output logs/validation/DRIVING-JOURNEY-01-normal-drive --size 1280 720 --restore
.venv/Scripts/python.exe tools/physics/run_sim_double.py tools/driving_journey_check.py --output logs/validation/DRIVING-JOURNEY-01-double-drive --size 1024 768 --restore
.venv/Scripts/python.exe docs/evidence/DRIVING-JOURNEY-01/recheck.py --evidence
```

输出目录应换新名；--restore使用此前同一目录，完整Double与最后边界命令见checks各summary.json。下一步补实际驾驶内容：测量滨海计时目标，为已有分段/幽灵提供铜银金挑战与明确重试目标，再结合用户体验调整趣味性，不继续堆叠成长菜单。

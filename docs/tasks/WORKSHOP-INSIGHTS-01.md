# WORKSHOP-INSIGHTS-01 工坊试验解读

- 状态：done（自动功能与渲染，人工体验待确认）；基线main/855b99a1，开始前工作区干净。上一轮HILL-TRAFFIC/ENV-SIGN-CLEARANCE完成真实功能/验证/本地提交，为progress；持续目标active。
- 目标：两道现有工坊在完成A/B后回答改了什么、收益多少、观察到哪些代价、下一次如何验证；失败/超预算也可解读和导出。依据原始快照，不能凭改装名称预填原因。
- 范围：同条件/连续完成步检查、真实ABS介入/侧偏/侧倾等描述、单项/组合边界、失败后的单项B建议与准备动作；工坊面板、只读解读、导出与同窗/已保存方案恢复。只改当前B一个选项，A仍为固定原车，须重跑才有新成绩。
- 禁止：改物理/默认配置/120Hz/原评分/奖牌/预算/旧记录，或把观察说成未验证的独立因果；不自动运行/应用新方案，不把路面μ作为改装。无推送/发布。
- 验收：真实A/B的原配失败/金牌/超预算、操稳侧偏失败与可行方案；篡改摘要/CSV、跨条件、未完成/坏记录边界；准备一次只改B一项/旧结果失效但曲线保留、取消/重开/保存失败、真实两库面板与导出、相关T0/T1及三种子。原物理/实时/人工Gate独立开放。
- 已完成的有效物理记录可明确复用；新界面/分析直接读原记录，不为报告重复广测。

## 实现与证据

- 两题新增“试验解读”：真实A/B主指标、预算、ABS轴介入/峰值横摆或侧偏/侧倾/车速/实际转角；单项改动与组合结果分别解释。失败可导出完整A/B及insights.json/txt/HTML，达标保存车辆时同时保留解读。
- 下一步一次只准备当前B一个选项，固定原车A不变；旧结果立即失效、原始曲线保留，不自动运行或应用车辆。Esc先关闭解读；同窗状态恢复、保存方案重新载回及文件失败边界已纳入相关测试。
- 制动从连续120Hz原始快照复算三维距离/峰值横摆，核对初速/停稳/摘要与全制动请求；ABS排除初始拍，以完成拍某轴至少一轮介入的比例表示，旧快照未定义留空。操稳复用既有原始快照指标与固定驾驶员协议，原评分保持。
- 两库各新短测原配/70%+大制动器/原配定圆/70k定圆，共3006拍；两库共6012新拍。制动组合32.406→24.445m、改善约24.57%但预算4/3；70k循迹约3.175→0.153m，峰值侧偏约5.79°且车速超限；均不获奖。两库原制动/50k操稳金牌A/B明确复用旧完整记录，非新物理或人工驾驶。
- Normal1280×720、Double1024×768各5种解读及3种单项准备画面，实际字体/边界/按钮均已查看；捕获期间冻结UI更新，不声称实时性能或人工趣味性通过。
- 首T0命令误将--tests重复，只执行末模块4项并通过，作为局部证据；修正为单参数文件列表后完整相关T0 57项通过。最终Normal/Double相关完整T1各112项及各0/17/23三种子通过。会话中断后旧轮询句柄已释放，读取完整passed终态核实，未重复启动验证。
- [证据包](../evidence/WORKSHOP-INSIGHTS-01/README.md)固定98份原始/压缩文件、51967677字节与12份源码LF SHA。物理/旧评分/参数/SDK保持；仅本地成果，无推送。提交范围为新解读计算/面板、原工坊/退出集成、4个相关测试模块、诊断工具、任务/进度与本包证据。后续优先继续完善实际驾驶挑战的决策和反馈；原T2/实时/人工Gate独立开放。

命令（输出目录须新建）：

```powershell
.venv/Scripts/python.exe tools/validate.py T0 --tests tests/test_workshop.py tests/test_cornering_workshop.py tests/test_workshop_ui.py tests/test_cornering_workshop_ui.py --output logs/validation/workshop-insights-full-t0
.venv/Scripts/python.exe tools/workshop_insights_check.py --output logs/validation/WORKSHOP-INSIGHTS-01-normal --braking logs/DESIGN-CHALLENGE-01/normal/records/20261018-032538-729436-workshop --cornering logs/DESIGN-CHALLENGE-02/normal-ui/reports/20261018-071436-480996-workshop
.venv/Scripts/python.exe tools/physics/run_sim_double.py tools/workshop_insights_check.py --output logs/validation/WORKSHOP-INSIGHTS-01-double --size 1024 768 --braking logs/DESIGN-CHALLENGE-01/double/records/20261018-032808-310603-workshop --cornering logs/DESIGN-CHALLENGE-02/double-ui/reports/20261018-071435-005591-workshop
.venv/Scripts/python.exe tools/validate.py T1 --tests tests/test_workshop.py tests/test_cornering_workshop.py tests/test_workshop_ui.py tests/test_cornering_workshop_ui.py tests/test_lab_ui.py tests/test_lab_records.py tests/test_workspace_transition.py tests/test_workshop_journey_ui.py --output logs/validation/WORKSHOP-INSIGHTS-01-T1
.venv/Scripts/python.exe tools/physics/run_sim_double.py tools/validate.py T1 --tests tests/test_workshop.py tests/test_cornering_workshop.py tests/test_workshop_ui.py tests/test_cornering_workshop_ui.py tests/test_lab_ui.py tests/test_lab_records.py tests/test_workspace_transition.py tests/test_workshop_journey_ui.py --output logs/validation/WORKSHOP-INSIGHTS-01-double-T1
```

原T2物理失败、实时与人工Gate继续开放；本批不重跑T2/T3，不推送。

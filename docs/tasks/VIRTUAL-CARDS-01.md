# VIRTUAL-CARDS-01 虚拟试车结果概览

- 状态：done（自动部分，人工体验待确认）；基线main/5c143bd4，开始时工作区干净。继续用户选择的界面/正常功能方向，不重接ABS候选。
- 缺口：结果依赖四列长文字，A完成/B运行或只有A时缺少可见结果；新一轮仍可能显示上一轮“报告已保存”。
- 范围：virtual_driver.py双方案状态/进度、真实轨迹概览、逐项A/B指标；A先结束即可查看，不外推失败/中断轨迹，无B不生成差值。正常重新运行重置报告提示；保留原试车、规则、源记录、报告、复盘和同窗驾驶链路。只同步依赖该面板的工具/测试，不改物理或策略。
- 验证：相关短T0和原UI模块T1；两画幅实际完整/只有A/重新运行图。静态结果复用原真实道路记录；重开只检查真实起步初始化，不重跑旧完整道路。正常完整试车由原相关测试覆盖，不追加边界矩阵。

## 实现与验收

- A/B改为独立方案状态卡，显示完成/未完成、通过门数/有效用时、已行道路位置与进度。A结束后即显示其指标及轨迹，B运行时保持可读；没有B不造差值。原模型、控制策略、课题规则、积分、存档/报告格式、玩家成绩及驾驶回调保持。
- 左侧实际轨迹概览按原完整记录抽点，保留真实末点，失败轨迹不外推；灰线为目标，竖线为门位，明确横向范围及0–320m道路进度。完整逐拍记录仍供复盘/报告使用。右侧六项指标对齐A/B/B−A，缺有效用时显示未完成，待运行显示待完成；不可比仍由原判定抑制差值。
- 轨迹几何只在记录数变化/结束/恢复时刷新；运行中的状态/道路位置只读当前完成步，未为绘图推进第二世界。正常重开重置报告提示、旧指标/轨迹与按钮状态。弹层覆盖到方案库底边，避免露出后面按钮。新增固定文字对象引用，修复首版实图标题/关闭字形消失。
- 首次单文件Ruff为导入排序失败，修正后正式T0 `tools/validate.py T0 --tests tests/test_virtual_driver_ui.py::test_actual_road_comparison_preserves_trial_draft_and_player_progress tests/test_virtual_driver_ui.py::test_review_single_partial_and_broken_gate_records_are_explicit --output logs/validation/VIRTUAL-CARDS-01-T0`：Ruff/2项通过，42.5秒。真实完整A/B检查A先显示、B仍运行；结束后重开提示清零；归档记录检查失败轨迹末点与单侧无差值。部分记录旧UI夹具同步为0门，不保留其原完整记录的3门指标。
- `tools/validate.py T1 --tests tests/test_virtual_driver_ui.py tests/test_scheme_slalom.py::test_explicit_b_slalom_overrides_workshop_and_preserves_reference_and_review --output logs/validation/VIRTUAL-CARDS-01-T1`：Ruff/9项/seed0、17、23各1200步通过，pytest检查76.4秒（pytest自身74.67秒）。包含原UI模块完整8项与正常同窗B过门/返回复盘链路；不扩大边界矩阵或运行完整物理Gate。
- 交互中断后原T1进程已结束，检查原summary终态passed后复用，没有重新启动。其后仅增加目标线/横向范围图例和道路位置数字，最终Ruff及1280×720/1024×768各3张实图通过，已查看；行为T1明确复用。实际像素区检查标题/关闭字形每图存在。
- 静态完整/仅A图复用VIRTUAL-DRIVER-01普通库4800拍真实35k/50k记录；仅A为明确只载入原A的展示状态，不伪称新取消物理。重新运行图使用已保存45k/50k方案，每次只实际132步起步初始化、道路驾驶0拍即关闭；T0/T1原测试内的短/完整试车实际新跑，分别记账。原试验/基线/驾驶车与复载快照保持。
- 原版、首版缺字图、最终两画幅、T0/T1及4份最终源码SHA在`docs/evidence/VIRTUAL-CARDS-01`。仅本地，不推送；原ABS数值精度、实时及全阶段人工Gate仍独立保留。

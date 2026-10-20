# RESULT-TUNING-01 结算后直接改装重试

- 状态：done（本功能自动验收分批完成，人工体验待确认）；基线main/825b3e68，开始前干净。上一实验台载入驾驶车为progress，持续目标active。本地无推送/发布。
- 功能/证据本地提交`ff9c0d0e`；91份原始文件和4源码指纹逐项核对索引/工作区，提交后干净；提交号由后续文档提交登记。
- 目标：普通/高速过门结算直接打开现有前胎面板；取消/预览/写失败仍回原结算。安装或恢复保存成功后才离开结束的驾驶会话，准备同一道题并用新车重试，旧成绩/方案继续独立。
- 范围：Application的结算入口、结果态模态键盘、保存成功的菜单交接、四按钮排版及相关测试/两库真实驾驶和截图。复用原配方/原车副本/恢复、原课题/成绩/默认车/物理/SDK；不允许在驾驶中改装或改变物理状态。
- 完整原结算在未安装时保持，包含HighwayResult/原snapshot/成绩文件字节；保存失败保留结果和配方预览。相同配方也不清除原结算。真改装成功后明确“返回同题重试”，不把旧结果显示成新车成绩。原实验台与主菜单按钮保持，原驾驶进阶返回语义保持。
- 验证：真实菜单/结果规则夹具覆盖成功失败、取消/相同配方/坏副本/写失败、结果键盘/原进阶/同题参数；Normal/Double新实际35k漏门→结果配方面板70k→同题金牌，每拍原规则复核/成绩文件/副本/模型保持，宽屏4:3；相关T0/T1与三种子。旧参考试验/独立恢复证据明确复用，不重复跑。原T2物理失败/实时/人工Gate开放。

## 已实现与实际验证

- 过门结算第4按钮“改装前胎再试”，原重试/实验台/主菜单或进阶按钮保持，结果页两列排列。结果态配方面板拥有键盘输入，旧逐门表在面板打开时隐藏，取消重新显示。
- 无改动/同配方保留原`HighwayResult`对象和物理Snapshot；保存成功且车辆确实变化后，才调用原`Session.menu()`结束旧车结果并通过原菜单接口应用硬件，准备同一普通/高速题。原驾驶进阶返回意图保持；没有在驾驶中改装或改写物理位姿。
- 安装/恢复失败保留结果、原车与预览；缺失原车副本明确失败。持久化、内容SHA副本、成绩分组、电子开关/输入及其他硬件沿用TIRE-TUNING-01，无新存档格式。原成绩不从旧车结算迁给新车。

两库各新真实35k失败→失败结算打开面板→取消回原结果（Snapshot/结果对象相同）→再次打开并安装70k→同一高速题实际完成。全程同窗、原75km/h二值KeyboardController策略、原物理/规则/辅助/SDK保持。

| SDK | 35k | 70k | 新驾驶记录拍 |
| --- | --- | --- | --- |
| Normal | 1587拍，第3门失败 | 2272拍，11.402889秒金 | 3859 |
| Double | 1587拍，第3门失败 | 2272拍，11.402890秒金 | 3859 |

- 合计7718新实际驾驶记录拍，各段原始请求/快照位置速度/逐门结果用原纯规则逐拍复核一致；原方案库16份输入与旧归档解压字节一致，运行前后保持。`tools/tire_tuning_check.py --from-results`显式测试新入口，原不加参数流程继续保留。
- 完整驾驶后先补下沿留白，再由旧保存失败提示场景发现表格与按钮间距不足：表格下沿−.576831，原按钮上沿−.557，真实重叠约.020。只把第一排按钮移到−.67、第二排−.80、面板下沿−.92；不放宽旧布局断言。修前源文件/SHA/中间版/最终差异在`before-display`保留。完整驾驶明确复用，最终两库完整相关布局模块T1另跑；主批失败如实保留。
- `normal-preview/double-preview`为第一次留白版；`normal-final-preview/double-final-preview`为最终布局，成功结果另加显式“未保存”文字夹具覆盖回归场景。使用新原始驾驶结果构造显示快照，背景为当前初始化场景；不回放车辆轨迹、不冒充第二次驾驶或真实文件写失败。已查看宽屏/4:3成功/失败与最终长提示图；完整驾驶根目录PNG是排版修正前现场图。
- 旧独立物理进程恢复、原子文件写入、旧A/B定圆与加载当前驾驶车分别复用TIRE-TUNING-01/LAB-DRIVING-CAR-01既有证据，本批不把它们记作新跑。

## 命令与验收

- T0：`tools/validate.py T0 --tests tests/test_result_tuning.py tests/test_slalom_ui.py tests/test_fast_slalom_ui.py --output logs/validation/RESULT-TUNING-01-T0`，Ruff/13项通过；此批采集后新增缺副本参数分支，纳入后续T1/最终T0。
- 新完整流程：`.venv/Scripts/python.exe tools/tire_tuning_check.py --output logs/validation/RESULT-TUNING-01-normal --from-results`；Double用`tools/physics/run_sim_double.py tools/tire_tuning_check.py --output logs/validation/RESULT-TUNING-01-double --size 1024 768 --from-results`。两库passed，首末源码/SDK一致。
- 主批T1：`tools/validate.py T1 --tests tests/test_result_tuning.py tests/test_tire_tuning_ui.py tests/test_fast_slalom_ui.py tests/test_slalom_ui.py tests/test_slalom_feedback_ui.py tests/test_scheme_slalom.py tests/test_driving_journey_ui.py tests/test_workspace_transition.py tests/test_mode_lifecycle.py`，Double同一范围经原启动器。两库各45过/1旧长提示布局失败，pytest661.04/581.65秒；各后续三种子未跑，不冒充主批通过。最终布局修复按下条两库完整相关模块另验，未改动的其他模块明确复用其已通过结果，不重复跑全批。
- 第一次留白补丁后T0：`--tests tests/test_result_tuning.py --output logs/validation/RESULT-TUNING-01-final-T0`，Ruff/8项通过，但未覆盖旧保存失败提示排版；专项`--tests tests/test_slalom_feedback_ui.py --output logs/validation/RESULT-TUNING-01-layout-repro-T0`为2过/1同原因失败。修复最终间距后，两库`T1 --tests tests/test_result_tuning.py tests/test_slalom_feedback_ui.py tests/test_fast_slalom_ui.py`完整重验，各13项/Ruff及seed0/17/23通过，pytest215.69/222.15秒。最终仅显示布局修正，已通过的其他模块和实际驾驶明确复用。
- 归档`docs/evidence/RESULT-TUNING-01`共91份原始文件、12,103,858字节及最终4源码LF SHA，包含原始失败输出、旧显示源/最终差异、最终长提示图。机械模块/物理参数/课题阈值保持，T2/T3未跑；原物理T2失败、实时性能与人工趣味性Gate仍开放，持续目标active，仅本地无推送。

下一优先把改装前后的道路表现并排呈现，直接比较完整一次的完成情况/用时/门余量，与实验台取舍保持各自口径；可按用户新反馈调整。

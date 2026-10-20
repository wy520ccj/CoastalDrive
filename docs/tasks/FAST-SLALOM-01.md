# FAST-SLALOM-01 高速验车过门

- 状态：done（自动功能完成，人工体验待确认）；基线main/27cef362，开始前干净。上批巡回为progress；持续目标active，仅本地，无推送。
- 功能/证据本地提交`1e309482`；提交后工作区干净。138份原始文件共15,643,158字节和12源码LF SHA已逐份核对Git索引与工作区，提交号由后续文档提交登记。
- 用户方向：让不同改装更影响挑战表现。先测量再定题，不改变已认可默认车/输入辅助或旧课题。
- 前测：原真实KeyboardController、同一SlalomDriver策略、原参考工坊前胎35/45/50/70k、其他选项不改。目标60km/h四车均6门金；目标75时35k第3门失败、45/50k第4门失败、70k6门11.402889秒。原始源/SDK/请求/快照在logs/validation/MOD-ROAD-01-probe与probe75；不是人工驾驶，不推导刚度越大越好。
- 功能：原“连续过门”说明页可切换“高速验车”；同一六门/原4m宽/原车身包络，新入口≥70km/h，80–320m全段70–80km/h，金≤11.5/银≤12.5/铜≤14s；40秒总上限。提前减到普通练习车速不能过题，碰撞/复位/越界/逆向仍按原课题失败。独立成绩键，旧普通40入口/15、18、24秒与驾驶进阶保持。
- 改装：沿用当前完整硬件、路面、电子开关和输入；可以返回原实验台改/保存方案，再回同一高速题。展示全段速度/违规点、逐门余量/最佳；不自动改装，不给虚拟成绩，不把本题当滨海工程验证。
- 允许：GameMode新增明确课题值；SlalomLesson与快照增加高速题状态，Session/HighwayRun选择；原门线标签/HUD/说明/结算/实验台返回识别；工具与相关测试/证据/文档。直接固定题目，无新框架或第二物理世界。
- 禁止：物理/默认调校/原辅助/SDK/NPC/旧门位门宽或阈值；用路面μ伪装轮胎改装；瞬移/关碰撞/虚构成绩；更换试车策略迎合成绩。
- 验收：连续速度带边界插值/跳过整带/低速/超速/倒退、旧规则回放旧字段保持；独立最佳/原子写失败沿用并测分组；正常/Double真实同条件35k失败、70k成功，至少再测一种中间配方与同车普通练习保持，所有原始轨迹纯规则复核。主菜单/键盘切换/同窗实验台返回/独立进程重启、宽屏/4:3图像；相关T0/T1与三种子，原T2失败/实时/人工Gate开放。

## 实现与实际结果

- `GameMode.FAST_SLALOM`明确选择新课题；原`SlalomLesson`只在fast时检查入口至终点的道路前向速度带，相邻完成步跨边界插值，停住/倒退不能绕过，全段低速/超速在下一门前即失败。原六门车身俯视判定、原普通练习及默认硬件/输入/物理均保留。
- `SlalomResult`增加题目标记、速度极值及违规位置，供原门线入口标签、HUD、结算和独立会话回传读取。新`fast-slalom-v1:`键与完整硬件/输入分组，原`slalom-v1:`及驾驶进阶保持。菜单从原连续过门说明页切换，新题不增加主菜单入口。
- 实验台返回保留普通/高速题目；只编辑草稿不替换车，完成参考试验后原“保存并试驾”才应用配置。显式“驾驶B连续过门”和工坊滨海验证保持各自原意图。

两库通过真实同窗“35k失败→进实验台导入50k/短参考试验/保存→原题失败→导入70k/试验/保存→原题成功”，使用原二值键盘与同一个75km/h策略；只前胎刚度改变，μ=1.1、电子开关和其他硬件保持。

| SDK | 35k | 50k | 70k | 新课题记录拍 |
| --- | --- | --- | --- | --- |
| Normal | 1587拍，第3门失败 | 1817拍，第4门失败 | 2272拍，11.402889秒金 | 5676 |
| Double | 1587拍，第3门失败 | 1817拍，第4门失败 | 2272拍，11.402889秒金 | 5676 |

- 两库各站逐拍纯规则复核一致，70k全带道路前向速度约74.663–77.543km/h；重试恢复同一完整最佳/逐门参考，窗口保持。两次短参考试验每库各12拍另计，不混入驾驶拍。
- 前测Normal四车60/75km/h合计18043拍；四车60全部金，75的35/45/50漏门而70完成。当前普通规则重放这些记录，所有旧字段精确保持；是本轮前测的重放，不是再次运行物理。新题11352拍加前测18043拍共29395新驾驶记录拍，不能当人工体验或实时性能验收。
- 70k在本高速策略下过关，不意味着所有工况更好。旧`WORKSHOP-INSIGHTS-01`真实定圆报告（本批只读引用）记录70k峰值侧偏约5.79°及末窗速度超限，原工坊仍不获奖；未重跑旧定圆或降低原标准。
- 完整驾驶后的生产改动仅两处倒计时空结果提示，补fast参数，规则/请求不变；保留`before-final-display`两旧文件及差异，完整驾驶明确复用。最终双库另验倒计时实际HUD。Normal宽屏与Double4:3实际成功/失败/说明/倒计时图已查看；前两版布局工具旧图保留，不用作最终HUD证据。
- 最终两库实际独立`SessionProcess`读取70k原完整最佳/六门参考，文件字节保持、首末源码/SDK一致；该检查没有新完整驾驶。

## 验证与工具修正

- T0：`.venv/Scripts/python.exe tools/validate.py T0 --tests tests/test_fast_slalom.py tests/test_fast_slalom_ui.py tests/test_slalom_lesson.py tests/test_slalom_ui.py --output logs/validation/FAST-SLALOM-01-T0`，Ruff和44项通过。最终另补倒计时空结果提示测试，纳入T1。
- 实际驾驶：`tools/fast_slalom_check.py --output logs/validation/FAST-SLALOM-01-normal-fixed`；Double用`tools/physics/run_sim_double.py tools/fast_slalom_check.py --output logs/validation/FAST-SLALOM-01-double --size 1024 768`。独立恢复对应命令追加`--restore`。
- 最终T1：`tools/validate.py T1 --tests tests/test_fast_slalom.py tests/test_fast_slalom_ui.py tests/test_slalom_lesson.py tests/test_slalom_session.py tests/test_slalom_ui.py tests/test_slalom_feedback.py tests/test_slalom_process.py tests/test_scheme_slalom.py tests/test_workspace_transition.py tests/test_mode_lifecycle.py tests/test_highway_run.py tests/test_driving_journey.py tests/test_driving_tour_ui.py`；Double同一范围经原启动器。两库Ruff、各111项与各seed0/17/23短测全部通过；pytest分别372.88/335.94秒。
- 工具先前失败保留：前测首次model_fingerprint导入位置错误，未执行物理；初次smoke漏回菜单导致按钮command为None；独立恢复先缺明确driving_mode，后误传非独立时钟，均未验证恢复，修正工具后通过，未改生产契约。首次布局工具漏refresh_panel、第二次漏右上按钮resize，旧图不作最终验收；最终工具调用原布局API后重新捕获。
- 完整驾驶工具误把已经为度的侧偏再做degrees；原gzip/summary字节保留，`corrected-metrics.json`仅按单位反换算，后续工具已修正。侧偏/侧倾截止各自失败或终点，窗口长短不同，不据此比较整程收益。完整驾驶时工具源码已按两库当时SHA恢复为`before-final-display/full-drive-tool.py`；与最终工具的差异不影响已记录物理/规则/键盘请求。
- 归档位置`docs/evidence/FAST-SLALOM-01`，138份原始文件与最终12源码LF SHA已归档；来源/字节数/原始SHA见`archive-manifest.json`，包括原始失败输出与人工记录的工具错误说明。原机械模块SHA保持`c84bfb06cae9d51a46f5cdff69107f96e73c6757d2853ef46673d0710010e7a2`；T2/T3未跑，原物理失败、实时与人工Gate保持开放。

下一块继续改装对挑战的作用：保留本题已验证的差异，优先把可驾驶的配方选择与试验代价摆在一起，减少来回找参数；制动收益与原驾控手感仍按实测分别处理。

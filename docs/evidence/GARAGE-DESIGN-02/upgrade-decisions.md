# 改装对照、安装状态与试车衔接

2026-10-23；基线`f4288276`，单线本地施工。上个回合完成BRZ法线与正式资源提交，属于progress；本轮接续用户优先菜单排版/控件/流程，持续目标仍active、任务包in_progress。

## 设计和真实行为

- 实际打开并查看William Emery的[FH5 Garage UI](https://williamemery.artstation.com/projects/lD1oL5)作品页、改装分类及完整调校表截图，学习分类/数据/解释/操作栏分区；没有把第三方截图重新分发成项目资产。
- 内置ImageGen先生成[18购买前](../../design/garage-v2/18-upgrade-compare.png)及[提示词](../../design/garage-v2/18-upgrade-compare-prompt.txt)，再编辑为[19安装后](../../design/garage-v2/19-upgrade-installed.png)及[提示词](../../design/garage-v2/19-upgrade-installed-prompt.txt)。初版生成底部偏挤，做一次间距修订，原候选在logs。最终原生坐标冻结在`layout-contract.md`，保持主按钮y711与其他车库页一致，未跟随生成候选移到页尾；生成车身美化不替换真实车模。
- 四分类→零件图/名称/作用/价格→同一两列对照→主操作→恢复，全部在原左面板内。轮胎/制动按安装函数实际配方读取，动力/悬架沿用实际升级函数；当前值只读当前车辆。数字和单位对齐，不硬填70或凭空生成性能评级。
- 已安装显示当前配置与应用状态，主操作改为进入对应真实简报：轮胎绕桩、制动停车、动力沿海冲刺、悬架山脊；未解锁时明确显示海岸初驶，不擅自解锁。进入简报停用车辆展示且不自动起跑；再确认才由原应用逻辑创建正式驾驶。
- 原车已有同样设定标“无需更换 / 当前已是该设定”。GR86原车70%即使全局零件已在其他车购买，也不误报为这辆车新安装。已购未装可免费安装；锁定/积分不足保持原阻止动作，价格/扣费/存档/恢复规则不变。
- 无原车副本时恢复按钮禁用，安装后出现副本才可用；沿用已有键盘跳过禁用动作，不再让玩家点到没有副本的恢复操作。
- 通知固定在面板与底栏之间的深色条；超长单行用省略号标示，完整原始notice保持原业务对象中。不让安装/文件错误提示白字叠在亮地板上。UI只保存控件引用，切页清理；没有新车辆状态、页面框架或物理世界。

## 验证范围

- 新28项跨七车/四零件，预览不写当前文件，读数与实际安装/保存后的完整配置比较，覆盖GR86不同前胎初值与库存制动设定。另验证实际购买→简报→恢复→免费重装→简报→正式试车启动，以及全局拥有/未拥有的GR86原设定。
- 首T0 30项通过；补全跨车拥有情况T0 2项通过。相关完整T1 **89项及0/17/23各1200步通过**；末次只改通知深底/单行省略，文件失败免费重试针对性T0 1项通过；随后恢复动作按副本有无禁用，针对性3项T0通过。最后只给采集夹具补保存检查，Ruff单独通过。没有宣称全部89项在最后提示/恢复细节之后重跑。
- T1完整模块：`test_garage_readouts / test_career_ui / test_career_tuning / test_career_garage / test_ui_theme / test_validation_runner`。`gameplay`映射补入新读数测试。测试中的真实试车启动与三种子物理短测独立于下方静态采集；不以简报截图证明完整赛事。
- 原始验证摘要、日志压缩字节、最终图与源码/保持文件SHA在`upgrade-decisions/`归档；源logs前缀`GARAGE-DESIGN-02-upgrade-*`。没有T2/T3、完整驾驶、正式性能或人工审美/趣味性验收。

## 最终采集

```text
.venv/Scripts/python.exe tools/garage_upgrade_check.py --output logs/validation/GARAGE-DESIGN-02-upgrade-final-1280 --size 1280 720
.venv/Scripts/python.exe tools/garage_upgrade_check.py --output logs/validation/GARAGE-DESIGN-02-upgrade-confirmed-1024 --size 1024 768
```

同一正常键盘购买/导航流程，两画幅各15张实际原生页；18星和奖励为隔离显示夹具，0新增驾驶拍，Snapshot逐截图保持。四项购买2460→1010积分，恢复不退款、已购重装不再扣费；GR86原设定直接进入停车简报，仍1010积分。读数/动作/信用余额在summary逐项记录。归档分别核对原始隔离进度文件的18星/2460初值/1010余额，选存宽屏12张与4:3六张，共18张原图。已重点查看两画幅轮胎购买前/安装后、GR86原制动、动力/悬架对照与试车简报；指标未覆盖主按钮或车辆区。

`manifest.json`记录最终六项源码、四个设计/提示文件、18张图的SHA，以及23项业务/物理/模型/光照/零件素材相对基线保持。完整T1与最后T0日志均压缩原字节归档。同一用例多批次有重叠，89项不是与T0相加的不同用例总数。

具体验证命令均使用`.venv/Scripts/python.exe tools/validate.py`：T1为`T1 --tests tests/test_garage_readouts.py tests/test_career_ui.py tests/test_career_tuning.py tests/test_career_garage.py tests/test_ui_theme.py tests/test_validation_runner.py --output logs/validation/GARAGE-DESIGN-02-upgrade-compare-T1`；末次T0为`T0 --tests tests/test_career_ui.py::test_upgrade_comparison_purchase_restore_free_reinstall_and_trial_start tests/test_career_ui.py::test_stock_gr86_brake_setting_is_not_reported_as_a_purchased_part --output logs/validation/GARAGE-DESIGN-02-upgrade-restore-final-T0`。其余T0完整命令在各归档摘要中。

## 排除的不完整夹具

末次`upgrade-final-1024`原采集脚本报告passed，但人工核对顶部发现只有15星。原始隔离进度缺少ridge-run，初始积分2010而非2460；此前循环快速记录奖励没有检查保存返回，未留下导致该次缺记录的具体错误，因此根因不冒称已确认。该批15图不列为最终证据，原摘要与排除审计保留在`rejected-fixture-*`。

采集工具改为显式一次保存完整18星显示夹具、断言保存成功及初始星级；新目录`upgrade-confirmed-1024`核对通过，再采正常购买/导航和最终图。宽屏原目录的记录/星级/余额均核对正确，因此保留而未重复跑。未更改生产领奖/保存逻辑，不把显示夹具当实际完赛。

早期`upgrade-compare-first`四静态候选及`upgrade-flow-1280`15图在末次通知条样式之前，保留作候选，不当最终交付图。原模型、材质、灯光、道路相机、配置、权威物理、成长阈值及旧完整驾驶结果保持。精细光照/道路画面与用户实际体验仍待继续处理；本块仅本地，无推送。

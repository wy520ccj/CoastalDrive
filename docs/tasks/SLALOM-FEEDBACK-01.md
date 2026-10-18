# SLALOM-FEEDBACK-01 逐门反馈与个人最佳节奏

- 状态：done（自动功能完成，人工体验pending）；基线main/d9f66f6，开始前干净；上轮progress，同车亲自过门/返回原复盘已实现并本地验证。
- 目标：让玩家知道哪一门耗时、余量如何；HUD最近门与结算六门成绩单，按同硬件/输入分组对照出发时个人完整最佳，鼓励有目标重试。
- 范围：在既有门线判定处记录入口后的累计插值时间，保存完整成功最佳的逐门时间/余量，旧数字成绩可继续用；可选runs详情坏/缺失仅停用该详情，不能丢总成绩或其他组。参考在出发时冻结，不拼接各次最快门；失败/较慢/写入失败不冒充新最佳。
- 只读表现：复用HUD分段区域和现有三列结算，不新增页面/Manager；观察值来自规则完成步，不推测车辆故障。虚拟试车只提供瞬时课题分数接口，不更新玩家历史或声明个人新最佳。
- 禁止：改物理/默认调校/辅助、门位/宽度/入口/奖牌/时间阈值、SDK/原生模块、瞬移/禁碰/改速度、放宽原Gate、推送。保留原当前车、倒车/菜单/同窗往返规则。
- 验证：相关T0→玩法相关T1/三种子；分组/旧文件/坏详情/原子保存失败/完整最佳与冻结参考/倒车不重复/漏门未到达/准确插值；普通Double实际键盘驾驶、重试读回、两分辨率HUD/结算与独立进程；旧真实完成步可重算新规则但必须明确区分新物理运行和规则复算。人工趣味性pending，原精度/实时Gate保持开放。

## 实现与验收

- 原门线交点记录入口后累计时间；HUD显示最近门余量、本段时间和相对出发时最佳的累计差。结算复用三列控件列出六门偏差、时间、余量与ΔPB；负数更快，漏门标出、未到达留空，失败不提供有效差值。重试/菜单隐藏旧表，滨海分段继续通过相关回归。
- 原version=1总成绩兼容，新增可选runs保存对应完整成功最佳的六门时间/余量。校验总用时一致、六门严格递增/有限、余量非负；坏详情保留总成绩/其他组。参考在创建课题时冻结，较慢/相同成绩不改写，不拼接单门；写入失败提示且不声明新最佳。虚拟试车仍不写玩家历史或声明个人新最佳。
- 普通/Double各新实际KeyboardController二值请求两次（非人工）：60km/h目标首次金牌14.214632943560819 / 14.214750521562149s；55km/h目标重试银牌15.486930696651132 / 15.486929295047595s。每库2585+2764步、全部6门/零碰撞；配置/输入保持，首次后与重试后最佳文件字节相同。四次共10698步所有SlalomResult字段用保存位置/速度/朝向逐步复算一致；复算未重跑物理。
- 普通1280×720和Double1024×768实际HUD/首次结算/重试六门差值图已查看，采集时冻结更新并重置展示相机到真实车位，未改变物理快照。失败/长存储提示的表格与按钮边界由明确UI显示夹具校验，未冒充人工失败驾驶。
- 原相关T0 49项通过（77.30s），新增首轮核心20项、补存储边界后核心+UI24项通过（24.52s）。最终普通相关T1 86项通过（139.53s pytest），0/17/23各1200步启动通过；Double最终核心/UI/独立进程25项通过（43.77s pytest）。独立权威进程实际6门金牌、逐门时间/新最佳回传及重启完整参考均通过。Ruff通过；初次RUF007按pairwise修正，未出现产品功能测试失败。
- [证据目录](../evidence/SLALOM-FEEDBACK-01/README.md)保存34份原样输出/4.19MB与10项归一LF施工源码指纹，归档只读逐步复核通过。根目录源码/SDK首末指纹相同；其model_fingerprint只覆盖原根源码/原生模块/配置，本批UI等另由source-manifest补充，未声称前者覆盖全部UI。
- 物理、默认硬件/输入辅助、门位/宽度/阈值/奖牌、120Hz、SDK/原生模块未改；T2/T3本批not_run，原T2失败/实时/人工Gate开放，持续目标active。无远端推送。

## 复现命令

```powershell
.venv/Scripts/python.exe tools/validate.py T1 --tests tests/test_slalom_lesson.py tests/test_slalom_feedback.py tests/test_slalom_feedback_ui.py tests/test_slalom_ui.py tests/test_slalom_session.py tests/test_slalom_process.py tests/test_race_feedback_ui.py tests/test_mode_lifecycle.py tests/test_snapshot_wire.py tests/test_road_comparison.py --output logs/validation/SLALOM-FEEDBACK-01-T1
.venv/Scripts/python.exe tools/physics/run_sim_double.py tools/validate.py T0 --tests tests/test_slalom_feedback.py tests/test_slalom_feedback_ui.py tests/test_slalom_process.py --output logs/validation/SLALOM-FEEDBACK-01-double-T0
.venv/Scripts/python.exe tools/slalom_feedback_check.py --output logs/validation/SLALOM-FEEDBACK-01-normal-drive --size 1280 720
.venv/Scripts/python.exe tools/physics/run_sim_double.py tools/slalom_feedback_check.py --output logs/validation/SLALOM-FEEDBACK-01-double-drive --size 1024 768
.venv/Scripts/python.exe docs/evidence/SLALOM-FEEDBACK-01/recheck.py --evidence
```

工具输出目录必须新建，复现时换新目录。下一轮按用户明确选择推进驾驶挑战与成长：让短课题成绩形成可见、可继续的进阶目标，初章原5步保持，先复用真实成绩，不凭空增加硬件性能奖励。

本地功能提交`5dc8abe`（基线`d9f66f6`）；提交后34份归档与原始输出字节一致，10项施工源码归一LF指纹与HEAD/工作区一致，工作区干净，未推送。此段收尾说明另作本地文档提交。

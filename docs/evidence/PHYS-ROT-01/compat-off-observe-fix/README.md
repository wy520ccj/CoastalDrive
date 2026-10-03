# PHYS-ROT-01 关闭转子输运兼容性复核

状态：**三场景逐快照旧字段精确相等**。这是PHYS-ROT-01实现过程中的短期兼容性复核，不构成任务整体验收；没有修改生产源码、测试或既有工具，没有运行T1，也没有提交/推送。

使用冻结A归档 `../PHYS-TIRE-04/final-validation-source-cg.zip`，SHA-256为 `05e4947a55580d6f20949cc490903a9bb76e2a22fd709e16eb50a2666d1891d6`。本次B工作树从运行前到运行后共75个 `src/**/*.py` 文件逐项SHA-256不变；开始和结束清单的文件SHA均为 `C1491D10B2148BF1DECDA6F505E1FB876C2EC5C71FC7EB12993A56467BA36A8F`。`vehicle_tires.py` SHA-256为 `738AD41DB6042F353648B1B4F51B9FB50FEDB40B999B35D9FFDD79B0A590F509`。清单分别保存在 `source-start-files.json` 与 `source-end-files.json`。

运行条件与前一目录相同：两边各自默认正常游戏CAR配置，120Hz固定步；加速、转向、倒车各120 tick，输入逐tick固定。运行前已确认 `wheel_rotor_transport=False`。每条轨迹包括初始状态和120个逐tick完整快照。A有288个递归旧快照字段，B均完整提供，并新增68个快照字段；所有A字段都逐tick进行Python数值精确相等比较，B新增字段不参与旧字段判定。公共车辆参数相同。

| 工况 | tick数 | 不同旧字段单元 | 首次差异 |
|---|---:|---:|---|
| 加速 | 120 | 0 | 无 |
| 转向 | 120 | 0 | 无 |
| 倒车 | 120 | 0 | 无 |

结果为 `comparison.json`，完整A/B原始逐tick轨迹为 `frozen-a.json` 与 `current-b.json`。运行与比较日志为 `current-b.log`。前一目录 `../compat-off-initial/` 保存了修正前的首次严格差异，未覆盖；该差异发生在修改前运行时观察分支未完全匹配旧算术表达式的工作树上。修正后的这一轮源树前后哈希稳定，三场景结果均为旧字段零差异。

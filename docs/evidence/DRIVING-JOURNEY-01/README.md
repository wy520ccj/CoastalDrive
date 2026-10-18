# DRIVING-JOURNEY-01 驾驶进阶证据

基线main/ee455b7，自动功能完成、人工体验pending，原精度/实时Gate开放；本批T2/T3未跑。无物理、硬件、辅助、120Hz、原奖牌标准或SDK变化，无推送。

- `normal/`1280×720、`double/`1024×768，各从进阶进入真实KeyboardController刹停金牌（1986拍、误差约−0.880m），返回3/6，再进入过门金牌（2585拍、约14.215s），返回6/6。每步位置/速度/按键/碰撞/规则结果、完整配置、根源码/SDK首末指纹和派生阶段见JSON/GZ；不含完整内部求解器重放载荷。
- 每库独立新进程`--restore`只读恢复6/6，成绩字节保持；summary/restore-summary与截图分开，不将重启称为新驾驶。宽屏/4:3实际图已查看，采集冻结更新并调整展示相机，非人工驾驶或实时性能结论。
- `recheck.py --evidence`从项目根使用临时成绩文件，9142步全部结果/成绩/阶段/重启一致；规则复核不重跑物理、不修改原数据。刹停速度按Session实际hypot(vx,vy)计算，记录的speed是带符号车速；首次工具误用此量在轻微倒退步失败，修正记录见任务包。
- `checks/core`10项；`ui`新6项/初章7项；`double-T0`16项；最后`modal-final`/`double-modal-final`及`lab-return`/`double-lab-return`各1项。明确夹具检查差距/分级/失败显示，实际成功驾驶另外记账。
- `checks/T1`34过3旧菜单断言失败；基线已有8入口，更新两份旧断言后`T1-repair`完整两模块8项/三种子通过。分批闭合，未声称最终37项全套重跑。原失败输出保留。
- 真实驾驶版本的application.py为`drive-application.py`，SHA与两库首末指纹一致；最终只增加F2模态守卫，差异见`drive-to-final.patch`。其他原根源码逐项SHA保持；最终守卫两库专项通过，复用原物理驾驶，不虚构最终版本重跑。最终10项施工源码归一LF指纹见`source-manifest.json`。

`layout/`为最终版本两分辨率初章新增按钮的单独布局采集，已查看，未执行课题；入口脚本为`chapter-layout.py`，从项目根运行并指定新输出目录和size。

`archive-manifest.json`记录60份6,374,385字节原样输出/源码快照、原路径与SHA256；`.gitattributes`保留原日志格式。复现命令/边界见[任务包](../../tasks/DRIVING-JOURNEY-01.md)。

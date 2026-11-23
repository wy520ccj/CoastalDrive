# 驾驶数值错误后的恢复

2026-11-02。接续玩家实际交通车崩溃，原除零根因已单独修复；本块处理失败后的窗口/方案恢复。HEAD仍15c321f5，保留此前全部未提交成果，未提交推送。

## 实际断点

原`SessionProcess._finish_frame`仅在成功更新快照后才清pending。子进程原异常已经从管道读走并抛回窗口时，pending仍为true；随后菜单命令会再次等已被消费的回包。为现有真实独立进程失败回归补该断言，原版1项失败，记录`logs/challenge-rebuild-20261102/numerical-recovery/red.log`。

现于`recv_bytes`成功取到完整回包后清pending，原异常类型/完整回溯仍向调用者传递；若等待超时未收到回包，pending保持，不发送替代请求或擅自重启。

`CoastalDrive.update`仅在读取驾驶帧时处理`ArithmeticError`：完整记录原始异常及远端回溯，明确中止本次会话；预算挑战返回同一份方案，自由驾驶返回首页。复用正常menu命令停止失败时钟、将未完成挑战记为无效并保存已有轨迹，重试时从起点正常重建，不沿用失败推进。

没有捕获全部内部异常、放宽求解精度、吞掉错误后继续驾驶或虚构成功结果。普通协议超时不进入该数值异常恢复分支。错误日志使用当前游戏存档/输出下`drive-errors/<唯一编号>.log`，不覆盖旧日志；写入失败会明确提示未保存。

## 验收与范围

- T0首次仅Ruff因测试夹具导入名称冲突停止；改为本文件实际窗口夹具。下一组3过1，失败是用例在倒计时尚未建立驾驶轨迹时要求已有记录；调整到真实发车并完成一拍再注入，生产恢复逻辑未因此改动。最终T0五项通过。
- 最终T1仅两个相关模块`test_session_process.py`、`test_driving_failure.py`，11项/Ruff/三种子启动通过，目录`T1-numerical-recovery`。没有重启整包T2、长驾驶或参数矩阵。
- 实际独立进程内注入数值失败，窗口经真实回包返回编辑页，同一PID继续可用、pending清除、原参数保留，正常键盘重试进入倒计时；没有重启第二套权威世界来掩盖故障。同步界面另验证不授奖、无效轨迹保存及日志写入失败后的菜单可用性。
- `numerical-recovery/scene/returned-to-build.png`实际画面已查看：110%扭矩/2250费用保留，现有提示区显示驾驶中止、方案保留和错误记录保存，按钮可继续使用。沿用原母版，只修交互和文字反馈，无新视觉方案。截图为主动注入诊断，不是又一次玩家崩溃或真人平衡成绩。
- 当前正常物理源码指纹与`manual-ready-after-steering-fix.json`相同；六份实际玩家记录SHA256均保持。本块只改窗口及回包状态，不改变物理方程、参数、价格和道路。

```powershell
.venv/Scripts/python.exe tools/validate.py T1 --tests tests/test_session_process.py tests/test_driving_failure.py --output logs/challenge-rebuild-20261102/T1-numerical-recovery
```

生产修改仅`src/session_process.py`与`src/application.py`，本块前文件副本在`numerical-recovery/`；原有其它未提交改动不回退。正式道路奖牌、付费收益和整体验收仍按主任务保留。

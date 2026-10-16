# LAB-REMOTE-INPUT-03 UU远程数值输入

- 状态：completed；基线main/1e0971f，施工前工作区干净。
- 用户实际条件：UU远程；数字框变浅蓝；退格能删除，数字不能输入。
- 范围：试验台数值输入、必要输入检查；物理/游戏/参数/其他远程软件设置不改。
- 依据：Panda1.10.16 WinGraphicsWindow在IME开启时忽略WM_CHAR，退格由PGEntry.press处理。此分支能解释现象，但未经UU端消息抓取不能唯一归因。
- 首块：16个数值框聚焦时结束本窗口IME候选状态；离屏GraphicsBuffer不调用窗口API；不自行补写字符，保护本地/远程字符不重复。
- 验收：相关T0/T1及用户UU实测；用户确认修正版窗口的“时长 s”能正常输入12.5。未另做硬件本地键盘、小键盘、所有远程软件或全部IME组合验收。

## 已完成与证据

- `src/lab_application.py::focus_parameter`共用焦点入口对实际`GraphicsWindow`调用`closeIme()`；离屏窗口保留原路径，不从按键事件额外补写数字，避免双写。
- 双精度T0：`.venv/Scripts/python.exe tools/physics/run_sim_double.py tools/validate.py T0 --tests tests/test_lab_ui.py --output logs/validation/LAB-REMOTE-INPUT-03-T0 --timeout 300`，Ruff及17项通过。
- 双精度T1：`.venv/Scripts/python.exe tools/physics/run_sim_double.py tools/validate.py T1 --area lab --output logs/validation/LAB-REMOTE-INPUT-03-T1 --timeout 300`，Ruff、145项及种子0/17/23各1200拍通过。未重跑全库、T2/T3或性能。
- 新开独立窗口“CoastalDrive · UU 数值输入复测”，载入已保存的3秒轮跳记录并展开高级参数；旧窗口保留用户当前内容。启动器`logs/manual-playtest/lab_uu_input.py`，输出`logs/manual-playtest/uu-input.*.log`，仅有正常管线提示。
- 用户UU实测：点击“时长 s”空白框输入12.5，用户回复“能正常显示 12.5”。该实际字符输入用例通过；其他字段和完整实验操作继续由用户使用确认。
- 修正作为本任务独立本地提交保存，未推送远端；启动的新窗口包含相同修正，旧窗口未被关闭或覆盖。

## 依据

- [Panda3D 1.10.16 WinGraphicsWindow](https://raw.githubusercontent.com/panda3d/panda3d/v1.10.16/panda/src/windisplay/winGraphicsWindow.cxx)：`WM_CHAR`在`_ime_open`为真时不发送keystroke；`close_ime`结束当前窗口IME状态。
- [PGEntry](https://raw.githubusercontent.com/panda3d/panda3d/v1.10.16/panda/src/pgui/pgEntry.cxx)：删除等控制键由`press`处理，字符由`keystroke`处理。该差异支持当前排查方向，尚未取得UU实际消息流证明唯一根因。

# 独立试玩版更新后沿用成绩

2026-11-07，基线 `15c321f5`。原独立版按整个程序和原生扩展的文件内容分组，换界面或重新链接就会产生新分组。打包时现另计算玩法摘要，包含物理、输入、赛道规则的源码依赖和实际原生扩展。项目原生扩展仅在玩法摘要中去除 COFF 和调试目录的时间戳，整包和逐拍文件仍按原始字节计算指纹。运行时只有包内指纹与构建清单一致时才启用玩法摘要，运行库、规则、车辆、路况和输入条件仍分别参与匹配。[Windows PE 字段说明](https://learn.microsoft.com/en-us/windows/win32/debug/pe-format)

对照两份已有预览包和构建清单，玩法源码保持，五个项目原生模块排除上述时间戳后相同，其余扩展和 DLL 字节相同。经核对将本版对齐最近的 `challenge-preview-20261107` 正常游戏分组。旧文件在原位置继续读写，无须迁移。更早的 `challenge-preview-20261106-playable` 原独立成绩组保留在旧包，未合并两组。源码运行的原始指纹因分组模块变更而更新，现有源码成绩组沿用已核对映射。

T1 通过 23 项，含实际源码依赖变化、冻结包清单匹配、添加诊断程序时组别稳定、错包清单回退及试车、原始逐拍兼容。Ruff 和三种子短启动通过。本轮未重复关卡标定，整包 T2 和剩余改装平衡开放。

新包位于 `builds/challenge-preview-20261107-records/app/win_amd64/coastaldrive.exe`。实际冻结诊断经山谷正常入口，在隔离存档读到按上一版真实分组写入的 60 秒个人最佳和试车对照。60 秒为存档验证夹具。新包实际指纹与旧包不同，成绩分组一致。构建回执及 `verification/record-upgrade.json` 记录两种指纹和结果。本地实现未提交、未推送或发布。

```powershell
$sdk=(Resolve-Path 'build/road-edge-sdk/panda/built-road-edge').Path
$env:PYTHONPATH="$sdk;$env:PYTHONPATH"
.venv/Scripts/python.exe tools/validate.py T1 --tests tests/test_lap_ghost.py tests/test_trial_references.py tests/test_challenge_trace.py --output logs/challenge-preview-records-20261107/T1 --timeout 130
```

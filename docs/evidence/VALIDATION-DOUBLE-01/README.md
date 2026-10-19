# VALIDATION-DOUBLE-01

2026-10-19；基线889b346。关闭前批Double机械测试的两项Normal字节参考错误，不修改生产代码、SDK、原生模块、硬件或数值阈值。

## 独立来源

`reference/`的26份结果由[前批归档](../PHYS-SHARED-ROUNDING-01/archive-manifest.json)中修复前机械模块6ca08643bc79e1f614eb8bfe263bb45dc338de95902878ecb276b212032d99a6实际执行生成，当前模块c84bfb06…没有参与期望值生成。生成器在导入力学代码前载入并确认旧模块；同时核对旧C源码SHA。输出目录必须不存在，不自动更新参考。

输入仍是[原26份实际子步夹具](../PHYS-PERF-01/structural-20261009/native-input-fixture)，硬件按原测试的显式适配读取。`context.json`固定实际Double SDK完整指纹、原55文件（含Normal结果）SHA、数值包签名、有效硬件和新26结果SHA。正序执行后重建几何版本、倒序重放，输出逐字节一致。没有创建Bullet世界，这些是旧输入在Double SDK下的独立数值参考。

26份Double结果都与原Normal结果有差别。输入适配中的Mat3/Quat/Vec3遵循实际Panda SDK别名，不能将Normal完整输出作为Double字节期望。首份轮速示例4.668957284033287与4.6689572872807相差约3.247413e-9；各字段单位不同，不能以跨字段最大绝对差评价物理误差。

测试按实际LPoint3类型选原Normal或明确Double参考。Double参考先验证上下文与内容，再严格比较完整输出；原工作区交错、52次真实内核调用、3线程各8次及异常恢复检查保持。格式/SDK/来源/签名/输入集合与内容/硬件/结果集合与内容/缺失元数据均拒绝，没有容差替代、跳过或回退。

## 实际命令与结果

```powershell
.venv/Scripts/python.exe tools/physics/run_sim_double.py tools/physics/capture_double_reference.py --output logs/validation/VALIDATION-DOUBLE-01-reference-final --reference-module docs/evidence/PHYS-SHARED-ROUNDING-01/production-before-mechanical_kernels.cp314-win_amd64.pyd --reference-source docs/evidence/PHYS-SHARED-ROUNDING-01/production-before.c
.venv/Scripts/python.exe tools/physics/run_sim_double.py tools/validate.py T0 --tests tests/test_continuous_solver.py --output logs/validation/VALIDATION-DOUBLE-01-T0
.venv/Scripts/python.exe tools/validate.py T0 --tests tests/test_continuous_reference.py tests/test_continuous_solver.py --output logs/validation/VALIDATION-DOUBLE-01-reader-T0
.venv/Scripts/python.exe tools/validate.py T1 --tests tests/test_driveline_native.py tests/test_drivetrain_jacobian.py tests/test_drivetrain_prepare.py tests/test_tire_drivetrain.py tests/test_transmission_ports.py tests/test_continuous_solver.py tests/test_continuous_reference.py --output logs/validation/VALIDATION-DOUBLE-01-normal-T1
.venv/Scripts/python.exe tools/physics/run_sim_double.py tools/validate.py T1 --tests tests/test_driveline_native.py tests/test_drivetrain_jacobian.py tests/test_drivetrain_prepare.py tests/test_tire_drivetrain.py tests/test_transmission_ports.py tests/test_continuous_solver.py tests/test_continuous_reference.py --output logs/validation/VALIDATION-DOUBLE-01-double-T1
```

Double T0 19项0.61s；Normal读取边界及连续内核T0 30项0.78s。最终Normal T1 600项3.28s、Double T1 600项3.29s；各自Ruff与0/17/23种子各1200步启动通过。11项新增测试包含实际SDK选择和损坏/自生成拒绝边界。上述T1包含真正启动世界的smoke，与不建世界的参考捕获分别记账；没有新驾驶、画面或性能验收。

`archive-manifest.json`固定45份原始文件/406376字节，含27份参考和18份检查日志/摘要；`source-manifest.json`固定4份相关源码的LF归一SHA。原55文件核对保持、`git diff HEAD -- src 原夹具目录`为空，当前安装机械模块仍c84bfb06cae9d51a46f5cdff69107f96e73c6757d2853ef46673d0710010e7a2。旧失败保存在前批证据中，本批证明其参考口径已修正，不追溯改成通过。

原落地制动T2失败、实时和人工趣味性Gate仍开放。本批仅本地开发，无推送。下一主线按用户反馈推进挑战内容和路线变化。

# Shared-solution 数值块归档

## 实现与边界

本轮生产实质修改为 `src/mechanical_kernels.c`、`src/tire_drivetrain.py`；`tests/test_drivetrain_jacobian.py` 将观测口接到真实 `shared_solution` 系数包和独立中心差分，仍保留16个样本与 `2e-6` 门槛。Python 原8维求解路径保留为对照。30轮、角更新 ULP/`1e-14`、端口 `1e-11`、8次线搜索、半步 `fsum`、暖分区直接更新保持。

`tire_drivetrain.py` 同步了主目录 `127c1d0` 已验证的 map160 三行修复；该上游差异已在主线 T0/T1 验证。其余工作树状态中 `suspension_contacts.py`、`wheel_contact_kernels.c` 两个 M 标记的原字节与 HEAD 完全相同，不属于本轮实质更改。

## 独立旧内核审计与验证

独立审计 r4 使用从 `127c1d0` 编译并改名的旧 C mapping/Jacobian/LU 基线，未通过新公开 helper 自证：10,661次调用（bias 9,380、ordinary 1,281）逐项完全一致，包含输出与暖状态。旧 C 原源、仅改模块名的副本、setup、构建日志、receipt/manifest均保留；未复制 PYD 或 obj，只有 SHA 留在收据/清单中。早期 Keycross、旧LU观测零调用、wrapper scope 错误及修正探针日志也一并保留，它们属于审计脚本/观测范围问题，不是物理失败。 audit JSON 的 baseline 字段仍有“current native boundaries”遗留字样；实际独立脚本明确加载旧 DLL 的 mapping/Jacobian/LU。原 JSON 保持不改，这个标签遗留不改变审计基线。

T0 为373 passed/Ruff通过。T1 为645 passed（81.36秒）、Ruff通过，三个种子为10.293、10.465、10.266秒。与主目录 map160 修复后的整合基线相比，0车和8车各48拍完整 Snapshot 全字段相同；0.8265195/5.5732561秒只记作诊断，不是FPS或性能Gate。

## 源码来源与完成边界

基线 HEAD 为 `6d5cc19`，`src/tests/tools` 354项 `.py/.c/.pyd` 已捕获完整起止 SHA，起止一致。实质差异仅三文件；旧基线独立 DLL 来源为 Git `127c1d0`。该功能块尚未并入 main，没有profile或实时FPS证据。main `01b99f3` 的 T2-r2 在本轮记录时仍运行；阶段、产品性能和人工Gate尚未完成。

大 JSON 使用 `mtime=0` gzip。`manifest.json` 校验来源字节、归档字节及gzip载荷 SHA；`receipt.json` 记录验证状态、旧二进制 SHA 和边界。

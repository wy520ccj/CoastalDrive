# 静态碰撞签名复用与凸体包刷新

2026-10-28，继续PERF-SMOOTH-01/VISUAL-EXTEND-01。已将一项完整步有收益的精确复用接入共用物理路径，未改模型参数、120Hz、子步、碰撞、镜位或视觉资源。整体画面推广与长期流畅度目标仍active，无提交/推送。

## 根因与实现

此前static_support_read每拍读取真实世界后，还重新分配各形状矩阵/姿态/margin/边界数组和完整签名，之后才发现没有变化。本轮在src/static_support_read.h先逐值核对已有签名：资格、顺序、当前形状、父级净变换、形状变换、margin、未登记凸体边界及三项登记来源继续按原值检查；只有完全相同时才复用原数值包。不复用旧接点/力，不减少查询频率，不跳过未知形状，发生变化时仍完整构建原记录。

复核RenderPipeline固定f858d071的[EnvironmentProbe](https://github.com/tobspr/RenderPipeline/blob/f858d071d54902e7d00eb0046dd5730eac9e4678/rpplugins/env_probes/environment_probe.py)：自身setter明确设置modified，不能把这个方法直接当成Bullet所有外部变化都可追踪。本地getBamModified探针中，改名称、质量、PythonTag、shape margin、添加shape/凸体点均未完整反映，因此否决仅凭此标记跳过读取的方案。沿用原仓库明确职责、已有值按需重用的组织方法，不导入整套管线。

新增登记凸体生命周期回归时另发现**原版已有错误**：清除凸体登记，或父级非单位缩放使原生凸体资格失效时，数值分区可能相等，packet_cache便保留旧hulls。原版与隔离候选在同一新回归的两种transform-cache政策下均失败。src/suspension_contacts.py现同时比较hull_packets决定是否刷新；错误来源与正常卡顿分开，不宣称它就是正常驾驶长帧根因。

## 完整物理步对照

独立候选源码/二进制在logs/visual-extend-20261028/static-signature-candidate。按正常入口game-tuned/原ViewDriver、自由8交通、真实settle_initial、检查点框关闭、seed0、预热120/测360步，A/B/B/A顺序运行，四轮完整Snapshot负载哈希与配置全部一致，0碰撞：

| 原/候选 | 完整步均值 | P95 | 最大值 |
| --- | ---: | ---: | ---: |
| A1原 | 5.383ms | 7.274ms | 12.774ms |
| B1候选 | 4.866ms | 6.253ms | 8.674ms |
| B2候选 | 5.126ms | 7.737ms | 12.152ms |
| A2原 | 5.313ms | 8.761ms | 12.824ms |

两组均值5.348→4.996ms，减少约**6.59%**，只支持该完整步短样本的收益。生产从原setup配置以/fp:strict重编wheel_contact_kernels，未重编其他模块；最终生产自由/计时各360步，共720个完整Snapshot负载哈希与原版相同，完整车辆配置相同。计时的原版哈希复用已有效历史样本，仅作数值等价，不作同时段速度比较。

本轮原版计算/前台已经明显比此前严重负载时快，**不能将先前57ms中位到本轮8ms的变化归因本修复**。单次生产4.240/3.085ms均值也不替代ABBA或120Hz长期门。

## 正常入口与地区检查

1280×720、默认/Draw、原独立120Hz，两版均从静止正常循线，未人工驾驶。滨海自由/计时分别190米，均0碰撞/丢时，0最小化；原自由1673/1675帧前台，其余全部前台。截图后回读帧按原工具单列：

| 模式 | 原帧数→新帧数 | 中位 原→新 | P95 原→新 | 最大 原→新 | >33.33ms 原→新 |
| --- | --- | --- | --- | --- | --- |
| 自由 | 1675→2003 | 8.925→8.361ms | 16.926→10.878ms | 49.160→28.074ms | 5→0 |
| 计时 | 1959→2025 | 8.315→8.165ms | 12.284→11.288ms | 45.173→38.760ms | 1→1 |

正常窗口两轮为相邻顺序，非随机交叉，不把全部差值归因单项优化，也不称长期流畅。新默认[滨海120米实图](static-signature-coastal-120m.png)已实看，动态海面/落日天空/HUD40保持，未加载短草实验。

原山脊生涯入口再正常270米，1037帧全部前台、0最小化、0碰撞/丢时；剔除截图回读后中位18.913/P95 24.406/最大51.062ms，仍非稳定60FPS。[山地120米实图](static-signature-ridge-120m.png)保持48d晴空与原树草石。最长帧相机往返33.379ms、快照0.784ms，另一47.784ms帧快照往返30.677ms；权威有对应长步，不能单凭等待时间断言IPC、GIL或GPU为唯一根因。最大流送步骤19.13ms含加载，不当作这两个驾驶长帧来源。原始frames/main_phases与authority-pauses共同保留。

## 回归、失败与保持

- 隔离构建首次未强制重编时只输出running build_ext，未算新内核；随后--force实际编译才运行检查和ABBA。旧lab_contact_native.h C4090警告保留，编译/链接成功。
- 原13项静态读取/缓存/查询生命周期通过；新增注册凸体回归在原版/候选各两项失败，确认旧packet失效漏洞后修正。最终隔离15项通过。
- 生产T0-hull-packet-refresh：Ruff/静态读取完整7项通过。生产最终T1-static-signature：**48项**静态读取、缓存、查询生命周期、候选、真实凸体、世界子步及原生悬架准备，Ruff与0/17/23各1200步种子全部通过。
- 中途读取JSON未指定UTF-8导致观察脚本GBK错误，修正读法后取到真实报告，不影响游戏/测试；未把该脚本失败称通过。
- 180份顶层生产源码/原生文件仅static_support_read.h、suspension_contacts.py、wheel_contact_kernels.cp314-win_amd64.pyd三份变化，其余177份保持。旧PERF72/视觉91全部指纹保持，新增登记后PERF76/视觉95。全部新增/临时输出B盘，无保留试玩窗。

完整数值/快照等价/前台状态/原始峰值/保持记录见[static-signature.json](static-signature.json)。主要命令：

```text
.venv/Scripts/python.exe tools/performance/benchmark_physics.py --source <原/隔离src> --workers 0 --traffic 8 --mode game --traffic-input-mode game --track coastal --driver coastal --vehicle-design game-tuned --checkpoint-frames off --settle-initial --seed 0 --warmup 120 --steps 360 --capture-hashes --output logs/visual-extend-20261028/signature-abba-<A1/B1/B2/A2>
.venv/Scripts/python.exe tools/validate.py T1 --tests tests/test_static_support_read.py tests/test_static_support_cache.py tests/test_suspension_query_lifetime.py tests/test_suspension_candidates.py tests/test_convex_queries.py tests/test_world_substeps.py tests/test_suspension_native.py tests/test_native_suspension_prepare.py --output logs/visual-extend-20261028/T1-static-signature --timeout 300
.venv/Scripts/python.exe tools/performance/check_coastal_modes.py --output logs/visual-extend-20261028/signature-normal-after
.venv/Scripts/python.exe tools/performance/check_driving_stalls.py --end-distance 270 --output logs/visual-extend-20261028/signature-ridge-normal
```

仍有计时38.76ms、山地51.06ms峰值。下一结合实际世界查询锁等待/物理长步继续定位，并继续设计38及地区规格39的画面推广；本块不替代其它模式/UI/试验台、人工视觉/手感或长期性能验收，总目标active。

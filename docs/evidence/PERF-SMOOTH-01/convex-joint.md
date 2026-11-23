# 护栏查询保留，机械迭代继续使用原生内核

2026-10-28，接续[撞后持续卡顿](post-impact.md)。上一轮已减少重复查询，但四子步撞击阶段仍超8.333ms预算。本轮继续优先性能，没有改视觉、车辆、碰撞形状、子步精度、120Hz、时间推进或存档。**当前提速已接入，仍有长帧，用户流畅度与全场景画面目标未通过。** 无提交/推送，新输出均B盘。

## 根因与实现

`native_contact_geometry`发现静态几何含未被纯数值支持面接管的护栏凸体后，原来直接返回None。这不仅保留了必须执行的原世界查询，还让整套机械迭代退回Python。场景远处有这类形状也会触发这一分界。

本轮增加一个明确的世界查询接点包：原`finite_contact_system`继续查询同一冻结Bullet世界、原凸体、当前变换与原5cm候选覆盖；得到的四轮梯度、对齐和接触结果交给已有`joint_solve`。机械方程、轮荷迭代、残差阈值和20轮限制保持。

这类包查询Python/Bullet，故整个迭代保持世界锁和GIL；原完整纯数值包继续按旧路径交出世界锁并释放GIL。没有把原世界查询放进无锁线程。共同接触API升为v3，两个原生模块一起按原setup的`/fp:strict`重编，避免新旧模块混用旧调用约定。原世界查询异常原对象向上传递，失败后工作区可继续复用。

改动为`src/tire_drivetrain.py`、`src/joint_contact_api.h`、`src/joint_contact_impl.h`、`src/joint_iteration.h`、`src/wheel_contact_kernels.c`及对应wheel/mechanical两个pyd。原7份备份在`logs/visual-extend-20261028/convex-joint-production-before/`。无新增第二物理世界、近似形状或模型参数。

## 同一完整步ABBA

延续玩家原车、8交通、正常/撞击各480拍的固定初态诊断。A为上一轮默认版，B为本轮隔离候选，按A1/B1/B2/A2运行。每轮完整配置相同、2次撞击/179细化拍，每轮960个完整Snapshot哈希一致（仅跨会话epoch归零）；正式重编后另做同一960拍，哈希仍同原。

| 顺序 | 细化拍均值 | 细化拍P95 | 最大 |
| --- | ---: | ---: | ---: |
| A1 | 11.212ms | 14.078ms | 20.828ms |
| B1 | 9.997ms | 12.383ms | 17.595ms |
| B2 | 10.125ms | 12.913ms | 16.114ms |
| A2 | 10.992ms | 14.270ms | 19.520ms |

两组均值11.102→10.061ms，减少约9.38%。具体P95/峰值以[原始汇总](convex-joint.json)为准；这些值仍超120Hz预算，只支持这一短样本的计算改善。不能将本轮原版比上一轮更快归因本修改，也不能用无窗口吞吐代替实际驾驶帧时。

## 大窗口正常控制撞栏

实际2509×1180、玩家原车、原音效与画质、8交通。从静止正常加速，在20米后转向自然撞护栏，无运行中姿态/速度修改。四轮交叉对照和最后正式版均在tick938/模拟7.816667秒撞击，再观察5模拟秒；全部前台、0最小化、0丢时。测量结束后才截图。

| 版本 | 全前台帧数 | 最大积压 | 撞后首2模拟秒帧时P95 | 第2–5模拟秒帧时P95 | 第2–5模拟秒最大帧 |
| --- | ---: | ---: | ---: | ---: | ---: |
| A1上一版 | 1145 | 457.633ms | 12.678ms | 10.693ms | 74.883ms |
| B1候选 | 1251 | 303.922ms | 11.908ms | 10.322ms | 51.196ms |
| B2候选 | 1250 | 310.053ms | 12.390ms | 10.586ms | 96.832ms |
| A2上一版 | 1167 | 444.833ms | 12.735ms | 11.011ms | 66.575ms |
| 正式版重编后 | 1180 | 377.674ms | 13.144ms | 10.699ms | 79.845ms |

相邻反向对照支持减少撞击计算积压；**最长帧并未稳定降低，不能说卡顿消除。** 正式版实图[convex-joint-current.png](convex-joint-current.png)已实际查看，水面/落日天空/HUD/镜位保持；截图不是性能验收。

四轮峰值对齐共同墙钟后，B2恢复区96.832ms帧内快照往返24.455ms、相机往返67.400ms，但权威相机函数本体仅7.432ms；同期两次reply耗时30.987/15.661ms，物理连续步约9–15ms，未发现对应GC峰值。A2、B1也在约撞后3.45模拟秒出现类似交接等待。现有相机idle在查询返回时开放，回包尚未必发出；这只是下一项需要隔离对照的假设，**本轮没有改回包协议、延长等待或用休眠掩盖它**。

## 验证与边界

- 隔离候选先构建并跑新原世界查询/异常/锁检查及完整continuous_solver，21项通过/0.73s。新回归检查四轮查询结果、原异常对象、真实海岸护栏使用原生机械内核、查询期间不得交出世界锁，以及异常后工作区可复用。
- 正式T1覆盖joint_world_queries、continuous_solver、driveline_native、tire_aligning、joint_suspension、convex_queries、suspension_query_lifetime、session_clock、session_process、world_substeps，**110项通过/7.33s**；全src/tests/tools Ruff和0/17/23各1200步种子全部通过。原完整输入夹具、两驾驶配置与纯数值路径继续覆盖，不能据此宣布所有地图/模式人工通过。
- 本轮没有出现新测试失败。读取不存在的tests/conftest.py时观察命令报缺文件，随后确认测试原本没有此文件，不当构建或测试失败。构建保留旧lab_contact_native.h的C4090 const警告，两个模块均成功编译链接。
- 上轮完整碰撞模块的悬空对称制动收敛检查，已用原版同值复现失败；本轮未重跑该节点，旧失败继续开放，不把本轮110项写成完整碰撞模块通过。
- 本轮176份顶层py/c/h/pyd源码快照中7份明确变化，其余169保持；四份cpp未纳入该快照，不能用该计数宣称已审计它们。当前PERF82中79份保持、3份更新，补本轮模块及相关测试后94；视觉101中98份保持、3份更新，补后113。两登记全部匹配；旧登记与源码均备份B盘。
- 窗口工具新增`--source`用于父/子进程选择同一隔离源码；B2/A2/正式版权威报告新增实际模块路径与SHA，确认候选及正式版均使用预期两个原生模块和机械装配。该元数据在结束后采集，未改变驾驶推进。
- 所有本轮窗口已结束，无保留预览。没有手动驾驶体验、长期性能Gate、新美术方案或跨全模式验收。高速山体UV误平铺和城市粗盒仍按[上轮已定位问题](post-impact.md)接续，设计38/地区规格39及其它UI/试验台推广仍未完成。

主要命令：

```text
.venv/Scripts/python.exe logs/visual-extend-20261028/convex-joint-candidate/build_kernel.py build_ext --force --build-lib logs/visual-extend-20261028/convex-joint-candidate/src --build-temp logs/visual-extend-20261028/convex-joint-candidate/obj
.venv/Scripts/python.exe tools/performance/check_post_impact_window.py [--source logs/visual-extend-20261028/convex-joint-candidate/src] --workspace <玩家vehicle.json> --output logs/visual-extend-20261028/convex-joint-window-<A1/B1/B2/A2>
.venv/Scripts/python.exe logs/visual-extend-20261028/build-convex-joint-production.py
.venv/Scripts/python.exe tools/validate.py T1 --tests tests/test_joint_world_queries.py tests/test_continuous_solver.py tests/test_driveline_native.py tests/test_tire_aligning.py tests/test_joint_suspension.py tests/test_convex_queries.py tests/test_suspension_query_lifetime.py tests/test_session_clock.py tests/test_session_process.py tests/test_world_substeps.py --output logs/visual-extend-20261028/T1-convex-joint --timeout 300
```

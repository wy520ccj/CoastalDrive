# 保留世界锁，仅在真实查询时接回解释器

2026-10-28，接续[相机回包交接](reply-handoff.md)。本轮找到恢复阶段长帧的重要来源，正式版大窗口短测最大20.710ms，反向原版为63.624/93.752ms。**物理仍有约0.325秒积压，长期60FPS、其它地图碰撞和人工体验尚未通过。** 全场景画面目标继续active，没有提交/推送，所有新输出B盘。

## 根因与实现

此前为保证原护栏查询安全，只要共同接触包需要Python查询，joint_solve便在整段机械数值迭代期间保持GIL。唯一Bullet世界锁确实需要保持，但纯C机械计算同时占用GIL，使快照/相机消息线程迟迟不能开始处理。前轮“查询结束到回包结束”的交接修正无法解决这段开始处理之前的等待。

按[CPython的线程状态规范](https://docs.python.org/3.14/c-api/threads.html#detaching-the-thread-state-from-extension-code)，长时间执行且不访问Python的原生计算可暂时分离线程状态，调用Python时必须重新接回。本轮没有使用旧的PyGILState接口或创建另一解释器：joint_solve保存调用线程的同一个PyThreadState，机械数值区分离；仅在原finite_contact_system查询和结果解包时接回，随后再分离。**世界锁仍始终保持原策略**，没有让另一线程推进或修改Bullet世界。

原Python查询异常对象由NativeSolveError保留引用，最终接回线程状态后原样抛出；查询期间暂停wheel/mechanical两模块本线程的延后错误记录，使查询内部再次调用原生方法时仍能正常抛出Python异常。新增回归覆盖原异常对象身份、两个模块内部参数错误及失败后工作区复用，避免出现丢失原异常的SystemError。

NativeSolveError布局改变，joint_contact_api升为v4，两个模块按原setup的/fp:strict一起重编，防止新旧布局混用。生产改变4份头文件、2份pyd；tire_drivetrain.py仅更新解释器交接注释。原几何、机械方程、完整查询、120Hz、四子步撞击精度、20轮限制、全部阈值、显示延迟、画面及镜位保持。未设置线程优先级、改变解释器切换间隔、加入休眠或丢弃模拟时间。

## 结果等价与回归

玩家原coastal-roadster、质量1040kg、GAME实际配置、8交通，固定初态正常/撞击各480拍。隔离候选及正式重编后各960个完整Snapshot哈希均与原版相同（只将跨会话epoch归零），完整配置相同，2次真实撞击/179细化拍保持。正式版细化拍均值10.347ms仍超过8.333ms预算，不宣称本轮降低了物理计算总成本。

隔离21项通过；补原生查询内部错误回归后21项/0.61s再次通过。正式T1覆盖joint_world_queries、continuous_solver、driveline_native、tire_aligning、joint_suspension、convex_queries、suspension_query_lifetime、session_clock、session_process、world_substeps、camera_reply_handoff：**113项通过/7.94s**，全src/tests/tools Ruff及0/17/23各1200步种子全部通过。旧悬空对称制动收敛失败继续按此前原版同值复现记录开放，本轮未重跑，不称完整碰撞模块通过。

## 真实大窗口ABBA

2509×1180、原音效/画质、玩家原车、8交通，从静止按原Control加速，20米后正常转向撞栏，无运行中姿态/速度修改。四轮及正式版均在tick938/模拟7.816667秒发生撞击，随后观察5模拟秒。全部帧前台、0最小化、0丢时，结束后才截图。B1-r2是修正隔离资源定位后的第一份有效B样本，不是挑选较快的驾驶重试。

| 顺序 | 全前台帧数 | 恢复区第2–5模拟秒最大帧 | 整段最大帧 | >33.33ms帧 | 最大物理积压 |
| --- | ---: | ---: | ---: | ---: | ---: |
| A1原版 | 1202 | 63.624ms | 63.624ms | 6 | 377.068ms |
| B1-r2候选 | 1267 | 17.198ms | 22.291ms | 0 | 336.802ms |
| B2候选 | 1279 | 17.522ms | 20.705ms | 0 | 336.995ms |
| A2原版 | 1237 | 93.752ms | 93.752ms | 4 | 312.865ms |
| 正式重编后 | 1251 | 16.508ms | 20.710ms | 0 | 324.636ms |

两次候选均减少了原版反复出现的恢复长帧，正式入口也保留这一改善。**积压没有稳定下降**，不能将A1的0.377秒到正式0.325秒称为计算提速，也不能将未出现>33ms的短样本当长期Gate。正式恢复区中位8.310/P95 10.833ms；[当前正式实图](joint-query-gil-current.png)已查看，截图仅证明真实运行画面，尚无人工驾驶接受结论。

完整配置、各阶段分布、峰值分项及对应权威步骤/回包/GC、实际模块路径/SHA见[joint-query-gil.json](joint-query-gil.json)。候选源和数据在`logs/visual-extend-20261028/joint-query-gil-*`，原7份生产文件另存`joint-query-gil-production-before/`。所有测量窗口已结束，无保留预览。

## 独立尝试：混合几何未采用

本轮先检查计算热点，260拍剖析中原完整接触回调4852次、逐轮relative_entry19408次。混合候选让普通路面用原生几何，仅有原护栏可能相交时回调原查询，完整世界和真正凸体求交保留；relative_entry降至4914次。但首轮ABBA完整细化步反而慢3.10%，新增完整候选投影抵消了收益，没有接入。

再精确复用相同坐标系的投影，R2的ABBA均值10.210→9.733ms，约快4.67%；四轮各960完整快照仍同原，真实沿海不同侧向位置/跨覆盖盒查询及旧数值夹具共22项通过。该候选仍单独留在`mixed-contact-candidate`，**没有进入默认，也没有正常窗口性能结论**。新混合几何测试存于同一候选目录，不把未采用的行为要求放入生产测试。当前生产wheel_contact_kernels.c SHA与开工相同，确认没有混入候选的包围盒/几何结构变更。正式长帧改善只归属于本轮解释器交接对照。

## 失败、来源与下一步

- 第一份GIL候选窗口在创建窗口前失败：完整隔离src使资源根指向候选目录，找不到原车配置。外层命令尾部读取日志使工具exit为0，不能因此算Python成功。失败日志保留，没有性能样本；诊断工具改为隔离源码前先载入主工作区paths，实际资源继续取原工作区，B1-r2/B2/正式报告均记录并核对resource_root。未复制/替换玩家资源。
- 混合R1性能退化保留；R2只有计算诊断，未采用，不用其收益修饰正式版。编译保留原lab_contact_native.h的C4090 const警告，两个模块均编译链接成功。
- 180份顶层生产文件仅上述7份变化，其余173份保持。PERF97中89份保持、8份更新，补native_solve_runtime.h后98；视觉116中108份保持、8份更新，补后117。两登记全部匹配，旧登记备份B盘。所有美术、地区天空、道路、车辆参数和3.2m镜位保持。
- 下一优先继续压低真实撞后计算成本，扩到山地/无限高速的正常碰撞流程；不能把滨海短样本扩成所有模式结论。设计38、其它UI/试验台/模式推广、高速山体UV误平铺与粗盒城市仍未完成，仍需研究/设计/真实成品对照。

主要命令：

```text
.venv/Scripts/python.exe logs/visual-extend-20261028/joint-query-gil-candidate/build_kernel.py build_ext --force --build-lib logs/visual-extend-20261028/joint-query-gil-candidate/src --build-temp logs/visual-extend-20261028/joint-query-gil-candidate/obj
.venv/Scripts/python.exe tools/performance/check_post_impact_window.py [--source logs/visual-extend-20261028/joint-query-gil-candidate/src] --workspace <玩家vehicle.json> --output logs/visual-extend-20261028/joint-query-gil-window-<A1/B1-r2/B2/A2>
.venv/Scripts/python.exe logs/visual-extend-20261028/build-joint-query-gil-production.py
.venv/Scripts/python.exe tools/validate.py T1 --tests tests/test_joint_world_queries.py tests/test_continuous_solver.py tests/test_driveline_native.py tests/test_tire_aligning.py tests/test_joint_suspension.py tests/test_convex_queries.py tests/test_suspension_query_lifetime.py tests/test_session_clock.py tests/test_session_process.py tests/test_world_substeps.py tests/test_camera_reply_handoff.py --output logs/visual-extend-20261028/T1-joint-query-gil --timeout 300
```

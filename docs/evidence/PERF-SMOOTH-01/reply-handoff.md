# 相机交接延续到回包发送完毕

2026-10-28，接续[护栏机械内核](convex-joint.md)。本轮修正一个已证实的交接缺口，**不宣称得到稳定帧时收益**。真实窗口仍有83.384ms长帧，性能/人工与全场景画面目标继续开放。所有新增输出B盘，无提交/推送。

## 已证实的问题与修正

原Session.camera_position在真实查询返回时就设置camera_idle；独立相机线程还要转换结果、编码和发送回包。追赶线程可能在这些工作完成前进入下一拍，使回包再次竞争计算时间。

新增受控线程回归，在真实查询已结束而send_bytes尚未返回时尝试推进下一拍。原版的正常结果、查询异常、发送失败三种情况均失败：camera_idle已经放行。不是以一次长帧猜测这个顺序问题。

交接现由`session_process._camera_loop`持有：收到相机请求后清除camera_idle，原查询和完整_reply结束后在finally恢复。`Session.camera_position`只保留原世界锁与重定位坐标转换；本地直接查询仍互斥，传输公平性由真实相机通道负责。没有新增等待时长、固定休眠、丢拍/丢时或消息协议。异常回包和发送失败也释放交接；保留原异常处理边界。

`SessionClock.tick`仅更新注释，仍在取得世界锁前等待原Event，不持世界锁等待回包。真实查询、物理、120Hz、碰撞精度、画质/镜位/模型和两个原生模块保持。

## 大窗口ABBA与正式复测

玩家原车、8交通、2509×1180、原音效/画质。从静止按原Control加速，在20米后转向自然撞栏，不中途改姿态/速度。每轮在tick938/模拟7.816667秒撞击，再观察5模拟秒；所有样本全程前台、0最小化、0丢时。截图在测量结束后采集。

| 顺序 | 全前台帧数 | 最大积压 | 撞后首2模拟秒帧时P95 | 恢复区第2–5模拟秒P95 | 恢复区最大帧 |
| --- | ---: | ---: | ---: | ---: | ---: |
| A1原交接 | 1234 | 322.756ms | 12.109ms | 10.025ms | 64.477ms |
| B1候选 | 1257 | 309.173ms | 11.783ms | 9.938ms | 51.719ms |
| B2候选 | 1208 | 332.152ms | 12.052ms | 10.387ms | 77.160ms |
| A2原交接 | 1230 | 319.854ms | 11.826ms | 10.561ms | 76.606ms |
| 正式版 | 1198 | 338.258ms | 12.524ms | 10.225ms | 83.384ms |

四次反向对照没有稳定降低最大帧或积压，不按B1最好值宣传提速。正式版0.338秒积压也不能与更早轮次负载不同的1.014秒直接归因比较。保留本轮修改的依据是明确的交接顺序和异常清理回归，而非“卡顿已修好”。当前[正式窗口实图](reply-handoff-current.png)已实看，视觉保持；截图不证明流畅。

B2的77.160ms恢复帧中，快照往返25.220ms、相机往返46.588ms；权威相机本体2.028ms、对应_reply2.083ms。A2相机本体8.331ms、对应_reply30.663ms。前者说明即使查询和回包一旦开始能够较快结束，消息开始处理之前仍会等；不能只把两端等待差值叫作管道传输成本。仍有物理超预算及线程开始处理消息的等待，下一继续沿该分界定位，不能靠延迟显示、瞬移或减少精度掩盖。

完整帧/峰值分项、对应权威步骤/回包/GC和实际模块SHA见[reply-handoff.json](reply-handoff.json)。各原始目录在`logs/visual-extend-20261028/reply-handoff-window-{A1,B1,B2,A2}`与`reply-handoff-production-window`。父/子进程源模块路径已核对，B仅session/session_clock/session_process来自隔离候选，物理模块均是同一生产实现。

## 检查、失败与保持

- 原实现运行新增回归，正常/查询错误/发送失败三项均按预期失败。原源码保存`reply-handoff-production-before/`，原始失败日志为`reply-handoff-original-regression.log`。
- 隔离测试入口首轮缺少__main__保护，含独立进程测试时出现失败并停滞，已确认并停止本次测试进程，记中断/未通过；没有停止其它程序。补入口保护并先加载simulation后，隔离相机回包/时钟/独立进程完整18项通过/4.24s。首轮日志保留，不算通过。
- 原直接查询回归调整为检查世界锁互斥及异常释放；完整相机通道交接由更强的新回归检查，包含故意阻塞发送时下一拍仍不能推进。未放宽时钟/物理/数值断言。
- 正式T1覆盖完整camera_reply_handoff、session_clock、session_process、snapshot_wire、mode_lifecycle、joint_world_queries：**27项通过/6.72s**，全src/tests/tools Ruff和0/17/23各1200步种子全部通过。没有重跑上一轮110项内核测试；其机械/原生实现SHA保持，此处不把历史结果冒称本轮重跑。
- 旧悬空对称制动收敛失败仍按前轮原版同值复现记录开放，本轮未重跑。没有完整碰撞模块、全模式手动体验或长期性能Gate通过结论。
- 180份顶层生产文件仅session.py、session_clock.py、session_process.py变化，其余177份保持；所有原生模块/物理计算源码与视觉资源登记保持。PERF94中88份保持、6份明确更新，补本轮测试登记后97；视觉113中107份保持、6份明确更新，补后116；两登记全部匹配。旧登记另存B盘。
- 诊断工具`--source`现在预载session_process，保证父/子进程选择同一候选；权威报告补这三个会话模块的真实路径和SHA，结束后采集，不改变测量中的模拟推进。
- 试验窗口全部正常结束，当前无保留预览。设计38、地区规格39、其它UI/模式/试验台及高速山体UV误平铺/粗盒城市仍未完成，总目标active。

主要命令：

```text
.venv/Scripts/python.exe -m pytest -q tests/test_camera_reply_handoff.py
.venv/Scripts/python.exe logs/visual-extend-20261028/reply-handoff-candidate/run_tests.py -q tests/test_camera_reply_handoff.py tests/test_session_clock.py tests/test_session_process.py
.venv/Scripts/python.exe tools/performance/check_post_impact_window.py [--source logs/visual-extend-20261028/reply-handoff-candidate/src] --workspace <玩家vehicle.json> --output logs/visual-extend-20261028/reply-handoff-window-<A1/B1/B2/A2>
.venv/Scripts/python.exe tools/validate.py T1 --tests tests/test_camera_reply_handoff.py tests/test_session_clock.py tests/test_session_process.py tests/test_snapshot_wire.py tests/test_mode_lifecycle.py tests/test_joint_world_queries.py --output logs/visual-extend-20261028/T1-reply-handoff --timeout 300
```

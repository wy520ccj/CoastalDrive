# 共享车库展示的实际网格取景

2026-10-23；基线`85c24ca6`，单线本地施工，无推送。本轮接续已有01/12/15等设计的车辆主体构图，没有重新生成或声称重新浏览参考图。上个目标回合有实际实现和渲染证据，属于progress；总目标仍active。

旧代码使用各部件包围盒八角，部分角落在车身之外，保守留白使车偏小。本轮以三角形实际引用的顶点计算投影；默认角度35°→55°，保留原展示框/90%宽和75%高上限、向下偏移及左右旋转。最终镜位重新投影再居中。几何按车型/配置缓存，换漆不重复提取。共享首页/车库/暂停/结果受益，工程固定镜头与道路相机不变。

## 测量与验证

`mesh-framing/compare.py`从固定基线Git源码调用原orbit，在同一实际BRZ、同一透视镜头下比较；不创建窗口或物理世界。原始`comparison.json`包含全部三种比例/三种算法与单次诊断耗时。BRZ 56204个唯一引用顶点；宽高比2.17时：

| 方法 | 车身实际占展示框宽度 |
|---|---:|
| 基线包围盒，35° | 56.05% |
| 实际网格，35° | 61.47% |
| 实际网格，默认55° | 75.51% |

批量网格投影单次约36–41ms，旧角点约4ms，这是一次静态诊断而非运行性能Gate；计算发生在显示重建/旋转，正常不逐帧运行。没有以画面变大宣称提速。地面反射/车身光照融合仍有差距。

- 针对性T0：`tools/validate.py T0 --tests tests/test_garage_framing.py tests/test_career_ui.py::test_garage_reserves_vehicle_area_and_directional_focus_follows_the_layout --output logs/validation/GARAGE-DESIGN-02-framing-T0-v2`，8项通过。
- 相关T1：`tools/validate.py T1 --tests tests/test_garage_framing.py tests/test_career_ui.py tests/test_results_keyboard.py tests/test_driving_mode_ui.py --output logs/validation/GARAGE-DESIGN-02-mesh-framing-T1`，33项及0/17/23各1200步通过。新7项逐车覆盖三种视口比例、四个角度，完整引用顶点不裁切；同时抽取点和Panda原生Lens.project核对矩阵/film offset。
- 旧正常布局测试及采集工具从包围盒断言改查实际网格。没有改车模/材质、权威物理、硬件、成长、存档或规则；`manifest.json`固定5个变更源码SHA和10个保持文件相对基线的SHA。
- T0/T1摘要及原始日志压缩字节见`mesh-framing/`；没有T2/T3、完整赛事或人工审美/手感结论。旧完整驾驶明确复用。

## 实际页面

命令均以`.venv/Scripts/python.exe`运行，星级与成绩隔离为显示夹具，不访问玩家存档：

```text
tools/garage_design_capture.py --output logs/validation/GARAGE-DESIGN-02-framing-first --size 1280 720 --car game-tuned --only cars
tools/garage_design_check.py --output logs/validation/GARAGE-DESIGN-02-mesh-framing-flow --size 1280 720 --car game-tuned
tools/driving_summary_check.py --output logs/validation/GARAGE-DESIGN-02-mesh-framing-summary --size 1024 768
tools/garage_design_capture.py --output logs/validation/GARAGE-DESIGN-02-mesh-framing-1024 --size 1024 768 --car coastal-roadster --only cars upgrade-suspension paint --stars 18
```

四命令均passed；分别1/12/17/3张实际截图。已重点查看宽屏BRZ选车/改装、4:3 Elise悬架、4:3结算；目录精选12张原图跨机器归档，原始全部33张仍在对应logs目录。正常流程覆盖购买安装/恢复、涂装预览取消/保存、旋转、返回赛事和显示缓冲无累积；该流程240新道路显示拍，无完整驾驶。暂停/结果命令四次装载各60拍，共240装载拍、0新驾驶拍；快照逐截图保持，5显示窗口/160GUI稳定。其余纯采集0新驾驶拍。两种拍数分别记账。

## 中断与未采用结果

- 首个图形诊断进程停在渲染等待，无图/无摘要；确认owned PID50052及命令后终止，原exec22030 exit1。不是验证通过，也不据此认定生产故障根因；后续改为无窗口数学探针，再由正常采集获得最终图。
- 首次T0输出目录与2026-10-22旧包同名，validate拒绝覆盖，未执行；改用`framing-T0-v2`新目录通过。没有覆盖或重新计入旧版本T0。
- 当前仅完成取景改善，车辆与地面融合、道路细节、整体审美/驾驶趣味性仍待继续处理与用户体验，任务包保持in_progress。

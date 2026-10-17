# LAB-TIMELINE-06 时间轴真实拖动

- 状态：done（自动与原生窗口输入/渲染检查完成；用户新窗口体验待确认）；基线main/6c6ddba，开始前工作区干净。
- 用户复现：实验运行时滑块始终在右端；结束后拖到中间，t仍为30.000s且画面不变。
- 时间轴含义：已计算记录的回看游标；运行中跟随最新完成拍，因此在已记录范围右端。不是百分比进度条。
- 范围：时间轴输入事件、文字提示及相关原生输入/渲染检查；不改物理、工况或120Hz记录。
- 验收：真实窗口鼠标拖动改变时间/车姿/曲线游标/遥测，暂停和完成/载入记录均可；运行中拖动暂停计算；程序跟随最新样本不能误暂停；释放到控件外不留下拖动状态。
- T0：lab UI相关测试。T1：lab模块+三种子；额外原生窗口输入拖动检查，不用直接调用seek或人为设pointer_pressed代替真实链路。

## 原因与修复

- 原生窗口复现：滑块控件收到thumb-press，全局mouse1为0；旧逻辑监听全局mouse1并结合父/子hover决定pointer_pressed。DirectGUI默认suppressMouse使全局事件不进入，滑块原生值已变但seek直接返回。
- 用6c6ddba的lab_application/工作台源码只读覆盖导入，其余模块保持当前；窗口输入设备连续拖动得到滑块0.347327s，显示仍为1.000s/第120拍，broken_observed=true。原生事件为thumb-press、无全局mouse1；源码未回滚工作区。
- 改为滑块/滑块按钮自身B1PRESS/B1RELEASE驱动；全局释放仅补控件外收尾。释放前读取PGSlider当前值，避免延迟ADJUST尚未同步DirectSlider选项时丢失最后位置。程序设置游标仍不会启动拖动。
- 点击轨道的pageSize改为当前记录全长、scrollSize=0，由原生PGSlider直接跳到点击处；原.001秒步长小于120Hz样本间隔。扩大命中区并标明“时间轴 · 点击/拖动回看”。参考[Panda3D 1.10.16原生实现](https://raw.githubusercontent.com/panda3d/panda3d/v1.10.16/panda/src/pgui/pgSliderBar.cxx)的advance_page/拖动行为；物理及记录未改。

## 验证与证据

- 普通T0：`tools/validate.py T0 --tests tests/test_lab_ui.py --output logs/validation/LAB-TIMELINE-06-T0-fixed --timeout 300`，Ruff/36项通过。首次T0因新增工具import排序失败，保留原日志。
- Double T1：`tools/physics/run_sim_double.py tools/validate.py T1 --area lab --tests tests/test_design_loop_ui.py --output logs/validation/LAB-TIMELINE-06-T1-double --timeout 300`，Ruff/172项及0、17、23各1200拍通过。随后仅删除无读取的timeline_target字段，并以Double最终T0完整36项覆盖；未重复全部T1。
- 原生普通/Double：`tools/lab_timeline_check.py --output logs/lab-timeline-06/{normal,double}-final`（Double经隔离启动），均通过。只向本工具窗口移动指针并注入buttonDown/Up；不直接调用seek、不设置pointer_pressed。检查完成记录拖动、轨道点击到第96拍、载入记录并移出控件释放到第72拍、运行中拖动暂停到第12拍；回看前后权威tick保持、车姿匹配对应快照、时间与遥测一致。查看两份实际渲染，曲线游标/readout同步到0.367s及0.100s。
- 工具初次把指针直接从末端跳到中间，未产生连续thumb移动，不能算原生拖动复现；改为48段连续位移后旧版复现、新版通过。辅助探测失败/未复现日志保留，未计为通过证据。
- 基线、普通/Double原生summary、验证summary及截图见`docs/evidence/LAB-TIMELINE-06/`。不跑T2/T3或车辆性能/物理数值对照，旧用户窗口和已有记录不改动。

## 交付

- 6c6ddba..本任务提交；本地提交，不推送。
- 用户当前30秒记录可能仅在旧窗口内存中；先导出，再重开原启动器并从“记录”载入即可回看。旧进程不自动热更新，新版人工操作待确认。

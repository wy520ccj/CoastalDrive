# WORKSPACE-01 同一窗口内的驾驶—实验过渡

- 状态：done（实现与自动验收完成，用户体验待确认）；基线main/daec9b3，开始前工作区干净；单条施工线。
- 用户目标：游戏与实验台像同一应用，切换不重开窗口、不重置尺寸，加载有统一画面和真实阶段进度。
- 架构：CoastalDrive保留唯一ShowBase/窗口/渲染管线，VehicleLab成为使用该窗口的实验视图；独立实验室检查入口仍可自行创建窗口。输入监听分属各自工作方式；旧物理会话关闭后才进入下一方式，实验工作区数据继续保留。
- 加载：同一幅“工程车从试验室驶向海岸公路”的像素插画，原生中文文字、车型卡和阶段进度条；按实际已完成阶段推进，不伪装成耗时百分比。没有新增Manager/Page框架。
- 范围：窗口/视图生命周期、加载UI/插画、实验窗口组合与必要调用方适配、相关验证。物理、参数、固定步、原生扩展、交通/输入调校不变。
- 验收：窗口对象/系统句柄/实际尺寸在往返前后相同；放大/非默认尺寸保持；加载先绘制再做阻塞工作，无未遮盖黑帧；阶段单调且有中间帧；真正独立游戏会话关闭，实验参数/记录恢复；多次往返任务/事件/显示区不累积；普通与Double实际渲染、T0/T1。
- 人工视觉/操作体验待用户确认；自动渲染不代填。T2/T3与车辆实时/精度Gate不在此包。

## 实现与验收

- `main.py`只建立一次CoastalDrive；普通/双精度`--lab`也进入该应用，未保存车辆时保留参考后驱默认。实验台使用显式`engine`组合，独立检查仍可创建自有窗口；调用方直接访问渲染环境，无兼容代理或页面管理层。
- 游戏输入监听独立于ShowBase窗口事件；过渡时停用当前输入/更新。先关闭旧物理会话，再建立下一会话；实验台完整工作区只交接数据。返回重置相机视口/画幅比例，并同步当前窗口焦点；试驾重新开始行程。
- 同一渲染管线与窗口保留。道路视觉可缓存，不保留第二物理世界；实验与道路视图关闭时释放阴影缓冲。初次连续往返暴露缓冲数5/6/7递增，修复后稳定3（主窗口及渲染缓冲总数），不是3个系统窗口。
- 原生加载层先经历正常绘制再执行同步加载，插画/车辆信息/实际阶段推进；菜单进公路共用该界面。失败保留覆盖层与退出按钮，记录runtime.log。生成插画来源已入素材账，中文和进度均由原生UI绘制。

### 自动检查

- 普通T0：`tools/validate.py T0 --tests tests/test_workspace_transition.py tests/test_lab_ui.py tests/test_design_loop_ui.py tests/test_vehicle_design_entry.py --output logs/validation/WORKSPACE-01-T0-r2 --timeout 300`，Ruff与55项通过；驾驶辅助UI另4项通过。
- Double T1：`tools/physics/run_sim_double.py tools/validate.py T1 --area lab --area design --tests tests/test_workspace_transition.py tests/test_driving_mode_ui.py --output logs/validation/WORKSPACE-01-T1-double --timeout 300`，Ruff与205项、0/17/23各1200拍通过。
- T1后补齐首次实验室默认车、加载结束焦点同步和背景色、验证入口映射，删去游戏多余engine自引用；普通最终T0 25项、Double最终T0 11项及最终兼容检查8项覆盖对应改动。未重复整套T1。
- 普通真实独立游戏进程：`tools/workspace_transition_check.py --output logs/WORKSPACE-01/normal-r4 --onscreen --independent`三往返通过；窗口句柄986104、1180×760六次不变，任务/显示区/图形输出/游戏事件均为11/4/3/54。
- Double真实独立游戏进程：`tools/physics/run_sim_double.py tools/workspace_transition_check.py --output logs/WORKSPACE-01/double-r2 --onscreen --independent`通过；句柄1313766始终不变，1180×760后手动请求放大1600×900，后续往返维持；11任务/4显示区/3图形输出/54游戏事件/68GUI控件稳定。试验B、A、未运行cg=.47、游标第2拍、已应用cg=.42分别核对；每次返回后通过窗口输入设备重新输入小数，声音会话关闭并重建。菜单→公路同一加载流程通过。
- 真实`main --lab`：`tools/physics/run_sim_double.py logs/WORKSPACE-01/entry-check.py`，无已存车辆从参考后驱进入，经菜单再进实验台，同一系统句柄919506和cg=.478草稿保持；实际界面查看通过。
- 独立实验窗口兼容：`tools/physics/run_sim_double.py tools/design_loop_check.py --output logs/WORKSPACE-01/standalone-compat --ui-only`通过，含参数/记录/A/B恢复与重启。该工具只检查三入口动作绑定；真实同窗往返以新工具为证。
- 查看普通加载/道路、Double恢复实验台和直接入口实际图像；107张阶段/就绪截图均有非黑画面。只证明采集到的帧，未逐帧录屏；同步初始化期间保留上次完整加载画面。工具含截图写盘，所记约3.3–7.9秒不作为交互性能基准；首次单次场景准备约2–4秒仍会在当前阶段等待。

### 失败与范围

- 早期Ruff导入排序、旧测试仍假设退出重建、工具对已关闭Process调用is_alive、未等待尺寸请求、隐藏高级参数框输入、阴影缓冲累积均保留原日志；最终对应检查已通过。一次窗口采集中系统尺寸从1180×760外部变为2560×1494，工具如实失败，未作为保持尺寸证据。
- 首次T0命令重复传`--tests`，解析只保留最后模块（4项），不计作55项结果；r2使用一次参数列表补齐范围。
- 物理、固定步、驾驶调校、五个原生扩展未改。人工流畅性/画面/声音试听待用户体验，T2/T3和原实时/物理精度Gate未跑。本批未推送，用户既有窗口与记录未覆盖。

## 交付

- 基线daec9b3至本任务本地提交；生成背景、功能代码、调用方适配、测试、操作说明和证据同批提交。
- 证据在`docs/evidence/WORKSPACE-01/`；命令完整日志在上述logs路径。重开原有启动器即可使用；仅在旧窗口内存的记录先导出，再重开载入。

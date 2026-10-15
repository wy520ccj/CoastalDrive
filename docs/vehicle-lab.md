# 车辆动力学实验室

2026-10-15集成状态：权威车辆动力学核心 + 自由驾驶 + 工程实验工作台。车辆硬件、输入辅助、实验工作方式分别选择。GAME/SIMULATION保留兼容；当前游戏入口在配置边界选120 Hz单次机械求解，实验台沿用设计配置每拍两次机械子步。该积分取舍及数值对照见[游戏任务](tasks/GAME-DRIVE-01.md)，不能把两者当作逐拍相同的积分配置。

## 工作流程与参考

配置车辆和工况 → 运行真实固定步 → 观察信号与动画 → 比较两次结果 → 导出可复现记录。借鉴成熟软件的工作流程，不复制其商业模型或宣称同等精度：

- [CarSim VS Visualizer](https://www.carsim.com/products/supporting/visualizer/)：结果动画与曲线分析。
- [CarSim GUI](https://www.carsim.com/products/supporting/sgui/)：车辆、工况、曲线配置。
- [IPG CarMaker](https://www.ipg-automotive.com/solutions/product-portfolio/carmaker)：车辆/道路/驾驶员与测试工作流。
- [MathWorks 车辆工况](https://www.mathworks.com/help/vdynblks/vehicle-reference-applications.html)：制动、定圆、阶跃转向等预设试验。

## 已实现的工作流

1. LAB-01：制动实验、120 Hz 真实信号、离线暂停/单步、时间轴回放、固定 A 与候选 B 叠加、CSV/完整模型/快照/HTML报告导出。默认无交通，沿用生产 Simulation 和机械子步。
2. 精确执行器：前轮目标转角以度输入，油门/制动/离合为比例，挡位独立设置。电子油门和四轮实际制动压力独立于踏板请求记录；ABS、ESC与车型分开选择。
3. LAB-02：阶跃/正弦/固定转角开环工况；定圆和参考双移线的真实闭环路径驾驶员；对开附着制动。双移线是3.5m研究路径（20/30/20/30m段），不标作ISO认证试验。定圆/双移线路径误差由驾驶员和整车共同决定，不能解释为车辆模型单独的精度。
4. 重放与复算：动画只读取历史快照；同版本复算逐拍施加原始执行器命令。源码摘要不同、失败/碰撞/复位终止记录不进入自动复算。载入时核对完整车辆文件、二进制快照SHA、120Hz时间及每一行信号与快照的一致性。
5. 对开路面：实际接触点x小于初始车身x采用左侧μ，其余采用右侧μ。生产接触接口内部仍以asphalt/grass分类承载两侧材料；两侧滚阻设置相同，仅改变附着。车轮跨界后按实际位置重新分类。

驾驶员采用[Pure Pursuit几何路径追踪](https://www.mathworks.com/help/nav/ref/controllerpurepursuit-system-object.html)与速度PI，预瞄max(6m, 1.2v)，P=0.20、I=0.08；饱和仅对应实际转角/踏板范围。短预瞄0.55v的初始候选会放大整车/转向响应延迟，已撤回；真实路径误差与输入一并保存。参考[定圆](https://www.mathworks.com/help/vdynblks/ug/constant-radius.html)、[双移线](https://www.mathworks.com/help/vdynblks/ug/double-lane-change-maneuver.html)的工况组织方式，不复制其模型或认证口径。

## 所有权与时间

游戏和实验室在入口切换时释放上一个会话/世界，再建立下一个。每次实验只有一个 Simulation；界面只读取完成步 Snapshot。独立lab场地是无障碍均匀平面，旧test场地/障碍不改动。落地后使用同一世界推进8个制动时间常数释放锁车压力，再设置初始滚动速度。全部初始快照保存，计时从初值设置后开始。离线运算按 1/120 s 逐拍推进，窗口刷新不决定积分步长，暂停与回放不推进物理。计算时间是物理步/快照的累计墙钟时间，不含初始化、界面等待、暂停和导出；动画不作为实时性能证据。停车条件采用水平速度模≤0.1m/s，距离为实际三维行驶路径长度，避免车辆横滑/旋转时仅纵向速度过零就判停车。

## 模型依据

保留 VehicleDesign 的原始 basis 与完整配置。GR86 的公开硬件、工程推导和待标定参数沿用车辆配置文件及 PHYS-REAL-01 原始证据；实验计算结果不等于实车标定成绩。前后驱参考车是明确的设计模型。

## 启动与操作

双击 `launchers/vehicle-lab.cmd`，或用项目 `.venv/Scripts/python.exe src/main.py --lab`。当前公开0.8.3试玩包没有该新增实验室；这是主目录源码入口。

先以100km/h、μ1.1、ABS开启运行直线制动，完成后固定当前为A；改μ0.6后开始第二次试验。主屏显示A/B停车距离、差值和两张曲线。高级参数内可改时长、转角、质心、定圆半径、右侧μ、转向起始时刻和ESC。曲线组、详细信号、时间滑块支持逐点分析；记录菜单可载入/复算/打开报告。暂停Space、单步`.`、Esc先关闭弹层再返回驾驶；输入框编辑时快捷键不触发试验。

`export`每次新建独立目录，包含signals.csv、vehicle.json、experiment.json、snapshots.bin、report.html；有A基线时另存baseline-A及comparison.json，比较列出全部改变条件。默认结果保存在用户数据experiments目录，可用`--output`指定。

## 设计与验证

布局依据用户认可的[生成设计参考](design/vehicle-lab-reference.png)，正文为Source Han Sans SC Bold，标题使用当前品牌字体。默认保持两张主曲线，参数/详细信号折叠；旧VI菜单截图不作为设计依据。规范及生成说明见[设计记录](design/vehicle-lab-design.md)。

自动功能与实际渲染证据见[evidence/LAB/README.md](evidence/LAB/README.md)。T2默认海岸10000拍旧求解失败在隔离本轮入口/场地改动后仍复现；本轮不调整方程、20轮上限或阈值。实验室新工况短测通过不代表整个物理阶段或13车实时Gate通过；人工操作/画面体验待确认。

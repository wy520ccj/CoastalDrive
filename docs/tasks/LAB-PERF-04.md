# LAB-PERF-04 试验台有限接触与四轮端口批量原生化

- 状态：done（本功能块完成；持续优化总目标active）
- 基线：82ba3ca，main，工作区干净；前一持续目标轮次已提交实际优化，属于progress。
- 目标：继续降低试验台独立轮心完整步耗时，不降低物理效果、精度、真实有限几何或工程模型能力。
- 范围：独立轮心tire_ports及有限接触梯度/正交基批量C计算，沿用既有支持函数/胎冠割线；新增原生入口不更改游戏入口或共享世界行为。
- 允许：unsprung_drivetrain.py、unsprung_contact_geometry.py、独立lab_contact_native.h、wheel_contact_kernels.c的新增注册/include及setup.py构建依赖，必要测试/比较工具/证据。
- 保持：120Hz/两机械子步、34变量、真实道路中点/末点查询、原浮点运算次序、Newton/差分epsilon/阈值、原完整模型与参数。
- 验收：随机和实际有限接触/端口对旧实现逐位对照；完整制动ABBA、转向与非线性实体凸起A/B全部快照/信号/命令/共同解/能量账一致，CPU/墙钟/P95/P99及初始化分开。旧/新实际扩展导入路径与SHA完整记账。
- 验证：相关T0、Double试验台完整专项/真实记录复算；游戏seed/window不在用户范围，通用T1/T2/T3、人工与实时Gate继续开放。
- 原源码与五扩展保存builds/lab-perf-04/baseline，不切换/重置工作树；仅本地提交，不推送。持续优化总目标保持active，不把这一功能块当总目标完成。

## 完成结果

- 两项严格浮点C批量入口已接通，复用原支持函数/胎冠割线；旧wheel C代码除include/注册完全相同，共同求解器不变，仅wheel扩展重编。
- [证据](../evidence/LAB-PERF-04/README.md)：完整制动ABBA 2.490→2.003s（−19.57%）、转向4.964→3.945s（−20.53%）、非线性实体凸起31.692→28.018s（−11.59%）。初始化/CPU/P95/P99单列；八次完整实验/960子步的完整payload逐字节相同。
- 800组随机非连续端口输入、108组实际Plane/Box/微小运动/腾空梯度对原公式逐位相同；18组额外旧/新求解输入所有数值和能量位模式相同。
- Double初始T0 33项、数值接入64项通过；最终普通SDK T0 82项、Double试验台29模块271项完整回归/Ruff通过，含实际记录保存/加载/复算。按用户范围不跑游戏seed/window，通用T1/T2/T3未跑。
- 六拍采样残差1692次/真实道路查询1122次/端口组装552次保持；前采样复用并核对旧03样本源码/扩展SHA，不做跨时段耗时拼接。
- 构建：项目Python `setup.py build_ext --inplace --build-temp builds/lab-perf-04/native`；完整对照`tools/performance/compare_lab_compute.py --baseline builds/lab-perf-04/baseline --output logs/lab-perf-04/complete-AB`。实际完整命令/二进制/日志与失败说明归档。
- 无物理失败或超时；新测试初始两个未用导入已修复。全部B测量实际源码/扩展SHA与最终代码一致；包完整性核对通过。
- 下一：按新采样继续真实径向道路查询和共同残差组装，保持原精度和完整输出验收。实时/人工/既有完整能量Gate开放，总目标保持active。

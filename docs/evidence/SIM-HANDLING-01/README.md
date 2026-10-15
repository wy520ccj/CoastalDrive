# SIM-HANDLING-01 工程信号与指标

基线b2fa419，codex/simulation-fidelity，C:/Users/15120/.codex/worktrees/simulation-fidelity/CoastalDrive。只改实验记录/分析/显示；完整物理、120Hz/两子步及另一AI施工的main保持。原轮胎485项有效结果复用。

## 工程意义

ABS/制动力分配可用MFDD、压力、滑移及各轮附着利用率分析。MFDD用80%→10%初速的水平路径距离平均，不是瞬时峰值；对开附着曲线路径仅作工程比较，不作为直线制动合格结果。利用率用同一末子步Fx/Fy和D，不混入完成步sample_grip，不夹到1；离地未定义，残差单独提供。

α/β及实际完成步Fn、侧倾、前后LTR支持前后轴饱和/载荷转移分析。LTR=(右−左)/(右+左)，整轴无载未定义，不是翻车合格判据；水平速度≤1m/s车身侧偏未定义。横摆增益Gr=−世界z横摆率/实际中心前轮角，右转为正；尾1s速度/角度峰峰≤2%、横摆≤5%，角度绝对容差0.02°。这些为本工作台公开分析条件，不冒用法规阈值；不是方向盘增益，也不从单点推算不足转向梯度。

独立解析轨迹验证6.7m/s²减速度、交点插值和左右转同增益；反向增速、失败/碰撞、区间不足、非稳态保留原因。实测数据尚未用于标定，不把绿色测试作为实车准确度证明。

## 真实工况

`.venv/Scripts/python.exe tools/physics/lab_engineering_probe.py --output logs/SIM-HANDLING-01/probe`当时运行四工况：100km/h直线μ1.1/0.6、对开1.1/0.3、60km/h/60m定圆8s。随后独立运行同一定圆12s，原8s记录保留；工具现包含五工况以便完整复现，未重复前三个制动试验。

| 工况 | 结果 | 含义 |
|---|---|---|
| μ1.1制动 | MFDD8.9311906m/s² | 前轮峰值预算利用率约0.809，后轮约0.998，未调制动份额 |
| μ0.6制动 | MFDD5.8885996m/s² | 四轮峰值利用率约1，保留略大于1的数值残差 |
| 对开制动/ESC关 | 路径区间减速度7.2249205m/s²，侧偏峰89.82765° | 明显侧滑保留，曲线路径值不是直线制动合格结果 |
| 定圆8s | 横摆增益未发布 | 末窗角度峰峰2.417%超过原2%条件，未放宽 |
| 定圆12s | 横摆增益7.3621174s⁻¹ | 11→12s平均16.626634m/s、中心角0.03746095rad、右转横摆0.2757919rad/s，原稳态条件满足 |

所有末子步实际合力按D+√2×分量残差+1e-7核对，不改求解精度。完整记录载入后信号/快照逐值相同，运行前后源/原生指纹相同。CSV保留force_contact_tick/sample_tick和分阶段数据。

`records.zip`为冻结完整记录/命令/CSV/配置/快照/报告，含原8s、12s及制动A/B；解压后实验台可载入。`reports`保存各工程JSON/HTML，含分析生成时definition_fingerprint，与原物理记录来源分别记账。summary.json为最初四工况结果，12s工程JSON单列。旧版完整目录先按Snapshot验证已有信号再补显示字段，原文件保持；篡改和任意删字段被拒绝。

## 验证和边界

T1命令：`.venv/Scripts/python.exe tools/validate.py T1 --area lab --tests tests/test_lab_metrics.py tests/test_parameter_help.py tests/test_vehicle_parameters.py --output logs/validation/SIM-HANDLING-01-T1 --timeout 180`，34项/Ruff、0/17/23各1200拍通过。T1后A/B面板、报告指纹与增强检查由13项final-T0、12项export-T0及两尺寸GUI覆盖；不重复相同物理长测。T0初轮12项通过。

GUI：`tools/lab_engineering_ui_check.py --records logs/SIM-HANDLING-01/probe --steady-record logs/SIM-HANDLING-01/steady-radius-12 --output logs/SIM-HANDLING-01/release-720 --height 720`，1080同入口。实际记录载入/悬停F1/Esc返回工程层/A/B/四组曲线/公式与原因布局通过，每尺寸8图；代表图已目视，没有创建物理世界。普通帧缓冲告警存在。

T2/T3/人工体验未执行；主目录整合、实车标定、气胎回正/外倾、簧下自由度与总体Gate仍开放。原物理485项和当前T1有效范围复用，不把本块分析进展当成整个物理完成。

## 一手依据

[UNECE定义文档](https://unece.org/sites/default/files/2022-01/ECE_TRANS_WP.29_2022_18E.pdf)给出MFDD区间及距离平均定义，本实现m/s式等价于km/h式的25.92系数；仅采用定义，未执行法规完整条件/认证。

[MathWorks操稳实例](https://www.mathworks.com/help/vdynblks/ug/vehicle-steering-gain-at-different-speeds.html)展示不同速度下转向/横向响应分析。当前用实际前轮角条件增益，未照搬方向盘角或从单点宣称J266/不足转向梯度验证。

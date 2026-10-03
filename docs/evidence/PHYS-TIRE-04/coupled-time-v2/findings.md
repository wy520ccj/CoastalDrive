# 共同积分细分诊断

冻结基线 `f2c145090d7c2342b0ba242bca8a066732748b0c`，原 BulletPlane、solver 10、split impulse false、轮胎子步 2，ABS/TCS/ESC 开启。每条 6 秒，外部采样与五个控制器均为 120 Hz；只有力预测、轮胎、Bullet 和 after_step 共同细分为 1/2/4/8。各控制器每条真实推进 720 次。冻结源码及诊断脚本前后 SHA 相同。

命令：`.venv/Scripts/python.exe docs/evidence/PHYS-TIRE-04/coupled_time_probe.py --output docs/evidence/PHYS-TIRE-04/coupled-time-v2`。进程句柄 65680 已退出，exit 0。原目录 `coupled-time` 的观察器失败及 not_run 保留；v2 修正的只是最后 micro 施力接触观察器，没有改控制或积分协议。

micro1 与原 `PHYS-TIRE-03/substeps/simulation-airborne-recontact-2.csv.gz` 的 721 行、393 个共享字段逐格严格相同，差异 0。原 CSV SHA256 为 `ee1fc6df25a50225617f780c83be3f140f7c84e12027a3b3eb64a3f271379ed3`。每条宏 CSV 721 行，原始 micro JSONL 分别 720/1440/2880/5760 行；全部输入、配置、能量、冲量、残差、源码哈希与账目在各目录和 summary.json 中。

|共同 micro 数|末累计航向 °|路径 m|首次停止 s|首次停止路径 m|ESC 秒|ABS 秒|
|---:|---:|---:|---:|---:|---:|---:|
|1|0.429319|63.493593|3.900000|63.432480|0.266667|2.908333|
|2|2.212811|64.236241|3.941667|64.165596|0.183333|3.033333|
|4|-7.780038|57.113652|3.683333|57.036070|0.758333|2.750000|
|8|3.911887|49.953324|3.375000|49.872406|0.241667|2.425000|

相邻航向差依次 +1.783491、−9.992849、+11.691925°，路径差 +0.742648、−7.122590、−7.160328 m，停止时间差 +0.041667、−0.258333、−0.308333 s。这组数据没有显示相邻细分收敛，不能据残差小宣称整车步长通过。

首次正法向车身 manifold 均为单个右侧点 x≈+1.05 m。micro1/2 分别在 t=0.666667 s 首次出现，法向冲量 436.773254/97.147575 Ns；micro4/8 在 t=0.668750 s 出现，冲量 966.954285/1159.380859 Ns。对应完成世界 z 横摆率为 +0.062769/+0.013907/+0.139250/+0.166795 rad/s，而车身 up 横摆率为 −0.084082/−0.018633/−0.185594/−0.222437 rad/s。保留两套坐标，不能混用。碰撞、raycast 悬架与刚体积分时序的贡献不能仅从 manifold 差额全部拆开。

前轮首次支撑在 t≈0.621–0.625 s，后轮在 t≈0.679–0.683 s。micro2/8 后轮首次支撑存在真实左右 micro 时刻差；该事件发生在前轮 ABS 指令已经分叉之后。相邻组合 ABS commanded/pressure 最早真实值差都在宏 tick 77，实际世界 yaw 最早差为 tick 80/80/81；ESC 请求最早差为 tick 82/91/82，ESC active 为 82/92/82。位置或速度更早的小差包括重力积分离散产生的实际状态差，analysis.json 给出原值；这些精确首差是定位记录，不是新的验收阈值。索引单位变化未用于判断物理分叉。

采样口径：原 run_trial 在 _step 前缓存施力姿态/接触，_step 后读取真实完成 body 速度、姿态及角速度。v2 的多 micro 观察器仅将轮胎力矩缓存更新到最后 micro 实际施力接触，并以 microdt 还原该 micro 平均力矩。宏 CSV 的 position、heading、velocity、speed、completed_yaw 和 sideslip 是最后 micro 完成即宏末值；dynamics、Fx/Fy、force slip、patch slip、变形、能量与轮胎力矩属于最后 micro 施力阶段。acceleration/lateral_acceleration 是最后 micro 的速度差除 microdt，不是整宏平均加速度。五个控制器结果在宏首 micro 按 macroDT 推进，然后保持；feedback_tick/contact_tick 等内部 tick 是 micro 索引，CSV tick/time 是外部宏索引。原耗散列仅代表最后 micro，macro_micro_sum 才是整宏累加耗散；elastic_energy 是储能，不能累加冒充耗散。

只读汇总见 analysis.json；原始时点、冲量、控制器调用计数和每轮能量保存在 micro1/2/4/8。没有修改生产源码或默认步数，没有提交或推送。

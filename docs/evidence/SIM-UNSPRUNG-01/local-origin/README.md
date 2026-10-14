# 局部原点与有限棱边验证

2026-10-14，基线bafc138，codex/simulation-fidelity独立树。正式实验场从局部原点创建；有限Box棱内部用法线锥支持函数驻点求法线。源机制、用途与边界见[坐标/棱边推导](../../../lab-coordinate-precision.md)。main和游戏场地保持；簧下开关仍默认关闭，本任务in_progress。

## 确认的原因及修复

- 原X=95m的float32相邻间隔7.629µm，小横向位移可舍入为零，转动却继续改变导向几何。相同五刚体小运动0.2s，95→0m的导向位置误差峰10.69→0.470µm、相对速度峰0.001465→0.00009154m/s。
- 保存的真实状态作独立初值，实际motor误差乘−0.2/h与下一步纠偏速度一致至1.61e−7m/s。诊断ERP零对照不进入生产；生产约束/ERP保持，没有运行中移动车辆或取消碰撞。
- 局部原点8步首次运行在第947机械步失败，已完成946步/0.9854167s。纯数值输入重放复现3.66893e−7Ns残差。Box棱内部法线几何修正后，同一输入4迭代通过：动量7.94e−13Ns、力1.17e−11N、端口零、局部能量−4.68e−12J。原1e−9Ns/1e−5N/1e−9Nm门槛保持。

## 完整真实凸起对照

相同参考配置40kg/200000N/m/500Ns/m、18km/h、10mm左侧实体Box、2.4s。各完整结果正常time_limit；原95m对照复用已保存的有效节点。

| 版本/机械子步 | 完成机械步 | 整车残差峰/J | 累计/J |
|---|---:|---:|---:|
| 原95m / 2 | 576 | 0.003230560 | −0.057585769 |
| 原95m / 4 | 1152 | 0.002997459 | −0.084126503 |
| 原95m / 8 | 2304 | 0.005229577 | +0.723039918 |
| 原点，棱边修正前 / 2 | 576 | 0.003295957 | −0.040129930 |
| 原点，棱边修正后 / 2 | 576 | 0.003302141 | −0.040149565 |
| 原点，棱边修正后 / 4 | 1152 | 0.003312474 | −0.122373686 |
| 原点，棱边修正后 / 8 | 2304 | 0.003428184 | +0.129424764 |

8步累计差改善，但2/4/8仍不单调，不能宣称完整能量收敛。新8步车身/轮端平动累计−12.604/+12.755J，角速度−0.001074J；相消仍大，沿行驶方向的绝对坐标量化、约束及全车有限步精度继续开放。没有用新耗散或道路功填账。4子步在最终源版本运行，2/8源仅早于Ruff要求的闭包变量绑定，数值算法/结果未改；两种执行字节分别保存。

## 验证与失败记账

9项局部原点T0/Ruff、36项棱边T0/Ruff、68项最终相关T1/Ruff/三种子通过。包括试验场/游戏坐标隔离、reset、真实轮心、Snapshot、记录精确复算及固定失败夹具；独立圆/棱法线按实际原生尺寸核对至2e−13。初次T0/T1因工具未使用变量/导入排序、棱边闭包绑定的Ruff失败已修，原summary保留。直接几何测试最初把名义10mm当精确原生高度而失败，改用实际原生尺寸，未放宽2e−13法线判据。CLI第一次误用--tier未启动验证，不作为通过结果。

8步r1/r2均因同一线搜索失败终止。r2已保存failure.json和failed-step.pkl，随后诊断CSV写入又因当时缺write_rows产生NameError；该辅助错误已修。r2没有completed-substeps.csv，未补造。failure.json中的summary是异常向上返回前状态，paused不表示试验完成；终端退出1和原error确认失败。夹具仅供仓库可信内部复现，不接收用户pickle；不作为工程配置导入格式。

本轮没有UI/公式资产修改，既有真实F1/两尺寸渲染复用；没有重新声明人工验收、整体Gate或实时性能通过。未合main、未推送。

## 归档与复核

comparison.json从原result提取。raw-evidence.zip保存完整CSV/峰值/原result、原失败输入及执行工具、两类原生诊断、失败和最终T0/T1日志。执行源逐SHA验证：origin-only源码由对应Git版本及原摘要恢复确切字节；早期2/8模型保留在原执行归档；最终4步对应executed-model-final.zip。原JSON摘要没有回填为当前源码。manifest记录各原文件与归档摘要。

使用项目venv，输出必须新目录：

```
.venv/Scripts/python.exe tools/physics/unsprung_origin_check.py --output logs/SIM-UNSPRUNG-01/origin-small-motion-r2
.venv/Scripts/python.exe tools/physics/unsprung_guide_checkpoint_check.py --input logs/SIM-UNSPRUNG-01/native-kinetic-parts-8-r1 --output logs/SIM-UNSPRUNG-01/guide-checkpoint-r2
.venv/Scripts/python.exe tools/physics/lab_energy_check.py --output logs/SIM-UNSPRUNG-01/lab-origin-edge-energy-4-r2 --maneuver ride_bump --duration 2.4 --substeps 4
```

下一继续完善全车有限步/原生导向精度及真实颠簸制动A/B；旧10m不等轮端自由落体门槛、实测、人工和整体目标仍开放。

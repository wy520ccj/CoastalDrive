# 独立双精度实验室

2026-10-15合并注：本文0944541来源现已合入主目录main；下文“仿真工作树/未合main”为原施工时点。当前主目录使用相同三个launchers入口，SDK从随Git保存的归档恢复至本地build，不覆盖普通环境。当前合并与版本纠正见[任务](tasks/INTEGRATE-NEW-LAB-01.md)。

2026-10-15，仿真工作树codex/simulation-fidelity，基线7c65e65。已实际构建并运行Panda3D 1.10.16/双精度Bullet，运行版本报告285，数学类型LPoint3d。常规环境仍为原Panda/Bullet284/LPoint3f；两者不在同一进程混用，未安装或覆盖共享.venv。

## 使用

- `launchers/vehicle-lab-double-preview.cmd`：显式开发预览，导入已有完整独立轮心工程配置。保留“非实测/整车验收未完成”标识。
- `launchers/vehicle-lab-double.cmd`：双精度SDK中的普通实验室，车型默认配置保持。
- `launchers/vehicle-lab.cmd`：原有普通运行环境。

左侧标明实际32/64位精度，报告也保存该精度。实验文件新增首末运行库摘要；同一源码而运行精度或库内容不一致时，允许查看已有数据，拒绝宣称确定性复算。旧记录仍可载入，未保存运行时的记录不能新声明确定性复算。

当前SDK位于本树`build/sim-double-runtime/panda-source/built-double`。如构建目录丢失，用本树Python恢复已归档Windows x64/CPython3.14运行时：

```
.venv/Scripts/python.exe tools/physics/restore_sim_double_runtime.py
.venv/Scripts/python.exe tools/physics/run_sim_double.py --check
```

23.47MiB的runtime.zip及成员SHA随证据保存。已将完整构建产物移到同一build目录的备份，实际从归档恢复后重新通过SDK类型、旧自由落体、颜色边界和真实跨精度记录检查；恢复没有依赖编译器临时对象。未验证其他操作系统/Python ABI。

## 构建与边界

Bullet由官方2.84源构建4个静态库，`USE_DOUBLE_PRECISION=ON`、MD运行库、关闭fast floating-point、使用`/fp:strict`；Panda桥接显式`BT_USE_DOUBLE_PRECISION=1`，全Panda以`STDFLOAT_DOUBLE=1`重建。保留现有物理方程、参数和唯一Simulation/120Hz世界，没有补偿速度或添加耗散。

实际Bullet和Panda构建日志已归档，Panda构建成功用时3分25秒。统一重建脚本按此次已执行的命令整理，未为验证脚本再次完整重建：

```
.venv/Scripts/python.exe tools/physics/build_sim_double_runtime.py --prepare --output logs/SIM-UNSPRUNG-01/rebuild-new
```

官方源/工具的URL与SHA见前一准备证据和本地prepared.json。重建修改仅限build；原游戏及共享包保持。Shader球谐颜色数组明确要求32位：隔离simplepbr只在写GPU数组边界转换，CPU投影和物理数学保持其原算法/双精度，不改原反射资源。

## 实际结果与作用

相同18km/h实体凸起2.4s，真实2/4/8机械子步完整576/1152/2304步：

| 子步 | 累计原始储能残差/J | 单步绝对峰/J |
|---|---:|---:|
| 2 | −0.002351595 | 0.0000445594 |
| 4 | −0.001235970 | 0.0000123344 |
| 8 | −0.000633875 | 0.0000031734 |

累计差近似按步长缩小，峰值近似按步长平方缩小。2子步原生车身速度峰差3.28e−12m/s，轮心9.77e−10m/s，剩余主要是悬架有限姿态/行程几何差。此前单精度累计差−0.026651/−0.081159/+0.136451J不能证明同样收敛。本结果是一个完整凸起工况的数值进展，不声明所有操纵/碰撞工况或完整有限姿态能量闭合通过。

60km/h手动0.125s累计−0.001219613J，仍有有限悬架项。旧10m、不等轮端质量38/41/40/39kg的真实自由落体速度峰差2.01e−14m/s，通过原5e−7门槛。40kg/轮颠簸制动4.021406m，全部状态/信号/命令复算完全一致；普通运行时4.021412m。该距离差约5µm，不能夸大为制动性能收益。

本升级使小力响应、动量/能量核对和步细化更可信，便于区分轮胎/悬架机制与计算底限。质量、惯量、轮胎标定、液压/ABS和悬架K&C仍按实际参数/数据验证。完整有限姿态、K&C/实测、人工及整体目标继续；常规实验室默认力学尚未切换。详见[证据](evidence/SIM-UNSPRUNG-01/double-runtime/README.md)。

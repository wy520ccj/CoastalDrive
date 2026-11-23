# 组合弯求根异常与后台油耗状态

2026-11-01。本轮修复此前约1088米的实际机械异常，并补齐完整车辆子步的油耗数值边界。未提交、未推送；价格、其它关卡、真人评级、T2和实际体验仍待完成。

## 从失败输入定位

原输入SHA256为`fbe0d793b769672faf6c08b35c90d8a4a174a917c35de9521e1b7ec4bf9dcb33`，仍保留在`logs/challenge-rebuild-20261031/bend-v2-mechanical-input/failed-input.pkl`。原世界候选盒未保存，重放清空空缓存、使用同批182组完整支持几何；不声称所有查询与原世界逐值等价。此前三次道路驱动、三次冻结重放均报相同错误。

`tools/physics/build_shared_trace.py`复制当前C/头文件到独立目录，保持严格浮点编译选项，只在失败时记录末十轮和候选残差。原模块不受诊断日志影响。输出在`logs/challenge-rebuild-20261101/shared-trace`和`shared-trace-candidates`，各有源码哈希、构建日志和完整重放日志。

第20轮，车身第0角速度残差为`1.2580214647783805e-14`，超过原`1e-14`容差；第3/4转子约545.8rad/s，原容差允许一个ULP，即`1.1368683772161603e-13`。完整Newton候选所有坐标均满足各自原容差，但最大绝对残差变成这个转子ULP，因此被原线搜索拒绝。它只接纳1/128步，让车身残差缓慢下降，第30轮仍为`1.1723261250651262e-14`。这证明问题在选步与停止准则不一致，不是需要降低精度。

两条共同求解入口现增加同一个`shared_state_converged`判断：保留原下降规则，同时接受已满足全部原逐坐标容差的候选；下一轮仍经过原停止/可行分区检查。30轮、角速度/端口容差、物理方程和硬件均保持。没有增加迭代次数、捕获后继续或修改碰撞。

## 回归与完整试车

- 新夹具在`tests/data/challenge-handling-shared`，压缩后839630字节，来源/哈希另记。`test_challenge_solver.py`用同一可信输入分别检查连续原生与原回调路径，原版两项均报同一ArithmeticError：`shared-regression-red.log`。修复后两路均可三次重复求解，法向残差`1.5006662579253316e-11`、轮胎残差`3.2546832235141576e-05`、悬架能量残差约`1.51e-14`，均满足原门槛。
- `shared-converged-candidate`独立版本先完成三次冻结重放及一次真实完整关卡；随后才正常编译正式模块。旧两模块备份与哈希在`production-before`，正式构建在`production-build.log`，保持`/fp:strict`；已有const限定符编译警告保留，构建成功。
- `production-frozen-replay`正式模块三次成功，完整结果摘要相同，报告包含模块路径/哈希。
- `bend-production-verify`正式模块依次跑原车、操控组合、单前胎，共三例全部完成且各自源码首末稳定。原车92.529882499秒/19.568236445 L/100km；操控组合2640经费，92.381058034秒/19.495323631；单前胎750经费，92.213500169秒/19.457954854。操控组合最大偏差1.851米/RMS0.386米，仍不如单前胎0.606/0.118米，不据此冻结底盘组合报价。
- `shared-path-comparison.json`核对原车1851、单前胎1845条实际20Hz轨迹，修复前后全部字段逐项相同；该结论只覆盖两套指定方案。整体物理源码版本已变化，旧数据不能直接混为最新版本的正式排名。
- 油耗数值边界修复后另跑`bend-handling-final`，最终源码下操控组合仍完整完成，92.381058034秒/19.495323631 L/100km，与前一次正式模块结果相同；该次源码首末稳定。不是重复宣称三例都在最终油耗边界源码下重跑。

## 扩展检查发现的油耗边界

首次T1先因新诊断工具缺少显式subprocess检查参数停在Ruff，修正后首组107过3失败。一个Jacobian测试原本未进入其要检查的旧映射，现显式选择原回调路径，连续原生路径仍由其专门测试覆盖；未改测试精度。

另两项揭示旧归档输入缺少油耗字段，并进一步确认当前完整车辆数值包不能直接传`FuelMeter`对象。现将计量器转为独立数值字典，试算中恢复独立计量器、输出同样数值字典，只有接受结果时提交。原始样本列表也复制，重复求解不能提前计入主世界、篡改输入或在主世界清空样本时修改旧结果。没有新增物理世界或把油耗反馈给求解器。

旧归档仅在测试读取时补零计量初值，比较原机械字节时剔除新观察字段；旧夹具原字节保持。实际输入/输出数值包测试补充了未提交不计量、重复求解相同、数值往返、提交后对应和样本不共享检查。

最终命令：

```powershell
$env:PYTEST_ADDOPTS='--basetemp=logs/challenge-rebuild-20261101/shared-final-T1-temp'
.venv/Scripts/python.exe tools/validate.py T1 --tests tests/test_challenge_solver.py tests/test_drivetrain_jacobian.py tests/test_continuous_solver.py tests/test_tire_shaft.py tests/test_joint_suspension.py tests/test_challenge_catalog.py tests/test_physics_wire.py tests/test_physics_workers.py tests/test_world_substeps.py tests/test_fuel.py --output logs/challenge-rebuild-20261101/T1-shared-fuel-final
```

最终144项通过，pytest37.12秒；全项目Ruff、0/17/23种子各1200步通过。包含旧完整机械夹具的52次次序/工作区核对、线程求解/错误恢复、真实多进程车辆子步，以及新求根回归和油耗状态边界。前组失败没有改称通过，也没有把重叠检查相加。不是完整T2、正常驾驶性能、真人样本或金牌平衡验收。

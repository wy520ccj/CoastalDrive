# 阶段回归：ABS当前物理事实

从`959acda`开始机械/参数化T2。Ruff通过，完整pytest输出`F.`后主动中断，以便先复现失败；进程已结束，后续检查均未跑，不能记为T2通过。`logs/validation/PHYS-DESIGN-01-stage-T2/summary.json`明确保存手工终止原因。柏油节点定向复现失败，53.88s：两组抱死为0，但后轮最坏kappa同为−.09095256，旧断言要求开启ABS必须改善此极值。

## 同条件对照

```powershell
.venv/Scripts/python.exe tools/physics/abs_probe.py --cases asphalt low-mu split-mu --output logs/physics/PHYS-DESIGN-01-abs-facts
```

沿用原工具、100km/h初速、完整参考硬件和执行器参数、独立重力平面，240拍静置后真实制动。六条A/B均完成，生产源码前后SHA一致。[机器摘要](abs-facts-summary.json)保存完整参考参数、逐轮最坏滑移/轮荷/压力、每拍ABS阶段计数及原始CSV/SHA。

| 工况 | 关闭ABS | 开启ABS |
|---|---|---|
| 柏油 | 390拍停车，45.549m，0轮秒抱死 | 完全相同；四轮390拍均normal |
| μ.6 | 642拍停车，73.642m，17.500轮秒抱死 | 571拍停车，66.007m，.183轮秒抱死；实际release/hold/apply |
| 对开附着，6秒限时 | 未停稳，98.929m，19.325轮秒抱死，累计最大偏航7.120° | 未停稳，90.222m，0轮秒抱死，累计最大偏航6.561°；实际调压 |

柏油两条完整已采样轨迹唯一差异为`state.abs_enabled`标志，物理和制动状态逐字段一致；硬件未达到ABS介入门槛，不能为了满足旧断言强制减压。此节点改为检查零抱死、全normal以及除开关标志外整条轨迹相等。强制动力矩、低附着和对开附着节点继续要求真实抱死减少、减压及实际轮胎力；强制动/低附着的停车与距离方向检查保持。

## 当前验证与待办

```powershell
.venv/Scripts/python.exe tools/validate.py T0 --tests tests/test_abs_integration.py --output logs/validation/PHYS-DESIGN-01-abs-T0 --timeout 1200
.venv/Scripts/python.exe tools/validate.py T0 --tests tests/test_validation_runner.py --output logs/validation/PHYS-DESIGN-01-stage-stop-T0
```

ABS模块首轮6通过/1失败，433.50s：空中制动旧账遗漏世界方向变化及发动机/传动轴转子。保持同一24拍轨迹，完整世界角动量误差为.00074725N·m·s，小于原.001门槛；完整转动能14111.405→937.574J。节点改为完整世界三维转动账，空中无支持/无地面力、轮速下降与无ABS检查保持。首个补测因导入排序失败、pytest未跑；修正排序后该节点及全Ruff通过(.51s)。[机械账与验证摘要](airborne-facts-summary.json)。其余6项代码和生产未变，复用有效通过结果，合并7项ABS检查，不重复整个模块。阶段入口已让T2/T3的完整pytest使用`-x`，首个失败直接输出报告并停止；成功时仍执行完整测试集合。已有验证入口合同扩充相应断言，13项及全Ruff通过(.82s)。T0/T1保持所选短检查汇总。生产物理和电子控制未改；下一恢复阶段T2。整个物理阶段、实车型/估计/研究入口及T3/前台性能/用户驾驶仍未完成。

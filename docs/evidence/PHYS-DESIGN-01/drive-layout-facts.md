# 阶段回归：轮端矩包含实体传动轴惯性反力

T2-r5续跑实际失败结束：Ruff通过，166通过／1原生布局轮端矩失败，329.90s；r4复用的52项保持有效，后14检查仍未跑。失败为原断言把全部轮端矩都当作齿轮输出的逐轮等分，遗漏PHYS-DRIVE-05已引入的输出／前／后驱动轴惯性反力。原日志保留在`logs/validation/PHYS-DESIGN-01-stage-T2-r5-continuation/`。

[原生24子步观测](drive-layout-facts.json)与[可重复脚本](drive-layout-facts-probe.py)覆盖两模式、RWD／AWD／FWD和正／倒挡的首拍。每个实体轴的`J*(ω_end−ω_start)/dt`直接计算惯性矩，再经实际主减速比及前后布局权重得到轮端反力；独立计算与真实轮端输出最大误差1.35525e−20N·m，原1e−10门槛保持。未改变生产物理。

测试只补足这项实际输出账：原齿轮等分矩加上Snapshot已保存的实体轴轮端反力。180拍起步、两模式／三布局／正倒挡、原轮胎残差门槛、位移起步要求、重定位与reset状态合同全部保留。

```powershell
.venv/Scripts/python.exe tools/validate.py T0 --tests tests/test_drive_layout.py::test_native_layout_launch_outputs_and_reset --output logs/validation/PHYS-DESIGN-01-layout-output-T0 --timeout 1200
```

12项／全Ruff通过，pytest123.03s。阶段续跑可复用r4的52项、r5的166项和本次12项，合计230项不同节点；其余1865项及原后14项继续运行。原失败仍为失败，累计覆盖未齐前不记阶段通过。

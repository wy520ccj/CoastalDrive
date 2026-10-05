# 工程车型与真实几何接通

基线`07145e7`，本增量接施工线③；参数分区IO基准沿用本目录`reference-engineering.json`。当前块仍施工中，设计参数标准A/B、参数化T2及机械T2/旧音频收口继续待办。

## 实现与参数来源

`vehicle_designs.py`提供明确的游戏调校、RWD/FWD/AWD参考设计。三个参考设计仅前轴驱动份额为0/1/.5，其余字段相同；基于reference-v28，另同步下述车身外廓。轴系仍为纵置设计，不能把FWD名称解释成横置实车。既有双门/轿车外观对应游戏调校，新增三项车库选择对应三种参考设计。

同一车型配置在游戏/困难仿真之间保持。模式改变输入辅助，ABS/TCS/ESC独立；Session菜单保存下一场配置，起步重建Simulation，不在行驶中换硬件。成绩键追加完整硬件内容哈希，避免参数修改后沿用旧成绩。无窗口默认车型与窗口默认车型同为明确游戏调校，可用`--vehicle-design`或`--vehicle-config`选择其他硬件。底层未显式传入硬件的历史Session/DrivingMode接口保留既有模式默认值，旧标准试验基准继续可复现。

本增量实读现有资产。主车原轮网格宽约238mm、NPC约145mm，与物理205mm不一致；车身原网格高度约1.343386m，与旧车身盒0.84m不一致。新设计的车身半宽.994m、半长2.128m、半高.671692818m，设计地面车身中心高.771692826m，取自主车移除四轮后的实际网格。显式车身惯量沿用原参考设计(1919.56,511.56,2290)kg·m²；它是设计硬件，不按显示网格重新推断。

车身网格按所选配置装配到真实Bullet车身盒；轮网格按胎宽/直径缩放并重置网格中心，缩放保留在轮姿枢轴的子网格。枢轴自身无缩放，Scene直接使用唯一Snapshot的世界轮位和四元数，悬架运动不被显示节点覆盖。Garage静态轮心为设计地面上的轮半径，车根高为设计质心高。

车身盒与四个有限宽轮胎分别定义几何。满舵轮胎扫掠可以超出车身盒；旧资产测试把两者当作同一外廓，在接通205mm轮宽后出现5.98mm越界。现在分别验证真实车身盒和轮柱扫掠范围；不缩小轮宽、改变舵角或扩大车身盒来隐藏差异。机械精度与既有碰撞机制未改。本次验证并不新增动态轮胎对轮胎多体碰撞能力。

四份完整工程文件见[designs](designs/manifest.json)。每份保存96字段、嵌套电子参数、单位/定义、设计属性与资产/源码SHA256。导出时HEAD为07145e7，实际未提交源由文件哈希明确记录；不将它误记为该HEAD已包含的代码。

```powershell
.venv/Scripts/python.exe tools/physics/export_designs.py --output <新目录>
.venv/Scripts/python.exe src/main.py --headless --track test --steps 120 --seed 23 --driving-mode simulation --vehicle-config docs/evidence/PHYS-DESIGN-01/designs/reference-fwd.json
.venv/Scripts/python.exe src/main.py --headless --track test --vehicle-design reference-awd
```

## 验证与失败记录

首轮T0日志`logs/validation/PHYS-DESIGN-01-geometry-T0`：29通过/7失败，169.71s。三种设计两输入模式的120拍完整玩家真值逐字段相同；三项失败仅为末段制动后仍要求末速度>.01m/s。改为实际起步区间峰值>.1m/s。两项几何断言漏加原生形状体积中心的质心偏置，按实际坐标修正；另外两项为Float32边界及上述轮胎/车身混用。数值几何误差仅采用微米级容差，未放宽机械收敛阈值。

`geometry-T0-r2`因新导出工具导入排序失败未跑pytest。修正后`geometry-T0-r3`全Ruff/8项通过，95.57s；其中一项菜单重建复验与首轮通过项重叠。合并有效结果为36项，不能累加成37项。

8项补测覆盖三种布局的两模式逐拍相同、菜单重建/成绩隔离，以及真实GLB/BAM与原生Bullet几何和Snapshot轮姿。修改实例采用1450kg、(700,950,1100)kg·m²、轴距2.6m、轮距1.9m、轮半径.37m、胎宽.245m、CG高.48m、前静载份额.6；车身位置比较使用真实分区Box体积中心，轮枢轴写入Snapshot后仍保持声明宽径与单位缩放。

相关集成T1命令：

```powershell
.venv/Scripts/python.exe tools/validate.py T1 --tests tests/test_driving_mode_ui.py --output logs/validation/PHYS-DESIGN-01-integration-T1
```

界面4项通过，19.86s；验证实际车库选FWD、保留电子设置、下一场重建正确硬件。集成T1完整通过：全Ruff及种子0/17/23各1200步通过，启动耗时82.7/79.5/82.6s。与有效T0合并为40项不同pytest检查；这是本增量相关验证，不是整块③T1/T2。单独工程FWD文件120步CLI通过，实际报告配置与导出设计完整一致，结果保存到`logs/physics/PHYS-DESIGN-01/explicit-fwd-cli.json`。最终全Ruff再检查通过。

游戏设计显式保留原Box名义惯量，避免按显示外廓变化自动重算驾驶硬件。实际Bullet旧/新惯量分别为(1919.560303,511.559875,2290.000244)/(1919.560059,511.559998,2290.0)kg·m²；差异为单精度装配，不能称原生位级相同。车身碰撞外廓同步是本次明确的物理变化，侧撞/实际驾驶仍须后续验证。

## 实际渲染

复用既有车库捕获工具：

```powershell
.venv/Scripts/python.exe tools/vehicles/capture_vehicle.py --models sports reference-rwd reference-fwd reference-awd --output logs/vehicles/PHYS-DESIGN-01-garage-r2
```

1920×1080实际离屏车库，四车型各界面/轮近景共8张；已目视核对FWD车库页及AWD轮近景，车型标题/车漆匹配、既有版式保持、轮网格装配正常。第一轮`PHYS-DESIGN-01-garage`的捕获脚本未刷新菜单缓存，车体正确但文字保留上一项；原输出保留，新版本显式刷新捕获界面。离屏几何证据不替代用户驾驶或前台性能。

下一步：使用这些完整配置进行同条件设计A/B，再收参数化T2。旧reference-v28有效平路标定保留，不把新车身外廓未做的侧撞/完整标定记作完成。

# PHYS-DRIVE-04 实体输入轴机械核心检查点

基线b7b6ff0。当前为in_progress：生产共同求解已支持九维速度，但驾驶层尚未传入轴状态与提交轴承反力，本块未完成。

九维速度q=(车身角速3,曲轴绝对轴速,输入轴绝对轴速,四轮绝对轴速)。曲轴/输入轴相对速分别为ωe−Ω·ae、ωs−Ω·as；机械轮的正滚动相对速为ωi+Ω·ai。离合滑差为se−ss，齿比误差为ss−R∑wi si。三轴限滑、四轮接触/制动、曲轴与输入轴共用一个隐式末状态；没有积分后调速。

已挂挡时先精确消去齿比约束，联立离合矩C、齿轮实际反力G、输入侧折算损失L与单轮制动。输入轴方程Js Δωs/h=C−G，因此G不能用C代替；驱动轮矩Rwi(G−L)。效率区间按G定义，两向功流维持非负损失。齿比反力壳体矩、轴承陀螺与Js储能同时存在。

未挂挡时离合仍作用于真实Js；有限同步器作用于待挂齿比的速差，容量饱和或锁合由同末状态解决定，热为h Gsync Δωsync。挂挡触发流程下一步由Powertrain接入，不能把本核心中的硬齿比端口直接拿来瞬时更换齿比。

实际实现入口：src/shaft_transmission.py、src/tire_drivetrain.py；八维原机制保留用于明确的旧/新A/B。differential的精确消元只扩展到包含输入轴的速度维度，没有改变本构、容量或残差门槛。共同求解返回实体轴速度、齿轮反力、同步热及轴承反力；VehicleTires调用/Powertrain保存尚待连接。

[机械核心回执](core-receipt.json)：115项实体端口检查和37项新共同接触检查通过；相关一次完整T0为729项通过（pytest20.94s），Ruff通过。前/后/四驱、倾斜机械轮轴、刚/柔接触、限滑与制动同时展开独立能量/角动量账，原3e−9J、1e−10Nms和.001N门槛保持。空挡闭合离合的实体输入轴有限升速已检出，省掉Js储能的负对照被验算拒绝。同步器经过多个实际饱和步达到速差为零，未设固定同步时间。最初独立验算的制动壳体反力符号错误造成108失败/7通过，纠正测试符号后115通过，记录保留；初次Ruff导入格式失败也保留说明。

命令：`.venv/Scripts/python.exe tools/validate.py T0 --tests tests/test_shaft_transmission.py tests/test_tire_shaft.py tests/test_transmission_ports.py tests/test_tire_drivetrain.py tests/test_differential.py --output docs/evidence/PHYS-DRIVE-04/validation-T0-core-r1`。本次未运行T1/T2；仅机械核心检查点，不宣称原生生命周期、默认模式、整阶段性能或人工驾驶已完成。

模型依据：[MathWorks Synchronizer](https://www.mathworks.com/help/sdl/ref/synchronizer.html)说明先通过摩擦同步轴速再接齿式离合；[Simple Gear](https://www.mathworks.com/help/sdl/ref/simplegear.html)明确齿比/转矩关系、损失及壳体端口。这里实现有限摩擦同步和理想已啮合齿轮，没有声称完整齿隙、拨叉/定位机构或实测硬件参数。

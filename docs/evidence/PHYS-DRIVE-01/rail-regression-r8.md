# r8 护栏刮擦工况与当前验证

r7完整T2首个失败为test_five_second_rail_scrape_stays_contact_without_repeated_impacts：7秒窗口840拍中最长真实连续接触330拍，原要求600拍，439通过/1失败、其余14检查未跑。原日志与冻结源保留于[失败回执](validation-T2-r7/receipt.json)。

## 原生复现与原因边界

同一(6.9,30,.55)、(.5,8,0)、初始纯滚动8m/s只设置一次，随后固定半油门/2°/D。旧传动最长667拍、有限传动330拍；两者全程仅1次真实撞击。原始逐拍[对照](rail-scrape-diagnosis-r7.json)及两个JSONL.gz保留全部车身、轮胎、传动和接触字段。

[原始manifold](rail-scrape-manifold-r7.json)显示第510拍无护栏接触点，第511拍恢复；不存在可补记的求解接触。该拍横向位置6.830168m，前后约6.83003m，没有长时间驶离护栏。没有修改接触采样、碰撞、坐标或轮速。改变Box内部margin为.001/.01/.04后840拍轨迹与原来完全相同，未支持margin修复；固定3°/4°和全油门也未建立原窗口的600拍连续段，原始失败全部保留。不用挑选新驾驶参数来通过。

[同一输入持续12秒](rail-duration-audit-r7.json)得到第511–1440拍930拍连续真实接触，仍仅1次撞击。其中第511–1110拍的600拍全部有真实接触，沿栏44.323128m，接触切向速度8.52414–9.08099m/s，属于实际刮擦。

因此r8只把观察窗口840拍(7秒)改为1440拍(12秒)，给接近及传动/车身收敛阶段更多时间；明确改变的是观察时限。最少600拍连续真实接触及仅1次撞击的断言不变，不跨缺失拍拼接，不沿用旧接触。增加旧传动/有限传动两分支参数化。未宣称原7秒行为通过，也不凭单拍缺失认定传动或碰撞算法已证实存在错误。

## 当前版本和验证

[280文件冻结回执](candidate-validation-r8-source-receipt.json)仅tests/test_impact_events.py与r7不同；所有生产源码/其他测试/工具保持。r8ZIP SHA-256为2f550a65b34be5c1e9470bc4a1869fa4eed45a972c9b3cec16c2097dc1d2ee48。r7的标准A/B和原生机械证据仍属于原生产源，不重写成新的实测结果。

第一条T0因重复--tests，参数被覆盖，仅实际执行声音模块9项；如实归档在validation-T0-rail-r8-sound-only。随后正确命令：`.venv/Scripts/python.exe tools/validate.py T0 --tests tests/test_impact_events.py tests/test_soundscape.py --output logs/validation/PHYS-DRIVE-01-T0-rail-r8-complete --timeout 900`。Ruff及完整22项通过，pytest20.34s，原始日志在[当前T0](validation-T0-rail-r8/summary.json)。源码清单在T0之后取样，不宣称该T0有前后SHA证明。

完整T2-r8命令：`.venv/Scripts/python.exe tools/validate.py T2 --output logs/validation/PHYS-DRIVE-01-T2-r8 --timeout 9000`；进程局部PYTEST_ADDOPTS=-x。完整T2-r8已失败结束：450通过/1音频集成失败，pytest2416.45s；其余14检查未跑，280源前后一致。失败为护栏工况预期1次有声撞击、实际0次。进程已退出，原始日志及[失败回执](validation-T2-r8/receipt.json)已归档。不能记为完整T2通过。

独立音频T0两个参数均失败（15.54s）：单Box/8m/s没有撞击事件；分区Box/16m/s没有连续两拍达到原25Ns刮擦启动压力。四组旧/有限传动原生对照见rail-audio-diagnosis-r8.json：分区Box压力问题在两种传动均出现，未证明由有限传动引起。

两个更强输入候选均失败，未修改生产音频或阈值：x6.9/vx1/3°出现2次真实有声撞击；x6.6/vx1/3°没有有声撞击。脚本都在首个False/8m/s工况断言退出，第二工况未运行；原始轨迹与决策保留，见rail-audio-fixture-failures-r8.json。用户指出测试拖住功能推进后停止追加实验，音频工况修复列为后续明确功能块。本轮按用户授权提交推送失败状态的开发检查点。

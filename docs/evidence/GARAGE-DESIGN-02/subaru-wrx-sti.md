# Subaru WRX STI 实际接入

基线`f2253ae8`，仅本地。作为第7款车在5星解锁，默认蓝色/金色源轮毂；现有9个设计完整配置逐字段不变，新车明确使用项目四驱调校。

- 来源：lubomircenovsky的[原作者条目](https://www.blendswap.com/blends/view/47523)、[原始Blender](https://github.com/stuntrally/blendfiles/blob/master/cars/S8/wrx_08.blend)及[逐车许可/纹理](https://github.com/stuntrally/stuntrally3/tree/main/data/cars/S8)。明确CC-BY-SA-3.0，Tapio/CryHam移植修正保留署名。原件与可编辑衍生文件随仓库保存，模型/缩略图/阴影衍生物继续同许可；运行署名`Subaru-WRX-STI-License.txt`。不据此声称厂商授权或原厂性能。
- 保留157165个源网格三角形、内饰、灯组和完整源轮胎/轮毂；不接入蓝图/备份车体。变换轴向、拆出四轮、PBR接图；源红色车身图提取红通道遮蔽以支持改色。工具`tools/blender/prepare_subaru.py`和`tools/vehicles/prepare_subaru.py`。
- 初次旧blend内嵌红图仍被复用，实图出现黑车身；显式加载新中性图修复。旧失败图留在`subaru-1024/`日志目录。最后仅清理可编辑衍生场景/内嵌纹理，GLB与BAM SHA保持一致，不重复驾驶。
- T0：车库保存/车型外观15项通过，`subaru-T0`。完整相关T1：车库、外观、生涯规则/UI及显示装配39项通过，0/17/23各1200步通过，`subaru-T1`。未运行T2/T3。
- 三赛新实际驾驶：起步1906拍/15.883秒，停车2300拍/19.167秒，绕桩4170拍/34.750秒，全部3星；共8376拍，每拍独立复核规则，正常二值输入，无改阈值。`subaru-driving`保存压缩逐拍记录。非人工手感验收。
- 配置对比：`subaru-baseline/summary.json`核对原9个完整配置全部相同。没有修改Simulation/120Hz/现有车硬件/规则。
- 正常UI流程首次因工具固定选择蓝色、恰与新车默认相同而断言失败，在涂装预览处中止，未执行道路；工具改为选择下一色。v2与最终流程各12张图、各240新道路显示拍，共480拍；最后版本`subaru-final-flow`完成换车、购件/恢复、预览取消/保存、键盘返回和显示资源不累积。道路显示拍不代替8376拍完整驾驶。
- 归档：`subaru-1280/`为最后12张流程实图，`subaru-1024/`为最终四页静态实图，`subaru-unlock-1024/`为明确合成5星奖励夹具，显示Subaru与GR86同时解锁。后两者0新道路拍。蓝/红/白实际车漆、两侧轮毂和画幅已检查。
- 文件SHA和尺寸见`subaru-source-sha256.json`，运行资源另入设计资源清单；许可与模型来源可追溯。

日志前缀均为`logs/validation/GARAGE-DESIGN-02-`。R2/经典车/GR86仍为旧简易资源，照明和道路质量仍低于参考目标；人工审美/驾驶趣味性待实际体验，总任务保持in_progress。

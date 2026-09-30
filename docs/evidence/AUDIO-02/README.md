# AUDIO-02 实录版

基线main f317d1b；2026-09-30按用户“更接近现实，像录音机电视机里”的反馈重做。主/VI两个目录同步，新独立包builds/0.8.3-audio02/win_amd64/coastaldrive.exe，入口试玩.cmd、试玩-AUDIO-02.cmd。

引擎实际来源：[TheLittleCrow / Mini Cooper S 2019](https://freesound.org/people/TheLittleCrow/sounds/669618/)，车身与缸体接触麦克风双轨，CC0。不同转速片段经离线点火谐波校稳音高后循环，不再用点火正弦/噪声合成。900/1800/3200/4700/6500为频谱估计和游戏音高锚点，非现场转速表读数。不同负载使用两麦克风混合，维持较低默认引擎音量。

碰撞主体实际来源：[harrisonlace / 空车身手击](https://freesound.org/people/harrisonlace/sounds/798843/)和[LPA134 / 机盖撞击](https://freesound.org/people/LPA134/sounds/329516/)，均CC0。采用实物发声而非文件柜/糖果盒拼接；不是交通事故实录。车体共振保留至3.2–4.8kHz，取消过窄低通和按强度降调，减少独立叠层。机盖录音的车库回声单独收短，碰撞不带轮胎滑动；实际接触刮擦循环不变。

| 验证 | 结果 |
|---|---|
| 相关T1 | Ruff、52项音频回归、0/17/23三种子各1200步通过；logs/validation/AUDIO-02-T1-complete |
| 实际OpenAL | 104/104素材句柄、驾驶/切台/暂停/结算生命周期通过；[openal.json](openal.json) |
| PCM/包音频 | 单次27样本最长0.344秒，刮擦4样本与上版SHA一致；试听峰值0.598、饱和样本0，59音频文件与包SHA一致；[feedback.json](feedback.json) |
| 引擎循环 | 起音、信号、环缝无异常尖峰回归通过；转速主谐波约30/60/106.7/156.7/216.7Hz |
| 独立包 | 仓库外三场景与各20次重开smoke、56高速资产SHA通过；[package.json](package.json) |
| 两目录 | 跟踪文件及新包逐文件SHA核对；[sync.json](sync.json) |

[引擎试听](engine-audition.wav)：12秒，怠速到升转速/换挡。[碰撞试听](collision-audition.wav)：10.2秒，轻车撞、护栏、硬物、重车撞，没有持续刮擦接触。[完整试听](audition.wav)：44秒，生产Soundscape混音，末段含双电台。自动验证不评判真实感，用户实际试听结果单独记录。

首轮T0发现机盖车库尾响超出既有短尾要求，已只收短该来源回声，原阈值未放宽。新增环缝测试首轮被Ruff pairwise规则阻断，修正后最终T1通过。打包输出包含既有Windows系统DLL/平台模块提示，独立包实际smoke通过。没有运行长时性能Gate。

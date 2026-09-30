# PLAY-01-FIX 实现与证据

2026-09-30，基线main 6b638ac。用户反馈：电台切换只听到一个BGM、暂停无法设置、碰撞偏铁皮且不够大、限速100与三角牌重叠。

已定位菜单切台bug：原MusicAudio把所有MENU状态的目标曲目固定为索引0，导致选台标签与实际歌曲不一致。现在菜单/驾驶/结算都消费所选电台；N/M改为按下沿触发，按住不会连跳。普通暂停停止音乐，暂停设置允许试听；设置期间仿真仍暂停，Esc先回暂停页，再次Esc继续驾驶。

暂停页复用现有七项设置页，添加“设置”入口，不增加页管理框架或未实现的参数占位。碰撞重调起音/主体：车身主体300–550Hz、车车起音1600Hz、护栏金属起音3000Hz；车身主体峰值0.84、增益0.50+0.48s，降低形变/碎屑尖锐占比。四种代表撞击350ms混音RMS比上一版提高1.7–3.9dB。短尾和真实擦碰逻辑继续保留。

原seed0在1100m同时放置100限速和横风警告，横向只差0.1m，实图复现完全叠牌。横风牌改为独立的公里250m槽，示例1100/1250m相隔150m。

| 检查 | 结果与证据 |
|---|---|
| T1 | Ruff、106项音频/UI/环境回归、三种子各1200步通过；logs/validation/PLAY-01-FIX-T1 |
| 真实曲目输出 | WASAPI回录OpenAL，菜单Sunset/菜单Midnight/驾驶Midnight/暂停设置Sunset均匹配正确曲目，相关度0.817–0.875，错误曲目约0.31–0.33；[radio-output/report.json](radio-output/report.json) |
| 真实素材载入 | OpenAL104/104 READY，关闭生命周期通过；[openal.json](openal.json) |
| 碰撞混音 | 代表车身主体500Hz以下能量占比提高到89–99%，试听峰值0.825、饱和样本0；[collision-mix.json](collision-mix.json)、[feedback.json](feedback.json) |
| 暂停设置 | 720p/1080p五项暂停菜单与七项设置实图、最长电台名、按钮边界及返回后仍暂停通过；[720p](pause-720/settings.png)、[1080p](pause-1080/settings.png) |
| 路牌间距 | 25种子×92分段，限速/三角警告至少相隔50m，跨分段无同点叠牌；生产模型实图[修订前](sign-spacing/before-overlap.png)、[限速牌](sign-spacing/after-limit.png)、[警告牌](sign-spacing/after-warning.png) |
| 独立包 | 仓库外三场景/20次重开smoke、56高速资产与59音频目录文件SHA核对；[package.json](package.json)、feedback.json |
| 主/副本 | 当前任务源码/资源/文档及新包同步到CoastalDrive-VI-v1，逐文件SHA核对；sync.json |

WASAPI驱动在录制分段打印过data discontinuity警告，实际波形仍明确匹配所选曲目；本项结论是选台输出正确，不作为无间断录音质量结论。首轮T0被新增测试的pairwise风格检查阻断，修正后定向T0与最终T1通过。声音主观验收仍以实际试听为准，未运行长时性能Gate。

新包：builds/0.8.3-play01-fix/win_amd64/coastaldrive.exe。入口试玩-PLAY-01-FIX.cmd及默认试玩.cmd；当前AUDIO/HWY/PERF入口统一更新，旧包保留。

[碰撞专门试听](collision-audition.wav)约10秒，依次为轻车撞、护栏、硬物、重车撞；由生产Soundscape混音截取，没有持续接触擦碰段。[完整44秒试听](audition.wav)含引擎、真实擦碰和双电台。实际电台输出回录文件保存在radio-output/，对应报告核对两首原曲。

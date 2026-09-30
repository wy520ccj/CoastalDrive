# 驾驶音频

AUDIO-01以PERF-04-FIX为基线，声音按功能直接消费Snapshot和真实ImpactEvent。

| 功能 | 代码 | 运行素材 | 表现 |
|---|---|---|---|
| 引擎 | src/audio/engine.py | assets/game/audio/engine | 原创程序化V8音色，900/1800/3200/4700/6500rpm，滑行/负载双层、相邻转速等功率交叉、换挡短暂卸载 |
| 行驶 | src/audio/driving.py | assets/game/audio/driving | 沥青/非铺装、随速度平方增加的风噪，按物理侧偏/横向载荷/制动调节轮胎声 |
| 碰撞 | src/audio/impact.py | assets/game/audio/impact | 31个重制变体；车车/护栏/硬物独立瞬态和主体，形变与碎屑、左右持续刮擦，重撞压低背景 |
| 音乐 | src/audio/music.py | assets/game/audio/music | 两首原创32小节双声道配乐，菜单BGM、驾驶电台交叉切换、暂停保留播放位置 |
| 提示 | src/audio/cues.py | assets/game/audio/cues | 导航/确认、倒计时/发车、检查点、成功/失败/结束和切台短音 |

入口src/soundscape.py只负责音量乘积、阶段和事件分发；不增加事件总线或通用声音管理框架。重开清理驾驶声和撞击尾音；结算接收最后一次真实撞击并保留尾音。效果静音不影响音乐，主音量控制所有声音。

N循环切换关闭/海岸FM/夜驰FM，M开关车载音乐。音乐默认55%；声音设置用上下选择、左右调整，也可点击按钮。海岸FM为104BPM暖色合成器巡航曲Sunset Run；夜驰FM为112BPM电子驾驶曲Midnight Circuit。每首约69–74秒，含逐段进入的和弦、低音、琶音、旋律及鼓组。

## 参考与采用

- [GTA V Self Radio](https://www.rockstargames.com/newswire/article/25o2411812a799/self-radio-create-your-own-custom-radio-station-in-gtav-pc)：借鉴驾驶中切换音乐与音乐单独控制。本轮内置双电台，本地歌曲导入未实现。
- [Cyberpunk 2077 2.1官方说明](https://www.cyberpunk.net/en/news/49597/update-2-1-patch-notes)：借鉴音乐随游戏状态连续切换和让位给关键提示的设计。本轮采用菜单/驾驶/暂停生命周期与重撞压低音乐。
- [ange-yaghi/engine-sim](https://github.com/ange-yaghi/engine-sim)（MIT）和[DasEtwas/enginesound](https://github.com/DasEtwas/enginesound)（MIT）：参考燃烧脉冲、排气/共振层、转速控制及离线闭合循环。项目使用原创简化声库生成器，未集成其物理求解或复制源码。
- [squareal / Car Crash](https://freesound.org/people/squareal/sounds/237375/)（CC0）：新增碰撞主体来源，作者以金属柜、砂砾、玻璃等分层制作；截取完整撞击及尾音，再滤波、轻微变速、压缩、校齐起音。其他金属形变/刮擦录音来源见音频License.txt。

## 素材制作与验证

制作工具：tools/audio/prepare_upgrade.py。运行仅需Panda3D；离线碰撞加工需ffmpeg。源录音预览及首次下载哈希保存在assets/source/audio-upgrade/sources.json，已核对的历史录音哈希在tools/prepare_impact_audio.py。新录音哈希也写入发布的impact-bank.json。资源哈希记录在impact-bank.json和upgrade-manifest.json，真实署名与加工方式记录在assets/game/audio/License.txt和docs/asset-register.csv。

引擎采用八次点火周期/排气共振/进气噪声，并移除DC、淡化环缝；这是符合当前美式双门车形象的声音表现，现有驾驶扭矩参数保持。轮胎摩擦是物理状态驱动的表现估计。

验收工具tools/audio/check_upgrade.py直接载入OpenAL，检查104个句柄及声音生命周期、峰值和DC。tools/audio/make_audition.py使用生产Soundscape离线混出44秒试听：0–12秒引擎加速换挡，14/17/20/23秒轻车撞/护栏/硬物/重车撞，25–28秒右侧刮擦，28–36秒海岸FM，36–44秒夜驰FM。

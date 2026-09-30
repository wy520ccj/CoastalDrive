# 驾驶音频

AUDIO-01以PERF-04-FIX为基线，声音按功能直接消费Snapshot和真实ImpactEvent。

| 功能 | 代码 | 运行素材 | 表现 |
|---|---|---|---|
| 引擎 | src/audio/engine.py | assets/game/audio/engine | Mini Cooper S双接触麦克风实录，频谱估计900/1800/3200/4700/6500rpm，车身/缸体不同混合双层、相邻转速等功率交叉、换挡短暂卸载 |
| 行驶 | src/audio/driving.py | assets/game/audio/driving | 沥青/非铺装、随速度平方增加的风噪，按物理侧偏/横向载荷/制动调节轮胎声 |
| 碰撞 | src/audio/impact.py | assets/game/audio/impact | 31个重制变体；车车/护栏/硬物独立瞬态和主体，形变与碎屑、左右持续刮擦，重撞压低背景 |
| 音乐 | src/audio/music.py | assets/game/audio/music | 独立首页BGM与两首授权完整电台曲；单曲切换、暂停保留播放位置 |
| 提示 | src/audio/cues.py | assets/game/audio/cues | 导航/确认、倒计时/发车、检查点、成功/失败/结束；切台不叠加提示音 |

入口src/soundscape.py只负责音量乘积、阶段和事件分发；不增加事件总线或通用声音管理框架。重开清理驾驶声和撞击尾音；结算接收最后一次真实撞击并保留尾音。效果静音不影响音乐，主音量控制所有声音。

PLAY-01-FIX修正菜单强制Sunset的问题：菜单、驾驶和结算统一消费所选电台，关闭电台时菜单音乐也停止。N/M按下一次只执行一次，按住不连跳。暂停页增加“设置”，复用同一音量/电台页，设置期间仿真保持暂停；设置页允许音乐试听，Esc先返回暂停页，再次Esc才继续驾驶。普通暂停仍停止音乐。

N循环切换关闭/海岸FM/夜驰FM，M开关车载音乐。音乐默认55%；声音设置用上下选择、左右调整，也可点击按钮。RADIO-02海岸FM采用70BPM吉他Bossa Nova《Bossa Antigua》，夜驰FM采用132BPM暗色电子《Future Gladiator》，作者Kevin MacLeod、CC BY 4.0。保留整首原编曲（约4:43与3:37），离线统一-18 LUFS，源文件SHA和署名随包提供。原104BPM海岸曲逐字节保留为首页BGM；驾驶/倒计时/结算播放所选电台，普通菜单播放首页曲，菜单/暂停设置页试听所选电台，普通暂停停曲。三首共用音乐音量，电台关闭仅关闭驾驶电台，首页曲仍可用音乐音量静音。

## 参考与采用

- [GTA V Self Radio](https://www.rockstargames.com/newswire/article/25o2411812a799/self-radio-create-your-own-custom-radio-station-in-gtav-pc)：借鉴驾驶中切换音乐与音乐单独控制。本轮内置双电台，本地歌曲导入未实现。
- [Cyberpunk 2077 2.1官方说明](https://www.cyberpunk.net/en/news/49597/update-2-1-patch-notes)：借鉴音乐随游戏状态连续切换和让位给关键提示的设计。本轮采用菜单/驾驶/暂停生命周期与重撞压低音乐。
- [ange-yaghi/engine-sim](https://github.com/ange-yaghi/engine-sim)（MIT）和[DasEtwas/enginesound](https://github.com/DasEtwas/enginesound)（MIT）：参考燃烧脉冲、排气/共振层、转速控制及离线闭合循环。项目使用原创简化声库生成器，未集成其物理求解或复制源码。
- [squareal / Car Crash](https://freesound.org/people/squareal/sounds/237375/)（CC0）：碰撞主体来源，作者以金属柜、砂砾、玻璃等分层制作；AUDIO-01-FIX从0.418–0.426秒真实强撞击附近截取0.18–0.36秒，剔除前置杂声和后续滑动/摩擦。护栏瞬态/主体采用短金属撞击，碎屑改用独立塑料落击。其他录音来源见音频License.txt。

## 素材制作与验证

制作工具：tools/audio/prepare_upgrade.py。运行仅需Panda3D；离线碰撞加工需ffmpeg。源录音预览及首次下载哈希保存在assets/source/audio-upgrade/sources.json，已核对的历史录音哈希在tools/prepare_impact_audio.py。新录音哈希也写入发布的impact-bank.json。资源哈希记录在impact-bank.json和upgrade-manifest.json，真实署名与加工方式记录在assets/game/audio/License.txt和docs/asset-register.csv。

引擎采用八次点火周期/排气共振/进气噪声，并移除DC、淡化环缝；这是符合当前美式双门车形象的声音表现，现有驾驶扭矩参数保持。轮胎摩擦是物理状态驱动的表现估计。

AUDIO-01-FIX按实际试听反馈重制全部27个单次碰撞样本：同一强撞击起音、短衰减和材质滤波形成统一声音，取消额外62Hz正弦层；提高轻撞/重撞增益，单次撞击在0.55秒内结束。4个真实连续接触擦碰循环保留，引擎满载内部混音0.495→0.19（约-8.3dB），不修改用户保存的音量设置。Sunset取消白噪军鼓和高通嘶声，改为轻音高打击；夜驰军鼓改为低音量滤波噪声，两台从开头加入琶音、第二小节后进入旋律。

PLAY-01-FIX进一步把碰撞主体调为车身钝感：轻撞/车车/护栏/硬物主体低通550/350/450/300Hz，车车起音低通1600Hz，护栏仍有3000Hz金属纹理；主体峰值0.84，增益0.50+0.48s，起音增益0.30+0.42s，形变/碎屑混音降低。四种代表撞击前350ms混音RMS提升1.7–3.9dB，峰值0.825、无饱和样本；主观厚度仍以实际试听为准。

tools/audio/check_radio_output.py用真实OpenAL与WASAPI回录，将实际输出分别与两首曲目的波形相关匹配，覆盖菜单双台、驾驶夜驰及暂停设置试听。开发环境可用tools/audio/requirements-verification.txt复现；游戏不需要NumPy/SoundCard。素材READY与FakeSound控制测试不能替代实际曲目输出验证。

验收工具tools/audio/check_upgrade.py直接载入OpenAL，检查104个句柄及声音生命周期、峰值和DC。tools/audio/make_audition.py使用生产Soundscape离线混出44秒试听：0–12秒引擎加速换挡，14/17/20/23秒轻车撞/护栏/硬物/重车撞，25–28秒右侧刮擦，28–36秒海岸FM，36–44秒夜驰FM。

## AUDIO-02：车辆实录音色

用户否定PLAY-01-FIX的真实感。撤除合成点火引擎和squareal文件柜/糖果盒碰撞主体，避免把现成影视Foley误当实车。引擎采用[TheLittleCrow的Mini Cooper S车身/缸体接触麦克风实录](https://freesound.org/people/TheLittleCrow/sounds/669618/)（CC0）；不同转速片段在离线根据点火谐波校稳音高，再做循环接缝。900/1800/3200/4700/6500只是游戏音高锚点，非现场转速表读数。负载控制麦克风混合比例，同源层采用线性淡化防止中油门叠加增响。保留0.19满载内部音量与换挡卸载。

车身采用[harrisonlace的空车身敲击](https://freesound.org/people/harrisonlace/sounds/798843/)前十次独立实录片段，以及[LPA134的真实机盖撞击](https://freesound.org/people/LPA134/sounds/329516/)（均CC0）。这是车身/机盖实物录音，非道路事故实录。车身宽频细节保留到3.2–4.8kHz，取消全段指数衰减和300–550Hz过窄低通；机盖仅收短车库回声。主层维持峰值0.84与0.50+0.48s增益，起音降至0.10+0.14s，护栏起音乘1.4；形变/碎屑再降低一半，运行时随机变调限制±1.5%，不再随严重度刻意降调。27个单次素材持续时间不超过0.36秒，4个实际接触刮擦循环逐字节保持。

制作入口tools/audio/prepare_recorded.py，离线依赖tools/audio/requirements-preparation.txt和ffmpeg，运行包仍仅依赖Panda3D。旧prepare_upgrade.py的all/impact入口委托实录制作，避免未来重建声库恢复旧合成音色。来源、制作和交付证据见evidence/AUDIO-02/README.md。

## RADIO-01：续播噪声、混台与切台帧耗时

Panda3D 1.10.16把两首大于1MB的WAV默认当作流式声音。其WavAudioCursor.seek按时间乘字节率取整，没有对齐16bit双声道的4字节采样帧。续播0.1234567秒落在21777字节，余数1，读出的PCM与该奇数字节起点逐字节匹配，RMS由1201变为19030；这是沙沙噪声的来源。参考实际版本源码：https://raw.githubusercontent.com/panda3d/panda3d/v1.10.16/panda/src/movies/wavAudioCursor.cxx 。

RADIO-01两首短曲改用musicManager独立缓存与SM_sample，原预载约25MB PCM；RADIO-02三首完整曲合计约97MiB PCM，规避流式seek与切台现场读盘。切台先短淡出旧曲至停止再启动新曲，任何时刻最多一首，快速切换/暂停/恢复也保持该约束。暂停位置继续保留。

N/M驾驶路径仅修改所选电台、音乐目标和HUD提示，不立即写audio.json、不重排整个页面；进入暂停/菜单/结算或退出时保存。HUD提示改用TextNode一次自动换行，避免逐字重排每个前缀产生约11ms阻塞；底板仅在行数改变时更新尺寸，现有风格、关键驾驶提示保留。

tools/audio/check_radio_switch.py用真实OpenAL/WASAPI连续往返切台，固定非整采样续播位置，旧版噪声/混台复现，修复版输出与原曲匹配且零混台。tools/audio/check_radio_driving.py在同一可见驾驶窗口对照新旧按键业务路径，独立记录按键和随后的真实任务帧；两组共用新版预载音乐后端，不能把此对照误称完整旧版性能。证据与新包见evidence/RADIO-01/README.md。


RADIO-02说明：此前两首原创电台曲共用和弦、主旋律与音色，仅速度/八度/打击略改，因此听感相似。波形匹配只能确认播放文件，不能确认编曲差异。现更换成独立成品作品，原Sunset专用于首页。标准鼓镲具有正常高频，旧“整曲二阶差分<0.0005”只适合旧合成曲，不再用于新录音；续播验证仍要求匹配原曲波形、无双曲播放、高频比例相对原曲不异常升高，原错位噪声复现仍被该检查识别。

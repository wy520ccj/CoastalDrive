# RADIO-02 独立曲目与首页BGM

2026-09-30，基线main c4ff5ec、VI 2138194。此前两个电台共用同一和弦、旋律和音色，只改BPM/八度/打击，用户听到相似的编曲属实。RADIO-01播放波形匹配只确认选台正确，不能证明曲目听感差异。

## 曲目与试听

| 用途 | 曲目 | 风格与长度 |
|---|---|---|
| 首页 | Home Coast，原Sunset Run | 原104BPM海岸曲，73.846秒，SHA逐字节相同 |
| 海岸FM | [Bossa Antigua — Kevin MacLeod](https://incompetech.com/music/royalty-free/index.html?isrc=USUAN1700069) | 70BPM吉他/贝斯/鼓，Bossa Nova，283.350秒 |
| 夜驰FM | [Future Gladiator — Kevin MacLeod](https://incompetech.com/music/royalty-free/index.html?isrc=USUAN1200051) | 132BPM暗色合成器/贝斯/拍手打击，217.025秒 |

两首独立作品均由作者官网按CC BY 4.0提供；署名、原下载URL与SHA随assets/game/audio/License.txt和music-sources.json打包。保留全曲编排，离线响度统一-18 LUFS，44.1kHz立体声16bit PCM。实际测得两曲-18.04与-17.99 LUFS，差0.05LU；[响度](loudness.json)、[时长和SHA](tracks.json)。未加电台噪声/失真/低通。

海岸FM（原曲12–24秒片段）：

![Bossa Antigua - Kevin MacLeod](sunset-run-preview.wav)

夜驰FM（原曲12–24秒片段）：

![Future Gladiator - Kevin MacLeod](midnight-circuit-preview.wav)

首页原曲（12–24秒）：

![Home Coast](home-coast-preview.wav)

## 路由与验证

首页独立于驾驶电台选择；菜单/暂停设置页试听所选电台；驾驶/倒计时/结算采用所选电台；普通暂停停止并保存位置。三个声音共用音乐音量，全部SM_sample预载（约97MiB），最多一曲播放。N/M路径不增读盘/即时存盘/动态文本生成。

- 真实OpenAL/WASAPI：首页原曲、菜单夜驰试听、驾驶海岸曲、暂停夜驰试听均匹配正确音轨，相关度0.804–0.891，错误曲0.042–0.085；[阶段输出](phase-output/report.json)。这确认播放正确，独立作品和试听片段用于评估风格。
- 四次往返非整采样续播：相关度0.694–0.829，双曲更新0；[连续输出](switch-output/report.json)。标准鼓镲含正常高频，因此退役旧合成曲的绝对高频阈值，改为相对原曲高频比例及完整波形匹配。原奇数字节错位在两首新曲上产生5.05/6.01的能量比，当前上限0.0071/0.0209，明确被拒绝；[离线错位对照](alignment-regression.json)。
- 可见驾驶窗口24次N，全部前景/未最小化/DRIVING，新路径中位0.054ms、最大0.068ms；[窗口检查](key-window.json)。对照仅按键业务路径，两组都用当前预载音频，非完整旧包FPS比较。加载期间catch-up 0.0917s单列。
- RADIO-02相关T0/T1、59项音频/UI回归、种子0/17/23各1200步；[T1](T1.json)。真实OpenAL105/105加载与生命周期通过；[OpenAL](openal.json)。
- 包内61个音频文件SHA均匹配源码；[音频](package-audio.json)。55个非音乐音频/碰撞清单文件与RADIO-01完全相同；[范围核对](unchanged-effects.json)。最终仓库外三场景/20次重启/56高速素材检查见[最终包](package-final.json)，package.json为UI补充修订前的首次包检查。
- 追加左上底板修订见[UI-NOTICE-FIX](../UI-NOTICE-FIX/README.md)。最终新包builds/0.8.3-radio02/win_amd64，试玩.cmd及试玩-RADIO-02.cmd；主/VI同步见[sync.json](sync.json)。

WASAPI驱动打印过data discontinuity；波形匹配用于选台/续播正确性，未把回录当作无间断录音质量验收。首次离线制作遇到ffmpeg输出UTF-8和JSON后有进度行的解析错误，明确指定UTF-8并按JSON对象边界读取后成功；音轨主观风格等待用户实际试听。

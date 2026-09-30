# RADIO-01 实现与对照

2026-09-30，基线main fc2a16b，VI c729bbe。针对偶发电台沙沙声、两首混播和驾驶N切台掉帧，曲目及引擎/碰撞素材未改。

## 根因与修改

Panda3D 1.10.16默认大于1MB的WAV流式播放；WavAudioCursor.seek没有按16bit双声道4字节帧对齐。续播0.1234567秒得到21777字节偏移，余数1，读取PCM确认恰好从奇数字节开始；RMS 1201→19030，形成宽带噪声。[实际解码与播放耗时](seek-probe.json)，[对应版本源码](https://raw.githubusercontent.com/panda3d/panda3d/v1.10.16/panda/src/movies/wavAudioCursor.cxx)。两首短曲现用独立musicManager、SM_sample预载约25MB PCM，不在驾驶帧读盘填流式队列。

原交叉淡化会同时播放两首，现先淡出并停止旧曲，再淡入新曲。暂停仍保存位置，快速往返及静音均最多一曲。驾驶N/M不再即时存盘、重排页面或叠加切台提示音，进入暂停/菜单/结算或退出再保存选择。

可见窗口首次检查发现按键虽快，随后驾驶帧仍变长；cProfile定位HUD.fit_lines逐字getWidth约11ms，属于N通知文本排版。最终HUD预生成三条固定电台标签，切台只切换可见性，不覆盖Session.notice；普通提示TextNode一次换行，底板只在行数改变时更新，保留关键提示和视觉样式。[初次剖析](before-switch-profile.txt)、[修复后剖析](after-switch-profile.txt)、[驾驶HUD](radio-hud.png)。

## 验证

| 检查 | 证据 |
|---|---|
| 真实连续切台 | 旧版四次续播相关度约0.009–0.011、底噪二阶差分能量比3.13–3.25、231次更新双曲播放；修复版相关度0.805–0.832、能量比0.000014–0.000731、零双曲更新；[旧版](before/report.json)、[新版](after/report.json) |
| 阶段输出 | 菜单双台、驾驶夜驰、暂停设置试听均匹配正确曲目；[phase-output/report.json](phase-output/report.json) |
| 切台后端耗时 | 单曲play旧流式3.5–6.1ms→预载0.020–0.026ms；连续更新最大4.012→0.351ms；seek-probe.json及连续切台报告 |
| 可见驾驶路径 | 同一窗口24次N，均前景/未最小化/DRIVING；按键业务耗时中位2.10ms→0.068ms，最大0.088ms；最终新版后续任务帧中位15.62ms，较紧邻普通帧增加中位0.34ms；[窗口对照](key-window.json) |
| 自动回归 | logs/validation/RADIO-01-T0-verified、RADIO-01-T1-delivery；59项最终T1，包含预载模式、快速切台不叠播、驾驶不写盘/不重排、暂停保存、关键HUD文字和边界、三种子1200步 |
| OpenAL | 104/104真实句柄和生命周期通过；[openal.json](openal.json) |
| 独立包 | 仓库外三场景/20次重开smoke、56高速资产SHA；[package.json](package.json)。音频目录逐文件SHA与源码相同；package-audio.json |
| 主/VI同步 | 全部跟踪文件及新包SHA一致；[sync.json](sync.json) |

窗口A/B业务路径共用修复版音乐与HUD后端，单独隔离按键逻辑成本；不是整体旧版/新版FPS对照。窗口加载期间记录过0.15–0.16秒catch-up，采样前已预热；未运行整体300秒性能Gate。WASAPI驱动打印过data discontinuity，正确曲目波形匹配清晰；本项验证续播/切台正确性，不作为无间断录音质量判断。

早期T0因新增工具的Ruff import/exec检查阻断；初次新增换行断言的提示过短无需换行而失败，改为真实长电台加关键提示后通过，原宽度阈值保留。新包builds/0.8.3-radio01/win_amd64/coastaldrive.exe，入口试玩.cmd、试玩-RADIO-01.cmd；现用AUDIO/HWY/PERF入口统一，旧包保留。

# AUDIO-01 实现与证据

2026-09-30，基线bdc447c（PERF-04-FIX），用户授权音效全面升级及新版覆盖主项目。

实施：五转速/双负载原创V8循环、换挡卸载、沥青/非铺装/风/轮胎声；31个重制碰撞变体，新增squareal CC0撞击录音，车车/护栏/硬物独立起音与主体，金属形变、碎屑与左右持续刮擦；九种界面/比赛提示；两首原创双声道配乐、电台交叉淡化、暂停续播、音乐独立音量与N/M按键。代码与资源按功能分区，见[audio-design](../../audio-design.md)。

| 验证 | 结果 | 证据 |
|---|---|---|
| 相关T1 | Ruff、52项测试、0/17/23三种子各1200步通过 | logs/validation/AUDIO-01-T1-final |
| 原始测试复现 | 原HEAD也有4项旧碰撞回归失败；宽碰撞盒摆位/接触分区尺寸问题已精确修正 | logs/audio-baseline/baseline.log，tests/test_impact_events.py，tests/test_impact_integration.py |
| 物理一致性 | 三组各1200tick完整物理Snapshot哈希一致，排除接触元数据 | [physics-equivalence.json](physics-equivalence.json) |
| OpenAL | 实际OpenALAudioManager，104/104 READY；驾驶/材质撞击/暂停/切台/结算/退出探针通过，更新P95约0.023ms | [openal.json](openal.json) |
| PCM质量 | 所有56个WAV峰值<0.9、DC/RMS<0.1，起音时序/同池响度/环缝专项通过 | openal.json与test_impact_assets |
| UI | 720p/1080p各14状态文本检查通过；声音设置7行、音乐音量与电台最长标签实图检查 | logs/AUDIO-01-ui720、logs/AUDIO-01-ui1080；最终settings-720/1080截图与最长标签/按钮边界report.json |
| 独立包 | 仓库外滨海/弯高速/弯坡3场景及20次重开smoke通过，56高速资产哈希一致 | [package.json](package.json) |
| 音频打包 | 全部59个音频目录文件哈希一致 | [audio-package-manifest.json](audio-package-manifest.json) |
| 可见启动 | 独立包正常OpenAL菜单首帧、切入八车滨海及退出完成 | [package-startup.json](package-startup.json)，package-startup.png |
| 原主项目备份 | 16420个文件逐一SHA256核对一致，原main73a466f保留 | ../backups/CoastalDrive-before-AUDIO-01-20260930/backup-manifest.json |

试玩包：builds/0.8.3-audio01/win_amd64/coastaldrive.exe；入口试玩.cmd / 试玩-AUDIO-01.cmd。

[44秒试听](audition.wav)：0–12秒加速/换挡；14/17/20/23秒轻车撞/护栏/硬物/重车撞；25–28秒右侧刮擦；28–36秒海岸FM；36–44秒夜驰FM。由生产Soundscape驱动离线混音，真实设备载入另有OpenAL证据。音乐名称与许可见音频License.txt。

用户实际音色反馈待试玩。此轮没有运行长时性能测试，PERF-04-FIX的性能记录继续保留。

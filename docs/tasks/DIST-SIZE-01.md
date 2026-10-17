# DIST-SIZE-01 试玩包空间精简

- 状态：done（精简、技术验证、推送与公开发布完成）；基线main/71147d405b6f048aa38009ddece914e592267e04，开始前工作区干净。
- 用户要求：测量并尝试优化上轮下载/安装包的空间占用；沿用当前发布施工线，单线实施。
- 基线：安装输入366,201,959字节；Setup198,305,740、ZIP241,443,252字节。音乐106,004,723、UI68,162,450、运行环境137,317,558字节；Git历史约2.52GiB，独立于玩家安装体积，本次不改写历史或删除只读归档。
- 允许：发行工具/资源清单、音乐资源文件映射、安装验证、版本与说明。源码WAV与全部原始素材保留；物理、驾驶参数、实际字体/画质不改。
- 方案：发行时将三首完整WAV无损转FLAC，原生Panda解码全采样及跳转与WAV核对；移除源码无引用的旧Regular/像素字体和两张旧背景；诊断exe只留构建验证目录，不随玩家包重复分发。
- 验收：量化实际安装/Setup/ZIP前后大小；T0/T1音频回归及三种子；安装后的真实主程序/音频、实验台往返、升级/卸载/用户数据保留；新版标签/下载与远端SHA核对。只对相同未改游戏代码复用既有物理结果，不重跑T2/T3或声称人工听感通过。
- FLAC技术依据：[Panda3D原生FLAC读取](https://docs.panda3d.org/1.10/python/reference/panda3d.core.FlacAudio)，实际使用当前安装运行库验证，不追加大型FFmpeg运行插件；FFmpeg只用于构建。

## 结果

- 版本：0.9.0-dev.20261017.1；隔离构建`builds/release-20261017-slim/`，命令`tools/build_release.py --output builds/release-20261017-slim --iscc builds/release-tools/inno/ISCC.exe --ffmpeg <现有ffmpeg.exe>`，status=built。源WAV/原始素材全部保留，四项裁剪和PCM对照见回执。
- 实测：安装后366.2→262.7MB（−28.26%）；安装器198.3→141.6MB（−28.58%）；ZIP241.4→165.3MB（−31.56%）。口径是实际文件字节总数，非NTFS压缩或只看压缩包。
- 全部三首音乐原生FLAC解码完整采样SHA与原始WAV一致，5个含非整秒的跳转从原PCM指定样本位置核对。初探直接对照WAV原生cursor在1.98765秒不一致，改用WAV原始采样定位后全通过；未降低容差或改音频信号。继续使用SM_sample完整预载，暂停/淡入淡出逻辑不动。
- T0：`tools/validate.py T0 --tests tests/test_soundscape.py tests/test_audio_upgrade.py tests/test_ui_theme.py::test_distribution_includes_font_license_and_icon --output logs/validation/DIST-SIZE-01-T0 --timeout 300`通过。
- 扩大T1：`tools/validate.py T1 --area audio --output logs/validation/DIST-SIZE-01-T1 --timeout 300`为61通过/1失败，护栏首拍未进入RESULTS，后续headless not_run。在首版隔离源码及原生扩展上单项复现同一失败，记录基线试验ROOT与原错误。本次不涉及碰撞源码，未修物理，不把扩大T1记为通过。
- 最终针对T1：`tools/validate.py T1 --tests tests/test_soundscape.py tests/test_audio_upgrade.py tests/test_audio_settings.py --output logs/validation/DIST-SIZE-01-targeted-T1 --timeout 300`为26项/三种子各1200拍通过。
- 实际安装：`tools/check_release_install.py --installer <本版Setup> --checker <本版diagnostics/coastaldrive-check.exe> --previous <首版Setup> --package <本版app/win_amd64> --output logs/DIST-SIZE-01/install`完整通过。中文/空格目录从首版升级，无旧发行残留，371个安装文件SHA与本版输入完全一致；正常音频、三种子/渲染/三次实验台往返/原生输入/短实验/记录恢复通过，随后同版覆盖升级和卸载通过，用户数据探针保留、测试程序/注册项/快捷方式移除。未结束用户原窗口。
- 主程序从系统TEMP执行`--profile-startup`，普通独立物理/音频与8车道路通过；主菜单1280×720与首版RGBA逐字节相同，实际实验台图已查看。保留的所有图片、模型、字体与效果音SHA相同。ZIP371文件逐SHA核对通过。
- 证据：[DIST-SIZE-01](../evidence/DIST-SIZE-01/README.md)。构建后全部源输入仍一致，T2/T3未跑；原人工听感/驾驶及物理/长期Gate不借机关闭。
- 已提交/推送发行提交`85167e7cb42af31a013be2edeb9f0b9aa42043b7`，标签`v0.9.0-dev.20261017.1`；公开prerelease于2026-10-17 14:17:08（北京时间）发布。后续提交只补发布回执与进度，不改包。
- [精简版下载](https://github.com/wy520ccj/CoastalDrive/releases/tag/v0.9.0-dev.20261017.1)：3资产远端SHA/大小与本地一致，公开HTTP200及Content-Length正确，SHA256SUMS实际下载摘要一致；回执见`remote-publication.json`。首页两个直链、下载说明及仓库主页网址已切到新版；首版及历史证据保留，旧Release增加新版入口提示。

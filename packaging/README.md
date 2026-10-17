# Windows发行构建

在项目虚拟环境中执行：

```powershell
.venv/Scripts/python.exe tools/build_release.py --output builds/release-20261017-slim --iscc "<Inno Setup 6.7.3安装目录>/ISCC.exe" --ffmpeg "<ffmpeg.exe路径>"
```

输出目录必须不存在。脚本重编五个原生扩展，冻结游戏与技术检查器，逐文件核对全部运行素材和扩展；三首完整音乐无损转FLAC，使用原生Panda解码逐采样核对原WAV及非整秒跳转。源码仍保留WAV，发行资源清单明确选择FLAC，不追加FFmpeg运行插件。四项无运行源码引用的旧字体/背景已从当前素材树清理；诊断exe移至`diagnostics/`供验证，不随玩家包重复分发。安装器仍清理旧版遗留的过期发行文件，支持升级。

`build-receipt.json`记录源码HEAD、构建时工作区、输入哈希、资源变换/PCM等价及产物哈希；修改版本号时同步setup.py、pyproject.toml、此脚本和iss。原始音频、字体、源码和历史包不由精简脚本删除。

安装器使用[Inno Setup](https://jrsoftware.org/isdl.php)，按用户安装，不要求管理员权限；卸载保留用户数据。简体中文翻译原样取自[Inno Setup 6.7.3官方源码中的贡献翻译](https://github.com/jrsoftware/issrc/blob/is-6_7_3/Files/Languages/Unofficial/ChineseSimplified.isl)，维护者和来源保留在文件头。安装器开发阶段说明由`development-notice.txt`提供。

构建后使用`tools/check_release_install.py --installer <最终安装器> --checker <构建目录>/diagnostics/coastaldrive-check.exe --package <构建目录>/app/win_amd64 --previous <上一版安装器> --output <新证据目录>`。检查器仅测试时临时放入安装目录，结束后移除。覆盖真实可见窗口、独立物理进程、短实验/草稿/A-B保留及三次往返；另含音乐句柄/时长、主程序smoke、三种子、旧版升级清理/覆盖升级/卸载及用户数据保留。源码运行与声音回录另按任务记录。

公开资产只上传`artifacts/`中的Setup、Portable、SHA256SUMS；源码、任务和简短证据正常提交，SDK/虚拟环境/工具安装和测试目录不上传。先建draft Release，核对资产后再公开并保留prerelease标记；首页使用明确版本链接，不依赖GitHub对正式版latest的筛选。

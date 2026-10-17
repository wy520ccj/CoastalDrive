# Windows发行构建

在项目虚拟环境中执行：

```powershell
.venv/Scripts/python.exe tools/build_release.py --output builds/release-20261017 --iscc "<Inno Setup 6.7.3安装目录>/ISCC.exe"
```

输出目录必须不存在。脚本重编五个原生扩展，冻结两个入口（游戏与技术检查器），逐文件核对全部运行素材和扩展，生成安装器、免安装ZIP及SHA256。`build-receipt.json`记录源码HEAD、构建时工作区、输入哈希及产物哈希；修改版本号时同步setup.py、pyproject.toml、此脚本和iss。

安装器使用[Inno Setup](https://jrsoftware.org/isdl.php)，按用户安装，不要求管理员权限；卸载保留用户数据。简体中文翻译原样取自[Inno Setup 6.7.3官方源码中的贡献翻译](https://github.com/jrsoftware/issrc/blob/is-6_7_3/Files/Languages/Unofficial/ChineseSimplified.isl)，维护者和来源保留在文件头。安装器开发阶段说明由`development-notice.txt`提供。

构建后必须从非仓库工作目录执行安装后的`coastaldrive-check.exe --output <新证据目录>`，覆盖真实可见窗口、正常独立物理进程、短实验/草稿/A-B保留及三次往返；另跑主程序`--smoke`、三种子headless、安装升级/卸载。检查器仅用于诊断，会打开并自动关闭测试窗口，输出隔离在指定目录。

公开资产只上传`artifacts/`中的Setup、Portable、SHA256SUMS；源码、任务和简短证据正常提交，SDK/虚拟环境/工具安装和测试目录不上传。先建draft Release，核对资产后再公开并保留prerelease标记；首页使用明确版本链接，不依赖GitHub对正式版latest的筛选。

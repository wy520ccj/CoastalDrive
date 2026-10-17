# 下载、安装与卸载 CoastalDrive

> **开发中 · 半成品 · 功能不齐全 · 潜在 bug 可能较多。**
> 这是开发试玩版，可能有崩溃、卡顿、车辆/交通异常、界面及数据兼容问题；尚未达到正式游戏或实车仿真软件的完成度。

## 下载 Windows 64 位版

| 选择 | 下载 | 如何使用 |
|---|---|---|
| **推荐：安装版** | **[下载安装器 .exe](https://github.com/wy520ccj/CoastalDrive/releases/download/v0.9.0-dev.20261017.1/CoastalDrive-0.9.0-dev.20261017.1-Windows-x64-Setup.exe)** | 双击安装，从开始菜单或可选桌面快捷方式启动；带标准卸载器 |
| 免安装版 | [下载完整 .zip](https://github.com/wy520ccj/CoastalDrive/releases/download/v0.9.0-dev.20261017.1/CoastalDrive-0.9.0-dev.20261017.1-Windows-x64-Portable.zip) | 完整解压到可写目录，打开`win_amd64/coastaldrive.exe` |
| 版本说明与校验 | [Release 页面](https://github.com/wy520ccj/CoastalDrive/releases/tag/v0.9.0-dev.20261017.1) · [SHA256SUMS.txt](https://github.com/wy520ccj/CoastalDrive/releases/download/v0.9.0-dev.20261017.1/SHA256SUMS.txt) | 下载包与源码版本、近期改动及验证范围 |

适用 Windows 10/11 x64，需支持 OpenGL 3.3 的显卡及驱动。本包自带 Python、Panda3D、NumPy和原生物理内核，运行无需另装 Python、编译器或开发环境。其他系统暂未提供安装包，也未在其他电脑完成兼容性验收。

GitHub 页面上的绿色 **Code → Download ZIP** 是源码，需要配置开发环境；想直接玩请使用上方安装器或免安装包。免安装版必须完整解压，不能只复制exe或直接在压缩包内运行。

## 安装与启动

1. 下载并运行`CoastalDrive-…-Setup.exe`，阅读开发阶段说明，选择安装位置。
2. 默认安装到当前用户的`%LOCALAPPDATA%\Programs\CoastalDrive`，不要求管理员权限；可勾选桌面快捷方式。
3. 开始菜单 **CoastalDrive (开发试玩版)** 启动游戏；**车辆实验台** 直接进入实验台。游戏主菜单也能进入实验台。
4. 完成实验后可点 **游戏联动 → 保存车辆并试驾**，驾驶中可返回实验台。操作细节见[车辆设计闭环](vehicle-design-loop.md)。

安装包目前未做代码签名；Windows可能显示未知发布者。可用下列命令对照Release中的SHA256，来源或校验不符时不要运行。

```powershell
Get-FileHash .\CoastalDrive-0.9.0-dev.20261017.1-Windows-x64-Setup.exe -Algorithm SHA256
```

## 卸载与用户数据

- 安装版：**Windows 设置 → 应用 → 已安装的应用 → CoastalDrive → 卸载**，或开始菜单 **卸载 CoastalDrive**。
- 免安装版：关闭游戏后删除解压出来的完整`win_amd64`目录。
- 两种版本都将设置、成绩、日志和默认工程数据保存在`%LOCALAPPDATA%\CoastalDrive`。卸载器保留此目录；完全清理前，请先导出、备份自己的试验记录，再手动删除该目录。自行导出到其他位置的记录由你保管。
- 更新前关闭游戏并导出尚未保存的实验。安装新版可覆盖同一安装目录；开发阶段不保证跨版本数据兼容，建议先备份用户目录。

本次空间精简后，安装器约142MB、免安装包约165MB，安装后的文件合计约263MB；保留完整曲目和现用画面。旧版安装可直接覆盖升级，安装器会清理随旧版分发的过期文件，保留用户数据。

## 本版包含与限制

- 当前普通精度游戏、滨海道路与无限高速、车流、车库、声音及车辆动力学实验台。
- 最近游戏/实验台联动、同窗口切换、输入与时间轴修复、海岸坡面修复、菜单和加载手绘背景均包含。
- 双精度隔离SDK及工程预览启动器属于源码开发流程，**不包含在此下载包**；见[双精度运行说明](sim-double-runtime.md)。
- 实验台部分工况可能慢于实时；原物理精度、实车标定、长期性能和人工体验验收仍有未完成项。偶发画面短停、复杂交通/碰撞与试验边界问题仍可能存在。
- 本版验证范围和已知问题保留在[发布记录](releases/0.9.0-dev.20261017.1.md)与[当前进度](current-progress.md)；自动检查通过不代表上述问题已全部解决。

## 遇到问题

在[Issues反馈](https://github.com/wy520ccj/CoastalDrive/issues/new/choose)时附版本号、Windows/显卡信息、操作步骤、截图，以及`%LOCALAPPDATA%\CoastalDrive`中的`crash.log`、`runtime.log`或`coastaldrive.log`（如有）。分享前检查日志与工程文件中是否包含自己的路径或私人数据。

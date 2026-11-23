# 本地挑战预览包

2026-11-07，基线 `15c321f5`。本地游戏入口为 `builds/challenge-preview-20261106-playable/app/win_amd64/coastaldrive.exe`，需要保留同目录运行文件和素材。打包未提交、未推送、未发布。完整来源清单和校验值见同级构建目录的 `build-receipt.json`。

- 从既有路面修正 SDK 导出 CPython 3.14 Windows wheel。打包只覆盖临时构建目录的 Panda3D 依赖，核对冻结后的 Bullet 扩展和 DLL 与 wheel 内文件的 SHA256，并与本次编译结果核对五个项目原生扩展。
- 打包纳入生涯 `coast-club`、`coast-final` 地形网格、海岸水面着色器，以及 Windows 窗口图标使用的 Python 3.14 `ctypes._layout`。首轮组装因漏水面着色器失败，第二轮实际启动因漏 `ctypes._layout` 失败。修复后新目录构建成功。
- 游戏程序在清除 `PYTHONPATH` 后运行 `--smoke`，退出码 0。`verification/smoke/h0-render-smoke.json` 记录了 290 个物理步、车辆移动和离屏截图。
- 冻结诊断程序 `--challenge-preview` 退出码 0。进程 48960 使用新版山谷规则 `budget-valley-braking-v1` 和山脊 `budget-ridge-long-waves`，从正常赛前操作启动山谷及生涯 `first-drive` 自动试车。两份生涯网格均从包内加载成功。`verification/challenge-preview.json` 保存诊断日志的结果行。
- 复用此前自动实跑作为奖牌标定。本轮验证打包、启动和受影响的入口，整包 T2、性能与剩余改装平衡继续开放。

本机已有 SDK 与 VS 的 `dumpbin` 环境可执行以下命令。离线构建可把 `PIP_FIND_LINKS` 指向既有 CPython 3.14 依赖缓存。

```powershell
.venv/Scripts/python.exe tools/physics/build_road_edge_runtime.py --wheel-output builds/challenge-preview-deps-20261106
$wheel=(Resolve-Path 'builds/challenge-preview-deps-20261106/panda3d-1.10.16+coastaldrive-cp314-cp314-win_amd64.whl').Path
.venv/Scripts/python.exe tools/build_release.py --local-preview --road-edge-wheel $wheel --ffmpeg (Get-Command ffmpeg).Source --output builds/challenge-preview-local
```

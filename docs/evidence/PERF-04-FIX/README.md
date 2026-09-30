# PERF-04-FIX 动态渲染与树影修复证据

2026-09-30，基线 `93275ed`。用户反馈左上/右下动态HUD闪烁、偶发车辆闪烁，以及树影靠近才突然出现。保留用户要求的两份阴阳师和动态壁纸后台负载；人工驾驶验收待确认。

## 修复与动态对照

上一轮 `Cull/Draw` 将动态文字更新与剔除分到不同线程。真实窗口录像复现动态计时/车速文字缺失；改为 `/Draw`，让更新和剔除同线程、绘制独立执行。其余有效计算、灯光槽和装配优化保留。尝试 `Cull` 或预生成文字几何仍存在缺失，未引入产品文字绕行逻辑或逐帧强制同步。此前静态截图不足以发现这一动态问题。

同一固定镜头、动态文字及轻微交通车姿态更新探针，各录制8秒、30FPS，共240帧。通过真实操作系统窗口录制检查可见像素，未将录制结果用作性能测试：

| 区域 | 修复前缺失帧 | 修复后缺失帧 |
| --- | ---: | ---: |
| 左上计时 | 240 | 0 |
| 右下车速 | 240 | 0 |
| 固定交通车样本 | 0 | 0 |

车辆偶发闪烁没有在这个受控样本中单独复现，不能据此认定其独立根因或宣布实际驾驶完全消除。详见 [逐帧计数](dynamic-pixels.json) 和 [修复后窗口](dynamic-hud.png)。原始录像由工具保存在系统临时目录，位置记录于 `logs/PERF-04-FIX/dynamic-{before,after}/capture-path.txt`。

草地、山面与植被原先直接采样动态阴影，移动覆盖边缘进入时突变。新着色器按覆盖边缘连续混合阴影，保持覆盖中心的原始暗度和采样次数。路面原有阴影过渡、固定护栏遮蔽、远景渐现、连续路肩遮蔽和物理参数保留。

固定树、镜头及256个地表采样点，将阴影覆盖中心每步移动0.5m，实际渲染201帧。最大相邻步亮度变化由 **64.33降至2.33/255**，通过5.1/255阈值；代表点完整暗度范围两版均为64.33/255，渐入没有通过削弱全部阴影实现。见 [数值检查](shadow-check.json)、[进入边缘](shadow-enter.png)、[过渡中](shadow-transition.png)、[完整阴影](shadow-full.png)。完整采样在 `logs/PERF-04-FIX/shadow-{before,after}/report.json`。

## 验证与当前性能

- [相关T1](T1.json)：Ruff、60项环境/UI测试，以及种子0/17/23的headless检查通过。
- [渲染和生命周期](render-lifecycle.json)：直路/弯路/坡路共12视点，以及Scene重用、菜单、车库切换通过。
- [独立包](package.json)：仓库外三场景启动、20次重开状态检查和56项资源哈希通过。

[最终短测](performance.json) 使用1080p、12辆交通车、坡路、种子23，45秒有效前台窗口，后台负载保留；性能采样期间没有并行录像、构建或其他诊断。

| 指标 | 修复版结果 |
| --- | ---: |
| 实际绘制平均FPS | 55.88 |
| 绘制帧间隔P95 | 24.41ms |
| 最长绘制帧间隔 | 50.84ms |
| 大于50ms绘制间隔 | 1 |
| 采样物理丢时 | 0s |
| 预热物理丢时（单列） | 0.5833s |

尚未达到60FPS短测条件，未运行300秒正式测试。背景程序瞬时负载会波动，不能将与上一轮49.15FPS的差值全部归因于本次代码。测试结果不替代用户实际驾驶验收。

## 复现与交付

使用相邻项目解释器 `..\CoastalDrive\.venv\Scripts\python.exe`，以下输出目录须不存在。动态探针是显示诊断，物理冻结；树影探针包含显式渲染读回，都不用于计时性能。

```powershell
..\CoastalDrive\.venv\Scripts\python.exe tools/performance/check_dynamic_hud.py --pipeline cull-draw --output logs/PERF-04-FIX/repro-hud-before
..\CoastalDrive\.venv\Scripts\python.exe tools/performance/check_dynamic_hud.py --output logs/PERF-04-FIX/repro-hud-after
..\CoastalDrive\.venv\Scripts\python.exe tools/environment/check_tree_shadow.py --baseline --output logs/PERF-04-FIX/repro-shadow-before
..\CoastalDrive\.venv\Scripts\python.exe tools/environment/check_tree_shadow.py --output logs/PERF-04-FIX/repro-shadow-after
..\CoastalDrive\.venv\Scripts\python.exe tools/performance/benchmark_runtime.py --seconds 45 --output logs/PERF-04-FIX/repro-performance
```

新版完整独立包位于 `builds/0.8.3-perf04-fix/win_amd64`；`试玩-PERF-04.cmd` 与 `试玩-HWY-04.cmd` 均指向此包。历史包保留，本轮只本地提交，不推送远端。

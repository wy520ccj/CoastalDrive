# SCENE-01 — Gameplay Scene 生命周期

- 状态：done（自动验证完成；人工试玩待确认）
- 基线 commit：`ab3806eada6df067751aa691e4db40dd1ece8147`
- 前置：PERF-01 诊断

## 目标与范围

程序启动只建立窗口、渲染器和菜单；选定模式后显示一帧加载提示，再同步创建 Gameplay Scene。返回菜单关闭 Scene；同一路网、道路形态和交通数量下重赛复用 Scene。计时检查点在 Scene 内切换可见性，纯规则变化不触发重建。

- 修改：`src/application.py`、`src/scene.py`、`src/main.py`、启动测量脚本、定向测试和本任务文档。
- 保持：物理、交通规则、车辆、环境资产、阴影、LOD、模型、UI 主视觉和 120 Hz 仿真。
- 不引入异步加载或管理器层。

## 验收记录

| 项目 | 结果 |
|---|---|
| 启动到主菜单 | 三次可见窗口全新进程均未创建 Scene；菜单首帧中位数 1.140 s，PERF-00 旧值 7.372 s |
| 第一次进入滨海 | 八车 Scene 创建一次；首次切换中位数 6.017 s；加载提示实际先渲染一帧，截图已检查 |
| 高速与模式切换 | 高速 Scene 创建一次；相同道路及交通配置的自由驾驶/挑战切换复用；滨海计时检查点按模式显示 |
| 返回菜单与重赛 | 返回菜单移除 Scene 节点；任务、事件数量稳定；相同配置重赛不重建 Scene |
| 回归 | 定向 UI/生命周期测试 9 项通过；T1 gameplay、appearance、environment 及三种子 headless 通过 |
| 可见窗口短测 | 1920×1080、八车、驶过 365 m，27.4 s；报告 `passed=true`，截图已检查；这是短程 sanity check，不作为长期 FPS Gate |
| 人工驾驶 | 待用户体验确认 |

## 验证与证据

- `logs/SCENE-01-startup/summary.json`：三次启动和进入驾驶计时；菜单首帧 PNG。
- `logs/SCENE-01-loading.png`：加载提示首帧。
- `logs/SCENE-01-drive-smoke/`：可见窗口短程报告与截图。
- `logs/SCENE-01-T1-final/summary.json`：最终代码的 T1 结果。以上日志位于 Git 忽略目录，留在本机。
- 未运行 300 秒或更长性能测试；本任务不判断 60 FPS Gate。

## 收尾

- 提交范围：本任务文件；具体 commit 以本地 Git 为准。
- 下一步：停止性能相关工作，按原产品阶段计划继续；人工体验另行确认。

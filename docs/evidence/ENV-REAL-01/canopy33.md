# 2026-10-26：树冠体积选型与木本碎影过滤

接续本机KCD2/HD2画面样板。先复用原作者完整场景研究、核对最新实图，再内置imagegen生成[33与制作规格](../../design/garage-v2/33-canopy-volume.md)。原游戏安装只读，本轮没有新增导出或发行资产。开始HEAD `15c321f5`，原有大量未提交工作保留；本轮也未提交、未推送。

## 选型与实际失败

本轮实际阅读并查看[Gaijin植被法线工具](https://gaijinentertainment.github.io/DagorEngine/dagor-tools/addons/3ds-max/dagor-maxscript-toolbox/editing_normals_tool.html)的01/04/07示例，比较源法线双面处理、40%/70%冠形椭球混合。r01冠形候选在赋值前读v_texcoord，驱动明确警告未初始化，不能用作有效结果；修正为直接读原输入UV后r02重采。[r02数据](canopy33-normal-candidates.json)中单纯保留原朝向、两种混合的收益都有限，均未接入默认运行。没有改动源法线或把树改成球冠。

另检查橡树原材料表的shadow_proxy：当前read_mesh早已排除材质2，未发现代理误绘。原15个网格的子集审计留在ignored实验目录，未据材料名误删网格。

r03参考[NVIDIA原作者PCF说明](https://developer.nvidia.com/gpugems/gpugems/part-ii-lighting-and-shadows/chapter-11-shadow-map-antialiasing)，实际比较单次原读取、3×3帐篷/1或2纹素步幅、冠形混合+过滤。[数据](canopy33-shadow-candidates.json)、[原读取](canopy33-before.png)、[选中候选](canopy33-filter-candidate.png)。选择单纯2纹素步幅：它缓和叶卡黑亮碎影，仍保留较大遮挡；不采用改变法线的组合。

## 实现

只在local_kcd_drive.tree_shader中对现有太阳深度图做9次硬件过滤采样，二维权重1/2/1、合计16；原320m/4096²下最大单轴偏移约15.6cm。作用于大橡树、幼树与山楂，草继续原材质。太阳深度、分辨率、偏移、源alpha、模型、密度、LOD、天空29、曝光、道路与物理都没有改变。它是当前渲染器的局部抗锯齿，不是KCD2/HD2原引擎光照复原。

复测工具新增--unfiltered-canopy-shadows，仅在独立对照进程恢复旧读取；结束恢复原函数。诊断工具check_canopy_normals始终从显式未过滤版本构建候选，避免把新过滤当成旧基线。

## GPU与真实驾驶

[T0三LOD GPU](canopy33-gpu-T0.json)：过滤实际影响可见树木，开/关/恢复的太阳深度SHA相同，恢复后RGB逐像素相同；原天空遮蔽、零SSS遮罩与反向SH误差检查仍通过。测试1项，Ruff/pytest通过，37.7s。不是新人工驾驶证据。

正常默认/Draw、独立120Hz权威会话、1280×720/4×MSAA、同一HD2样板和Controller，按开/关/关/开依次实际山脊270m，各0碰撞/观察窗权威丢时0、全程前台/0最小化。截图回读帧剔除后：

| 运行 | 木本过滤 | 显示中位ms | P95 ms | P99 ms | 最大ms |
|---|---|---:|---:|---:|---:|
| r04 | 开 | 27.715 | 33.508 | 36.304 | 88.287 |
| r05 | 关 | 28.233 | 33.585 | 36.585 | 45.087 |
| r06 | 关 | 28.567 | 32.669 | 35.468 | 42.626 |
| r07 | 开 | 27.197 | 30.834 | 33.674 | 47.802 |

[完整摘要与限制](canopy33-normal-comparison.json)。各次tick/实际位置有小差异，不是逐帧锁定输入的GPU净计时；9次采样本身增加工作，不能把本批约1ms差归因过滤提速。当前仍不稳定60FPS，r04的88ms长帧保留，不能称卡顿已解决。真实[r07山脊120m](canopy33-ridge-120m.png)/[270m](canopy33-ridge-270m.png)已查看；全部帧留ignored logs。

r08实际沿海450m/4505行，[驾驶摘要](canopy33-coast-driving.json)与[保持核对](canopy33-preserved.json)：全部已记录Control/位置/朝向/时间/原点/进度/碰撞与上一HD2 r08相同，六处相机/车位/FOV同；四冻结资源字节、八源码LF归一SHA保持。真实[120m](canopy33-coast-120m.png)/[270m](canopy33-coast-270m.png)/[450m](canopy33-coast-450m.png)及40/190/360m保存；不扩大为完整Snapshot等价或人工接受。

## 命令与当前边界

```powershell
.venv/Scripts/python.exe tools/environment/check_canopy_normals.py --output logs/visual-upgrade-20261026-canopy/<新目录>
.venv/Scripts/python.exe tools/environment/check_interactive_local_drive.py --hd2-rocks --output logs/visual-upgrade-20261026-canopy/<新目录>
# 上条追加--unfiltered-canopy-shadows即旧读取对照，其他参数保持。
.venv/Scripts/python.exe tools/environment/check_hd2_rock_sample.py --full-drive --output logs/visual-upgrade-20261026-canopy/<新目录>
.venv/Scripts/python.exe tools/validate.py T1 --tests tests/test_local_kcd_drive.py --output logs/visual-upgrade-20261026-canopy/validation-T1 --timeout 420
```

本轮仅使碎影较柔和，完整画面仍未达到33。林缘/林下连续组织、山坡过空、用户实际驾驶/审美接受、偶发退出/等待和正式实时Gate仍开放。默认game-current和单独HD2入口共用这项木本材质；没有借这一项宣布整体升级完成。下一应以现有真实树位与树冠覆盖组织林下连接，并研究原件枝簇的大形，不能重走本轮收益有限的整树椭球法线方案。

最终T1：Ruff/34项（pytest205.83s，入口记录206.727s）及0/17/23三种子各1200步通过，[报告](canopy33-validation.json)。本次重跑完整相关模块，没有把此前32项结果当作新版本通过。之后只补文档和归档，无运行代码再改。三LOD最终GPU报告另存[此处](canopy33-gpu-T1.json)。草顶点早退在开工源码快照已存在，本轮没有修改该段，也不归因其性能收益；旧任务尾部仍停在早退审计阶段，不将那段文字误当本轮源码状态。

新实验目录logs/visual-upgrade-20261026-canopy是指向当前聊天C盘visualizations/canopy-study的junction；基线副本、失败与原始输出保留，没有清理原项目或旧证据。

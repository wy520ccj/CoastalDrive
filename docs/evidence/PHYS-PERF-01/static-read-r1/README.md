# 真实静态支撑批量读取 r7

2026-10-12，主目录main，基线 `a7b57ea`。当前仅关闭几何读取中的一段串行开销，**困难实时120Hz、慢动作及整体流畅目标仍未达到**。目标保持，不将局部提速当作收口。仅本地保存，不推送。

## 实现与验证

`static_support_read.h` 在一个原生入口读取真实Bullet刚体资格、碰撞掩码、稳定排序、形状/局部及父节点变换、margin、网格/边界/凸体标签与未注册Hull的实际可变边界。原签名逐值相同时复用原几何，移除真实退役引用；变化项仍由原代码构造相同几何。没有按修订号跳过实际检查，没有改变有限面查询、精度、120Hz、两个子步、完整玩家/困难NPC或原生正常交通模型。

- 固定真实坡道182静态体，独立ABBA各300次：旧平均约0.720110ms，新0.464749ms，核对几何相同。这是冻结世界的资格/签名读取耗时，不是完整物理步或FPS。
- 13车/GR86/坡道/seed23/9工作进程，预热120拍、采样480拍，ABBA四次完整Snapshot SHA逐拍一致。完整步均值13.822191→13.683175ms（−1.006%），仍超过8.333ms；后两次负载高于前两次，不与其他轮次拼接收益。
- 原相关T0 19通过；新增读取检查先因未用导入Ruff失败、pytest未跑，修正后5项通过。最终相关T1 **57项、全Ruff、0/17/23各1200拍**通过；两种子0/23各30秒、12NPC正常弯坡真实物理检查通过。包括缓存开/关、同名同位置的稳定顺序、质量/掩码/形状/父节点变化、有限网格标签替换、凸体增点、候选/凸体实际查询、完整共同求解与工作进程生命周期。没有重复完整T2/T3。
- 有效困难前台1080p/GR86/12完整NPC/坡道/seed23/9工作进程/30秒：旧65.357152Hz物理/68.886265绘制FPS/丢时12.316667秒；新66.224824Hz/69.612663FPS/丢时12.108333秒。窗口/权威及工作进程源码有效，均零玩家碰撞；两次退出1，性能Gate失败。只有一组短样本，不认定稳定整体收益。正常前台60秒本轮未测。

## 包与后续

r7四原生模块与最终src构建SHA一致，仓库外双模式真实会话启动、海岸8车120拍、离屏及各20次重开通过；截图实际查看。两个原试玩入口更新到r7，公开0.8.3和根入口仍独立。独立包启动、离屏和自动检查不代替流畅/手感验收。

后续优先权威进程的完整控制、轮端观测及快照装配，再推进完整车辆原生边界。当前约66Hz会持续产生真实慢动作；尚不能标记目标完成。

复现：

```powershell
.venv/Scripts/python.exe tools/validate.py T1 --tests tests/test_static_support_read.py tests/test_static_support_cache.py tests/test_suspension_candidates.py tests/test_convex_queries.py tests/test_triangle_support.py tests/test_continuous_solver.py tests/test_physics_workers.py --output <新目录>
.venv/Scripts/python.exe tools/performance/benchmark_physics.py --output <新目录> --workers 9 --traffic 12 --mode simulation --traffic-input-mode game --track endless --shape hills --driver endurance --seed 23 --warmup 120 --steps 480 --capture-hashes
.venv/Scripts/python.exe tools/performance/benchmark_runtime.py --output <新目录> --seconds 30 --track endless --shape hills --vehicle-design gr86-2022-premium-6mt --driving-mode simulation --traffic-count 12 --independent-clock
```

原始报告在 `logs/performance/static-read-r1/`。归档报告仅去除逐次GC数组，保留原路径/SHA。冻结基线仅改资源根目录适配，物理代码与旧DLL保持；微基准抽取该基线的原读取函数并共享实际不变几何构造器。T2/T3、正常长帧定位和人工Gate待办。

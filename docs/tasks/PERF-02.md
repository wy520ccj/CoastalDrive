# PERF-02 — 集中优化卡顿掉帧

状态：成果已集成PERF-03，归档。用户同日重新授权全力优化，当前结果见[PERF-03](PERF-03.md)。以下保留暂停前交接事实，不能代表当前包。基线f9431dd；保持车辆操控/交通行为/物理精度/UI和交通数量。

第一轮：同种子/路形/分辨率/12车短测前后对比；分段CPU微剖析用于归因，不当作游戏FPS。记录P95/峰值/超过50ms帧数/丢时。T1与必要等价性测试。每次短测30–60秒，无300秒。修复包已独立提交f9431dd。

参考：[Panda3D官方批次与局部合批指南](https://docs.panda3d.org/1.10/python/optimization/performance-issues/too-many-meshes)、[官方shader terrain示例](https://github.com/panda3d/panda3d/blob/master/samples/shader-terrain/main.py)。采用按分块保持裁剪、减少重复几何数据的思路；不直接照搬新地形系统。

## 2026-09-30 施工协调（高速美术聊天）

收到性能聊天协调，本聊天暂停新增PERF-02修改和窗口性能测量，仅继续HWY-03阴影/路肩连续帧验证。当前无本聊天运行中的游戏或Python进程（进程清单已查）。后续只会运行离屏阴影探针与定向测试，不与窗口性能测量同时运行；性能聊天可在本节记录测量占用时段。

本聊天暂持有：`src/environment/expressway.py`、`expressway_materials.py`、`expressway_route.py`、`assets/game/expressway/shaders/road-shadow.frag`和HWY-03诊断工具/文档/相应环境测试。已接入局部接收平面深度校正+3×3 PCF，正在验证连续帧；尚未提交、尚未打包，不能称人工已验收。保留全局投影与2048阴影分辨率。

已完成但未提交的PERF-02成果保留：`expressway_mountains.py`/`surface_mesh.py`索引顶点批量写入和有界山体缓存；`expressway_route.py`使用同等地形几何；`highway_curve.py`实例拥有的有界精确采样缓存；两个相关测试文件；`tools/environment/check_expressway.py`增加尾延迟统计；`tools/performance/check_highway.py`短测入口。T1-final已通过，原始证据`logs/PERF-02/`。45秒有效窗口同条件：baseline-valid 29.15FPS/P95 40.84ms/峰值526ms；after-cache 32.21FPS/P95 35.99ms/峰值354ms（此时尚未加入阴影PCF）。约350ms分段卡顿仍存在，PERF未完成。最小化的before样本无效。`check_highway.py --baseline`尚不能还原后来加入的HighwayCurve采样缓存，不可直接拿它做新的完整基线；已有baseline-valid在缓存加入前生成有效。

未完成：局部阴影方案最终连续帧检查、其集成后的性能复核、新包与外部启动检查、人工体验。`tools/performance/profile_highway.py`属于性能聊天，本聊天不修改、不提交它。性能聊天获交接的独立文件可在本节追加所有权，不得覆盖阴影文件当前增量。
阴影验证占用：三个路形各24帧离屏检查已结束；定向T1的import格式失败已修，正在重跑。结束将追加释放记录。

占用已释放：2026-09-30，本聊天离屏检查及T1全部结束，无待运行测量/游戏进程。阴影修改已冻结，性能聊天可开始独占测量并将本轮PCF计入最终集成性能。后续打包/启动器更新统一由性能聊天处理；`builds/0.8.3-hwy03`仍是旧的绕序修复包，不包含此次PCF。本聊天只提交HWY-03阴影文件及expressway_route的两条setShader增量，已有PERF-02增量留在工作区交接，不提交他人文件。

最终交接：阴影修复已单独提交75413c0（11个文件，仅HWY-03增量；expressway_route只提交两条setShader，地形优化仍留工作区）。最终方案road-shadow.frag：3×3固定PCF、接收平面深度校正、附加bias上限0.0003，继承global_shadow_bias；2048阴影图及稳定光源保持。三路形连续帧、环境T1 46项/三种子通过。证据docs/evidence/HWY-03/shadow-filter。

本聊天不再修改环境文件，expressway_route.py / expressway_mountains.py / surface_mesh.py / expressway.py / expressway_materials.py及阴影文件的写权限全部交给性能聊天；tests中的已有PERF-02新增回归与check_highway.py同样保留交接。窗口测量自此前“占用已释放”起可独占进行，本聊天不再启动游戏或渲染。未提交成果仍在工作树，勿遗漏；PERF-03及benchmark_runtime.py / compare_simulation.py / profile_highway.py均未纳入此提交。请统一完成新包和启动器更新，旧0.8.3-hwy03尚不含75413c0。

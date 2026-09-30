# UI-NOTICE-FIX 深蓝提示底板稳定性

2026-09-30，用户追加左上深蓝块闪烁，暂不能回忆是底板消失、亮度跳变还是文字闪。当前运行进程为旧builds/0.8.3-audio02；本轮来源已有RADIO-01的提示高度缓存和/Draw管线。

真实前台、未最小化的240帧固定场景探针，覆盖稳定文字、每帧换字、每帧长短文本交替，没有复现整块底板缺失；[原版固定背景](before-game.json)。不能把旧Cull/Draw文字问题写成本次已经确认的根因。

确认的现象是底板alpha=0.86，会显示场景明暗。采用稳定2D背景交替深浅的同条件窗口对照：原版底色单步最大变化35.43/255、117帧偏离颜色中位超过15/255；底板改为alpha=1且MNone后最大0.99/255、异常0/240。两次全部渲染观测均前景/未最小化；[原版](background-before.json)、[修订](background-after.json)。此对照证明背景透色变化消除，不证明所有可能的间歇缺失原因。

![修订后的实际游戏HUD](<B:/AI agent/暑期计算机程序设计/CoastalDrive/docs/evidence/UI-NOTICE-FIX/after-game.png>)

修订保留字号、位置、长提示高度和电台标签，只固定底板实色。真实海岸场景再录240帧，零异常、最大变化0.33/255，全部前景/未最小化；[场景复测](after-game.json)。窗口录像在logs/UI-NOTICE-FIX/{repro,background-before-visible,background-after-visible,after-game}/window.mp4；截图和读取不用于FPS结论。

初次录制窗口名与用户正在运行的包冲突，后改为唯一标题；中途失去前景的background-before录制也排除。仅上述可见完整对照进入交付证据。新增探针首次Ruff因import排序阻断T0/T1，调整后相关6项UI T0通过；最终T1/种子记录见[T1](T1.json)。独立包同RADIO-02，新包已包含此次修订；用户实际驾驶闪烁体验仍需以新版结果为准。

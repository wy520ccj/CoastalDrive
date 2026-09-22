# 旧版 MFC 工程

`ADAS/` 是本项目改造前的 Visual Studio C++/MFC 源码参考。当前游戏在 `src/`，不依赖这个目录编译或运行。

公开副本只保留源码、工程文件和图标。原始文件仍在上一级工作库的 `ADAS/` 与 `ADAS.zip`；这里将 GB18030、UTF-16 文本转为 UTF-8，方便 GitHub 和网页 AI 阅读。未上传自动生成的 `.APS`、用户设置、运行日志和来源许可未确认的爱给网音效。工程中的音效资源条目因此被移除，旧版碰撞音不会播放；此副本未作为可运行交付物验收。

从 `ADAS/CSimulationEngine.cpp` 可以看到旧交通与随机行为实现；改造后的道路、交通和车辆分别见 `src/highway_curve.py`、`src/highway_driver.py`、`src/vehicle.py`。旧工程的问题分析在 [legacy-traffic-review.md](../docs/legacy-traffic-review.md)。

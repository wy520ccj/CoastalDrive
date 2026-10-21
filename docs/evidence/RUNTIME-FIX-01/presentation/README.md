# 绘制节奏与呈现等待续查

接续213526e5；原上级目录证据保持不改。实际生产同步窗口去掉额外90Hz睡眠，P99约19→13ms；终点每次重建真实源码目录以减少不存在路径的磁盘查询，约33→22ms。相关T0/T1通过，6074帧真实圈位姿/圈速/分段与原记录字节相同，当前版本复载通过。

偶发约0.1s停顿尚未修复，目标仍active。video-pacing的120秒有分项候选0长帧；native-window无分项复核仍1长帧/严格Gate失败，不互相替代。single/关闭同步均失败且未采用。当前仍/Draw和垂直同步。

native-stacks为侵入式自有诊断进程抓栈，只在调用已>40ms后短暂挂起窗口线程（物理子进程保持），不算性能通过证据。展开无错误，采集约1.09ms；实际导出表偏移对应end_flip/SwapBuffers/NVIDIA/WaitForSingleObjectEx。DLL仅诊断，非游戏native扩展；C源码与实际DLL都冻结。官方API为GetThreadContext/RtlLookupFunctionEntry/RtlVirtualUnwind，恢复在C finally内保证。

运行脚本的runtime-tool.py是各自实际执行版本；首两个早期采样尚未保存该副本，其区域计时未覆盖延迟创建的阴影缓冲，限制见任务包。检查日志保留完整，未重复原32/26项有效模块。ETW脚本语法检查通过，但实际启动被Windows以0xc5585011拒绝，无ETL/无采样/WPR未启动；管理员采集待用户操作，不虚构结果。

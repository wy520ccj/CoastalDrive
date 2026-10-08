# Package r10 证据归档

构建基于main HEAD `6d58e9a` 与当前冻结的制动修正源码。构建返回码0，耗时约29.45秒，主目录输入SHA前后相同。机械原生PYD为128,512 bytes，SHA-256 `d23a8665e35e08dd23dfbbba3009a22d5ed9589fa18c1f1dbaa8a8cf9dd12c8a`；轮胎接触PYD为52,224 bytes，SHA-256 `0668d40d48e9ddc3d27504c6fb1480653cb16d69f220d8beadf53dcb2d6aa833`；两者打包副本均逐字节匹配输入。完整源码和工程输入SHA在build摘要中。

仓库外Game与Simulation headless各120拍、seed17、GR86配置，均返回0且完整硬件字段可见；可执行文件、许可与GR86工程配置存在。两个模式的离屏test-track smoke均通过，Game tick260、Simulation tick256，20次节点/task/event稳定性标记均通过。测试道路traffic_count为0。原始日志、JSON、脚本及截图已归档并逐件记SHA/bytes。

离屏渲染不代表前台FPS、交通负载性能或人工驾驶验收。本归档未复制大型候选包，未重复T1/T2或其他物理验证。

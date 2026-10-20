# ROAD-AB-DIAGRAM-01 原始证据

基线main/e8a2d0cc，仅道路A/B显示与交互改动。没有持久化/物理/评分/SDK变化，无新完整驾驶。

`normal`、`double`分别为当前源码另起实际独立120Hz进程的只读界面，共各八张图。输入来源是PLAYER-ROAD-AB-01实际前胎A/B、BRAKE-ROAD-AB-01实际制动A/B，summary保存原路径/SHA。全部交互与渲染前后Snapshot及两份输入字节保持；源/SDK首末一致。原7718过门拍、9560制动拍明确复用，不另计为新驾驶。

实际图包括slalom-focus默认第3门、slalom-next第4门A未到达、slalom-table原数值表、brake-distance最大前进点和brake-table原制动表。未到达以轴外—标示，没有零值条或外推轨迹。图是整车余量/停车位置摘要，不是车辆路径。

三个fixture文件和对应图片明确为显示夹具：定点162/172米，过门前结束且B为空，失败43米/实际B35.193米同轴；不是新实际驾驶。成功实心、失败空心，失败不产生有效差值。

已查看Normal1280×720实际漏门/下一门/制动表及Double1024×768制动点/过门表和三个边界图；人工手感/可见实时性能/趣味性不由离屏证明。没有渲染后生产微调。

`checks/T0`为测试常数链式比较Ruff失败、pytest未跑；`T0-final`6项通过，pytest32.71秒。两库最终相关T1各15项及seed0/17/23通过，pytest292.34/231.20秒。

`archive-manifest.json`记录47份原始文件共6,532,003字节，来源/原始SHA可逐项核对；`source-manifest.json`记录6最终代码/测试/工具的LF SHA。原生机械模块SHA保持c84bfb06cae9d51a46f5cdff69107f96e73c6757d2853ef46673d0710010e7a2。T2/T3未跑，原物理T2失败、实时/人工Gate开放，持续目标active，仅本地无推送。

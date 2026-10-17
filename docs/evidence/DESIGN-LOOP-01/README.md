# DESIGN-LOOP-01 证据

基线main/72fabc1；实现与验证细节见[任务包](../../tasks/DESIGN-LOOP-01.md)。

- `comparisons.json`：普通/Double各4组完整真实计算的差异报告、原始记录路径、源码摘要哈希和实际原生运行库。源摘要对应各次生成版本；不把后续UI/显示边界修改声明为相同全源版本。
- `normal-T0.json`：74项与Ruff通过。
- `double-T1-230-pass-1-fail.json`：原始失败汇总不改写；230项通过，1项旧绘图读取测试类型错误。
- `double-T1-supplement-1-pass-seeds.json`：仅修测试最后一处tuple转换后，该项与0/17/23各1200拍通过。生产源码相同，230项明确复用。
- `normal-workflow.json` / `double-workflow.json`：真实实验窗口、磁盘加载、独立游戏进程、关闭后回到实验室；普通最终只跑UI，避免重复已有4组计算。
- PNG：实际1280×720联动面板/完成提示/游戏菜单/试驾，以及1024×768返回实验室，均已查看。

这些证据覆盖功能与显示，不代替人工驾驶手感、工程车实时性能、跨运行库误差标定或原精度Gate。

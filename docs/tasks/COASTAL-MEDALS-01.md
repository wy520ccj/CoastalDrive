# COASTAL-MEDALS-01 滨海计时目标

- 状态：done（自动功能完成，人工趣味性pending）；基线main/9eb7bf9，开始前干净；前轮驾驶进阶为progress，用户选择驾驶挑战与成长。两段原始参考已读，按本地事实取舍。数值前置修复与剩余Gate见PHYS-SHARED-ROUNDING-01。
- 目标：为现有滨海计时圈增加可追赶的铜/银/金标准、赛中目标与结算差距，结合原分段/个人最佳幽灵鼓励下一次驾驶。
- 先测量：默认当前游戏车/原辅助/120Hz真实赛道，已有RouteDriver作为模型基准，另测实际KeyboardController二值请求能否完成；先记录有效/无效、圈速/碰撞与完整条件，再冻结目标。不是人工手感证明。
- 范围：仅滨海计时的目标评价/显示与相关入口提示，已有保存的完整硬件/输入分组圈速可显示历史奖牌；有效圈才获奖，无效/提前结束/别的赛道不评。旧存档/分段/幽灵保持，奖牌派生而非另一份状态。无需新生涯面板或经济/硬件奖励。
- 禁止：改物理模型/默认硬件/辅助/120Hz、原门线/判圈/倒车/检查点相机/幽灵兼容边界、SDK、瞬移/禁碰/放宽原Gate、推送。真实Double数值失败按独立前置任务修复，不能用UI通过替代；仅该任务重编机械核，其余原生模块保持。
- 验证：冻结标准后纯规则/T0→相关T1/三种子；目标边界、旧历史/硬件分组、无效/未完成/存储错误、赛中/结算/重试/幽灵回归；普通Double真实驾驶与两分辨率实际图，原记录只读复核分别记账。人工趣味性与原精度/实时Gate继续开放。

## 目标冻结

原基线默认游戏车/单机械步/原辅助/seed0：RouteDriver90连续Control50.606774s；实际二值键盘90/60/45/35目标分别49.918965/51.538891/59.707218/73.531006s，五圈均有效、零碰撞。先保存真实请求/位置/完整条件再定档：金≤55s、银≤65s、铜≤80s。它们是当前赛道玩法目标，按当前硬件分组评价，不声称每辆车同难度或人工趣味性已通过。

同时修复原BestTimes保存失败仍在内存替换最佳/分段/幽灵链接、RaceTracker仍声明new_best的存储边界；不改变有效圈判定。失败保留原已保存参考，允许展示本次有效奖牌并明确未保存，不能把未落盘结果变成下一场个人最佳。

## 实现与验收

- 主菜单计时按钮小字显示同硬件/输入组的已保存奖牌和下一目标；旧数字成绩保留，不凭空补分段或跨组发奖。HUD在原分段下列完整三档与出发时目标余时，错过目标后提示仍可争取的低档，超80秒也可以完成有效圈；自由驾驶/其他赛道/短课题不显示滨海目标。
- 结算显示本圈奖牌、距下一档的差距，金牌后追赶个人最佳；复用原三列分段及幽灵。只对滨海计时完整有效圈评价，提前结束/复位等无效圈不发奖；奖牌直接派生总圈速，没有新增成长存档。工坊道路通过仍按原有效圈规则，不要求拿牌。
- BestTimes改为写盘成功后才提交新的内存总时长/完整分段/幽灵关联状态；原子替换失败保留旧字节和内存参考、其他组与旧幽灵链接，失败第一圈不变成重试参考；new_best必须保存成功，较慢下一圈不继承上次存储错误提示。幽灵兼容规则未放宽，C/判圈源码修订后的旧幽灵按原机制提示版本不兼容，旧总成绩仍保留。
- 最终普通1280×720、Double1024×768各真实KeyboardController三圈：铜73.53660344913249 / 73.53052507758666s，银59.7037988014685 / 59.70045261419741s，金50.16815290438231 / 50.041664063881974s，均有效/零碰撞。重试载入前一完整最佳及对应幽灵；再各独立启动只读恢复金牌/分段/完整幽灵，分数文件字节不变。展示采集冻结更新并按真实车位重置相机，不冒充人工驾驶或实时性能。
- 六圈普通8825+7165+6021、Double8824+7165+6005拍，共44005拍；保存位置/速度/真实请求/规则结果逐拍纯规则复算一致，3次最佳总时长/分段/幽灵校验/帧数及独立重启一致。复核历史幽灵使用归档当时上下文，只证明原文件内部一致；当时独立启动才是生产兼容验收，不声称未来源码可继续播放。
- 普通改数值前3圈与最终3圈所有已记录JSON字段字节一致，复用一份GZ并保留两份摘要及共享内容SHA；这不是完整求解器内部状态等价声明。最终图像已查看，初版有存储警告时表格与按钮重叠，按OnscreenText实际上沿修正；其自身文字坐标和NodePath偏移不能重复叠加。
- 首轮核心T0因I001停止，排序后50项通过；首UI10过3失败，其中HUD夹具未打开父层、未达铜文字预期各1，真实存储警告布局1，修复后完整新旧UI13项通过（63.79s pytest）。数值修复前普通相关T1 65项/三种子、Double规则/UI53项通过；初次真实Double低速圈失败，已如实进入独立数值修复，不以这些检查冒充道路通过。
- 最终生产机械核后，普通完整相关T1 **661项通过**（181.94s pytest）及0/17/23各1200步启动通过，覆盖数值/传动/原生、原低速实际回归、奖牌/存储、分段/幽灵/独立进程与菜单/结果。Double新增低速回归通过，相关机械587过/2项旧Normal字节夹具跨SDK失败，旧模块同样失败；修复前53项规则/UI证据明确复用，最终实际三圈/两分辨率与独立重启另计。两项失败不改写为通过。
- 物理方程、原阈值/入口/门线/辅助、120Hz及SDK保持；仅数值择步与机械核重编见[PHYS-SHARED-ROUNDING-01](PHYS-SHARED-ROUNDING-01.md)。原T2真实失败、实时/人工与两项Double字节基线Gate继续开放；本批T2/T3未跑，持续目标active，未推送。

## 命令与证据

```powershell
.venv/Scripts/python.exe tools/coastal_medal_probe.py --output logs/validation/COASTAL-MEDALS-01-probe --cases analog:90 keyboard:90 keyboard:60
.venv/Scripts/python.exe tools/coastal_medal_probe.py --output logs/validation/COASTAL-MEDALS-01-slower-probe --cases keyboard:45 keyboard:35
.venv/Scripts/python.exe tools/coastal_medals_check.py --output logs/validation/COASTAL-MEDALS-01-normal-fixed-drive --size 1280 720
.venv/Scripts/python.exe tools/physics/run_sim_double.py tools/coastal_medals_check.py --output logs/validation/COASTAL-MEDALS-01-double-fixed-drive --size 1024 768
.venv/Scripts/python.exe tools/coastal_medals_check.py --output logs/validation/COASTAL-MEDALS-01-normal-fixed-drive --size 1280 720 --restore
.venv/Scripts/python.exe tools/physics/run_sim_double.py tools/coastal_medals_check.py --output logs/validation/COASTAL-MEDALS-01-double-fixed-drive --size 1024 768 --restore
.venv/Scripts/python.exe docs/evidence/COASTAL-MEDALS-01/recheck.py --evidence
```

验证工具输出目录须新建，复现时改新名；--restore沿用对应驾驶目录。T0/T1完整命令见checks各summary.json；证据75份原样输出/24.04MB与10项归一LF源码在[目录](../evidence/COASTAL-MEDALS-01/README.md)。下一步闭合两项Double原始字节参考的SDK口径，再按实际体验完善驾驶内容；不继续堆叠成长页面。

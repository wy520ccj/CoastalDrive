# RUNTIME-FIX-01 卡顿、运行bug与画面检查

- 状态：in_progress；基线main/5244d220，开始时工作区干净。
- 用户目标：检查卡顿掉帧以及各种bug、画面问题并修复；不要过度检验边界。
- 先测当前真实窗口高速/滨海与启动/结算切换，区分物理Hz/欠账/丢时、帧P95/P99、CPU/等待及实际画面；历史GAME-DRIVE-01仅定位参考，不复用作当前性能结论。
- 依据测量修复明确热点和确认bug，保持120Hz唯一物理、碰撞、原认可操控与实验台完整模型。相关T0/T1与同场景前后比较；不靠降物理、改阈值或FPS单项宣称流畅。
- 实际命令、失败、源范围、画面与下一步在后文续记；本地实施，不推送。

## 当前诊断与修复

- 先运行`benchmark_runtime.py --seconds 30 --traffic-count 18 --audio --trace-phases --trace-streaming`：真实前台1080p/18NPC/弯坡，旧工具默认inline物理，68.39FPS/P99 27.50ms、120.004Hz、0丢时；只作定位，不当正式配置基线。确认正式入口默认SessionProcess独立时钟后，修正工具默认匹配正式配置，保留`--inline-clock`显式旧诊断，原`--independent-clock`兼容。
- 正式配置30秒`--independent-clock`：86.41FPS/P95 16.64/P99 19.07/最大32.99ms，119.997Hz/落后P95 15.45ms/峰33.59ms，0丢时/停滞/碰撞。距离约562m未达到原600m完整性要求，总passed=false，未放宽。窗口分项和权威分项显示新路段attach均值15.98/峰19.26ms，主因是TriangleSupport递归反复规范顶点/计算面界/排序键，亦会阻塞相机查询。
- TriangleSupport.build同一网格只准备一次顶点、面界与三轴排序键，递归只划分索引，原稳定排序、二分、叶面顺序、边界和原生索引构造不改。实际24个弯坡网格ABBA：旧54.54/51.23ms，新45.75/47.04ms；整树公开字段序列化SHA相同。局部构建成本，不冒充整体帧率改善；无机械参数、碰撞或native扩展改动。
- 相同正式负载40秒：85.98FPS/P95 16.96/P99 19.09/最大28.20ms，120.012Hz/落后P95 15.57ms/峰35.03ms、0丢时/停滞/碰撞、811m，原短Gate通过。attach均值14.23/峰17.58ms；时长不同且总FPS无明显提升，不声称稳定整体收益。
- 120秒无分项插桩实际前台：86.12FPS/P95 17.03/P99 19.39/最大127.54ms，共2绘制帧>50ms；119.995Hz/落后P95 15.55/峰32.97ms、0丢时/停滞/碰撞，2843m。功能完整性passed=true但严格short_performance_passed=false，偶发绘制停顿仍未修复，不收口整体目标。
- 远景空气透视原固定采样天空赤道色，较高山体/云层方向产生明显色块/点阵边缘；改为与天空球同经纬度取样。只改高速shader，保持几何、覆盖范围和原抖动渐隐。固定相机实际旧/新图比较，早期相机误用全局位置已在最终工具改为相对玩家位置；最终图另采。
- 窗口ICO原相对路径不在Panda搜索路径；改绝对路径后仍暴露中文路径加载失败。确认同文件LoadImageW成功且Panda1.10.16原生get_icon用窄字符LoadImage，新增仅Windows真实窗口Unicode图标资源加载/释放；离屏和其他系统跳过。原ICO及打包资源保持。实际中文目录小/大图标WM_GETICON均等于所加载句柄，销毁窗口后释放通过。
- 原始官方实现定位：https://raw.githubusercontent.com/panda3d/panda3d/v1.10.16/panda/src/windisplay/winGraphicsWindow.cxx （get_icon，LoadImage及警告）。本次不改引擎或复制新图标资产。

## 验证

- `validate.py T0 --tests tests/test_triangle_support.py::test_prepared_build_preserves_real_road_tree_and_query_order --output logs/validation/RUNTIME-FIX-01-T0`：Ruff/1项通过；12份真实网格完整树pickle相同与48个接触查询相同。
- `validate.py T1 --tests tests/test_triangle_support.py tests/test_expressway_route.py tests/test_scene_lifecycle.py --output logs/validation/RUNTIME-FIX-01-T1`：Ruff/32项/seed0、17、23各1200步通过，pytest检查22.0秒。覆盖原有限面/胎宽/原生查询、真实流送生命周期与场景返回；当时application仅绝对图标路径，后续Unicode图标补丁另验，不冒充该T1覆盖后改动。
- 图标补丁初Ruff为import顺序失败，已直接修正；正式补验另记。实际原始日志和失败保留，不重跑已不变索引/流送套件。

- Unicode图标第一版同步SendMessage在真实/Draw启动时互等（单线程小窗口未覆盖该路径）。确认仅该诊断主进程CPU约1.7s、无权威子进程/报告，停止明确PID17796；该120秒trace没有进入驾驶，不能当性能样本。改为PostMessage后重启于全新long-trace-fixed目录，后续实际/Draw图标检查另记。原日志保留。

- 新增/Draw图标查询初工具也在主线程同步WM_GETICON，超时失败；改为读取线程查询、主线程继续正常任务泵，`check_window_icon.py --output logs/validation/RUNTIME-FIX-01-icon-draw-fixed`实际小/大图标句柄及销毁释放通过。两次失败均未隐藏。正式120秒long-trace-fixed正常结束且无图标警告。
- long-trace-fixed有效前台120秒：86.31FPS/P99 19.14/最大124.02ms，共2帧>50ms，120.003Hz/落后峰36.22ms、0丢时/停滞。分项render-frame峰113.187ms/主线程CPU0，另81.471ms/CPU0；声音、GC、物理同刻无长停，定位为绘制线程/驱动等待，根因未闭合。
- 滨海真实RouteDriver完赛并观察2秒：完赛处244.7ms、转结算99.4ms，实际完成有效圈/幽灵保存，严格短Gate失败。定位Session.record_ghost_step在终点再调用ghost_context：87份源码AST约14万个节点，本机原函数复测207ms，冷调用278ms（含首次SDK摘要）。加128项有界、以完整源码内容/包为键的依赖解析复用；每次仍重读源码、枚举依赖、内容SHA和原SDK摘要机制不变，不按mtime跳过或弱化兼容规则。旧函数/新冷/新暖完整上下文字典相同，暖调用59.5ms，源码新增import及新依赖内容变化均被检测。
- 补齐后续新增奖牌/目标/幽灵/分段固定字形并分别预生成主字体/分段字体，原布局和文字保持。原离屏完成态探针刷新22.14→8.98ms，100组旧/新换行一致；该探针首次渲染仍87/116ms，不能当实际前台改善证据。
- Ghost依赖T0初失败为新增测试误把Windows路径当斜杠字符串，改为真实Path相对值；生产算法已包含新extra.py，未因失败改兼容判定。补验`validate.py T1 --tests tests/test_lap_ghost.py tests/test_ghost_session.py tests/test_coastal_medals_ui.py tests/test_race_feedback_ui.py tests/test_scene_lifecycle.py --output logs/validation/RUNTIME-FIX-01-finish-T1`：Ruff/完整5模块26项/三种子通过，pytest检查133.8秒。包括独立进程真实完整圈、落盘/重新载入/暂停返回；原32项索引/流送T1有效结果复用，没有重复大套。
- 真实50.6秒圈幽灵无损压缩局部比较：level5约23–24ms/861KB，level1约6.7–6.9ms/1085KB，level3约16.6–16.9ms/883KB；解压字节均相同。目前仅记录候选，生产压缩等级仍5，未因此改格式或采样。
- 最终相对玩家坐标的固定实际rear/bay/mountain旧/新各3图在final-views-before/after，0新增物理，已查看海湾对照，远景天空方向匹配改善。该静态检查不替代行驶窗口或人工验收。

- 首轮结算修复后的真实前台完成同一50.6秒圈：最大98.73ms/1帧>50ms、86.99FPS/P99 16.44ms，物理119.740Hz、0丢时，严格Gate仍失败。权威版本复核56.67ms、ghost保存29.02ms，相机等待85.26ms。继而仅在每次依赖图扫描内去重重复module名（不跨次跳过文件检查），完整上下文仍与旧算法相同，暖复核降至32.74ms；无损压缩采用level1，真实原圈候选解压完全同字节、约增加224KB文件换取约17ms收尾计算减少。原CDG1/元数据、120Hz位姿采样、SHA内容关联和旧level5加载保持。
- 后续`validate.py T0 --tests tests/test_lap_ghost.py --output logs/validation/RUNTIME-FIX-01-ghost-final-T0`：Ruff/完整8项通过；26项T1前版未变模块复用，真实最终完赛另测，不重复其独立慢窗口完整圈。

- 最终实际同圈前台（含分项）86.99FPS/P99 16.33ms，119.853Hz/0丢时，已实际完赛观察2秒；幽灵收尾45.16ms（版本32.70、保存12.07）、相机等待44.38ms，终点主帧55.72ms、首次结算44.62ms。相比原终点244.71ms/结算99.36ms明显减少，但仍有一帧终点>50ms；结算静止约1.6秒后另出现renderFrame等待81.46ms/主线程CPU0，绘制间隔98.79ms，整体严格Gate仍失败。此静止结果页证据排除了只由道路流送/物理计算引发全部长帧的解释，下一继续绘制线程/驱动等待定位及终点余量，不放宽阈值。
- 三次真实圈均6074帧、50.60595505566297秒、五段门线时刻和全部34d车身/车轮位姿字节SHA完全相同；这是幽灵位姿/规则证据，不声称全世界完整Snapshot等价。最终level1文件约1085KB（原861KB），当前源码/SDK上下文匹配并独立载入、终点插值通过，旧数据没有覆盖。最终实际结算图已查看。
- 仅保存本地施工检查点；本任务和整体目标均in_progress/active，渲染等待及终点短Gate余量未闭合，原ABS精度/实时/人工阶段Gate不因此改变。不追加全量T2/T3或边界矩阵。

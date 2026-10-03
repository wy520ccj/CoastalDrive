# PHYS-ROT-01 机械轮轴与轴承反力

2026-10-03，基线`ec469b7`（04实现为`e635124`）。两模式默认启用，reference-v9/game-controls-v8，64字段完整参数见[参考表](reference-v9.json)。**自动部分完成：111项相关T0、44条A/B、4条坡停、20条原生诊断、完整730项T1及全部三种子启动/双种子弯坡通过；273个Python文件验证前后哈希一致。**首次失败、中断与r1失败保留；实现/证据本地提交2b7f908df29176ce99ccb1fb0d848ce318474b02，未推送。整个物理goal保持active，人工及阶段Gate仍待完成。

## 生产机制

`wheel_geometry.py`分开机械右轴e与路面normal n。保持原射线轮毂`hub=p+r n`，取`t=normalize(n×e)`、`l=t×n`、`ρ=e·((-r n)×t)`。Fx车身广义力臂为`p×t−ρe`；纵速为`V·t+Ω·(p×t−ρe)`，表面纵速再减去`ρω`。这是接触广义坐标，不等同于一般倾斜/转向时的轮心投影速度。ABS/TCS使用同一采样ρ和广义纵速，未改容量、硬件或增益。

正滚动车轮自旋角动量为`S=−ΣJωe`。`rotor_dynamics.py`计算零功车身随动反力`S_end×Ω_end`，四轮求解内用`(I−h[S_end]×)Ω_end=IΩ_free`。局部轮胎Newton保留物理对称Mobility；每轮扫次冻结共同轴承力，最终残差重新核对真正共同末状态。反力与轮胎/制动一起求解后才提交到同一Bullet车身，未覆盖运行速度/姿态；Bullet自身刚体陀螺项仍保留。

每个轮胎子步插值真实齿条角。指定转向的轴向变化反力为`Jω_old(e_new−e_old)/h`，驱动/制动/接触轴向项负责`JΔω e_new/h`，两者合成精确的冻结车身姿态下乘积变化。转向执行器功按共同末Ω单列，陀螺功为零。此功对应当前轴向转子输运模型；射线支撑尚无独立转向节/主销/簧下多体模型。道路normal改变不生成转向执行器反力。全局0.001N、局部0.0001N、制动等效1e−9N、20次迭代及原能量3e−9J门槛保持。

Snapshot记录采样机械轴、有效半径、累计陀螺/转向冲量和指定转向功；纵横接点角冲量分别累计，诊断工具不会用最后一子步基轴重算转向中的全部冲量。玩家/NPC/reset/rebase/回收/模式重建走同一Tires，不增加第二套车辆状态。刚性/柔性轮胎开关与转子开关独立，真实接地短程两种组合均验证。

## 已完成证据

- [最终关闭分支](compat-off-final/README.md)：显式关闭转子，与04冻结A加速/转向/倒车共122,632个既有快照单元精确相等；75生产Python文件运行前后SHA一致。旧初始差异与修正复测均保留，不覆盖历史。
- [44条两模式逐tick A/B](ab-initial/summary.json)：两模式各11工况，6s/120Hz，完整配置仅转子开关不同，77个生产/相关工具哈希前后一致。加速末速度两模式相同；阶跃末速变化game−0.01653m/s、simulation−0.03146m/s；饱和转向−0.03541/−0.06622m/s。转向指定功分别保存，不要求所有操稳指标改善。该批仍以默认关闭的候选源码运行，但每条B显式开启；之后只改默认开关与成绩/导出版本，无驾驶方程变化。
- [4条真实5°坡停](grade-initial/summary.json)：先5s静置制动，再10s完整轨迹；漂移0.0019275～0.0019284m，平均Fx约1026N；原0.01m与1%理论力平衡门槛保持，源码前后稳定。
- [12条无外力原生轨迹](free-world-initial/summary.json)：spin0关闭及spin60开/关，各120/240/480/960Hz走1s，gravity/damping/drive/brake均0。spin60、120Hz世界角动量偏差86.256139→0.163144Nms；细化后0.0819479/0.0395207/0.0205128Nms。对应能量变化−0.032526/−0.016193/−0.008441/−0.004047J。机械功恒等式不等于有限旋转严格守恒；这些误差必须保留。
- [8条补充原生轨迹](free-world-zero-and-steer/summary.json)：spin0开启与旧关闭各步长读数完全相同；spin60首次子步指定前轮3°转向，120Hz能量变化+0.088891J、指定转向功+0.175465J；陀螺反力不承担该非零功。该诊断固定首次角位移，步长细化并不细化这一瞬时转向输入，不将其功差当连续转向的精度结论。
- [T0原始记录](validation-T0/)：最终默认开启111项通过，涵盖27组独立虚功、60组坡度/转向/驱动/制动共同末状态功和动量、世界逆惯量旋转等变、原生时间细化、柔性独立开关、反馈、真实NPC生命周期与参数导出。先前99项台架、105项扩展各自保留。首次重复`--tests`只跑12项旧测试，随后新测试失败来自独立夹具漏计相对转速Ω·e；修正公式后99项通过。扩展首轮ruff要求pairwise后修正；未放宽力/功门槛。

探针实际源码副本及SHA见[probe-source](probe-source/sha256.json)。上述源码、配置、时序与轨迹均是设计模型证据，未作实车测量或人工驾驶验收。

## 初轮验证与修复历史

初轮完整T1于UTC05:36:07启动，730项集合的第120项`test_post_bullet_slip_matches_current_snapshot_velocity_and_contact`出现失败：旧轮心投影速度7.685492m/s与真实广义接触速度7.685377m/s相差约0.000115m/s。独立复现后，主动停止pytest实际子进程17684，runner以非零退出码4294967295记录失败，后续headless/弯坡未跑；472.5s耗时不是完整730项结果。[初轮原始日志](validation-T1-initial/summary.json)及终止原因保留，初轮[273文件清单](validation-source-before.json)保留。未借此调整生产方程或放宽测试门槛。

该节点改为从轮毂/表面相对运动独立核对广义纵速及有效半径，仍保持原1e−6速度/滑移门槛；[修正后的单节点T0](validation-T0-snapshot-geometry/summary.json)通过。当前完整命令：`.venv/Scripts/python.exe tools/validate.py T1 --area vehicle --area core --area gameplay --area traffic --area road --output logs/validation/PHYS-ROT-01-T1-r1 --timeout 7200`，执行会话`83431`，实际启动时间以runner summary为准。冻结[273文件r1清单](validation-source-r1-before.json)，生产物理与初轮相同，只改上述独立测试期望。当前pytest运行中，后续三种子headless与双弯坡尚未开始；不得将相关T0当作完整T1。

通过后核对273文件SHA、保存T1原始回执、完成本地提交，再建立PHYS-DRIVE-01。发动机/有限离合/开放差速器、布局/悬架/估计器/实车型及研究接口仍待实施；传动功能组之后再T2。整体T3、真实可见性能和用户两模式驾驶Gate仍待完成。

T1-r1冻结期间新增[下一传动闭环准备](next-drive-design.md)：发动机自旋并入ROT独立求解副本，理想齿轮/双向效率各50组、静止/倒挡回拖12组及静止活动集修正6组均通过原门槛；省略发动机陀螺项的负对照准确出现理论缺项。仅证据目录，273生产/测试/工具哈希不变，尚未接入动力总成驾驶。


## T1-r1旧版本断言历史

UTC06:24第646节点`tests/test_traction_lifecycle.py::test_mode_abs_tcs_variants_get_distinct_score_keys`失败；单项独立复现1 failed/0.34s。键的八种电子配置唯一性及标签检查通过，失败为漏改`game-controls-v7/reference-v8`对当前`v8/v9`的两行版本字符串期望。当前全文回归继续采集，273源码/测试/工具文件仍冻结；不标通过、不取消其余结果。待运行终止后修正期望并复验。

下一传动任务已先记录[PHYS-DRIVE-01范围](../../tasks/PHYS-DRIVE-01.md)，生产接入仍待ROT收口。新增固定阻抗活动集360组与完整惯量/九种状态定向72组的原始数据/适用范围见[设计准备](next-drive-design.md#接口求解成本准备)；不作为生产验收。


## T1-r1终态与完整T1-r2

[原始r1与回执](validation-T1-r1/receipt.json)：完整730项pytest自然结束729 passed/1 failed（3247.26s，runner计时3248.271s），唯一失败为上述版本断言；后三种子启动/两种子弯坡均not_run，当前不计通过。273基线/末次哈希全部一致，完整日志及collection映射已保存。

修正`tests/test_traction_lifecycle.py`的两行版本期望为game-controls-v8/reference-v9，[相关单节点T0](validation-T0-score-version/summary.json)通过。生产物理源码未变；新[273文件基线](validation-source-r2-before.json)只在这个测试文件与r1不同。完整T1-r2（五个原完整area）开始UTC2026-10-03T06:41:23.492705+00:00，实际会话29394，逐项7200s，不拼接失败runner成通过。所有src/tests/tools Python继续冻结；本地尚未提交或推送，整体goal/T3/可见性能/人工驾驶保持待验。

## 最终完整T1-r2

[回执](validation-T1-r2/receipt.json)及[原始runner结果](validation-T1-r2/raw-runner/summary.json)保存完整单次运行。会话29394正常退出0，七项检查全部通过：ruff、730项pytest、三种子1200步headless、双种子30s弯坡。pytest日志2937.19s、runner2938.150s；弯坡0/23分别279.793/279.782s。273/273文件哈希相同，无缺失/新增/修改；此前失败runner仍按失败记录。

[最终源码ZIP](final-validation-source.zip)与[manifest](final-validation-source-manifest.json)保留该验证版本，SHA-256为`e5c348ea856e14fbbfe81f81866c333cfa9a488817f3dc64a4c87b793238eac5`。T1完成后解除源码冻结，后续生产变化归入PHYS-DRIVE-01；本回执不覆盖后续版本。

下一传动预研进一步完成432组离合/齿轮/制动活动集、48组四轮非线性共同末状态、112组完整世界惯量旋转/摩擦/效率验证，原0.001N力残差及能量门槛保持，最多7轮收敛；首次输入JSON几何类型失败保留。详见[设计与适用范围](next-drive-design.md)。这些仍是冻结几何台架，没有代替连续原生驾驶、刚性轮胎、空挡和生命周期接入。

本任务只完成自动部分。下一块[PHYS-DRIVE-01](../../tasks/PHYS-DRIVE-01.md)接入真实曲轴、有限离合与开放差速器；传动功能组完成再T2，整体T3、可见性能和用户两模式驾驶另行验收。

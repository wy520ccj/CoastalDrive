# LAB-PARAM-01 参数说明与数学排版

施工树：C:/Users/15120/.codex/worktrees/simulation-fidelity/CoastalDrive，codex/simulation-fidelity，基线7e8be5f。任务成果尚未整合main/公开包。F1说明只读取工程配置与已有记录，未创建物理副本。

`T1/summary.json`保存29项/Ruff/0、17、23三种子各1200拍结果与完整命令。`ui-720`、`ui-1080`保存每尺寸8张实际渲染及result.json。测试使用真实VirtualMouse→MouseWatcher→ButtonThrower输入；检查悬停F1、输入框焦点F1、不合法输入不提交、Esc关闭恢复原层、手动参数名称F1、128项浏览、纹理未自动缩小与布局边界。只为配置上下文校验显式启动0.1秒试验，当前4100N和待运行5000N分别显示，帮助自身没有发起试验。

所有关键公式采用离线TeX数学行，渲染器为Matplotlib MathText 3.11.2/STIX，不调用外部TeX或浏览器；不是完整LaTeX文档编译器。公式源`src/parameter_formulas.py`，生成工具`tools/design/render_parameter_formulas.py`，运行资产/原始TeX/尺寸/SHA在`assets/game/ui/formulas`。Matplotlib只列入开发可选design依赖；运行只读取PNG/JSON。参考[官方数学排版说明](https://matplotlib.org/stable/users/explain/text/mathtext.html)。

语义区分：稳态质心轴荷式与小滑移刚度式保留近似号；真实轮荷由权威耦合悬架求解。压力式的u是ABS调节后的请求，p是比例而非MPa；转向δ是中心前轮角。输入数据的来源/用途单独说明，不捏造计算式；旧记录显示其已保存配置，但帮助使用当前源码，未宣称回溯历史算法版本。

中间问题如实保留：早期纹理996×90被Panda缩为512×64且透明像素RGB为白色，显示偏薄/发灰；最终二次幂透明画布和恒定墨色透明像素修正，实际纹理尺寸检查通过。中文字体缺下标零/上标负号，最终符号释义改兼容文字和单位写法。首次Ruff导入排序失败后修正。T1后手动名称命中框透明修正及新增检查由最终GUI/T0覆盖；未重跑相同物理T1。普通离屏帧缓冲告警存在，最终无缺字告警。

这是自动功能与离屏渲染证据，人工观感/F1体验待确认；T2/T3未执行，整体真实性目标未完成。SIM-TIRE-01有效485项物理结果复用，物理方程和游戏AI改动未更改。

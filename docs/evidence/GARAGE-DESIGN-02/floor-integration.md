# 车辆与车库地面的低强度反射

2026-10-23，基线`227ea9fd`，单线本地施工，无推送；接续目标的实际渲染改善，上回合有代码/实图/提交，属于progress。总目标与任务包仍in_progress。

## 设计与实施

- 先查看上一块实际BRZ改装图，沿用已学FH5的车库构图，再用内置image_gen生成[17地面融合](../../design/garage-v2/17-floor-integration.png)；[原提示词](../../design/garage-v2/17-floor-integration-prompt.txt)保存。只取接地点、低强度反射和淡出方向；生成图额外平滑车身不作为运行模型变化，也不把生成车辆/反射图烘焙进背景。
- 实际反射复制当前展示车的节点、共享原Geom和贴图，围绕z=0镜像；峰值alpha .20，深度0—.85米平滑淡出。先仅写最近表面深度，再仅绘制等深度的透明颜色，避免内部网格/背面重复混合。反射面序反向剔除，世界法线/光源方向恢复到原车方向，环境采样的观察点镜像到地面下方。
- 使用Panda官方的[坐标空间定义](https://docs.panda3d.org/1.10/python/programming/shaders/coordinate-spaces)、[GLSL自动输入](https://docs.panda3d.org/1.10/cpp/programming/shaders/list-of-glsl-inputs)与[反向剔除](https://docs.panda3d.org/1.10/cpp/reference/panda3d.core.CullFaceAttrib)；扩展锁定simplepbr 0.13.1片段，接口不匹配明确报错。
- 同车型/硬件/颜色的反射组复用，换车/硬件/漆色清理旧组；进入工程预览移除，隐藏展示缓冲不渲染，关闭随原Scene清理。镜像排除UI零件高亮/轮胎强调色，不修改源节点。首页、车库、暂停和结果共用，无新显示窗口/物理世界。
- 原接地阴影、车模、材质、灯光数量/曝光、UI位置、驾驶相机、权威物理/120Hz、完整硬件/存档/评分保持。不是完整3D车库，也不是粗糙地面BRDF或全场景SSR；背景仍是既有生成空车库，场景与车辆的精细光照差距没有据此称全部解决。

## 自动与实际检查

本轮日志仍在`logs/validation/GARAGE-DESIGN-02-floor-*`；最终摘要、原始日志压缩字节、图与源SHA在`floor-integration/`归档。T0首批7过1失败，针对性补验1过；最终完整相关T1 **53项**及0/17/23各1200步通过。最后只给采集工具补总CPU统计，再单独Ruff通过，生产源码在T1后未改。

- 几何检查7项：七款实际车，两个镜像pass的Geom与原资源共享，取样点关于原轮胎地面镜像；原节点变换/高亮保持，镜像剔除UI装饰。
- 车库夹具检查实际换漆清理旧组、同条件复用、进入工程预览清除反射；相关模块完整T1同时覆盖购买/恢复/保存、菜单/暂停/结果与缩放资源生命周期。
- `tools/garage_floor_check.py`七车实图、同场景反射开关像素对照、地面上方像素保持、BRZ/最高面数Elise各48帧开关显示诊断；所有截图/采样Snapshot保持，0新驾驶拍，18星是隔离显示夹具。CPU中位可能受Windows线程计时粒度影响为0，因此另记总CPU，不能宣称零CPU。
- 静态显示短窗的墙钟中位约11.4ms，受同步/窗口等待影响；没有GPU分项、长窗P99或正式驾驶性能Gate，不据此宣称没有GPU开销或整体提速。新增两次源几何绘制仅在可见车库展示发生，模型资源本身没有降模替代。

## 保留的失败/候选

- `floor-candidate`半透明单次绘制出现车内/背面重影，不采用；`floor-depth-candidate`修复遮挡后，再按镜像坐标修正直接光/环境观察方向，后续原生开关探针确认效果只在地面区域。`floor-probe`还对比Equal/LessEqual/不淡出，最终保留Equal和淡出，未以强亮度掩盖方向问题。
- 首次局部Ruff报未使用变量，移除赋值后通过。T0初7过1失败、第二次相同夹具失败：预览BRZ后切换涂装会按正常流程回到实际驾驶的参考车，测试误断言为同一身份。补齐明确选择驾驶后，针对性T0通过；没有改生产换车/取消预览语义。
- `floor-1280`采集工具把地面空盒角超出视口时的Lens.project返回False误当成无投影，落盘9张但无通过摘要；工具改为独立检查近裁面、使用其实际投影坐标。原失败保留，最终另用新目录采集。

人工审美、驾驶趣味性、道路精细度与完整场景融合仍未验收；没有以生成图、自动脚本或静态显示短窗代签。

## 最终命令与实图

均使用`.venv/Scripts/python.exe`，不覆盖旧目录：

```text
tools/validate.py T0 --tests tests/test_garage_reflection.py tests/test_career_ui.py::test_garage_paint_coat_stays_on_paint_and_clears_for_engineering_preview --output logs/validation/GARAGE-DESIGN-02-floor-T0
tools/validate.py T0 --tests tests/test_career_ui.py::test_garage_paint_coat_stays_on_paint_and_clears_for_engineering_preview --output logs/validation/GARAGE-DESIGN-02-floor-T0-selected
tools/validate.py T1 --tests tests/test_garage_reflection.py tests/test_career_ui.py tests/test_results_keyboard.py tests/test_driving_mode_ui.py tests/test_ui_assets.py tests/test_ui_theme.py tests/test_validation_runner.py --output logs/validation/GARAGE-DESIGN-02-floor-T1
tools/garage_floor_check.py --output logs/validation/GARAGE-DESIGN-02-floor-final-1280 --size 1280 720
tools/garage_floor_check.py --output logs/validation/GARAGE-DESIGN-02-floor-final-1024 --size 1024 768
tools/garage_design_check.py --output logs/validation/GARAGE-DESIGN-02-floor-flow-1024 --size 1024 768 --car coastal-hatch
tools/driving_summary_check.py --output logs/validation/GARAGE-DESIGN-02-floor-summary-1280 --size 1280 720
```

- 最终两种画幅七车各9张GUI图/2张原始buffer；4:3正常选车/购件/恢复/涂装/旋转/返回12张，普通暂停/结果/设置往返17张。共47张GUI实图和4张buffer，精选16张GUI及4张buffer原件归档，另保留首版失败重影候选。宽屏七车已逐张查看，4:3重点查看BRZ/Elise、i20升级/颜色/正面旋转，宽屏暂停/银牌结果也已查看。
- 两幅反射开关分别改变原始buffer的102136/129414像素，地面顶部399/390行以上保持；每车场景始终1个反射组、两个绘制pass。不是重复绘制的第二个物理车。
- 两幅BRZ/Elise静态48帧开关的中位墙钟11.42—11.58ms，P95 12.56—14.03ms。4:3总主线程CPU为每组46.875—93.75ms，单帧中位受粒度影响为0；未据此证明GPU开销/正式实时性能。宽屏批次在补CPU总统计前，摘要没有此新增字段，未伪称重跑。
- 正常车库流程240新道路显示拍；暂停/结算四次工况各60拍装载，另240装载拍、0新驾驶拍，5显示窗口/160GUI稳定；其余静态采集0新驾驶拍，Snapshot保持。旧完整赛事/物理结论明确复用，没有T2/T3或完整驾驶新跑。
- `manifest.json`固定最终六项源码、设计图/提示词和20张实图SHA，并核对15个物理/模型/材质/菜单源文件相对基线保持。`validate.py`的appearance范围补入网格取景与镜像检查，后续相关验证可直接覆盖。

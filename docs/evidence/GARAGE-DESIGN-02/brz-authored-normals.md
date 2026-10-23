# BRZ原作者车漆法线的正确适配

2026-10-23，基线`07384654`；接续上一块反射实际实现，前回合属于progress。本轮沿用既有01/17构图和曲面高光目标，没有新生成页面或声称重看新参考图；仅修复已有开放模型的转换，不新建车身几何。

## 原因与实施

- 原始`SX_body`为15081顶点、27313三角形、81939面角，带作者自定义法线。旧适配合并重合点后14995顶点/相同面数和面角，删除作者法线后用40°折边重算。原作者曲面信息因此丢失，并非UI叠层或光照数值本身造成。
- 本轮对原始法线先旋转，再以现有分段轮拱/轴距适配的局部Jacobian逆转置转换。保留已有合并重合点与折边步骤，逐面角检查位置对应后写回作者法线；不改`fit_point`的顶点适配或驾驶参数。源面角与派生对应最大位置误差0.960微米，全部81939角通过2微米对应检查。
- 相对旧自动法线，角度差P50 .075°、P90 22.227°、P95 25.647°、P99 34.621°，最大85.528°。先在logs隔离生成/打包候选，用同进程、同灯光/曝光/粗糙度/车漆/相机拍55°和35°，确认引擎盖高光连续性改善后纳入转换工具。
- 正式更新可编辑BLEND/GLB/运行BAM及manifest、许可加工说明；仍103071三角形。BRZ缩略图从新源渲染，原接地阴影因遮挡几何保持而复用；旧六张赛事预览作为原拍摄版本保留，本轮不伪称重拍。
- 旧源文件及运行资源完整备份在`logs/validation/GARAGE-DESIGN-02-paint-normals/baseline/`；原作者`art/vehicles/sources/subaru-brz/`只读，CC-BY-4.0及轮源署名保持。工具使用本机Steam Blender 5.2.3 LTS，实际版本高于旧环境文档5.2.2，已在检查JSON记账。

## 几何/材质边界

`compare_geometry.py`分别加载基线和最终GLB，逐材质把三角形三角点的实际位置/UV按七位小数编码，循环换起点保持绕序，再比较全部三角形记录；另比较解码贴图像素及材质数值。五个材质、103071三角形全部相同，报告`geometry-comparison.json`。几何结论有意排除法线；法线另以六位小数比较，只有Body Paint变化，玻璃/外饰灯组/内饰/车轮四材质法线保持。不是只比顶点数或包围盒。

没有降低金属度/增大粗糙度、改曝光或移动灯光掩盖问题；没有改变车身轮廓、轮胎/轮距/轴距、材质分区/UV/像素、原车辆硬件、权威物理或120Hz。新法线仍受源网格本身的曲面质量限制，不据此宣称其他车型、场景光照或人工审美全部通过。

## 验证与命令

均在项目目录执行；每个validate输出使用新目录：

```text
B:/steam/steamapps/common/Blender/blender.exe --background --factory-startup --disable-autoexec --python-exit-code 1 --python tools/blender/prepare_brz.py
.venv/Scripts/python.exe tools/vehicles/prepare_brz.py
B:/steam/steamapps/common/Blender/blender.exe --background --factory-startup --disable-autoexec --python-exit-code 1 --python tools/blender/render_garage_catalog.py -- --thumbnails-only game-tuned
.venv/Scripts/python.exe logs/validation/GARAGE-DESIGN-02-paint-normals/compare_geometry.py
.venv/Scripts/python.exe tools/validate.py T0 --tests tests/test_vehicle_visual_asset.py tests/test_career_garage.py --output logs/validation/GARAGE-DESIGN-02-authored-normals-T0
.venv/Scripts/python.exe tools/validate.py T1 --tests tests/test_vehicle_visual_asset.py tests/test_career_garage.py tests/test_career_ui.py tests/test_vehicle_visual_parameters.py tests/test_ui_theme.py tests/test_garage_framing.py tests/test_garage_reflection.py --output logs/validation/GARAGE-DESIGN-02-authored-normals-T1
```

T0 **25项通过**；最终相关完整T1 **62项及0/17/23各1200步通过**。生产工具/源模型/运行资源在T1后保持，后续仅署名加工说明与证据/进度更新。没有T2/T3、完整赛事、正式性能或人工验收结论；旧完整驾驶/参数结论明确复用。

正式资源命令及结果：

```text
.venv/Scripts/python.exe tools/garage_design_check.py --output logs/validation/GARAGE-DESIGN-02-authored-normals-flow --size 1280 720 --car game-tuned
.venv/Scripts/python.exe tools/garage_design_capture.py --output logs/validation/GARAGE-DESIGN-02-authored-normals-1024 --size 1024 768 --car game-tuned --only cars upgrade-tires paint
```

- 两命令passed；宽屏正常12图，包含选车、购买/恢复、漆色预览取消/保存、三个旋转角、返回原赛事及实际道路显示；4:3三页静态图。已查看正式宽屏改装/道路和4:3选车；同场景候选两个角度前后四图也已查看。精选最终4图与候选4图归档，明确区分，不把候选当最终程序图。
- 正常流程240新道路显示拍；4:3静态0新驾驶拍，完整赛事/驾驶参数结论明确复用。原界面焦点/返回/存档边界与Snapshot保持、显示资源无累积沿用正常采集检查，不以两秒道路显示证明完整赛事或性能。
- `brz-authored-normals/`归档原始T0/T1日志压缩字节、完整摘要、诊断/候选/几何检查脚本与原JSON、8张原图。`manifest.json`固定最终资源/工具SHA，并核对20项物理/显示/光照/原始来源/适配配置/遮蔽/阴影/启动器保持；文本按LF规范化、二进制原字节比较。
- 已核对`launchers/game-current.cmd`仍直接用本目录`.venv/Scripts/pythonw.exe`运行`src/main.py --driving-mode game`；本轮不生成安装包或更换启动器。

## 诊断中保留的失败

- 首次只读检查按`SX_body`精确找派生对象，但Blender已自动命名`SX_body.001`，出现KeyError；按确认后的派生名字规则读取并成功。首轮Blender默认退出0但有异常，不当通过；后续显式`--python-exit-code 1`。
- 最初临时脚本名`inspect.py`遮蔽Python标准库，候选打包与采集均未启动；更名后正常运行。没有改依赖或全局安装来绕过。
- 首次几何比较假设所有材质都有UV，玻璃材质没有该列，Panda reader报错；按实际顶点格式区分无UV材质后完成强比较，原失败不作为通过。
- 临时注入候选只作用于隔离进程，候选BAM/GLB保留在logs；正式工具生成的运行资源另行采集，不把候选图冒充最终图。所有候选静态采集0新驾驶拍。
- 首归档按原字节比较Git中的LF与工作树CRLF适配JSON导致误报，规范化文本后证明保持；恢复部分归档目录时又被已存在子目录拒绝，保留原文件后完成归档，未把中断当通过，也未改配置内容。

总包仍in_progress：其他源网格/材质、精细车库光照与地面、道路细节及用户实际审美/驾驶趣味性仍待继续。

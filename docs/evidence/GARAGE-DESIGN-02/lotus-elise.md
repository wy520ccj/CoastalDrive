# Lotus Elise 替换旧R2外观

基线`a0d769e8`，单线本地。用户优先开放许可、现实车型；这次把`coastal-roadster`原简易敞篷外观换为有明确作者和许可的Lotus Elise，保留旧车型/存档键、3星解锁及全部原硬件。不把本块完成写成整个画面目标完成。

## 来源与实际资源

- 作者[Stéphane Agullo / sa3d](https://sketchfab.com/sa3d)，[LOTUS ÉLISE原作](https://sketchfab.com/3d-models/lotus-elise-75e9045ac1af4cdbb69318108c81edfd)，2016-05-25发布。当前作者API明确CC-BY-4.0，原GLB的`asset.extras`内同样有作者、源UID和许可，不靠游戏代码许可证推断素材许可。
- 原始24,492,596字节GLB从[Ai2 Objaverse公开档案](https://huggingface.co/datasets/allenai/objaverse)取得；对象UID映射、下载URL、SHA与API原记录保存在`art/vehicles/sources/lotus-elise/`。原件完整保留。Objaverse整体数据库ODC-By，单件继续CC-BY-4.0，数据集作者署名随源README和运行许可保留。
- 初步整场预览会拍到巨大的演示台；实际检查网格后，提取完整车身/内饰/灯组/后视镜/四个建模车轮，去掉演示场景、人物、动画、可拆软顶和天线；厂标几何移除，车牌/轮心不使用原标识纹理。保留396170个源网格三角形，没有以新建立方体车身或圆柱车轮代替。
- 依据原R2的2.34m轴距、1.548m轮距、.31m轮半径和外廓适配源曲面；变形后重算法线，PBR车漆/玻璃/灯组/内饰分别保留。车身与四轮是独立显示根，车库/道路共用`lotus_elise.bam`，驾驶轮姿继续读Snapshot，表现不反写物理。
- 原件GLB、可编辑衍生`art/vehicles/lotus_elise.blend`、GLB、源/运行清单、离线提取/打包工具齐全。运行署名`Lotus-Elise-License.txt`；模型开放许可未冒充车厂授权。界面显示Lotus Elise并标“项目调校”，约96kW/1040kg为原项目配置，不称Lotus原厂参数。

## 与现有车库整合

- 继续冻结的车库页面构图；本次没有重排控件或重新生成另一种UI。新车选择、改装、涂装、取消预览、逐车保存/恢复、返回原赛事，仍使用实际WorkspaceVehicle和已有动作。
- 目录图与接地阴影由真实网格在项目CC0车库HDRI中渲染。初版近端车头/轮胎裁切；第一次单纯拉远仍有最后一行alpha，因此改为按真实网格的相机投影范围做正交取景，88%范围统一留边。
- 同时修正原七辆目录缩略图的同类裁切，保留同一角度、材质与源资产；只重渲染目录图，不重制其他车的网格/阴影。七张图片均实际查看，逐图alpha四边检查不接触边缘。最后Elise两画幅目录页重新采集，其余纯车型展示和功能结果复用。

## 验证

- 原十套完整设计配置逐字段比较`a0d769e8`全部相同：`elise-baseline-summary.json`。已有R2三赛记录也与当前游戏模式的完整配置一致，仅直接输入模式与该旧游戏记录相差既有`tire_substeps`；不是用工程模式混充复用证据。
- 本轮相关T0初因Ruff建议字典访问简化失败，pytest未跑；修正后完整车库9项T0通过。完整相关T1为`test_career_garage / test_career_ui / test_career / test_appearance / test_vehicle_visual_parameters / test_ui_theme`，**44项通过**，0/17/23各1200步通过。最后只改离线缩略图取景并补七图边缘检查，完整车库**16项T0通过**，不重复完整T1或驾驶。最后补入Elise车模/署名/阴影的真实打包包含模式，完整主题模块另5项T0通过。
- 新正常车库流程`tools/garage_design_check.py --car coastal-roadster --output logs/validation/GARAGE-DESIGN-02-elise-flow --size 1280 720`：12实际图，锁定/选车、买前胎/完整恢复、颜色预览取消保存、键盘返回、旋转与展示资源不累积通过；另**240新道路显示拍**，实图后方排气/灯组/四轮与涂装正常。不是新完整赛事。
- 旧完整驾驶明确复用`docs/evidence/GARAGE-FESTIVAL-01/driving/coastal-roadster/summary.json`：起步2045拍/17.042秒/三星，停车2272拍/18.933秒/二星，绕桩4210拍/35.083秒/三星；共8527旧拍，本轮未重复计入。原评分、物理、输入和新动力/悬架实现保持。
- `elise-flow/`12图为正常操作版本，目录里仍是初版裁切缩略图，不作为最终目录展示；`elise-1024/`为4:3五页静态（18星是隔离夹具），0新道路拍。`elise-final-1280 / elise-final-1024`是最后七图统一留边后的目录实图，分别9星隔离夹具，0新拍；`elise-rear/`补实际尾部，原先Elise缩略图已修，其余旧目录图尚未统一，车模本体最终不变。
- 两画幅均核对真实操作区/车模互不覆盖；正面/侧面/尾部/内饰/轮位/真实改装参数显示已看。截图和自动驾驶不等于用户认可。源码/资产SHA在`elise-source-sha256.json`，完整命令日志前缀`logs/validation/GARAGE-DESIGN-02-elise-*`；早期取景候选与失败留在源日志目录。

本块自动部分完成，工作区仅本任务变更、只做本地提交。总包仍in_progress：GR86仍是旧简易网格，道路精细度及车库与概念图差距尚未消除；人工审美/驾驶趣味性待体验。未跑T2/T3、性能阶段或人工Gate。

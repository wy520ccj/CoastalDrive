# 车库反射方向与透明漆面层

基线`1070ccc8`，仅本地。依据已冻结车库设计继续改善实际材质，未改变控件构图、车辆网格、参数或挑战判定。

## 问题与实现

- 原经纬图转换错误理解PfmFile的图像行方向，且六面坐标和Panda原生方向采样不一致。旧立方体向上取到约(0.367, 0.357, 0.318)的地面，向下却取到约(9.062, 9.250, 10.938)的明亮屋顶。修复后分别约(9.021, 9.218, 10.919)与(0.349, 0.353, 0.331)。原生采样/SHA见`light-directions.json`；独立Blender图像像素对照在源日志`light-probe/hdr_coords.py`，Pfm第0行与Blender最上行相同。
- 使用方向编码经纬图，经真实TexturePeeker按24个世界向量选择六面，覆盖离轴与接缝附近；不以复制转换公式作判定。最大通道误差要求.015。经度环绕、纬度夹边并双线性采样，保持128面尺寸/64过滤样本，运行环境文件尺寸仍3140130字节。
- 参照[Khronos clearcoat规范](https://github.com/KhronosGroup/glTF/blob/main/extensions/2.0/Khronos/KHR_materials_clearcoat/README.md)的分层方法，给已有底漆叠加IOR1.5/粗糙度.10无色面层：沿用当前GGX、BRDF积分和环境反射，用视角Fresnel衰减底层并加直射/间接高光。是固定展示面层，没有声称完整导入所有glTF扩展参数或达到参考游戏画质。
- 仅在车库展示paint节点使用定制着色，车轮/玻璃/内饰不加面层，工程预览清除覆盖；结算/暂停共用车库展示实现。保留一个主灯、原曝光、.12/.65底漆和阴影；没有采用诊断中的纯HDRI或降曝光候选。道路着色与全部10套硬件配置源保持。
- 新增`assets/game/shaders/garage-clearcoat.glsl`；setup包含模式与实际打包配置匹配检查同步，文件缺失会正常报错，不作视觉降级替代。最后纯文案把橙色改名“日落橙”、制动说明缩为“制动力偏向前轮”，消除4:3孤字换行，所有保存ID/颜色值不变。

## 验证与复用边界

- 初T0仅Ruff导入排序失败；首次坐标候选没有计入Texture装载行翻转，方向测试失败，修正后`light-direction-T0-v3`1项通过。面层T0测试误用NodePath查询API，修正后`light-coat-T0-v2`2项通过，失败日志均保留。
- 完整相关T1为`test_garage_environment`、`test_career_ui`、`test_career_garage`、`test_appearance`，26项与0/17/23各1200步通过。随后打包包含模式与断言增加，完整`test_ui_theme` T0另5项通过；最后明确零向量构造，方向T0再1项通过。不冒充一次31项T1。摘要在本目录`light-*-summary.json`。
- 正常车库流程`light-flow`12图，选择/锁定、购买/恢复、预览取消/保存、键盘/返回、展示资源生命周期通过，另240新道路显示拍。不是完整赛事复跑；旧完整驾驶数据保持，纯材质变化不再重跑。
- `light-1280/`归档该流程，`light-1024/`归档同版本四页静态；另`light-gt/`2图、`light-bmw/`1图、`light-i20/`1图、`light-wrx/`1图已看。所有静态隔离9星夹具，0新道路拍。
- `light-comparison/`是同窗口、同车漆和相机的旧环境/正确环境/正确环境+面层三图；诊断0星，不拿来当生涯完赛。`light-final-copy-1024/`只补最后文案两页；`light-result-pause/`补结算与暂停两图，均0新道路拍/合成成绩。其他图片复用，不把旧文案截图标成末次文字证据。
- 实际采集日志无着色编译失败或shader warning，常见帧缓冲能力提示是既有环境提示，未计为新错误。Scoped Ruff、差异检查与资源SHA一致。代码/资产SHA见`light-source-sha256.json`；原始日志前缀`logs/validation/GARAGE-DESIGN-02-`。

仍待办：R2/GR86简易模型、实际道路精细度和车库与概念图的整体质量差距；人工画面/驾驶趣味性未验收。没有阶段性能或人工Gate通过结论，总任务in_progress。

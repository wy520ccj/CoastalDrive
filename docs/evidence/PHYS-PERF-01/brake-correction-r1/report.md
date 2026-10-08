# Brake correction r1 证据归档

旧/新对照覆盖804个完整推进，所有字段hex与世界引用一致。3,111次制动修正分别以原Python端口导数、矩阵和`brake_increment`独立核对，hex完全相同；36组台架覆盖FWD/RWD/AWD、正反挡、空挡与同步，完整推进另含真实落地和海岸九车。成对耗时仅为诊断数据，不作FPS结论。

`audit.py`以相邻目录`../joint-native-r1`为基线输入：使用`../joint-native-r1/original-tire_drivetrain.py`及`../joint-native-r1/_joint_native_old.cp314-win_amd64.pyd`。这些源文件和独立旧DLL已在[上一组归档](../joint-native-r1/)中。制动前的C/Python/PYD同样引用该归档的`production/`副本，避免重复PYD。当前C/Python/PYD已按本次audit结束SHA冻结复制到`production/`。

T1初轮保留699通过/1失败（旧`shared_solution`测试hook引发AttributeError），Ruff通过，三个seed未运行。r2只修测试hook以捕获实际`wheel_map/shared_load_solution`；原16样本与`2e-6`容差未变。r2仅重跑1个Jacobian节点并通过，Ruff通过，seed 0/17/23各1200拍成功；此前699项是证据复用，不是本轮重跑700项。

`setup.py build_ext --inplace`成功，PYD SHA见收据；该次原始build输出只在终端显示，没有落盘，本归档不补造日志。最新候选包记录见[package-r10](../package-r10/report.md)。所有`.log`以`.txt`归档并保留原字节，`.gitattributes`设置`* -text`。本归档不代表T2/T3、FPS或人工驾驶通过。

Git索引按仓库文本属性把CRLF规范为LF；原始受测/建包源码和PYD保持在production。source-index-chain.json逐件记录原字节与索引SHA，并确认唯一差异为行尾转换，最终机械C索引SHA为061523360dcc5469f44e655476f4df109cb8e7e732b15ca75aa725a804ca4084。

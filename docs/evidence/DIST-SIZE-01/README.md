# 发行体积优化证据

- `comparison.json`：十进制字节口径，安装文件366,201,959→262,715,788（−28.26%）；Setup198,305,740→141,626,321（−28.58%）；ZIP241,443,252→165,251,074（−31.56%）。ZIP371文件SHA与安装输入一致。
- `build-receipt.json`：独立源码上下文、五扩展重编、原素材SHA、四项发行裁剪、三首FLAC原始/压缩SHA及完整PCM/精确跳转验证。构建完成后所有输入再次核对保持，无事后补造快照。
- `T0.json`、`T1.json`：相关Ruff/音频回归及0/17/23种子各1200拍通过，最终针对T1为26项。
- `audio-wide-T1-failed.json`/`wide-T1-failure.txt`：扩大音频模块检查61项通过、1项护栏碰撞失败，后续headless未跑；`baseline-impact-failure.txt`/`baseline_impact_delivery.py`使用首版隔离源码/原生扩展复现同一失败（只改测试ROOT到旧上下文）。旧碰撞问题保留，不调整物理或阈值。
- `install.json`：从首版安装升级到精简版后371文件逐SHA相同、无旧WAV/字体/诊断残留；三种子、smoke、三次真实实验台往返、同版覆盖升级/卸载及用户数据保留通过。诊断exe仅测试期间临时注入，结束移除，不随玩家包发布。
- `workspace.json`、`smoke.json`、`startup.json`：冻结程序正常独立物理/音频、短试验/输入/A-B/游标恢复与原生窗口生命周期；音乐句柄非BAD且长度有效；常规主程序从系统TEMP启动进入8车道路。
- `menu-comparison.json`：首版与精简版1280×720主菜单RGBA逐字节相同；`lab.png`为本版实际恢复界面，已查看。全部保留的图片/字体/模型/效果音与首版SHA相同。
- `remote-publication.json`：公开开发试玩版标签/提交、3资产远端大小及SHA，全部公开HTTP200/Content-Length核对，校验文件实际下载验证。

原始完整音频、字体和旧发行包保留；Git历史未重写。上述不代表旧碰撞问题、长期性能、实车标定或人工听感/手感已关闭。

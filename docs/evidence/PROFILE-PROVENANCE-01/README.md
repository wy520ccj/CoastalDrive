# GR86来源补齐证据

基线main/15e083e；原参数/默认导入语义与634ffcd逐文件一致。`before.json`保存修改前完整参数、实际配置和输入哈希，`original-profile.json`保留原JSON。JSON只改metadata，未运行生成器重新计算标定值。

- 来源覆盖100→110字段，每项value与实际导入配置一致；新增10项见before.missing。
- 参数规范JSON SHA256：`eb7ae4bf3c35974f0233cebf06df103128e73e862c4306835609806397decc54`。
- 实际配置规范JSON SHA256：`7417aa912c63b616d85d002b9d8a9583228e4e3c13171ae05694a334808bdd7f`。
- 普通/Double的summary均独立从before核对完全相同；不是只比较字段数量。
- `normal-final`/`double-final`各5张实际F1截图，覆盖未启用通用质量、轮胎Mz数据缺失、None阻尼含义、原厂分类以及覆盖值解除来源归属。来源在原滚动面板内；无新增独立车辆状态。两库PNG哈希比较见render-comparison，不作为物理等价证据。
- 普通T1 22项/三种子，Double相关9项通过。原复现及后续旧模式断言失败均保留：现Game单轮胎子步、Simulation双子步；测试显式只归一该既有积分差异，仍检查其余完整硬件一致和实际底盘质量。
- 工具：`.venv/Scripts/python.exe tools/profile_provenance_check.py --before <before.json> --output <新目录>`；Double前置`tools/physics/run_sim_double.py`。只显示F1，不运行新物理试验。

原整批T2的667通过/GR86首败仍保留在GAME-GHOST-01；本包短测不能代替后续未执行的T2范围。人工阅读/驾驶体验待确认。

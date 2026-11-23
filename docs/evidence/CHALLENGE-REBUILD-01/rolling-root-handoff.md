# 滚动求根修复接手核查

2026-11-02核查上轮未收尾成果。基线HEAD仍为`15c321f547dbc0f8891200c8fb84bede91d07257`，已有大量未提交改动；本轮未重新编译或修改机械源码。

第二轮完整回归在`tests/test_core.py::test_render_rates_use_identical_simulation`失败，379过1失败，1445.08秒。原生滚动求解报20轮后残差`0.000150026 N`，原始失败和冻结输入保存在`logs/challenge-rebuild-20261101/core-rolling-*`及`tests/data/core-rolling-root/`。

已有追踪显示：外层纵向根仍未收敛时，内层因横向残差小于单独门槛，在第0轮反复沿用上轮近似横向根。纵向残差在约±0.00012 N之间震荡。已有修复在联合残差未通过且并非首次外层时，至少细化一次横向根，保留原`1e-4 N`联合精度、20轮上限及物理方程。

上轮正式模块冻结输入重放三次均成功，结果哈希均为`d8f1500d6592ff1240cb023fd163931db38b9cdfd3f3583b87f1731a77db6293`；另有原生/非原生各三次候选结果一致。原候选盒未捕获，证据只支持冻结输入加完整支持几何，不能声称与原世界逐值等价。

已有`T1-rolling-root-final`通过：82项相关pytest、Ruff及0/17/23三种子各1200步headless。2026-11-02核对五个实际扩展SHA256全部与`rolling-module-sha256.json`一致，明确复用该结果，不冒称本轮重跑。

随后`T2-challenge-rolling-fixed/summary.json`停在running，pytest日志为不完整进度，没有完成行；接手时无Python测试进程，因此记为中断，后续项目未执行，完整T2未过。新完整回归命令：

```powershell
$env:PYTEST_ADDOPTS='--basetemp=logs/challenge-rebuild-20261102/full-T2-temp'
.venv/Scripts/python.exe tools/validate.py T2 --timeout 7200 --output logs/challenge-rebuild-20261102/T2-takeover
```

新回归与生涯预算对比运行期间，生产源码和pytest集合保持，接手哈希记录于`logs/challenge-rebuild-20261102/takeover-baseline.json`。最终状态以新目录实际summary为准。

# Suspension prescribed closed partition

目标改动是 `src/mechanical_kernels.c` 的悬架 prescribed closed partition。零法向逆质量且四轮法向反力非负时，按已指定末行程直接计算；硬件反力仍用原 FMA。其它情况继续走完整64轮活动集，所有原门槛不变。

独立127旧DLL对照为16,081次调用，四tuple输出hex全部相同：zero mobility 10,744、direct four-contact 10,061、general partition 6,020。T0为172 passed/6.56s并通过Ruff；T1为601 passed/28.84s并通过Ruff，三个headless seed 8.841/8.730/8.636s通过。原始summary包装计时一并保留（T0 pytest 6.634s、T1 pytest 29.282s）。标准0车/8车48拍完整Snapshot与主线fa037c4 wall-port-precision基线逐字段相同；短测0.7078002/4.7717689s仅诊断，不是FPS或Gate。

参考链包括试验时的 `triangle-bound-snapshots.json` 和既有 `main-wall-port-precision-r1/snapshots.json.gz`。静态核对两组参考与新快照在两场景的Snapshot完全相同；main-fa原件保留其来源路径及SHA。旧127 DLL基线的原始C、重命名C、setup、构建日志、manifest与receipt/PYD SHA留存，未复制二进制产物。

源SHA按360项清单在HEAD `9a127e566c55d07756795bd27deb0826aabce6aa` 前后比较一致；本块目标C SHA-256为 `429661d06cb9796e191d711b6867f63edf3a98ef1ff82620a996e934d2f55159`。T0/T1原summary的HEAD仍为756d262，保留其原始启动元数据；当前HEAD与归档时点写入receipt。

# PHYS-DESIGN-01 T2-r11 continuation failure archive

本目录保存 r11 续跑的原始 summary、Ruff 日志、完整 pytest 日志（gzip mtime=0）、collection 输出及596节点复用清单。逐件原件/归档SHA与压缩payload SHA见 [`receipt.json`](receipt.json)。测试节点筛选顺序和源哈希比对见 [`node-sequence-audit.json`](node-sequence-audit.json) 与 [`source-audit.json`](source-audit.json)。

## 结果

Ruff通过；pytest remaining 有32项通过，随后第33个节点 `tests/test_h3_review.py::test_highway_traffic_stays_grounded_and_retires_beyond_finish` 失败。失败运行末行报告：`1 failed, 32 passed, 596 deselected in 2436.80s (0:40:36)`。summary中的计时为 2437.206 s，而 pytest 日志结尾为2436.80 s，两个原始来源存在约0.41 s的记录差异，均按来源保留。失败共同求解超过20轮，残差为2.08274 N、制动0 Nm、法向0.102191 N、几何共轭冲量12.2837 Ns/Nms。失败后其余1468个已选节点未执行；summary记录的后14项check均为not_run。

当前collection共2097个节点，596个复用节点逐ID都存在于collection；筛选后为1501个remaining。已验证有效节点数为596+32=628，不能据此宣称整组T2通过。停在第33个节点后，remaining序列中从第33位起有1469个节点尚未获得通过结果，其中第33位为失败项，后1468项未运行。

## 源码身份与边界

启动summary保存332个生产/测试/工具文件SHA；当前按同一332路径逐个复核，332个文件均可读，匹配332个，差异0个。当前HEAD为 `a7649d4`。工作区文档状态单独记录，不计入这332个源码哈希。未对失败作修复或因果结论。

`logs/physics/PHYS-DESIGN-01-highway/capture-native.py` 的活动诊断进程不属于此T2版本，且仍在写入；没有归档其日志或输入，也不将其结果作为续跑通过证据。主目录T2仍有后续工作。

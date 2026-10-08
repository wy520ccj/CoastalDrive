# Shared load r1 证据归档

生产入口已共用同一 C 数值函数，当前共同载荷迭代20轮、端口最多30轮及8次线搜索、原残差判据和120Hz步进保持。八维旧机制及旧公开入口保留；`force`、`normal_responses`、`gradients` 每次读取当前状态，局部排除轮自身切向力时仍保留全部法向载荷。没有动态物理状态缓存或回退框架。

独立旧 DLL 审计 exit 0：804 complete_steps、14,823 shared_load_calls、11,220 wheel_free_calls、36 bench_cases，完整字段 hex 与世界引用相同；C/Python/PYD 起止 SHA 相同。相关 T0 为77项通过（1.32秒），Ruff通过。生产 C/Python/PYD 的副本 SHA 与审计 `source_sha_end` 一致。

本目录原样保存指定审计、源文件、日志、单份独立旧 DLL、T0摘要和生产副本；`.gitattributes` 禁止Git转换换行。逐件路径、字节数与 SHA-256 见 [receipt.json](receipt.json)。日志扩展名 `.log` 归档为 `.txt`，内容字节不变。

本次仅归档，没有重跑 T1、种子、48拍、profile、T2或T3，也没有运行测试、模拟或构建。无 FPS 结论；最终包、前台性能和两模式人工验收待完成。

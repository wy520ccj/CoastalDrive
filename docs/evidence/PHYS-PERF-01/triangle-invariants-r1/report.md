# Triangle query invariant 归档

基线为 `500ad9b`，工作树源码与T1最终复核时点保持冻结。360项 `src/tests/tools` `.py/.c/.pyd/.json/.gz` 加根 `setup.py` 的哈希首尾一致。归档包含triangle-bound全部探针、源码、构建日志/产物、初始失败、profile、三轮验证，以及独立旧DLL基线来源/构建清单。原始日志转为同字节txt；主/首轮48拍快照、基线DLL及编译中间件使用mtime=0 gzip。

查询规则复用首轮精确plane fraction：旧二次face入口在fraction达到ceiling时也返回None；最终同query把原padding传给边角回调，独立单面入口仍自行计算。候选顺序、64次扫掠、96次GJK和原精度保持。独立的ab204a9旧Python与旧DLL对照了39,672次query/9,685次hit，输出hex一致；edge调用35323降为22361。第一轮未保留独立JSON，未重建；当前无后缀审计JSON与r2 JSON计数相同。

首轮T1未含padding复用，560 passed/26.87s；最终T1-r2为560 passed/27.01s、Ruff通过，三seed为8.558/8.534/8.610s。T0为27 passed/0.27s、Ruff通过。相应summary包裹耗时略有不同，均完整保留。两版2×48拍Snapshot与主线fa037c4 accurate-map基线相同；主目录压缩基准作为 `reference/main-wall-port-precision-r1/snapshots.json.gz` 原件保留并校验SHA。首轮0车/8车为0.69787/4.98381s，r2为0.70440/4.86585s，仅诊断数据，不是FPS。

初轮审计JSON被r2相同counts覆盖，因此档案只保留初轮log及当时snapshot里的源指纹；r1的JSON不在来源中，未补造。独立DLL的原/重命名源、setup、构建日志、SHA与产物见 `reference/contact-system-baseline/`。

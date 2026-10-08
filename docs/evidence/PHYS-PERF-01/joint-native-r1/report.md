# Joint native r1 证据归档

主目录基线为 `6d58e9a`。原生范数探针复用 CPython 3.14.2 `mathmodule.c` 中的实现；来源为 `https://raw.githubusercontent.com/python/cpython/v3.14.2/Modules/mathmodule.c`，SHA-256 `fb618164d4dd0ba5dc45062d3521f9c44e270ce513a40bbb8ba8aecf1e374179`。196个边界值与100,000组随机位输入共100,196项，hex结果全部相同。

最终 audit 对照 804 个完整步、11,024 次 loaded force、2,805 次 wheel residual、2,709 次 suspension residual、36个台架案例；全部完整字段hex值及世界对象引用相同。两侧配对耗时只作诊断，不代表FPS。548项T0属于前三块且早于原生norm探针，不能当作norm后的T0。初次 `None` callback 的TypeError完整保留。CLI首轮保留11通过/2失败（旧入口限制），r2仅有的两项检查通过。

受测C SHA为 `b0958c451bb1df6234d32d0f57aea19979f7b1beccc174628a23a3a75ffe0a3d`；r1冻结C只移除已导入norm函数体中的行尾空白，SHA `dfd665c69e0ea595312c123f64789001f4148186f05f054ebce1533563e3a484`。format chain 记录tokens与行数相同，受测PYD未重建且SHA保持 `316ef5afd22f0967ef36a52f9d807f6d0868a9e7ff2434fe749951b468de0fca`。r1生产C/Python/PYD原样副本均列入收据。格式链原始字段committed_sha256记录的是当时拟提交的格式整理版本；它没有对应独立提交。本批随后追加制动块，主线最终源码与完整T1见[brake-correction-r1](../brake-correction-r1/receipt.json)。

所有`.log`以`.txt`名称逐字节归档，目录含`.gitattributes`（`* -text`）。本次归档没有运行新的验证；原功能组未逐小块重复T1/T2、种子或48拍，profile只在合并后定位一次，未作FPS结论。

已有离屏profile定位证据也已归档：GR86、coastal、8辆交通车，8拍预热后16拍采样，120Hz，源码哈希树前后相同。它只用于热点定位，不代表FPS或前台性能Gate。

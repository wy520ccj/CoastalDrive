# Toyota GR86 ZN8 社区外观

- 作者：Mona x Supercars / Car2022；上传者标注 CC BY 4.0，主作者 API 快照见 sketchfab-primary-api.json。
- 本项目实际取得的是 WebSim 公开衍生数据，固定提交/URL/SHA 见 download-record.json；未取得原始 GLB，不把上游下载声明当成本项目操作。
- gr86-runtime.js 原字节保存，只解析 gzip/base64 数值数据，不执行；源记录与署名逐字保留。上游包含第三方组件复用，额外 Kazutoshi Mods 署名与源文件说明保持，不声称上传者独立创作全部组件或厂家授权。
- 非精确 Premium 原厂轮毂：二代 ZN8 社区外观配 ADVAN 改装轮；既有 2022 Premium 6MT 物理账本保持。
- tools/blender/prepare_gr86_community.py 重建可编辑曲面/纹理，移除 2738 个索引完全重合的面后保留 163931 三角形。原数据、源法线、UV 和14张贴图不作重绘；tools/vehicles/prepare_gr86_community.py 输出道路/车库共用 BAM。
- gr86_community.blend 为贴图打包的可编辑衍生场景；脚本生成纹理文件来自公开 payload 原字节，非替代素材。

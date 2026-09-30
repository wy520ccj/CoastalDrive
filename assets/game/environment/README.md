# 海岸运行资产

仅由 `src/environment/` 消费；`scene.py` 装配到现有滨海赛道。新增 GLB 全部是装饰，不含碰撞体。

| 目录 | 内容 | 制作源 |
|---|---|---|
| models | 12 个 GLB：松树、灌木、花、岩石、崖岛、小屋、灯塔、路牌、路灯 | `art/coastal/coastal_kit.blend`，`tools/blender/build_coastal_kit.py` |
| materials | 原3张表面纹理、512px地表细节、768px岸线距离及坐标JSON | `tools/environment/` 对应离线制作工具 |
| terrain | 草坡、岩岸、灯塔礁与1800片双面草叶，共24790三角形 | `art/coastal/coastal_terrain.blend` |
| sky | 参考用户海岸图生成的天空全景，1774×887 | `source-manifest.json`；仅天空，不包含道路或前景 |
| shaders | 天空颜色转换与低成本动态海面 | 项目 GLSL 源码 |

模型来源、尺寸、三角形数量见 `kit-manifest.json`。本包模型为项目原创 Blender 几何，没有下载或打包新的第三方模型。既有 Kenney 源 GLB不改；0–360m的树冠在滨海实例上替换，树干网格和变换保留；树石碰撞形状不变。原第三方许可继续保留。

模型用米制、落地原点，GLB 经 Panda3D 实际加载测量。Blender 源文件不进入游戏包。生产工具不进入运行依赖。修改某个资产后重导对应文件，并运行 `tools/validate.py T0 --area environment`；提交前更新来源哈希和实机截图。

天空 shader 对已固定 simplepbr 0.13.1 的 filmic 曲线做逆转换，避免定稿天空被二次压灰；升级渲染依赖时需重新检查天空。海面以 Snapshot.time 驱动，暂停即冻结，不建立水体物理。

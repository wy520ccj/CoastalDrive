# 海岸实时画面与资产边界

UI v1 已获用户观感认可并暂时冻结。环境开发从保留侧碰修复的 `7588527` 开始，继续使用 `visual-identity-v1`，不回退 UI 或车辆配置。原 main、DS 和设计图均为只读参考。

## 按功能分区

| 位置 | 唯一职责 |
|---|---|
| `src/environment/foundation.py` | 海岸配色、光照参数、表面纹理和既有景物材质 |
| `src/environment/water.py` | 海面 shader 装配 |
| `src/environment/coastal_slice.py` | 0–360 m 景物布局、GLB 加载与既有树冠替换 |
| `src/environment/terrain.py` | 护栏外视觉地貌、接地采样与离线岸线交线 |
| `src/sky_dome.py` | 天空球；滨海贴图和 shader 单独选择，其他赛道保持原路径 |
| `src/scene.py` | 场景装配、Snapshot 驱动的表现更新 |
| `assets/game/environment/` | 按 models/terrain/materials/sky/shaders 分区的运行资源 |
| `art/coastal/` | 可编辑 `.blend` 美术源文件与制作说明 |
| `tools/blender/` | 离线模型制作与导出 |
| `tools/environment/` | 纹理生产、固定相机和真实驾驶留证 |
| `tests/test_environment.py` | 导出尺寸、原点、净空、材质隔离与打包路径检查 |

环境模块只读地图点和岛面三角形。道路、岛面和碰撞的权威定义仍在既有地图/Simulation，不能为装饰反向修改地图。视觉地貌可以在护栏外隆起，必须保留道路接缝及既有碰撞树石的地面接触。新装饰按最终导出网格采样落地；该采样不供车辆或 Simulation 使用。新景物全部在护栏外，不能生成第二套可驾驶地形。若以后需要新增可碰撞地标，另开明确任务，不能在美术任务中顺手加规则。

不扩大 `application.py`，不迁移 UI/Session/Vehicle/Traffic，不按目录整齐程度重排源码。没有通用资产管理器、页面系统或新渲染框架。

## 视觉取舍与参考

用户 `graphic_design` 中的驾驶图是方向：蓝绿海、暖云、浅色石岸、植被和地标。先统一光色，在既有道路上做小段可驾驶场景，再评估是否扩展。主菜单插画不能替代实时截图。

- [Firewatch / Jane Ng 的 GDC 分享](https://www.gdcvault.com/play/1022296/The-Art-of)：参考小团队把二维色稿转成可探索三维环境的取舍；本轮采用有限色板、剪影分层和集中地标。
- [Polycount 作者的风格化植被讨论](https://polycount.com/discussion/209623/smooth-foliage-like-in-breath-of-the-wild-europa-by-helder-pinto-mini-tutorial)：参考树冠整体读形的重要性。本轮没有照搬其 shader 或材质代码。
- [Kenney Nature Kit](https://kenney.nl/assets/nature-kit)：已核对成熟 CC0 来源；本轮保留项目已有模型，新 12 件资产由本机 Blender 制作，没有声称采用未下载的资源。

## 本轮停止线

完成环境基底和一小段示范，等待用户实际驾驶确认。全图铺景、车辆模型和驾驶 FX 均未开始。现有低模树、山体细节、天空清晰度与设计稿仍有距离；不能因本轮回归通过宣布 Visual v1 完成。

整体性能门槛继续使用既有 1080p、8 车、预热 30 秒后采样 5 分钟：平均至少 60 FPS、P95 不超过 25 ms。ENV-01 的约28秒窗口路线仅为短程记录。ENV-02 增加独立长采样入口 `tools/environment/drive_slice.py --onscreen --benchmark --output <新目录>`，期间不截屏、不并行构建；结果见对应任务，不替代人工验收。

## ENV-02 制作规则

- 用四段明确的景观节奏组织0–360m：起点草坡、松林岩坡、开阔海湾、灯塔礁。随机只用于群内小变化；房屋和巨型独立岩岛不再摆放，源资产仍保留。
- 草土石由同一地貌网格的顶点色过渡，加离线细节贴图；根部和岩脚采用周边地面的最低支撑值埋入。道路顶点、碰撞地图、控制器和规则不动。
- 既有碰撞树只替换这一段的叶冠，保留树干网格及变换；既有岩石近岸斜率保留。范围外树冠保持原样，不全图替换。
- 海水泡沫使用最终岸坡/礁石与海平面的三角形交线烘焙距离；不能凭道具中心叠圆盘。距离贴图的世界范围写在同名JSON，修改时同步 shader 对应坐标常量并运行岸线检查。
- [Alex Hallenbeck: All About Rocks](https://alexhallenbeck.artstation.com/blog/KgGb/all-about-rocks) 提供岩石/地面混合与顶面材质的参考；这里使用自己的网格、顶点色与烘焙流程，没有移植文章中的工程实现或纹理。
- [Quaternius Nature Pack](https://quaternius.com/packs/ultimatestylizednature.html) 作为成熟资产轮廓参考审看，本轮未下载或纳入该包，不能记为已采用资产。

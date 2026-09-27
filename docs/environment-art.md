# 海岸实时画面与资产边界

UI v1 已获用户观感认可并暂时冻结。环境开发从保留侧碰修复的 `7588527` 开始，继续使用 `visual-identity-v1`，不回退 UI 或车辆配置。原 main、DS 和设计图均为只读参考。

## 按功能分区

| 位置 | 唯一职责 |
|---|---|
| `src/environment/foundation.py` | 海岸配色、光照参数、表面纹理和既有景物材质 |
| `src/environment/water.py` | 海面 shader 装配 |
| `src/environment/coastal_slice.py` | 0–360 m 示范段的装饰位置与 GLB 加载 |
| `src/sky_dome.py` | 天空球；滨海贴图和 shader 单独选择，其他赛道保持原路径 |
| `src/scene.py` | 场景装配、Snapshot 驱动的表现更新 |
| `assets/game/environment/` | 按 models/materials/sky/shaders 分区的运行资源 |
| `art/coastal/` | 可编辑 `.blend` 美术源文件与制作说明 |
| `tools/blender/` | 离线模型制作与导出 |
| `tools/environment/` | 纹理生产、固定相机和真实驾驶留证 |
| `tests/test_environment.py` | 导出尺寸、原点、净空、材质隔离与打包路径检查 |

环境模块只读地图点和岛面三角形。道路、岛面和碰撞的权威定义仍在既有地图/Simulation，不能为装饰反向修改地图。内陆高度查询仅用于把装饰放在已有表面上。新景物全部在护栏外，不能生成第二套可驾驶地形。若以后需要新增可碰撞地标，另开明确任务，不能在美术任务中顺手加规则。

不扩大 `application.py`，不迁移 UI/Session/Vehicle/Traffic，不按目录整齐程度重排源码。没有通用资产管理器、页面系统或新渲染框架。

## 视觉取舍与参考

用户 `graphic_design` 中的驾驶图是方向：蓝绿海、暖云、浅色石岸、植被和地标。先统一光色，在既有道路上做小段可驾驶场景，再评估是否扩展。主菜单插画不能替代实时截图。

- [Firewatch / Jane Ng 的 GDC 分享](https://www.gdcvault.com/play/1022295/The-Art-of)：参考小团队把二维色稿转成可探索三维环境的取舍；本轮采用有限色板、剪影分层和集中地标。
- [Polycount 作者的风格化植被讨论](https://polycount.com/discussion/209623/smooth-foliage-like-in-breath-of-the-wild-europa-by-helder-pinto-mini-tutorial)：参考树冠整体读形的重要性。本轮没有照搬其 shader 或材质代码。
- [Kenney Nature Kit](https://kenney.nl/assets/nature-kit)：已核对成熟 CC0 来源；本轮保留项目已有模型，新 12 件资产由本机 Blender 制作，没有声称采用未下载的资源。

## 本轮停止线

完成环境基底和一小段示范，等待用户实际驾驶确认。全图铺景、车辆模型和驾驶 FX 均未开始。现有低模树、山体细节、天空清晰度与设计稿仍有距离；不能因本轮回归通过宣布 Visual v1 完成。

整体性能门槛继续使用既有 1080p、8 车、预热 30 秒后采样 5 分钟：平均至少 60 FPS、P95 不超过 25 ms。本轮约 28 秒窗口路线只作短程记录，不能替代该门槛，也不能替代人工验收。

# HWY-01 工程模块源

本套采用尺寸化Python网格源，运行资产为Panda3D原生BAM。编辑 `tools/environment/build_expressway_kit.py` 中的米制尺寸后运行：

```powershell
../CoastalDrive/.venv/Scripts/python.exe tools/environment/build_expressway_kit.py
```

初版12件BAM模块：路灯、反光桩、门架、桥梁预告牌、4m隔音墙、防撞缓冲块、排水篦、公里牌、设备箱、跨线桥、阔叶树冠、灌木簇。前10件工程设施继续使用，后2件植被由本次Blender资产替代；保留初版文件与来源记录。标牌用Panda3D随附默认字体离线生成几何，BAM自带字形纹理，无外部字体路径。

## Blender植被与岩层

`expressway_landscape.blend`为可编辑场景，包含两种完整阔叶树、保留原碰撞树干用的独立树冠、灌木带和分层岩石。树木有分叉、立体叶簇与小叶面；网格、材质与纹理均保存在源文件中。重建命令：

```powershell
& 'B:/steam/steamapps/common/Blender/blender.exe' --background --python tools/blender/build_expressway_landscape.py
```

输出5个GLB与`landscape-manifest.json`，无需运行期Blender。新增林缘/灌木采用明确里程带和成组尺度；原带碰撞树干网格、位置、变换保留。详见[材质与真实摄影参考](material-notes.md)。

`tools/environment/make_expressway_surfaces.py`只重建原创晴空和颗粒图，不覆盖imagegen生成的草/岩图；`bake_expressway_shore.py`在地貌修改后重建岸线。运行期只加载图像与模型。

`src/environment/expressway.py` 负责0–800m固定布局、地貌和轻量背景轮廓。地貌沿全局里程求值；树干仍是原Kenney模型与原变换，20–34m林带保留原地面高度。左侧为路堑与山脚，右侧为填方至海湾；城市和远山作为背景，几何范围自然超出可驾驶样板窗口，由第2号segment持有和回收。

Scene只对straight的0/1/2/3号segment调用新装配，沿用原根节点移动和回收。直线高速天空统一为本套配色；800m之后的道路、树与设施保持原样。弯路/坡路、有限highway与海岸不接入本套。

新模块不加碰撞；门架最低横跨部分5.8m，桥梁底部约6.325m。路灯杆位于护栏外，挑臂仅在高空进入路肩。现有护栏的0–0.8m碰撞实体保持同位置可见，不伪装成可穿越的独立W梁。

源文件没有通用生成器/注册器或实时几何重建循环。未来修改模块后应重建BAM，定向运行`tests/test_expressway.py`，再查看实景截图。

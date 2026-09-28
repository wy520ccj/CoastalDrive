# HWY-01 工程模块源

本套采用尺寸化Python网格源，运行资产为Panda3D原生BAM。编辑 `tools/environment/build_expressway_kit.py` 中的米制尺寸后运行：

```powershell
../CoastalDrive/.venv/Scripts/python.exe tools/environment/build_expressway_kit.py
```

12件模块：路灯、反光桩、门架、桥梁预告牌、4m隔音墙、防撞缓冲块、排水篦、公里牌、设备箱、跨线桥、阔叶树冠、灌木簇。前10件为工程设施，后2件为植被。几何、颗粒贴图与高速天空原创生成；标牌用Panda3D随附默认字体离线生成几何，BAM自带字形纹理，无外部字体路径。没有新增下载素材；本轮不宣称有Blender源文件。

`src/environment/expressway.py` 负责0–800m固定布局、地貌和轻量背景轮廓。地貌沿全局里程求值；树干仍是原Kenney模型与原变换，20–34m林带保留原地面高度。左侧为路堑与山脚，右侧为填方至海湾；城市和远山作为背景，几何范围自然超出可驾驶样板窗口，由第2号segment持有和回收。

Scene只对straight的0/1/2/3号segment调用新装配，沿用原根节点移动和回收。直线高速天空统一为本套配色；800m之后的道路、树与设施保持原样。弯路/坡路、有限highway与海岸不接入本套。

新模块不加碰撞；门架最低横跨部分5.8m，桥梁底部约6.325m。路灯杆位于护栏外，挑臂仅在高空进入路肩。现有护栏的0–0.8m碰撞实体保持同位置可见，不伪装成可穿越的独立W梁。

源文件没有通用生成器/注册器或实时几何重建循环。未来修改模块后应重建BAM，定向运行`tests/test_expressway.py`，再查看实景截图。

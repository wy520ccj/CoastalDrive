# 真实来源植物

Powered by Poly Haven。三组源模型、原始1K贴图和作者API元数据均为2026-10-23取得；许可CC0-1.0，见运行资源中的`License-Vegetation.txt`。

- Island Tree 01：Rob Tuytel扫描/处理，Rico Cilliers清理/处理；完整阔叶树作为林缘与原碰撞树位置的外观。
- Wild Rooibos Bush：James Ray Cock建模，Jenelle van Heerden摄影；选b/e变体6287/1193三角形。
- Grass Medium 01：Rob Tuytel摄影，Rico Cilliers建模；选small a LOD0与tiny c LOD0，833/40三角形。

`manifest.json`记录24份原始文件的固定URL、MD5、SHA256和字节数。独立alpha PNG亦从同一官方files API取得；主站glTF的RGB底色没有包含这些遮罩，制作时须显式接回，不能把整片卡当作不透明叶片。所有原始像素保持；原模型带的PBR法线/ARM保留在这里，当前运行植被仅使用底色/遮罩。

重建顺序（项目根目录，Blender 5.2.3 LTS）：

```powershell
.venv/Scripts/python.exe tools/environment/fetch_photographed_vegetation.py
& 'B:/steam/steamapps/common/Blender/blender.exe' --background --factory-startup --disable-autoexec --python-exit-code 1 --python tools/blender/prepare_photographed_vegetation.py
.venv/Scripts/python.exe tools/environment/pack_photographed_vegetation.py
```

Blender工具导入glTF数据而非执行外来脚本，保持源树的地面轴心。完整树减面至87967三角形并在近远档共享，整株落地；不使用旧细杆拼树冠或远景平面剪贴。灌木和草使用作者b/e、small a/tiny c的三维距离档。可编辑衍生在`art/expressway/photographed_vegetation.blend`，最终源GLB与采样/三角形报告同目录。Panda原生LOD沿既有道路分段回收，远处遮罩阈值从.4降到.12以保留细叶覆盖；静态设施合批不得递归展开植被网格。

未采用的Fir Tree / Shrub 02、早期裁冠、远景烘焙和过度减面实验只保留在本地忽略的验证日志，不进入运行包。设计图21的针叶目标已放弃，22改用本组实际阔叶源，23按用户否定与FH5晴天实图再统一光照/HUD；生成图中的草地密度、山体/海面细节仍未全面实现。

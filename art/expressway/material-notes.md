# 高速专用材质与参考

2026-09-28 HWY-01修订。海岸仅作为完成度参照；本套没有使用海岸天空、草地、岩石贴图，也没有修改海岸资产。

真实摄影参照为 NEXCO 西日本第23届公路摄影获奖作「霊峰を望む」，作者黒河廣志，爱媛县西条市。已查看[原页面](https://www.w-nexco.co.jp/drive_porter/photo_contest/contest23/)及[照片](https://www.w-nexco.co.jp/drive_porter/photo_contest/contest23/images/photo_a_3_09.jpg)。提取晴空、薄白云、由近到远变淡的山脊、植被/土坡/沿湾高架的层次关系；照片未下载、采样或打入游戏。

## 原创资产

- `grass-albedo.png`：内置OpenAI imagegen生成。brief为正交俯视、无方向投影的可平铺高速路侧草皮；橄榄/鼠尾草绿细叶，少量枯草、土与米色矿物颗粒，约2m地表尺度，禁止风景/文字/边框。运行时3m平铺并随地貌变色。
- `strata-albedo.png`：内置OpenAI imagegen生成。brief为正视可平铺的灰米色砂岩/页岩路堑；细水平岩层、碎裂薄片、少量赭色沉积、细颗粒，无植被/方向投影/风景/文字。地貌以5m纵向、3m高度尺度采样；Blender岩层资产嵌入同图。
- `expressway-sky.png`：独立离线程序制作的2048×1024晴空与稀疏白云，非海岸暖色云图。另一次imagegen天空请求因额度不足失败，没有CLI/API替代调用。
- `aggregate.png`：离线原创多尺度沥青颗粒；贴在唯一道路底面，移除上一版毫米级重复铺装面。
- `shore-profile.png`：视觉地面三角形与-3m海平面的交点曲线，每1m一个样本，用于海湾近岸色差与细波。

运行材质保留既有simplepbr 0.13.1光照、阴影和色调映射；高速地表只替换底色采样为草/土/岩连续混合。没有透明地表叠面。全局米制UV避免segment接缝与origin重定位时纹理游走。

`surface-manifest.json`记录贴图SHA-256；`landscape-manifest.json`记录原创网格、Blender版本、三角数与GLB哈希。两个图像资产已复制入仓库，运行时不依赖生成工具目录。

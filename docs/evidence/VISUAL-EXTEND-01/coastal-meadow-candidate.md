# 海岸短草实体样段：未采用

2026-10-28。沿设计38先补施工规格、实际查看[Poly Haven原作者完整成品](https://polyhaven.com/a/grass_bermuda_01)，再使用已登记Rico Cilliers/CC0原始glTF。没有另换一个容易达到的设计替代38。样段只在capture_coastal.py显式--meadow-candidate参数下装配，默认入口/其它地区保持。

## 制作与实际结果

tools/environment/prepare_coastal_meadow.py核对manifest全部源SHA，保留六种原叶位置/法线/UV/切线；按12米道路段离线合批，0–225米、内侧7–23米，6.5–13厘米高、18厘米株距、固定株位，树根留空。19批共110814株/2085330三角形，按原视觉地形精确落根，未移动原物件/碰撞/镜位。

使用原PBR/单太阳阴影，独立alpha同时供可见/深度遮罩。65–105米高度渐隐目前只接可见顶点shader，深度顶点尚未同步，**不能称阴影/LOD稳定通过**。BAM引用art下原纹理，未作可发布资产，未作风动验收。

最终1920×1080的0/90/225米图在logs/visual-extend-20261028/coastal-meadow-native-capture-r7；低机位诊断在coastal-meadow-native-inspect-r3，不是默认追车成品。草已可见，但追车下仍稀疏、发暗，远未达到38的连续地被，**不接入默认入口，不推广其它地图**。不能只靠再堆三角形解决设计差距。

固定场景45次renderFrame+syncFrame诊断，0/90/225米均值11.20/8.26/8.00ms，P95 13.68/10.15/11.51ms；无同时段原/新交叉对照，不归因提速/退化，也不是正常驾驶或长期性能验收。

## 失败与修正

- 烘焙r1漏切线，r2补齐，r3保留UV数值并统一默认texcoord/stage绑定，源文件保持。
- 采图r1/r2未挂源独立alpha而出黑片；r3裁可见片但深度投整卡片阴影。r4合并参数错误；r5/r6虽无黑片，实际草几乎不显示，不能当效果改善。
- 低机位inspect-r1确认草未显示；inspect-r2源遮罩/合并alpha一致性检查触发AssertionError，失败退出。
- 本源PNMImage.copyChannel实测产生全零alpha，统一16/8位范围仍失败，未将位深当已证实唯一原因。最终离线用getGray/setAlpha归一化逐像素合并，inspect-r3草叶可见，再采最终r7。这仅在诊断装配时运行，不增加驾驶帧工作。
- 最终采集/烘焙/物理基准/setup/相关测试Ruff通过。生产指纹保持的旧Scene水面回归/T1复用，本轮未重复完整视觉T1，无新增正常驾驶或人工体验。

## 实际落地与保持

另补wave-normals.txo.pz/ground-material.glsl漏打包，完整相关5项T1/Ruff/三种子通过，见[物理诊断与资源完整性](../PERF-SMOOTH-01/coastal-static-candidates.md)，不当安装器验收。180份顶层生产源码/原生文件与实验前保持；当前PERF72/视觉91，[保持记录](native-meadow-preserved.json)。全部B盘、无提交/推送、无保留预览。

整体画面/卡顿、其它模式/UI/试验台推广与人工门继续开放。后续短草先解决源叶密度/明暗和完整阴影距离一致性，不按这个未接受样段铺开。

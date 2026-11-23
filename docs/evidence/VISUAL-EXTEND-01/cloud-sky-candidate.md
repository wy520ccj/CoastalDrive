# 离线云层样板：未采用

2026-10-28。继续设计38，不降低目标。参考固定版本RenderPipeline云模块的噪声预计算/分阶段组织；原render_clouds.frag.glsl明确标注unfinished，未整包导入。

本机原创公里制薄云层/太阳遮蔽离线烘焙，运行时只替换原天空和同源过滤环境。r1云团太大；r2改为更细碎云群，2048×1024/120步只是构图样板。原生HDR读回通过，实际0/90/225米Scene运行采集exit0，新工具Ruff通过。

**实际成品仍不合格：**云形重复、边缘糊、太阳小且金色云底不足。增加输出分辨率不能修正密度场的大形和光照，因此没有继续放大8K，也没有写入默认运行目录。原8K摄影天空、动态海面修复、物理及已接受镜位保持。

源：`art/expressway/sky/coastal-sunset-bake.*`、`tools/environment/bake_coastal_sunset.py`；r1源码快照、r2HDR/来源/实际三图保存于B盘logs/visual-extend-20261028/sky-cloud-bake-r1、sky-cloud-bake-r2、sky-cloud-bake-r2-runtime、coastal-cloud-bake-r2。采集入口新增--sky-candidate只对本次工具生效，不改变默认入口。

参照源码：https://github.com/tobspr/RenderPipeline/tree/f858d071d54902e7d00eb0046dd5730eac9e4678/rpplugins/clouds 。本候选为项目原创程序生成资源，不能冒称摄影HDR或已实现设计38。

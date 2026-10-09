# Bullet 2.84 凸体查询依赖

来源：[Bullet 官方 2.84 标签](https://github.com/bulletphysics/bullet3/tree/2.84/src)。许可证见 `../../licenses/Bullet-LICENSE.txt`。保留原版权头；本目录53份上游C++源/头文件未改写，另有本说明。

`setup.py`只编译连续凸体扫掠、GJK/EPA及其数学依赖。游戏唯一的刚体世界仍由Panda3D/Bullet管理；这个扩展不创建世界，也不施力或积分。项目适配代码在 `src/convex_cast_kernels.cpp`，使用原64次扫掠上限及原单精度算法。

Windows使用 `/fp:strict`；查询与Panda3D真实世界独立对照见 `tests/test_convex_queries.py`。胎冠仍保留原17×64顶点，角度定位只缩小支持点候选，最终内积和并列顶点顺序保持原实现。

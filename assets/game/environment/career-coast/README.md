# 沿海生涯表现候选

本项目原始地形的离线派生数据，由 `tools/environment/prepare_career_coast.py` 制作。
不含KCD2、HD2或其它商业游戏的模型、贴图和数据。原物理地形保持。

`coast-club/final.npz` 包含分段表现网格、共享法线、岩土权重、2米草高场及64米远景；相邻JSON记录源和内容SHA256。水材质由本项目原高速水材质派生，独立保存，不替换通用高速版本。

状态：候选未采用。仅 `COASTALDRIVE_COAST_CANDIDATE=1` 开启；离屏工具使用 `--career-coast-candidate`。画面、驾驶性能、完整路线和人工验收均未通过。研究、设计及失败记录见 `docs/evidence/VISUAL-EXTEND-01/career-shore2.md`。

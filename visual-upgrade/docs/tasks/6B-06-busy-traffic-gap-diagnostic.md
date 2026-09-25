# 6B-06 繁忙车流空档诊断

- 状态：done（诊断证据完成；不包含交通修复）
- 基线 commit：`51ba3b2230b509fae8f02751d5a74bf0ef31f4b2`
- 开始状态：工作区干净，`main` 比 `origin/main` 超前 1 个提交
- 所属阶段：6B 画面规划

## 目标与范围

解释繁忙 18 车弯坡高速在驾驶中出现的可感知车流空档。只增加只读采样、固定种子重放、测试和证据文档。`src/` 没有修改；车辆数、生成范围、回收距离、安全间距、NPC 速度、HighwayDriver、道路、玩家、摄像机和物理均保持基线。

## 验收

- [x] 固定 seed 0 和 23，各完成 5 km 弯坡繁忙模式；无仿真失败。
- [x] 每秒记录 tick/time、玩家道路进度、18 辆车的 id/状态/generation/lane/道路相对纵横距/速度/phase，以及前后 150/300/600 m 计数。
- [x] 逐 tick 识别 generation 转换；同一 tick 的 retire + recycle 分别记录。retired 采样可直接显示等待放置；未伪造安全位置拒绝原因。
- [x] 标记最长稀疏区间，并保留可对齐 tick/time 的实际渲染录像。
- [x] T0 与 traffic + road T1；本包不运行 T2/T3。

## 命令与证据

- 诊断：`.\.venv\Scripts\python.exe tools/traffic_gap_diagnostic.py --seed 0 --distance 5000 --output logs/6B-06/seed-0`；seed 23 同命令改 seed 与输出。原始每秒采样、回收事件、汇总分别在各目录 `samples.jsonl`、`events.jsonl`、`summary.json`。
- 画面：`.\.venv\Scripts\python.exe tools/traffic_gap_video.py --seed 0 --start 138 --end 156 --output logs/6B-06/video-seed-0-longest`；seed 23 用 `--start 184 --end 192.9 --output logs/6B-06/video-seed-23-front-gap`。`frames.json` 精确对应实际画面帧与仿真 tick/time；帧序列编码为同目录 `replay.mp4`。
- T0 最终：`logs/validation/6B-06-T0-final/summary.json`。首次诊断命令因工具读取不存在的 `density.count` 在仿真开始前退出；改为实际字段 `density.cars` 后两个完整行程通过。
- T1 最终：`logs/validation/6B-06-T1-final/summary.json`。初次 T1 因录像工具 import 顺序检查失败，修正后 Ruff、traffic + road 测试、3 个 headless 启动和 seed 0/23 弯坡 30 秒检查通过。
- 详细数据、判读边界和结论：[`docs/6B-06-traffic-gap-evidence.md`](../6B-06-traffic-gap-evidence.md)。

## 交接

诊断归类 A：两次复现未出现交通生成/回收失败；体验上的空档可由车辆相对空间分布解释。seed 23 的前向画面确实出现无近车时段，物理数据同时显示前方 150 m 无车、前方最近车约 287–289 m，后方仍有 3 辆近车。更远车辆是否被弯坡遮挡只可作可能原因，不能从 headless 状态推断。当前证据不支持修改交通系统；若 Astra 要追究用户原录像的那次具体空档，需要其录像时间点/对应 seed，再进行逐帧对齐。

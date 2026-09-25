# CoastalDrive 工作规则

- 新会话先读 `docs/current-progress.md` 和当前 `docs/tasks/<ID>.md`，再看 `git status` / 相关差异；只按任务需要补读文件。
- 源码、接口和测试定义实际行为；进度页记录当前事实，`docs/development-plan.md` 定义路线，旧 review 只是对应版本的证据。
- 默认单条施工线：规划模型定范围，实施模型完成一个可独立验收的功能块；不默认创建并行 agent 或新任务。
- 阶段规划、核心接口变更、同一问题两轮实质修复仍失败、阶段复核时使用高能力模型；普通测试失败先复现和修复。
- Python + Panda3D/Bullet；使用 `.venv/Scripts/python.exe`，不安装到全局环境。
- `Simulation` 唯一推进物理；120 Hz 固定步，渲染/UI/声音只消费状态。保持 Control、快照和生命周期接口清晰。
- 代码简洁直白、按作用分块，可读性优先；注释和文档字符串用中文，只解释必要的意图与边界。
- 小模块、直接数据流；只在文件/设备/外部进程等真实边界处理错误，不写层层防御，不引入大型 ECS 或通用事件总线。
- 不靠瞬移、关闭碰撞或放宽阈值掩盖交通问题；先保留固定种子复现。
- 保留玩家认可的驾驶参数、倒车调姿规则、检查点相机行为；外观不得暗改物理性能。
- `legacy/`、相邻 `../ADAS` 和原 ZIP 只读；保留已有未提交工作，不覆盖或重置他人成果。
- 本地开发为默认；远端推送/发布按用户当次授权执行。
- 验证优先相关短检查，节省额度；同一版本已有有效结果不重复跑。修改行为跑相关 T0，任务完成跑 T1；小阶段才跑 T2，阶段 Gate 才安排 T3。具体入口见 `docs/tasks/README.md`。
- 失败、超时、中断、未跑必须如实记录；短测、离屏渲染、人工驾驶分别记账，不能互相替代。
- 手感、画面、声音的阶段验收须有用户实际体验结论，自动测试通过不等于阶段通过。
- 收尾更新任务包和精简进度页，记录基线/提交范围、命令、证据和下一步；不把聊天记录或施工流水账加入长期规则。
- 本地提交只包含本任务成果；未提交时明确记录工作区状态，不虚构 commit。完成任务包保留存档，下一任务无需阅读。

## 按需入口

| 涉及内容 | 从这里开始 |
|---|---|
| 交通/恢复 | `src/highway_driver.py`、`src/traffic_recovery.py`；设计依据 `docs/traffic-research.md`、`docs/traffic-recovery.md` |
| 车辆物理/操控 | `src/vehicle.py`、`src/vehicle_dynamics.py`、`src/vehicle_response.py`；`docs/vehicle-physics.md`、`docs/handling-v2.md` |
| 无限道路/重定位 | `src/highway_segments.py`、`src/highway_curve.py`、`src/streamed_road.py`；`docs/H4B-curves-design.md` |
| 玩法/界面 | `src/session.py`、`src/race.py`、`src/highway_run.py`、`src/application.py`；`docs/phase5c-gameplay.md` |
| 画面/车库/声音 | `src/scene.py`、`src/garage.py`、`src/settings.py`、`src/soundscape.py`；`docs/phase6a-garage.md`、`docs/phase6b-atmosphere.md` |
| 素材 | `docs/asset-register.csv`；新增资源记录真实来源、许可及加工过程 |

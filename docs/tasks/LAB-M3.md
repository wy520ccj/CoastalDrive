# LAB-M3 弯道制动 ABS–DYC 协调控制

课程工作区的 M1 五个固定工况和 M2 ISO 平面模型作为输入。本次在本地工作区接入 Lab，控制器仍由课程源码提供。试验台默认使用原生控制。

- 打开 `launchers/vehicle-lab.cmd`，在「高级参数」的 ESC 列表选择「协调控制（ABS–DYC）」。可先运行原生 ABS/ESC，固定为 A，再切换模式运行 B。载入评估脚本导出的 `lab_record_ab/experiment.json` 时自动读入同包的 `baseline-A`。
- 上层使用带制动附着约束的单轨参考和双线风险。参考侧向附着下限取综合附着的 12%。四轮分配仍采用实时物理附着上界。积分项受限，横摆请求超出可达区间时停止向饱和方向累积。
- 轮系制动力幅值为 `f ≥ 0`，转入 ISO 车身轴后是 `(-f cosδ, -f sinδ)`。因此左轮直行制动为正横摆力矩，力臂为 `y cosδ - x sinδ`。分配同时受实时摩擦圆、ABS 压力上限及执行器容量限制。QP 在无量纲力空间内用有效集处理边界。
- 遥测记录本拍生成的控制命令，并同时保留控制输入所用的前一拍索引。停车保护及无踏板区间的 `qp_iters` 为零。记录复算按保存的逐轮命令，以当时生效的原生电子开关重放。

课程工作区路径：`B:\AI agent\暑期计算机程序设计\汽车理论\作业\cornering_braking_control`，验收入口为 `scripts/run_m3_eval.py` 和 `tests/test_m3_controller.py`。

## 2026-11-23 宿主验收与试验台前端精修

状态：`done`（自动闭环与离屏渲染全部通过，桌面人工交互体验可随时用 `launchers/vehicle-lab.cmd` 复核）。

- **后端闭环验收**：
  - 课程单测 `pytest -q tests/test_m3_controller.py`：12 passed（34.71 s）。
  - 五工况闭环 `scripts/run_m3_eval.py --out-dir logs/lab-m3-host-eval --overwrite`：5 工况 × 4 组控制全部 `stopped` 闭环通过，S2 A/B 导出与原位读回一致（S2 停距 38.30 → 32.70 m、MFDD 3.39 → 4.11 m/s²、侧偏峰值 10.53° → 3.64°、压力 TV 12.70 → 4.63）。
- **试验台前端精修**（`src/ui/lab_workbench.py`、`src/lab_application.py`、`src/ui/lab_engineering.py`）：
  - 修复右侧结果卡 `timing` 两行文字压住「详细信号」按钮的问题，改为单行清爽留白；对齐页眉副标题基线、拉清左侧分组间距。
  - 在右侧结果卡、工程指标弹窗及 A/B 固定/载入提示中动态标明控制策略（如 `A · ABS+ESC` vs `B · ABS–DYC`），并在主栏按钮标出 `高级/DYC ›`。
  - 16:9（1280×720）与 4:3（1024×768）A/B 页面及工程指标弹窗离屏实拍已核对（`logs/lab-m3-host-eval/after-*.png`）。
- **回归验证**：`ruff check` 通过；`tests/test_lab_ui.py` + `tests/test_lab_driving_car.py` 43 passed（新增 `test_coordinated_abs_dyc_control_updates_main_indicator_and_ab_labels`），并补跑 0/17/23 三种子 headless 短启动。

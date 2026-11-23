# 山脊转向限制与缓弯候选

2026-11-05，HEAD `15c321f5`，本地未提交、未推送。保留已有全部生产改动。本轮仅改独立比较工具、相关测试及候选设计，生产车辆、道路、报价、奖牌、输入辅助均未修改。

## 先区分策略限制

复核已有 `ridge-demand-limit/paired-drive`：两方案的起伏段最高约126.8km/h，方向饱和88/156、89/156个观察点；770—830米横向偏差继续扩大至6米以上，随后失败。提高局部目标到140km/h与曲率目标7.5m/s²，不能证明车能保持这一路径。

`tools/challenge_balance_check.py`新增显式 `--steering-reserve .9`：按真实输入模式计算追踪转角，在转角需求超过90%时降低目标速度，保留原控制接口、120Hz、碰撞和裁判。默认不启用，策略记录为v6；交通控制不支持该选项并明确拒绝。另允许已有两种起伏路线规格经原候选加载入口载入，仍限单独山脊，文件全文哈希进入规则版本。

现有默认60度路线仅跑同一前胎/免费调校与加硬簧硬阻尼一对：73.050秒/20.908 L/100km、73.126秒/20.912 L/100km，均四门有效。起伏段最高约92.6/93.2km/h，出口偏差降至0.26/0.23米；说明该策略恢复了可完成轨迹，没有证明硬悬架计时收益。

## 设计后试跑30度候选

先重新查看GT7官方既有整图和图06，保存规格及准确几何，再原生生成[图07](../../design/challenge-courses-v2/07-ridge-suspension-30-design.png)。只将起伏段累计转向60°减至30°，周期、高差和其它路段不变。生产默认不读取该文件。

局部目标140km/h、曲率7.5、区外105km/h/3.8、转向余量.9；全部含前胎1.3、前制动份额.65、防倾前份额.4。同策略三例：

| 配置 | 费用 | 时间/s | L/100km | 起伏峰值km/h |
| --- | ---: | ---: | ---: | ---: |
| 原悬架 | 2000 | 70.557 | 23.332 | 130.10 |
| 弹簧1.25＋阻尼1.25 | 5000 | 71.089 | 23.584 | 129.90 |
| 弹簧0.75 | 3500 | 70.516 | 22.921 | 126.30 |

三例均通过四门，起伏段未观察到接地丢失或方向打满。硬簧组合降低垂向误差，但出口轨迹与计时更差；软簧比原悬架节油约1.76%，时间只差0.041秒，不宣称显著提速。软簧横向偏差稍大、垂向误差也更大；这是该策略下时间/能耗与稳定性的取舍，不是全面升级。完成这次定向软簧对照后停止追加试参。

该候选目前**不替换默认路线**：单次自动策略结果不足以证实普遍付费价值，尚缺原车、重复/驾驶策略稳健性及人工体验。现阶段无需继续硬簧参数搜索；下一步围绕软簧节油来源与实际关卡可玩性做决定。

## 证据与检查

- 输出统一在 `logs/challenge-takeover-20261105/`：`ridge-steering-reserve`两例，`ridge-30-candidate`两例，`ridge-30-soft`一例。各 `summary.json`、`path.json`、`dynamics.json`、120Hz原始驾驶记录保留。
- `review_reserve.py` / `review_drives.py`复算五次原始燃油和终点时间，各组 `review.json`通过；全部自动、非正式、不授奖，五例生产来源指纹一致且首末稳定，原六份玩家记录哈希保持。
- 新策略完整测试模块8项通过，覆盖方向饱和时减速、直线和起步保持、实际输入模式、非法余量。首次Ruff导入顺序失败，修正后相关Ruff通过。
- `capture_candidate.py`只在独立进程加载候选；`ridge-30-scene`四张实际静态图已查看，完整轮廓与图07一致，起终点投影在画内。既有地形条带/坡顶遮挡仍在。没有前台驾驶、驾驶FPS或真人结论。
- 未跑T1整包、完整T2/矩阵或重复物理smoke；任务仍in_progress，候选未达到生产采用或正式标定条件。

试跑命令共同参数：

```powershell
.venv/Scripts/python.exe tools/challenge_balance_check.py --output <新目录> --routes ridge_sprint --builds rough-free rough-firm-damped --seconds 120 --target-kph 105 --curve-acceleration 3.8 --rough-acceleration 7.5 --rough-target-kph 140 --steering-reserve 0.9
```

候选添加 `--ridge-profile docs/design/challenge-courses-v2/ridge-suspension-30-profile.json`；最后一次仅 `--builds rough-free-soft`。验证：`.venv/Scripts/python.exe -m pytest tests/test_challenge_balance_policy.py -q --tb=short`，相关Ruff为该测试与 `tools/challenge_balance_check.py`。

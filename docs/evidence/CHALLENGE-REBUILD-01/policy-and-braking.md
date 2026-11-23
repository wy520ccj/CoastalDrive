# 限速策略纠正与制动作用范围

2026-11-01。接山脊路线比较；本块只修改自动试车工具，车辆、道路、限速规则、奖牌门槛、报价和求解器均保持。整包in_progress，未提交推送。

## 山谷：先排除试车策略错误

旧`logs/challenge-rebuild-20261031/balance-hills-full`十例均在400米入口超速失败，原车56.92km/h；当时工具直到360米才把目标压至43km/h。不能把这批失败解释为改装不足。

`tools/challenge_balance_check.py`策略改为`road-budget-pursuit-v3`：直接读取SprintRoute的限速区间，在入口前按v²=v区间²+2a×剩余距离预先减速，入口预留10米；区间目标取35—50的中间42.5km/h。250米≥60km/h及400—650米全段35—50km/h原规则保持。未改真实车辆、位置或裁判。

命令：`.venv/Scripts/python.exe tools/challenge_balance_check.py --output logs/challenge-rebuild-20261101/valley-pilot-v3 --routes valley_pace --builds stock braking free-setup power-only efficiency balanced --target-kph 105 --curve-acceleration 3.8`。

六例全部真实完成，120Hz规则有效，源码首末稳定；20Hz限速段观察约41.82—43.31km/h，详细值在该目录`review.json`，只将它称为观察采样，不替代120Hz规则记录。

| 方案 | 经费 | 用时/s | L/100km |
| --- | ---: | ---: | ---: |
| 原车 | 0 | 56.246 | 19.023 |
| 制动1.25/前份额0.65 | 1840 | 56.305 | 19.035 |
| 免费调校 | 0 | 56.246 | 19.023 |
| 动力1.15 | 3940 | 55.259 | 19.614 |
| 减重/低阻 | 4780 | 56.008 | 18.493 |
| 均衡 | 5000 | 55.322 | 19.647 |

免费方案还含防倾份额0.4，不能把所有道路差异归因于制动分配。山谷仍是旧hills，尚未按新路线需求重做；这里仅解除了测量错误，未宣布底盘需求足够。

## 隔离制动容量与分配

使用现有LabExperiment、正常实验初始化、游戏原车硬件、游戏120Hz、80→0km/h、同附着和电子开关，动力分离/零转向/全制动。完整配置与各BuildDraft逐字段相同，四例真实停稳，源码和运行模块首末稳定。沿用原始120Hz观察校验，不改物理或工坊评分。

复算脚本`logs/challenge-rebuild-20261101/check-brake-capacity.py`；记录`brake-capacity-final`各子目录含experiment.json、vehicle.json、signals.csv和snapshots.bin。最初脚本用了不存在的StabilityConfig.enabled，启动即失败、无驾驶样本；修正为真实esc_enabled后完成，空旧目录保留。后续元数据核对首次误读metadata.json文件名，改读实际experiment.json后四例完整配置核对通过；这些错误不改变原始驾驶记录。

| 方案 | 经费 | 停车距离/m | 前轴ABS样本占比 | 后轴ABS样本占比 |
| --- | ---: | ---: | ---: | ---: |
| 原车 | 0 | 28.376 | 0% | 85.15% |
| 仅前份额0.65 | 0 | 28.123 | 0% | 0% |
| 仅制动1.25 | 1840 | 25.342 | 0% | 88.52% |
| 制动1.25/前份额0.65 | 1840 | 24.472 | 90.77% | 86.92% |

容量升级单独缩距约10.69%，配合分配相对原车缩距约13.76%。硬件作用存在，但这是明确的固定初速实验，不能直接用实验差值证明普通道路每次都能省时或作真人奖牌样本。

## 同一道路、更晚制动

工具新增`--braking-acceleration`及仅制动候选，原默认2.5保持，所有运行记录具体参数。实际命令：`.venv/Scripts/python.exe tools/challenge_balance_check.py --output logs/challenge-rebuild-20261101/ridge-later-braking --routes ridge_sprint --builds stock free-setup brakes-only braking --target-kph 105 --curve-acceleration 3.8 --braking-acceleration 6`。

同一山脊、同一更晚制动策略、同一源码，四例完成程序，其中三例有效：

| 方案 | 有效 | 用时/s | L/100km | 20Hz最大中心横向偏差/m |
| --- | --- | ---: | ---: | ---: |
| 原车 | 否，驶离 | — | — | 6.436 |
| 免费调校 | 是 | 69.849 | 22.226 | 4.528 |
| 仅制动1.25 | 是 | 70.054 | 22.196 | 5.108 |
| 制动1.25/前份额0.65 | 是 | 69.843 | 22.109 | 2.898 |

付费制动支持了此策略的完成，相比免费调校用时仅差0.006秒、油耗降低约0.52%；最大中心偏差下降约1.63米，体现这次策略的道路余量。不能把中心偏差直接当最小车身门线净距，也不能凭一套自动策略宣布最优解、重复真人手感或报价已合理。保持价格待定，后续继续设计实际制动需求并与免费方案比较。

本块全项目Ruff通过；没有修改生产行为，复用前块相关最终29项T1与三种子结果，不冒称重跑。完整T2、真人标定、正常驾驶性能和整包体验仍待完成。

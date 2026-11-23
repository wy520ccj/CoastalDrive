# 起伏段分段驾驶比较

2026-11-01。继续检查悬架的计时作用范围，仅扩展自动驾驶工具；车辆、路线、价格、燃油和裁判门槛保持。自动记录不作为真人金牌样本。

`tools/challenge_balance_check.py`增加显式分段策略，均记为`road-budget-pursuit-v4`并保存具体参数：`--rough-acceleration`只调整530—650米预瞄曲率目标；`--rough-target-kph`只调整470—650米加速目标，含进弯前60米。其它路段沿用target105、曲率4.4、制动2.5。仅允许明确的预算山脊起伏路线，默认调用仍保持原v3策略。

第一批`logs/challenge-rebuild-20261101/ridge-segmented-55`六例，将起伏段曲率目标从4.4升到5.5，全部完成。每例完整120Hz原始samples、fuel_steps及20Hz path/dynamics均与其此前基线相同，说明这项约束未实际限制当时输入；不能把参数变动本身当性能收益。

第二批`ridge-segmented-target120`将局部目标再升到120km/h，四例均有效完成，源码首末稳定，统计见`ridge-segmented-review.json`。实际峰值约114km/h，区外目标仍105。

| 方案 | 经费 | 用时/s | L/100km | 起伏段接地不足观察点 |
| --- | ---: | ---: | ---: | ---: |
| 前胎1.3/免费调校 | 2000 | 69.019 | 22.017 | 17 |
| 再加软弹簧0.75 | 3500 | 77.544 | 24.783 | 57 |
| 前胎1.3/阻尼1.25 | 3500 | 69.057 | 22.040 | 15 |
| 前胎1.3/弹簧0.875/阻尼1.125 | 3140 | 69.412 | 22.164 | 11 |

软弹簧在较温和策略中的贴地优势没有延续到这一速度选择，出现明显俯仰和倒向速度；更快输入不是无代价升级。其它付费组合也未在本批显示更快/更省油优势。原先的贴地/弯中轨迹改善仍是对应速度策略的有效观察，不能外推到任意速度或宣布报价合理。

命令示例：`.venv/Scripts/python.exe tools/challenge_balance_check.py --output logs/challenge-rebuild-20261101/ridge-segmented-target120 --routes ridge_sprint --builds rough-free rough-free-soft rough-damped rough-balanced --target-kph 105 --curve-acceleration 4.4 --rough-acceleration 5.5 --rough-target-kph 120`。

十例全部程序完成，无机械异常；结束后才施工山谷，未在运行中修改源码/工具。后续山谷T0首次Ruff发现本工具合并条件可精简，修正后全Ruff及相关T0/T1通过。保留当前悬架价值尚不足的结论，继续主要关卡需求和多方案平衡。

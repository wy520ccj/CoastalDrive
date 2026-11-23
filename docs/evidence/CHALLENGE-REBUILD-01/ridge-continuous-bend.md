# 山脊连续起伏弯落地

2026-11-02。按用户“不要总是做无用的测试”的纠正，停止继续铺开参数矩阵和完整T2，转入实际关卡修改。原运行的已完成/中断部分见`logs/challenge-rebuild-20261102/verification-stop.json`；未重启长回归。

## 实际改动

预算山脊默认改为`budget-ridge-suspension`/`budget-route-v4`。530—770米从单一120米起伏改为连续240米弯道：16/24/20米周期各4组，平顺高差仍0.06米，累计转向60度；后段后移120米，出口直线260→140米。总长1400米、预算5000、路宽13.5米、四门位置及原爬升/下坡高差保持。旧v2/v3路线和专家hills保留，规则版本隔离原草稿/记录。

仅修改生产`career_courses.py`与`challenge_catalog.py`；与接手哈希相比，其它生产文件及五个扩展全部保持。没有改变玩家车辆、附着、求解、报价或奖牌线。完整差异名单保存于`logs/challenge-rebuild-20261102/implemented-file-changes.json`，另外两项是相关测试文件；工具变化单独保留，未提交推送。

## 设计与实际画面

复用原GT7任务情境研究，重新查看保存的官方完整任务图及图04。先保存米制`ridge-suspension-profile.json`及准确几何参考，再原生生成[图06](../../design/challenge-courses-v2/06-ridge-suspension-design.png)。第一张沿用了旧路线轮廓，已保存为first并纠正；核对最终轮廓后才改生产数据。设计、规格、两轮提示词和生成结果全部留存，无新增运行模型/贴图。

`ridge-suspension-scene`一次加载采集435/590/790米实际静态视角及几何总览，四图均已查看。实际路线轮廓与图06一致，起终点投影均在画内；道路与护栏连贯。现有远景地形仍有分块/条带，未扩大为环境美术修订。6厘米高差在正常静态镜位不显著，不能用示意图的夸张纵轴冒称实景大幅起伏；道路显示与碰撞仍共用1米采样。

## 必要对照与结论

只跑原车、同一免费设定的前胎方案、在该方案上增加悬架三例，target105km/h、曲率目标3.8m/s²，其余输入策略相同，三例均完成、无碰撞、预算内、首末源码稳定，全部自动不授奖。

| 方案 | 经费 | 用时/s | L/100km | 起伏段垂向跟随误差RMS m/s |
| --- | ---: | ---: | ---: | ---: |
| 原车 | 0 | 72.295 | 20.316 | 0.07018 |
| 前胎1.3/免费调校 | 2000 | 71.974 | 20.230 | 0.07094 |
| 再加弹簧1.25/阻尼1.25 | 5000 | 71.995 | 20.251 | 0.05287 |

免费调校统一为前制动份额0.65、防倾前份额0.4。悬架组合使该起伏段垂向跟随误差约降25.5%、俯仰跨度1.897→1.793度，但用时略慢0.021秒且油耗略高；本次仍不支持按计时/能耗收益冻结悬架报价。原车可完成、新路线已落地，悬架计价价值与人工驾驶感受继续开放。不继续追加参数搜索。

命令及证据：

```powershell
.venv/Scripts/python.exe tools/validate.py T1 --tests tests/test_career_courses.py tests/test_challenge_catalog.py --output logs/challenge-rebuild-20261102/T1-ridge-suspension
.venv/Scripts/python.exe tools/challenge_balance_check.py --output logs/challenge-rebuild-20261102/ridge-suspension-drive --routes ridge_sprint --builds stock rough-free rough-firm-damped --seconds 150 --target-kph 105 --curve-acceleration 3.8
.venv/Scripts/python.exe tools/challenge_ui_check.py --output logs/challenge-rebuild-20261102/ridge-suspension-scene --course-scenes --course-route ridge_sprint --size 1672 941
```

相关34项、Ruff及三种子各1200步headless通过；新增断言覆盖三种周期、1米实际路面峰值、跨分段连续性和正常预算入口/旧专家入口隔离。没有另跑重复T0、扩大测试模块或再次启动T2。静态图、自动驾驶与真人手感分别记账，整个CHALLENGE-REBUILD-01仍in_progress。

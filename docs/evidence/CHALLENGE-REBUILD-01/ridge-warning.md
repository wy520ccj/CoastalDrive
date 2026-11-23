# 山脊下坡弯提前提示

2026-11-02。本轮用户继续后，任务恢复in_progress。没有重启完整T2或参数矩阵；已完成的进度、原始记录及未提交成果保留。

## 实际修改

预算山脊现有540米龙门牌由“海滨 临海”改为“前方下坡急弯 / 300米 · 提前减速”。下坡急弯始于830米，牌面标注为290米距离的近似。沿用原尺寸、字体、颜色、箭头、支撑和位置，只替换文字；其它路线和旧专家山脊仍用原牌。

生成源为`tools/environment/make_expressway_sign_faces.py::ridge_warning`，新增`assets/game/expressway/signs/ridge-gantry.png`；`expressway.load_kit`复制同一龙门架并替换牌面纹理，`expressway_route.segment_steps`仅在`budget-ridge-suspension`的540米使用。没有修改道路几何、车辆、碰撞、报价、奖牌规则或真人记录。

这是既有设计上的文字修订，沿用已有牌面制作源与设计；未新增视觉方案。一次实际场景采集435/590/790米静态追车及总览，四张均已查看。435米可见“前方下坡急弯”，远处副行较小；790米仍显示坡顶遮挡下坡的实际视域，因此提示承担提前告知用途。静态图不代表玩家一定读到、正常驾驶表现或人工体验通过。

## 相关验证

下列检查各执行一次并通过，无新增测试代码、长回归或驾驶矩阵：

```powershell
.venv/Scripts/python.exe -m ruff check src/environment/expressway.py src/environment/expressway_route.py tools/environment/make_expressway_sign_faces.py tools/challenge_balance_check.py
.venv/Scripts/python.exe -m pytest tests/test_expressway.py::test_kit_clearance_uses_serialized_geometry -q
.venv/Scripts/python.exe tools/challenge_ui_check.py --course-scenes --course-route ridge_sprint --output logs/challenge-rebuild-20261102/ridge-warning/scene --size 1672 941
```

相关模型检查1项通过；渲染工具4图通过，物理快照保持。渲染提示实际帧缓冲与请求不同，采集正常完成。未跑新的T1/T2或人工驾驶，旧完整T2未通过的状态保留。

源文件本轮前副本和成图保存在`logs/challenge-rebuild-20261102/ridge-warning/`。本地未提交、未推送。

## 悬架需求核对：未完成

此前正常策略对照已经证明垂向跟随误差改善约25.5%，没有计时/油耗收益。本轮仅追加两方案一次对照，检查此前85—99km/h起伏段是否掩盖更快驾驶需求。独立工具新增v4真实起伏区间530—770米支持，原默认策略保持；未改生产驾驶或规则。

```powershell
.venv/Scripts/python.exe tools/challenge_balance_check.py --output logs/challenge-rebuild-20261102/ridge-demand-limit/paired-drive --routes ridge_sprint --builds rough-free rough-firm-damped --seconds 150 --target-kph 105 --curve-acceleration 3.8 --rough-acceleration 7.5 --rough-target-kph 140
```

| 方案 | 费用 | 停止时刻/s | 最远进度/m | 完成 | 碰撞 |
| --- | ---: | ---: | ---: | --- | ---: |
| 前胎1.3/免费调校 | 2000 | 38.067 | 835.167 | 否，驶出道路 | 0 |
| 再加弹簧1.25/阻尼1.25 | 5000 | 37.692 | 828.057 | 否，驶出道路 | 0 |

两套均以约125km/h通过起伏段，无轮胎失去支撑，随后在下坡衔接处失败。起伏段垂向跟随误差RMS约0.1222→0.0929m/s，仍只是垂向改善。失败发生在自动控制提前减速不足的共同路径，不是完成成绩，也不能将较短失败时刻当作更快或把未完成油耗当作节油收益。悬架收费价值仍未证明，停止追加试参。对照数据、旧工具副本分别保存在`ridge-demand-limit/paired-drive/`和`ridge-demand-limit/tool-before.py`。

道路两套真人方案各两次记录、正式奖牌线、其它未完成平衡与用户体验结论继续开放；原6份初章记录不替代道路标定。下一步围绕实际玩家的路线判断与改装取舍收口，不重复已有效的检查。

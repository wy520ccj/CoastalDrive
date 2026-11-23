# 山谷节奏的制动窗口

2026-11-06，基线 HEAD 15c321f5。既有山谷数据表明原 250 米测速门与 400 米限速带之间有 150 米，玩家可以提前减速。预算版把首个测速门移到 **375 米**，门线速度至少 **80 km/h**，25 米后进入原 35–50 km/h 限速带。后续三个门位、1 公里路线、5000 预算、原车、路面、价格和联合奖牌线保持。

新版本为 `budget-valley-braking-v1`，裁判、HUD、场景标线、自动试车与分段取同一组门位。测速与限速门沿用[原山谷设计](../../design/challenge-courses-v2/design.md)的路面和标牌样式，按当前目标依次显示文字，避免近距叠字。赛前方案页也列出要求。旧专家和显式加载的旧预算规则仍是 250 米、至少 60 km/h。旧草稿可读；旧山谷成绩与含旧规则的巡回存档保留原分组，不与本版合算。

固定种子 17、本机道路 SDK，同一套自动策略和电子设置。三套均采用前制动份额 65% 与前防倾份额 40%，该免费调校作为比较基准。

| 实跑方案 | 费用 | 用时 / s | L/100 km | 375–400 米平均刹车请求 | 达到现有奖牌线 |
| --- | ---: | ---: | ---: | ---: | --- |
| 免费调校 | 0 | 59.249 | 20.743 | 85.5% | 银 |
| 同调校加制动扭矩 25% | 1840 | 59.828 | 20.199 | 71.9% | 金 |
| 同调校加轻量低阻 | 4780 | 59.001 | 20.228 | 81.9% | 金 |

三趟均无碰撞并通过全部门位、连续限速裁判。复算了 120 Hz 终点和原始机械子步燃油。踏板请求的平均值取 375–400 米的实际控制样本，两种制动硬件的峰值请求均达到 100%。付费制动降低这一段平均请求、全程稍慢。轻量低阻全程最快。两种付费方案的油耗仅差约 0.029 L/100 km，结果限于该策略各一次。两套付费方案已在菜单按实跑参数接入，自动试车不记玩家成绩。

T1 相关 25 项、全仓 Ruff、种子 0/17/23 离屏启动通过。覆盖旧版规则、预算版精确门位、测速与限速边界、实际标线及预算入口。首次离屏核对发现门牌叠字，调整后复用实跑，单独核对显示与 Ruff。方案页和测速前的 4:3 截图在 `logs/challenge-valley-braking-20261106/`。赛道截图采用同一实际场景的静态位置夹具。

```powershell
$sdk=(Resolve-Path 'build/road-edge-sdk/panda/built-road-edge').Path
$env:PYTHONPATH="$sdk;$env:PYTHONPATH"
.venv/Scripts/python.exe tools/challenge_balance_check.py --output logs/challenge-valley-braking-20261106/first --routes valley_pace --builds free-setup tuned-braking tuned-efficiency --seconds 90 --target-kph 100 --curve-acceleration 3.4 --braking-acceleration 2.8
.venv/Scripts/python.exe tools/validate.py T1 --tests tests/test_valley_pace.py tests/test_sprint_ui.py tests/test_challenge_catalog.py::test_budget_uses_new_physical_course_and_preserves_legacy_route tests/test_challenge_balance_policy.py --output logs/challenge-valley-braking-20261106/T1 --timeout 180
.venv/Scripts/python.exe logs/challenge-valley-braking-20261106/review.py
```

三份原始记录和 `verified.json` 保留。其它路线改装平衡、跨策略复现与整包 T2 仍开放。改动保留在本地。

# 海岸巡回的单站试行牌与整轮积分

2026-11-06，基线 `15c321f5`。平路连弯启用试行奖牌后，巡回原本把平路试行金牌计作3分，总览把它显示为普通金牌。单站本来就要求达到试行铜牌才可前进，赛前总览没有列出这一要求。以当前真实关卡目录运行原核心测试，4项通过，试跑整轮应为零分的断言失败。

现在平路站赛前显示“过站需试行铜牌”，未达时仍重试本站。站点结算及新巡回历史保留试行奖牌并带“试行”标记。三站均有正式门槛后才启用整轮积分、奖牌和综合最佳。有效试跑仍能保存进度与最近完整轮次，已有成绩文件按原格式读取。旧规则历史保留其原奖牌名称。

最终相关11项T0及全仓Ruff通过。覆盖混合规则、三站有门槛但含试行站的边界、三站正式计分、保存与恢复、完整正常界面转场。960×720实际巡回总览和三站完成截图均已查看，夹具使用自动试跑的用时与油耗渲染，独立于真人存档。本块未重新驾驶完整巡回，未提交推送。

```powershell
$sdk=(Resolve-Path 'build/road-edge-sdk/panda/built-road-edge').Path
$env:PYTHONPATH="$sdk;$env:PYTHONPATH"
.venv/Scripts/python.exe tools/validate.py T0 --tests tests/test_tour_budget.py tests/test_driving_tour_ui.py --output logs/challenge-takeover-20261106/T0-tour-trial-medals --timeout 180
.venv/Scripts/python.exe logs/challenge-takeover-20261106/tour-trial-medals-ui/capture.py
```

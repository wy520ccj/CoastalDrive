# 五公里分路况正式奖牌

基线 `15c321f5`。在无限高速选定直线或弯坡、稀疏/普通/繁忙车流后，方案页、驾驶和结算使用同一组联合门槛。正式五公里采用固定种子0，六组各存奖牌、最佳和分段对照。其它显式种子保持可试跑。路况仍共用原有五公里方案草稿，旧完赛记录保留在各自原分组。判定仍要求预算内、无碰撞、未复位且完整行驶五公里。

| 路况 | 铜 / 秒、L/100km | 银 / 秒、L/100km | 金 / 秒、L/100km |
| --- | --- | --- | --- |
| 直线 · 稀疏 | 214.2 / 15.3 | 184.5 / 13.2 | 164.7 / 11.7 |
| 直线 · 普通 | 253.3 / 14.1 | 218.2 / 12.1 | 194.8 / 10.8 |
| 直线 · 繁忙 | 285.4 / 13.3 | 245.9 / 11.5 | 219.5 / 10.2 |
| 弯坡 · 稀疏 | 235.9 / 14.5 | 203.2 / 12.5 | 181.4 / 11.1 |
| 弯坡 · 普通 | 271.7 / 12.4 | 234.1 / 10.7 | 209.0 / 9.5 |
| 弯坡 · 繁忙 | 297.2 / 12.1 | 256.1 / 10.5 | 228.6 / 9.3 |

本轮只补直线稀疏、直线繁忙、弯坡稀疏、弯坡普通各一次原车。用时/油耗分别为159.871/11.357、213.099/9.808、176.028/10.766、202.900/9.212。复用[已跑的直线普通原车与轻量低阻、弯坡繁忙原车](distance-conditions.md)。七份记录均固定种子0、无碰撞，复算已接受的机械子步油耗和首次终点过线时刻，并核对四个计量点、实际车流分组和SDK指纹。金牌取各组入选样本的用时和油耗较大值各加3%，银铜基于金牌放宽12%/30%，全部向上取0.1。直线普通两套，其余各一套；金牌线已经启用，跨方案重复收益仍待验收。

HUD按累计用时和已用油量显示仍能争取的最高档。超出铜牌后继续提示驶向终点，预算内有效完赛仍可保存对照。结算明确显示路况和同次成绩。960×720方案、短驾驶和金牌结算三图已查看，结算为实际实跑数值夹具。实跑文件、`derive_targets.py`、`verified-targets.json`、截图和验证日志在 `logs/challenge-distance-medals-20261106/`。自动驾驶记录与玩家成绩隔离。

最终T0 7项及全仓Ruff通过。首轮仅因三处导入格式失败，修正后执行选定测试。覆盖六组门槛、实际菜单换组/重试、正式成绩隔离、任意种子不套用正式线、倒车与碰撞/复位优先判定，以及HUD降档。独立物理进程另核对弯坡繁忙、18辆、固定种子0及正式门槛回包。旧六份玩家逐拍文件SHA256一致。未提交推送，未运行整包T2。

```powershell
$sdk=(Resolve-Path 'build/road-edge-sdk/panda/built-road-edge').Path
$env:PYTHONPATH="$sdk;$env:PYTHONPATH"
.venv/Scripts/python.exe logs/challenge-distance-medals-20261106/derive_targets.py
.venv/Scripts/python.exe logs/challenge-distance-medals-20261106/verify_process.py
.venv/Scripts/python.exe logs/challenge-distance-medals-20261106/capture.py
```

T0完整命令与输出见该目录的 `T0-final/summary.json`。补跑使用 `tools/challenge_balance_check.py --routes distance_challenge --builds stock --seconds 320`，指定各组 `--distance-shape`、`--distance-density`，直线 `--target-kph 144`、弯坡 `--target-kph 128`。

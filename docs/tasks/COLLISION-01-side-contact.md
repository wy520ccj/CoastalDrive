# COLLISION-01 Vehicle Side Contact

- 状态：done
- 基线 commit：`c12abee` (`Complete keyboard navigation in UI panels`)
- 目标：修复车辆侧向接近时可见车身穿透；重点覆盖不同车身朝向
- 允许修改：`src/vehicle_config.py`、`src/vehicle.py`、`tests/test_h3_review.py`、本任务包、`docs/current-progress.md`
- 禁止修改：Simulation 步长、车辆驱动/转向参数、AI 交通策略、UI/Scene 表现、音频和其他玩法
- 局部重构：仅把车辆碰撞盒半尺寸集中到车辆配置；玩家车和交通车通过同一 `Vehicle` 使用，不增加碰撞后传送或额外状态

## 复现与原因

- 当前两种正式车型及车轮的实际模型边界为横向半宽 `1.0325 m`、纵向半长 `2.145 m`。
- `Vehicle` 的 Bullet 盒碰撞体却只有 `0.78 m × 2.05 m` 半尺寸；两车真实外观已重叠时，Bullet 还可能没有接触点。两车型横纵向外廓相同、高度不同，因此使用共同水平碰撞尺寸，不按车型暗改驾驶性能。
- 新回归用 0°/30°/90° 同向并排和 0°/±30° 斜向车身，在可见外廓交叠 0.10 m 时查询 Bullet 接触；改动前同向三个角度均无接触，测试稳定复现。

## 验收

- [x] 玩家与交通车共用半宽 `1.05 m`、半长 `2.15 m` 的碰撞盒，覆盖两个车型及车轮；交通控制保持原有缓冲，避免拓宽感知范围造成拥堵。
- [x] 五种侧碰姿态和动态侧向接近回归通过；追尾动量/不过车测试保持通过。动态侧撞在 12 步内正常记录碰撞，中心距最小 `2.03 m`。
- [x] T1 交通完整测试及 headless seeds 0/17/23 通过。
- [x] 更新后的本机包通过窗口 smoke；玩家侧向实驾体验仍待确认。碰撞继续由 Bullet 求解，没有关闭碰撞或瞬移。

## 验证

- T0：Ruff 与侧碰五姿态、动态侧擦、既有追尾测试通过。
- T1：`tools/validate.py T1 --area traffic --tests tests/test_h3_review.py tests/test_traffic_impacts.py --output logs/validation/2026-09-27-side-contact-T1-final`；Ruff、49 项测试、headless seeds 0/17/23、hills seeds 0/23 均通过。
- 一次对照试验拓宽了交通行为感知半宽，导致固定种子下两辆车停车；随后对照证明碰撞盒单独加宽不会产生该回归，现保留原交通感知值及间距缓冲。初次失败报告在 `logs/validation/2026-09-27-side-contact-T1/`，最终报告在 `...-T1-final/`。
- Windows 文件夹包在 `builds/0.8.3-collision01/win_amd64/` 构建完成；从系统临时目录启动 smoke 通过，报告 `logs/package-collision01-external/h0-render-smoke.json`。
- T2/T3：不属于阶段 Gate，不运行。
- 用户截图是一个示例；验收覆盖多个相对朝向，追尾保留原回归，不扩大追尾行为调校。

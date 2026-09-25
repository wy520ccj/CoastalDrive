# 6B-03 小型分层素材池

- 状态：done（素材/自动部分）；实际汽车撞击音色归 6B-05 用户试听。设计基线 `34cec49231391c769ef38db1ee2e22363863c20b`。
- 实施：Astra 接续 6B-02 后直接实现；许可与加工配方见 `tools/prepare_impact_audio.py` 和素材登记。

## 目标与范围

交付可被后续播放器直接使用的素材清单与试听样本，解决起音、车身重量、结构变形、碎片和无缝摩擦五种功能。不得仅复制四个旧文件改名。

- 允许：`assets/game/audio/impact/`、`assets/game/audio/impact-bank.json`（新增）、`assets/source/phase6b_audio/` 原始素材、`assets/game/audio/License.txt`、`docs/asset-register.csv`、`tools/prepare_audio.py`、`tests/test_impact_assets.py`、`tools/validate.py` audio 映射、本包与进度。
- 只读：物理/Session、Soundscape、发动机/怠速/路噪现有文件与其处理参数。只扩展准备流程，不重制那三项。
- 禁止：无依据的许可声明、改物理、将旧整段 heavy 作为完整新重撞、用重复剪辑冒充 variant。旧四文件在播放器切换前保留，避免过渡版本缺资源。

## 确定性交付

`impact-bank.json` 采用普通 JSON：`version`、`pools`、`materials`、`severity_curve`、`mix` 四类实际配置（含版本共五个键）。每个 pool 记录 layer 和 variants；每个 variant 有稳定 id、相对文件路径、gain_db、peak、onset_ms、source_id；materials 指向 pool ID 与少量权重，无位置素材矩阵。severity_curve 初始留明确 provisional 状态及 6B-02 记录来源，不虚构已校准值；6B-04 接入前填可用的单调节点。路径相对于该 manifest，运行时不联网。

- [ ] 硬/金属 transient 各≥3；轻/重 body 各≥3；crunch≥3；debris≥3；金属/粗糙 scrape 各≥2。若真实素材短缺，列缺口，不以合成箱子声凑数。
- [ ] transient 显著起音≤5 ms，池内响度接近；保留动态和混音余量，短峰值检测与短时 RMS/感知试听并用，不能只做 peak normalize。
- [ ] scrape ≥数秒稳定段，环缝无跳变/嵌入式首撞/明显周期抽动；至少循环 10 s 试听样本。
- [ ] 来源页真实可访问，明确许可允许加工及当前公开分发；记录作者、许可版本/证据、原始 hash、处理参数、派生 hash，署名齐全。
- [ ] 提供轻/中/重分层组合试听 WAV 与各层独听样本到本次 logs 子目录；只作为选材工具，不冒充游戏实时验收。
- [ ] 自动检查 PCM 格式、文件存在、起音、峰值/池内电平差与 loop 接缝；实际听感由用户确认，不能写“波形通过=音色通过”。

## 验证与交接

新增映射后执行 T0/T1 `--area audio`；工具重新加工只操作本包素材，hash 可复现。正常 OpenAL 加载检查所有新 WAV；本包以离线音色样本和许可记录交付，游戏人工八项留 6B-05，T2/T3 不在本包跑。

- 22 条新 PCM WAV：金属/硬物瞬态、轻/重车身、crunch、debris 各 3，金属/粗糙 scrape 各 2。`impact-bank.json` 保存来源、派生 SHA-256、曲线及配方；`assets/game/audio/License.txt` 与 `docs/asset-register.csv` 保存 CC0 来源页。旧四个单文件碰撞声已退出运行资源。
- `tests/test_impact_assets.py` 检查全部派生 hash、格式、瞬态起音小于 5 ms、池内早期 RMS 差小于 4 dB、擦碰长度与接缝；2026-09-23 T0/T1 audio 通过。`tools/render_impact_audition.py --output logs/impact-audition-20260923` 生成轻/中/重单独样本、连续对比和 10 秒擦碰预览。
- 波形/自动指标只说明素材可用，汽车质感与事故混音是否通过仍按 6B-05 实驾试听判断。
- 通过机械检查后进入 6B-04；素材不合格先补素材，禁止回到旧碰撞分型阈值上掩盖。

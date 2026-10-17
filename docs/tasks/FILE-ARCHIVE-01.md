# FILE-ARCHIVE-01 项目旧版归档

- 状态：done；基线main/b31f420，施工前工作区干净。
- 用户授权：整理多余旧版文件，统一归入可回溯目录，不能影响最新主版本。
- 目标：统一archive/2026-10-17，按原相对路径保留构建包、历史启动器、旧源码快照和过期日志；保存SHA256清单、原路径映射与恢复脚本。
- 保护：src、assets/game、art源文件、vendor、.venv、5个src原生扩展、build/sim-double-runtime、当前源码启动器、当前任务/可复算证据、运行中窗口及用户LOCALAPPDATA实验记录。
- 范围：用户确认包括相邻旧副本、旧备份和独立工作树；后续明确授权精简无回溯意义或不影响回溯的文件。
- 验证：移动前后文件数/总字节/SHA256相同；当前运行依赖指纹相同；普通与Double运行入口和相关T1检查，保留未跑/失败原证据，不重跑性能或T2/T3。

## 完成内容

- 统一目录`archive/2026-10-17`。主目录954个归档根项迁移，旧构建包/旧入口/MFC旧工程/过期日志保持原相对路径。当前`launchers`只留4个源码入口和README，`builds`已清空待新构建，`build`只保留当前双精度SDK。
- 相邻VI工作树、旧AUDIO-01前备份、Codex下GR86与simulation-fidelity工作树均纳入同目录；3个工作树迁移前均无未提交/未追踪文件，包含的有意义ignored产物一并保留。VI仍有34个未合入main提交，分支和源码完整保留；另外两条来源提交已在main历史中，不删除分支。
- VI同盘用`git worktree move`；两个C盘工作树的Git跨盘move报`Improper link`，未改填成功。改用Robocopy `/E /SJ /SL /COPY:DAT /DCOPY:DAT`复制，完整SHA核验通过后`git worktree repair`更新关联；先移除旧目录的共享.venv链接，再检查无其他重解析点，按显式绝对路径删除已核验的跨盘原副本。共享主环境未遍历、未复制或删除。
- `repository.bundle`保留整理前全部24个可达refs及完整历史，`git bundle verify`通过，SHA256存档。bundle本地约2.59GiB，不提交到远端。
- 按用户精简授权删除11,332个缓存/中间/压缩重复文件，共7,672,147,456字节（7.145GiB）：Python、pytest、Ruff、打包wheel缓存和5类编译中间根；2.5GiB原始PStats日志已验证gzip解压SHA完全相同，只保留gzip。没有删独立版本运行文件、源码差异、历史失败或中断记录。zip展开副本仅检查，没有满足完整相等条件的整目录删除。
- 最终保留194,287个归档文件、38,777,013,754字节（不含新生成的Git bundle与索引）；15个主归档链接和3个外部共享环境链接保持目标不变。
- 根README、入口README、release-main及AGENTS旧工程只读路径已更新；旧发布说明原文另存归档。历史任务/证据不改写，旧绝对路径用moves.json/external.json映射。主程序不会从归档自动发现或加载依赖。

## 不影响主版本的证据

- 首轮主目录完整SHA校验：56,951文件/21,970,405,791字节一致；迁移前2,180个保护文件一致。更新入口说明后最终主目录保留46,525文件SHA重新检查通过，10,426个被授权精简的文件单列；2,179个当前源码/素材/原生扩展/SDK等指纹不变，唯一登记的保护项文本变更是`launchers/README.md`。
- 外部完整复制SHA：148,668文件/24,478,755,419字节一致；精简后的147,762文件大小/路径/链接/Git HEAD与干净状态再次核对通过。内容SHA复用精简前完整校验，实际仅按prune清单删除，未重复读全量哈希。906个外部被精简缓存另列。
- 当前`src/tests/tools/assets/art/vendor/setup.py/pyproject.toml/requirements*`无Git差异；src五原生扩展和`build/sim-double-runtime`保持原SHA。`.venv/Scripts/python.exe tools/physics/run_sim_double.py --check`两次均从原build路径加载Panda1.10.16/Bullet285/64位数学；不覆盖虚拟环境。
- `.venv/Scripts/python.exe tools/validate.py T1 --area core --area lab --area workflow --output logs/validation/FILE-ARCHIVE-01-T1 --timeout 600`：Ruff、210项、种子0/17/23各1200拍通过（含10000步与异工作目录启动检查）。这不是T2/T3、性能或新增人工驾驶验收，未重复执行这些范围。
- 19个历史启动器的exe目标全部存在；恢复脚本默认只预览，精简后949项可恢复，原位置有文件则停止，避免覆盖当前工作。恢复没有实际覆盖主目录。
- 归档工具两次临时检查错误（编码别名、相对/绝对Path混用）已修正；工作树首次跨盘move失败、原始日志/失败验证记录均如实保留。`logs/project-archive-20261017`保存过程与Robocopy摘要，任务代表证据位于`docs/evidence/FILE-ARCHIVE-01`。

## 回溯入口与提交

- [统一归档入口](../../archive/README.md)，批次README提供恢复命令；`moves.json`和`external.json`保存路径/HEAD/分支，逐文件清单gzip本地保存，`prune.json`解释精简依据。
- 当前用户LOCALAPPDATA实验数据、当前任务/可复算工程证据、原始相邻ADAS/ADAS.zip、美术源文件与非项目imagegen输出均保留。
- 归档二进制、完整逐文件清单、备份与工作树被archive整体忽略；索引、校验摘要、恢复脚本、历史入口与legacy原文显式本地提交。无远端推送。

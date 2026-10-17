# 开发试玩版发行证据

- `build-receipt.json`：最终构建，HEAD为内容基线8b03e0f，构建时未提交打包改动如实记录；761项源输入、五个重编扩展与最终产物SHA。
- `SHA256SUMS.txt`、`portable-integrity.json`：公开资产校验及ZIP内376个文件与安装输入一致。
- `source-T1.json`：相关51项与三种子；`package-tools-T0.json`：最终冻结工具/配置Ruff与资源检查。
- `normal-startup.json`/`menu.png`：冻结主程序从仓库外启动，正常音频/独立物理进程进入8车道路。
- `installed-runtime.json`、`installed-smoke.json`：真正安装后的冻结程序，三次可见窗口/实验台往返、原生数字输入、短试验/草稿/A槽/游标保持、正常独立物理进程关闭/重建；56张截图中保留代表`lab.png`、`drive.png`，已查看。
- `initial-lifecycle-race.json`、`initial-uninstall-tail.txt`：首次脚本过早检查导致失败；卸载日志实际Removed all=Yes，原失败不删除，完整原日志保留本地。
- `lifecycle-final.json`：外部检查器等待临时卸载进程实际清理后，使用同一SHA安装器仅复测安装/覆盖升级/卸载；程序/注册项/快捷方式移除，用户数据保留。
- `post-build-input-check.json`：最终构建后仅外部安装验证脚本改变，其不进入冻结包；其余760项输入保持。构建回执保留原始输入，不回填假快照。

完整日志/所有截图位于`logs/RELEASE-20261017/`，未上传大批本地日志。自动功能、实际渲染、人工体验分别记账；手感/声音/美术尚未全部获本版用户验收，不关闭原物理/长期性能Gate。

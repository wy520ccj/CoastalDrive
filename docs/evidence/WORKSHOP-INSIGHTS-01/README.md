# WORKSHOP-INSIGHTS-01 试验解读证据

基线main/855b99a1；[任务包](../../tasks/WORKSHOP-INSIGHTS-01.md)。新增两题解读、单项B准备及失败导出。旧评分/奖牌/预算、默认车辆/120Hz物理/SDK保持；无推送，人工体验pending，原T2与实时Gate保持开放。

Normal/Double各新执行4个短试验：原配制动346拍、70%加大制动器260拍、原配定圆1200拍、70k定圆1200拍，两库共6012新拍。组合制动32.406→24.445m（约24.57%）但4/3预算失败；70k循迹约3.175→0.153m，同时峰值侧偏约5.79°、末窗速度超限而失败。完整快照/执行器请求/元数据见各库raw/，gzip解压回experiment.json和snapshots.bin即可使用load_record读取。

两库brake-gold和corner-gold明确复用DESIGN-CHALLENGE-01/02真实金牌A/B；源路径、原SDK、原源码及首末摘要保留在summary与原始记录中，不算本轮新物理。reports/下每例均保留insights.json/txt及压缩HTML；两种金牌另保留完整A/B。其它例的原始A/B来自raw/：brake-original使用brake-base两次，brake-over使用brake-base/brake-over，corner-sharp使用corner-base/corner-sharp。

Normal1280×720、Double1024×768各5种解读和3种“准备”截图均为实际Panda界面，冻结更新后拍摄；已查看长失败提示、4项指标、按钮/换行及新准备状态。解读Esc先返回工坊，同窗捕获恢复保持；准备只改当前B一个选项、固定原车A不变、旧成绩立即失效且旧曲线保留，不自动运行或应用车辆。

首T0重复--tests参数仅末模块4项，明确为局部通过；修正后4模块57项通过。最终相关完整T1普通/Double各112项及0/17/23各1200步启动通过；覆盖原始记录篡改/协议、全部旧配方/奖牌、失败导出/保存、取消、方案恢复、模态退出、原实验台与同窗生命周期。执行命令见任务包；两T1旧进程在会话恢复时句柄已释放，按落盘完整终态核实，无重启/重复验证。

`archive-manifest.json`固定98份文件/51967677归档字节及各原始SHA；`source-manifest.json`固定12份最终源码LF SHA。`.gitattributes`禁用本目录自动换行转换和空白风格检查；首次Git检查将原始CRLF/日志尾空格报为空白错误，随后仅改此目录属性，原始记录字节保持。HTML已写出并检查内容/转义，未重新尝试此前安全策略拒绝的浏览器预览。自动回归、真实短试验、旧记录复用、静态渲染和人工体验分别记账。

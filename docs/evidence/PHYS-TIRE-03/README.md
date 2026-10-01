# PHYS-TIRE-03 接触区变形证据

当前生产默认启用柔性，两种模式共用四轮同末速度机制。完整T1及最终轮胎功能组T2已通过；首次超时与擦碰音频回归失败保留。完整T3、可见性能与人工驾驶pending。再接触闭环的子步精度限制见下文。

## 机制与参数

各向同性二维接触区弹簧/阻尼 `F=Kz+b ż` 与载荷敏感路面滑移元件串联，接点相对速度分为胎体变形速度与真实路面滑移速度。四轮局部隐式Fx/Fy求解共用一个车体末速度，保持旧轮速/变形直至共同收敛后提交冲量与变形；不在已求出的力后追加滤波。世界坐标变形经接触平面投影，离地/零μ按元件自由松弛。

[reference-parameters.json](reference-parameters.json)为reference-v6，完整62车辆字段；新增 `tire_compliance=True`、`K=150000 N/m`、`b=1000 N·s/m`。参数为通用参考车设计值，源码SHA及本机Bullet读回随表保存。成绩版本game-controls-v5/reference-v6保留ABS/TCS/ESC三开关分区。

每子步接触账本包含弹性储能变化、材料耗散、路面耗散和后向Euler弹性数值耗散；法线投影损失另列。部件/四轮测试检查机械+弹性总能量与动量。整车CSV的能量字段仅覆盖接触区储能/耗散，不是整车发动机、制动、碰撞及外力的完整能量守恒报告。耗散按tick内子步累加后求试验总和；储能峰值不按时间求和。力阶段 `force_contact_tick` 与完成步 `sample_tick` 分开。

## 原始轨迹与关闭分支

[mechanical-rigid/summary.json](mechanical-rigid/summary.json)：柔性False与冻结基线0362ee6在test/coastal/endless各1200tick严格对照，分别359792、1070373、1071284个既有值，共2,501,449值，差异0、最大数值差0。新增诊断字段单列；此结论限定关闭分支。

[vehicle-ab/summary.json](vehicle-ab/summary.json)包含两模式×11工况×A/B共44条独立6s轨迹，A=False、B=True；同车、同初值/输入/三电子开关，未调整发动机或控制增益。包含铺装/低μ/split制动、转向阶跃/饱和、弯中制动、倒车、再接触、滑行扰动、加速及定转向。[substeps/summary.json](substeps/summary.json)另存两模式×4工况×2/8子步共16条轨迹。[recontact-sensitivity/summary.json](recontact-sensitivity/summary.json)新增4条隔离轨迹，六条比较中on2/on8引用已有两条并保存引用SHA。因此新增物理轨迹为44+16+4，不能把六条比较都算新运行。

困难仿真主要6s指标如下，A/B均开启ABS/TCS/ESC。`path_distance_m`是完整6s路径，`stopping_path_distance_m`是首次满足停车判据时的路径；后二者不可混称停车距离。

| 工况 | 6s路径A→B m | 首次停车路径A→B m | 首次停车时间A→B s |
|---|---:|---:|---:|
| 铺装制动 | 43.857→43.918 | 43.844→43.857 | 3.125→3.133 |
| 低μ制动 | 64.919→64.984 | 64.911→64.943 | 4.683→4.683 |
| split-μ制动 | 67.109→66.532 | 67.095→66.471 | 4.250→4.200 |
| 弯中制动 | 25.680→25.712 | 25.670→25.669 | 3.167→3.167 |
| 离地再接触 | 63.361→63.494 | 63.348→63.432 | 3.892→3.900 |
| 加速 | 64.156→64.046 | 未停车 | 未停车 |

变化原样保留，不要求全部工况停距更短。split-μ末累计航向13.582→14.538°，再接触0.650→0.429°；局部变化不代表整个模型或数值精度已验收。

## 子步限制与下一优先项

[再接触隔离发现](recontact-sensitivity/findings.md)显示ABS on时2/4子步末航向0.429/0.384°，8/16为−4.593/−4.621°；路径分别63.494/63.577/64.379/64.408m。2/4与8/16落入不同结果分支，不能宣称默认2子步收敛。ABS off的2/8航向−11.775/−11.362°，偏航本身更大，关闭ABS不是修复。

on2/on8最早命令差tick77，完成步yaw差tick80，施力轮荷左右差tick97，ABS active分支差tick166。反馈与再接触演化可能放大小差异，当前证据没有唯一定位某一ABS规则；后来的轮荷不对称不能直接当最初原因。能量账本/求解残差良好不替代整车子步验收。下一完整阶段前优先继续此精度问题，保留原始轨迹及限制，不提高阈值掩盖差异。

## 分阶段检查与失败保留

- [component-t0.log](component-t0.log)：初轮102项组件T0通过，属于当时单轮原型；[component-scan/](component-scan/)的2025样本及三条240步序列早于最终四轮模型，不替代最终整车验收。
- 当前四轮共末速度及真实坡停专项88项通过，独立于上述旧原型计数。初轮顺序模型5°坡停10s位移0.033187m、外力时序修正后0.015551m仍超过0.01m；四轮共同求解修正后保持原门槛通过。
- [initial-findings.md](initial-findings.md)保留制动微小负功、弹性短暂回弹及低速测试输入错误。`vehicle-t0-initial.log`为69通过、2失败；正常游戏S触发真实倒车，改用SIMULATION_INPUT直接制动后[braking-command-t0.log](braking-command-t0.log)两项通过，保留0.01m/s与0.01rad/s门槛。
- 真实NPC生命周期定向T0为3项通过：实际驾驶产生非零变形/储能，shift/rebase保留，reset/真正回收清空，模式重建新车True且无旧储能。各批测试范围和模型阶段不同，不相加成统一最终数量。

完整[T1](t1/summary.json)的575测试、Ruff、三个种子各1200tick启动及两个种子12车弯坡30s全部通过。真实NPC生命周期3项定向T0在T1启动后新增，随后由全量T2覆盖；没有把它们计入575。

[校正全轨迹审计](trajectory-audit-corrected.json)逐行扫描60份CSV、43260行和173040个轮观测，6256348个数值字段均有限。最大求解残差0.000999953N，最大力预算正超量0.000334531N，均满足原0.001N容差；3793个零载荷与3477个施力阶段离地观测的力精确为零。柔性`Kz+b ż`最大误差9.10e−13N；材料/弹性数值/坐标耗散非负，路面有符号功最小−5.98e−6J、最大1149.315J。最小负值位于低速sticking，原有限力残差对应预算上界2.20e−5J，位置及推导见[初轮记录](initial-findings.md)，不钳负值或提高门槛。两个矩阵生成前后与审计时的72个生产Python源码SHA一致。审计初稿统计问题保留在原报告及初轮记录，未改原轨迹。

[护栏诊断](rail-contact/findings.md)保存刚性2°及柔性2°/4°/6°四条真实840tick轨迹。柔性2°首hit后仅2tick物理接触缺失，734tick因冲量低于25Ns失去开始资格；修复后的中间诊断进一步定位到真实护栏接缝source集合`(1)→(1,2)→(2)`。表现层保留25Ns/1.6m/s开始门槛；正在播放时按同材质、source交集接续，低/零冲量只降低实际音量，3tick缺失及释放判据不变。新来源无交集或不同材质仍须原开始门槛。修复未调整物理轨迹、车速或碰撞。

[音频失败与复测](audio-contact-t0.log)保留误判及失败fixture，最终真实1200tick仅撞击decision93、attack210；追加制动段release1019切向速度1.471m/s、off1022为1.322m/s，末车速0.000397m/s。原840tick的1hit/1attack要求保留，off现在验证真实停止。音频完整[T1](audio-t1/summary.json)59测试、Ruff及三个种子启动通过。[音频源码变化核对](audio-source-transition.json)证明相对A/B的72生产文件和4工具仅`src/audio/impact.py`改变；旧物理轨迹仍描述相同物理版本，最终表现行为由新验收覆盖。

首次[T2](t2/summary.json)全仓pytest1800s超时、护栏测试失败，后续14项未跑，不能作为通过证据。最终[T2](t2-final/summary.json)752测试及全部16项检查通过，包含handling/路面/交互、两条有限地图交通和三种子各120s直道/弯坡。pytest约2448s，全组约6637s墙钟；仅将进程预算提高至7200s，全部物理和测试门槛保持。[最终源核对](stage-source-verification.json)261个src/tests/tools Python验收前后逐文件相同；[首次源核对](stage-source-initial-verification.json)单独保留，不覆盖旧失败版本的核对事实。

用户已授权Luna一次本地提交及正常推送，含此前17个本地物理提交；提交范围预检见[publish-preflight.json](publish-preflight.json)，实际发布结论以本地`logs/publication/PHYS-TIRE-03.json`和远端HEAD核对为准。整个物理goal仍未完成，下一[PHYS-TIRE-04](../../tasks/PHYS-TIRE-04.md)处理再接触精度与求解效率。

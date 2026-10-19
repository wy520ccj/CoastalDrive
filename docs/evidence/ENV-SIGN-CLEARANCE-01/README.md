# ENV-SIGN-CLEARANCE-01 警示牌与隔音屏

用户截图见`user-report.png`。[任务包](../../tasks/ENV-SIGN-CLEARANCE-01.md)。seed23、2050米的curve-left与2048/2052米soundwall均d=10.4；真实警示牌宽1.96m，屏障半宽.24m，重叠约1.22m。实际游戏段同视角复现见`before/2050m.png`。

仅把屏障段（含面板边缘）的警示/限速小牌移到d=8.8的路肩，保留原里程、数量、图案、杆体、隔音屏、护栏、树木和道路/物理。`after/2050m.png`及`double-fixed-after/2050m.png`为真实资产修复图：目标净距Normal0.378334m、Double0.378331m；0/17/23种子、直线/平弯/弯坡0–16km共40处模型包络投影全部≥0.375m。读取序列化BAM所有顶点，按实际姿态计算，不只比较中心点；原始模型文件SHA保持。

画面为真实游戏美术段的固定相机静态渲染，物理快照和刚体数不变，不是新驾驶。原HILL-TRAFFIC两库完整驾驶/规则验证明确复用。最终Normal相关完整T1 36项（布置边界、原资产/原表面/原窗口、弯坡实际UI往返）及三种子通过，Double完整新UI模块1项及三种子通过，Ruff通过。

首T0为7过/1项夹具要求每种路形必有改动失败；有的直路种子没有小牌与屏障重合，修改为全组总计，并保留逐项设施不变比较。修正后8过。Double首静态工具把Vec3f直接传给Double NodePath失败；传原始坐标tuple后40处及实际渲染通过，未改生产几何/模型。原失败说明均保留。

```powershell
.venv/Scripts/python.exe tools/environment/soundwall_sign_check.py --output logs/validation/ENV-SIGN-CLEARANCE-01-before --phase before
.venv/Scripts/python.exe tools/environment/soundwall_sign_check.py --output logs/validation/ENV-SIGN-CLEARANCE-01-after --phase after
.venv/Scripts/python.exe tools/physics/run_sim_double.py tools/environment/soundwall_sign_check.py --output logs/validation/ENV-SIGN-CLEARANCE-01-double-fixed-after --phase after
.venv/Scripts/python.exe tools/validate.py T0 --tests tests/test_sign_clearance.py --output logs/validation/ENV-SIGN-CLEARANCE-01-fixed-T0
.venv/Scripts/python.exe tools/validate.py T1 --tests tests/test_sign_clearance.py tests/test_expressway_route.py tests/test_expressway.py tests/test_hill_traffic_ui.py --output logs/validation/ENV-SIGN-CLEARANCE-01-T1
.venv/Scripts/python.exe tools/physics/run_sim_double.py tools/validate.py T1 --tests tests/test_hill_traffic_ui.py --output logs/validation/ENV-SIGN-CLEARANCE-01-double-ui-T1
```

`archive-manifest.json`固定26份原始文件/1275392字节；4源码LF SHA见`source-manifest.json`，图像/日志/JSON原始字节禁用换行转换。早期Normal脚本与最终仅差无用导入移除和Float→Double坐标传参修正，生产布置与各自首末源码/SDK均留证。用户观感待查看，未代用户接受；仅本地，无推送。

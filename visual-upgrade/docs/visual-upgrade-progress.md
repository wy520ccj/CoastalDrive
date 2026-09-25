# 画面升级施工记录（visual-upgrade 副本）

副本位置：`visual-upgrade/`，由仓库根目录 robocopy 复制（排除 `.venv`、`build`、`builds`、`logs`、`legacy`、`.git`）。
**原仓库文件保持只读**；副本用原仓库 `.venv` 的 Python 解释器运行，源码与素材从副本加载。

## 运行方式

```powershell
# 工作目录：visual-upgrade/
$env:LOCALAPPDATA = "$PWD\logs\_localappdata"   # 沙箱不允许写真实 LOCALAPPDATA
& "..\.venv\Scripts\python.exe" src/main.py --headless --steps 600 --seed 17
& "..\.venv\Scripts\python.exe" tools/ui_preview.py --page menu --size 1672x941 `
    --output logs/ui-preview/menu-1672x941.png
```

`ui_preview.py` 用离屏真实渲染出图，用于和 `graphic_design/` 设计图逐张对照；它不是画面验收，只作对照证据。

## 基线（V00，已完成）

- 副本建立后首次离屏 smoke 通过：`logs/baseline-copy/h0-offscreen.png`、`h0-render-smoke.json`，渲染器为 RTX 4060 Laptop GPU。
- 原仓库开工快照：副本内 `.orig-baseline-snapshot.txt`（5442 个文件的大小与修改时间）。
- 设计图映射（10 张）：主菜单、计时 HUD、自由驾驶 HUD、无限高速挑战 HUD、暂停、声音设置、结算成功/失败/自由驾驶结束、车库。

## V01 UI 组件与视觉规范（进行中）

已完成：

- `tools/make_ui_textures.py` 重写为像素素材生成器：九宫格切片（panel / panel-solid / well / pill / chip）、
  24 张整块按钮贴图（4 种尺寸 × 6 种状态）、17 个 32px 图标。
- 配色与设计图一致：奶白 `#F3EFE3`、深海蓝 `#102B3A`、橙 `#F47C24`、金 `#FFC247`。
- 新增 `src/ui_theme.py`（配色、字号、间距唯一来源）、`src/ui_components.py`（Canvas 参考像素换算、
  UiSkin 贴图缓存与九宫格、PixelButton、PageRoot）、`src/ui_layout.py`（主菜单与居中页面构图）。
- 新增 `tools/ui_preview.py`（离屏页面渲染）、`tools/preview_ui_textures.py`（素材预览板）、
  `tools/compare_ui.py`（设计图与实际渲染上下拼接）。
- **主菜单已接入应用**：`python src/main.py --new-ui`，或副本根目录的 `run_new_ui.ps1`。
  默认（不带 `--new-ui`）仍是原界面，两套可来回对照。
- 主菜单在 1672x941 与 1280x720 渲染通过：`logs/ui-preview/menu-wired-1672x941.png`、`menu-1280x720.png`；
  对照图 `logs/ui-preview/compare-menu.png`（上=设计图，下=实际渲染）。

关键实现约束（踩过的坑，改动前先读）：

1. **PNG 必须带 alpha 通道**。Panda 的 PNG 写出器在 alpha 全为不透明时会丢掉 alpha，贴图变 RGB；
   开透明混合的节点遇到无 alpha 贴图会把整片判成透明。`write()` 在角落留 0.996 的差异保住通道。
2. **`OnscreenImage` 的 `setScale` 是半宽半高**。它的几何是 -1..1，想要 700 像素宽必须传
   `ux(700) / 2`。这是之前整个界面“一坨”的根因：面板被撑到 1060、Logo 被推出屏幕。
3. **`DirectFrame` 的 PGItem 默认不激活**，PGUI 不派发鼠标事件，按钮全都点不动。
   必须 `frame.node().setActive(True)`。
4. **按钮用整块贴图**，不要用九宫格拼在 `DirectFrame` 子节点里。同一套九宫格代码在 `aspect2d` 下正常，
   嵌进 `DirectFrame`/`PixelButton` 后图元位置与渲染都不受控；整块 `OnscreenImage` 表现稳定。
5. **所有 UI 坐标用全局参考像素**。页面节点锚在屏幕原点、`frameSize` 为零，子元素统一 `canvas.x/y`；
   不要把全局坐标的元素挂到带偏移的父节点下。
6. **像素字体缺 U+2212**（数学减号）会渲染成方框，音量按钮必须用 ASCII `-`。
7. **页面必须有 `destroy()`**，否则切页时崩在 `_hide_pixel_page`。
8. 字号：`scale = 像素 / 540`（1080p 基准），720p 自动等比。
9. `doMethodLater` 的任务里 `task.time` 是**延迟到期后的相对时间**，不能用来等固定时长。
10. `run_new_ui.ps1` 与 `启动新界面.bat` 必须保持**纯 ASCII**：cmd 按 GBK 解码 UTF-8 批处理会拆坏语法，
    Windows PowerShell 5.1 在无 BOM 时按 ANSI 读脚本，中文注释错位后会吃掉引号。

## 修复记录：界面重叠 / 菜单不消失（2026-09-24）

- 现象：真实窗口里暂停页、菜单页留在屏幕上，与旧 HUD 叠在一起。
- 根因：`_show_pixel_page` 只在“有像素页面”的分支里切页；**驾驶、加载、车库这些没有像素页面的
  状态直接 `return False`，却没有销毁上一个页面**。于是从菜单点进驾驶、或从暂停恢复驾驶后，
  像素页仍留在屏幕上，旧 HUD 同时在显示。
- 修法：`_show_pixel_page` 改为先把目标页解析出来；没有目标页（驾驶/加载）或该状态由旧面板承担
  （车库）时，先 `_hide_pixel_page()` 再返回 False。
- 已加 `tools/check_ui_states.py`：遍历菜单 / 驾驶 / 暂停 / 声音 / 高速 / 结算 / 车库 / 返回菜单，
  断言**像素页面与旧 HUD 互斥**，且驾驶态必须显示旧 HUD。这类“两套界面叠加”的 bug 现在能被自动发现。

## 修复记录：按钮点不动（2026-09-24，两次）

**第一次（崩溃）**：`PixelButton._on_press` 返回了不存在的常量。这一版 Panda3D 里按下状态名是
`DGG.BUTTON_DEPRESSED_STATE`，没有 `BUTTON_PRESSED`。

**第二次（点了毫无反应、也不报错）**：真正的根因是 **不能子类化 DirectGui 控件**。
实测：`class A(DirectButton): pass` 就足以让 `PGItem.has_frame()` 变成假，而裸 `DirectButton` 为真；
PGUI 的鼠标拾取依赖 frame，没有 frame 时鼠标永远落不到按钮上，且不抛任何异常。
现在 `PixelButton` 改为**组合**（内部持有一个普通 `DirectButton` 并转发 `set_text`/`set_style`/`destroy`），
六个按钮全部恢复 `hasFrame=True` + `active=True`，与原界面实测可点的按钮结构一致。

**两次都暴露了同一个测试漏洞**：之前的“点击验证”直接调 `button.command()`，绕过了事件处理与拾取。
`tools/check_buttons.py` 现在做三件事：
1. 断言每个按钮的 `has_frame()` 与 `getActive()`（可拾取性的硬前提）；
2. 发送 DirectGui 真正 accept 的事件名（`ENTER/EXIT/B1PRESS/B1RELEASE/B1CLICK` + `guiId`）；
3. 主菜单点击后断言真的进入自由驾驶。
覆盖主菜单、暂停、声音、高速与两种结算页。**按钮类改动必须跑它，不能只调 `command()`。**

## V04 滨海环境首轮（已完成）

- `Scene.add_inner_slope()`：内侧坡地装饰带——12 段近景山体（复用 `_add_ridge`）提供体量，
  4 排共 240 棵松树形成路边林带，坡脚 26 块岩石。**全部是展示几何，不参与物理**，
  放在远离行驶线的不可达区域。
- **踩过的坑**：山体的 footprint 很宽（半径的 1.7 倍），第一版把中心放在 -84 时覆盖到 -9，
  把新加的松林、岩块和原有路边树一起埋进山体里，只露出几块破面。现在山体中心推到 -112，
  给 -11..-40 留出林带。
- 岩壁材质改用下载的 Poly Haven `cliff_side`（CC0），文件缺失时回退到程序生成纹理。
- 证据：`logs/ui-preview/compare-scene-v04.png`（上=基线，下=当前）、`logs/v04d/h0-offscreen.png`。

## V02 傍晚光照与天空（已完成首轮）

- `src/scene.py`：光照改为傍晚方案——低角度暖阳（`SUN_OFFSET` 指向海面侧前方）、冷色环境补光、
  暖色地平线雾；天空背景色与雾色分开设置，避免整片天一样亮。
- `src/sky_dome.py`：程序化天空着色器重调——地平线金橙带、上层深蓝、云层更暖更有层次、
  太阳光斑与大范围霞光分开；着色器的太阳位置与方向光的方位一致。
- 海面基色改为更饱和的绿松石（`0.10, 0.58, 0.72`）。
- 证据：`logs/v02-drive/h0-offscreen.png`（驾驶视图）与 `logs/baseline-copy/h0-offscreen.png`（改造前基线）。
- 仍未做：草地/岩壁材质分层、山体与村落、植被密度（属 V04/V06）。

## 素材下载管线

- `tools/fetch_assets.py`：按清单从 Poly Haven（CC0）取贴图，带重试，并把来源/许可/本地路径写入
  `assets/raw/polyhaven-manifest.json`。清单当前包含 `cliff_side`（岩壁）与 `coast_sand_rocks_02`（礁石）。
- `tools/fetch_font.py`：取 Ark Pixel 字体并落盘 OFL 许可。
- **限制**：Poly Haven 的 CDN 很慢且偶发 TLS 握手超时（实测约 60 KB/s）。需要下载时放后台跑，
  不要阻塞画面工作；1K 贴图足够，不必下 2K/4K。

## 字体与素材获取

- **界面中文换成 Ark Pixel Font 12px 比例字形**（SIL OFL 1.1）。它比仓库原有的 Fusion Pixel
  笔画更粗、字形更宽，明显更接近设计图；OFL 许可文本与字体一同存放在 `assets/game/ui/fonts/`。
  获取方式固化为 `tools/fetch_font.py`（记录版本与许可），字体缺失时自动回退到 Fusion Pixel。
- 字号统一取 12 的整数倍（24/36/72），避免非整数缩放导致糊边；再叠一层同色 1 像素描边加粗，
  补偿像素字体笔画偏细的问题。
- 素材登记见 `docs/asset-register.csv`。
- **沙箱网络**：`.NET`/PowerShell 的 HTTPS 因 schannel 无凭证而失败，但 **Python 自带 OpenSSL 可以下载**
  （`urllib`）。后续获取贴图/模型/字体一律走 Python 脚本，并登记来源与许可。
- 字体对照工具：`tools/preview_fonts.py`；设计图量取工具：`tools/measure_design.py`。

## 已完成的像素界面页面

主菜单、暂停、声音设置、高速设置、结算（计时成功/失败、自由驾驶结束、高速挑战）全部由像素界面接管。
`--new-ui` 控制，默认关闭时仍是原界面；车库预览仍在旧面板上编辑。

## 与设计图的剩余差距

对照 `logs/ui-preview/compare-menu.png`（上=设计图，下=实际渲染）：

- 图标仍是简化形：设计图的秒表、棕榈、高速、房屋、扬声器有更多细节。
- 设计图面板是半透明白、带投影；当前为不透明奶白加底部阴影。
- **场景差距最大**：设计图是夕阳、岩壁、松林、白墙村落、跨海桥、灯塔与精细跑车；
  当前仍是原低模场景与方块车（属 V02/V03/V04/V06）。

## 验证记录（2026-09-24）

| 检查 | 命令 | 结果 |
|---|---|---|
| Ruff | `python -m ruff check src tools` | 通过 |
| 旧界面离屏 smoke | `python src/main.py --smoke` | `passed: true` |
| 新界面离屏 smoke | `python src/main.py --smoke --new-ui` | `passed: true` |
| 启动器端到端 | `cmd /c "启动新界面.bat --smoke --output logs\smoke-bat"` | `passed: true`（cmd→PS→游戏全链路） |
| 点击与导航 | 直接触发各按钮 command | 6 个命中框 `active=True`；进入自由驾驶、进出高速/声音设置、音量 100%→90% 均生效 |
| 页面矩阵 | `python tools/ui_preview.py --state <8 个状态>` | 8 个状态全部出图无异常 |

**未执行**：仓库 pytest 套件。本沙箱下 pytest 无法扫描自己创建的临时目录
（`PermissionError: WinError 5`），与本次改动无关，但**不能声称测试套件已通过**。
正式验收请在正常环境下按 `docs/tasks/README.md` 跑 T0/T1。

## 遗留问题

- 车库仍是旧界面；从新菜单进入车库会看到新旧切换。
- 各页面尚未逐像素核对设计图；图标细节偏简。
- 车辆造型、傍晚光照/天空、滨海与高速景观、车库（V02–V08）均未开始。

## 与原应用的关系

`src/application.py` 只加了 `new_ui` 开关、`_show_pixel_page` / `_show_page` / `_hide_old_panel`
与各页面构造函数，原界面路径保持原样。旧界面仍需要整张 `panel.png` / `panel-wide.png` / `button*.png`，
这些贴图由 `make_ui_textures.py` 的 `whole()` 继续生成，等车库也换成像素版后再移除。


"""落日黑曜石与琥珀金风格多层级游戏设置界面（大类 → 子页 → 设置项 + 右侧详情检视器）。"""

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectButton, DirectFrame, OnscreenText
from panda3d.core import TextNode, TextureStage, TransparencyAttrib

from audio.music import STATIONS
from session import Phase
from settings import (
    CAMERA_DISTANCES,
    FPS_LIMITS,
    GRAPHICS_PRESETS,
    KEY_PRESETS,
    MSAA_OPTIONS,
    RESOLUTIONS,
    SHADOW_QUALITIES,
    SPEED_UNITS,
    VIEW_DISTANCES,
    WINDOW_MODES,
    key_label,
)
from ui import atelier, theme
from ui.lab_widgets import gradient_panel, rounded_panel

WHITE = theme.WHITE

# 一级大类定义：(id, 标题, 副标题, 图标)
CATEGORIES = (
    ("graphics", "画面设置", "显示 · 画质 · 视野", "atelier/icon-compass.png"),
    ("audio", "声音设置", "混音 · 电台 · 试听", "atelier/icon-speaker.png"),
    ("controls", "操作设置", "键位 · 辅助开关", "atelier/icon-steering.png"),
    ("gameplay", "游戏与界面", "视角 · 仪表 · 行为", "atelier/icon-sliders.png"),
)

# 二级子分页定义：每页 2–5 行，保证 16:9 与 4:3 下宽松无遮挡。
SUBSECTIONS = {
    "graphics": (
        ("display", "显示与窗口"),
        ("quality", "画质与渲染"),
        ("camera", "镜头与视野"),
    ),
    "audio": (
        ("mixer", "音量混音"),
        ("radio", "电台与行为"),
    ),
    "controls": (
        ("driving_keys", "驾驶键位"),
        ("shortcut_keys", "快捷功能键"),
        ("assists", "驾驶辅助"),
    ),
    "gameplay": (
        ("hud_cam", "视角与仪表"),
        ("behavior", "驾驶行为"),
    ),
}

WINDOW_MODE_LABELS = {
    "windowed": "窗口模式",
    "borderless": "无边框全屏",
    "fullscreen": "独占全屏",
}
PRESET_LABELS = {
    "low": "流畅",
    "medium": "均衡",
    "high": "高清",
    "ultra": "极高",
    "custom": "自定义",
}
SHADOW_LABELS = {
    "off": "关闭",
    "medium": "中 (1024)",
    "high": "高 (默认)",
    "ultra": "极高 (4096)",
}
VIEW_LABELS = {
    "short": "近 (800m)",
    "medium": "中 (1150m)",
    "far": "远 (1500m)",
    "ultra": "极远 (2000m)",
}
KEY_PRESET_LABELS = {
    "wasd": "WASD 标准",
    "arrows": "方向键驾驶",
    "custom": "自定义方案",
}
ACTION_TITLES = {
    "throttle": "油门 / 加速",
    "brake": "刹车 / 倒车",
    "steer_left": "向左转向",
    "steer_right": "向右转向",
    "camera": "切换追车视角",
    "reset": "车辆复位",
    "radio_next": "切换车载电台",
    "radio_mute": "静音 / 恢复电台",
    "ghost": "幽灵车开关",
}


class SettingsPanel:
    """独立多层级设置界面：管理画面、声音、操作与游戏界面设置。"""

    def __init__(self, app):
        self.app = app
        self.root = app.aspect2d.attachNewNode("settings-panel")
        self.root.setTransparency(TransparencyAttrib.MAlpha)
        self.content = self.root.attachNewNode("settings-content")
        self.visible = False
        self.category = "graphics"
        self.subsections = {cat[0]: 0 for cat in CATEGORIES}
        self.selected = 0
        self.listening_action = None
        self.feedback_notice = ""
        self.restart_needed = False
        self._aspect = None
        self._return_target = "menu"
        self._widgets = []
        self._row_specs = []
        self._row_frames = []
        self._row_bars = []
        self._row_titles = []
        self.root.hide()

    @property
    def audio_preview_active(self):
        """仅在打开设置且停留在声音分类时试听车载电台。"""
        return self.visible and self.category == "audio"

    def open(self, category="graphics", *, subsection=0, return_target="menu"):
        if category not in SUBSECTIONS:
            category = "graphics"
        self.category = category
        self.subsections[category] = max(0, min(len(SUBSECTIONS[category]) - 1, subsection))
        self.selected = 0
        self.listening_action = None
        self.feedback_notice = ""
        self._return_target = return_target
        self.visible = True
        self.root.show()
        self.redraw()

    def close(self):
        self.listening_action = None
        self.visible = False
        self._clear()
        self.root.hide()

    def _clear(self):
        for widget in self._widgets:
            widget.destroy()
        self._widgets.clear()
        self._row_frames.clear()
        self._row_bars.clear()
        self._row_titles.clear()
        self.content.removeNode()
        self.content = self.root.attachNewNode("settings-content")

    def destroy(self):
        self._clear()
        self.root.removeNode()

    def resize(self, aspect):
        if self.visible and aspect != self._aspect:
            self.redraw()

    def select_category(self, category):
        if category == self.category and self.listening_action is None:
            return
        self.listening_action = None
        self.feedback_notice = ""
        self.category = category
        self.selected = 0
        self.app.audio_cue("select")
        self.redraw()

    def cycle_category(self, step):
        ids = [item[0] for item in CATEGORIES]
        self.select_category(ids[(ids.index(self.category) + step) % len(ids)])

    def select_subsection(self, index):
        count = len(SUBSECTIONS[self.category])
        target = index % count
        if target == self.subsections[self.category] and self.listening_action is None:
            return
        self.listening_action = None
        self.feedback_notice = ""
        self.subsections[self.category] = target
        self.selected = 0
        self.app.audio_cue("select")
        self.redraw()

    def _current_rows(self):
        """生成当前 (category, subsection) 的真实设置项描述。"""
        gs = self.app.game_settings
        au = self.app.audio_settings
        sub_id = SUBSECTIONS[self.category][self.subsections[self.category]][0]
        in_menu = self.app.session.phase == Phase.MENU

        if self.category == "graphics":
            if sub_id == "display":
                res_label = f"{gs.resolution[0]} × {gs.resolution[1]}"
                fps_label = "不限" if gs.fps_limit == 0 else f"{gs.fps_limit} FPS"
                return [
                    {
                        "id": "window_mode",
                        "kind": "cycle",
                        "title": "显示模式",
                        "subtitle": "窗口、无边框或全屏显示",
                        "value": WINDOW_MODE_LABELS[gs.window_mode],
                        "default": "窗口模式",
                        "timing": ("立即生效", theme.PINE),
                        "detail": "切换游戏窗口形态。无边框全屏兼顾多任务切屏与全屏沉浸感；独占全屏适合追求最低合成延迟。",
                        "dots": (WINDOW_MODES.index(gs.window_mode), len(WINDOW_MODES)),
                    },
                    {
                        "id": "resolution",
                        "kind": "cycle",
                        "title": "渲染分辨率",
                        "subtitle": "窗口或全屏输出尺寸",
                        "value": res_label,
                        "default": "1280 × 720",
                        "timing": ("立即生效", theme.PINE),
                        "detail": "设置渲染窗口的目标像素尺寸。提高分辨率可获得更锐利的路面标线与仪表字形，同时增加 GPU 像素填充开销。",
                        "dots": (
                            RESOLUTIONS.index(gs.resolution) if gs.resolution in RESOLUTIONS else 0,
                            len(RESOLUTIONS),
                        ),
                    },
                    {
                        "id": "vsync",
                        "kind": "toggle",
                        "title": "垂直同步 (VSync)",
                        "subtitle": "与显示器刷新率同步出帧",
                        "value": gs.vsync,
                        "default": "开启",
                        "timing": ("下次启动生效", theme.STEEL_TEXT),
                        "detail": "垂直同步可消除高速转弯时的画面撕裂，但可能带来轻微输入延迟。关闭后将启用帧率上限节拍。",
                    },
                    {
                        "id": "fps_limit",
                        "kind": "cycle",
                        "title": "帧率上限",
                        "subtitle": "关闭垂直同步时的渲染限帧",
                        "value": fps_label,
                        "default": "90 FPS",
                        "timing": ("立即生效", theme.PINE),
                        "detail": "限制非垂直同步模式下的最大渲染帧率，在流畅度、GPU 温度与物理步长稳定性间取得平衡。120 Hz 物理世界始终独立运行。",
                        "dots": (FPS_LIMITS.index(gs.fps_limit), len(FPS_LIMITS)),
                    },
                ]
            if sub_id == "quality":
                preset = gs.graphics_preset
                msaa_label = "关闭" if gs.msaa_samples == 0 else f"{gs.msaa_samples}× MSAA"
                return [
                    {
                        "id": "graphics_preset",
                        "kind": "cycle",
                        "title": "画质预设",
                        "subtitle": "一键联动阴影、抗锯齿与视距",
                        "value": PRESET_LABELS[preset],
                        "default": "高清",
                        "timing": ("部分重启生效", theme.STEEL_TEXT),
                        "detail": "快速切换整体画面档位：流畅（核显优先）、均衡、高清（默认推荐）或极高。单独调整下方任意细项会自动切换为自定义。",
                        "dots": (
                            list(GRAPHICS_PRESETS).index(preset) if preset in GRAPHICS_PRESETS else 0,
                            len(GRAPHICS_PRESETS),
                        ),
                    },
                    {
                        "id": "shadow_quality",
                        "kind": "cycle",
                        "title": "太阳阴影质量",
                        "subtitle": "动态平行光阴影贴图精度",
                        "value": SHADOW_LABELS[gs.shadow_quality],
                        "default": "高 (默认)",
                        "timing": ("立即生效", theme.PINE),
                        "detail": "控制车身、护栏与海岸林木的实时日光阴影精度。在核显或追求极高帧率时，下调至中或关闭可显著减轻渲染负担。",
                        "dots": (SHADOW_QUALITIES.index(gs.shadow_quality), len(SHADOW_QUALITIES)),
                    },
                    {
                        "id": "msaa_samples",
                        "kind": "cycle",
                        "title": "多重采样抗锯齿",
                        "subtitle": "平滑车身轮廓与斜向标线边缘",
                        "value": msaa_label,
                        "default": "4× MSAA",
                        "timing": ("下次启动生效", theme.STEEL_TEXT),
                        "detail": "硬件 MSAA 能有效抑制远距道路标线与车辆边缘闪烁。此项在创建渲染管线时生效，修改后将在下次启动游戏时应用。",
                        "dots": (MSAA_OPTIONS.index(gs.msaa_samples), len(MSAA_OPTIONS)),
                    },
                    {
                        "id": "view_distance",
                        "kind": "cycle",
                        "title": "渲染视距",
                        "subtitle": "主相机远裁面距离",
                        "value": VIEW_LABELS[gs.view_distance],
                        "default": "远 (1500m)",
                        "timing": ("立即生效", theme.PINE),
                        "detail": "控制远景海岸山体与高速地平线的最大绘制距离。缩短视距可减少远景几何绘制，延长视距可令长直道视野更开阔。",
                        "dots": (VIEW_DISTANCES.index(gs.view_distance), len(VIEW_DISTANCES)),
                    },
                    {
                        "id": "exposure",
                        "kind": "slider",
                        "title": "画面亮度 / 曝光",
                        "subtitle": "微调落日与晴空整体明暗",
                        "value": gs.exposure,
                        "min": 80,
                        "max": 120,
                        "step": 5,
                        "unit": "%",
                        "default": "100%",
                        "timing": ("立即生效", theme.PINE),
                        "detail": "按百分比微调场景物理光照曝光强度，适配不同亮度的显示器，不改变真实路面附着或光照方向。",
                    },
                ]
            return [
                {
                    "id": "fov",
                    "kind": "slider",
                    "title": "基础水平视野 (FOV)",
                    "subtitle": "追车相机的基准广角范围",
                    "value": gs.fov,
                    "min": 60,
                    "max": 82,
                    "step": 2,
                    "unit": "°",
                    "default": "68°",
                    "timing": ("立即生效", theme.PINE),
                    "detail": "调整追车镜头的基础视场角。较低数值（60°–66°）更贴近弯心判断，较高数值（72°–82°）速度感更强且适合宽屏显示器。",
                },
                {
                    "id": "dynamic_fov",
                    "kind": "toggle",
                    "title": "高速动态视野",
                    "subtitle": "随车速提升平滑拓宽最多 4° 视野",
                    "value": gs.dynamic_fov,
                    "default": "开启",
                    "timing": ("立即生效", theme.PINE),
                    "detail": "加速时小幅拉宽视野以增强高速巡航的速度张力；若希望弯道距离感始终保持恒定几何比例，可关闭此项。",
                },
            ]

        if self.category == "audio":
            if sub_id == "mixer":
                return [
                    {
                        "id": "master_volume",
                        "kind": "slider",
                        "title": "主音量",
                        "subtitle": "控制全部声音通道的总输出",
                        "value": au.master_volume,
                        "min": 0,
                        "max": 100,
                        "step": 10,
                        "unit": "%",
                        "default": "100%",
                        "timing": ("立即生效", theme.PINE),
                        "detail": "全局音量总控。归零时将彻底静音引擎、轮胎、碰撞、电台与界面提示音。",
                    },
                    {
                        "id": "effects_volume",
                        "kind": "slider",
                        "title": "效果音总量",
                        "subtitle": "碰撞、环境与效果总缩放",
                        "value": au.effects_volume,
                        "min": 0,
                        "max": 100,
                        "step": 10,
                        "unit": "%",
                        "default": "100%",
                        "timing": ("立即生效", theme.PINE),
                        "detail": "控制所有非音乐音效的总体比例，包含护栏碰撞、抓地反馈以及下方引擎与提示音分轨。",
                    },
                    {
                        "id": "engine_volume",
                        "kind": "slider",
                        "title": "引擎与轮胎",
                        "subtitle": "发动机声浪、胎噪与风噪",
                        "value": au.engine_volume,
                        "min": 0,
                        "max": 100,
                        "step": 10,
                        "unit": "%",
                        "default": "100%",
                        "timing": ("立即生效", theme.PINE),
                        "detail": "单独调节驾驶时的动力声浪与轮胎滑移听觉反馈，方便在听车载电台或专心听换挡转速间按喜好混音。",
                    },
                    {
                        "id": "music_volume",
                        "kind": "slider",
                        "title": "车载音乐",
                        "subtitle": "电台曲目与首页背景音乐",
                        "value": au.music_volume,
                        "min": 0,
                        "max": 100,
                        "step": 10,
                        "unit": "%",
                        "default": "55%",
                        "timing": ("立即生效", theme.PINE),
                        "detail": "调节电台与菜单音乐音量。停留在本页面期间会实时试听当前所选电台，方便边听边调。",
                    },
                    {
                        "id": "ui_volume",
                        "kind": "slider",
                        "title": "界面与赛事提示音",
                        "subtitle": "菜单按键、倒计时与检查点短音",
                        "value": au.ui_volume,
                        "min": 0,
                        "max": 100,
                        "step": 10,
                        "unit": "%",
                        "default": "100%",
                        "timing": ("立即生效", theme.PINE),
                        "detail": "调节菜单切换、确认、起步 3-2-1 倒计时与通过检查点时的提示短音量。",
                    },
                ]
            return [
                {
                    "id": "radio_station",
                    "kind": "cycle",
                    "title": "当前车载电台",
                    "subtitle": "驾驶中亦可按 N 切台 · M 静音",
                    "value": STATIONS[au.radio_station],
                    "default": STATIONS[1],
                    "timing": ("立即生效", theme.PINE),
                    "detail": "选择驾驶时播放的车载电台频道，支持无缝切换与暂停续播。选择“关闭”可在保留菜单提示音的同时关闭电台音乐。",
                    "dots": (au.radio_station, len(STATIONS)),
                },
                {
                    "id": "mute_unfocused",
                    "kind": "toggle",
                    "title": "切出窗口自动静音",
                    "subtitle": "窗口失去焦点时暂停音频输出",
                    "value": au.mute_unfocused,
                    "default": "关闭",
                    "timing": ("立即生效", theme.PINE),
                    "detail": "开启后，切换到桌面或其他应用时将自动静音游戏声音，切回窗口后自动恢复原音量。",
                },
            ]

        if self.category == "controls":
            if sub_id == "driving_keys":
                preset = gs.key_preset
                return [
                    {
                        "id": "key_preset",
                        "kind": "cycle",
                        "title": "键位预设方案",
                        "subtitle": "一键套用 WASD 或方向键驾驶",
                        "value": KEY_PRESET_LABELS[preset],
                        "default": "WASD 标准",
                        "timing": ("立即生效", theme.PINE),
                        "detail": "快速切换主驾驶键位布局。自定义下方任意按键后会自动切换为“自定义方案”；菜单方向键导航始终保持可用。",
                        "dots": (
                            list(KEY_PRESETS).index(preset) if preset in KEY_PRESETS else 0,
                            len(KEY_PRESETS),
                        ),
                    },
                    *[
                        {
                            "id": f"bind:{action}",
                            "kind": "keybind",
                            "action": action,
                            "title": ACTION_TITLES[action],
                            "subtitle": "按 Enter 或点击后输入新按键",
                            "value": gs.key_bindings[action],
                            "default": key_label(KEY_PRESETS["wasd"][action]),
                            "timing": ("立即生效", theme.PINE),
                            "detail": f"设置“{ACTION_TITLES[action]}”对应的键盘按键。若新按键已被其他动作占用，系统会自动互换以避免按键冲突。",
                        }
                        for action in ("throttle", "brake", "steer_left", "steer_right")
                    ],
                ]
            if sub_id == "shortcut_keys":
                return [
                    {
                        "id": f"bind:{action}",
                        "kind": "keybind",
                        "action": action,
                        "title": ACTION_TITLES[action],
                        "subtitle": "按 Enter 或点击后输入新按键",
                        "value": gs.key_bindings[action],
                        "default": key_label(KEY_PRESETS["wasd"][action]),
                        "timing": ("立即生效", theme.PINE),
                        "detail": f"设置“{ACTION_TITLES[action]}”的快捷键。Esc、Enter、Tab、F2、F3 为系统保留键，不可覆盖。",
                    }
                    for action in ("camera", "reset", "radio_next", "radio_mute", "ghost")
                ]
            # 驾驶辅助子页：直接对接 session 与 DrivingModeStore。
            timing = ("下次发车生效", theme.AMBER) if in_menu else ("仅主菜单可调", theme.DARK_SUB)
            return [
                {
                    "id": "abs",
                    "kind": "toggle",
                    "title": "ABS  制动防抱死",
                    "subtitle": "全力制动时维持转向抓地力",
                    "value": self.app.session.abs_enabled,
                    "default": "开启",
                    "disabled": not in_menu,
                    "timing": timing,
                    "detail": "高附着或急刹时动态调节各轮制动力矩，防止车轮抱死失控。车辆电子配置与圈速榜隔离，需在主菜单更改并于下次发车生效。",
                },
                {
                    "id": "tcs",
                    "kind": "toggle",
                    "title": "TCS  驱动防滑",
                    "subtitle": "抑制大油门出弯时的驱动轮空转",
                    "value": self.app.session.tcs_enabled,
                    "default": "开启",
                    "disabled": not in_menu,
                    "timing": timing,
                    "detail": "监测驱动轮纵向滑移率并在超出阈值时限制过量扭矩，帮助出弯更平稳加速。关闭后可体验完全自由的油门控制。",
                },
                {
                    "id": "esc",
                    "kind": "toggle",
                    "title": "ESC  车身横摆稳定",
                    "subtitle": "主动修正转向过度与甩尾偏转",
                    "value": self.app.session.esc_enabled,
                    "default": "开启",
                    "disabled": not in_menu,
                    "timing": timing,
                    "detail": "通过单轮差动制动修正过度横摆角速度，降低高速变线与连续弯道失控风险。关闭后完全由轮胎与驾驶操作决定姿态。",
                },
            ]

        # 游戏与界面 (gameplay)
        if sub_id == "hud_cam":
            cam_label = "标准跟车 (11m)" if gs.camera_distance <= 12.0 else "远距视野 (16m)"
            unit_label = "km/h (公制)" if gs.speed_unit == "kmh" else "mph (英制)"
            return [
                {
                    "id": "camera_distance",
                    "kind": "cycle",
                    "title": "默认追车距离",
                    "subtitle": "驾驶中亦可按视角键随时切换",
                    "value": cam_label,
                    "default": "标准跟车 (11m)",
                    "timing": ("立即生效", theme.PINE),
                    "detail": "选择追车镜头的默认跟车距离，同时保留经认可的 3.2m 镜位高度与道路纵坡贴合。16m 远距更利于预判高速弯道与车流。",
                    "dots": (CAMERA_DISTANCES.index(gs.camera_distance), len(CAMERA_DISTANCES)),
                },
                {
                    "id": "speed_unit",
                    "kind": "cycle",
                    "title": "车速表单位",
                    "subtitle": "切换驾驶仪表盘的速度显示制式",
                    "value": unit_label,
                    "default": "km/h (公制)",
                    "timing": ("立即生效", theme.PINE),
                    "detail": "切换滨海、高速与生涯 HUD 速度表读数单位（公里/小时 或 英里/小时）。纯表现层转换，不影响车辆物理速度与赛事判定。",
                    "dots": (SPEED_UNITS.index(gs.speed_unit), len(SPEED_UNITS)),
                },
                {
                    "id": "show_key_hints",
                    "kind": "toggle",
                    "title": "HUD 按键提示栏",
                    "subtitle": "驾驶画面左下角的操作键位提示",
                    "value": gs.show_key_hints,
                    "default": "开启",
                    "timing": ("立即生效", theme.PINE),
                    "detail": "熟悉键位后可关闭左下角按键提示栏，让海岸风景与路面视野更加清爽无遮挡。",
                },
            ]
        return [
            {
                "id": "ghost_default",
                "kind": "toggle",
                "title": "计时挑战幽灵车",
                "subtitle": "有个人最佳记录时显示参照幽灵",
                "value": gs.ghost_default,
                "default": "开启",
                "timing": ("立即生效", theme.PINE),
                "detail": "在滨海计时挑战中显示个人同配置最佳圈的半透明参照车影，方便直观对比走线与制动点（驾驶中可按幽灵键随时开关）。",
            },
            {
                "id": "show_diagnostics",
                "kind": "toggle",
                "title": "物理诊断遥测 (F3)",
                "subtitle": "显示 120 Hz 物理步、载荷与侧偏角",
                "value": gs.show_diagnostics,
                "default": "关闭",
                "timing": ("立即生效", theme.PINE),
                "detail": "在屏幕左上侧叠显实时物理步数、前后轴载荷、横向 g 值、横摆角速度与侧偏角，适合调校车辆时观察动力学状态。",
            },
            {
                "id": "pause_on_focus_loss",
                "kind": "toggle",
                "title": "切出窗口自动暂停",
                "subtitle": "游戏窗口退至后台时自动暂停驾驶",
                "value": gs.pause_on_focus_loss,
                "default": "开启",
                "timing": ("立即生效", theme.PINE),
                "detail": "开启后，切到其他窗口时将自动暂停当前驾驶会话，防止车辆无人操控偏离赛道。",
            },
        ]

    def _adjust_row(self, row, direction):
        """对单个设置项执行增量调整、循环切换、开关切换或进入改键。"""
        gs = self.app.game_settings
        au = self.app.audio_settings
        item_id = row["id"]
        if row.get("disabled"):
            self.feedback_notice = "驾驶辅助开关需返回主菜单后修改，以免影响当前车辆物理配置。"
            self.redraw()
            return
        self.feedback_notice = ""

        if item_id == "window_mode":
            idx = (WINDOW_MODES.index(gs.window_mode) + direction) % len(WINDOW_MODES)
            gs.window_mode = WINDOW_MODES[idx]
            gs.save()
            self.app.apply_display_settings()
        elif item_id == "resolution":
            idx = RESOLUTIONS.index(gs.resolution) if gs.resolution in RESOLUTIONS else 0
            gs.resolution = RESOLUTIONS[(idx + direction) % len(RESOLUTIONS)]
            gs.save()
            self.app.apply_display_settings()
        elif item_id == "vsync":
            gs.vsync = not gs.vsync
            gs.save()
            self.restart_needed = True
            self.app.apply_frame_pacing()
        elif item_id == "fps_limit":
            idx = (FPS_LIMITS.index(gs.fps_limit) + direction) % len(FPS_LIMITS)
            gs.fps_limit = FPS_LIMITS[idx]
            gs.save()
            self.app.apply_frame_pacing()
        elif item_id == "graphics_preset":
            keys = tuple(GRAPHICS_PRESETS)
            cur = gs.graphics_preset
            idx = (keys.index(cur) + direction) % len(keys) if cur in keys else 2
            prev_msaa = gs.msaa_samples
            gs.apply_graphics_preset(keys[idx])
            if gs.msaa_samples != prev_msaa:
                self.restart_needed = True
            self.app.apply_graphics_settings()
        elif item_id == "shadow_quality":
            idx = (SHADOW_QUALITIES.index(gs.shadow_quality) + direction) % len(SHADOW_QUALITIES)
            gs.shadow_quality = SHADOW_QUALITIES[idx]
            gs.save()
            self.app.apply_graphics_settings()
        elif item_id == "msaa_samples":
            idx = (MSAA_OPTIONS.index(gs.msaa_samples) + direction) % len(MSAA_OPTIONS)
            gs.msaa_samples = MSAA_OPTIONS[idx]
            gs.save()
            self.restart_needed = True
        elif item_id == "view_distance":
            idx = (VIEW_DISTANCES.index(gs.view_distance) + direction) % len(VIEW_DISTANCES)
            gs.view_distance = VIEW_DISTANCES[idx]
            gs.save()
            self.app.apply_graphics_settings()
        elif item_id == "exposure":
            gs.exposure = max(80, min(120, gs.exposure + direction * 5))
            gs.save()
            self.app.apply_graphics_settings()
        elif item_id == "fov":
            gs.fov = max(60, min(82, gs.fov + direction * 2))
            gs.save()
            self.app.apply_camera_settings()
        elif item_id == "dynamic_fov":
            gs.dynamic_fov = not gs.dynamic_fov
            gs.save()
            self.app.apply_camera_settings()
        elif item_id in ("master_volume", "effects_volume", "engine_volume", "music_volume", "ui_volume"):
            step = direction * 10
            field_map = {
                "master_volume": "master",
                "effects_volume": "effects",
                "engine_volume": "engine",
                "music_volume": "music",
                "ui_volume": "ui",
            }
            self.app.adjust_audio_volume(field_map[item_id], step)
            return
        elif item_id == "radio_station":
            self.app.cycle_radio(direction)
            return
        elif item_id == "mute_unfocused":
            au.save(
                au.master_volume,
                au.effects_volume,
                au.music_volume,
                au.radio_station,
                engine_volume=au.engine_volume,
                ui_volume=au.ui_volume,
                mute_unfocused=not au.mute_unfocused,
            )
            self.app.apply_audio_settings()
        elif item_id == "key_preset":
            keys = tuple(KEY_PRESETS)
            cur = gs.key_preset
            idx = (keys.index(cur) + direction) % len(keys) if cur in keys else 0
            gs.apply_key_preset(keys[idx])
            self.app.apply_control_settings()
            self.feedback_notice = f"已套用“{KEY_PRESET_LABELS[keys[idx]]}”键位方案。"
        elif item_id.startswith("bind:"):
            self.listening_action = row["action"]
            self.feedback_notice = f"请按下“{row['title']}”的新按键（按 Esc 取消）"
        elif item_id == "abs":
            self.app.toggle_abs()
            return
        elif item_id == "tcs":
            self.app.toggle_tcs()
            return
        elif item_id == "esc":
            self.app.toggle_esc()
            return
        elif item_id == "camera_distance":
            idx = (CAMERA_DISTANCES.index(gs.camera_distance) + direction) % len(CAMERA_DISTANCES)
            gs.camera_distance = CAMERA_DISTANCES[idx]
            gs.save()
            self.app.apply_camera_settings()
        elif item_id == "speed_unit":
            idx = (SPEED_UNITS.index(gs.speed_unit) + direction) % len(SPEED_UNITS)
            gs.speed_unit = SPEED_UNITS[idx]
            gs.save()
            self.app.apply_hud_settings()
        elif item_id == "show_key_hints":
            gs.show_key_hints = not gs.show_key_hints
            gs.save()
            self.app.apply_hud_settings()
        elif item_id == "ghost_default":
            gs.ghost_default = not gs.ghost_default
            gs.save()
            self.app.ghost_enabled = gs.ghost_default
            self.app.refresh_ghost_button()
        elif item_id == "show_diagnostics":
            gs.show_diagnostics = not gs.show_diagnostics
            gs.save()
            self.app.apply_hud_settings()
        elif item_id == "pause_on_focus_loss":
            gs.pause_on_focus_loss = not gs.pause_on_focus_loss
            gs.save()
        self.app.audio_cue("confirm")
        self.redraw()

    def reset_current_category(self):
        """恢复当前一级分类的全部默认值，不影响其他分类。"""
        self.listening_action = None
        if self.category == "audio":
            self.app.audio_settings.reset_defaults()
            self.app.apply_audio_settings()
            self.feedback_notice = "已恢复“声音设置”默认音量与电台。"
        elif self.category == "controls":
            self.app.game_settings.reset_category("controls")
            self.app.apply_control_settings()
            if self.app.session.phase == Phase.MENU:
                self.app.session.set_abs_enabled(True)
                self.app.session.set_tcs_enabled(True)
                self.app.session.set_esc_enabled(True)
                self.app.driving_mode_settings.save(self.app.session.driving_mode, True, True, True)
                self.app.save_workspace_electronics()
            self.feedback_notice = "已恢复“操作设置”默认键位" + ("与驾驶辅助。" if self.app.session.phase == Phase.MENU else "。")
        elif self.category == "graphics":
            prev_msaa, prev_vsync = self.app.game_settings.msaa_samples, self.app.game_settings.vsync
            self.app.game_settings.reset_category("graphics")
            if self.app.game_settings.msaa_samples != prev_msaa or self.app.game_settings.vsync != prev_vsync:
                self.restart_needed = True
            self.app.apply_display_settings()
            self.app.apply_frame_pacing()
            self.app.apply_graphics_settings()
            self.app.apply_camera_settings()
            self.feedback_notice = "已恢复“画面设置”默认参数。"
        else:
            self.app.game_settings.reset_category("gameplay")
            self.app.ghost_enabled = self.app.game_settings.ghost_default
            self.app.apply_camera_settings()
            self.app.apply_hud_settings()
            self.feedback_notice = "已恢复“游戏与界面”默认设置。"
        self.app.audio_cue("confirm")
        self.redraw()

    def handle_key(self, key):
        """统一处理键盘与手柄导航，以及改键捕获。"""
        if self.listening_action is not None:
            action = self.listening_action
            if key == "escape":
                self.listening_action = None
                self.feedback_notice = "已取消改键。"
                self.app.audio_cue("select")
                self.redraw()
                return True
            ok, swapped = self.app.game_settings.rebind_key(action, key)
            if not ok:
                self.feedback_notice = f"“{key_label(key)}”为系统保留键或不可绑定，请换一个按键。"
                self.app.audio_cue("select")
                self.redraw()
                return True
            self.listening_action = None
            self.app.apply_control_settings()
            if swapped is not None:
                self.feedback_notice = (
                    f"已绑定 {key_label(key)}；与“{ACTION_TITLES[swapped]}”冲突，已自动互换。"
                )
            else:
                self.feedback_notice = f"已将“{ACTION_TITLES[action]}”绑定为 {key_label(key)}。"
            self.app.audio_cue("confirm")
            self.redraw()
            return True

        if key == "escape":
            self.app.audio_cue("select")
            self.app.back_from_audio_settings()
            return True
        if key == "q":
            self.cycle_category(-1)
            return True
        if key == "e":
            self.cycle_category(1)
            return True
        if key == "tab":
            self.select_subsection(self.subsections[self.category] + 1)
            return True
        if not self._row_specs:
            return True
        if key in ("arrow_up", "w"):
            self.selected = (self.selected - 1) % len(self._row_specs)
            self.app.audio_cue("select")
            self.redraw()
            return True
        if key in ("arrow_down", "s"):
            self.selected = (self.selected + 1) % len(self._row_specs)
            self.app.audio_cue("select")
            self.redraw()
            return True
        if key in ("arrow_left", "a"):
            row = self._row_specs[self.selected]
            if row["kind"] in ("slider", "cycle", "toggle"):
                self._adjust_row(row, -1)
            return True
        if key in ("arrow_right", "d"):
            row = self._row_specs[self.selected]
            if row["kind"] in ("slider", "cycle", "toggle"):
                self._adjust_row(row, 1)
            return True
        if key == "enter":
            row = self._row_specs[self.selected]
            self._adjust_row(row, 1)
            return True
        return False

    def _select_row(self, index):
        if index != self.selected and 0 <= index < len(self._row_specs):
            self.selected = index
            self.redraw()

    def redraw(self):
        if not self.visible:
            return
        self._clear()
        app = self.app
        aspect = self._aspect = app.getAspectRatio()
        width, unit = 941.0 * aspect, 2.0 / 941.0
        rows = self._row_specs = self._current_rows()
        if rows:
            self.selected %= len(rows)
        else:
            self.selected = 0

        def point(x, y):
            return (x - width / 2.0) * unit, 1.0 - y * unit

        def box(x, y, w, h):
            a, b = point(x, y + h), point(x + w, y)
            return a[0], b[0], a[1], b[1]

        def fill(x, y, w, h, color, radius=6, parent=None):
            node = rounded_panel(self.content if parent is None else parent, "settings-fill",
                                 box(x, y, w, h), color, radius * unit)
            node.setTransparency(TransparencyAttrib.MAlpha)
            return node

        def pic(name, x, y, w, h, *, color=(1, 1, 1, 1), sort_order=0, parent=None):
            frame = atelier.picture(
                self.content if parent is None else parent, app.loader, name,
                box(x, y, w, h), color=color, sort_order=sort_order)
            self._widgets.append(frame)
            return frame

        def label(text, x, y, size, color=WHITE, *, bold=False, display=False, right=False, center=False, parent=None):
            font = app.display_font if display else app.ui_font if bold else app.main_menu.regular
            align = TextNode.ARight if right else TextNode.ACenter if center else TextNode.ALeft
            node = OnscreenText(
                parent=self.content if parent is None else parent,
                text=text, font=font, fg=color, align=align,
                pos=point(x, y), scale=size * unit, mayChange=True,
            )
            self._widgets.append(node)
            return node

        def make_btn(text, x, y, w, h, command, *, tex_name="atelier/btn-ghost.png",
                     fg=WHITE, size=17, bold=False, align=TextNode.ACenter, text_offset=(0, -6),
                     hover_cb=None):
            px, pz = point(x + w / 2.0, y + h / 2.0)
            tex = atelier.tex(app.loader, tex_name) if tex_name else None
            btn = DirectButton(
                parent=self.content, text=text,
                text_font=app.ui_font if bold else app.main_menu.regular,
                text_fg=fg, text_scale=size * unit, text_align=align,
                text_pos=(text_offset[0] * unit, text_offset[1] * unit),
                pos=(px, 0, pz),
                frameSize=(-w * unit / 2.0, w * unit / 2.0, -h * unit / 2.0, h * unit / 2.0),
                frameTexture=tex, frameColor=(1, 1, 1, 1) if tex else (0, 0, 0, 0),
                relief=DGG.FLAT, pressEffect=False, command=command,
            )
            btn.setTransparency(TransparencyAttrib.MAlpha)
            if hover_cb is not None:
                btn.bind(DGG.ENTER, lambda _e: hover_cb())
            self._widgets.append(btn)
            return btn

        # ── 落日工坊柔暗背景 + 顶底通栏 ──
        bg = DirectFrame(
            parent=self.content, frameSize=(-aspect, aspect, -1, 1),
            frameColor=(0.30, 0.28, 0.32, 1),
            frameTexture=atelier.tex(app.loader, atelier.SUNSET_GARAGE_BG),
            sortOrder=-10, state=DGG.DISABLED,
        )
        tex = bg["frameTexture"]
        ratio = aspect / (tex.getXSize() / tex.getYSize())
        bg.setTexScale(TextureStage.getDefault(), min(1, ratio), min(1, 1 / ratio))
        bg.setTexOffset(TextureStage.getDefault(), max(0, (1 - ratio) / 2), max(0, (1 - 1 / ratio) / 2))
        self._widgets.append(bg)
        gradient_panel(self.content, "settings-bg-scrim", (-aspect, aspect, -1, 1),
                       (0.035, 0.044, 0.066, 0.90), (0.035, 0.044, 0.066, 0.74))
        pic("atelier/bar-top.png", 0, 0, width, 72)
        pic("atelier/footer-surface.png", 0, 858, width, 83)

        margin = max(24.0, width * 0.026)
        gap = 18.0
        cat_info = next(item for item in CATEGORIES if item[0] == self.category)
        sub_list = SUBSECTIONS[self.category]
        active_sub_idx = self.subsections[self.category]
        active_sub_label = sub_list[active_sub_idx][1]

        # ── 顶栏：标识 + 面包屑 + 上下文徽标 ──
        wm = atelier.wordmark(self.content, app.loader, box(margin, 15, 212, 40))
        self._widgets.append(wm)
        fill(margin + 228, 21, 1.5, 28, (0.34, 0.40, 0.50, 0.85), 0)
        label("游戏设置", margin + 246, 44, 20, WHITE, bold=True)
        fill(margin + 246, 67, 82, 3, theme.AMBER, 1.5)
        if aspect > 1.45:
            label(f"设置   ›   {cat_info[1]}   ›   {active_sub_label}",
                  margin + 362, 43, 15.5, theme.DARK_SUB)
        ctx_text = "主菜单" if app.session.phase == Phase.MENU else "驾驶已暂停"
        ctx_w = 138.0
        pic("atelier/btn-ghost.png", width - margin - ctx_w, 15, ctx_w, 42)
        label(ctx_text, width - margin - ctx_w / 2.0, 42, 16, theme.AMBER, bold=True, center=True)

        # ── 三栏主区几何计算（严格适配 16:9 与 4:3）──
        body_y, body_h = 90.0, 752.0
        rail_w = 248.0 if aspect > 1.5 else 210.0
        rem = width - 2 * margin - rail_w - 2 * gap
        center_w = rem * (0.64 if aspect > 1.5 else 0.63)
        insp_w = rem - center_w
        rail_x = margin
        center_x = rail_x + rail_w + gap
        insp_x = center_x + center_w + gap

        # ── Col 1: 一级大类导航侧栏 ──
        pic("atelier/panel-obsidian.png", rail_x - 8, body_y - 4, rail_w + 16, body_h + 8)
        fill(rail_x + 12, body_y + 24, 4, 24, theme.AMBER, 2)
        label("设置分类", rail_x + 26, body_y + 44, 19, WHITE, bold=True)
        fill(rail_x + 12, body_y + 62, rail_w - 24, 1, (0.20, 0.25, 0.33, 0.85), 0)

        for idx, (cat_id, title, sub, icon_name) in enumerate(CATEGORIES):
            cy = body_y + 82 + idx * 102
            active = cat_id == self.category
            make_btn(
                "", rail_x + 12, cy, rail_w - 24, 88,
                command=lambda cid=cat_id: self.select_category(cid),
                tex_name="atelier/card-active.png" if active else "atelier/card-idle.png",
            )
            if active:
                fill(rail_x + 14, cy + 16, 4, 56, theme.AMBER, 2)
            pic(icon_name, rail_x + 28, cy + 28, 28, 28,
                color=theme.AMBER if active else (0.76, 0.82, 0.90, 0.95))
            label(title, rail_x + 68, cy + 38, 19, theme.AMBER if active else WHITE, bold=True)
            label(sub, rail_x + 68, cy + 64, 13, theme.DARK_SUB)

        # 左栏底部快捷导航提示卡
        tip_y = body_y + body_h - 140
        fill(rail_x + 14, tip_y, rail_w - 28, 120, (0.052, 0.066, 0.092, 0.86), 8)
        label("快捷切换", rail_x + 28, tip_y + 28, 14, theme.AMBER, bold=True)
        label("Q / E   切换一级大类", rail_x + 28, tip_y + 56, 13.5, theme.DARK_SUB)
        label("Tab     切换二级子页", rail_x + 28, tip_y + 80, 13.5, theme.DARK_SUB)
        label("← / →   实时调节选项", rail_x + 28, tip_y + 104, 13.5, theme.DARK_SUB)

        # ── Col 2: 二级子分页 + 设置项主表 ──
        pic("atelier/panel-obsidian.png", center_x - 8, body_y - 4, center_w + 16, body_h + 8)
        fill(center_x + 16, body_y + 24, 4, 34, theme.AMBER, 2)
        label(cat_info[1], center_x + 32, body_y + 49, 28, WHITE, bold=True)
        label(cat_info[2], center_x + center_w - 22, body_y + 47, 15, theme.DARK_SUB, right=True)

        # 二级子分页标签条
        tab_y = body_y + 72
        tab_gap = 10.0
        tab_w = min(186.0, (center_w - 36 - tab_gap * (len(sub_list) - 1)) / max(1, len(sub_list)))
        for s_idx, (_sid, s_title) in enumerate(sub_list):
            tx = center_x + 18 + s_idx * (tab_w + tab_gap)
            is_cur = s_idx == active_sub_idx
            make_btn(
                s_title, tx, tab_y, tab_w, 40,
                command=lambda si=s_idx: self.select_subsection(si),
                tex_name="atelier/card-active.png" if is_cur else "atelier/btn-ghost.png",
                fg=theme.AMBER if is_cur else (0.78, 0.83, 0.90, 1),
                size=15.5, bold=is_cur, text_offset=(0, -5),
            )
            if is_cur:
                fill(tx + 12, tab_y + 37, tab_w - 24, 3, theme.AMBER, 1.5)
        fill(center_x + 16, tab_y + 52, center_w - 32, 1, (0.20, 0.25, 0.33, 0.85), 0)

        # 设置项列表（最多 5 行，每行 104px + 12px 间距）
        row_x = center_x + 18
        row_w = center_w - 36
        row_h = 102.0
        row_gap = 12.0
        ctrl_w = min(312.0, row_w * 0.44)
        ctrl_x = row_x + row_w - ctrl_w - 16

        for r_idx, row in enumerate(rows):
            ry = tab_y + 68 + r_idx * (row_h + row_gap)
            focused = r_idx == self.selected
            disabled = bool(row.get("disabled"))
            is_listening = row["kind"] == "keybind" and self.listening_action == row["action"]

            # 整行可点击聚焦（对于 toggle/keybind 点行本身即可直接交互）
            row_cmd = (
                (lambda r=row, i=r_idx: (setattr(self, "selected", i), self._adjust_row(r, 1)))
                if row["kind"] in ("toggle", "keybind")
                else (lambda i=r_idx: self._select_row(i))
            )
            make_btn(
                "", row_x, ry, row_w, row_h, command=row_cmd,
                tex_name="atelier/card-active.png" if (focused or is_listening) else "atelier/card-idle.png",
                hover_cb=lambda i=r_idx: self._select_row(i),
            )
            if focused or is_listening:
                fill(row_x + 3, ry + 16, 4, row_h - 32, theme.AMBER, 2)

            title_col = theme.DARK_LOCKED if disabled else (theme.AMBER if focused else WHITE)
            label(row["title"], row_x + 20, ry + 42, 19.5, title_col, bold=True)
            label(row["subtitle"], row_x + 20, ry + 72, 13.5,
                  theme.DARK_LOCKED if disabled else theme.DARK_SUB)

            # 右侧对应交互控件
            kind = row["kind"]
            if kind == "slider":
                val = row["value"]
                lo, hi = row["min"], row["max"]
                frac = 0.0 if hi <= lo else (val - lo) / (hi - lo)
                unit_str = row.get("unit", "")
                val_text = f"{val}{unit_str}"
                label(val_text, ctrl_x + ctrl_w, ry + 38, 22,
                      theme.AMBER if focused or val > lo else theme.DARK_SUB,
                      bold=True, right=True, display=True)
                btn_w = 42.0
                track_x = ctrl_x + btn_w + 10
                track_w = ctrl_w - 2 * btn_w - 20
                fill(track_x, ry + 64, track_w, 8, (0.14, 0.17, 0.23, 0.96), 4)
                if frac > 0:
                    fill(track_x, ry + 64, max(8.0, track_w * frac), 8,
                         theme.AMBER_BRIGHT if focused else theme.AMBER, 4)
                make_btn(
                    "−", ctrl_x, ry + 48, btn_w, 38,
                    command=lambda r=row, i=r_idx: (setattr(self, "selected", i), self._adjust_row(r, -1)),
                    tex_name="atelier/btn-ghost-hover.png" if focused else "atelier/btn-ghost.png",
                    fg=WHITE, size=20, bold=True, text_offset=(0, -6),
                )
                make_btn(
                    "+", ctrl_x + ctrl_w - btn_w, ry + 48, btn_w, 38,
                    command=lambda r=row, i=r_idx: (setattr(self, "selected", i), self._adjust_row(r, 1)),
                    tex_name="atelier/btn-ghost-hover.png" if focused else "atelier/btn-ghost.png",
                    fg=WHITE, size=20, bold=True, text_offset=(0, -6),
                )
            elif kind == "cycle":
                btn_w = 42.0
                mid_x = ctrl_x + ctrl_w / 2.0
                make_btn(
                    "‹", ctrl_x, ry + 26, btn_w, 44,
                    command=lambda r=row, i=r_idx: (setattr(self, "selected", i), self._adjust_row(r, -1)),
                    tex_name="atelier/btn-ghost-hover.png" if focused else "atelier/btn-ghost.png",
                    fg=theme.AMBER if focused else WHITE, size=22, bold=True, text_offset=(0, -7),
                )
                make_btn(
                    "›", ctrl_x + ctrl_w - btn_w, ry + 26, btn_w, 44,
                    command=lambda r=row, i=r_idx: (setattr(self, "selected", i), self._adjust_row(r, 1)),
                    tex_name="atelier/btn-ghost-hover.png" if focused else "atelier/btn-ghost.png",
                    fg=theme.AMBER if focused else WHITE, size=22, bold=True, text_offset=(0, -7),
                )
                val_str = str(row["value"])
                val_size = 17.5 if len(val_str) <= 10 else 14.5
                label(val_str, mid_x, ry + 54, val_size,
                      theme.AMBER if focused else WHITE, bold=True, center=True)
                dots = row.get("dots")
                if dots and dots[1] > 1:
                    cur_dot, total_dots = dots
                    dot_w = min(22.0, (ctrl_w - 110.0) / total_dots - 6.0)
                    span = total_dots * dot_w + (total_dots - 1) * 6.0
                    dx0 = mid_x - span / 2.0
                    for d_i in range(total_dots):
                        fill(dx0 + d_i * (dot_w + 6.0), ry + 78, dot_w, 4,
                             theme.AMBER if d_i == cur_dot else (0.24, 0.29, 0.38, 0.85), 2)
            elif kind == "toggle":
                enabled = bool(row["value"])
                pw, ph = 124.0, 44.0
                px = ctrl_x + ctrl_w - pw
                py = ry + (row_h - ph) / 2.0
                bg_col = (
                    (0.24, 0.27, 0.32, 0.72) if disabled else
                    (theme.AMBER_BRIGHT if focused else theme.AMBER) if enabled else
                    (theme.CHARCOAL_SOFT if focused else (0.17, 0.20, 0.26, 1))
                )
                fill(px - 1.5, py - 1.5, pw + 3, ph + 3,
                     theme.AMBER if focused and not disabled else theme.CARBON_EDGE, ph / 2.0 + 1.5)
                fill(px, py, pw, ph, bg_col, ph / 2.0)
                knob_x = (px + pw - ph + 5) if enabled else (px + 5)
                fill(knob_x, py + 5, ph - 10, ph - 10,
                     theme.INK if enabled and not disabled else WHITE, (ph - 10) / 2.0)
                label("开启" if enabled else "关闭",
                      px + (42 if enabled else pw - 42), py + 29, 16.5,
                      theme.DARK_LOCKED if disabled else (theme.INK if enabled else WHITE),
                      bold=True, center=True)
            elif kind == "keybind":
                kw, kh = 148.0, 46.0
                kx = ctrl_x + ctrl_w - kw
                ky = ry + (row_h - kh) / 2.0
                cap_text = "按下新键…" if is_listening else key_label(row["value"])
                make_btn(
                    cap_text, kx, ky, kw, kh,
                    command=lambda r=row, i=r_idx: (setattr(self, "selected", i), self._adjust_row(r, 1)),
                    tex_name="atelier/btn-primary.png" if is_listening else (
                        "atelier/card-active.png" if focused else "atelier/btn-ghost.png"),
                    fg=theme.INK if is_listening else (theme.AMBER if focused else WHITE),
                    size=17 if is_listening else 18.5, bold=True, text_offset=(0, -6),
                )

        # ── Col 3: 右侧上下文详情检视面板 ──
        pic("atelier/panel-obsidian.png", insp_x - 8, body_y - 4, insp_w + 16, body_h + 8)
        fill(insp_x + 16, body_y + 24, 4, 24, theme.AMBER, 2)
        label("选项说明", insp_x + 30, body_y + 44, 19, WHITE, bold=True)
        fill(insp_x + 16, body_y + 62, insp_w - 32, 1, (0.20, 0.25, 0.33, 0.85), 0)

        if rows:
            cur_row = rows[self.selected]
            badge_text, badge_col = cur_row["timing"]
            bw = max(106.0, len(badge_text) * 16.0 + 24.0)
            fill(insp_x + 18, body_y + 82, bw, 30, (0.11, 0.14, 0.20, 0.96), 6)
            fill(insp_x + 18, body_y + 82, 4, 30, badge_col, 2)
            label(badge_text, insp_x + 30, body_y + 103, 14, badge_col, bold=True)

            label(cur_row["title"], insp_x + 18, body_y + 150, 23, WHITE, bold=True)
            fill(insp_x + 18, body_y + 168, 56, 3, theme.AMBER, 1.5)
            desc = app.fit_lines(cur_row["detail"], (insp_w - 40) * unit, 15.5 * unit, 6)
            label(desc, insp_x + 18, body_y + 202, 15.5, (0.80, 0.85, 0.92, 1))

            # 当前值 vs 出厂默认对照盒
            cmp_y = body_y + 388
            fill(insp_x + 16, cmp_y, insp_w - 32, 112, (0.055, 0.070, 0.098, 0.88), 8)
            cur_val_disp = (
                ("开启" if cur_row["value"] else "关闭") if cur_row["kind"] == "toggle" else
                key_label(cur_row["value"]) if cur_row["kind"] == "keybind" else
                f"{cur_row['value']}{cur_row.get('unit', '')}" if cur_row["kind"] == "slider" else
                str(cur_row["value"])
            )
            label("当前设定", insp_x + 30, cmp_y + 34, 14, theme.DARK_SUB)
            label(cur_val_disp, insp_x + insp_w - 30, cmp_y + 36, 17, theme.AMBER, bold=True, right=True)
            fill(insp_x + 28, cmp_y + 56, insp_w - 56, 1, (0.20, 0.25, 0.33, 0.72), 0)
            label("出厂默认", insp_x + 30, cmp_y + 88, 14, theme.DARK_SUB)
            label(str(cur_row["default"]), insp_x + insp_w - 30, cmp_y + 90, 16, WHITE, right=True)

        # 右栏底部：按当前大类展示实时环境/电台/键位摘要
        status_y = body_y + 522
        fill(insp_x + 16, status_y, insp_w - 32, 150, (0.055, 0.070, 0.098, 0.88), 8)
        fill(insp_x + 16, status_y + 18, 4, 24, theme.STEEL_TEXT, 2)
        gs, au = app.game_settings, app.audio_settings
        if self.category == "graphics":
            label("当前渲染概览", insp_x + 30, status_y + 36, 15.5, theme.STEEL_TEXT, bold=True)
            label(f"窗口：{WINDOW_MODE_LABELS[gs.window_mode]} · {gs.resolution[0]}×{gs.resolution[1]}",
                  insp_x + 30, status_y + 68, 14.5, WHITE)
            label(f"画质：{PRESET_LABELS[gs.graphics_preset]} · 阴影 {SHADOW_LABELS[gs.shadow_quality]}",
                  insp_x + 30, status_y + 94, 14, theme.DARK_SUB)
            label(f"视野：{gs.fov}°{' +动态' if gs.dynamic_fov else ''} · MSAA {gs.msaa_samples}×",
                  insp_x + 30, status_y + 120, 14, theme.DARK_SUB)
        elif self.category == "audio":
            label("电台实时试听", insp_x + 30, status_y + 36, 15.5, theme.AMBER, bold=True)
            st_name, _, song = STATIONS[au.radio_station].partition(" · ")
            label(st_name, insp_x + 30, status_y + 70, 19, WHITE, bold=True)
            label(song or "当前已关闭车载音乐", insp_x + 30, status_y + 98, 14, theme.DARK_SUB)
            label(f"总 {au.master_volume}% · 效果 {au.effects_volume}% · 音乐 {au.music_volume}%",
                  insp_x + 30, status_y + 126, 13.5, theme.STEEL_TEXT)
        elif self.category == "controls":
            kb = gs.key_bindings
            label("当前键位摘要", insp_x + 30, status_y + 36, 15.5, theme.STEEL_TEXT, bold=True)
            label(f"驾驶：{key_label(kb['throttle'])} / {key_label(kb['brake'])} / {key_label(kb['steer_left'])} / {key_label(kb['steer_right'])}",
                  insp_x + 30, status_y + 68, 15, WHITE, bold=True)
            label(f"视角 {key_label(kb['camera'])} · 复位 {key_label(kb['reset'])} · 电台 {key_label(kb['radio_next'])}/{key_label(kb['radio_mute'])}",
                  insp_x + 30, status_y + 96, 14, theme.DARK_SUB)
            assists_str = " / ".join(
                name for name, on in (
                    ("ABS", app.session.abs_enabled),
                    ("TCS", app.session.tcs_enabled),
                    ("ESC", app.session.esc_enabled),
                ) if on
            ) or "全部关闭"
            label(f"辅助开启：{assists_str}", insp_x + 30, status_y + 124, 14, theme.AMBER)
        else:
            label("驾驶体验摘要", insp_x + 30, status_y + 36, 15.5, theme.STEEL_TEXT, bold=True)
            label(f"追车距离：{gs.camera_distance:g} m（高度 3.2 m）",
                  insp_x + 30, status_y + 68, 14.5, WHITE)
            label(f"速度表：{'km/h 公制' if gs.speed_unit == 'kmh' else 'mph 英制'} · 提示栏{'开启' if gs.show_key_hints else '隐藏'}",
                  insp_x + 30, status_y + 96, 14, theme.DARK_SUB)
            label(f"幽灵车{'开启' if gs.ghost_default else '关闭'} · 失焦暂停{'开启' if gs.pause_on_focus_loss else '关闭'}",
                  insp_x + 30, status_y + 124, 14, theme.DARK_SUB)

        # 底部状态提示（改键提示 / 保存异常 / 重启提示）
        notice_msg = (
            self.feedback_notice
            or app.audio_settings.notice
            or app.game_settings.notice
            or app.driving_mode_settings.notice
            or ("部分画面更改（垂直同步 / MSAA）将在下次启动后生效。" if self.restart_needed else "")
        )
        if notice_msg:
            wrapped = app.fit_lines(notice_msg, (insp_w - 36) * unit, 14 * unit, 2)
            label(wrapped, insp_x + 18, body_y + 700, 14, theme.AMBER)

        # ── 底部通栏：操作提示 + 恢复默认 + 返回 ──
        hint = (
            "按下目标键盘按键绑定    Esc 取消改键"
            if self.listening_action is not None
            else "Q / E 切换大类    Tab 切换子页    ↑ ↓ 选择    ← → 调整    Enter 确认"
        )
        label(hint, margin, 908, 15.5, theme.DARK_SUB)
        back_label = "Esc  返回首页" if app.session.phase == Phase.MENU else "Esc  返回暂停"
        make_btn(
            "恢复本页默认", width - margin - 368, 878, 168, 44,
            command=self.reset_current_category,
            tex_name="atelier/btn-ghost.png", fg=WHITE, size=16, text_offset=(0, -5),
        )
        make_btn(
            back_label, width - margin - 184, 878, 184, 44,
            command=app.back_from_audio_settings,
            tex_name="atelier/btn-primary.png", fg=theme.INK, size=16.5, bold=True, text_offset=(0, -5),
        )

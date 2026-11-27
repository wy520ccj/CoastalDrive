"""玩家外观、声音、驾驶模式与多层级游戏设置持久化存储。"""

import json

from driving_modes import DrivingMode
from paths import user_data
from skins import PLAYER_VEHICLES, SKINS

# 画质预设映射到具体渲染项；手动改任一子项后预设自动显示为 custom。
GRAPHICS_PRESETS = {
    "low": {"shadow_quality": "off", "msaa_samples": 0, "view_distance": "short"},
    "medium": {"shadow_quality": "medium", "msaa_samples": 2, "view_distance": "medium"},
    "high": {"shadow_quality": "high", "msaa_samples": 4, "view_distance": "far"},
    "ultra": {"shadow_quality": "ultra", "msaa_samples": 8, "view_distance": "ultra"},
}
WINDOW_MODES = ("windowed", "borderless", "fullscreen")
RESOLUTIONS = ((1280, 720), (1600, 900), (1920, 1080), (2560, 1440))
FPS_LIMITS = (0, 60, 90, 120)
SHADOW_QUALITIES = ("off", "medium", "high", "ultra")
SHADOW_MAP_SIZES = {"off": 0, "medium": 1024, "high": 2048, "ultra": 4096}
MSAA_OPTIONS = (0, 2, 4, 8)
VIEW_DISTANCES = ("short", "medium", "far", "ultra")
VIEW_FAR_METERS = {"short": 800.0, "medium": 1150.0, "far": 1500.0, "ultra": 2000.0}
CAMERA_DISTANCES = (11.0, 16.0)
SPEED_UNITS = ("kmh", "mph")

KEY_PRESETS = {
    "wasd": {
        "throttle": "w",
        "brake": "s",
        "steer_left": "a",
        "steer_right": "d",
        "camera": "c",
        "reset": "r",
        "radio_next": "n",
        "radio_mute": "m",
        "ghost": "g",
    },
    "arrows": {
        "throttle": "arrow_up",
        "brake": "arrow_down",
        "steer_left": "arrow_left",
        "steer_right": "arrow_right",
        "camera": "c",
        "reset": "r",
        "radio_next": "n",
        "radio_mute": "m",
        "ghost": "g",
    },
}
KEY_ACTIONS = tuple(KEY_PRESETS["wasd"])
RESERVED_KEYS = frozenset({"escape", "enter", "f2", "f3", "tab"})
BINDABLE_KEYS = frozenset(
    {
        *(chr(code) for code in range(ord("a"), ord("z") + 1)),
        *(str(digit) for digit in range(10)),
        "arrow_up",
        "arrow_down",
        "arrow_left",
        "arrow_right",
        "space",
        "lshift",
        "rshift",
        "lcontrol",
        "rcontrol",
        "q",
        "e",
    }
)

KEY_LABELS = {
    "arrow_up": "↑",
    "arrow_down": "↓",
    "arrow_left": "←",
    "arrow_right": "→",
    "space": "Space",
    "lshift": "L-Shift",
    "rshift": "R-Shift",
    "lcontrol": "L-Ctrl",
    "rcontrol": "R-Ctrl",
}


def key_label(key):
    """格式化 Panda3D 键名为界面键帽显示文本。"""
    if key in KEY_LABELS:
        return KEY_LABELS[key]
    return key.upper() if len(key) == 1 else key.replace("_", " ").title()


class AppearanceStore:
    def __init__(self, path=None):
        self.path = path if path is not None else user_data() / "appearance.json"
        self.model_id = PLAYER_VEHICLES[0].id
        self.skin_id = SKINS[0].id
        self.notice = ""
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return
        except (OSError, ValueError):
            self.notice = "外观设置无法读取，已使用默认外观"
            return
        if not isinstance(data, dict):
            self.notice = "外观设置无效，已使用默认外观"
            return
        model, skin = data.get("model_id"), data.get("skin_id")
        if model in [item.id for item in PLAYER_VEHICLES] and skin in [item.id for item in SKINS]:
            self.model_id, self.skin_id = model, skin
        else:
            self.notice = "原外观已不可用，已使用默认外观"

    def save(self, model_id, skin_id):
        if model_id not in [item.id for item in PLAYER_VEHICLES] or skin_id not in [item.id for item in SKINS]:
            raise ValueError("Unknown garage appearance")
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_suffix(".tmp")
            temporary.write_text(
                json.dumps({"model_id": model_id, "skin_id": skin_id}, indent=2), encoding="utf-8"
            )
            temporary.replace(self.path)
        except OSError:
            self.notice = "外观未能保存，请检查存储空间或目录权限"
            return False
        self.model_id, self.skin_id = model_id, skin_id
        self.notice = ""
        return True


class AudioSettingsStore:
    """主音量、效果、引擎/胎噪、音乐、界面提示音、电台与失焦静音，存入 audio.json。"""

    def __init__(self, path=None):
        self.path = path if path is not None else user_data() / "audio.json"
        self.master_volume = 100
        self.effects_volume = 100
        self.engine_volume = 100
        self.music_volume = 55
        self.ui_volume = 100
        self.radio_station = 1
        self.mute_unfocused = False
        self.notice = ""
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return
        except (OSError, ValueError):
            self.notice = "声音设置损坏，已使用默认音量"
            return
        if not isinstance(data, dict):
            self.notice = "声音设置无效，已使用默认音量"
            return
        values = (data.get("master_volume"), data.get("effects_volume"))
        if any(not isinstance(value, int) or isinstance(value, bool) for value in values):
            self.notice = "声音设置无效，已使用默认音量"
            return
        self.master_volume, self.effects_volume = values
        limited = (max(0, min(100, value)) for value in values)
        self.master_volume, self.effects_volume = limited
        if (self.master_volume, self.effects_volume) != values:
            self.notice = "声音设置超出范围，已限制到 0–100%"
        music = data.get("music_volume", 55)
        station = data.get("radio_station", 1)
        if type(music) is int and type(station) is int and 0 <= station <= 2:
            self.music_volume = max(0, min(100, music))
            self.radio_station = station
        else:
            self.notice = "音乐设置无效，已使用默认电台"
        # 扩展分轨字段在旧 audio.json 中可缺省，保持向上兼容。
        for field_name, default in (("engine_volume", 100), ("ui_volume", 100)):
            raw = data.get(field_name, default)
            if type(raw) is int:
                setattr(self, field_name, max(0, min(100, raw)))
        mute = data.get("mute_unfocused", False)
        if type(mute) is bool:
            self.mute_unfocused = mute

    def save(
        self,
        master_volume,
        effects_volume,
        music_volume=None,
        radio_station=None,
        *,
        engine_volume=None,
        ui_volume=None,
        mute_unfocused=None,
    ):
        self.master_volume = max(0, min(100, int(master_volume)))
        self.effects_volume = max(0, min(100, int(effects_volume)))
        if music_volume is not None:
            self.music_volume = max(0, min(100, int(music_volume)))
        if engine_volume is not None:
            self.engine_volume = max(0, min(100, int(engine_volume)))
        if ui_volume is not None:
            self.ui_volume = max(0, min(100, int(ui_volume)))
        if mute_unfocused is not None:
            self.mute_unfocused = bool(mute_unfocused)
        if radio_station is not None:
            if radio_station not in (0, 1, 2):
                raise ValueError("Unknown radio station")
            self.radio_station = radio_station
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_suffix(".tmp")
            temporary.write_text(
                json.dumps(
                    {
                        "master_volume": self.master_volume,
                        "effects_volume": self.effects_volume,
                        "engine_volume": self.engine_volume,
                        "music_volume": self.music_volume,
                        "ui_volume": self.ui_volume,
                        "radio_station": self.radio_station,
                        "mute_unfocused": self.mute_unfocused,
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            temporary.replace(self.path)
        except OSError:
            self.notice = "声音设置未能保存，请检查存储空间或目录权限"
            return False
        self.notice = ""
        return True

    def reset_defaults(self):
        return self.save(100, 100, 55, 1, engine_volume=100, ui_volume=100, mute_unfocused=False)


class DrivingModeStore:
    """驾驶模式及独立ABS/TCS/ESC开关；损坏文件明确回到默认值并提示。"""

    def __init__(self, path=None):
        self.path = path if path is not None else user_data() / "driving-mode.json"
        self.mode = DrivingMode.GAME
        self.abs_enabled = True
        self.tcs_enabled = True
        self.esc_enabled = True
        self.notice = ""
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return
        except (OSError, ValueError):
            self.notice = "驾驶模式无法读取，已使用正常游戏"
            return
        if not isinstance(data, dict) or data.get("mode") not in {m.value for m in DrivingMode}:
            self.notice = "驾驶模式无效，已使用正常游戏"
            return
        self.mode = DrivingMode(data["mode"])
        enabled = data.get("abs_enabled", True)
        tcs_enabled = data.get("tcs_enabled", True)
        esc_enabled = data.get("esc_enabled", True)
        invalid = []
        if type(enabled) is bool:
            self.abs_enabled = enabled
        else:
            invalid.append("ABS")
        if type(tcs_enabled) is bool:
            self.tcs_enabled = tcs_enabled
        else:
            invalid.append("TCS")
        if type(esc_enabled) is bool:
            self.esc_enabled = esc_enabled
        else:
            invalid.append("ESC")
        if invalid:
            label = "/".join(invalid)
            self.notice = f"{label}设置无效，已启用{label}"

    def save(self, mode, abs_enabled=None, tcs_enabled=None, esc_enabled=None):
        if not isinstance(mode, DrivingMode):
            raise TypeError("Expected DrivingMode")
        abs_enabled = self.abs_enabled if abs_enabled is None else abs_enabled
        tcs_enabled = self.tcs_enabled if tcs_enabled is None else tcs_enabled
        esc_enabled = self.esc_enabled if esc_enabled is None else esc_enabled
        if any(type(value) is not bool for value in (abs_enabled, tcs_enabled, esc_enabled)):
            raise TypeError("ABS/TCS/ESC开关须为bool")
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_suffix(".tmp")
            temporary.write_text(json.dumps({
                "mode": mode.value,
                "abs_enabled": abs_enabled,
                "tcs_enabled": tcs_enabled,
                "esc_enabled": esc_enabled,
            }, indent=2), encoding="utf-8")
            temporary.replace(self.path)
        except OSError:
            self.notice = "驾驶模式未能保存，请检查存储空间或目录权限"
            return False
        self.mode = mode
        self.abs_enabled = abs_enabled
        self.tcs_enabled = tcs_enabled
        self.esc_enabled = esc_enabled
        self.notice = ""
        return True


class GameSettingsStore:
    """画面、操作键位与游戏界面多层级设置，存入 game-settings.json。"""

    def __init__(self, path=None):
        self.path = path if path is not None else user_data() / "game-settings.json"
        self.notice = ""
        self._load_defaults()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return
        except (OSError, ValueError):
            self.notice = "游戏设置损坏，已使用默认设置"
            return
        if not isinstance(data, dict):
            self.notice = "游戏设置无效，已使用默认设置"
            return
        self._parse(data)

    def _load_defaults(self):
        # 画面设置默认保持项目认可的 1280×720、2048 阴影、4× MSAA、68° 视野。
        self.window_mode = "windowed"
        self.resolution = (1280, 720)
        self.vsync = True
        self.fps_limit = 90
        self.shadow_quality = "high"
        self.msaa_samples = 4
        self.view_distance = "far"
        self.exposure = 100
        self.fov = 68
        self.dynamic_fov = True
        # 操作键位默认保持标准 WASD 与既有快捷键。
        self.key_bindings = dict(KEY_PRESETS["wasd"])
        # 游戏与界面设置默认保持 11m 追车距离、km/h、开启按键提示与失焦暂停。
        self.camera_distance = 11.0
        self.speed_unit = "kmh"
        self.show_key_hints = True
        self.ghost_default = True
        self.show_diagnostics = False
        self.pause_on_focus_loss = True

    def _parse(self, data):
        invalid = False
        if data.get("window_mode") in WINDOW_MODES:
            self.window_mode = data["window_mode"]
        elif "window_mode" in data:
            invalid = True
        raw_res = data.get("resolution")
        if (isinstance(raw_res, (list, tuple)) and len(raw_res) == 2
                and all(type(v) is int and 640 <= v <= 7680 for v in raw_res)):
            self.resolution = (raw_res[0], raw_res[1])
        elif "resolution" in data:
            invalid = True
        if type(data.get("vsync")) is bool:
            self.vsync = data["vsync"]
        elif "vsync" in data:
            invalid = True
        if type(data.get("fps_limit")) is int and data["fps_limit"] in FPS_LIMITS:
            self.fps_limit = data["fps_limit"]
        elif "fps_limit" in data:
            invalid = True
        if data.get("shadow_quality") in SHADOW_QUALITIES:
            self.shadow_quality = data["shadow_quality"]
        elif "shadow_quality" in data:
            invalid = True
        if type(data.get("msaa_samples")) is int and data["msaa_samples"] in MSAA_OPTIONS:
            self.msaa_samples = data["msaa_samples"]
        elif "msaa_samples" in data:
            invalid = True
        if data.get("view_distance") in VIEW_DISTANCES:
            self.view_distance = data["view_distance"]
        elif "view_distance" in data:
            invalid = True
        if type(data.get("exposure")) is int:
            self.exposure = max(80, min(120, data["exposure"]))
        elif "exposure" in data:
            invalid = True
        if type(data.get("fov")) is int:
            self.fov = max(60, min(82, data["fov"]))
        elif "fov" in data:
            invalid = True
        if type(data.get("dynamic_fov")) is bool:
            self.dynamic_fov = data["dynamic_fov"]
        elif "dynamic_fov" in data:
            invalid = True
        raw_keys = data.get("key_bindings")
        if isinstance(raw_keys, dict):
            parsed = dict(self.key_bindings)
            used = set()
            valid_map = True
            for action in KEY_ACTIONS:
                key = raw_keys.get(action, parsed[action])
                if not isinstance(key, str) or key not in BINDABLE_KEYS or key in RESERVED_KEYS or key in used:
                    valid_map = False
                    break
                parsed[action] = key
                used.add(key)
            if valid_map:
                self.key_bindings = parsed
            else:
                invalid = True
        elif "key_bindings" in data:
            invalid = True
        raw_cam = data.get("camera_distance")
        if isinstance(raw_cam, (int, float)) and not isinstance(raw_cam, bool) and float(raw_cam) in CAMERA_DISTANCES:
            self.camera_distance = float(raw_cam)
        elif "camera_distance" in data:
            invalid = True
        if data.get("speed_unit") in SPEED_UNITS:
            self.speed_unit = data["speed_unit"]
        elif "speed_unit" in data:
            invalid = True
        for field_name in ("show_key_hints", "ghost_default", "show_diagnostics", "pause_on_focus_loss"):
            if type(data.get(field_name)) is bool:
                setattr(self, field_name, data[field_name])
            elif field_name in data:
                invalid = True
        if invalid:
            self.notice = "部分游戏设置无效，已恢复为默认值"

    @property
    def graphics_preset(self):
        current = {
            "shadow_quality": self.shadow_quality,
            "msaa_samples": self.msaa_samples,
            "view_distance": self.view_distance,
        }
        for name, spec in GRAPHICS_PRESETS.items():
            if spec == current:
                return name
        return "custom"

    @property
    def key_preset(self):
        for name, mapping in KEY_PRESETS.items():
            if self.key_bindings == mapping:
                return name
        return "custom"

    @property
    def shadow_map_size(self):
        return SHADOW_MAP_SIZES[self.shadow_quality]

    @property
    def far_distance(self):
        return VIEW_FAR_METERS[self.view_distance]

    def apply_graphics_preset(self, preset):
        if preset not in GRAPHICS_PRESETS:
            raise ValueError(f"Unknown graphics preset: {preset}")
        spec = GRAPHICS_PRESETS[preset]
        self.shadow_quality = spec["shadow_quality"]
        self.msaa_samples = spec["msaa_samples"]
        self.view_distance = spec["view_distance"]
        return self.save()

    def apply_key_preset(self, preset):
        if preset not in KEY_PRESETS:
            raise ValueError(f"Unknown key preset: {preset}")
        self.key_bindings = dict(KEY_PRESETS[preset])
        return self.save()

    def rebind_key(self, action, key):
        """重绑单个动作按键；若与另一动作冲突则自动互换并回报被交换动作名。"""
        if action not in KEY_ACTIONS:
            raise ValueError(f"Unknown action: {action}")
        if key in RESERVED_KEYS or key not in BINDABLE_KEYS:
            return False, None
        previous = self.key_bindings[action]
        if previous == key:
            return True, None
        swapped = None
        for other, bound in self.key_bindings.items():
            if other != action and bound == key:
                self.key_bindings[other] = previous
                swapped = other
                break
        self.key_bindings[action] = key
        return self.save(), swapped

    def reset_category(self, category):
        """按大类恢复默认设置，不影响其他大类。"""
        if category == "graphics":
            self.window_mode = "windowed"
            self.resolution = (1280, 720)
            self.vsync = True
            self.fps_limit = 90
            self.shadow_quality = "high"
            self.msaa_samples = 4
            self.view_distance = "far"
            self.exposure = 100
            self.fov = 68
            self.dynamic_fov = True
        elif category == "controls":
            self.key_bindings = dict(KEY_PRESETS["wasd"])
        elif category == "gameplay":
            self.camera_distance = 11.0
            self.speed_unit = "kmh"
            self.show_key_hints = True
            self.ghost_default = True
            self.show_diagnostics = False
            self.pause_on_focus_loss = True
        else:
            raise ValueError(f"Unknown settings category: {category}")
        return self.save()

    def save(self):
        payload = {
            "window_mode": self.window_mode,
            "resolution": list(self.resolution),
            "vsync": self.vsync,
            "fps_limit": self.fps_limit,
            "shadow_quality": self.shadow_quality,
            "msaa_samples": self.msaa_samples,
            "view_distance": self.view_distance,
            "exposure": self.exposure,
            "fov": self.fov,
            "dynamic_fov": self.dynamic_fov,
            "key_bindings": dict(self.key_bindings),
            "camera_distance": self.camera_distance,
            "speed_unit": self.speed_unit,
            "show_key_hints": self.show_key_hints,
            "ghost_default": self.ghost_default,
            "show_diagnostics": self.show_diagnostics,
            "pause_on_focus_loss": self.pause_on_focus_loss,
        }
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_suffix(".tmp")
            temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            temporary.replace(self.path)
        except OSError:
            self.notice = "游戏设置未能保存，请检查存储空间或目录权限"
            return False
        self.notice = ""
        return True

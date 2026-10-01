"""The applied garage appearance, stored separately from driving results."""

import json

from driving_modes import DrivingMode
from paths import user_data
from skins import PLAYER_VEHICLES, SKINS


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
    """主音量、效果、音乐和电台，单独存入 audio.json。"""

    def __init__(self, path=None):
        self.path = path if path is not None else user_data() / "audio.json"
        self.master_volume = 100
        self.effects_volume = 100
        self.music_volume = 55
        self.radio_station = 1
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

    def save(self, master_volume, effects_volume, music_volume=None, radio_station=None):
        self.master_volume = max(0, min(100, int(master_volume)))
        self.effects_volume = max(0, min(100, int(effects_volume)))
        if music_volume is not None:
            self.music_volume = max(0, min(100, int(music_volume)))
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
                        "music_volume": self.music_volume,
                        "radio_station": self.radio_station,
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

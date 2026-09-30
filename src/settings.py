"""The applied garage appearance, stored separately from driving results."""

import json

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

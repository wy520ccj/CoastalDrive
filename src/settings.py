"""The applied garage appearance, stored separately from driving results."""

import json

from paths import user_data
from skins import MODELS, SKINS


class AppearanceStore:
    def __init__(self, path=None):
        self.path = path if path is not None else user_data() / "appearance.json"
        self.model_id = MODELS[0].id
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
        if model in [item.id for item in MODELS] and skin in [item.id for item in SKINS]:
            self.model_id, self.skin_id = model, skin
        else:
            self.notice = "原外观已不可用，已使用默认外观"

    def save(self, model_id, skin_id):
        if model_id not in [item.id for item in MODELS] or skin_id not in [item.id for item in SKINS]:
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

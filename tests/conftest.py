"""测试分级标记：自动标注启动 Panda3D/OpenGL 窗口的界面测试，方便按需分层执行。"""

import re
from functools import cache
from pathlib import Path

import pytest

_UI_ENGINE_PATTERN = re.compile(r"\b(CoastalDrive|VehicleLab)\s*\(")


@cache
def _uses_3d_window(path_str: str) -> bool:
    text = Path(path_str).read_text(encoding="utf-8", errors="replace")
    return bool(_UI_ENGINE_PATTERN.search(text))


def pytest_collection_modifyitems(items):
    ui_mark = pytest.mark.ui
    for item in items:
        if _uses_3d_window(str(item.path)):
            item.add_marker(ui_mark)

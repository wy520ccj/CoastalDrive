import ast
import fnmatch
import hashlib
import json
import runpy
import struct
from pathlib import Path

import pytest
from panda3d.core import DynamicTextGlyph, PNMImage

import paths
from ui import theme

ROOT = Path(__file__).resolve().parents[1]


def test_font_covers_current_interface_and_matches_pinned_source():
    font = theme.load_font()
    characters = set()
    for name in ("application", "session", "race", "highway_run", "settings", "skins"):
        tree = ast.parse((ROOT / f"src/{name}.py").read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                characters.update(c for c in node.value if not c.isspace())
    missing = [c for c in sorted(characters)
               if not isinstance(font.getGlyph(ord(c)), DynamicTextGlyph)]
    assert not missing, f"当前界面字体缺字：{missing}"
    fonts = ROOT / "assets/game/ui/fonts"
    source = json.loads((fonts / "font-source.json").read_text(encoding="utf-8"))
    assert hashlib.sha256((ROOT / "assets/game/ui" / theme.FONT_FILE).read_bytes()).hexdigest() == source["sha256"]
    assert hashlib.sha256((ROOT / "assets/game/ui" / theme.FONT_LICENSE).read_bytes()).hexdigest() == source["license_sha256"]


def test_frozen_resource_location_and_missing_font_are_explicit(tmp_path, monkeypatch):
    monkeypatch.setattr(paths.sys, "frozen", True, raising=False)
    monkeypatch.setattr(paths.sys, "executable", str(tmp_path / "coastaldrive.exe"))
    target = tmp_path / "assets/game/ui" / theme.FONT_FILE
    with pytest.raises(FileNotFoundError, match="缺少界面资源"):
        theme.load_font()
    target.parent.mkdir(parents=True)
    target.write_bytes(b"not a font")
    assert Path(theme.asset_filename(theme.FONT_FILE).toOsSpecific()) == target
    with pytest.raises(OSError):
        theme.load_font()


def test_distribution_includes_font_license_and_icon(monkeypatch):
    import setuptools

    config = {}
    monkeypatch.setattr(setuptools, "setup", lambda **kwargs: config.update(kwargs))
    runpy.run_path(str(ROOT / "setup.py"))
    patterns = config["options"]["build_apps"]["include_patterns"]
    for name in (theme.FONT_FILE, theme.FONT_LICENSE, "fonts/font-source.json",
                 "coastal-drive.ico", "panel.png", "button.png"):
        relative = "assets/game/ui/" + name
        assert (ROOT / relative).is_file()
        assert any(fnmatch.fnmatchcase(relative, pattern) for pattern in patterns), relative


def test_icon_contains_valid_native_sizes():
    folder = ROOT / "assets/game/ui"
    data = (folder / "coastal-drive.ico").read_bytes()
    assert struct.unpack_from("<HHH", data) == (0, 1, 6)
    for index, size in enumerate((16, 32, 48, 64, 128, 256)):
        w, h, _, _, planes, bits, length, offset = struct.unpack_from(
            "<BBBBHHII", data, 6 + index * 16
        )
        assert (w or 256, h or 256, planes, bits) == (size, size, 1, 32)
        png = folder / f"coastal-drive-icon-{size}.png"
        assert data[offset:offset + length] == png.read_bytes()
        image = PNMImage()
        assert image.read(theme.asset_filename(png.name))
        assert (image.getXSize(), image.getYSize()) == (size, size)


def test_text_palette_retains_readable_contrast():
    def luminance(color):
        channels = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
                    for c in color[:3]]
        return sum(c * weight for c, weight in zip(channels, (0.2126, 0.7152, 0.0722)))

    for foreground in (theme.INK, theme.MUTED, theme.SUCCESS, theme.FAILURE):
        ratio = (luminance(theme.PAPER) + 0.05) / (luminance(foreground) + 0.05)
        assert ratio >= 4.5

"""将 authored TeX 数学行离线排版为透明高分辨率图片，运行时不依赖排版库。"""

import hashlib
import json
import sys
from pathlib import Path

import matplotlib
from matplotlib.font_manager import FontProperties
from matplotlib.mathtext import math_to_image
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from parameter_formulas import FORMULAS


def build():
    output = ROOT / "assets/game/ui/formulas"
    output.mkdir(parents=True, exist_ok=True)
    manifest = {"renderer": f"Matplotlib MathText {matplotlib.__version__}",
                "fontset": "stix", "dpi": 240, "font_points": 24,
                "source": "src/parameter_formulas.py", "formulas": {}}
    with matplotlib.rc_context({"mathtext.fontset": "stix", "mathtext.default": "it",
                                "savefig.transparent": True}):
        for key, (lines, _) in FORMULAS.items():
            entries = []
            for index, tex in enumerate(lines):
                filename = f"{key}-{index}.png"
                path = output / filename
                math_to_image(f"${tex}$", path, prop=FontProperties(size=24), dpi=240,
                              format="png", color="#122e3a")
                with Image.open(path) as image:
                    width, height = image.size
                    assert image.mode == "RGBA" and image.getextrema()[3][0] == 0
                    # Panda默认向下缩为二次幂；预留透明画布，保持原字形采样。
                    padded_width, padded_height = 1 << (width-1).bit_length(), 1 << (height-1).bit_length()
                    ink = Image.new("RGBA", (width, height), "#122e3a")
                    ink.putalpha(image.getchannel("A"))
                    padded = Image.new("RGBA", (padded_width, padded_height), (18, 46, 58, 0))
                    padded.paste(ink, (0, 0))
                padded.save(path)
                entries.append({"file": filename, "tex": tex, "width": width, "height": height,
                                "texture_width": padded_width, "texture_height": padded_height,
                                "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
            manifest["formulas"][key] = entries
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Rendered {sum(len(lines) for lines in manifest['formulas'].values())} mathematical lines")


if __name__ == "__main__":
    build()

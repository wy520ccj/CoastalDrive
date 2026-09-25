"""从许可明确的旧车体生成带独立车灯和车身细节的 BAM 预览模型。"""

import sys
from pathlib import Path

from panda3d.core import Filename, Loader, NodePath

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from skins import MODELS
from vehicle_visual import decorate_vehicle


def main():
    output = ROOT / "assets/game/vehicles"
    output.mkdir(parents=True, exist_ok=True)
    loader = Loader.getGlobalPtr()
    for definition in MODELS:
        source = ROOT / "assets/game" / definition.filename
        model = NodePath(loader.loadSync(Filename.fromOsSpecific(str(source))))
        decorate_vehicle(definition.id, model)
        target = output / f"{definition.id}.bam"
        if not model.writeBamFile(Filename.fromOsSpecific(str(target))):
            raise OSError(f"无法写入车辆模型：{target}")
        print(f"{definition.id}: {target.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

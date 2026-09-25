"""Copy the two Phase 6B nature models used by the roadside scenery."""

from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "assets" / "raw" / "kenney_nature-kit.zip"
DESTINATION = ROOT / "assets" / "game" / "nature"

MODELS = {
    "Models/GLTF format/tree_pineTallB.glb": "tree_pineTallB.glb",
    "Models/GLTF format/plant_bushLargeTriangle.glb": "plant_bushLargeTriangle.glb",
}


def main():
    DESTINATION.mkdir(parents=True, exist_ok=True)

    with ZipFile(ARCHIVE) as archive:
        for source, filename in MODELS.items():
            (DESTINATION / filename).write_bytes(archive.read(source))
            print(f"Prepared {filename}")


if __name__ == "__main__":
    main()

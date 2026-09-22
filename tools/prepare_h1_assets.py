"""Copy the two CC0 nature models used by the test field from the phase-0 archive."""

from pathlib import Path
from zipfile import ZipFile


def main():
    root = Path(__file__).resolve().parents[1]
    output = root / "assets/game/nature"
    output.mkdir(parents=True, exist_ok=True)
    with ZipFile(root / "assets/raw/kenney_nature-kit.zip") as archive:
        for name in ("tree_pineTallA.glb", "rock_largeA.glb"):
            (output / name).write_bytes(archive.read(f"Models/GLTF format/{name}"))
        (output / "License.txt").write_bytes(archive.read("License.txt"))
    print(f"Prepared H1 nature assets in {output}")


if __name__ == "__main__":
    main()

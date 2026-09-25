"""Fetch the two CC0 Poly Haven diffuse maps used by the road scene."""

import hashlib
from pathlib import Path
from urllib.request import Request, urlopen

FILES = {
    "asphalt_floor_diff_2k.jpg": (
        "https://dl.polyhaven.org/file/ph-assets/Textures/jpg/2k/asphalt_floor/asphalt_floor_diff_2k.jpg",
        "7862881b57c46b192ddeb2925e4c1fe3",
    ),
    "grass_ground_diff_2k.jpg": (
        "https://dl.polyhaven.org/file/ph-assets/Textures/jpg/2k/grass_ground/grass_ground_diff_2k.jpg",
        "fd97f2402677e6686b2d9159fc3a4256",
    ),
}


def main():
    output = Path(__file__).resolve().parents[1] / "assets/game/materials"
    output.mkdir(parents=True, exist_ok=True)
    for name, (url, expected) in FILES.items():
        target = output / name
        if target.exists() and hashlib.md5(target.read_bytes()).hexdigest() == expected:
            continue
        request = Request(url, headers={"User-Agent": "CoastalDrive asset preparation"})
        with urlopen(request, timeout=60) as response:
            data = response.read()
        if hashlib.md5(data).hexdigest() != expected:
            raise ValueError(f"Poly Haven checksum mismatch: {name}")
        target.write_bytes(data)
        print(f"Prepared {target}")


if __name__ == "__main__":
    main()

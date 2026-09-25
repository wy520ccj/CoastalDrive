"""Fetch the CC0 sunset sky used by the outdoor tracks."""

import hashlib
from pathlib import Path
from urllib.request import Request, urlopen

URL = "https://dl.polyhaven.org/file/ph-assets/HDRIs/extra/Tonemapped%20JPG/industrial_sunset_puresky.jpg"
MD5 = "be98161b9ba68820ae9cd80a41d37d97"


def main():
    target = Path(__file__).resolve().parents[1] / "assets/game/sky/industrial_sunset_puresky.jpg"
    if target.exists() and hashlib.md5(target.read_bytes()).hexdigest() == MD5:
        return
    request = Request(URL, headers={"User-Agent": "CoastalDrive asset preparation"})
    with urlopen(request, timeout=60) as response:
        data = response.read()
    if hashlib.md5(data).hexdigest() != MD5:
        raise ValueError("Poly Haven sky checksum mismatch")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    print(f"Prepared {target}")


if __name__ == "__main__":
    main()

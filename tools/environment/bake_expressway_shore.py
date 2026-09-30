"""从高速实际三角面烘焙一维海岸线，海水着色不猜测地形接触位置。"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from panda3d.core import Filename, PNMImage

from environment.expressway import END, support_height


def main():
    image = PNMImage(END + 1, 1, 1, 65535)
    for s in range(END + 1):
        lower, upper = 36.0, 120.0
        if support_height(upper, s) > -3:
            coast = 160
        else:
            for _ in range(20):
                middle = (lower + upper) * 0.5
                if support_height(middle, s) > -3:
                    lower = middle
                else:
                    upper = middle
            coast = (lower + upper) * 0.5
        image.setGray(s, 0, coast / 160)
    path = ROOT / "assets/game/expressway/shore-profile.png"
    assert image.write(Filename.fromOsSpecific(str(path)))
    print(path)


if __name__ == "__main__":
    main()

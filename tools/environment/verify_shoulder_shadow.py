"""固定镜头移动太阳覆盖范围，以真实像素检查路肩不再随覆盖变色。"""

import argparse
import json
from pathlib import Path

from panda3d.core import Filename, PNMImage


def profile(folder):
    report = json.loads((folder / "frames.json").read_text(encoding="utf-8"))
    assert report["camera"] == "static" and report["step_m"] == 4
    images = []
    for frame in report["frames"]:
        image = PNMImage()
        assert image.read(Filename.fromOsSpecific(str(folder / frame["file"])))
        images.append(image)
    rows = []
    for point in report["frames"][0]["shoulder"]:
        if 62 <= point["ahead"] <= 95:
            x, y = (round(v) for v in point["pixel"])
            values = [sum(image.getXel(x, y)) / 3 * 255 for image in images]
            rows.append({"ahead": point["ahead"], "values": values,
                         "range": max(values)-min(values)})
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before", type=Path, required=True)
    parser.add_argument("--after", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    before, after = profile(args.before), profile(args.after)
    old_max = max(row["range"] for row in before)
    new_max = max(row["range"] for row in after)
    # 与远景渲染检查一致，使用2%颜色差；保留全部原始值，不隐藏金属盖的末位变化。
    threshold = 255 * .02
    passed = old_max > 50 and new_max <= threshold
    result = {"passed": passed, "kind": "rendered static-camera moving-light probe; not FPS",
              "before_max_change_255": old_max, "after_max_change_255": new_max,
              "threshold_255": threshold,
              "before": before, "after": after}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k not in ("before", "after")}))
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

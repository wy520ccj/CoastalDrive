"""冻结T2前的生产、测试和工具Python，结束后逐文件核对。"""

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUTPUT = Path(__file__).with_name("stage-source-verification.json")


def hashes():
    return {path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for folder in ("src", "tests", "tools")
            for path in sorted((ROOT / folder).rglob("*.py"))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("before", "after"))
    phase = parser.parse_args().phase
    current = hashes()
    if phase == "before":
        with OUTPUT.open("x", encoding="utf-8") as stream:
            json.dump({"source_before": current}, stream, indent=2)
    else:
        report = json.loads(OUTPUT.read_text(encoding="utf-8"))
        report.update(source_after=current, source_unchanged=report["source_before"] == current,
                      file_count=len(current))
        OUTPUT.write_text(json.dumps(report, indent=2)+"\n", encoding="utf-8")
        print({"files": len(current), "unchanged": report["source_unchanged"]})
        return 0 if report["source_unchanged"] else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

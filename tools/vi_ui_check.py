"""复用稳定版页面检查，在全新目录保存 VI 画面和来源哈希。"""

import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path

import ui_6b08_check as check

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--size", choices=("1280x720", "1920x1080"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = (ROOT / args.output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    os.environ["LOCALAPPDATA"] = str(output / "user-data")
    source_hashes = {}
    for folder in ("src", "assets/game", "tools", "tests"):
        for path in sorted((ROOT / folder).rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts:
                source_hashes[path.relative_to(ROOT).as_posix()] = hashlib.sha256(
                    path.read_bytes()
                ).hexdigest()
    source_hashes["setup.py"] = hashlib.sha256((ROOT / "setup.py").read_bytes()).hexdigest()
    metadata = {
        "git_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                            text=True).strip(),
        "git_status": subprocess.check_output(["git", "status", "--short"], cwd=ROOT,
                                              text=True, encoding="utf-8").strip(),
        "source_sha256": source_hashes,
        "kind": "Panda3D offscreen; result branches injected; not human acceptance",
        "human_gate": "pending",
    }
    (output / "source-manifest.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    check.OUTPUT = output
    size = tuple(map(int, args.size.split("x")))
    states = check.run_resolution(size)
    report = {"passed": all(s["text_fits"] for s in states.values()), "states": states}
    (output / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"passed": report["passed"], "states": len(states)}))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

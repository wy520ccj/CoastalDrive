"""仓库外独立包离屏启动及资源哈希检查；不代替窗口性能或人工体验。"""

import argparse
import hashlib
import json
import os
import subprocess
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    package = args.package.resolve()
    scratch = Path(tempfile.mkdtemp(prefix="CoastalDrive-PERF03-final-"))
    assets = []
    for path in sorted((ROOT / "assets/game/expressway").rglob("*")):
        if path.is_file():
            relative = path.relative_to(ROOT)
            assets.append({"path": relative.as_posix(), "sha256": digest(path),
                           "same": digest(package / relative) == digest(path)})
    smokes = []
    for track, shape in (("endless", "hills"), ("endless", "curves"), ("coastal", "straight")):
        folder = scratch / f"{track}-{shape}"
        folder.mkdir()
        environment = dict(os.environ, LOCALAPPDATA=str(folder / "user-data"))
        started = time.perf_counter()
        with (folder / "process.log").open("w", encoding="utf-8") as log:
            process = subprocess.run([str(package / "coastaldrive.exe"), "--smoke", "--track", track,
                                      "--road-shape", shape, "--output", str(folder)],
                                     cwd=folder, env=environment, stdout=log, stderr=log, timeout=90,
                                     check=False)
        smokes.append({"track": track, "shape": shape, "returncode": process.returncode,
                       "seconds": time.perf_counter()-started, "output": str(folder),
                       "files": [p.name for p in folder.iterdir() if p.is_file()],
                       "rendered": (folder / "h0-offscreen.png").is_file(),
                       "report": json.loads((folder / "h0-render-smoke.json").read_text(encoding="utf-8"))})
    result = {"kind": "offscreen independent package smoke outside repository; not FPS or human gate",
              "passed": all(a["same"] for a in assets)
              and all(s["returncode"] == 0 and s["rendered"] and s["report"]["passed"]
                      and all(s["report"][name] for name in ("restart_20_nodes_stable",
                              "restart_20_tasks_stable", "restart_20_events_stable")) for s in smokes),
              "package": str(package / "coastaldrive.exe"),
              "package_sha256": digest(package / "coastaldrive.exe"), "assets": assets, "smokes": smokes}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({"passed": result["passed"], "assets": len(assets), "smokes": len(smokes)}))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

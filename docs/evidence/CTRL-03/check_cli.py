"""经真实命令入口验证两模式八种电子开关组合，完整输出独立存档。"""

import itertools
import json
import subprocess
import sys
from pathlib import Path

OUTPUT = Path(__file__).resolve().parent / "cli"
OUTPUT.mkdir(exist_ok=False)
ROOT = OUTPUT.parents[3]
results = []
for mode in ("game", "simulation"):
    for switches in itertools.product(("off", "on"), repeat=3):
        args = [sys.executable, "src/main.py", "--headless", "--track", "test",
                "--steps", "240", "--driving-mode", mode,
                "--abs", switches[0], "--tcs", switches[1], "--esc", switches[2]]
        run = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=True)
        filename = mode + "-" + "-".join(switches)
        (OUTPUT / (filename + ".json")).write_text(run.stdout, encoding="utf-8")
        (OUTPUT / (filename + ".stderr.txt")).write_text(run.stderr, encoding="utf-8")
        state = json.loads(run.stdout)
        actual = tuple(state["player"][name] for name in ("abs_enabled", "tcs_enabled", "esc_enabled"))
        expected = tuple(switch == "on" for switch in switches)
        assert actual == expected, (args, actual, expected)
        results.append({"mode": mode, "switches": switches, "actual": actual, "command": args, "passed": True})
(OUTPUT / "summary.json").write_text(json.dumps({"passed": True, "cases": results}, indent=2) + "\n", encoding="utf-8")
print(f"{len(results)} CLI configurations passed")

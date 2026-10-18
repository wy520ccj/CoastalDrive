"""冻结9c21f2f的相关源码与旧测试，重现T1两项历史失败。"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
output = args.output.resolve()
output.mkdir(parents=True, exist_ok=False)
files = ("src/application.py", "src/race.py", "src/session.py", "src/ui/hud.py",
         "tests/test_ui.py", "tests/test_traction_lifecycle.py")
for relative in files:
    path = output/relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(subprocess.run(["git", "show", f"9c21f2f:{relative}"], cwd=ROOT,
                                     check=True, capture_output=True).stdout)
sys.path[:0] = [str(ROOT/"src"), str(ROOT/"tools"), str(ROOT/"tests")]
import ui

ui.__path__.insert(0, str(output/"src/ui"))
sys.path.insert(0, str(output/"src"))
import pytest

import application
import race
import session
import ui.hud

tests = [str(output/"tests/test_traction_lifecycle.py")+"::test_mode_abs_tcs_variants_get_distinct_score_keys",
         str(output/"tests/test_ui.py")+"::test_keyboard_navigation_for_secondary_menus"]
print(json.dumps({"baseline": "9c21f2f", "modules": {module.__name__: module.__file__
                 for module in (application, race, session, ui.hud)}, "tests": tests}), flush=True)
raise SystemExit(pytest.main([*tests, "-q"]))

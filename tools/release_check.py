"""在源码或冻结包中复用真实窗口、独立物理进程和实验台往返检查。"""

import argparse
import json
import multiprocessing
import os
from pathlib import Path

from workspace_transition_check import check

if __name__ == "__main__":
    multiprocessing.freeze_support()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    os.environ["LOCALAPPDATA"] = str(output / "user-data")
    print(json.dumps(check(output, onscreen=True, independent=True), ensure_ascii=False))

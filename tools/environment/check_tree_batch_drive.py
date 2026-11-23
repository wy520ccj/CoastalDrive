"""正常入口对照远树合批；候选仅注入本次进程，不修改正式配置。"""

import argparse
import multiprocessing
from pathlib import Path

import local_kcd_drive
from check_interactive_local_drive import check


def run(output, end_distance=270, legacy=False):
    original_batch = local_kcd_drive.tree_batch_steps
    if legacy:
        # 只给独立对照进程恢复未合批的原树；不改物理或玩家设置。
        local_kcd_drive.tree_batch_steps = lambda root, kit: iter(())
    try:
        check(output, False, False, loading_profile=True, end_distance=end_distance, trace_state_cache=True)
    finally:
        local_kcd_drive.tree_batch_steps = original_batch


if __name__ == '__main__':
    multiprocessing.freeze_support()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--end-distance', type=int, choices=(270, 450, 900), default=270)
    parser.add_argument('--legacy', action='store_true')
    args = parser.parse_args()
    run(args.output.resolve(), args.end_distance, args.legacy)

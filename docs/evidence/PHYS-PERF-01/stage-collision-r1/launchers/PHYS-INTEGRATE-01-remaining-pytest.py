"""阶段一次性复用清单；避免将数百节点展开到Windows命令行。"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

reused = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
assert len(reused) == len(set(reused))

class ReuseCollection:
    def pytest_collection_modifyitems(self, config, items):
        known = {item.nodeid for item in items}
        missing = set(reused)-known
        if missing:
            raise pytest.UsageError(f'复用节点不属于当前集合：{sorted(missing)}')
        selected = [item for item in items if item.nodeid not in reused]
        excluded = [item for item in items if item.nodeid in reused]
        config.hook.pytest_deselected(items=excluded)
        selected.sort(key=lambda item: item.nodeid != 'tests/test_h3_review.py::test_highway_traffic_stays_grounded_and_retires_beyond_finish')
        items[:] = selected

sys.exit(pytest.main(['-q','-x','tests',*sys.argv[2:]],plugins=[ReuseCollection()]))

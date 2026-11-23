"""底层原生内核过渡期逐位核对归档测试的独立导入路径配置。"""

import sys
from pathlib import Path

_HERE = str(Path(__file__).resolve().parent)
_TESTS = str(Path(__file__).resolve().parent.parent)
for _p in (_HERE, _TESTS):
    if _p not in sys.path:
        sys.path.insert(0, _p)

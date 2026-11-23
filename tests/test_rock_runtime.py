"""核对真实运行岩岸与原glTF转换结果，不能只凭文件可加载认定无损。"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools/performance'))

from check_rock_runtime import check


def test_native_rock_assets_preserve_original_geometry_materials_and_textures(tmp_path):
    check(tmp_path/'rock-equivalence')

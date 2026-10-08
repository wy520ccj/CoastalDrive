"""复用已存原算式观测器，以100位十进制独立核对乘积补偿。"""
import json
import sys
from decimal import Decimal,localcontext
from pathlib import Path
root=Path.cwd();folder=root/'logs/physics/PHYS-DESIGN-01-wall'
sys.path[:0]=[str(root/'src'),str(folder/'map-terms/b'),str(folder/'accurate-map/b')]
import mechanical_kernels
import _map_terms
import _accurate_map as _stable_map
source=(folder/'check-map-rounding.py').read_text(encoding='utf-8')
source=source[source.index('def unpack(value):'):].replace("'map-rounding.json'","'accurate-map-rounding.json'")
exec(compile(source,__file__,'exec'))

"""原失败系统对照正确乘积补偿重建；原求解与原精度保持。"""
from pathlib import Path
root=Path.cwd();p=root/'logs/physics/PHYS-DESIGN-01-wall/probe-stable-map.py'
s=p.read_text(encoding='utf-8').replace('stable-map/b','accurate-map/b').replace('_stable_map','_accurate_map').replace('replay-stable-map.json','replay-accurate-map.json')
exec(compile(s,__file__,'exec'))

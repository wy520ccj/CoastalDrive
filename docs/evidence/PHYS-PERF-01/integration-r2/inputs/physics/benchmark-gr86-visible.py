"""沿用现有实际绘制观测，只选择本轮GR86/8车输入和隔离的外观设置。"""
import hashlib
import json
from pathlib import Path
root=Path(__file__).resolve().parents[3]
original=root/'tools/performance/benchmark_runtime.py'
source=original.read_text(encoding='utf-8')
source=source.replace('    from application import CoastalDrive\n','''    from application import CoastalDrive
    from highway_run import TRAFFIC_DENSITIES, TrafficDensity
    from settings import AppearanceStore
    from skins import SKINS
    AppearanceStore(args.output / "test-appearance.json").save("gr86-2022", SKINS[0].id)
    density = TRAFFIC_DENSITIES["normal"]
    TRAFFIC_DENSITIES["normal"] = TrafficDensity(density.label, 8, density.spawn_span)
''',1)
source=source.replace('"kind": "45-second comparison; not final performance or human gate",',
    '"kind": "30-second GR86/8-car visible short probe; not final performance or human gate",\n                "vehicle_design": "gr86-2022-premium-6mt",')
(root/'logs/physics/PHYS-PERF-01/visible-probe-original-source.sha256').write_text(hashlib.sha256(original.read_bytes()).hexdigest(),encoding='utf-8')
exec(compile(source,str(original)+' GR86 eight-car diagnostic','exec'),{'__file__':str(original),'__name__':'__main__'})

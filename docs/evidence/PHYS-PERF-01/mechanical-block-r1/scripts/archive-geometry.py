from pathlib import Path

folder = Path(__file__).resolve().parent
source = (folder / 'archive-projections.py').read_text(encoding='utf-8')
source = source.replace('projections-r1', 'geometry-r1').replace('projections-snapshots', 'geometry-snapshots')
source = source.replace('projections-comparison', 'geometry-comparison').replace('PHYS-PERF-01-projections', 'PHYS-PERF-01-geometry')
source = source.replace("'baseline': '30763c8'", "'baseline': '11c7c07'")
source = source.replace('Exact repeated rotation projection reuse;', 'Exact surface transforms, box intervals and finite rotation paths;')
exec(compile(source, str(__file__), 'exec'), {'__file__': str(__file__)})
output = Path(__file__).resolve().parents[3] / 'docs/evidence/PHYS-PERF-01/geometry-r1'
for name in ('transforms-exact.json', 'geometry-loops-exact.json'):
    (output / name).write_bytes((folder / name).read_bytes())

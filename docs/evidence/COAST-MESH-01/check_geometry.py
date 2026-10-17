import json
import subprocess
import sys
from collections import Counter
from pathlib import Path
import gltf
from panda3d.core import GeomVertexReader, NodePath
sys.path.insert(0, 'src')
from environment.terrain import landscape_meshes

out = Path('logs/COAST-MESH-01')
out.mkdir(parents=True, exist_ok=True)
previous = {'__name__': 'baseline_terrain'}
exec(subprocess.check_output(['git', 'show', '591a99a:src/environment/terrain.py']).decode('utf-8'), previous)
old = previous['landscape_meshes']()
new = landscape_meshes()
for a,b in zip(old,new,strict=True):
    assert a['vertices'] == b['vertices']
    assert a['colors'] == b['colors']
    assert a['faces'] == ([(f[0],f[2],f[1]) for f in b['faces']] if a['name']=='coast' else b['faces'])

baseline = out / 'baseline-terrain.glb'
baseline.write_bytes(subprocess.check_output(['git','show','591a99a:assets/game/environment/terrain/coastal-terrain.glb']))
def triangles(path):
    model = NodePath(gltf.load_model(str(path)))
    result = {}
    for node in model.findAllMatches('**/+GeomNode'):
        records = Counter()
        for geom in node.node().getGeoms():
            data = geom.getVertexData()
            readers = [GeomVertexReader(data, name) for name in ('vertex','color','texcoord.0')]
            for primitive in geom.getPrimitives():
                primitive = primitive.decompose()
                for i in range(primitive.getNumPrimitives()):
                    points = []
                    for k in range(primitive.getPrimitiveStart(i),primitive.getPrimitiveEnd(i)):
                        for reader in readers: reader.setRow(primitive.getVertex(k))
                        points.append(tuple(readers[0].getData3())+tuple(readers[1].getData4())+tuple(readers[2].getData2()))
                    records[tuple(sorted(points))]+=1
        result[node.getName()] = records
    return result
before = triangles(baseline)
after = triangles(Path('assets/game/environment/terrain/coastal-terrain.glb'))
assert before == after
report = {'baseline':'591a99a', 'source_vertices_and_colors_identical':True, 'source_only_coast_winding_reversed':True, 'exported_triangle_positions_colors_uv_identical':True, 'triangle_counts':{k:sum(v.values()) for k,v in after.items()}}
(out/'geometry-comparison.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))

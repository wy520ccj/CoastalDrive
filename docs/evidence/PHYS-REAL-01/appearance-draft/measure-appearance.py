"""从游戏同一glTF导入器读取草稿尺寸，不创建Simulation。"""
import hashlib
import json
from pathlib import Path
import gltf
from panda3d.core import Filename, NodePath

base=Path('logs/physics/PHYS-REAL-01-preparation/appearance-draft')
root=NodePath(gltf.load_model(Filename.fromOsSpecific(str((base/'gr86_2022_premium_draft.glb').resolve()))))
names=('wheel-front-left','wheel-front-right','wheel-back-left','wheel-back-right')
def bounds():
    lo,hi=root.getTightBounds(root)
    return {'low_m':list(lo),'high_m':list(hi),'size_m':list(hi-lo)}
wheels=[]
for name in names:
    node=root.find('**/'+name);lo,hi=node.getTightBounds(root)
    wheels.append({'name':name,'center_m':list((lo+hi)/2),'size_m':list(hi-lo)})
paint=root.find('**/paint');low,high=paint.getTightBounds(root)
paint_body={'low_m':list(low),'high_m':list(high),'size_m':list(high-low)}
whole=bounds()
for name in names:root.find('**/'+name).removeNode()
body=bounds()
report={'scope':'Panda3D glTF import readback; preparation only, no Simulation/catalog changes',
        'body_without_wheels':body,'paint_body_without_mirrors':paint_body,'whole_with_wheels':whole,'wheels':wheels,
        'fit_note':'Mirrors are included in full bounds; original nominal body width is kept as a distinct source quantity.'}
(base/'geometry-readback.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
p=base/'manifest.json';manifest=json.loads(p.read_text(encoding='utf-8'))
manifest['sha256']={name:hashlib.sha256((base/name).read_bytes()).hexdigest() for name in ('gr86_2022_premium_draft.blend','gr86_2022_premium_draft.glb','front.png','rear.png')}
manifest['geometry_readback']='geometry-readback.json'
manifest['render_review']='Glass occlusion repaired and reviewed; rim geometry adjusted to stay inside nominal tire section width. Coarse shape and game materials still pending.'
p.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('body',body['size_m'])
print('wheels',[(w['center_m'],w['size_m']) for w in wheels])

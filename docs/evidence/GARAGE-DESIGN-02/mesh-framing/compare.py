import hashlib, json, subprocess, sys, time
from pathlib import Path
from types import SimpleNamespace
import numpy as np
sys.path.insert(0, 'src')
from panda3d.core import Camera, NodePath, PerspectiveLens, Point3
from skins import vehicle_for_design
from vehicle_designs import vehicle_design
from vehicle_visual import load_vehicle
from ui.garage_framing import mesh_vertices, project_vertices
from ui.workshop_vehicle import WorkshopVehicle
baseline = '85c24ca6'
source = subprocess.check_output(['git', 'show', baseline+':src/ui/workshop_vehicle.py']).decode('utf-8')
old = {'__name__': 'baseline_framing'}
exec(compile(source, baseline+':src/ui/workshop_vehicle.py', 'exec'), old)
scene = NodePath('comparison')
root = scene.attachNewNode('car')
config = vehicle_design('game-tuned').config
load_vehicle(root, vehicle_for_design('game-tuned', 'sports'), config=config)
root.setZ(config.center_of_mass_height)
vertices = mesh_vertices(root, scene)
boxes = []
for part in root.findAllMatches('**/+GeomNode'):
    low, high = part.getTightBounds(scene)
    boxes.extend(Point3(x,y,z) for x in (low.x,high.x) for y in (low.y,high.y) for z in (low.z,high.z))
lens = PerspectiveLens()
lens.setFov(46)
lens.setNearFar(.1,80)
camera = scene.attachNewNode(Camera('comparison-camera',lens))
view = SimpleNamespace(car_root=root, scene=scene, camera=camera, framing_vertices=vertices, framing_points=boxes, studio_angle=35.)
measurements=[]
for aspect in (1.3,1.6,2.17):
    lens.setAspectRatio(aspect)
    for method, angle, orbit in (('baseline-box',35.,old['WorkshopVehicle'].orbit),('mesh-same-angle',35.,WorkshopVehicle.orbit),('mesh-default',55.,WorkshopVehicle.orbit)):
        started=time.perf_counter()
        orbit(view,angle-view.studio_angle)
        seconds=time.perf_counter()-started
        points=project_vertices(vertices,scene,camera)
        measurements.append(dict(aspect=aspect,method=method,angle=angle,width_fraction=float(np.ptp(points[:,0])/2),height_fraction=float(np.ptp(points[:,1])/2),orbit_seconds=seconds))
report=dict(baseline=baseline,baseline_source_sha256=hashlib.sha256(source.encode()).hexdigest(),unique_vertices=len(vertices),measurements=measurements,scope='headless projection diagnostic; one timing sample per case, not a runtime performance gate')
Path('logs/validation/GARAGE-DESIGN-02-framing-math/comparison.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps(report))

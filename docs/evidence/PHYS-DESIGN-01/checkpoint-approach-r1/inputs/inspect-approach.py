import json
import sys
from pathlib import Path
root=Path(__file__).resolve().parents[3];sys.path.insert(0,str(root/'src'))
from simulation import Simulation
from coastal_map import nearest_point,road_height
sim=Simulation(track='coastal')
try:
    rows=[]
    for i,(prop,z) in enumerate(sim.props):
        if prop.kind=='checkpoint':
            point,distance=nearest_point(prop.x,prop.y)
            rows.append({'i':i,'prop':str(prop),'z':z,'road_z':road_height(prop.x,prop.y),'distance':distance,'point':str(point)})
    print(json.dumps(rows))
finally:sim.close()

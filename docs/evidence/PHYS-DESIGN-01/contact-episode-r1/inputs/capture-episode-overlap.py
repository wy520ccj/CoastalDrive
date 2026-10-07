"""只复现原事故计数的中心重合输入，保存实际接触对和失败事实。"""
import json
import sys
from dataclasses import asdict
from pathlib import Path
root=Path(__file__).resolve().parents[3];sys.path.insert(0,str(root/'src'))
from simulation import Simulation,Control
sim=Simulation(track='endless',traffic_count=1)
try:
    for _ in range(120):sim.step(Control())
    before=asdict(sim.snapshot())
    rows=[]
    for attempt in range(5):
        sim.npcs[0].reset(tuple(sim.player._chassis.getTransform().getPos()))
        distances=[c.getManifoldPoint().getDistance() for c in sim._world.contactTestPair(sim.player._chassis,sim.npcs[0]._chassis).getContacts()]
        try:
            sim.step(Control());error=None
        except ArithmeticError as failure:error=str(failure)
        rows.append({'attempt':attempt,'pair_distances':distances,'error':error})
        if error is not None:break
    report={'before':before,'identical_body_origins':True,'attempts':rows,'production_unchanged':True}
    (Path(__file__).resolve().parent/'episode-original-overlap-five.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps([{'attempt':row['attempt'],'min_pair_distance':min(row['pair_distances']),'error':row['error']} for row in rows]))
finally:sim.close()

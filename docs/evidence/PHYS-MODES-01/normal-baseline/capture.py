"""保存配置贯通前的正常游戏逐步物理基线。"""
import gzip
import hashlib
import json
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT / "src"))
from simulation import Control,Simulation
from vehicle_config import CAR
from panda3d.core import PandaSystem
from panda3d.bullet import getBulletVersion

OUT=Path(__file__).resolve().parent
CASES=(("test", "straight", 0),("coastal", "straight", 2),("endless", "hills", 2))
metadata={"git_head":subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip(),
          "config":asdict(CAR),"fixed_dt":1/120,"ticks":1200,
          "panda":PandaSystem.getVersionString(),"bullet":getBulletVersion(),
          "source_sha256":{str(p.relative_to(ROOT)).replace("\\","/"):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((ROOT/"src").rglob("*.py"))},
          "sampling":"Every tick; full player/traffic CarState and world counters. Contact epoch identity and ImpactEvent source identities excluded.","cases":[]}
for track,shape,count in CASES:
    sim=Simulation(23,track=track,road_shape=shape,traffic_count=count)
    filename=f"{track}-{shape}.jsonl.gz"
    try:
        with gzip.open(OUT/filename,"wt",encoding="utf-8") as stream:
            for tick in range(1200):
                control=(Control(throttle=.65) if tick<360 else
                         Control(steering=.12,throttle=.4) if tick<720 else
                         Control(brake=1))
                sim.step(control)
                snap=sim.snapshot()
                record={"tick":snap.tick,"time":snap.time,"input":asdict(control),
                        "player":asdict(snap.player),"traffic":[asdict(car) for car in snap.traffic],
                        "origin_y":snap.origin_y,"collisions":snap.collisions,"events":snap.events}
                stream.write(json.dumps(record,ensure_ascii=False,allow_nan=False,separators=(",",":"))+"\n")
        metadata["cases"].append({"track":track,"road_shape":shape,"traffic_count":count,"seed":23,"file":filename,
                                  "sha256":hashlib.sha256((OUT/filename).read_bytes()).hexdigest()})
        print(track,"saved",flush=True)
    finally:
        sim.close()
(OUT/"metadata.json").write_text(json.dumps(metadata,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

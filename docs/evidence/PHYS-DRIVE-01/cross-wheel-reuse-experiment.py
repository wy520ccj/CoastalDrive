"""仅在本进程装入拟议函数；磁盘生产源和后台验证不变。"""
import hashlib,inspect,json
from pathlib import Path
import sys
E=Path(__file__).resolve().parent;ROOT=E.parents[2]
sys.path.insert(0,str(ROOT/"src"))
import tire_drivetrain
import vehicle_tires
ORIGINAL=tire_drivetrain.advance_drivetrain
NEEDLE="""    plans = (tuple(clutch_brake_plans(local_response[i], capacity, brakes[i], efficiency) for i in range(4))
             if ratio else ((),) * 4)
"""
REPLACEMENT="""    if ratio:
        plans_by_response = {}
        wheel_plans = []
        for response, brake in zip(local_response, brakes):
            key = response, brake
            # 同一子步内相同端口共用不可变候选；各轮暖模式仍分别保存。
            if key not in plans_by_response:
                plans_by_response[key] = clutch_brake_plans(response, capacity, brake, efficiency)
            wheel_plans.append(plans_by_response[key])
        plans = tuple(wheel_plans)
    else:
        plans = ((),) * 4
"""
text=inspect.getsource(ORIGINAL)
assert text.count(NEEDLE)==1
namespace=vars(tire_drivetrain).copy()
exec(compile(text.replace(NEEDLE,REPLACEMENT),"<cross-wheel-reuse-experiment>","exec"),namespace)
CANDIDATE=namespace["advance_drivetrain"]
def install(candidate=True):
    function=CANDIDATE if candidate else ORIGINAL
    tire_drivetrain.advance_drivetrain=function
    vehicle_tires.advance_drivetrain=function

def source():
    frozen=json.loads((E/"validation-r8-source-before.json").read_text(encoding="utf-8"))
    now={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in frozen}
    assert now==frozen
    return now

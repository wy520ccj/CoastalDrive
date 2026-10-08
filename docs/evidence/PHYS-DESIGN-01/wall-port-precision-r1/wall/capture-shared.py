"""保存实际撞墙轨迹失败的原共同转子数值输入，不改物理或摆位。"""
import json
import sys
from pathlib import Path

root=Path.cwd(); sys.path.insert(0,str(root/'src'))
folder=root/'logs/physics/PHYS-DESIGN-01-wall'; folder.mkdir(exist_ok=True)
import mechanical_kernels
import tire_drivetrain

registry={}
def traced(name,original):
    def make(*args,**kwargs):
        result=original(*args,**kwargs)
        registry[id(result)]=(result,name,args,kwargs)
        return result
    return make

for name in ('mass_coefficients','rotor_coefficients','shared_map_coefficients'):
    wrapper=traced(name,getattr(mechanical_kernels,name))
    setattr(tire_drivetrain,name,wrapper)

def pack(value):
    if id(value) in registry:
        original,name,args,kwargs=registry[id(value)]
        assert original is value
        return {'capsule':name,'args':pack(args),'kwargs':pack(kwargs)}
    if isinstance(value,tuple):return {'tuple':[pack(x) for x in value]}
    if isinstance(value,list):return [pack(x) for x in value]
    if isinstance(value,dict):return {k:pack(v) for k,v in value.items()}
    assert value is None or isinstance(value,(float,int,str,bool)),type(value)
    return value

from simulation import Simulation,Control
from test_track import SPAWN
sim=Simulation(17,track='test')
sim.reset_player((95,670,SPAWN[2]))
tick=0
try:
    for tick in range(1440):
        sim.step(Control() if tick<240 else Control(throttle=1))
except ArithmeticError as error:
    tb=error.__traceback__
    while tb is not None and tb.tb_frame.f_code.co_name!='shared':tb=tb.tb_next
    assert tb is not None
    scope=tb.tb_frame.f_locals
    packet={key:scope[key] for key in ('shared_map','guess','state','loads','shared_branch','shared_port_index',
            'bias_ports','dimensions','torque_bias','rolling_active','shaft','error','iteration')}
    packet['wheel_loads']=tuple(f.load for f in scope['frames'])
    packet['supported']=tuple(f.supported for f in scope['frames'])
    packet['residual']=scope['residual']
    packet['tick']=tick;packet['completed_ticks']=sim.snapshot().tick;packet['exception']=str(error)
    (folder/'shared-input.json').write_text(json.dumps(pack(packet),indent=2),encoding='utf-8')
    print(json.dumps({k:packet[k] for k in ('tick','completed_ticks','error','iteration','torque_bias','exception')}))
else:
    raise AssertionError('原撞墙轨迹未复现失败')
finally:sim.close()

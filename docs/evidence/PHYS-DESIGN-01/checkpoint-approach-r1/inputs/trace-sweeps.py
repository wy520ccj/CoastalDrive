"""只读记录保存输入的求解迭代与有限运动分区。"""
import json
import sys
from pathlib import Path
root=Path(__file__).resolve().parents[3];folder=Path(__file__).resolve().parent
rows=[];correct=[]
def trace(frame,event,arg):
    if frame.f_code.co_filename.endswith('tire_drivetrain.py') and event=='line':
        values=frame.f_locals
        if frame.f_code.co_name=='advance_drivetrain' and frame.f_lineno==792:
            rows.append({k:values[k] for k in ('sweep','state','end_velocity','maximum','normal_error','geometry_error')})
        if frame.f_code.co_name=='correct_suspension' and frame.f_lineno in (738,746):
            correct.append({'line':frame.f_lineno,**{k:values[k] for k in ('values','errors','before','delta','candidate','after','attempt') if k in values}})
    return trace
sys.settrace(trace)
source=(folder/'replay-original.py').read_text(encoding='utf-8').replace('replay-original.json','replay-traced.json')
exec(compile(source,str(folder/'replay-original.py'),'exec'),{'__file__':str(folder/'replay-original.py')})
sys.settrace(None)
(folder/'sweep-trace.json').write_text(json.dumps({'sweeps':rows,'correct_suspension':correct},indent=2),encoding='utf-8')
print(json.dumps({'sweeps':[(r['sweep'],r['geometry_error']) for r in rows],'correct':correct[-8:]}))

"""独立读取试验导出的外层接触拍及两个子阶段时间戳。"""
import json
import sys
from pathlib import Path
root=Path.cwd();sys.path[:0]=[str(root/'src'),str(root/'tools')]
from physics.tire_compliance_probe import run_trial,trial_config
facts=[]
for case in ('acceleration','constant-turn'):
    for candidate in (False,True):
        config=trial_config(case,candidate,'simulation')
        summary,rows=run_trial(case,candidate,.1)
        facts.append({'case':case,'candidate':candidate,'si':config.suspension_si_enabled,
                      'coupled':config.suspension_coupled_enabled,'ticks':summary['ticks'],
                      'contact_rows':[{'contact_tick':r['state.contact_tick'],
                                       'force':[r[f'state.wheel_dynamics.{i}.force_contact_tick'] for i in range(4)],
                                       'sample':[r[f'state.wheel_dynamics.{i}.sample_tick'] for i in range(4)]}
                                      for r in rows]})
path=root/'logs/physics/PHYS-PERF-01/compliance-timestamp-observations.json'
path.write_text(json.dumps(facts,indent=2),encoding='utf-8')
print(json.dumps([{'case':r['case'],'candidate':r['candidate'],'first':r['contact_rows'][1],'last':r['contact_rows'][-1]} for r in facts]))

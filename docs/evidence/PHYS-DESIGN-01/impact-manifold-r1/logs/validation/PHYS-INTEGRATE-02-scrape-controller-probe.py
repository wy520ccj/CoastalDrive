"""用真实输入闭环维持沿栏轻压；只在本诊断进程试验夹具。"""
import json
import time
from pathlib import Path
root=Path.cwd();path=root/'tests/test_impact_events.py'
source=path.read_text(encoding='utf-8')
source=source.replace('simulation.reset_player((6.9, 30, 0.55))',
    'simulation.reset_player((6.81, 30, 0.55))')
source=source.replace('Vec3(.5, 8, 0)','Vec3(2 * ImpactDetectionConfig().normal_enter, 8, 0)')
source=source.replace('VehicleCommand(throttle=.5, steering=2, direction=1)',
    'VehicleCommand(throttle=.5, steering=2 + simulation.snapshot().player.heading, direction=1)')
source=source.replace('        assert longest >= 600\n        assert len(impacts) == 1',
    '        facts.append({"finite":finite,"longest_contact_ticks":longest,"impact_ticks":[e.tick for e in impacts],"final_position":simulation.snapshot().player.position,"final_heading":simulation.snapshot().player.heading})\n        assert longest >= 600\n        assert len(impacts) == 1')
space={'__file__':str(path),'__name__':'scrape_controller_probe','facts':[]}
exec(compile(source,str(path)+' controller probe','exec'),space)
start=time.perf_counter();errors=[]
for finite in (False,True):
    try:space['test_five_second_rail_scrape_stays_contact_without_repeated_impacts'](finite)
    except AssertionError as error:errors.append({'finite':finite,'error':str(error)})
report={'facts':space['facts'],'errors':errors,'seconds':time.perf_counter()-start,'scope':'test-fixture control inputs only in separate process; production/test files unchanged'}
(root/'logs/validation/PHYS-INTEGRATE-02-scrape-controller-probe.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report));raise SystemExit(1 if errors else 0)

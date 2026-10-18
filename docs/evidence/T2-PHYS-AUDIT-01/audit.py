import sys,json,hashlib,subprocess
from pathlib import Path
from dataclasses import replace
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tools')]
from physics import esc_probe
from driving_modes import REFERENCE_CAR
from lab_runtime import runtime_fingerprint
trials=[]
for steps in (2,4,8,16):
 summary,rows=esc_probe.run_trial('airborne-recontact',True,6,'simulation',vehicle_config=replace(REFERENCE_CAR,engine_axis=(1.,0.,0.),input_shaft_axis=(1.,0.,0.),downstream_axes=((1.,0.,0.),)*3,tire_substeps=steps))
 trials.append({'substeps':steps,'summary':summary})
differences=[abs(b['summary']['path_distance_m']-a['summary']['path_distance_m']) for a,b in zip(trials,trials[1:])]
changed=subprocess.check_output(['git','diff','--name-only','250be45','HEAD'],cwd=ROOT).decode().splitlines()
result={'runtime':runtime_fingerprint(),'trials':trials,'path_differences':differences,'monotonic_path_refinement':differences[2]<differences[1]<differences[0],'source_changes':[x for x in changed if x.startswith('src/')],'test_unchanged':not subprocess.check_output(['git','diff','250be45','HEAD','--','tests/test_vehicle_collision.py','tools/physics/esc_probe.py'],cwd=ROOT)}
out=Path(sys.argv[1]);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'bits':result['runtime']['math_scalar_bits'],'differences':differences,'monotonic':result['monotonic_path_refinement'],'test_unchanged':result['test_unchanged'],'source_changes':result['source_changes']},ensure_ascii=False))

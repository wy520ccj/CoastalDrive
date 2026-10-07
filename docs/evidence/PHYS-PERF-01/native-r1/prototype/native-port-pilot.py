"""核对原生端口探针的实际调用逐值相同，再记录短原生轨迹。"""
import json
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[3]
folder = Path(__file__).resolve().parent
sys.path[:0] = [str(folder / 'native-lib'), str(root / 'src')]
import _port_probe
import tire_drivetrain
from shaft_transmission import shaft_brake_state

audited = 0


def native_port(*args):
    global audited
    result = _port_probe.shaft_brake_state(*args)
    if audited < 256:
        expected = shaft_brake_state(*args)
        assert expected == result, (expected, result)
        audited += 1
    return result


tire_drivetrain.shaft_brake_state = native_port
script = folder / 'compare_ticks.py'
sys.argv = [str(script), str(folder / 'native-port-pilot-snapshots.json')]
exec(compile(script.read_text(encoding='utf-8'), str(script), 'exec'), {'__file__': str(script)})
result = {'in_memory_only': True, 'native_call_exact_comparisons': audited,
          'status': 'completed', 'compiler_flags': ['/fp:strict', '/utf-8']}
(folder / 'native-port-pilot.json').write_text(json.dumps(result, indent=2))
print(json.dumps(result))

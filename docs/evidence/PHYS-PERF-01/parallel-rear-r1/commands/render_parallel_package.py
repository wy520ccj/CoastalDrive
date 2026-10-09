import json
import os
import subprocess
import tempfile
import time
from pathlib import Path

root = Path(__file__).resolve().parents[3]
package = root / 'builds/physics-native-candidate-parallel-r1b/win_amd64'
output = root / 'logs/validation/PHYS-PERF-01-package-parallel-r1b-render'
output.mkdir(exist_ok=False)
scratch = Path(tempfile.mkdtemp(prefix='CoastalDrive-parallel-r1b-render-'))
checks = []
for mode in ('game', 'simulation'):
    local = output / mode
    local.mkdir()
    command = [str(package / 'coastaldrive.exe'), '--smoke', '--track', 'test', '--seed', '17',
               '--vehicle-design', 'gr86-2022-premium-6mt', '--driving-mode', mode, '--output', str(local)]
    started = time.perf_counter()
    with (local / 'process.txt').open('wb') as log:
        try:
            result = subprocess.run(command, cwd=scratch,
                env={**os.environ, 'LOCALAPPDATA': str(local / 'user-data')},
                stdout=log, stderr=subprocess.STDOUT, timeout=90,
                creationflags=subprocess.CREATE_NO_WINDOW)
            exitcode, timed_out = result.returncode, False
        except subprocess.TimeoutExpired:
            exitcode, timed_out = None, True
    report_path = local / 'h0-render-smoke.json'
    report = json.loads(report_path.read_text(encoding='utf-8')) if report_path.is_file() else None
    checks.append({'mode': mode, 'command': command, 'cwd': str(scratch), 'returncode': exitcode,
        'timeout': timed_out, 'seconds': time.perf_counter()-started, 'report': report,
        'passed': exitcode == 0 and report is not None and report['passed']})
    summary = {'checks': checks, 'passed': all(check['passed'] for check in checks),
               'scope': '独立包离屏渲染与20次场景重启；不代表前台FPS或人工驾驶。'}
    (output / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    if not checks[-1]['passed']:
        break
print(json.dumps(summary, ensure_ascii=False))
raise SystemExit(0 if summary['passed'] and len(checks) == 2 else 1)

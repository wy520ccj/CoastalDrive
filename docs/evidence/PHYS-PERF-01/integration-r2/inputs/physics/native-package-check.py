"""仓库外独立包读取原生内核、实车配置与两种输入模式。"""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

root = Path(__file__).resolve().parents[3]
package = root / sys.argv[1]
folder = root / sys.argv[2]
folder.mkdir(exist_ok=False)
scratch = Path(tempfile.mkdtemp(prefix='CoastalDrive-physics-native-'))
checks = []
for mode in ('game', 'simulation'):
    local = scratch / mode
    local.mkdir()
    command = [str(package / 'coastaldrive.exe'), '--headless', '--steps', '120',
               '--track', 'test', '--seed', '17', '--vehicle-design', 'gr86-2022-premium-6mt',
               '--driving-mode', mode]
    started = time.perf_counter()
    completed = subprocess.run(command, cwd=local,
        env={**os.environ, 'LOCALAPPDATA': str(local / 'user-data')},
        capture_output=True, timeout=90, check=False)
    # GUI启动器使用Panda内置USER_APPDATA，应用崩溃报告使用本次LOCALAPPDATA。
    log = Path(os.environ['LOCALAPPDATA']) / 'CoastalDrive/coastaldrive.log'
    body = log.read_bytes()
    (folder / (mode+'.log')).write_bytes(body)
    crash = local / 'user-data/CoastalDrive/crash.log'
    if crash.is_file():
        (folder / (mode+'-crash.log')).write_bytes(crash.read_bytes())
    checks.append({'mode': mode, 'command': command, 'cwd': str(local),
                   'returncode': completed.returncode, 'seconds': time.perf_counter()-started,
                   'log': mode+'.log', 'report_tick_present': b'"tick": 120' in body,
                   'full_hardware_present': b'"axle_torque_bias_ratios"' in body})
files = {}
for file in ('coastaldrive.exe', 'mechanical_kernels.pyd', 'assets/game/vehicle-configs/gr86-2022-premium-6mt.json'):
    files[file] = hashlib.sha256((package / file).read_bytes()).hexdigest()
result = {'kind': 'outside-repository independent package headless; not render, FPS or human gate',
          'passed': all(c['returncode'] == 0 and c['report_tick_present'] and c['full_hardware_present'] for c in checks),
          'checks': checks, 'sha256': files}
(folder / 'summary.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'passed': result['passed'], 'checks': checks}))
assert result['passed']

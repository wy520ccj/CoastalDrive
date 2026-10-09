"""仓库外验证parallel-r1候选包的原生模块、GR86配置与双模式120拍启动。"""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

root = Path(__file__).resolve().parents[3]
if len(sys.argv) != 3:
    raise SystemExit('usage: native-package-check-parallel-r1.py <package-relative-path> <validation-relative-path>')
package = root / sys.argv[1]
folder = root / sys.argv[2]
summary_path = folder / 'summary.json'
if not summary_path.is_file():
    raise RuntimeError('parallel-r1 build summary is missing')
build = json.loads(summary_path.read_text(encoding='utf-8'))
if build.get('status') != 'passed' or not build.get('native_byte_identical'):
    raise RuntimeError('package test requires a passed build with byte-identical native modules')

scratch = Path(tempfile.mkdtemp(prefix='CoastalDrive-physics-native-parallel-r1-'))
checks = []
for mode in ('game', 'simulation'):
    local = scratch / mode
    local.mkdir()
    command = [
        str(package / 'win_amd64/coastaldrive.exe'),
        '--headless', '--steps', '120', '--track', 'coastal', '--seed', '17',
        '--physics-workers','9','--traffic-count','8',
        '--vehicle-design', 'gr86-2022-premium-6mt', '--driving-mode', mode,
    ]
    started_wall_ns = time.time_ns()
    started = time.perf_counter()
    completed = subprocess.run(
        command,
        cwd=local,
        env={**os.environ, 'LOCALAPPDATA': str(local / 'user-data')},
        capture_output=True,
        timeout=90,
        check=False,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
    )

    # Panda的USER_APPDATA记录启动状态；LOCALAPPDATA承接用户数据和崩溃日志。
    app_log = Path(os.environ['LOCALAPPDATA']) / 'CoastalDrive/coastaldrive.log'
    if not app_log.is_file() or app_log.stat().st_mtime_ns < started_wall_ns:
        raise RuntimeError(f'{mode} did not produce a fresh application log')
    body = app_log.read_bytes()
    report = json.loads(body[body.index(b'{'):].decode('utf-8'))
    tick_ok = report.get('tick') == 120 and report.get('driving_mode') == mode
    hardware_ok = (b'"axle_torque_bias_ratios"' in body and len(report['traffic'])==8 and report['physics_workers']['remote']==2160 and report['physics_workers']['world_required']==0 and report['physics_workers']['processes']==9)
    (folder / (mode + '.txt')).write_bytes(body)
    crash = local / 'user-data/CoastalDrive/crash.log'
    if crash.is_file():
        (folder / (mode + '-crash.txt')).write_bytes(crash.read_bytes())
    checks.append({
        'mode': mode,
        'command': command,
        'cwd': str(local),
        'returncode': completed.returncode,
        'seconds': time.perf_counter() - started,
        'tick_120_and_mode_ok': tick_ok,
        'full_hardware_and_eight_npcs_present':hardware_ok,'full_hardware_present': hardware_ok,
        'log': mode + '.txt','physics_workers':report['physics_workers'],
    })

native_files = {}
for module in ('mechanical_kernels', 'wheel_contact_kernels', 'convex_cast_kernels'):
    matches = sorted((package / 'win_amd64').rglob(module + '.pyd'))
    if len(matches) != 1:
        raise RuntimeError(f'expected one packaged {module}.pyd, found {len(matches)}')
    packaged = matches[0]
    expected = build['source_native_sha256'][module]
    native_files[module] = {
        'path': packaged.relative_to(package).as_posix(),
        'bytes': packaged.stat().st_size,
        'sha256': hashlib.sha256(packaged.read_bytes()).hexdigest(),
        'matches_build_source_sha256': hashlib.sha256(packaged.read_bytes()).hexdigest() == expected,
    }

license_path = package / 'win_amd64/licenses/CPython-LICENSE.txt'
vehicle_path = package / 'win_amd64/assets/game/vehicle-configs/gr86-2022-premium-6mt.json'
required_files = {
    'executable': package / 'win_amd64/coastaldrive.exe',
    'license': license_path,
    'bullet_license':package/'win_amd64/licenses/Bullet-LICENSE.txt',
    'repaired_gr86_model':package/'win_amd64/assets/game/vehicles/gr86_2022_premium.glb',
    'gr86_hardware_config': vehicle_path,
}
required_presence = {name: path.is_file() and path.stat().st_size > 0 for name, path in required_files.items()}
files = {
    name: hashlib.sha256(path.read_bytes()).hexdigest()
    for name, path in required_files.items()
    if path.is_file()
}
result = {
    'kind': 'external-repository package headless check; not render, FPS or human acceptance',
    'passed': (
        all(check['returncode'] == 0 and check['tick_120_and_mode_ok'] and check['full_hardware_present'] for check in checks)
        and all(required_presence.values())
        and all(item['matches_build_source_sha256'] for item in native_files.values())
    ),
    'checks': checks,
    'native_modules': native_files,
    'required_files_present': required_presence,
    'sha256': files,
}
(folder / 'package-check.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'passed': result['passed'], 'checks': checks}, ensure_ascii=False))
raise SystemExit(0 if result['passed'] else 1)

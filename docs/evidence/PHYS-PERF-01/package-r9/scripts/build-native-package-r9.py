"""在代码冻结后，以当前主目录输入构建本地原生物理候选包。"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

root = Path(__file__).resolve().parents[3]
expected_python = root / '.venv/Scripts/python.exe'
if os.path.normcase(str(Path(sys.executable).resolve())) != os.path.normcase(str(expected_python.resolve())):
    raise RuntimeError(f'use repository Python: {expected_python}')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def copied_inputs(base):
    files = []
    for area in ('src', 'licenses'):
        for path in (base / area).rglob('*'):
            if not path.is_file() or '__pycache__' in path.parts or path.suffix == '.pyc':
                continue
            files.append(path)
    files.extend(base / name for name in ('setup.py', 'pyproject.toml', 'requirements.txt'))
    return {
        path.relative_to(base).as_posix(): sha(path)
        for path in sorted(files)
    }


def asset_json_inputs():
    return {
        path.relative_to(root).as_posix(): sha(path)
        for path in sorted((root / 'assets').rglob('*.json'))
        if path.is_file()
    }


def complete_inputs():
    return {
        **copied_inputs(root),
        **asset_json_inputs(),
    }


def native_sources(base):
    results = {}
    for module in ('mechanical_kernels', 'wheel_contact_kernels'):
        matches = sorted((base / 'src').glob(module + '.*.pyd'))
        if len(matches) != 1:
            raise RuntimeError(f'expected one {module} source PYD, found {len(matches)}')
        results[module] = matches[0]
    return results


suffixes = ('r9', 'r9b', 'r9c')
selected = None
for suffix in suffixes:
    context = root / f'builds/physics-native-candidate-{suffix}-source'
    package = root / f'builds/physics-native-candidate-{suffix}'
    output = root / f'logs/validation/PHYS-PERF-01-package-{suffix}'
    if not any(path.exists() for path in (context, package, output)):
        selected = (suffix, context, package, output)
        break
if selected is None:
    raise RuntimeError('r9, r9b and r9c targets already exist; preserving them all')
suffix, context, package, output = selected

before = complete_inputs()
copy_before = copied_inputs(root)
source_native = native_sources(root)
native_sha = {name: sha(path) for name, path in source_native.items()}

context.mkdir(parents=True)
shutil.copytree(root / 'src', context / 'src', ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
shutil.copytree(root / 'licenses', context / 'licenses')
for name in ('setup.py', 'pyproject.toml', 'requirements.txt'):
    shutil.copy2(root / name, context / name)

asset_link = context / 'assets'
asset_source = root / 'assets'
if os.name == 'nt':
    link_text = str(asset_link).replace("'", "''")
    source_text = str(asset_source).replace("'", "''")
    subprocess.run(
        ['powershell', '-NoProfile', '-Command',
         f"New-Item -ItemType Junction -Path '{link_text}' -Value '{source_text}' | Out-Null"],
        check=True,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
    )
else:
    asset_link.symlink_to(asset_source, target_is_directory=True)
if not os.path.samefile(asset_link, asset_source):
    raise RuntimeError('asset junction does not point to the repository assets')

copied = copied_inputs(context)
if copied != copy_before:
    raise RuntimeError('source context differs from the main repository inputs')
context_native = native_sources(context)
if {name: sha(path) for name, path in context_native.items()} != native_sha:
    raise RuntimeError('native PYD copies differ from the main repository inputs')

output.mkdir(parents=True, exist_ok=False)
record = {
    'candidate': suffix,
    'main_head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip(),
    'source_context': str(context),
    'package': str(package),
    'validation': str(output),
    'asset_junction': str(asset_link),
    'asset_junction_target': str(asset_source),
    'before_sha256': before,
    'copied_sha256': copied,
    'source_native_sha256': native_sha,
    'status': 'running',
}
(output / 'summary.json').write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')

command = [sys.executable, 'setup.py', 'build_apps', '--build-base', str(package)]
started = time.perf_counter()
with (output / 'build.txt').open('wb') as log:
    result = subprocess.run(
        command,
        cwd=context,
        stdin=subprocess.DEVNULL,
        stdout=log,
        stderr=subprocess.STDOUT,
        check=False,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
    )

after = complete_inputs()
context_after = copied_inputs(context)
packaged_native = {}
native_bytes_equal = True
for module, source_path in context_native.items():
    matches = sorted(package.rglob(module + '.pyd'))
    if len(matches) != 1:
        native_bytes_equal = False
        packaged_native[module] = {'matches': [str(path) for path in matches]}
        continue
    packaged = matches[0]
    equal = packaged.read_bytes() == source_path.read_bytes()
    native_bytes_equal = native_bytes_equal and equal
    packaged_native[module] = {
        'path': str(packaged),
        'bytes': packaged.stat().st_size,
        'sha256': sha(packaged),
        'source_sha256': sha(source_path),
        'byte_identical': equal,
    }

main_source_frozen = before == after
context_unchanged = copied == context_after
status = 'passed' if result.returncode == 0 and main_source_frozen and context_unchanged and native_bytes_equal else 'failed'
record.update(
    command=command,
    returncode=result.returncode,
    seconds=time.perf_counter() - started,
    after_sha256=after,
    context_after_sha256=context_after,
    main_source_frozen=main_source_frozen,
    context_unchanged=context_unchanged,
    packaged_native=packaged_native,
    native_byte_identical=native_bytes_equal,
    status=status,
)
(output / 'summary.json').write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({key: record[key] for key in ('candidate', 'status', 'main_source_frozen', 'native_byte_identical')}))
raise SystemExit(0 if status == 'passed' else 1)

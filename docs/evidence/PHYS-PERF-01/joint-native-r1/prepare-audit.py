from pathlib import Path

root = Path(__file__).resolve().parents[4]
folder = Path(__file__).resolve().parent
source = (root / 'logs/physics/PHYS-PERF-01/shared-load-r1/audit.py').read_text(encoding='utf-8')
source = source.replace('import types', 'import types\nimport time')
source = source.replace('_shared_load_old', '_joint_native_old').replace('_shared_load_original', '_joint_native_original')
source = source.replace('b5c35c5', '6d58e9a')
source = source.replace("'shared_load_calls': 0, 'wheel_free_calls': 0", "'loaded_force_calls': 0, 'wheel_residual_calls': 0, 'suspension_residual_calls': 0")
start = source.index('shared = tire_drivetrain.shared_load_solution')
end = source.index('def audited(', start)
source = source[:start] + '''loaded = tire_drivetrain.loaded_wheel_force_solution
wheel_residual = tire_drivetrain.wheel_residuals
suspension_residual = tire_drivetrain.suspension_residuals
timing = {'old_seconds': 0., 'new_seconds': 0.}

def counted_loaded(*args):
    counts['loaded_force_calls'] += 1
    return loaded(*args)

def counted_wheel(*args):
    counts['wheel_residual_calls'] += 1
    return wheel_residual(*args)

def counted_suspension(*args):
    counts['suspension_residual_calls'] += 1
    return suspension_residual(*args)

''' + source[end:]
source = source.replace('''    expected = baseline.advance_drivetrain(*args, **kwargs)
    actual = advance(*args, **kwargs)''', '''    started = time.perf_counter()
    expected = baseline.advance_drivetrain(*args, **kwargs)
    timing['old_seconds'] += time.perf_counter() - started
    started = time.perf_counter()
    actual = advance(*args, **kwargs)
    timing['new_seconds'] += time.perf_counter() - started''')
source = source.replace('''tire_drivetrain.shared_load_solution = counted_shared
tire_drivetrain.wheel_free_state = counted_free''', '''tire_drivetrain.loaded_wheel_force_solution = counted_loaded
tire_drivetrain.wheel_residuals = counted_wheel
tire_drivetrain.suspension_residuals = counted_suspension''')
source = source.replace("'counts': counts, 'source_sha_start'", "'counts': counts, 'paired_step_timing_diagnostic_only': timing, 'source_sha_start'")
(folder / 'audit.py').write_text(source, encoding='utf-8')

from pathlib import Path

root = Path(__file__).resolve().parents[4]
folder = Path(__file__).resolve().parent
path = root / 'src/mechanical_kernels.c'
source = path.read_text(encoding='utf-8')
source = source.replace('#include <stdint.h>', '#include <stdint.h>\n#include <string.h>')
source = source.replace('static PyMethodDef methods[] = {', (folder / 'residual-body.c').read_text(encoding='utf-8') + '''
static PyMethodDef methods[] = {
    {"wheel_residuals", (PyCFunction)wheel_residuals, METH_VARARGS, "同一末状态四轮接触与制动残差"},
    {"suspension_residuals", (PyCFunction)suspension_residuals, METH_VARARGS, "原法向/几何共轭残差"},''')
path.write_text(source, encoding='utf-8')
path = root / 'src/tire_drivetrain.py'
source = path.read_text(encoding='utf-8')
source = source.replace('    wheel_free_state,', '    wheel_free_state,\n    wheel_residuals,\n    suspension_residuals,')
source = source.replace('    wheel_supported = tuple(frame.supported for frame in frames)',
                        '    wheel_supported = tuple(frame.supported for frame in frames)\n'
                        '    tire_compliance = tuple(car.tire_compliance for car in configurations)')
start = source.index('        maximum, brake_error = 0., 0.\n')
end = source.index('        if suspension is not None:\n', start)
old = source[start:end]
source = source[:start] + '''        if shaft:
            maximum, brake_error = wheel_residuals(wheel_map, state, end_velocity, forces, modes,
                deformations, contact_parameters, tire_hardware, rolling, moments_x, moments_y,
                tire_compliance, math.hypot)
        else:
''' + ''.join('    ' + line if line.strip() else line for line in old.splitlines(keepends=True)) + source[end:]
source = source.replace('''            normal_error = max(abs(a - b) for a, b in zip(normal_forces, normal_step.axial_force))
            target_system = finite_contact_system(reference_suspension, end_velocity, state[:3], dt)
            geometry_error = dt * max(abs(sum(force * (new[a] - old[a]) for force, new, old in
                                             zip(normal_forces, target_system.gradients, suspension.gradients))) for a in range(6))''',
'''            target_system = finite_contact_system(reference_suspension, end_velocity, state[:3], dt)
            normal_error, geometry_error = suspension_residuals(normal_forces, normal_step.axial_force,
                suspension.gradients, target_system.gradients, dt)''')
path.write_text(source, encoding='utf-8')

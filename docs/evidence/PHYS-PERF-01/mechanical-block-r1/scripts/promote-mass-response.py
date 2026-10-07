from pathlib import Path

root = Path(__file__).resolve().parents[3]
folder = Path(__file__).resolve().parent
target = root / 'src/mechanical_kernels.c'
source = target.read_text(encoding='utf-8')
body = (folder / 'mass-response-body.c').read_text(encoding='utf-8')
source = source.replace('static PyMethodDef methods[] = {', body + '\nstatic PyMethodDef methods[] = {\n'
    '    {"mass_response", (PyCFunction)mass_response_call, METH_VARARGS | METH_KEYWORDS, "原实体转子消元及发动机阻力响应"},')
target.write_text(source, encoding='utf-8')
target = root / 'src/tire_drivetrain.py'
source = target.read_text(encoding='utf-8')
source = source.replace('from mechanical_kernels import dot', 'from mechanical_kernels import dot, mass_response')
source = source.replace('inertia_projections, project_inertia, rotor_gradients', 'inertia_projections, rotor_gradients')
begin = source.index('    def base_inverse_mass(vector):')
end = source.index('    downstream = ', begin)
source = source[:begin] + ('    def base_inverse_mass(vector):\n'
    '        return mass_response(vector, inverse_inertia, engine_inertia, shaft_inertia if shaft else None,\n'
    '                             wheel_inertia, (), 0., None)\n\n') + source[end:]
source = source.replace('return project_inertia(base_inverse_mass(vector), downstream_projections)',
    'return mass_response(vector, inverse_inertia, engine_inertia, shaft_inertia if shaft else None,\n'
    '                             wheel_inertia, downstream_projections, 0., None)')
begin = source.index('    def mobility(vector):')
end = source.index('    normal_forces = ', begin)
source = source[:begin] + ('    def mobility(vector):\n'
    '        return mass_response(vector, inverse_inertia, engine_inertia, shaft_inertia if shaft else None,\n'
    '                             wheel_inertia, downstream_projections, drag_factor, engine_response)\n\n') + source[end:]
target.write_text(source, encoding='utf-8')

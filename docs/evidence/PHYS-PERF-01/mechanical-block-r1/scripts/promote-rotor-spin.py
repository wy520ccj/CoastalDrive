from pathlib import Path

root = Path(__file__).resolve().parents[3]
folder = Path(__file__).resolve().parent
target = root / 'src/mechanical_kernels.c'
source = target.read_text(encoding='utf-8')
body = (folder / 'rotor-spin-body.c').read_text(encoding='utf-8')
source = source.replace('static PyMethodDef methods[] = {', body + '\nstatic PyMethodDef methods[] = {\n'
    '    {"rotor_spin", (PyCFunction)rotor_spin_call, METH_VARARGS | METH_KEYWORDS, "原整组转子轴向角动量"},')
target.write_text(source, encoding='utf-8')
target = root / 'src/tire_drivetrain.py'
source = target.read_text(encoding='utf-8')
source = source.replace('from mechanical_kernels import dot, mass_response', 'from mechanical_kernels import dot, mass_response, rotor_spin')
begin = source.index('    def spin(state):')
end = source.index('    def load_terms(', begin)
source = source[:begin] + ('    def spin(state):\n'
    '        return rotor_spin(state[:dimensions], engine_inertia, engine_axis, wheel_inertia, axes, rotor,\n'
    '                          shaft_inertia if shaft else None, shaft_axis, inertias, gradients, downstream_axes)\n\n') + source[end:]
target.write_text(source, encoding='utf-8')

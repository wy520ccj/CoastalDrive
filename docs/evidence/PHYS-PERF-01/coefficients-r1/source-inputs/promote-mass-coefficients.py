from pathlib import Path

root = Path(__file__).resolve().parents[3]
folder = Path(__file__).resolve().parent
target = root / 'src/mechanical_kernels.c'
source = target.read_text(encoding='utf-8')
begin = source.index('static int project_response_data(')
end = source.index('static int matrix_values(', begin)
source = source[:begin] + source[end:]
body = (folder / 'mass-coefficients-body.c').read_text(encoding='utf-8')
compatibility = '''
/* 一次性数值接口与子步系数接口共用同一算法，不保留第二份公式。 */
static PyObject *mass_response_call(PyObject *self,PyObject *args,PyObject *kwargs) {
    PyObject *input,*inverse,*shaft,*projections,*engine_response;
    double engine_inertia,wheel_inertia,drag_factor;
    static char *names[]={"vector","inverse_inertia","engine_inertia","shaft_inertia","wheel_inertia",
                         "projections","drag_factor","engine_response",NULL};
    if (!PyArg_ParseTupleAndKeywords(args,kwargs,"OOdOdOdO",names,&input,&inverse,&engine_inertia,&shaft,
                                     &wheel_inertia,&projections,&drag_factor,&engine_response)) return NULL;
    PyObject *parameters=Py_BuildValue("(OdOdOdO)",inverse,engine_inertia,shaft,wheel_inertia,projections,drag_factor,engine_response);
    if (!parameters) return NULL;
    PyObject *coefficients=mass_coefficients_call(self,parameters,NULL);
    Py_DECREF(parameters);
    if (!coefficients) return NULL;
    parameters=PyTuple_Pack(2,coefficients,input);
    Py_DECREF(coefficients);
    if (!parameters) return NULL;
    PyObject *result=mass_response_prepared_call(self,parameters,NULL);
    Py_DECREF(parameters);
    return result;
}
'''
source = source.replace('static PyMethodDef methods[] = {', body + '\n' + compatibility + '\nstatic PyMethodDef methods[] = {\n'
    '    {"mass_coefficients", (PyCFunction)mass_coefficients_call, METH_VARARGS | METH_KEYWORDS, "本共同求解的只读逆惯量系数"},\n'
    '    {"mass_response_prepared", (PyCFunction)mass_response_prepared_call, METH_VARARGS | METH_KEYWORDS, "复用本共同求解固定逆惯量系数"},')
target.write_text(source, encoding='utf-8')
target = root / 'src/tire_drivetrain.py'
source = target.read_text(encoding='utf-8')
source = source.replace('from mechanical_kernels import dot, mass_response, rotor_spin, wheel_load_terms',
    'from mechanical_kernels import dot, mass_coefficients, mass_response_prepared, rotor_spin, wheel_load_terms')
begin = source.index('    def base_inverse_mass(vector):')
end = source.index('    downstream = ', begin)
source = source[:begin] + ('    # 逆惯量及硬件在本次共同求解中固定，下一物理子步重新读取并构造。\n'
    '    base_coefficients = mass_coefficients(inverse_inertia, engine_inertia, shaft_inertia if shaft else None,\n'
    '                                          wheel_inertia, (), 0., None)\n\n'
    '    def base_inverse_mass(vector):\n'
    '        return mass_response_prepared(base_coefficients, vector)\n\n') + source[end:]
begin = source.index('    def inverse_mass(vector):')
end = source.index('    engine_response = ', begin)
source = source[:begin] + ('    inverse_coefficients = mass_coefficients(inverse_inertia, engine_inertia, shaft_inertia if shaft else None,\n'
    '                                             wheel_inertia, downstream_projections, 0., None)\n\n'
    '    def inverse_mass(vector):\n'
    '        return mass_response_prepared(inverse_coefficients, vector)\n\n') + source[end:]
begin = source.index('    def mobility(vector):')
end = source.index('    normal_forces = ', begin)
source = source[:begin] + ('    mobility_coefficients = mass_coefficients(inverse_inertia, engine_inertia, shaft_inertia if shaft else None,\n'
    '                                              wheel_inertia, downstream_projections, drag_factor, engine_response)\n\n'
    '    def mobility(vector):\n'
    '        return mass_response_prepared(mobility_coefficients, vector)\n\n') + source[end:]
target.write_text(source, encoding='utf-8')

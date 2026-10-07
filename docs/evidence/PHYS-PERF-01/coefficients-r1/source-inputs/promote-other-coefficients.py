from pathlib import Path

root = Path(__file__).resolve().parents[3]
folder = Path(__file__).resolve().parent
target = root / 'src/mechanical_kernels.c'
source = target.read_text(encoding='utf-8')
begin = source.index('static PyObject *rotor_spin_call(')
end = source.index('/* 同一次共同求解', begin)
source = source[:begin] + source[end:]
body = (folder / 'rotor-coefficients-body.c').read_text(encoding='utf-8')
body += '\n' + (folder / 'load-coefficients-body.c').read_text(encoding='utf-8')
body += '''
static PyObject *load_terms_call(PyObject *self,PyObject *args,PyObject *kwargs) {
    PyObject *forces,*responses,*tangents,*axles,*velocity,*normal_forces,*normal_responses,*gradients,*exclude;
    double dt,mass;
    int dimensions;
    static char *names[]={"forces","responses","tangents","axles","velocity","dt","mass",
                         "normal_forces","normal_responses","normal_gradients","exclude","dimensions",NULL};
    if (!PyArg_ParseTupleAndKeywords(args,kwargs,"OOOOOddOOOOi",names,&forces,&responses,&tangents,&axles,&velocity,
                                     &dt,&mass,&normal_forces,&normal_responses,&gradients,&exclude,&dimensions)) return NULL;
    PyObject *parameters=Py_BuildValue("(OOOddi)",responses,tangents,axles,dt,mass,dimensions);
    if (!parameters) return NULL;
    PyObject *coefficients=load_coefficients_call(self,parameters,NULL);
    Py_DECREF(parameters);
    if (!coefficients) return NULL;
    parameters=PyTuple_Pack(7,coefficients,forces,velocity,normal_forces,normal_responses,gradients,exclude);
    Py_DECREF(coefficients);
    if (!parameters) return NULL;
    PyObject *result=wheel_load_prepared_call(self,parameters,NULL);
    Py_DECREF(parameters);
    return result;
}
'''
source = source.replace('static PyMethodDef methods[] = {', body + '\nstatic PyMethodDef methods[] = {\n'
    '    {"rotor_coefficients", (PyCFunction)rotor_coefficients_call, METH_VARARGS | METH_KEYWORDS, "本共同求解的只读转子系数"},\n'
    '    {"rotor_spin_prepared", (PyCFunction)rotor_spin_prepared_call, METH_VARARGS | METH_KEYWORDS, "复用本共同求解固定转子系数"},\n'
    '    {"load_coefficients", (PyCFunction)load_coefficients_call, METH_VARARGS | METH_KEYWORDS, "本共同求解的固定轮端投影"},\n'
    '    {"wheel_load_prepared", (PyCFunction)wheel_load_prepared_call, METH_VARARGS | METH_KEYWORDS, "当前轮端力与法向状态的原投影"},')
target.write_text(source, encoding='utf-8')
target = root / 'src/tire_drivetrain.py'
source = target.read_text(encoding='utf-8')
source = source.replace('    rotor_spin,\n    wheel_load_terms,',
    '    rotor_coefficients,\n    rotor_spin_prepared,\n    load_coefficients,\n    wheel_load_prepared,')
begin = source.index('    def spin(state):')
end = source.index('    def known(', begin)
source = source[:begin] + ('    spin_coefficients = rotor_coefficients(engine_inertia, engine_axis, wheel_inertia, axes, rotor,\n'
    '        shaft_inertia if shaft else None, shaft_axis, inertias, gradients, downstream_axes)\n'
    '    wheel_coefficients = load_coefficients(responses, tuple(frame.tangent for frame in frames),\n'
    '                                          tuple(frame.axle for frame in frames), dt, mass, dimensions)\n\n'
    '    def spin(state):\n'
    '        return rotor_spin_prepared(spin_coefficients, state[:dimensions])\n\n'
    '    def load_terms(exclude=None):\n'
    '        # 法向响应会随末姿态刷新；当前力和梯度逐次传入，固定轮端矩阵只读复用。\n'
    '        return wheel_load_prepared(wheel_coefficients, forces, velocity,\n'
    '            normal_forces if suspension is not None else None, normal_responses,\n'
    '            suspension.gradients if suspension is not None else None, exclude)\n\n') + source[end:]
target.write_text(source, encoding='utf-8')

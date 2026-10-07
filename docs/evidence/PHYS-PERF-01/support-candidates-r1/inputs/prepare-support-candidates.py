from pathlib import Path
root=Path.cwd()
block=r'''
/* 批量执行原覆盖盒筛选，表面对象及分区次序由唯一物理子步提供。 */
static PyObject *support_candidates(PyObject *self, PyObject *args, PyObject *kwargs) {
    PyObject *groups, *low_object, *high_object;
    static char *names[] = {"static_shapes", "low", "high", NULL};
    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "OOO", names,
                                     &groups, &low_object, &high_object)) return NULL;
    double low[3], high[3], center[3], half[3];
    if (!vector(low_object, low) || !vector(high_object, high)) return NULL;
    if (!PyTuple_Check(groups)) {
        PyErr_SetString(PyExc_ValueError, "静态形状分组须为元组"); return NULL;
    }
    for (int i = 0; i < 3; ++i) { center[i] = (low[i]+high[i])/2; half[i] = (high[i]-low[i])/2; }
    PyObject *result = PyList_New(0), *projections = PyDict_New(), *selected = NULL;
    if (!result || !projections) goto error;
    for (Py_ssize_t group_index = 0; group_index < PyTuple_GET_SIZE(groups); ++group_index) {
        PyObject *group = PyTuple_GET_ITEM(groups, group_index);
        if (!PyTuple_Check(group) || PyTuple_GET_SIZE(group) != 3) {
            PyErr_SetString(PyExc_ValueError, "静态形状分组格式错误"); goto error;
        }
        PyObject *parts = PyTuple_GET_ITEM(group, 2);
        if (!PyTuple_Check(parts)) { PyErr_SetString(PyExc_ValueError, "静态形状分区须为元组"); goto error; }
        selected = PyList_New(0);
        if (!selected) goto error;
        for (Py_ssize_t part_index = 0; part_index < PyTuple_GET_SIZE(parts); ++part_index) {
            PyObject *part = PyTuple_GET_ITEM(parts, part_index);
            if (!PyTuple_Check(part) || PyTuple_GET_SIZE(part) != 8) {
                PyErr_SetString(PyExc_ValueError, "静态形状分区格式错误"); goto error;
            }
            PyObject *frame = PyTuple_GET_ITEM(part, 1), *projection = PyDict_GetItemWithError(projections, frame);
            if (!projection && PyErr_Occurred()) goto error;
            if (!projection) {
                double projected[3], local_half[3], row[3], terms[3];
                if (!PyTuple_Check(frame) || PyTuple_GET_SIZE(frame) != 3) {
                    PyErr_SetString(PyExc_ValueError, "形状旋转矩阵须为三维"); goto error;
                }
                for (int i = 0; i < 3; ++i) {
                    if (!vector(PyTuple_GET_ITEM(frame, i), row)) goto error;
                    for (int j = 0; j < 3; ++j) terms[j] = row[j] * center[j];
                    projected[i] = sum_three(terms);
                    for (int j = 0; j < 3; ++j) terms[j] = fabs(row[j]) * half[j];
                    local_half[i] = sum_three(terms);
                }
                projection = Py_BuildValue("((ddd)(ddd))", projected[0], projected[1], projected[2],
                                            local_half[0], local_half[1], local_half[2]);
                if (!projection) goto error;
                int inserted = PyDict_SetItem(projections, frame, projection);
                Py_DECREF(projection);
                if (inserted < 0) goto error;
                projection = PyDict_GetItemWithError(projections, frame);
                if (!projection) goto error;
            }
            double local_center[3], local_half[3], translation[3], projected[3];
            if (!vector(PyTuple_GET_ITEM(part, 2), translation)
                || !vector(PyTuple_GET_ITEM(projection, 0), projected)
                || !vector(PyTuple_GET_ITEM(projection, 1), local_half)) goto error;
            for (int i = 0; i < 3; ++i) local_center[i] = translation[i] + projected[i];
            PyObject *bounds = PyTuple_GET_ITEM(part, 7);
            if (bounds != Py_None) {
                double bound_low[3], bound_high[3];
                if (!PyTuple_Check(bounds) || PyTuple_GET_SIZE(bounds) != 2) {
                    PyErr_SetString(PyExc_ValueError, "形状边界须含上下界"); goto error;
                }
                if (!vector(PyTuple_GET_ITEM(bounds, 0), bound_low)
                    || !vector(PyTuple_GET_ITEM(bounds, 1), bound_high)) goto error;
                int separated = 0;
                for (int i = 0; i < 3; ++i)
                    if (local_center[i]+local_half[i] < bound_low[i]
                        || local_center[i]-local_half[i] > bound_high[i]) separated = 1;
                if (separated) continue;
            }
            PyObject *entry = Py_BuildValue("(O(ddd)O)", part, local_center[0], local_center[1], local_center[2],
                                           PyTuple_GET_ITEM(projection, 1));
            if (!entry) goto error;
            int appended = PyList_Append(selected, entry); Py_DECREF(entry);
            if (appended < 0) goto error;
        }
        if (PyList_GET_SIZE(selected)) {
            PyObject *entry = Py_BuildValue("(OOO)", PyTuple_GET_ITEM(group, 0), PyTuple_GET_ITEM(group, 1), selected);
            if (!entry) goto error;
            int appended = PyList_Append(result, entry); Py_DECREF(entry);
            if (appended < 0) goto error;
        }
        Py_CLEAR(selected);
    }
    Py_DECREF(projections);
    return result;
error:
    Py_XDECREF(selected); Py_XDECREF(projections); Py_XDECREF(result);
    return NULL;
}
'''
(root/'logs/physics/PHYS-PERF-01/support-candidates-body.c').write_text(block,encoding='utf-8')

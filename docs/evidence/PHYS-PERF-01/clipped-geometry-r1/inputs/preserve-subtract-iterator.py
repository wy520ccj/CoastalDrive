from pathlib import Path
p=Path('src/wheel_contact_kernels.c');s=p.read_text(encoding='utf-8');start=s.index('    PyObject *a=PySequence_Fast(',s.index('static PyObject *subtract_vector('));end=s.index('\n}\n\n/* 原六个',start) if '\n}\n\n/* 原六个' in s[start:] else s.index('\n}\n\n/* 原六',start)
# 泛用差量入口保持zip的左/右迭代及提前结束行为，标量减法仍由原数值类型决定。
replacement='''    PyObject *a=PyObject_GetIter(first),*b=PyObject_GetIter(second),*values=PyList_New(0);
    if (!a || !b || !values) { Py_XDECREF(a); Py_XDECREF(b); Py_XDECREF(values); return NULL; }
    while (1) {
        PyObject *left=PyIter_Next(a);
        if (!left) { if (PyErr_Occurred()) goto failed; break; }
        PyObject *right=PyIter_Next(b);
        if (!right) { Py_DECREF(left); if (PyErr_Occurred()) goto failed; break; }
        PyObject *value=PyNumber_Subtract(left,right); Py_DECREF(left); Py_DECREF(right);
        if (!value) goto failed;
        int appended=PyList_Append(values,value); Py_DECREF(value);
        if (appended<0) goto failed;
    }
    PyObject *result=PyList_AsTuple(values);
    Py_DECREF(a); Py_DECREF(b); Py_DECREF(values); return result;
failed:
    Py_DECREF(a); Py_DECREF(b); Py_DECREF(values); return NULL;'''
s=s[:start]+replacement+s[end:];p.write_text(s,encoding='utf-8')

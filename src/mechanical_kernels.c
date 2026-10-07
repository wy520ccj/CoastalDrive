#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <math.h>
#include <limits.h>
#include <stdint.h>

#define PORT_TOLERANCE 1e-11

/* 固定小向量采用补偿求和，保持Python 3.14 sum的舍入结果。 */
static double compensated(const double *values, int count) {
    double main_sum = 0.0, correction = 0.0;
    for (int i = 0; i < count; ++i) {
        double next = main_sum + values[i];
        correction += fabs(main_sum) >= fabs(values[i])
            ? (main_sum - next) + values[i] : (values[i] - next) + main_sum;
        main_sum = next;
    }
    return correction != 0.0 && isfinite(correction) ? main_sum + correction : main_sum;
}

static int vector(PyObject *obj, double *data, int count) {
    PyObject *sequence = PySequence_Fast(obj, "机械向量须为序列");
    if (!sequence) return 0;
    if (PySequence_Fast_GET_SIZE(sequence) != count) {
        PyErr_SetString(PyExc_ValueError, "机械向量维数不一致");
        Py_DECREF(sequence);
        return 0;
    }
    for (int i = 0; i < count; ++i) {
        data[i] = PyFloat_AsDouble(PySequence_Fast_GET_ITEM(sequence, i));
        if (PyErr_Occurred()) { Py_DECREF(sequence); return 0; }
    }
    Py_DECREF(sequence);
    return 1;
}

static PyObject *shaft_state(PyObject *self, PyObject *args, PyObject *kwargs) {
    PyObject *free_object, *response_object, *plans, *warm_object = Py_None;
    double dt, capacity, brake_capacity, efficiency;
    static char *names[] = {"free", "response", "dt", "capacity", "brake_capacity", "efficiency", "plans", "warm", NULL};
    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "OOddddO|O", names, &free_object, &response_object,
                          &dt, &capacity, &brake_capacity, &efficiency, &plans, &warm_object)) return NULL;
    double free_values[4], response[4][4];
    if (!vector(free_object, free_values, 4)) return NULL;
    if (!PyTuple_Check(response_object) || PyTuple_GET_SIZE(response_object) != 4
        || !PyTuple_Check(plans)) {
        PyErr_SetString(PyExc_ValueError, "固定四端口矩阵或活动分区格式错误");
        return NULL;
    }
    for (int i = 0; i < 4; ++i)
        if (!vector(PyTuple_GET_ITEM(response_object, i), response[i], 4)) return NULL;
    Py_ssize_t warm = -1, count = PyTuple_GET_SIZE(plans);
    if (warm_object != Py_None) {
        warm = PyLong_AsSsize_t(warm_object);
        if (PyErr_Occurred()) return NULL;
        if (warm < 0 || warm >= count) {
            PyErr_SetString(PyExc_IndexError, "活动分区索引越界");
            return NULL;
        }
    }
    const int ports[3] = {0, 2, 3};
    const double tolerance = PORT_TOLERANCE;
    double gear_free = free_values[1] / (dt * response[1][1]), reduced[3];
    for (int i = 0; i < 3; ++i)
        reduced[i] = free_values[ports[i]] - response[ports[i]][1] * free_values[1] / response[1][1];
    for (Py_ssize_t visit = warm >= 0 ? -1 : 0; visit < count; ++visit) {
        Py_ssize_t index = visit < 0 ? warm : visit;
        if (visit >= 0 && index == warm) continue;
        PyObject *plan = PyTuple_GetItem(plans, index);
        if (!plan || !PyTuple_Check(plan) || PyTuple_GET_SIZE(plan) != 4) {
            PyErr_SetString(PyExc_ValueError, "四端口活动分区格式错误");
            return NULL;
        }
        double modes[3], sign = PyFloat_AsDouble(PyTuple_GET_ITEM(plan, 1));
        double slope = PyFloat_AsDouble(PyTuple_GET_ITEM(plan, 2));
        double columns[3][3];
        PyObject *column_object = PyTuple_GET_ITEM(plan, 3);
        if (PyErr_Occurred() || !vector(PyTuple_GET_ITEM(plan, 0), modes, 3)) return NULL;
        if (!PyTuple_Check(column_object) || PyTuple_GET_SIZE(column_object) != 3) {
            PyErr_SetString(PyExc_ValueError, "活动分区逆矩阵须为三维");
            return NULL;
        }
        for (int i = 0; i < 3; ++i)
            if (!vector(PyTuple_GET_ITEM(column_object, i), columns[i], 3)) return NULL;
        double rhs[3] = {modes[0] == 0 ? reduced[0] / dt : modes[0] * capacity,
                         modes[1] == 0 ? reduced[1] / dt : slope * gear_free,
                         modes[2] == 0 ? reduced[2] / dt : modes[2] * brake_capacity};
        double unknown[3], terms[4];
        for (int i = 0; i < 3; ++i) {
            for (int j = 0; j < 3; ++j) terms[j] = columns[j][i] * rhs[j];
            unknown[i] = compensated(terms, 3);
        }
        double clutch = unknown[0], loss = unknown[1], brake = unknown[2];
        if (fabs(clutch) > capacity + tolerance || fabs(brake) > brake_capacity + tolerance) continue;
        for (int j = 0; j < 3; ++j) terms[j] = response[1][ports[j]] * unknown[j] / response[1][1];
        double gear = gear_free - compensated(terms, 3);
        double low = (gear >= 0 ? 1 - 1 / efficiency : 1 - efficiency) * gear;
        double high = (gear >= 0 ? 1 - efficiency : 1 - 1 / efficiency) * gear;
        if (loss < low - tolerance || loss > high + tolerance || (sign != 0 && gear * sign < -tolerance)) continue;
        double values[4] = {clutch, gear, loss, brake}, speeds[4];
        for (int i = 0; i < 4; ++i) {
            for (int j = 0; j < 4; ++j) terms[j] = response[i][j] * values[j];
            speeds[i] = free_values[i] - dt * compensated(terms, 4);
        }
        if (fabs(speeds[1]) > tolerance) continue;
        if ((modes[0] == 0 && fabs(speeds[0]) > tolerance) || modes[0] * speeds[0] < -tolerance) continue;
        if ((modes[2] == 0 && fabs(speeds[3]) > tolerance) || modes[2] * speeds[3] < -tolerance) continue;
        if (modes[1] == 0 && fabs(speeds[2]) > tolerance) continue;
        if (modes[1] > 0 && (speeds[2] < -tolerance || fabs(loss - high) > tolerance)) continue;
        if (modes[1] < 0 && (speeds[2] > tolerance || fabs(loss - low) > tolerance)) continue;
        return Py_BuildValue("((dddd)(dddd)n)", clutch, gear, loss, brake,
                             speeds[0], speeds[1], speeds[2], speeds[3], index);
    }
    PyErr_SetString(PyExc_ArithmeticError, "实体输入轴/离合/齿轮/制动共同末状态无可行解");
    return NULL;
}

static PyObject *dot_vector(PyObject *self, PyObject *args, PyObject *kwargs) {
    PyObject *first, *second;
    static char *names[] = {"first", "second", NULL};
    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "OO", names, &first, &second)) return NULL;
    PyObject *a = PySequence_Fast(first, "点积输入须为序列");
    if (!a) return NULL;
    PyObject *b = PySequence_Fast(second, "点积输入须为序列");
    if (!b) { Py_DECREF(a); return NULL; }
    Py_ssize_t count = PySequence_Fast_GET_SIZE(a) < PySequence_Fast_GET_SIZE(b)
        ? PySequence_Fast_GET_SIZE(a) : PySequence_Fast_GET_SIZE(b);
    double main_sum = 0.0, correction = 0.0;
    for (Py_ssize_t i = 0; i < count; ++i) {
        double value = PyFloat_AsDouble(PySequence_Fast_GET_ITEM(a, i))
                     * PyFloat_AsDouble(PySequence_Fast_GET_ITEM(b, i));
        if (PyErr_Occurred()) { Py_DECREF(a); Py_DECREF(b); return NULL; }
        double next = main_sum + value;
        correction += fabs(main_sum) >= fabs(value)
            ? (main_sum - next) + value : (value - next) + main_sum;
        main_sum = next;
    }
    Py_DECREF(a); Py_DECREF(b);
    return PyFloat_FromDouble(correction != 0.0 && isfinite(correction)
                              ? main_sum + correction : main_sum);
}

static PyObject *dot_three(PyObject *self, PyObject *args, PyObject *kwargs) {
    PyObject *first, *second;
    static char *names[] = {"first", "second", NULL};
    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "OO", names, &first, &second)) return NULL;
    double a[3], b[3], products[3];
    if (!vector(first, a, 3) || !vector(second, b, 3)) return NULL;
    for (int i = 0; i < 3; ++i) products[i] = a[i] * b[i];
    return PyFloat_FromDouble(compensated(products, 3));
}

static PyObject *cross_three(PyObject *self, PyObject *args, PyObject *kwargs) {
    PyObject *first, *second;
    static char *names[] = {"first", "second", NULL};
    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "OO", names, &first, &second)) return NULL;
    double a[3], b[3];
    if (!vector(first, a, 3) || !vector(second, b, 3)) return NULL;
    return Py_BuildValue("(ddd)", a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]);
}

static PyObject *project_vector(PyObject *self, PyObject *args, PyObject *kwargs) {
    PyObject *input, *projection_object;
    static char *names[] = {"vector", "projections", NULL};
    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "OO", names, &input, &projection_object)) return NULL;
    PyObject *projections = PySequence_Fast(projection_object, "机械投影须为序列");
    if (!projections) return NULL;
    if (PySequence_Fast_GET_SIZE(projections) == 0) {
        Py_DECREF(projections);
        return Py_NewRef(input);
    }
    PyObject *sequence = PySequence_Fast(input, "机械向量须为序列");
    if (!sequence) { Py_DECREF(projections); return NULL; }
    Py_ssize_t count = PySequence_Fast_GET_SIZE(sequence);
    double *values = PyMem_Malloc((size_t)count * sizeof(double));
    if (!values) { Py_DECREF(sequence); Py_DECREF(projections); return PyErr_NoMemory(); }
    for (Py_ssize_t i = 0; i < count; ++i) {
        values[i] = PyFloat_AsDouble(PySequence_Fast_GET_ITEM(sequence, i));
        if (PyErr_Occurred()) goto failed;
    }
    for (Py_ssize_t step = 0; step < PySequence_Fast_GET_SIZE(projections); ++step) {
        PyObject *projection = PySequence_Fast(PySequence_Fast_GET_ITEM(projections, step), "投影须含梯度、响应与系数");
        if (!projection) goto failed;
        if (PySequence_Fast_GET_SIZE(projection) != 3) {
            Py_DECREF(projection);
            PyErr_SetString(PyExc_ValueError, "投影须含梯度、响应与系数");
            goto failed;
        }
        PyObject *gradient = PySequence_Fast(PySequence_Fast_GET_ITEM(projection, 0), "梯度须为序列");
        PyObject *response = PySequence_Fast(PySequence_Fast_GET_ITEM(projection, 1), "响应须为序列");
        double factor = PyFloat_AsDouble(PySequence_Fast_GET_ITEM(projection, 2));
        Py_DECREF(projection);
        if (!gradient || !response || PyErr_Occurred()) {
            Py_XDECREF(gradient); Py_XDECREF(response); goto failed;
        }
        if (PySequence_Fast_GET_SIZE(gradient) != count || PySequence_Fast_GET_SIZE(response) != count) {
            Py_DECREF(gradient); Py_DECREF(response);
            PyErr_SetString(PyExc_ValueError, "投影与机械向量维数不一致");
            goto failed;
        }
        double main_sum = 0., correction = 0.;
        for (Py_ssize_t i = 0; i < count; ++i) {
            double value = PyFloat_AsDouble(PySequence_Fast_GET_ITEM(gradient, i)) * values[i];
            if (PyErr_Occurred()) { Py_DECREF(gradient); Py_DECREF(response); goto failed; }
            double next = main_sum + value;
            correction += fabs(main_sum) >= fabs(value)
                ? (main_sum-next)+value : (value-next)+main_sum;
            main_sum = next;
        }
        double scale = factor * (correction != 0. && isfinite(correction) ? main_sum + correction : main_sum);
        for (Py_ssize_t i = 0; i < count; ++i) {
            double change = PyFloat_AsDouble(PySequence_Fast_GET_ITEM(response, i));
            if (PyErr_Occurred()) { Py_DECREF(gradient); Py_DECREF(response); goto failed; }
            values[i] = values[i] - scale * change;
        }
        Py_DECREF(gradient); Py_DECREF(response);
    }
    PyObject *result = PyTuple_New(count);
    if (!result) goto failed;
    for (Py_ssize_t i = 0; i < count; ++i) {
        PyObject *value = PyFloat_FromDouble(values[i]);
        if (!value) { Py_DECREF(result); goto failed; }
        PyTuple_SET_ITEM(result, i, value);
    }
    PyMem_Free(values); Py_DECREF(sequence); Py_DECREF(projections);
    return result;
failed:
    PyMem_Free(values); Py_DECREF(sequence); Py_DECREF(projections);
    return NULL;
}

/* 无重叠部分和遵循CPython math.fsum的有限数算法与半偶舍入。 */
static double exact_sum(const double *values, Py_ssize_t length, double *partials) {
    Py_ssize_t count = 0;
    double high = 0., low = 0.;
    for (Py_ssize_t k = 0; k < length; ++k) {
        double x = values[k];
        Py_ssize_t write = 0;
        for (Py_ssize_t j = 0; j < count; ++j) {
            double y = partials[j];
            if (fabs(x) < fabs(y)) { double swap=x; x=y; y=swap; }
            high = x+y; low = y-(high-x);
            if (low != 0.) partials[write++] = low;
            x = high;
        }
        count = write;
        if (!isfinite(x)) { PyErr_SetString(PyExc_OverflowError,"有限机械矩阵求和溢出"); return 0.; }
        if (x != 0.) partials[count++] = x;
    }
    high = 0.;
    if (count) {
        high = partials[--count];
        while (count) {
            double x=high, y=partials[--count];
            high=x+y; low=y-(high-x);
            if (low != 0.) break;
        }
        if (count && ((low<0. && partials[count-1]<0.) || (low>0. && partials[count-1]>0.))) {
            double twice=low*2., rounded=high+twice;
            if (twice == rounded-high) high=rounded;
        }
    }
    return high;
}

static void lu_substitute(const double *rows, const double *values, const Py_ssize_t *order,
                          Py_ssize_t n, double *result, double *terms, double *partials) {
    for (Py_ssize_t i=0; i<n; ++i) result[i]=values[order[i]];
    for (Py_ssize_t i=0; i<n; ++i) {
        terms[0]=result[i];
        for (Py_ssize_t j=0; j<i; ++j) terms[j+1]=-rows[i*n+j]*result[j];
        result[i]=exact_sum(terms,i+1,partials);
    }
    for (Py_ssize_t i=n; i-- > 0;) {
        terms[0]=result[i];
        for (Py_ssize_t j=i+1; j<n; ++j) terms[j-i]=-rows[i*n+j]*result[j];
        result[i]=exact_sum(terms,n-i,partials)/rows[i*n+i];
    }
}

static PyObject *solve_lu(PyObject *self, PyObject *args, PyObject *kwargs) {
    PyObject *matrix_object,*rhs_object;
    static char *names[]={"matrix","rhs",NULL};
    if (!PyArg_ParseTupleAndKeywords(args,kwargs,"OO",names,&matrix_object,&rhs_object)) return NULL;
    PyObject *matrix=PySequence_Fast(matrix_object,"机械矩阵须为行序列");
    if (!matrix) return NULL;
    Py_ssize_t n=PySequence_Fast_GET_SIZE(matrix);
    if (n == 0) { Py_DECREF(matrix); return PyTuple_New(0); }
    if ((size_t)n > INT_MAX || (size_t)n+3 > (SIZE_MAX/sizeof(double)-2)/(2*(size_t)n)) {
        Py_DECREF(matrix); return PyErr_NoMemory();
    }
    double *memory=PyMem_Malloc((2*n*n+6*n+2)*sizeof(double));
    Py_ssize_t *order=PyMem_Malloc(n*sizeof(Py_ssize_t));
    if (!memory || !order) { PyMem_Free(memory); PyMem_Free(order); Py_DECREF(matrix); return PyErr_NoMemory(); }
    double *original=memory,*rows=original+n*n,*rhs=rows+n*n,*result=rhs+n;
    double *residual=result+n,*correction=residual+n,*terms=correction+n,*partials=terms+n+1;
    if (!vector(rhs_object,rhs,(int)n)) goto failed;
    for (Py_ssize_t i=0; i<n; ++i) {
        if (!vector(PySequence_Fast_GET_ITEM(matrix,i),original+i*n,(int)n)) goto failed;
        order[i]=i;
        for (Py_ssize_t j=0; j<n; ++j) rows[i*n+j]=original[i*n+j];
    }
    for (Py_ssize_t col=0; col<n; ++col) {
        Py_ssize_t pivot=col;
        for (Py_ssize_t i=col+1; i<n; ++i)
            if (fabs(rows[i*n+col]) > fabs(rows[pivot*n+col])) pivot=i;
        for (Py_ssize_t j=0; j<n; ++j) {
            double swap=rows[col*n+j]; rows[col*n+j]=rows[pivot*n+j]; rows[pivot*n+j]=swap;
        }
        Py_ssize_t swap=order[col]; order[col]=order[pivot]; order[pivot]=swap;
        if (rows[col*n+col] == 0.) { PyErr_SetString(PyExc_ZeroDivisionError,"机械LU矩阵奇异"); goto failed; }
        for (Py_ssize_t i=col+1; i<n; ++i) {
            double factor=rows[i*n+col]/rows[col*n+col];
            rows[i*n+col]=factor;
            for (Py_ssize_t j=col+1; j<n; ++j) rows[i*n+j]-=factor*rows[col*n+j];
        }
    }
    lu_substitute(rows,rhs,order,n,result,terms,partials);
    if (PyErr_Occurred()) goto failed;
    for (Py_ssize_t i=0; i<n; ++i) {
        terms[0]=rhs[i];
        for (Py_ssize_t j=0; j<n; ++j) terms[j+1]=-original[i*n+j]*result[j];
        residual[i]=exact_sum(terms,n+1,partials);
    }
    lu_substitute(rows,residual,order,n,correction,terms,partials);
    if (PyErr_Occurred()) goto failed;
    PyObject *output=PyTuple_New(n);
    if (!output) goto failed;
    for (Py_ssize_t i=0; i<n; ++i) {
        PyObject *value=PyFloat_FromDouble(result[i]+correction[i]);
        if (!value) { Py_DECREF(output); goto failed; }
        PyTuple_SET_ITEM(output,i,value);
    }
    PyMem_Free(memory); PyMem_Free(order); Py_DECREF(matrix); return output;
failed:
    PyMem_Free(memory); PyMem_Free(order); Py_DECREF(matrix); return NULL;
}

static PyMethodDef methods[] = {
    {"solve_lu", (PyCFunction)solve_lu, METH_VARARGS | METH_KEYWORDS, "小型稠密LU及原精度残差修正"},
    {"shaft_brake_state", (PyCFunction)shaft_state, METH_VARARGS | METH_KEYWORDS, "四端口有限末状态原方程C内核"},
    {"dot", (PyCFunction)dot_vector, METH_VARARGS | METH_KEYWORDS, "同次序补偿点积"},
    {"dot3", (PyCFunction)dot_three, METH_VARARGS | METH_KEYWORDS, "三维补偿点积"},
    {"cross", (PyCFunction)cross_three, METH_VARARGS | METH_KEYWORDS, "三维叉积"},
    {"project_vector", (PyCFunction)project_vector, METH_VARARGS | METH_KEYWORDS, "同次序逐端口机械投影"},
    {NULL, NULL, 0, NULL}
};
static struct PyModuleDef module = {PyModuleDef_HEAD_INIT, "mechanical_kernels", NULL, -1, methods};
PyMODINIT_FUNC PyInit_mechanical_kernels(void) {
    PyObject *result = PyModule_Create(&module);
    if (!result) return NULL;
    PyObject *precision = PyFloat_FromDouble(PORT_TOLERANCE);
    if (!precision) { Py_DECREF(result); return NULL; }
    if (PyModule_AddObject(result, "PORT_TOLERANCE", precision) < 0) {
        Py_DECREF(precision); Py_DECREF(result); return NULL;
    }
    return result;
}

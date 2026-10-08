#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <math.h>
#include <limits.h>
#include <stdint.h>
#include <string.h>
#include <float.h>

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
        PyObject *item=PySequence_Fast_GET_ITEM(sequence,i);
        // 生产向量已是Python浮点；直接读取，外部数值类型仍按原转换报错。
        if (PyFloat_CheckExact(item)) data[i]=PyFloat_AS_DOUBLE(item);
        else if (item==Py_True || item==Py_False) data[i]=item==Py_True ? 1. : 0.;
        else {
            data[i]=PyFloat_AsDouble(item);
            if (PyErr_Occurred()) { Py_DECREF(sequence); return 0; }
        }
    }
    Py_DECREF(sequence);
    return 1;
}


/* 分区顺序与三维余子式保持原实现；相同行只在本次构造内复用。 */
static PyObject *shaft_plans(PyObject *self, PyObject *args, PyObject *kwargs) {
    PyObject *input;
    double capacity, brake_capacity, efficiency;
    static char *names[] = {"response", "capacity", "brake_capacity", "efficiency", NULL};
    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "Oddd", names, &input, &capacity,
                                     &brake_capacity, &efficiency)) return NULL;
    if (!PyTuple_Check(input) || PyTuple_GET_SIZE(input) != 4) {
        PyErr_SetString(PyExc_ValueError, "固定四端口矩阵格式错误");
        return NULL;
    }
    double response[4][4], reduced[3][3], gear_response[3];
    for (int i = 0; i < 4; ++i)
        if (!vector(PyTuple_GET_ITEM(input, i), response[i], 4)) return NULL;
    if (response[1][1] == 0.0 || efficiency == 0.0) {
        PyErr_SetString(PyExc_ZeroDivisionError, "端口响应或效率为零");
        return NULL;
    }
    const int ports[3] = {0, 2, 3}, modes[] = {0, 1, -1}, motions[] = {1, -1, 0};
    for (int j = 0; j < 3; ++j) {
        gear_response[j] = response[1][ports[j]] / response[1][1];
        for (int i = 0; i < 3; ++i)
            reduced[i][j] = response[ports[i]][ports[j]]
                         - response[ports[i]][1] * response[1][ports[j]] / response[1][1];
    }
    double cached_rows[45][3][3];
    PyObject *cached_columns[45];
    int cache_count = 0, plan_index = 0;
    int count = (capacity != 0.0 ? 3 : 2) * 5 * (brake_capacity != 0.0 ? 3 : 2);
    PyObject *result = PyTuple_New(count);
    if (!result) return NULL;
    for (int cm = capacity != 0.0 ? 0 : 1; cm < 3; ++cm)
        for (int mi = 0; mi < 3; ++mi)
            for (int bm = brake_capacity != 0.0 ? 0 : 1; bm < 3; ++bm)
                for (int si = 0; si < (motions[mi] != 0 ? 2 : 1); ++si) {
                    int clutch = modes[cm], motion = motions[mi], brake = modes[bm];
                    int sign = motion != 0 ? (si == 0 ? 1 : -1) : 0;
                    double slope = motion * sign > 0 ? 1 - efficiency : 1 - 1 / efficiency;
                    double rows[3][3];
                    for (int j = 0; j < 3; ++j) {
                        rows[0][j] = clutch == 0 ? reduced[0][j] : (double)(j == 0);
                        rows[1][j] = motion == 0 ? reduced[1][j] : slope * gear_response[j] + (double)(j == 1);
                        rows[2][j] = brake == 0 ? reduced[2][j] : (double)(j == 2);
                    }
                    int cached = 0, created = 0;
                    for (; cached < cache_count; ++cached) {
                        int equal = 1;
                        for (int i = 0; i < 3; ++i)
                            for (int j = 0; j < 3; ++j)
                                if (rows[i][j] != cached_rows[cached][i][j]) equal = 0;
                        if (equal) break;
                    }
                    if (cached == cache_count) {
                        double cofactors[3][3], terms[3], columns[3][3];
                        for (int i = 0; i < 3; ++i) {
                            int a = (i + 1) % 3, b = (i + 2) % 3;
                            cofactors[i][0] = rows[a][1]*rows[b][2] - rows[a][2]*rows[b][1];
                            cofactors[i][1] = rows[a][2]*rows[b][0] - rows[a][0]*rows[b][2];
                            cofactors[i][2] = rows[a][0]*rows[b][1] - rows[a][1]*rows[b][0];
                        }
                        for (int j = 0; j < 3; ++j) terms[j] = rows[0][j] * cofactors[0][j];
                        double determinant = compensated(terms, 3);
                        if (determinant == 0.0) {
                            PyErr_SetString(PyExc_ZeroDivisionError, "端口约束矩阵奇异");
                            Py_DECREF(result);
                            return NULL;
                        }
                        for (int k = 0; k < 3; ++k)
                            for (int i = 0; i < 3; ++i) {
                                for (int j = 0; j < 3; ++j) terms[j] = cofactors[j][i] * (double)(j == k);
                                columns[k][i] = compensated(terms, 3) / determinant;
                            }
                        PyObject *column = Py_BuildValue("((ddd)(ddd)(ddd))",
                            columns[0][0], columns[0][1], columns[0][2],
                            columns[1][0], columns[1][1], columns[1][2],
                            columns[2][0], columns[2][1], columns[2][2]);
                        if (!column) { Py_DECREF(result); return NULL; }
                        for (int i = 0; i < 3; ++i)
                            for (int j = 0; j < 3; ++j) cached_rows[cached][i][j] = rows[i][j];
                        cached_columns[cache_count++] = column;
                        created = 1;
                    }
                    PyObject *plan = Py_BuildValue("((iii)idO)", clutch, motion, brake,
                                                  sign, slope, cached_columns[cached]);

                    if (created) Py_DECREF(cached_columns[cached]);
                    if (!plan) { Py_DECREF(result); return NULL; }
                    PyTuple_SET_ITEM(result, plan_index++, plan);
                }
    return result;
}

/* 同一分区判据供既有端口入口与共同状态映射使用。 */
static int shaft_trial(const double free_values[4],const double response[4][4],double dt,
                       double capacity,double brake_capacity,double efficiency,
                       double gear_free,const double reduced[3],const double modes[3],
                       double sign,double slope,const double columns[3][3],
                       double result[4],double end_speeds[4]) {
    const int ports[3]={0,2,3};
    const double tolerance=PORT_TOLERANCE;
        double rhs[3] = {modes[0] == 0 ? reduced[0] / dt : modes[0] * capacity,
                         modes[1] == 0 ? reduced[1] / dt : slope * gear_free,
                         modes[2] == 0 ? reduced[2] / dt : modes[2] * brake_capacity};
        double unknown[3], terms[4];
        for (int i = 0; i < 3; ++i) {
            for (int j = 0; j < 3; ++j) terms[j] = columns[j][i] * rhs[j];
            unknown[i] = compensated(terms, 3);
        }
        double clutch = unknown[0], loss = unknown[1], brake = unknown[2];
        if (fabs(clutch) > capacity + tolerance || fabs(brake) > brake_capacity + tolerance) return 0;
        for (int j = 0; j < 3; ++j) terms[j] = response[1][ports[j]] * unknown[j] / response[1][1];
        double gear = gear_free - compensated(terms, 3);
        double low = (gear >= 0 ? 1 - 1 / efficiency : 1 - efficiency) * gear;
        double high = (gear >= 0 ? 1 - efficiency : 1 - 1 / efficiency) * gear;
        if (loss < low - tolerance || loss > high + tolerance || (sign != 0 && gear * sign < -tolerance)) return 0;
        double values[4] = {clutch, gear, loss, brake}, speeds[4];
        for (int i = 0; i < 4; ++i) {
            for (int j = 0; j < 4; ++j) terms[j] = response[i][j] * values[j];
            speeds[i] = free_values[i] - dt * compensated(terms, 4);
        }
        if (fabs(speeds[1]) > tolerance) return 0;
        if ((modes[0] == 0 && fabs(speeds[0]) > tolerance) || modes[0] * speeds[0] < -tolerance) return 0;
        if ((modes[2] == 0 && fabs(speeds[3]) > tolerance) || modes[2] * speeds[3] < -tolerance) return 0;
        if (modes[1] == 0 && fabs(speeds[2]) > tolerance) return 0;
        if (modes[1] > 0 && (speeds[2] < -tolerance || fabs(loss - high) > tolerance)) return 0;
        if (modes[1] < 0 && (speeds[2] > tolerance || fabs(loss - low) > tolerance)) return 0;
    for (int i=0; i<4; ++i) { result[i]=values[i]; end_speeds[i]=speeds[i]; }
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
        double values[4],speeds[4];
        if (!shaft_trial(free_values,response,dt,capacity,brake_capacity,efficiency,
                         gear_free,reduced,modes,sign,slope,columns,values,speeds)) continue;
        return Py_BuildValue("((dddd)(dddd)n)", values[0], values[1], values[2], values[3],
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

/* 公开LU与四轮活动集共用原消元、fsum及一次残差修正。 */
static int lu_values(const double *original,const double *rhs,Py_ssize_t n,
                     double *rows,Py_ssize_t *order,double *result,double *residual,
                     double *correction,double *terms,double *partials) {
    for (Py_ssize_t i=0; i<n; ++i) {
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
        if (rows[col*n+col] == 0.) { PyErr_SetString(PyExc_ZeroDivisionError,"机械LU矩阵奇异"); return 0; }
        for (Py_ssize_t i=col+1; i<n; ++i) {
            double factor=rows[i*n+col]/rows[col*n+col];
            rows[i*n+col]=factor;
            for (Py_ssize_t j=col+1; j<n; ++j) rows[i*n+j]-=factor*rows[col*n+j];
        }
    }
    lu_substitute(rows,rhs,order,n,result,terms,partials);
    if (PyErr_Occurred()) return 0;
    for (Py_ssize_t i=0; i<n; ++i) {
        terms[0]=rhs[i];
        for (Py_ssize_t j=0; j<n; ++j) terms[j+1]=-original[i*n+j]*result[j];
        residual[i]=exact_sum(terms,n+1,partials);
    }
    lu_substitute(rows,residual,order,n,correction,terms,partials);
    if (PyErr_Occurred()) return 0;
    for (Py_ssize_t i=0; i<n; ++i) result[i]=result[i]+correction[i];
    return 1;
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
    }
    if (!lu_values(original,rhs,n,rows,order,result,residual,correction,terms,partials)) goto failed;
    PyObject *output=PyTuple_New(n);
    if (!output) goto failed;
    for (Py_ssize_t i=0; i<n; ++i) {
        PyObject *value=PyFloat_FromDouble(result[i]);
        if (!value) { Py_DECREF(output); goto failed; }
        PyTuple_SET_ITEM(output,i,value);
    }
    PyMem_Free(memory); PyMem_Free(order); Py_DECREF(matrix); return output;
failed:
    PyMem_Free(memory); PyMem_Free(order); Py_DECREF(matrix); return NULL;
}

static int matrix_values(PyObject *object,double *values,int rows,int columns) {
    PyObject *sequence=PySequence_Fast(object,"机械矩阵须为行序列");
    if (!sequence) return 0;
    if (PySequence_Fast_GET_SIZE(sequence) != rows) {
        Py_DECREF(sequence); PyErr_SetString(PyExc_ValueError,"机械矩阵行数不一致"); return 0;
    }
    for (int i=0; i<rows; ++i) {
        if (!vector(PySequence_Fast_GET_ITEM(sequence,i),values+i*columns,columns)) { Py_DECREF(sequence); return 0; }
    }
    Py_DECREF(sequence); return 1;
}

/* 同一次共同求解的逆惯量和实体轴投影固定，只保存只读数值系数。 */
typedef struct {
    int dimensions,wheel_start,projection_count,has_drag;
    double inverse[9],engine_inertia,shaft_inertia,wheel_inertia,drag_factor;
    double gradients[3][9],responses[3][9],factors[3],engine_response[9];
} MassCoefficients;

static const char *mass_coefficients_name="CoastalDrive.mass_coefficients";

static void release_mass_coefficients(PyObject *object) {
    PyMem_Free(PyCapsule_GetPointer(object,mass_coefficients_name));
}

static PyObject *mass_coefficients_call(PyObject *self,PyObject *args,PyObject *kwargs) {
    PyObject *inverse,*shaft,*projections_object,*engine_response;
    double engine_inertia,wheel_inertia,drag_factor;
    static char *names[]={"inverse_inertia","engine_inertia","shaft_inertia","wheel_inertia",
                         "projections","drag_factor","engine_response",NULL};
    if (!PyArg_ParseTupleAndKeywords(args,kwargs,"OdOdOdO",names,&inverse,&engine_inertia,&shaft,&wheel_inertia,
                                     &projections_object,&drag_factor,&engine_response)) return NULL;
    MassCoefficients *data=PyMem_Calloc(1,sizeof(MassCoefficients));
    if (!data) return PyErr_NoMemory();
    data->dimensions=shaft == Py_None ? 8 : 9;
    data->wheel_start=shaft == Py_None ? 4 : 5;
    data->engine_inertia=engine_inertia;
    data->wheel_inertia=wheel_inertia;
    data->shaft_inertia=shaft == Py_None ? 1. : PyFloat_AsDouble(shaft);
    data->drag_factor=drag_factor;
    data->has_drag=engine_response != Py_None;
    if (PyErr_Occurred() || !matrix_values(inverse,data->inverse,3,3)
        || (data->has_drag && !vector(engine_response,data->engine_response,data->dimensions))) goto failed;
    if (data->engine_inertia == 0. || data->shaft_inertia == 0. || data->wheel_inertia == 0.) {
        PyErr_SetString(PyExc_ZeroDivisionError,"机械转子惯量为零"); goto failed;
    }
    PyObject *projections=PySequence_Fast(projections_object,"实体轴投影须为序列");
    if (!projections) goto failed;
    Py_ssize_t count=PySequence_Fast_GET_SIZE(projections);
    if (count>3) {
        Py_DECREF(projections); PyErr_SetString(PyExc_ValueError,"实体输出/前/后轴投影最多三组"); goto failed;
    }
    data->projection_count=(int)count;
    for (int i=0; i<data->projection_count; ++i) {
        PyObject *part=PySequence_Fast(PySequence_Fast_GET_ITEM(projections,i),"实体轴投影须为梯度/响应/系数");
        if (!part) { Py_DECREF(projections); goto failed; }
        if (PySequence_Fast_GET_SIZE(part)!=3) {
            Py_DECREF(part); Py_DECREF(projections); PyErr_SetString(PyExc_ValueError,"实体轴投影须为梯度/响应/系数"); goto failed;
        }
        int ok=vector(PySequence_Fast_GET_ITEM(part,0),data->gradients[i],data->dimensions)
            && vector(PySequence_Fast_GET_ITEM(part,1),data->responses[i],data->dimensions);
        data->factors[i]=PyFloat_AsDouble(PySequence_Fast_GET_ITEM(part,2));
        Py_DECREF(part);
        if (!ok || PyErr_Occurred()) { Py_DECREF(projections); goto failed; }
    }
    Py_DECREF(projections);
    PyObject *result=PyCapsule_New(data,mass_coefficients_name,release_mass_coefficients);
    if (!result) goto failed;
    return result;
failed:
    PyMem_Free(data); return NULL;
}

static void mass_response_values(const MassCoefficients *data, const double source[9], double values[9]) {
    double terms[9];
    for (int a=0; a<3; ++a) {
        for (int b=0; b<3; ++b) terms[b]=data->inverse[a*3+b]*source[b];
        values[a]=compensated(terms,3);
    }
    values[3]=source[3]/data->engine_inertia;
    if (data->wheel_start==5) values[4]=source[4]/data->shaft_inertia;
    for (int a=data->wheel_start; a<data->dimensions; ++a) values[a]=source[a]/data->wheel_inertia;
    for (int i=0; i<data->projection_count; ++i) {
        for (int a=0; a<data->dimensions; ++a) terms[a]=data->gradients[i][a]*values[a];
        double scale=data->factors[i]*compensated(terms,data->dimensions);
        for (int a=0; a<data->dimensions; ++a) values[a]=values[a]-scale*data->responses[i][a];
    }
    if (data->has_drag) {
        for (int a=0; a<data->dimensions; ++a) terms[a]=data->engine_response[a]*source[a];
        double projection=data->drag_factor*compensated(terms,data->dimensions);
        for (int a=0; a<data->dimensions; ++a) values[a]=values[a]-projection*data->engine_response[a];
    }
}

static PyObject *mass_response_prepared_call(PyObject *self,PyObject *args,PyObject *kwargs) {
    PyObject *coefficients,*input;
    static char *names[]={"coefficients","vector",NULL};
    if (!PyArg_ParseTupleAndKeywords(args,kwargs,"OO",names,&coefficients,&input)) return NULL;
    MassCoefficients *data=PyCapsule_GetPointer(coefficients,mass_coefficients_name);
    if (!data) return NULL;
    double source[9],values[9];
    if (!vector(input,source,data->dimensions)) return NULL;
    mass_response_values(data,source,values);
    PyObject *result=PyTuple_New(data->dimensions);
    if (!result) return NULL;
    for (int a=0; a<data->dimensions; ++a) {
        PyObject *value=PyFloat_FromDouble(values[a]);
        if (!value) { Py_DECREF(result); return NULL; }
        PyTuple_SET_ITEM(result,a,value);
    }
    return result;
}


/* 一次性数值接口与子步系数接口共用同一算法，不保留第二份公式。 */
static PyObject *suspension_projection(PyObject *self,PyObject *args) {
    PyObject *coefficients,*input;
    double mass;
    if (!PyArg_ParseTuple(args,"OOd",&coefficients,&input,&mass)) return NULL;
    MassCoefficients *data=PyCapsule_GetPointer(coefficients,mass_coefficients_name);
    double gradients[4][6],responses[4][9],bare[4][6],mobility[4][4];
    if (!data || !matrix_values(input,&gradients[0][0],4,6)) return NULL;
    if (mass==0.) {PyErr_SetString(PyExc_ZeroDivisionError,"车身质量不能为零"); return NULL;}
    for (int i=0;i<4;++i) {
        double source[9]={0.},terms[6];
        for (int a=0;a<3;++a) {source[a]=gradients[i][a+3]; bare[i][a]=gradients[i][a]/mass;}
        mass_response_values(data,source,responses[i]);
        for (int a=0;a<3;++a) {
            for (int b=0;b<3;++b) terms[b]=data->inverse[a*3+b]*gradients[i][b+3];
            bare[i][a+3]=compensated(terms,3);
        }
    }
    for (int i=0;i<4;++i) for (int j=0;j<4;++j) {
        double terms[6]; for (int a=0;a<6;++a) terms[a]=gradients[i][a]*bare[j][a];
        mobility[i][j]=compensated(terms,6);
    }
    PyObject *result=PyTuple_New(4),*normal=PyTuple_New(4);
    if (!result || !normal) {Py_XDECREF(result); Py_XDECREF(normal); return NULL;}
    for (int i=0;i<4;++i) {
        PyObject *row=PyTuple_New(data->dimensions);
        if (!row) {Py_DECREF(result); Py_DECREF(normal); return NULL;}
        for (int a=0;a<data->dimensions;++a) {
            PyObject *value=PyFloat_FromDouble(responses[i][a]);
            if (!value) {Py_DECREF(row); Py_DECREF(result); Py_DECREF(normal); return NULL;}
            PyTuple_SET_ITEM(row,a,value);
        }
        PyTuple_SET_ITEM(result,i,row);
        row=Py_BuildValue("(dddd)",mobility[i][0],mobility[i][1],mobility[i][2],mobility[i][3]);
        if (!row) {Py_DECREF(result); Py_DECREF(normal); return NULL;}
        PyTuple_SET_ITEM(normal,i,row);
    }
    return Py_BuildValue("(NN)",result,normal);
}

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

typedef struct {
    int dimensions,wheel_start,rotor,shaft,downstream;
    double engine_inertia,wheel_inertia,shaft_inertia;
    double engine_axis[3],wheel_axes[12],shaft_axis[3],inertias[3],gradients[27],downstream_axes[9];
} RotorCoefficients;

static const char *rotor_coefficients_name="CoastalDrive.rotor_coefficients";

static void release_rotor_coefficients(PyObject *object) {
    PyMem_Free(PyCapsule_GetPointer(object,rotor_coefficients_name));
}

static PyObject *rotor_coefficients_call(PyObject *self,PyObject *args,PyObject *kwargs) {
    PyObject *engine_axis,*axes,*shaft,*shaft_axis,*inertias,*gradients,*downstream_axes;
    double engine_inertia,wheel_inertia;
    int rotor;
    static char *names[]={"engine_inertia","engine_axis","wheel_inertia","wheel_axes","rotor",
                         "shaft_inertia","shaft_axis","inertias","gradients","downstream_axes",NULL};
    if (!PyArg_ParseTupleAndKeywords(args,kwargs,"dOdOpOOOOO",names,&engine_inertia,&engine_axis,&wheel_inertia,
                                     &axes,&rotor,&shaft,&shaft_axis,&inertias,&gradients,&downstream_axes)) return NULL;
    RotorCoefficients *data=PyMem_Calloc(1,sizeof(RotorCoefficients));
    if (!data) return PyErr_NoMemory();
    data->rotor=rotor; data->shaft=shaft != Py_None;
    data->dimensions=data->shaft ? 9 : 8; data->wheel_start=data->shaft ? 5 : 4;
    data->engine_inertia=engine_inertia; data->wheel_inertia=wheel_inertia;
    data->shaft_inertia=data->shaft ? PyFloat_AsDouble(shaft) : 0.;
    if (PyErr_Occurred() || !vector(engine_axis,data->engine_axis,3) || !matrix_values(axes,data->wheel_axes,4,3)
        || (data->shaft && !vector(shaft_axis,data->shaft_axis,3))) goto failed;
    PyObject *sequence=PySequence_Fast(inertias,"实体轴惯量须为序列");
    if (!sequence) goto failed;
    data->downstream=PySequence_Fast_GET_SIZE(sequence) != 0;
    Py_DECREF(sequence);
    if (data->downstream && (!vector(inertias,data->inertias,3)
        || !matrix_values(gradients,data->gradients,3,data->dimensions)
        || !matrix_values(downstream_axes,data->downstream_axes,3,3))) goto failed;
    PyObject *result=PyCapsule_New(data,rotor_coefficients_name,release_rotor_coefficients);
    if (!result) goto failed;
    return result;
failed:
    PyMem_Free(data); return NULL;
}

static void rotor_spin_values(const RotorCoefficients *data, const double state[9], double result[3]) {
    double terms[9],base[3];
    for (int a=0; a<3; ++a) {
        for (int i=0; i<4; ++i) terms[i]=state[i+data->wheel_start]*data->wheel_axes[i*3+a];
        base[a]=data->engine_inertia*state[3]*data->engine_axis[a]
            -(data->rotor ? data->wheel_inertia*compensated(terms,4) : 0.)
            +(data->shaft ? data->shaft_inertia*state[4]*data->shaft_axis[a] : 0.);
    }
    if (data->downstream) {
        double momentum[3];
        for (int i=0; i<3; ++i) {
            for (int b=0; b<data->dimensions; ++b) terms[b]=data->gradients[i*data->dimensions+b]*state[b];
            momentum[i]=data->inertias[i]*compensated(terms,data->dimensions);
        }
        for (int a=0; a<3; ++a) {
            for (int i=0; i<3; ++i) terms[i]=momentum[i]*data->downstream_axes[i*3+a];
            result[a]=base[a]+compensated(terms,3);
        }
    } else {
        for (int a=0; a<3; ++a) result[a]=base[a];
    }
}

static PyObject *rotor_spin_prepared_call(PyObject *self,PyObject *args,PyObject *kwargs) {
    PyObject *coefficients,*input;
    static char *names[]={"coefficients","state",NULL};
    if (!PyArg_ParseTupleAndKeywords(args,kwargs,"OO",names,&coefficients,&input)) return NULL;
    RotorCoefficients *data=PyCapsule_GetPointer(coefficients,rotor_coefficients_name);
    if (!data) return NULL;
    double state[9],result[3];
    if (!vector(input,state,data->dimensions)) return NULL;
    rotor_spin_values(data,state,result);
    return Py_BuildValue("(ddd)",result[0],result[1],result[2]);
}


static void known_values(const MassCoefficients *data,const double base[9],const double gyro[3],
                         const double angular[9],const double *normal,double dt,const double *road,
                         double values[9]) {
    double input[9]={0.},response[9];
    for (int a=0; a<3; ++a) input[a]=gyro[a];
    mass_response_values(data,input,response);
    for (int a=0; a<data->dimensions; ++a) values[a]=base[a]+dt*response[a]+angular[a];
    if (road) {
        for (int a=0; a<3; ++a) input[a]=0.;
        for (int a=0; a<4; ++a) input[a+data->wheel_start]=-road[a];
        mass_response_values(data,input,response);
        for (int a=0; a<data->dimensions; ++a) values[a]=values[a]+dt*response[a];
    }
    if (normal) for (int a=0; a<data->dimensions; ++a) values[a]=values[a]+normal[a];
}

/* 自由状态按原先后次序叠加陀螺、轮端、滚阻及当前法向载荷。 */
static PyObject *known_result(const MassCoefficients *data, PyObject *base_object,
                              const double gyro[3], PyObject *loads, double dt, PyObject *road) {
    double base[9],angular[9],normal[9],values[9];
    if (!PyTuple_Check(loads) || PyTuple_GET_SIZE(loads)!=3) {
        PyErr_SetString(PyExc_ValueError,"共同载荷须含角向、法向及平动自由速度"); return NULL;
    }
    if (!vector(base_object,base,data->dimensions)
        || !vector(PyTuple_GET_ITEM(loads,0),angular,data->dimensions)) return NULL;
    double torques[4];
    if (road!=Py_None && !vector(road,torques,4)) return NULL;
    PyObject *normal_object=PyTuple_GET_ITEM(loads,1);
    if (!PyTuple_Check(normal_object)) {
        PyErr_SetString(PyExc_ValueError,"法向载荷须为元组"); return NULL;
    }
    int suspension=PyTuple_GET_SIZE(normal_object)!=0;
    if (suspension && !vector(normal_object,normal,data->dimensions)) return NULL;
    known_values(data,base,gyro,angular,suspension ? normal : NULL,dt,
                 road!=Py_None ? torques : NULL,values);
    PyObject *free=PyTuple_New(data->dimensions);
    if (!free) return NULL;
    for (int a=0; a<data->dimensions; ++a) {
        PyObject *value=PyFloat_FromDouble(values[a]);
        if (!value) { Py_DECREF(free); return NULL; }
        PyTuple_SET_ITEM(free,a,value);
    }
    return Py_BuildValue("(NO)",free,PyTuple_GET_ITEM(loads,2));
}

static PyObject *known_state_call(PyObject *self,PyObject *args,PyObject *kwargs) {
    PyObject *coefficients,*base,*input,*loads,*road;
    double dt,gyro[3];
    static char *names[]={"coefficients","free_base","gyro","loads","dt","road_torques",NULL};
    if (!PyArg_ParseTupleAndKeywords(args,kwargs,"OOOOdO",names,&coefficients,&base,&input,&loads,&dt,&road)) return NULL;
    MassCoefficients *data=PyCapsule_GetPointer(coefficients,mass_coefficients_name);
    if (!data || !vector(input,gyro,3)) return NULL;
    return known_result(data,base,gyro,loads,dt,road);
}

static PyObject *rotor_known_state_call(PyObject *self,PyObject *args,PyObject *kwargs) {
    PyObject *coefficients,*spin_coefficients,*base,*input,*loads,*road;
    double dt;
    static char *names[]={"coefficients","rotor_coefficients","free_base","state","loads","dt","road_torques",NULL};
    if (!PyArg_ParseTupleAndKeywords(args,kwargs,"OOOOOdO",names,&coefficients,&spin_coefficients,
                                     &base,&input,&loads,&dt,&road)) return NULL;
    MassCoefficients *data=PyCapsule_GetPointer(coefficients,mass_coefficients_name);
    RotorCoefficients *spin=PyCapsule_GetPointer(spin_coefficients,rotor_coefficients_name);
    if (!data || !spin) return NULL;
    if (data->dimensions!=spin->dimensions) {
        PyErr_SetString(PyExc_ValueError,"共同自由状态与转子维数不一致"); return NULL;
    }
    double state[9],momentum[3],gyro[3];
    if (!vector(input,state,data->dimensions)) return NULL;
    rotor_spin_values(spin,state,momentum);
    gyro[0]=momentum[1]*state[2]-momentum[2]*state[1];
    gyro[1]=momentum[2]*state[0]-momentum[0]*state[2];
    gyro[2]=momentum[0]*state[1]-momentum[1]*state[0];
    return known_result(data,base,gyro,loads,dt,road);
}

static PyObject *rotor_spin_call(PyObject *self,PyObject *args,PyObject *kwargs) {
    PyObject *state,*engine_axis,*axes,*shaft,*shaft_axis,*inertias,*gradients,*downstream_axes;
    double engine_inertia,wheel_inertia;
    int rotor;
    static char *names[]={"state","engine_inertia","engine_axis","wheel_inertia","wheel_axes","rotor",
                         "shaft_inertia","shaft_axis","inertias","gradients","downstream_axes",NULL};
    if (!PyArg_ParseTupleAndKeywords(args,kwargs,"OdOdOpOOOOO",names,&state,&engine_inertia,&engine_axis,&wheel_inertia,
                                     &axes,&rotor,&shaft,&shaft_axis,&inertias,&gradients,&downstream_axes)) return NULL;
    PyObject *parameters=Py_BuildValue("(dOdOiOOOOO)",engine_inertia,engine_axis,wheel_inertia,axes,rotor,
                                      shaft,shaft_axis,inertias,gradients,downstream_axes);
    if (!parameters) return NULL;
    PyObject *coefficients=rotor_coefficients_call(self,parameters,NULL);
    Py_DECREF(parameters);
    if (!coefficients) return NULL;
    parameters=PyTuple_Pack(2,coefficients,state);
    Py_DECREF(coefficients);
    if (!parameters) return NULL;
    PyObject *result=rotor_spin_prepared_call(self,parameters,NULL);
    Py_DECREF(parameters);
    return result;
}

typedef struct {
    int dimensions;
    double dt,mass,responses[108],tangents[12],axles[12];
} LoadCoefficients;

static const char *load_coefficients_name="CoastalDrive.load_coefficients";

static void release_load_coefficients(PyObject *object) {
    PyMem_Free(PyCapsule_GetPointer(object,load_coefficients_name));
}

static PyObject *load_coefficients_call(PyObject *self,PyObject *args,PyObject *kwargs) {
    PyObject *responses,*tangents,*axles;
    double dt,mass;
    int dimensions;
    static char *names[]={"responses","tangents","axles","dt","mass","dimensions",NULL};
    if (!PyArg_ParseTupleAndKeywords(args,kwargs,"OOOddi",names,&responses,&tangents,&axles,&dt,&mass,&dimensions)) return NULL;
    if (dimensions!=8 && dimensions!=9) { PyErr_SetString(PyExc_ValueError,"机械状态须为八或九维"); return NULL; }
    if (mass==0.) { PyErr_SetString(PyExc_ZeroDivisionError,"机械车身质量为零"); return NULL; }
    LoadCoefficients *data=PyMem_Calloc(1,sizeof(LoadCoefficients));
    if (!data) return PyErr_NoMemory();
    data->dimensions=dimensions; data->dt=dt; data->mass=mass;
    if (!matrix_values(tangents,data->tangents,4,3) || !matrix_values(axles,data->axles,4,3)) goto failed;
    PyObject *wheels=PySequence_Fast(responses,"轮端响应须为四轮序列");
    if (!wheels) goto failed;
    if (PySequence_Fast_GET_SIZE(wheels)!=4) {
        Py_DECREF(wheels); PyErr_SetString(PyExc_ValueError,"轮端响应须为四轮序列"); goto failed;
    }
    for (int i=0; i<4; ++i) {
        if (!matrix_values(PySequence_Fast_GET_ITEM(wheels,i),data->responses+i*3*dimensions,3,dimensions)) {
            Py_DECREF(wheels); goto failed;
        }
    }
    Py_DECREF(wheels);
    PyObject *result=PyCapsule_New(data,load_coefficients_name,release_load_coefficients);
    if (!result) goto failed;
    return result;
failed:
    PyMem_Free(data); return NULL;
}

/* 当前四轮力与法向几何逐次读取，中间载荷直接供共同/局部数值入口使用。 */
static int wheel_load_values(const LoadCoefficients *data,PyObject *forces,PyObject *velocity_object,
    PyObject *normal_forces_object,PyObject *normal_responses_object,PyObject *gradients_object,long exclude,
    double angular[9],double normal[9],double end_velocity[3]) {
    double force[12],velocity[3],terms[4];
    if (!matrix_values(forces,force,4,3) || !vector(velocity_object,velocity,3)) return 0;
    for (int a=0; a<data->dimensions; ++a) {
        int count=0;
        for (int i=0; i<4; ++i) {
            if (i==exclude) continue;
            terms[count++]=force[i*3]*data->responses[(i*3)*data->dimensions+a]
                +force[i*3+1]*data->responses[(i*3+1)*data->dimensions+a]
                -force[i*3+2]*data->responses[(i*3+2)*data->dimensions+a];
        }
        angular[a]=data->dt*compensated(terms,count);
    }
    /* 平动自由速度每次从真实调用输入读取，不属于固定轮端系数。 */
    for (int a=0; a<3; ++a) {
        int count=0;
        for (int i=0; i<4; ++i) {
            if (i!=exclude) terms[count++]=force[i*3]*data->tangents[i*3+a]+force[i*3+1]*data->axles[i*3+a];
        }
        end_velocity[a]=velocity[a]+data->dt/data->mass*compensated(terms,count);
    }
    int suspension=normal_forces_object!=Py_None;
    if (suspension) {
        double normal_forces[4],normal_responses[36],gradients[24];
        if (!vector(normal_forces_object,normal_forces,4)
            || !matrix_values(normal_responses_object,normal_responses,4,data->dimensions)
            || !matrix_values(gradients_object,gradients,4,6)) return 0;
        for (int a=0; a<data->dimensions; ++a) {
            for (int i=0; i<4; ++i) terms[i]=normal_forces[i]*normal_responses[i*data->dimensions+a];
            normal[a]=data->dt*compensated(terms,4);
        }
        for (int a=0; a<3; ++a) {
            for (int i=0; i<4; ++i) terms[i]=normal_forces[i]*gradients[i*6+a];
            end_velocity[a]=end_velocity[a]+data->dt/data->mass*compensated(terms,4);
        }
    }
    return 1;
}
static PyObject *wheel_load_prepared_call(PyObject *self,PyObject *args,PyObject *kwargs) {
    PyObject *coefficients,*forces,*velocity_object,*normal_forces_object,*normal_responses_object,*gradients_object,*exclude_object;
    static char *names[]={"coefficients","forces","velocity","normal_forces","normal_responses","normal_gradients","exclude",NULL};
    if (!PyArg_ParseTupleAndKeywords(args,kwargs,"OOOOOOO",names,&coefficients,&forces,&velocity_object,&normal_forces_object,
                                     &normal_responses_object,&gradients_object,&exclude_object)) return NULL;
    LoadCoefficients *data=PyCapsule_GetPointer(coefficients,load_coefficients_name);
    if (!data) return NULL;
    long exclude=exclude_object==Py_None ? -1 : PyLong_AsLong(exclude_object);
    if (PyErr_Occurred()) return NULL;
    double angular[9],normal[9],end_velocity[3];
    if (!wheel_load_values(data,forces,velocity_object,normal_forces_object,normal_responses_object,
                           gradients_object,exclude,angular,normal,end_velocity)) return NULL;
    int suspension=normal_forces_object!=Py_None;
    PyObject *angular_result=PyTuple_New(data->dimensions),*normal_result=PyTuple_New(suspension ? data->dimensions : 0);
    if (!angular_result || !normal_result) { Py_XDECREF(angular_result); Py_XDECREF(normal_result); return NULL; }
    for (int a=0; a<data->dimensions; ++a) {
        PyObject *value=PyFloat_FromDouble(angular[a]);
        if (!value) { Py_DECREF(angular_result); Py_DECREF(normal_result); return NULL; }
        PyTuple_SET_ITEM(angular_result,a,value);
        if (suspension) {
            value=PyFloat_FromDouble(normal[a]);
            if (!value) { Py_DECREF(angular_result); Py_DECREF(normal_result); return NULL; }
            PyTuple_SET_ITEM(normal_result,a,value);
        }
    }
    return Py_BuildValue("(NN(ddd))",angular_result,normal_result,end_velocity[0],end_velocity[1],end_velocity[2]);
}

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


/* 当前共同求解的固定机械分区；仅含数值，不持有车辆或物理世界。 */
typedef struct {
    double modes[3],sign,slope,columns[3][3];
} SharedPortPlan;
typedef struct {
    int projection_count,plan_count;
    double gradients[3][9],responses[3][9],factors[3],offset[9],modes[3];
    double mc[9],ml[9],mg[9],port_response[4][4];
    SharedPortPlan plans[45];
} SharedBranch;
typedef struct {
    MassCoefficients mass;
    RotorCoefficients spin;
    int hard,limited,bias,rolling,downstream,branch_count;
    double base[9],spin_columns[9][3],dt,capacity,efficiency,synchronizer;
    double ports[4][9],differential[3][9],damping[3],limits[3];
    double differential_responses[3][9],radii[4],rolling_coefficients[4],transition;
    double ratio,share,final_drive,biases[2],inertias[3],down_gradients[3][9],old_omega[3];
    SharedBranch branches[27];
    int port_seeds[27];
} SharedMap;
static const char *shared_map_name="CoastalDrive.shared_map";
static void release_shared_map(PyObject *object) {
    PyMem_Free(PyCapsule_GetPointer(object,shared_map_name));
}
static int tuple_fields(PyObject *object,Py_ssize_t count) {
    if (!PyTuple_Check(object) || PyTuple_GET_SIZE(object)!=count) {
        PyErr_SetString(PyExc_ValueError,"共同机械数值结构不一致"); return 0;
    }
    return 1;
}
static PyObject *shared_map_coefficients(PyObject *self,PyObject *args,PyObject *kwargs) {
    PyObject *mass_object,*spin_object,*base,*branches,*ports,*differential,*damping,*limits,*responses,*rolling,*bias;
    double dt,capacity,efficiency,synchronizer;
    int hard;
    static char *names[]={"mass_coefficients","rotor_coefficients","free_base","branches","port_gradients",
        "differential_gradients","damping","limits","differential_responses","dt","capacity","efficiency",
        "synchronizer_capacity","hard_gear","rolling","bias",NULL};
    if (!PyArg_ParseTupleAndKeywords(args,kwargs,"OOOOOOOOOddddpOO",names,&mass_object,&spin_object,&base,
        &branches,&ports,&differential,&damping,&limits,&responses,&dt,&capacity,&efficiency,&synchronizer,&hard,
        &rolling,&bias)) return NULL;
    MassCoefficients *mass=PyCapsule_GetPointer(mass_object,mass_coefficients_name);
    RotorCoefficients *spin=PyCapsule_GetPointer(spin_object,rotor_coefficients_name);
    if (!mass || !spin) return NULL;
    if (mass->dimensions!=9 || spin->dimensions!=9) {
        PyErr_SetString(PyExc_ValueError,"共同分区映射须为实体输入轴九维机制"); return NULL;
    }
    SharedMap *data=PyMem_Calloc(1,sizeof(SharedMap));
    if (!data) return PyErr_NoMemory();
    data->mass=*mass; data->spin=*spin; data->dt=dt; data->capacity=capacity;
    for (int i=0;i<27;++i) data->port_seeds[i]=-1;
    for (int j=0; j<9; ++j) {
        double unit[9]={0.}; unit[j]=1.;
        rotor_spin_values(spin,unit,data->spin_columns[j]);
    }
    data->efficiency=efficiency; data->synchronizer=synchronizer; data->hard=hard;
    if (!vector(base,data->base,9) || !matrix_values(ports,&data->ports[0][0],hard ? 4 : 3,9)
        || !matrix_values(differential,&data->differential[0][0],3,9)
        || !vector(damping,data->damping,3) || !vector(limits,data->limits,3)
        || !tuple_fields(rolling,3) || !vector(PyTuple_GET_ITEM(rolling,0),data->radii,4)
        || !vector(PyTuple_GET_ITEM(rolling,1),data->rolling_coefficients,4)
        || !tuple_fields(bias,7)) goto failed;
    data->transition=PyFloat_AsDouble(PyTuple_GET_ITEM(rolling,2));
    data->ratio=PyFloat_AsDouble(PyTuple_GET_ITEM(bias,0));
    data->share=PyFloat_AsDouble(PyTuple_GET_ITEM(bias,1));
    data->final_drive=PyFloat_AsDouble(PyTuple_GET_ITEM(bias,2));
    if (PyErr_Occurred() || !vector(PyTuple_GET_ITEM(bias,3),data->biases,2)) goto failed;
    data->bias=data->biases[0]>1. || data->biases[1]>1.;
    if (data->bias && !matrix_values(responses,&data->differential_responses[0][0],3,9)) goto failed;
    PyObject *old=PyTuple_GET_ITEM(bias,6);
    if (!PyTuple_Check(old)) { PyErr_SetString(PyExc_ValueError,"实体轴初始速度须为元组"); goto failed; }
    data->downstream=PyTuple_GET_SIZE(old)!=0;
    if (data->downstream && (!vector(PyTuple_GET_ITEM(bias,4),data->inertias,3)
        || !matrix_values(PyTuple_GET_ITEM(bias,5),&data->down_gradients[0][0],3,9)
        || !vector(old,data->old_omega,3))) goto failed;
    for (int i=0; i<3; ++i) if (data->damping[i]!=0. && data->limits[i]!=0.) data->limited=1;
    for (int i=0; i<4; ++i) if (data->rolling_coefficients[i]!=0.) data->rolling=1;
    if (!PyTuple_Check(branches) || PyTuple_GET_SIZE(branches)<1 || PyTuple_GET_SIZE(branches)>27) {
        PyErr_SetString(PyExc_ValueError,"三个有限限滑端口的分区数不一致"); goto failed;
    }
    data->branch_count=(int)PyTuple_GET_SIZE(branches);
    for (int i=0; i<data->branch_count; ++i) {
        SharedBranch *branch=&data->branches[i];
        PyObject *input=PyTuple_GET_ITEM(branches,i);
        if (!tuple_fields(input,8)) goto failed;
        PyObject *partition=PyTuple_GET_ITEM(input,0),*local=PyTuple_GET_ITEM(input,5),*shaft=PyTuple_GET_ITEM(input,7);
        if (!tuple_fields(partition,3) || !tuple_fields(local,4) || !tuple_fields(shaft,2)
            || !vector(PyTuple_GET_ITEM(partition,1),branch->offset,9)
            || !vector(PyTuple_GET_ITEM(partition,2),branch->modes,3)
            || !vector(PyTuple_GET_ITEM(input,1),branch->mc,9)
            || !vector(PyTuple_GET_ITEM(input,2),branch->ml,9)
            || !vector(PyTuple_GET_ITEM(shaft,0),branch->mg,9)) goto failed;
        PyObject *projections=PyTuple_GET_ITEM(partition,0);
        if (!PyTuple_Check(projections) || PyTuple_GET_SIZE(projections)>3) {
            PyErr_SetString(PyExc_ValueError,"限滑投影数不一致"); goto failed;
        }
        branch->projection_count=(int)PyTuple_GET_SIZE(projections);
        for (int j=0; j<branch->projection_count; ++j) {
            PyObject *projection=PyTuple_GET_ITEM(projections,j);
            if (!tuple_fields(projection,3) || !vector(PyTuple_GET_ITEM(projection,0),branch->gradients[j],9)
                || !vector(PyTuple_GET_ITEM(projection,1),branch->responses[j],9)) goto failed;
            branch->factors[j]=PyFloat_AsDouble(PyTuple_GET_ITEM(projection,2));
            if (PyErr_Occurred()) goto failed;
        }
        PyObject *response=PyTuple_GET_ITEM(local,0);
        int n=hard ? 4 : 3;
        if (!tuple_fields(response,n)) goto failed;
        for (int j=0; j<n; ++j) if (!vector(PyTuple_GET_ITEM(response,j),branch->port_response[j],n)) goto failed;
        PyObject *plans=PyTuple_GET_ITEM(shaft,1);
        if (!PyTuple_Check(plans) || PyTuple_GET_SIZE(plans)<1 || PyTuple_GET_SIZE(plans)>45) {
            PyErr_SetString(PyExc_ValueError,"实体轴有序分区数不一致"); goto failed;
        }
        branch->plan_count=(int)PyTuple_GET_SIZE(plans);
        for (int j=0; j<branch->plan_count; ++j) {
            SharedPortPlan *plan=&branch->plans[j];
            PyObject *source=PyTuple_GET_ITEM(plans,j);
            if (!tuple_fields(source,hard ? 4 : 2) || !vector(PyTuple_GET_ITEM(source,0),plan->modes,3)) goto failed;
            if (hard) {
                plan->sign=PyFloat_AsDouble(PyTuple_GET_ITEM(source,1));
                plan->slope=PyFloat_AsDouble(PyTuple_GET_ITEM(source,2));
                if (PyErr_Occurred()) goto failed;
            }
            if (!matrix_values(PyTuple_GET_ITEM(source,hard ? 3 : 1),&plan->columns[0][0],3,3)) goto failed;
        }
    }
    PyObject *result=PyCapsule_New(data,shared_map_name,release_shared_map);
    if (!result) goto failed;
    return result;
failed:
    PyMem_Free(data); return NULL;
}
static void shared_projection(const SharedBranch *branch,double values[9]) {
    double terms[9];
    for (int i=0; i<branch->projection_count; ++i) {
        for (int a=0; a<9; ++a) terms[a]=branch->gradients[i][a]*values[a];
        double scale=branch->factors[i]*compensated(terms,9);
        for (int a=0; a<9; ++a) values[a]=values[a]-scale*branch->responses[i][a];
    }
}
static void shared_branch_free(const SharedMap *data,const SharedBranch *branch,
                           const double free[9],const double active[3],double projected[9]) {
    for (int a=0; a<9; ++a) projected[a]=free[a];
    if (data->limited) {
        shared_projection(branch,projected);
        double offset[9];
        for (int a=0; a<9; ++a) offset[a]=data->bias ? 0. : branch->offset[a];
        if (data->bias) {
            for (int i=0; i<3; ++i) if (branch->modes[i]!=0.)
                for (int a=0; a<9; ++a) offset[a]=offset[a]-data->dt*branch->modes[i]*active[i]*data->differential_responses[i][a];
            shared_projection(branch,offset);
        }
        for (int a=0; a<9; ++a) projected[a]=projected[a]+offset[a];
    }
}
static int shared_branch_feasible(const SharedMap *data,const SharedBranch *branch,
                              const double end[9],const double active[3]) {
    double terms[9];
    int feasible=1;
    for (int i=0; i<3; ++i) {
        if (data->damping[i]==0. || active[i]==0.) continue;
        for (int a=0; a<9; ++a) terms[a]=data->differential[i][a]*end[a];
        double viscous=data->damping[i]*compensated(terms,9);
        double torque=branch->modes[i]!=0. ? branch->modes[i]*active[i] : viscous;
        double bounded=viscous<active[i] ? viscous : active[i];
        double expected=bounded > -active[i] ? bounded : -active[i];
        if (fabs(torque-expected)>PORT_TOLERANCE) { feasible=0; break; }
    }
    return feasible;
}
static int shared_port_state(const SharedMap *data,const SharedBranch *branch,const double free[4],
                             double brake_capacity,int warm,double values[4],int *index) {
    double speeds[4],reduced[3],gear_free=0.;
    const int ports[3]={0,2,3};
    if (data->hard) {
        gear_free=free[1]/(data->dt*branch->port_response[1][1]);
        for (int i=0; i<3; ++i) reduced[i]=free[ports[i]]-branch->port_response[ports[i]][1]*free[1]
                                                      /branch->port_response[1][1];
    }
    for (int visit=-1; visit<branch->plan_count; ++visit) {
        int k=visit<0 ? warm : visit;
        if (k<0 || (visit>=0 && k==warm)) continue;
        const SharedPortPlan *plan=&branch->plans[k];
        if (data->hard) {
            if (!shaft_trial(free,branch->port_response,data->dt,data->capacity,brake_capacity,data->efficiency,
                gear_free,reduced,plan->modes,plan->sign,plan->slope,plan->columns,values,speeds)) continue;
        } else {
            double capacities[3]={data->capacity,data->synchronizer,brake_capacity},rhs[3],terms[3],sync_values[3];
            for (int i=0; i<3; ++i) rhs[i]=plan->modes[i]==0. ? free[i]/data->dt : plan->modes[i]*capacities[i];
            for (int i=0; i<3; ++i) {
                for (int j=0; j<3; ++j) terms[j]=plan->columns[j][i]*rhs[j];
                sync_values[i]=compensated(terms,3);
            }
            int feasible=1;
            for (int i=0; i<3; ++i) {
                for (int j=0; j<3; ++j) terms[j]=branch->port_response[i][j]*sync_values[j];
                double speed=free[i]-data->dt*compensated(terms,3);
                if (fabs(sync_values[i])>capacities[i]+PORT_TOLERANCE
                    || (plan->modes[i]==0. ? fabs(speed)>PORT_TOLERANCE : plan->modes[i]*speed < -PORT_TOLERANCE)) feasible=0;
            }
            if (!feasible) continue;
            values[0]=sync_values[0]; values[1]=sync_values[1]; values[2]=0.; values[3]=sync_values[2];
        }
        *index=k; return 1;
    }
    PyErr_SetString(PyExc_ArithmeticError,data->hard ? "实体输入轴/离合/齿轮/制动共同末状态无可行解"
                                                  : "实体输入轴/离合/同步器/制动共同末状态无可行解");
    return 0;
}
static void shared_axle_torques(const SharedMap *data,const double state[11],double torques[2]) {
    double terms[9];
        double axial[3]={0.};
        if (data->downstream) for (int i=0; i<3; ++i) {
            for (int a=0; a<9; ++a) terms[a]=data->down_gradients[i][a]*state[a];
            axial[i]=data->inertias[i]*(compensated(terms,9)-data->old_omega[i])/data->dt;
        }
        double output=data->ratio*(state[9]-state[10]);
        torques[0]=data->share*output-data->final_drive*(data->share*axial[0]+axial[1]);
        torques[1]=(1-data->share)*output-data->final_drive*((1-data->share)*axial[0]+axial[2]);
}

static void shared_active_limits(const SharedMap *data,const double state[11],double active[3]) {
    for (int i=0; i<3; ++i) active[i]=data->limits[i];
    if (data->bias) {
        double torques[2];
        shared_axle_torques(data,state,torques);
        for (int i=0; i<2; ++i) if (data->biases[i]>1.) {
            double capacity=fabs(torques[i])*(data->biases[i]-1.)/(2*(data->biases[i]+1.));
            active[i]=capacity<data->limits[i] ? capacity : data->limits[i];
        }
    }
}

static int shared_map_values(SharedMap *data,const double state[11],const double angular[9],
    const double *normal,const double load[4],const double support[4],int warm,double output[11],
    double road[4],double active[3],double port_values[4],int *branch_output,int *port_output) {
    double momentum[3],gyro[3],free[9],terms[9],end[9];
    int suspension=normal!=NULL;
    for (int i=0; i<4; ++i) {road[i]=0.; port_values[i]=0.;}
    shared_active_limits(data,state,active);
    if (data->rolling) for (int i=0; i<4; ++i) if (support[i]!=0.) {
        double speed=fabs(data->radii[i]*state[i+5]);
        double denominator=speed>data->transition ? speed : data->transition;
        road[i]=data->rolling_coefficients[i]*load[i]*pow(data->radii[i],2.)*state[i+5]/denominator;
    }
    rotor_spin_values(&data->spin,state,momentum);
    gyro[0]=momentum[1]*state[2]-momentum[2]*state[1];
    gyro[1]=momentum[2]*state[0]-momentum[0]*state[2];
    gyro[2]=momentum[0]*state[1]-momentum[1]*state[0];
    known_values(&data->mass,data->base,gyro,angular,suspension ? normal : NULL,data->dt,
                 data->rolling ? road : NULL,free);
    int branch_index=-1,port_index=-1;
    for (int visit=-1; visit<data->branch_count; ++visit) {
        int index=visit<0 ? warm : visit;
        if (visit>=0 && index==warm) continue;
        const SharedBranch *branch=&data->branches[index];
        double projected[9];
        shared_branch_free(data,branch,free,active,projected);
        double port_free[4]={0.};
        for (int i=0; i<(data->hard ? 4 : 3); ++i) {
            for (int a=0; a<9; ++a) terms[a]=data->ports[i][a]*projected[a];
            port_free[i]=compensated(terms,9);
        }
        /* 暖索引仅属于本advance；每次仍检查实际容量、速度与原端口精度。 */
        if (!shared_port_state(data,branch,port_free,0.,data->port_seeds[index],port_values,&port_index)) return 0;
        data->port_seeds[index]=port_index;
        /* 输入轴上的离合/齿轮反力近乎抵消时，保留乘积低位再重建末速度。 */
        for (int a=0; a<9; ++a) {
            double updates[6],torques[3]={port_values[0],port_values[2],port_values[1]},
                responses[3]={branch->mc[a],branch->ml[a],branch->mg[a]};
            for (int j=0; j<3; ++j) {
                updates[2*j]=torques[j]*responses[j];
                updates[2*j+1]=fma(torques[j],responses[j],-updates[2*j]);
            }
            end[a]=fma(-data->dt,compensated(updates,6),projected[a]);
        }
        int feasible=shared_branch_feasible(data,branch,end,active);
        if (feasible) { branch_index=index; break; }
    }
    if (branch_index<0) { PyErr_SetString(PyExc_ArithmeticError,"限滑/离合共同末状态无可行分区"); return 0; }
    for (int a=0; a<(data->bias ? 11 : 9); ++a) output[a]=a<9 ? end[a] : port_values[a==9 ? 1 : 2];
    *branch_output=branch_index; *port_output=port_index;
    return 1;
}

static PyObject *shared_map_state(PyObject *self,PyObject *args,PyObject *kwargs) {
    PyObject *coefficients,*input,*loads,*wheel_loads,*supported;
    int warm;
    static char *names[]={"coefficients","state","loads","wheel_loads","supported","warm_branch",NULL};
    if (!PyArg_ParseTupleAndKeywords(args,kwargs,"OOOOOi",names,&coefficients,&input,&loads,&wheel_loads,&supported,&warm)) return NULL;
    SharedMap *data=PyCapsule_GetPointer(coefficients,shared_map_name);
    if (!data) return NULL;
    if (warm<0 || warm>=data->branch_count) { PyErr_SetString(PyExc_IndexError,"共同分区索引越界"); return NULL; }
    double state[11],angular[9],normal[9],load[4],support[4];
    double active[3],road[4],end[11],port_values[4];
    if (!vector(input,state,data->bias ? 11 : 9) || !tuple_fields(loads,3)
        || !vector(PyTuple_GET_ITEM(loads,0),angular,9)
        || !vector(wheel_loads,load,4) || !vector(supported,support,4)) return NULL;
    PyObject *normal_object=PyTuple_GET_ITEM(loads,1);
    if (!PyTuple_Check(normal_object)) { PyErr_SetString(PyExc_ValueError,"法向载荷须为元组"); return NULL; }
    int suspension=PyTuple_GET_SIZE(normal_object)!=0;
    if (suspension && !vector(normal_object,normal,9)) return NULL;
    int branch_index,port_index;
    if (!shared_map_values(data,state,angular,suspension ? normal : NULL,load,support,warm,
        end,road,active,port_values,&branch_index,&port_index)) return NULL;
    PyObject *result=PyTuple_New(data->bias ? 11 : 9);
    if (!result) return NULL;
    for (int a=0; a<(data->bias ? 11 : 9); ++a) {
        double value=a<9 ? end[a] : port_values[a==9 ? 1 : 2];
        PyObject *number=PyFloat_FromDouble(value);
        if (!number) { Py_DECREF(result); return NULL; }
        PyTuple_SET_ITEM(result,a,number);
    }
    return Py_BuildValue("(NOdddii(dddd)(ddd))",result,PyTuple_GET_ITEM(loads,2),
        port_values[0],port_values[2],port_values[1],branch_index,port_index,
        road[0],road[1],road[2],road[3],active[0],active[1],active[2]);
}


/* 同一活动分区的本构解析导数，不改变Newton或线搜索判据。 */
static void shared_jacobian_values(const SharedMap *data,const double state[11],const double load[4],
    const double support[4],int branch_index,int port_index,double columns[11][11]) {
    const SharedBranch *branch=&data->branches[branch_index];
    const SharedPortPlan *plan=&branch->plans[port_index];
    int variables=data->bias ? 11 : 9;
    double current_spin[3],derivatives[3][11]={{0.}},terms[9];
    rotor_spin_values(&data->spin,state,current_spin);
    if (data->bias) {
        double torques[2]; shared_axle_torques(data,state,torques);
        for (int axle=0; axle<2; ++axle) {
            double bias=data->biases[axle],weight=axle==0 ? data->share : 1-data->share;
            double coefficient=(bias-1.)/(2*(bias+1.));
            double slope=bias>1. && fabs(torques[axle])*coefficient<data->limits[axle]
                         ? copysign(coefficient,torques[axle]) : 0.;
            for (int j=0; j<variables; ++j)
                derivatives[axle][j]=slope*(weight*data->ratio*((double)(j==9)-(double)(j==10))
                    -(data->downstream && j<9 ? data->final_drive/data->dt
                      *(weight*data->inertias[0]*data->down_gradients[0][j]
                        +data->inertias[axle+1]*data->down_gradients[axle+1][j]) : 0.));
        }
    }
    for (int j=0; j<variables; ++j) {
        double gyro[3]={0.},input_response[9]={0.},direction[9];
        if (j<9) {
            const double *spin=data->spin_columns[j];
            gyro[0]=spin[1]*state[2]-spin[2]*state[1];
            gyro[1]=spin[2]*state[0]-spin[0]*state[2];
            gyro[2]=spin[0]*state[1]-spin[1]*state[0];
        }
        if (j<3) {
            double unit[3]={0.},second[3]; unit[j]=1.;
            second[0]=current_spin[1]*unit[2]-current_spin[2]*unit[1];
            second[1]=current_spin[2]*unit[0]-current_spin[0]*unit[2];
            second[2]=current_spin[0]*unit[1]-current_spin[1]*unit[0];
            for (int a=0; a<3; ++a) gyro[a]=gyro[a]+second[a];
        }
        for (int a=0; a<3; ++a) input_response[a]=gyro[a];
        mass_response_values(&data->mass,input_response,direction);
        if (data->rolling && j>=5 && j<9) {
            int i=j-5;
            double slope=support[i]!=0. && fabs(data->radii[i]*state[j])<data->transition
                ? data->rolling_coefficients[i]*load[i]*pow(data->radii[i],2.)/data->transition : 0.;
            double rolling_input[9]={0.},rolling_direction[9]; rolling_input[j]=-slope;
            mass_response_values(&data->mass,rolling_input,rolling_direction);
            for (int a=0; a<9; ++a) direction[a]=direction[a]+rolling_direction[a];
        }
        if (data->bias) for (int i=0; i<3; ++i) if (branch->modes[i]!=0.)
            for (int a=0; a<9; ++a) direction[a]=direction[a]-branch->modes[i]*derivatives[i][j]*data->differential_responses[i][a];
        shared_projection(branch,direction);
        double port_direction[4]={0.},dc,dg,dl;
        for (int i=0; i<(data->hard ? 4 : 3); ++i) {
            for (int a=0; a<9; ++a) terms[a]=data->ports[i][a]*direction[a];
            port_direction[i]=compensated(terms,9);
        }
        double rhs[3],values[3];
        if (data->hard) {
            const int ports[3]={0,2,3};
            double gear_free=port_direction[1]/branch->port_response[1][1],reduced[3];
            for (int i=0; i<3; ++i) reduced[i]=port_direction[ports[i]]-branch->port_response[ports[i]][1]*gear_free;
            rhs[0]=plan->modes[0]==0. ? reduced[0] : 0.;
            rhs[1]=plan->modes[1]==0. ? reduced[1] : plan->slope*gear_free;
            rhs[2]=plan->modes[2]==0. ? reduced[2] : 0.;
            for (int i=0; i<3; ++i) {
                for (int k=0; k<3; ++k) terms[k]=plan->columns[k][i]*rhs[k];
                values[i]=compensated(terms,3);
            }
            dc=values[0]; dl=values[1];
            for (int k=0; k<3; ++k) terms[k]=branch->port_response[1][ports[k]]*values[k]/branch->port_response[1][1];
            dg=gear_free-compensated(terms,3);
        } else {
            for (int i=0; i<3; ++i) rhs[i]=plan->modes[i]==0. ? port_direction[i] : 0.;
            for (int i=0; i<3; ++i) {
                for (int k=0; k<3; ++k) terms[k]=plan->columns[k][i]*rhs[k];
                values[i]=compensated(terms,3);
            }
            dc=values[0]; dg=values[1]; dl=0.;
        }
        for (int a=0; a<variables; ++a) {
            double end_column=a<9 ? data->dt*(direction[a]-dc*branch->mc[a]-dg*branch->mg[a]-dl*branch->ml[a])
                                 : (a==9 ? dg : dl);
            columns[j][a]=(double)(a==j)-end_column;
        }
    }
}

static PyObject *shared_map_jacobian(PyObject *self,PyObject *args,PyObject *kwargs) {
    PyObject *coefficients,*input,*wheel_loads,*supported;
    int branch_index,port_index;
    static char *names[]={"coefficients","state","wheel_loads","supported","branch_index","port_index",NULL};
    if (!PyArg_ParseTupleAndKeywords(args,kwargs,"OOOOii",names,&coefficients,&input,&wheel_loads,&supported,
                                    &branch_index,&port_index)) return NULL;
    SharedMap *data=PyCapsule_GetPointer(coefficients,shared_map_name);
    if (!data) return NULL;
    if (branch_index<0 || branch_index>=data->branch_count) {
        PyErr_SetString(PyExc_IndexError,"共同分区索引越界"); return NULL;
    }
    SharedBranch *branch=&data->branches[branch_index];
    if (port_index<0 || port_index>=branch->plan_count) {
        PyErr_SetString(PyExc_IndexError,"共同端口索引越界"); return NULL;
    }
    int variables=data->bias ? 11 : 9;
    double state[11],load[4],support[4];
    if (!vector(input,state,variables) || !vector(wheel_loads,load,4) || !vector(supported,support,4)) return NULL;
    double numeric[11][11];
    shared_jacobian_values(data,state,load,support,branch_index,port_index,numeric);
    PyObject *columns=PyList_New(variables);
    if (!columns) return NULL;
    for (int j=0; j<variables; ++j) {
        PyObject *column=PyTuple_New(variables);
        if (!column) {Py_DECREF(columns); return NULL;}
        for (int a=0; a<variables; ++a) {
            PyObject *value=PyFloat_FromDouble(numeric[j][a]);
            if (!value) {Py_DECREF(column); Py_DECREF(columns); return NULL;}
            PyTuple_SET_ITEM(column,a,value);
        }
        PyList_SET_ITEM(columns,j,column);
    }
    return columns;
}

/* 局部轮力与端口分区共用原共同映射判据，暖模式按每次尝试直接更新。 */
typedef struct {
    SharedBranch ports;
    double force_responses[2][9];
} WheelBranch;
typedef struct {
    PyObject *shared_owner;
    SharedMap *shared;
    LoadCoefficients load;
    double brake_gradients[4][9],brakes[4];
    WheelBranch local[];
} WheelMap;
static const char *wheel_map_name="CoastalDrive.wheel_map";
static void release_wheel_map(PyObject *object) {
    WheelMap *data=PyCapsule_GetPointer(object,wheel_map_name);
    Py_DECREF(data->shared_owner);
    PyMem_Free(data);
}
static PyObject *wheel_map_coefficients(PyObject *self,PyObject *args) {
    PyObject *shared_object,*load_object,*branches,*gradients,*brakes;
    if (!PyArg_ParseTuple(args,"OOOOO",&shared_object,&load_object,&branches,&gradients,&brakes)) return NULL;
    SharedMap *shared=PyCapsule_GetPointer(shared_object,shared_map_name);
    LoadCoefficients *load=PyCapsule_GetPointer(load_object,load_coefficients_name);
    if (!shared || !load) return NULL;
    WheelMap *data=PyMem_Calloc(1,sizeof(WheelMap)+4*shared->branch_count*sizeof(WheelBranch));
    if (!data) return PyErr_NoMemory();
    data->shared=shared; data->load=*load;
    if (!matrix_values(gradients,&data->brake_gradients[0][0],4,9) || !vector(brakes,data->brakes,4)) goto failed;
    for (int b=0; b<shared->branch_count; ++b) {
        PyObject *input=PyTuple_GET_ITEM(branches,b);
        PyObject *responses=PyTuple_GET_ITEM(input,5),*all_plans=PyTuple_GET_ITEM(input,6);
        for (int w=0; w<4; ++w) {
            WheelBranch *wheel_branch=&data->local[4*b+w];
            SharedBranch *local=&wheel_branch->ports;
            PyObject *wheel=PyTuple_GET_ITEM(PyTuple_GET_ITEM(input,4),w);
            for (int j=0; j<2; ++j)
                if (!vector(PyTuple_GET_ITEM(wheel,j),wheel_branch->force_responses[j],9)) goto failed;
            int n=shared->hard ? 4 : 3;
            for (int j=0; j<n; ++j)
                if (!vector(PyTuple_GET_ITEM(PyTuple_GET_ITEM(responses,w),j),local->port_response[j],n)) goto failed;
            PyObject *plans=PyTuple_GET_ITEM(all_plans,w);
            local->plan_count=(int)PyTuple_GET_SIZE(plans);
            for (int j=0; j<local->plan_count; ++j) {
                PyObject *source=PyTuple_GET_ITEM(plans,j);
                SharedPortPlan *plan=&local->plans[j];
                if (!vector(PyTuple_GET_ITEM(source,0),plan->modes,3)) goto failed;
                if (shared->hard) {
                    plan->sign=PyFloat_AsDouble(PyTuple_GET_ITEM(source,1));
                    plan->slope=PyFloat_AsDouble(PyTuple_GET_ITEM(source,2));
                    if (PyErr_Occurred()) goto failed;
                }
                if (!matrix_values(PyTuple_GET_ITEM(source,shared->hard ? 3 : 1),&plan->columns[0][0],3,3)) goto failed;
            }
            if (!vector(PyTuple_GET_ITEM(wheel,2),local->mc,9)) goto failed;
        }
    }
    Py_INCREF(shared_object); data->shared_owner=shared_object;
    PyObject *result=PyCapsule_New(data,wheel_map_name,release_wheel_map);
    if (!result) { Py_DECREF(shared_object); goto failed; }
    return result;
failed:
    PyMem_Free(data); return NULL;
}
/* 四轮制动共用当前端口分区；饱和行和相关约束保留原消元顺序。 */
static PyObject *wheel_brake_correction(PyObject *self,PyObject *args) {
    PyObject *coefficients,*state_object,*forces_object;
    int branch_index,port_index;
    if (!PyArg_ParseTuple(args,"OOOii",&coefficients,&state_object,&forces_object,&branch_index,&port_index)) return NULL;
    WheelMap *packet=PyCapsule_GetPointer(coefficients,wheel_map_name);
    if (!packet) return NULL;
    SharedMap *data=packet->shared;
    if (branch_index<0 || branch_index>=data->branch_count) {
        PyErr_SetString(PyExc_IndexError,"制动修正分区索引越界"); return NULL;
    }
    SharedBranch *branch=&data->branches[branch_index];
    if (port_index<0 || port_index>=branch->plan_count) {
        PyErr_SetString(PyExc_IndexError,"制动修正端口索引越界"); return NULL;
    }
    SharedPortPlan *plan=&branch->plans[port_index];
    double state[9],forces[4][3],corrections[4][9],rows[4][5],terms[9];
    if (!vector(state_object,state,9) || !matrix_values(forces_object,&forces[0][0],4,3)) return NULL;
    for (int wheel=0;wheel<4;++wheel) {
        const double *rb=packet->local[4*branch_index+wheel].ports.mc;
        double direction[4],rhs[3],output[3],dc,dg,dl;
        int n=data->hard ? 4 : 3;
        for (int i=0;i<n;++i) {
            const double *gradient=i==n-1 ? packet->brake_gradients[0] : data->ports[i];
            for (int a=0;a<9;++a) terms[a]=gradient[a]*rb[a];
            direction[i]=compensated(terms,9);
        }
        if (data->hard) {
            const int ports[3]={0,2,3};
            double gear_free=direction[1]/branch->port_response[1][1],reduced[3];
            for (int i=0;i<3;++i)
                reduced[i]=direction[ports[i]]-branch->port_response[ports[i]][1]*gear_free;
            rhs[0]=plan->modes[0]==0. ? reduced[0] : 0.;
            rhs[1]=plan->modes[1]==0. ? reduced[1] : plan->slope*gear_free;
            rhs[2]=plan->modes[2]==0. ? reduced[2] : 0.;
            for (int i=0;i<3;++i) {
                for (int j=0;j<3;++j) terms[j]=plan->columns[j][i]*rhs[j];
                output[i]=compensated(terms,3);
            }
            dc=output[0]; dl=output[1];
            for (int j=0;j<3;++j)
                terms[j]=branch->port_response[1][ports[j]]*output[j]/branch->port_response[1][1];
            dg=gear_free-compensated(terms,3);
        } else {
            for (int i=0;i<3;++i) rhs[i]=plan->modes[i]==0. ? direction[i] : 0.;
            for (int i=0;i<3;++i) {
                for (int j=0;j<3;++j) terms[j]=plan->columns[j][i]*rhs[j];
                output[i]=compensated(terms,3);
            }
            dc=output[0]; dg=output[1]; dl=0.;
        }
        for (int a=0;a<9;++a)
            corrections[wheel][a]=rb[a]-dc*branch->mc[a]-dg*branch->mg[a]-dl*branch->ml[a];
    }
    double largest=0.;
    for (int i=0;i<4;++i) {
        const double *gradient=packet->brake_gradients[i],*response=packet->load.responses+27*i+18;
        for (int a=0;a<9;++a) terms[a]=gradient[a]*state[a];
        double speed=compensated(terms,9);
        for (int a=0;a<9;++a) terms[a]=gradient[a]*response[a];
        double diagonal=compensated(terms,9);
        double demand=forces[i][2]+speed/(data->dt*diagonal);
        if (fabs(demand)<packet->brakes[i]) {
            for (int j=0;j<4;++j) {
                for (int a=0;a<9;++a) terms[a]=gradient[a]*corrections[j][a];
                rows[i][j]=compensated(terms,9);
            }
            rows[i][4]=speed/data->dt;
        } else {
            double target=demand<packet->brakes[i] ? demand : packet->brakes[i];
            if (target < -packet->brakes[i]) target=-packet->brakes[i];
            for (int j=0;j<4;++j) rows[i][j]=(double)(i==j);
            rows[i][4]=target-forces[i][2];
        }
        for (int j=0;j<4;++j) if (fabs(rows[i][j])>largest) largest=fabs(rows[i][j]);
    }
    double rounding=16*(nextafter(largest,INFINITY)-largest);
    int pivot_rows[4],pivot_columns[4],row=0;
    for (int column=0;column<4;++column) {
        int pivot=row;
        for (int i=row+1;i<4;++i) if (fabs(rows[i][column])>fabs(rows[pivot][column])) pivot=i;
        if (fabs(rows[pivot][column])<=rounding) continue;
        for (int j=0;j<5;++j) {
            double value=rows[row][j]; rows[row][j]=rows[pivot][j]; rows[pivot][j]=value;
        }
        double scale=rows[row][column];
        for (int j=0;j<5;++j) rows[row][j]=rows[row][j]/scale;
        for (int i=0;i<4;++i) if (i!=row) {
            double factor=rows[i][column];
            for (int j=0;j<5;++j) rows[i][j]=rows[i][j]-factor*rows[row][j];
        }
        pivot_rows[row]=row; pivot_columns[row]=column;
        if (++row==4) break;
    }
    double delta[4]={0.};
    for (int i=0;i<row;++i) delta[pivot_columns[i]]=rows[pivot_rows[i]][4];
    return Py_BuildValue("((ddd)(ddd)(ddd)(ddd))",
        forces[0][0],forces[0][1],forces[0][2]+delta[0],forces[1][0],forces[1][1],forces[1][2]+delta[1],
        forces[2][0],forces[2][1],forces[2][2]+delta[2],forces[3][0],forces[3][1],forces[3][2]+delta[3]);
}

static PyObject *wheel_free_state(PyObject *self,PyObject *args) {
    PyObject *coefficients,*forces,*velocity,*normal_forces,*normal_responses,*gradients,*gyro_object,*road_object;
    int exclude;
    if (!PyArg_ParseTuple(args,"OOOOOOOOi",&coefficients,&forces,&velocity,&normal_forces,&normal_responses,
        &gradients,&gyro_object,&road_object,&exclude)) return NULL;
    WheelMap *packet=PyCapsule_GetPointer(coefficients,wheel_map_name);
    if (!packet) return NULL;
    double angular[9],normal[9],end_velocity[3],gyro[3],road[4],state[9];
    if (!wheel_load_values(&packet->load,forces,velocity,normal_forces,normal_responses,gradients,exclude,
        angular,normal,end_velocity) || !vector(gyro_object,gyro,3)
        || (road_object!=Py_None && !vector(road_object,road,4))) return NULL;
    SharedMap *data=packet->shared;
    known_values(&data->mass,data->base,gyro,angular,normal_forces!=Py_None ? normal : NULL,
        data->dt,road_object!=Py_None ? road : NULL,state);
    PyObject *result=PyTuple_New(9);
    if (!result) return NULL;
    for (int a=0;a<9;++a) {
        PyObject *value=PyFloat_FromDouble(state[a]);
        if (!value) { Py_DECREF(result); return NULL; }
        PyTuple_SET_ITEM(result,a,value);
    }
    return Py_BuildValue("(N(ddd))",result,end_velocity[0],end_velocity[1],end_velocity[2]);
}
static int wheel_map_values(WheelMap *packet,int wheel,const double base[9],const double base_velocity[3],
    double fx,double fy,const double active[3],int warm,PyObject *warm_modes,const double tangent[3],const double axle[3],
    double end[9],double velocity[3],double *brake,int *branch_index,int *mode_index) {
    SharedMap *data=packet->shared;
    double free[9],terms[9],values[4];
    for (int a=0;a<9;++a) free[a]=base[a];
    for (int a=0;a<3;++a) velocity[a]=base_velocity[a];
    const double *rx=packet->load.responses+27*wheel,*ry=rx+9;
    for (int a=0; a<9; ++a) free[a]=free[a]+data->dt*(rx[a]*fx+ry[a]*fy);
    int selected=-1,port_index=-1;
    for (int visit=-1; visit<data->branch_count; ++visit) {
        int index=visit<0 ? warm : visit;
        if (visit>=0 && index==warm) continue;
        SharedBranch *branch=&data->branches[index],*local=&packet->local[4*index+wheel].ports;
        double projected[9];
        shared_branch_free(data,branch,free,active,projected);
        double port_free[4]={0.};
        int n=data->hard ? 4 : 3;
        for (int i=0; i<n; ++i) {
            const double *gradient=i==n-1 ? packet->brake_gradients[wheel] : data->ports[i];
            for (int a=0; a<9; ++a) terms[a]=gradient[a]*projected[a];
            port_free[i]=compensated(terms,9);
        }
        PyObject *warm_row=PyList_GET_ITEM(warm_modes,index),*old=PyList_GET_ITEM(warm_row,wheel);
        int mode=old==Py_None ? -1 : (int)PyLong_AsLong(old);
        if (PyErr_Occurred() || !shared_port_state(data,local,port_free,packet->brakes[wheel],mode,values,&port_index)) return 0;
        PyObject *updated=PyLong_FromLong(port_index);
        if (!updated || PyList_SetItem(warm_row,wheel,updated)<0) return 0;
        for (int a=0; a<9; ++a) end[a]=projected[a]-data->dt*(values[0]*branch->mc[a]+values[2]*branch->ml[a]
                                                       +values[3]*local->mc[a]+values[1]*branch->mg[a]);
        int feasible=shared_branch_feasible(data,branch,end,active);
        if (feasible) { selected=index; break; }
    }
    if (selected<0) { PyErr_SetString(PyExc_ArithmeticError,"限滑/离合/制动共同末状态无可行分区"); return 0; }
    for (int a=0; a<3; ++a) velocity[a]=velocity[a]+data->dt/packet->load.mass*(fx*tangent[a]+fy*axle[a]);
    *brake=values[3]; *branch_index=selected; *mode_index=port_index;
    return 1;
}
static PyObject *wheel_map_state(PyObject *self,PyObject *args) {
    PyObject *coefficients,*base_object,*velocity_object,*limits_object,*warm_modes,*tangent_object,*axle_object;
    int wheel,warm;
    double fx,fy;
    if (!PyArg_ParseTuple(args,"OiOOddOiOOO",&coefficients,&wheel,&base_object,&velocity_object,&fx,&fy,
                         &limits_object,&warm,&warm_modes,&tangent_object,&axle_object)) return NULL;
    WheelMap *packet=PyCapsule_GetPointer(coefficients,wheel_map_name);
    if (!packet) return NULL;
    double base[9],base_velocity[3],active[3],tangent[3],axle[3],end[9],velocity[3],brake;
    int selected,port_index;
    if (!vector(base_object,base,9) || !vector(velocity_object,base_velocity,3) || !vector(limits_object,active,3)
        || !vector(tangent_object,tangent,3) || !vector(axle_object,axle,3)) return NULL;
    if (!wheel_map_values(packet,wheel,base,base_velocity,fx,fy,active,warm,warm_modes,tangent,axle,
                          end,velocity,&brake,&selected,&port_index)) return NULL;
    PyObject *state=PyTuple_New(9);
    if (!state) return NULL;
    for (int a=0; a<9; ++a) {
        PyObject *number=PyFloat_FromDouble(end[a]);
        if (!number) { Py_DECREF(state); return NULL; }
        PyTuple_SET_ITEM(state,a,number);
    }
    return Py_BuildValue("(N(ddd)d(ii))",state,velocity[0],velocity[1],velocity[2],brake,selected,port_index);
}


/* 同一轮端活动分区的完整解析导数；输入末状态来自原轮力映射。 */
static int wheel_derivative_values(WheelMap *packet,int wheel,int branch_index,int port_index,
    const double state[9],const double velocity[3],const double moment_x[3],const double moment_y[3],double radius,
    const double tangent[3],const double axle[3],double speed[2],double slip[2],double gradients[2][3]) {
    SharedMap *data=packet->shared;
    if (wheel<0 || wheel>=4 || branch_index<0 || branch_index>=data->branch_count) {
        PyErr_SetString(PyExc_IndexError,"轮端导数分区索引越界"); return 0;
    }
    WheelBranch *wheel_branch=&packet->local[4*branch_index+wheel];
    SharedBranch *branch=&data->branches[branch_index],*local=&wheel_branch->ports;
    if (port_index<0 || port_index>=local->plan_count) {
        PyErr_SetString(PyExc_IndexError,"轮端导数端口索引越界"); return 0;
    }
    SharedPortPlan *plan=&local->plans[port_index];
    double terms[9];
    for (int a=0; a<3; ++a) terms[a]=velocity[a]*tangent[a];
    double vx=compensated(terms,3);
    for (int a=0; a<3; ++a) terms[a]=state[a]*moment_x[a];
    vx=vx+compensated(terms,3);
    for (int a=0; a<3; ++a) terms[a]=velocity[a]*axle[a];
    double vy=compensated(terms,3);
    for (int a=0; a<3; ++a) terms[a]=state[a]*moment_y[a];
    vy=vy+compensated(terms,3);
    for (int column=0; column<2; ++column) {
        const double *response=wheel_branch->force_responses[column];
        const double *direction=column==0 ? tangent : axle;
        double port_direction[4],rhs[3],dc,dg,dl,db;
        int n=data->hard ? 4 : 3;
        for (int i=0; i<n; ++i) {
            const double *g=i==n-1 ? packet->brake_gradients[wheel] : data->ports[i];
            for (int a=0; a<9; ++a) terms[a]=g[a]*response[a];
            port_direction[i]=compensated(terms,9);
        }
        if (data->hard) {
            int ports[3]={0,2,3};
            double gear_free=port_direction[1]/local->port_response[1][1],reduced[3],output[3];
            for (int j=0; j<3; ++j) reduced[j]=port_direction[ports[j]]-local->port_response[ports[j]][1]*gear_free;
            rhs[0]=plan->modes[0]==0. ? reduced[0] : 0.;
            rhs[1]=plan->modes[1]==0. ? reduced[1] : plan->slope*gear_free;
            rhs[2]=plan->modes[2]==0. ? reduced[2] : 0.;
            for (int a=0; a<3; ++a) {
                for (int j=0; j<3; ++j) terms[j]=plan->columns[j][a]*rhs[j];
                output[a]=compensated(terms,3);
            }
            dc=output[0]; dl=output[1]; db=output[2];
            for (int j=0; j<3; ++j) terms[j]=local->port_response[1][ports[j]]*output[j]/local->port_response[1][1];
            dg=gear_free-compensated(terms,3);
        } else {
            double output[3];
            for (int j=0; j<3; ++j) rhs[j]=plan->modes[j]==0. ? port_direction[j] : 0.;
            for (int a=0; a<3; ++a) {
                for (int j=0; j<3; ++j) terms[j]=plan->columns[j][a]*rhs[j];
                output[a]=compensated(terms,3);
            }
            dc=output[0]; dg=output[1]; db=output[2]; dl=0.;
        }
        double dq[9];
        for (int a=0; a<9; ++a) dq[a]=data->dt*(response[a]-dc*branch->mc[a]-dl*branch->ml[a]-db*local->mc[a]-dg*branch->mg[a]);
        for (int a=0; a<3; ++a) terms[a]=direction[a]*tangent[a];
        double dx=data->dt/packet->load.mass*compensated(terms,3);
        for (int a=0; a<3; ++a) terms[a]=dq[a]*moment_x[a];
        dx=dx+compensated(terms,3);
        for (int a=0; a<3; ++a) terms[a]=direction[a]*axle[a];
        double dy=data->dt/packet->load.mass*compensated(terms,3);
        for (int a=0; a<3; ++a) terms[a]=dq[a]*moment_y[a];
        dy=dy+compensated(terms,3);
        gradients[column][0]=radius*dq[wheel+5]-dx;
        gradients[column][1]=-dy; gradients[column][2]=dx;
    }
    speed[0]=vx; speed[1]=vy; slip[0]=radius*state[wheel+5]-vx; slip[1]=-vy;
    return 1;
}
static PyObject *wheel_map_derivatives(PyObject *self,PyObject *args) {
    PyObject *coefficients,*state_object,*velocity_object,*moment_x_object,*moment_y_object,*tangent_object,*axle_object;
    int wheel,branch_index,port_index;
    double radius;
    if (!PyArg_ParseTuple(args,"OiiiOOOOdOO",&coefficients,&wheel,&branch_index,&port_index,
        &state_object,&velocity_object,&moment_x_object,&moment_y_object,&radius,&tangent_object,&axle_object)) return NULL;
    WheelMap *packet=PyCapsule_GetPointer(coefficients,wheel_map_name);
    if (!packet) return NULL;
    double state[9],velocity[3],moment_x[3],moment_y[3],tangent[3],axle[3],speed[2],slip[2],gradients[2][3];
    if (!vector(state_object,state,9) || !vector(velocity_object,velocity,3)
        || !vector(moment_x_object,moment_x,3) || !vector(moment_y_object,moment_y,3)
        || !vector(tangent_object,tangent,3) || !vector(axle_object,axle,3)) return NULL;
    if (!wheel_derivative_values(packet,wheel,branch_index,port_index,state,velocity,moment_x,moment_y,radius,
                                 tangent,axle,speed,slip,gradients)) return NULL;
    return Py_BuildValue("(dd(dd)[(ddd)(ddd)])",speed[0],speed[1],slip[0],slip[1],
        gradients[0][0],gradients[0][1],gradients[0][2],gradients[1][0],gradients[1][1],gradients[1][2]);
}

/* 原四轮接触/阻尼/止挡活动集；分区次序、64轮与精度保持。 */
static int suspension_contact_values(const double compression[4],const double speed[4],const double mobility[16],
    const double touching[4],const double stiffness[16],const double cd[4],const double ed[4],const double stops[4],
    double travel,double dt,const double geometry[4],double end[4],double forces[4],double raw[4],double damping[4]) {
    double bound[4],terms[9],partials[9];
    int modes[4],stop_modes[4],zero_mobility=1,converged=0;
    for (int i=0; i<16; ++i) if (mobility[i]!=0.) zero_mobility=0;
    for (int i=0; i<4; ++i) {
        modes[i]=touching[i]!=0.; damping[i]=speed[i]<0. ? cd[i] : ed[i];
        stop_modes[i]=compression[i]>travel ? 1 : compression[i]<-travel ? -1 : 0;
        bound[i]=stop_modes[i]*travel;
    }
    /* 零迁移率且四轮受压时，接触约束已直接指定四个末行程，无须八维LU。 */
    if (zero_mobility && modes[0] && modes[1] && modes[2] && modes[3]) {
        double direct_end[4],direct_damping[4],direct_raw[4];
        int admissible=1;
        for (int i=0; i<4; ++i) {
            direct_end[i]=geometry[i]-dt*speed[i];
            direct_damping[i]=direct_end[i]>=compression[i] ? cd[i] : ed[i];
        }
        for (int i=0; i<4; ++i) {
            int stop=direct_end[i]>travel ? 1 : direct_end[i]<-travel ? -1 : 0;
            for (int j=0; j<4; ++j) {
                double k=stiffness[i*4+j];
                terms[j]=fma(-k*dt,speed[j],k*geometry[j]);
            }
            terms[4]=fma(-direct_damping[i],speed[i],direct_damping[i]*(geometry[i]-compression[i])/dt);
            terms[5]=stop ? fma(-stops[i]*dt,speed[i],stops[i]*(geometry[i]-stop*travel)) : 0.;
            direct_raw[i]=exact_sum(terms,6,partials);
            if (!(direct_raw[i]>=0.)) admissible=0;
        }
        if (PyErr_Occurred()) return 0;
        if (admissible) {
            for (int i=0;i<4;++i) {
                end[i]=direct_end[i]; forces[i]=raw[i]=direct_raw[i]; damping[i]=direct_damping[i];
            }
            return 1;
        }
    }
    for (int iteration=0; iteration<64; ++iteration) {
        double system[16],rhs[4],equations[64]={0.},values[8],rows[64],solution[8],residual[8],correction[8];
        Py_ssize_t order[8];
        for (int i=0; i<16; ++i) system[i]=stiffness[i];
        for (int i=0; i<4; ++i) {
            system[4*i+i]+=damping[i]/dt+(stop_modes[i] ? stops[i] : 0.);
            rhs[i]=damping[i]*compression[i]/dt+(stop_modes[i] ? stops[i]*bound[i] : 0.);
            for (int j=0; j<4; ++j) {
                if (!modes[i]) {
                    equations[(2*i)*8+j]=system[i*4+j];
                    equations[(2*i+1)*8+j+4]=(double)(i==j);
                } else {
                    equations[(2*i)*8+j]=(double)(i==j);
                    equations[(2*i)*8+j+4]=dt*dt*mobility[i*4+j];
                    equations[(2*i+1)*8+j]=-system[i*4+j];
                    equations[(2*i+1)*8+j+4]=(double)(i==j);
                }
            }
            values[2*i]=modes[i] ? geometry[i]-dt*speed[i] : rhs[i];
            values[2*i+1]=modes[i] ? -rhs[i] : 0.;
        }
        if (!lu_values(equations,values,8,rows,order,solution,residual,correction,terms,partials)) return 0;
        for (int i=0; i<4; ++i) {end[i]=solution[i]; forces[i]=solution[i+4];}
        int next_modes[4],next_stops[4],same=1;
        double next_damping[4];
        for (int i=0; i<4; ++i) {
            for (int j=0; j<4; ++j) terms[j]=stiffness[i*4+j]*end[j];
            terms[4]=damping[i]*(end[i]-compression[i])/dt;
            terms[5]=stop_modes[i] ? stops[i]*(end[i]-bound[i]) : 0.;
            raw[i]=exact_sum(terms,6,partials);
            for (int j=0; j<4; ++j) terms[j]=mobility[i*4+j]*forces[j];
            double target=geometry[i]-dt*speed[i]-dt*dt*compensated(terms,4);
            next_modes[i]=modes[i];
            if (!modes[i] && touching[i]!=0. && end[i]<target-1e-10) next_modes[i]=1;
            else if (modes[i] && forces[i]<-1e-7) next_modes[i]=0;
            next_damping[i]=end[i]>=compression[i] ? cd[i] : ed[i];
            next_stops[i]=end[i]>travel ? 1 : end[i]<-travel ? -1 : 0;
            if (next_modes[i]!=modes[i] || next_damping[i]!=damping[i] || next_stops[i]!=stop_modes[i]) same=0;
        }
        if (PyErr_Occurred()) return 0;
        if (same) {
            if (zero_mobility) for (int i=0; i<4; ++i) {
                if (modes[i]) {
                    for (int j=0; j<4; ++j) {
                        double k=stiffness[i*4+j];
                        terms[j]=modes[j] ? fma(-k*dt,speed[j],k*geometry[j]) : k*end[j];
                    }
                    terms[4]=fma(-damping[i],speed[i],damping[i]*(geometry[i]-compression[i])/dt);
                    terms[5]=stop_modes[i] ? fma(-stops[i]*dt,speed[i],stops[i]*(geometry[i]-bound[i])) : 0.;
                    raw[i]=exact_sum(terms,6,partials);
                }
                forces[i]=modes[i] ? raw[i] : 0.;
            }
            converged=1; break;
        }
        for (int i=0; i<4; ++i) {
            modes[i]=next_modes[i]; damping[i]=next_damping[i]; stop_modes[i]=next_stops[i]; bound[i]=stop_modes[i]*travel;
        }
    }
    if (PyErr_Occurred()) return 0;
    if (!converged) {PyErr_SetString(PyExc_ArithmeticError,"悬架接触/阻尼/止挡活动集未收敛"); return 0;}
    return 1;
}

static PyObject *suspension_contact_state(PyObject *self,PyObject *args) {
    PyObject *compression_object,*speed_object,*mobility_object,*touching_object,*stiffness_object;
    PyObject *compression_damping_object,*extension_damping_object,*stops_object,*geometry_object;
    double travel,dt;
    if (!PyArg_ParseTuple(args,"OOOOOOOOddO",&compression_object,&speed_object,&mobility_object,
        &touching_object,&stiffness_object,&compression_damping_object,&extension_damping_object,
        &stops_object,&travel,&dt,&geometry_object)) return NULL;
    double compression[4],speed[4],mobility[16],touching[4],stiffness[16],cd[4],ed[4],stops[4],geometry[4];
    if (!vector(compression_object,compression,4) || !vector(speed_object,speed,4)
        || !matrix_values(mobility_object,mobility,4,4) || !vector(touching_object,touching,4)
        || !matrix_values(stiffness_object,stiffness,4,4) || !vector(compression_damping_object,cd,4)
        || !vector(extension_damping_object,ed,4) || !vector(stops_object,stops,4)
        || !vector(geometry_object,geometry,4)) return NULL;
    double end[4],forces[4],raw[4],damping[4];
    if (!suspension_contact_values(compression,speed,mobility,touching,stiffness,cd,ed,stops,travel,dt,geometry,
                                   end,forces,raw,damping)) return NULL;
    return Py_BuildValue("((dddd)(dddd)(dddd)(dddd))",end[0],end[1],end[2],end[3],
        forces[0],forces[1],forces[2],forces[3],raw[0],raw[1],raw[2],raw[3],
        damping[0],damping[1],damping[2],damping[3]);
}

/* 一个advance的材料状态和硬件固定；迭代只求反力，末状态再记完整能量账。 */
typedef struct {
    double compression[4],geometry[4],stiffness[16],cd[4],ed[4],stops[4],travel,dt;
} SuspensionCoefficients;
static const char *suspension_coefficients_name="coastaldrive.suspension_coefficients";
static void release_suspension_coefficients(PyObject *object) {
    PyMem_Free(PyCapsule_GetPointer(object,suspension_coefficients_name));
}
static PyObject *suspension_coefficients(PyObject *self,PyObject *args) {
    PyObject *compression,*geometry,*rates_object,*cd,*ed,*bars_object,*stops;
    double travel,dt,rates[4],bars[2];
    if (!PyArg_ParseTuple(args,"OOOOOOOdd",&compression,&geometry,&rates_object,&cd,&ed,&bars_object,&stops,&travel,&dt)) return NULL;
    SuspensionCoefficients *data=PyMem_Calloc(1,sizeof(SuspensionCoefficients));
    if (!data) return PyErr_NoMemory();
    data->travel=travel; data->dt=dt;
    if (!vector(compression,data->compression,4) || !vector(geometry,data->geometry,4)
        || !vector(rates_object,rates,4) || !vector(cd,data->cd,4) || !vector(ed,data->ed,4)
        || !vector(bars_object,bars,2) || !vector(stops,data->stops,4)) { PyMem_Free(data); return NULL; }
    for (int i=0;i<4;++i) data->stiffness[4*i+i]=rates[i];
    for (int axle=0;axle<2;++axle) {
        int left=2*axle,right=left+1;
        data->stiffness[4*left+left]+=bars[axle]; data->stiffness[4*right+right]+=bars[axle];
        data->stiffness[4*left+right]-=bars[axle]; data->stiffness[4*right+left]-=bars[axle];
    }
    PyObject *result=PyCapsule_New(data,suspension_coefficients_name,release_suspension_coefficients);
    if (!result) PyMem_Free(data);
    return result;
}
static PyObject *suspension_forces(PyObject *self,PyObject *args) {
    PyObject *coefficients,*gradients_object,*velocity_object,*angular_object,*touching_object,*mobility_object,*forces_object;
    if (!PyArg_ParseTuple(args,"OOOOOOO",&coefficients,&gradients_object,&velocity_object,&angular_object,
        &touching_object,&mobility_object,&forces_object)) return NULL;
    SuspensionCoefficients *data=PyCapsule_GetPointer(coefficients,suspension_coefficients_name);
    if (!data) return NULL;
    double gradients[24],velocity[3],angular[3],touching[4],mobility[16]={0.},previous[4],speed[4],terms[6];
    if (!matrix_values(gradients_object,gradients,4,6) || !vector(velocity_object,velocity,3)
        || !vector(angular_object,angular,3) || !vector(touching_object,touching,4)
        || (mobility_object!=Py_None && !matrix_values(mobility_object,mobility,4,4))
        || !vector(forces_object,previous,4)) return NULL;
    for (int i=0;i<4;++i) {
        for (int a=0;a<6;++a) terms[a]=gradients[6*i+a]*(a<3 ? velocity[a] : angular[a-3]);
        double free=compensated(terms,6);
        for (int j=0;j<4;++j) terms[j]=mobility[4*i+j]*previous[j];
        speed[i]=free-data->dt*compensated(terms,4);
    }
    double end[4],forces[4],raw[4],damping[4];
    if (!suspension_contact_values(data->compression,speed,mobility,touching,data->stiffness,data->cd,data->ed,data->stops,
        data->travel,data->dt,data->geometry,end,forces,raw,damping)) return NULL;
    return Py_BuildValue("(dddd)",forces[0],forces[1],forces[2],forces[3]);
}

/* 同一悬架势能、硬件梯度与离散能量账；保留原乘法/求和次序。 */
static void suspension_elastic_values(const double compression[4],const double rates[4],const double bars[2],
    const double stops[4],double travel,double *spring,double bar[2],double *stop,double force[4]) {
    double matrix[16]={0.},terms[4],excess[4];
    for (int i=0; i<4; ++i) {
        matrix[i*4+i]=rates[i];
        terms[i]=rates[i]*compression[i]*compression[i]/2;
        double bounded=compression[i]<travel ? compression[i] : travel;
        bounded=bounded>-travel ? bounded : -travel;
        excess[i]=compression[i]-bounded;
    }
    *spring=compensated(terms,4);
    for (int axle=0; axle<2; ++axle) {
        int left=2*axle,right=left+1;
        matrix[left*4+left]+=bars[axle]; matrix[right*4+right]+=bars[axle];
        matrix[left*4+right]-=bars[axle]; matrix[right*4+left]-=bars[axle];
        bar[axle]=bars[axle]*pow(compression[left]-compression[right],2.)/2;
    }
    for (int i=0; i<4; ++i) terms[i]=stops[i]*excess[i]*excess[i]/2;
    *stop=compensated(terms,4);
    for (int i=0; i<4; ++i) {
        for (int j=0; j<4; ++j) terms[j]=matrix[i*4+j]*compression[j];
        force[i]=compensated(terms,4)+stops[i]*excess[i];
    }
}
static PyObject *suspension_elastic_terms(PyObject *self,PyObject *args) {
    PyObject *compression_object,*rates_object,*bars_object,*stops_object;
    double travel,compression[4],rates[4],bars[2],stops[4],spring,bar[2],stop,force[4];
    if (!PyArg_ParseTuple(args,"OOOOd",&compression_object,&rates_object,&bars_object,&stops_object,&travel)) return NULL;
    if (!vector(compression_object,compression,4) || !vector(rates_object,rates,4)
        || !vector(bars_object,bars,2) || !vector(stops_object,stops,4)) return NULL;
    suspension_elastic_values(compression,rates,bars,stops,travel,&spring,bar,&stop,force);
    return Py_BuildValue("(d(dd)d(dddd))",spring,bar[0],bar[1],stop,force[0],force[1],force[2],force[3]);
}
static PyObject *suspension_energy_account(PyObject *self,PyObject *args) {
    PyObject *compression_object,*speed_object,*mobility_object,*geometry_object,*end_object,*forces_object;
    PyObject *rates_object,*bars_object,*stops_object,*damping_object;
    double dt,travel,compression[4],speed[4],mobility[16],geometry[4],end[4],forces[4],rates[4],bars[2],stops[4],damping[4];
    if (!PyArg_ParseTuple(args,"OOOdOOOOOOdO",&compression_object,&speed_object,&mobility_object,&dt,
        &geometry_object,&end_object,&forces_object,&rates_object,&bars_object,&stops_object,&travel,&damping_object)) return NULL;
    if (!vector(compression_object,compression,4) || !vector(speed_object,speed,4)
        || !matrix_values(mobility_object,mobility,4,4) || !vector(geometry_object,geometry,4)
        || !vector(end_object,end,4) || !vector(forces_object,forces,4) || !vector(rates_object,rates,4)
        || !vector(bars_object,bars,2) || !vector(stops_object,stops,4) || !vector(damping_object,damping,4)) return NULL;
    double delta[4],rate[4],initial_spring,initial_bar[2],initial_stop,initial_force[4],spring,bar[2],stop,elastic_force[4],terms[4];
    for (int i=0; i<4; ++i) {delta[i]=end[i]-compression[i]; rate[i]=delta[i]/dt;}
    suspension_elastic_values(compression,rates,bars,stops,travel,&initial_spring,initial_bar,&initial_stop,initial_force);
    suspension_elastic_values(end,rates,bars,stops,travel,&spring,bar,&stop,elastic_force);
    double energy_change=spring+compensated(bar,2)+stop-initial_spring-compensated(initial_bar,2)-initial_stop;
    for (int i=0; i<4; ++i) terms[i]=damping[i]*delta[i]*delta[i]/dt;
    double damping_loss=compensated(terms,4);
    for (int i=0; i<4; ++i) terms[i]=elastic_force[i]*delta[i];
    double elastic_loss=compensated(terms,4)-energy_change;
    for (int i=0; i<4; ++i) {
        double row[4];
        for (int j=0; j<4; ++j) row[j]=mobility[i*4+j]*forces[j];
        terms[i]=forces[i]*compensated(row,4);
    }
    double body_loss=dt*dt*compensated(terms,4)/2;
    for (int i=0; i<4; ++i) terms[i]=forces[i]*(geometry[i]-compression[i]);
    double offset_work=compensated(terms,4);
    for (int i=0; i<4; ++i) terms[i]=forces[i]*speed[i];
    double kinetic_change=dt*compensated(terms,4)+body_loss;
    double residual=kinetic_change+energy_change+damping_loss+elastic_loss+body_loss-offset_work;
    return Py_BuildValue("((dddd)d(dd)ddddddd)",rate[0],rate[1],rate[2],rate[3],spring,bar[0],bar[1],
        stop,damping_loss,elastic_loss,body_loss,offset_work,residual,kinetic_change+body_loss);
}

/* 原九/十一维共同求根；分区暖状态按每次试探更新，30轮及原精度保持。 */
static double angular_tolerance(double a,double b) {
    double x=fabs(a),y=fabs(b),tol=1e-14;
    double ua=nextafter(x,INFINITY)-x,ub=nextafter(y,INFINITY)-y;
    if (ua>tol) tol=ua;
    if (ub>tol) tol=ub;
    return tol;
}
static double shared_residual_size(const SharedMap *data,const double state[11],const double end[11]) {
    int variables=data->bias ? 11 : 9;
    double maximum=0.;
    for (int a=0; a<variables; ++a) {
        double value=fabs(state[a]-end[a]);
        if (data->bias) value/=a<9 ? angular_tolerance(state[a],end[a]) : PORT_TOLERANCE;
        if (value>maximum) maximum=value;
    }
    return maximum;
}
static PyObject *shared_solution_result(SharedMap *data,double state[11],const double angular[9],
    const double *normal,const double load[4],const double support[4],int warm,double ports[2],PyObject *velocity) {
    if (data->bias) {state[9]=ports[0]; state[10]=ports[1];}
    int variables=data->bias ? 11 : 9,branch_index=warm,port_index=-1;
    double end[11],road[4],active[3],port_values[4],error=0.,previous_error=INFINITY;
    for (int iteration=0; iteration<30; ++iteration) {
        if (!shared_map_values(data,state,angular,normal,load,support,branch_index,
            end,road,active,port_values,&branch_index,&port_index)) return NULL;
        double residual[11];
        int angular_converged=1,ports_converged=1;
        double last_error=error;
        error=0.;
        for (int a=0; a<variables; ++a) {
            residual[a]=state[a]-end[a];
            double magnitude=fabs(residual[a]);
            if (magnitude>error) error=magnitude;
            if (a<9 && !(magnitude<=angular_tolerance(state[a],end[a]))) angular_converged=0;
            if (a>=9 && !(magnitude<=PORT_TOLERANCE)) ports_converged=0;
        }
        if (angular_converged && ports_converged) {
            if (data->bias) {
                ports[0]=port_values[1]; ports[1]=port_values[2];
                shared_active_limits(data,end,active);
                if (!shared_branch_feasible(data,&data->branches[branch_index],end,active)) {
                    for (int a=0; a<variables; ++a) state[a]=end[a];
                    continue;
                }
            }
            PyObject *result=PyTuple_New(9);
            if (!result) return NULL;
            for (int a=0; a<9; ++a) {
                PyObject *value=PyFloat_FromDouble(end[a]);
                if (!value) {Py_DECREF(result); return NULL;}
                PyTuple_SET_ITEM(result,a,value);
            }
            return Py_BuildValue("(NOdddii(dddd)(ddd)(dd))",result,velocity,
                port_values[0],port_values[2],port_values[1],branch_index,port_index,
                road[0],road[1],road[2],road[3],active[0],active[1],active[2],ports[0],ports[1]);
        }
        /* 固定点已快速下降时沿用原路线；停滞分区提前使用已有解析Newton。 */
        previous_error=iteration ? last_error : INFINITY;
        if ((data->rolling || data->bias) && (iteration>=4 || (iteration>=1 && error>=.2*previous_error))) {
            double columns[11][11],matrix[121],rhs[11],rows[121],delta[11],lu_residual[11],correction[11],terms[12],partials[12];
            Py_ssize_t order[11];
            shared_jacobian_values(data,state,load,support,branch_index,port_index,columns);
            for (int a=0; a<variables; ++a) {
                rhs[a]=-residual[a];
                for (int j=0; j<variables; ++j) matrix[a*variables+j]=columns[j][a];
            }
            if (!lu_values(matrix,rhs,variables,rows,order,delta,lu_residual,correction,terms,partials)) return NULL;
            double before=shared_residual_size(data,state,end);
            int accepted=0;
            for (int attempt=0; attempt<8; ++attempt) {
                double candidate[11],target[11],step=ldexp(1.,-attempt);
                for (int a=0; a<variables; ++a) candidate[a]=state[a]+step*delta[a];
                if (!shared_map_values(data,candidate,angular,normal,load,support,branch_index,
                    target,road,active,port_values,&branch_index,&port_index)) return NULL;
                if (shared_residual_size(data,candidate,target)<before) {
                    for (int a=0; a<variables; ++a) state[a]=candidate[a];
                    if (data->bias) shared_active_limits(data,state,active);
                    accepted=1; break;
                }
            }
            if (!accepted) {
                for (int a=0; a<variables; ++a) {
                    double pair[2]={state[a],end[a]};
                    state[a]=exact_sum(pair,2,partials)/2;
                }
                if (PyErr_Occurred()) return NULL;
            }
        } else for (int a=0; a<variables; ++a) state[a]=end[a];
    }
    char *number=PyOS_double_to_string(error,'g',6,0,NULL);
    if (!number) return NULL;
    char message[160];
    PyOS_snprintf(message,sizeof(message),"曲轴/四轮转子共同末状态超过30次迭代：%s",number);
    PyErr_SetString(PyExc_ArithmeticError,message);
    PyMem_Free(number); return NULL;
}
static PyObject *shared_solution(PyObject *self,PyObject *args) {
    PyObject *coefficients,*guess,*loads,*wheel_loads,*supported,*bias_ports;
    int warm;
    if (!PyArg_ParseTuple(args,"OOOOOiO",&coefficients,&guess,&loads,&wheel_loads,&supported,&warm,&bias_ports)) return NULL;
    SharedMap *data=PyCapsule_GetPointer(coefficients,shared_map_name);
    if (!data) return NULL;
    if (warm<0 || warm>=data->branch_count) {PyErr_SetString(PyExc_IndexError,"共同分区索引越界"); return NULL;}
    double state[11],angular[9],normal[9],load[4],support[4],ports[2];
    if (!vector(guess,state,9) || !tuple_fields(loads,3)
        || !vector(PyTuple_GET_ITEM(loads,0),angular,9) || !vector(wheel_loads,load,4)
        || !vector(supported,support,4)) return NULL;
    PyObject *normal_object=PyTuple_GET_ITEM(loads,1);
    if (!tuple_fields(bias_ports,2) || !PyTuple_Check(normal_object)) {
        if (!PyErr_Occurred()) PyErr_SetString(PyExc_ValueError,"法向载荷须为元组");
        return NULL;
    }
    int suspension=PyTuple_GET_SIZE(normal_object)!=0;
    if ((suspension && !vector(normal_object,normal,9)) || !vector(bias_ports,ports,2)) return NULL;
    return shared_solution_result(data,state,angular,suspension ? normal : NULL,load,support,warm,ports,PyTuple_GET_ITEM(loads,2));
}
static PyObject *shared_load_solution(PyObject *self,PyObject *args) {
    PyObject *coefficients,*guess,*forces,*velocity_object,*normal_forces,*normal_responses,*gradients;
    PyObject *wheel_loads,*supported,*bias_ports;
    int warm;
    if (!PyArg_ParseTuple(args,"OOOOOOOOOiO",&coefficients,&guess,&forces,&velocity_object,&normal_forces,
        &normal_responses,&gradients,&wheel_loads,&supported,&warm,&bias_ports)) return NULL;
    WheelMap *packet=PyCapsule_GetPointer(coefficients,wheel_map_name);
    if (!packet) return NULL;
    SharedMap *data=packet->shared;
    if (warm<0 || warm>=data->branch_count) {PyErr_SetString(PyExc_IndexError,"共同分区索引越界"); return NULL;}
    double state[11],angular[9],normal[9],load[4],support[4],ports[2],end_velocity[3];
    if (!vector(guess,state,9) || !vector(wheel_loads,load,4) || !vector(supported,support,4)
        || !vector(bias_ports,ports,2) || !wheel_load_values(&packet->load,forces,velocity_object,
            normal_forces,normal_responses,gradients,-1,angular,normal,end_velocity)) return NULL;
    PyObject *velocity=Py_BuildValue("(ddd)",end_velocity[0],end_velocity[1],end_velocity[2]);
    if (!velocity) return NULL;
    PyObject *result=shared_solution_result(data,state,angular,normal_forces!=Py_None ? normal : NULL,
        load,support,warm,ports,velocity);
    Py_DECREF(velocity); return result;
}

/* CPython 3.14.2 vector_norm两维原算法；缩放/补偿平方/微分校正均保持。
 * 来源Modules/mathmodule.c，许可见licenses/CPython-LICENSE.txt。 */
typedef struct{ double hi; double lo; } HypotPair;

static HypotPair
hypot_fast_sum(double a, double b)
{

    assert(fabs(a) >= fabs(b));
    double x = a + b;
    double y = (a - x) + b;
    return (HypotPair) {x, y};
}

static HypotPair
hypot_product(double x, double y)
{

    double z = x * y;
    double zz = fma(x, y, -z);
    return (HypotPair) {z, zz};
}

static inline double
hypot_vector_norm(Py_ssize_t n, double *vec, double max, int found_nan)
{
    double x, h, scale, csum = 1.0, frac1 = 0.0, frac2 = 0.0;
    HypotPair pr, sm;
    int max_e;
    Py_ssize_t i;

    if (isinf(max)) {
        return max;
    }
    if (found_nan) {
        return Py_NAN;
    }
    if (max == 0.0 || n <= 1) {
        return max;
    }
    frexp(max, &max_e);
    if (max_e < -1023) {

        for (i=0 ; i < n ; i++) {
            vec[i] /= DBL_MIN;
        }
        return DBL_MIN * hypot_vector_norm(n, vec, max / DBL_MIN, found_nan);
    }
    scale = ldexp(1.0, -max_e);
    assert(max * scale >= 0.5);
    assert(max * scale < 1.0);
    for (i=0 ; i < n ; i++) {
        x = vec[i];
        assert(isfinite(x) && fabs(x) <= max);
        x *= scale;
        assert(fabs(x) < 1.0);
        pr = hypot_product(x, x);
        assert(pr.hi <= 1.0);
        sm = hypot_fast_sum(csum, pr.hi);
        csum = sm.hi;
        frac1 += pr.lo;
        frac2 += sm.lo;
    }
    h = sqrt(csum - 1.0 + (frac1 + frac2));
    pr = hypot_product(-h, h);
    sm = hypot_fast_sum(csum, pr.hi);
    csum = sm.hi;
    frac1 += pr.lo;
    frac2 += sm.lo;
    x = csum - 1.0 + (frac1 + frac2);
    h +=  x / (2.0 * h);
    return h / scale;
}

static double hypot_two(double x,double y) {
    double vec[2]={fabs(x),fabs(y)},maximum=0.;
    for (int i=0;i<2;++i) if (vec[i]>maximum) maximum=vec[i];
    return hypot_vector_norm(2,vec,maximum,isnan(x) || isnan(y));
}

/* None显式选择同版本原生算法；旧入口仍调用实际传入的函数。 */
static int tire_norm(PyObject *hypot_function,double x,double y,double *value) {
    if (hypot_function==Py_None) { *value=hypot_two(x,y); return 1; }
    PyObject *result=PyObject_CallFunction(hypot_function,"dd",x,y);
    if (!result) return 0;
    *value=PyFloat_AsDouble(result); Py_DECREF(result); return !PyErr_Occurred();
}
static int tire_curve_values(double kappa,double alpha,double grip,double cx,double cy,
    double shape,double curvature,PyObject *hypot_function,double target[2]) {
    target[0]=target[1]=0.;
    if (grip==0.) return 1;
    double qx=cx*kappa,qy=-cy*tan(alpha),magnitude;
    if (!tire_norm(hypot_function,qx,qy,&magnitude)) return 0;
    if (magnitude==0.) return 1;
    double n=magnitude/(shape*grip);
    double force=grip*sin(shape*atan(n-curvature*(n-atan(n))));
    target[0]=force*qx/magnitude; target[1]=force*qy/magnitude;
    return 1;
}
static PyObject *tire_combined_force(PyObject *self,PyObject *args) {
    double kappa,alpha,grip,cx,cy,shape,curvature,target[2];
    PyObject *hypot_function;
    if (!PyArg_ParseTuple(args,"dddddddO",&kappa,&alpha,&grip,&cx,&cy,&shape,&curvature,&hypot_function)) return NULL;
    if (!tire_curve_values(kappa,alpha,grip,cx,cy,shape,curvature,hypot_function,target)) return NULL;
    return Py_BuildValue("(dd)",target[0],target[1]);
}
static int tire_contact_values(const double force[2],const double previous[2],const double slip[2],
    double denominator,int rolling,double grip,double cx,double cy,double dt,double stiffness,double damping,
    double shape,double curvature,PyObject *hypot_function,double target[2],double deformation[2],double rate[2],
    double patch[2],double *kappa,double *alpha,const char **mode) {
    double impedance=stiffness*dt+damping;
    for (int i=0; i<2; ++i) {
        rate[i]=(force[i]-stiffness*previous[i])/impedance;
        deformation[i]=previous[i]+dt*rate[i]; patch[i]=slip[i]-rate[i];
    }
    *kappa=patch[0]/denominator; *alpha=atan2(-patch[1],denominator);
    if (rolling) {
        if (!tire_curve_values(*kappa,*alpha,grip,cx,cy,shape,curvature,hypot_function,target)) return 0;
        *mode="compliant-rolling";
    } else {
        double trial[2],magnitude;
        for (int i=0; i<2; ++i) trial[i]=stiffness*previous[i]+impedance*slip[i];
        if (!tire_norm(hypot_function,trial[0],trial[1],&magnitude)) return 0;
        if (magnitude<=grip) {
            target[0]=trial[0]; target[1]=trial[1]; *mode="compliant-sticking";
        } else {
            for (int i=0; i<2; ++i) target[i]=grip*trial[i]/magnitude;
            *mode="compliant-sliding";
        }
    }
    return 1;
}
static PyObject *tire_contact_force(PyObject *self,PyObject *args) {
    PyObject *force_object,*previous_object,*slip_object,*hypot_function;
    double denominator,grip,cx,cy,dt,stiffness,damping,shape,curvature;
    int rolling;
    if (!PyArg_ParseTuple(args,"OOOdpddddddddO",&force_object,&previous_object,&slip_object,&denominator,&rolling,
        &grip,&cx,&cy,&dt,&stiffness,&damping,&shape,&curvature,&hypot_function)) return NULL;
    double force[2],previous[2],slip[2],rate[2],deformation[2],patch[2],target[2];
    if (!vector(force_object,force,2) || !vector(previous_object,previous,2) || !vector(slip_object,slip,2)) return NULL;
    double kappa,alpha; const char *mode;
    if (!tire_contact_values(force,previous,slip,denominator,rolling,grip,cx,cy,dt,stiffness,damping,
                             shape,curvature,hypot_function,target,deformation,rate,patch,&kappa,&alpha,&mode)) return NULL;
    return Py_BuildValue("((dd)(dd)(dd)(dd)dds)",target[0],target[1],deformation[0],deformation[1],
        rate[0],rate[1],patch[0],patch[1],kappa,alpha,mode);
}
/* 接点速度与机械轮速共用原力臂；各点积分别保留补偿求和次序。 */
static void wheel_velocity_values(const double *state,const double velocity[3],int coordinate,
    const double tangent[3],const double axle[3],const double moment_x[3],const double moment_y[3],
    double radius,double speed[2],double slip[2]) {
    double terms[3];
    for (int a=0;a<3;++a) terms[a]=velocity[a]*tangent[a];
    speed[0]=compensated(terms,3);
    for (int a=0;a<3;++a) terms[a]=state[a]*moment_x[a];
    speed[0]=speed[0]+compensated(terms,3);
    for (int a=0;a<3;++a) terms[a]=velocity[a]*axle[a];
    speed[1]=compensated(terms,3);
    for (int a=0;a<3;++a) terms[a]=state[a]*moment_y[a];
    speed[1]=speed[1]+compensated(terms,3);
    slip[0]=radius*state[coordinate]-speed[0]; slip[1]=-speed[1];
}
static PyObject *wheel_contact_state(PyObject *self,PyObject *args) {
    PyObject *state_object,*velocity_object,*tangent_object,*axle_object,*moment_x_object,*moment_y_object;
    PyObject *force_object,*previous_object,*parameters_object,*hardware_object,*hypot_function;
    int wheel_start,wheel,rolling;
    double radius,dt,state[9],velocity[3],tangent[3],axle[3],moment_x[3],moment_y[3];
    double force[2],previous[2],parameters[3],hardware[5],speed[2],slip[2],target[2],deformation[2],rate[2],patch[2];
    if (!PyArg_ParseTuple(args,"OOiiOOOOdOOOOdpO",&state_object,&velocity_object,&wheel_start,&wheel,
        &tangent_object,&axle_object,&moment_x_object,&moment_y_object,&radius,&force_object,&previous_object,
        &parameters_object,&hardware_object,&dt,&rolling,&hypot_function)) return NULL;
    if ((wheel_start!=4 && wheel_start!=5) || wheel<0 || wheel>=4) {
        PyErr_SetString(PyExc_IndexError,"接点机械轮速索引越界"); return NULL;
    }
    if (!vector(state_object,state,wheel_start+4) || !vector(velocity_object,velocity,3)
        || !vector(tangent_object,tangent,3) || !vector(axle_object,axle,3)
        || !vector(moment_x_object,moment_x,3) || !vector(moment_y_object,moment_y,3)
        || !vector(force_object,force,2) || !vector(previous_object,previous,2)
        || !vector(parameters_object,parameters,3) || !vector(hardware_object,hardware,5)) return NULL;
    wheel_velocity_values(state,velocity,wheel_start+wheel,tangent,axle,moment_x,moment_y,radius,speed,slip);
    double denominator=fabs(speed[0])>hardware[0] ? fabs(speed[0]) : hardware[0],kappa,alpha;
    const char *mode;
    if (!tire_contact_values(force,previous,slip,denominator,rolling,parameters[0],parameters[1],parameters[2],
        dt,hardware[1],hardware[2],hardware[3],hardware[4],hypot_function,target,deformation,rate,patch,&kappa,&alpha,&mode)) return NULL;
    return Py_BuildValue("((dd)[(dd)(dd)(dd)dds])",target[0],target[1],deformation[0],deformation[1],
        rate[0],rate[1],patch[0],patch[1],kappa,alpha,mode);
}
static PyObject *tire_energy_terms(PyObject *self,PyObject *args) {
    PyObject *force_object,*previous_object,*deformation_object,*rate_object,*patch_object;
    double dt,stiffness,damping,force[2],previous[2],deformation[2],rate[2],patch[2],terms[2];
    if (!PyArg_ParseTuple(args,"OOOOOddd",&force_object,&previous_object,&deformation_object,&rate_object,
        &patch_object,&dt,&stiffness,&damping)) return NULL;
    if (!vector(force_object,force,2) || !vector(previous_object,previous,2)
        || !vector(deformation_object,deformation,2) || !vector(rate_object,rate,2) || !vector(patch_object,patch,2)) return NULL;
    for (int a=0;a<2;++a) terms[a]=deformation[a]*deformation[a];
    double energy=.5*stiffness*compensated(terms,2);
    for (int a=0;a<2;++a) terms[a]=rate[a]*rate[a];
    double material=dt*damping*compensated(terms,2);
    for (int a=0;a<2;++a) terms[a]=force[a]*patch[a];
    double road=dt*compensated(terms,2);
    for (int a=0;a<2;++a) terms[a]=pow(deformation[a]-previous[a],2.);
    double numerical=.5*stiffness*compensated(terms,2);
    return Py_BuildValue("(dddd)",energy,material,road,numerical);
}
static int tire_jacobian_values(const double force[2],const double previous[2],const double slip[2],
    const double slip_jacobian[4],double denominator,const double denominator_gradient[2],int rolling,
    double grip,double cx,double cy,double dt,double stiffness,double damping,double shape,double curvature,
    PyObject *hypot_function,double result[4]) {
    if (grip==0.) { for (int i=0;i<4;++i) result[i]=0.; return 1; }
    double impedance=stiffness*dt+damping;
    if (!rolling) {
        double trial[2],magnitude,trial_jacobian[4],projection[4],terms[2];
        for (int i=0; i<2; ++i) trial[i]=stiffness*previous[i]+impedance*slip[i];
        if (!tire_norm(hypot_function,trial[0],trial[1],&magnitude)) return 0;
        for (int i=0; i<4; ++i) trial_jacobian[i]=impedance*slip_jacobian[i];
        if (magnitude<=grip) {
            for (int i=0; i<4; ++i) result[i]=trial_jacobian[i];
        } else {
            for (int i=0; i<2; ++i) for (int j=0; j<2; ++j)
                projection[2*i+j]=grip/magnitude*((double)(i==j)-trial[i]*trial[j]/pow(magnitude,2.));
            for (int i=0; i<2; ++i) for (int j=0; j<2; ++j) {
                for (int a=0; a<2; ++a) terms[a]=projection[2*i+a]*trial_jacobian[2*a+j];
                result[2*i+j]=compensated(terms,2);
            }
        }
    } else {
        double patch[2],q[2],q_jacobian[4],radial_jacobian[4],magnitude,terms[2];
        const double stiffnesses[2]={cx,cy};
        for (int i=0; i<2; ++i) {
            patch[i]=slip[i]-(force[i]-stiffness*previous[i])/impedance;
            q[i]=stiffnesses[i]*patch[i]/denominator;
            for (int j=0; j<2; ++j) {
                double patch_jacobian=slip_jacobian[2*i+j]-(double)(i==j)/impedance;
                q_jacobian[2*i+j]=(stiffnesses[i]*patch_jacobian-q[i]*denominator_gradient[j])/denominator;
            }
        }
        if (!tire_norm(hypot_function,q[0],q[1],&magnitude)) return 0;
        if (magnitude==0.) {
            for (int i=0; i<4; ++i) result[i]=q_jacobian[i];
        } else {
            double n=magnitude/(shape*grip),u=n-curvature*(n-atan(n));
            double angle=shape*atan(u),ratio=grip*sin(angle)/magnitude;
            double radial=cos(angle)*(1-curvature+curvature/(1+n*n))/(1+u*u);
            for (int i=0; i<2; ++i) for (int j=0; j<2; ++j)
                radial_jacobian[2*i+j]=ratio*(double)(i==j)+(radial-ratio)*(q[i]/magnitude)*(q[j]/magnitude);
            for (int i=0; i<2; ++i) for (int j=0; j<2; ++j) {
                for (int a=0; a<2; ++a) terms[a]=radial_jacobian[2*i+a]*q_jacobian[2*a+j];
                result[2*i+j]=compensated(terms,2);
            }
        }
    }
    return 1;
}
static PyObject *tire_contact_jacobian(PyObject *self,PyObject *args) {
    PyObject *force_object,*previous_object,*slip_object,*slip_jacobian_object,*denominator_gradient_object,*hypot_function;
    double denominator,grip,cx,cy,dt,stiffness,damping,shape,curvature;
    int rolling;
    if (!PyArg_ParseTuple(args,"OOOOdOpddddddddO",&force_object,&previous_object,&slip_object,&slip_jacobian_object,
        &denominator,&denominator_gradient_object,&rolling,&grip,&cx,&cy,&dt,&stiffness,&damping,&shape,&curvature,&hypot_function)) return NULL;
    if (grip==0.) return Py_BuildValue("((dd)(dd))",0.,0.,0.,0.);
    double force[2],previous[2],slip[2],slip_jacobian[4],denominator_gradient[2],result[4];
    if (!vector(force_object,force,2) || !vector(previous_object,previous,2) || !vector(slip_object,slip,2)
        || !matrix_values(slip_jacobian_object,slip_jacobian,2,2)
        || !vector(denominator_gradient_object,denominator_gradient,2)) return NULL;
    if (!tire_jacobian_values(force,previous,slip,slip_jacobian,denominator,denominator_gradient,rolling,
                              grip,cx,cy,dt,stiffness,damping,shape,curvature,hypot_function,result)) return NULL;
    return Py_BuildValue("((dd)(dd))",result[0],result[1],result[2],result[3]);
}

/* 完整悬架步直接组合原接触解和能量账，Python只发布原SuspensionStep。 */
static PyObject *suspension_step(PyObject *self,PyObject *args) {
    PyObject *compression,*speed,*mobility,*touching,*rates_object,*cd,*ed,*bars_object,*stops,*geometry;
    double travel,dt,rates[4],bars[2],matrix[16]={0.};
    if (!PyArg_ParseTuple(args,"OOOOOOOOOddO",&compression,&speed,&mobility,&touching,&rates_object,
        &cd,&ed,&bars_object,&stops,&travel,&dt,&geometry)) return NULL;
    if (!vector(rates_object,rates,4) || !vector(bars_object,bars,2)) return NULL;
    for (int i=0; i<4; ++i) matrix[i*4+i]=rates[i];
    for (int axle=0; axle<2; ++axle) {
        int left=2*axle,right=left+1;
        matrix[left*4+left]+=bars[axle]; matrix[right*4+right]+=bars[axle];
        matrix[left*4+right]-=bars[axle]; matrix[right*4+left]-=bars[axle];
    }
    PyObject *stiffness=Py_BuildValue("((dddd)(dddd)(dddd)(dddd))",matrix[0],matrix[1],matrix[2],matrix[3],
        matrix[4],matrix[5],matrix[6],matrix[7],matrix[8],matrix[9],matrix[10],matrix[11],matrix[12],matrix[13],matrix[14],matrix[15]);
    if (!stiffness) return NULL;
    PyObject *contact_args=Py_BuildValue("(OOOOOOOOddO)",compression,speed,mobility,touching,
        stiffness,cd,ed,stops,travel,dt,geometry);
    Py_DECREF(stiffness);
    if (!contact_args) return NULL;
    PyObject *contact=suspension_contact_state(self,contact_args);
    Py_DECREF(contact_args);
    if (!contact) return NULL;
    PyObject *energy_args=Py_BuildValue("(OOOdOOOOOOdO)",compression,speed,mobility,dt,geometry,
        PyTuple_GET_ITEM(contact,0),PyTuple_GET_ITEM(contact,1),rates_object,bars_object,stops,travel,PyTuple_GET_ITEM(contact,3));
    if (!energy_args) { Py_DECREF(contact); return NULL; }
    PyObject *energy=suspension_energy_account(self,energy_args);
    Py_DECREF(energy_args);
    if (!energy) { Py_DECREF(contact); return NULL; }
    PyObject *result=PyTuple_New(13);
    if (!result) { Py_DECREF(energy); Py_DECREF(contact); return NULL; }
    PyTuple_SET_ITEM(result,0,Py_NewRef(PyTuple_GET_ITEM(contact,0)));
    PyTuple_SET_ITEM(result,1,Py_NewRef(PyTuple_GET_ITEM(energy,0)));
    PyTuple_SET_ITEM(result,2,Py_NewRef(PyTuple_GET_ITEM(contact,1)));
    PyTuple_SET_ITEM(result,3,Py_NewRef(PyTuple_GET_ITEM(contact,2)));
    for (int i=1; i<10; ++i) PyTuple_SET_ITEM(result,3+i,Py_NewRef(PyTuple_GET_ITEM(energy,i)));
    Py_DECREF(energy); Py_DECREF(contact); return result;
}

/* 滚动根的控制流与Python原式相同，残差/Jacobian仍回本次真实轮端方程。 */
static int rolling_root_evaluate(PyObject *function, double fx, double fy, double *values, int count) {
    PyObject *result = PyObject_CallFunction(function, "dd", fx, fy);
    if (!result) return 0;
    int success = vector(result, values, count);
    Py_DECREF(result);
    return success;
}

static PyObject *rolling_root_failure(const char *message, double residual) {
    char buffer[256];
    PyOS_snprintf(buffer, sizeof(buffer), "%s%.6g N", message, residual);
    PyErr_SetString(PyExc_ArithmeticError, buffer);
    return NULL;
}

typedef int (*ForceEvaluation)(void *,double,double,int,double *);
typedef struct { PyObject *residual,*jacobian; } CallbackForce;
static int callback_force_values(void *context,double fx,double fy,int jacobian,double *values) {
    CallbackForce *data=context;
    return rolling_root_evaluate(jacobian ? data->jacobian : data->residual,fx,fy,values,jacobian ? 4 : 2);
}
static int rolling_root_values(ForceEvaluation evaluate,void *context,double grip,double tolerance,
    double force[2],PyObject *hypot_function,double *final_error) {
    double error=0.;
    for (int i = 0; i < 2; ++i) {
        double limited = force[i] < grip ? force[i] : grip;
        force[i] = limited > -grip ? limited : -grip;
    }
    double lower_x = -grip, upper_x = grip;
    for (int outer = 0; outer < 20; ++outer) {
        double lower_y = -grip, upper_y = grip, r[2], matrix[4];
        int lateral;
        for (lateral = 0; lateral < 20; ++lateral) {
            if (!evaluate(context,force[0],force[1],0,r)
                || !evaluate(context,force[0],force[1],1,matrix)) return 0;
            if (fabs(r[1]) < tolerance) break;
            if (r[1] > 0.) upper_y = force[1]; else lower_y = force[1];
            if (matrix[3] == 0.) { PyErr_SetString(PyExc_ZeroDivisionError, "横向根导数为零"); return 0; }
            double candidate = force[1] - r[1] / matrix[3];
            force[1] = lower_y < candidate && candidate < upper_y ? candidate : (lower_y + upper_y) / 2;
        }
        if (lateral == 20) { rolling_root_failure("轮胎横向隐式积分超过20次迭代：残差 ",r[1]); return 0; }
        if (!tire_norm(hypot_function,r[0],r[1],&error)) return 0;
        if (error < tolerance) { *final_error=error; return 1; }
        if (r[0] > 0.) upper_x = force[0]; else lower_x = force[0];
        if (matrix[3] == 0.) { PyErr_SetString(PyExc_ZeroDivisionError, "横向根导数为零"); return 0; }
        double derivative = matrix[0] - matrix[1] * matrix[2] / matrix[3];
        if (derivative == 0.) { PyErr_SetString(PyExc_ZeroDivisionError, "纵向根导数为零"); return 0; }
        double candidate = force[0] - r[0] / derivative;
        force[0] = lower_x < candidate && candidate < upper_x ? candidate : (lower_x + upper_x) / 2;
    }
    rolling_root_failure("轮胎滚动隐式积分超过20次迭代：残差 ",error); return 0;
}
static PyObject *rolling_force_solution(PyObject *self,PyObject *args) {
    CallbackForce context;
    PyObject *initial,*hypot_function;
    double grip,tolerance,force[2],error;
    if (!PyArg_ParseTuple(args,"OOddOO",&context.residual,&context.jacobian,&grip,&tolerance,&initial,&hypot_function)) return NULL;
    if (!vector(initial,force,2) || !rolling_root_values(callback_force_values,&context,grip,tolerance,force,hypot_function,&error)) return NULL;
    return Py_BuildValue("(ddd)",force[0],force[1],error);
}

/* 本次轮端方程的固定输入；暖分区仍逐次写回原list。 */
typedef struct {
    WheelMap *map;
    int wheel,rolling;
    double base[9],velocity[3],active[3],tangent[3],axle[3],moment_x[3],moment_y[3];
    double radius,previous[2],parameters[3],hardware[5];
    PyObject *warm_branches,*warm_modes,*hypot;
} WheelForce;

static int wheel_force_state(WheelForce *data,double fx,double fy,double state[9],double velocity[3],
    double *brake,int *selected,int *mode) {
    int warm=(int)PyLong_AsLong(PyList_GET_ITEM(data->warm_branches,data->wheel));
    if (PyErr_Occurred() || !wheel_map_values(data->map,data->wheel,data->base,data->velocity,fx,fy,data->active,
        warm,data->warm_modes,data->tangent,data->axle,state,velocity,brake,selected,mode)) return 0;
    PyObject *updated=PyLong_FromLong(*selected);
    if (!updated || PyList_SetItem(data->warm_branches,data->wheel,updated)<0) return 0;
    return 1;
}
static int wheel_force_values(void *context,double fx,double fy,int jacobian,double *result) {
    WheelForce *data=context;
    double state[9],velocity[3],brake;
    int selected,mode;
    if (!wheel_force_state(data,fx,fy,state,velocity,&brake,&selected,&mode)) return 0;
    double force[2]={fx,fy},speed[2],slip[2],gradients[2][3];
    if (jacobian) {
        if (!wheel_derivative_values(data->map,data->wheel,selected,mode,state,velocity,data->moment_x,data->moment_y,
            data->radius,data->tangent,data->axle,speed,slip,gradients)) return 0;
    } else {
        wheel_velocity_values(state,velocity,data->wheel+5,data->tangent,data->axle,
            data->moment_x,data->moment_y,data->radius,speed,slip);
    }
    double denominator=fabs(speed[0]);
    if (data->hardware[0]>denominator) denominator=data->hardware[0];
    double dt=data->map->shared->dt;
    if (jacobian) {
        double slip_jacobian[4]={gradients[0][0],gradients[1][0],gradients[0][1],gradients[1][1]};
        double denominator_gradient[2]={0.},target[4];
        if (fabs(speed[0])>data->hardware[0])
            for (int a=0;a<2;++a) denominator_gradient[a]=copysign(1.,speed[0])*gradients[a][2];
        if (!tire_jacobian_values(force,data->previous,slip,slip_jacobian,denominator,denominator_gradient,data->rolling,
            data->parameters[0],data->parameters[1],data->parameters[2],dt,data->hardware[1],data->hardware[2],
            data->hardware[3],data->hardware[4],data->hypot,target)) return 0;
        result[0]=1-target[0]; result[1]=-target[1]; result[2]=-target[2]; result[3]=1-target[3];
    } else {
        double target[2],deformation[2],rate[2],patch[2],kappa,alpha;
        const char *contact_mode;
        if (!tire_contact_values(force,data->previous,slip,denominator,data->rolling,
            data->parameters[0],data->parameters[1],data->parameters[2],dt,data->hardware[1],data->hardware[2],
            data->hardware[3],data->hardware[4],data->hypot,target,deformation,rate,patch,&kappa,&alpha,&contact_mode)) return 0;
        result[0]=fx-target[0]; result[1]=fy-target[1];
    }
    return 1;
}
static int wheel_newton_values(WheelForce *data,double tolerance,double force[2],double *final_error) {
    double error=0.;
    for (int iteration=0;iteration<20;++iteration) {
        double residual[2],matrix[4];
        if (!wheel_force_values(data,force[0],force[1],0,residual)
            || !tire_norm(data->hypot,residual[0],residual[1],&error)) return 0;
        if (error<tolerance) { *final_error=error; return 1; }
        if (!wheel_force_values(data,force[0],force[1],1,matrix)) return 0;
        double determinant=matrix[0]*matrix[3]-matrix[1]*matrix[2];
        if (determinant==0.) { PyErr_SetString(PyExc_ZeroDivisionError,"轮胎Jacobian行列式为零"); return 0; }
        double dx=(matrix[3]*residual[0]-matrix[1]*residual[1])/determinant;
        double dy=(matrix[0]*residual[1]-matrix[2]*residual[0])/determinant;
        int exponent;
        for (exponent=0;exponent<12;++exponent) {
            double scale=ldexp(1.,-exponent),candidate_x=force[0]-scale*dx,candidate_y=force[1]-scale*dy;
            double next[2],next_error;
            if (!wheel_force_values(data,candidate_x,candidate_y,0,next) || !tire_norm(data->hypot,next[0],next[1],&next_error)) return 0;
            if (next_error<error) { force[0]=candidate_x; force[1]=candidate_y; break; }
        }
        if (exponent==12) { rolling_root_failure("轮胎隐式积分不收敛：残差 ",error); return 0; }
    }
    rolling_root_failure("轮胎隐式积分超过20次迭代：残差 ",error); return 0;
}
static PyObject *wheel_force_result(WheelForce *context,double tolerance,double force[2],int predict) {
    double error;
    double state[9],end_velocity[3],brake;
    int selected,mode;
    if (predict) {
        /* 首轮真实轮荷刷新后的同方程零滑移切线初值。 */
        double speed[2],slip[2],gradients[2][3],slopes[2],patch[2],matrix[4];
        if (!wheel_force_state(context,0.,0.,state,end_velocity,&brake,&selected,&mode)
            || !wheel_derivative_values(context->map,context->wheel,selected,mode,state,end_velocity,
                context->moment_x,context->moment_y,context->radius,context->tangent,context->axle,speed,slip,gradients)) return NULL;
        double dt=context->map->shared->dt,impedance=context->hardware[1]*dt+context->hardware[2];
        double denominator=fabs(speed[0])>context->hardware[0] ? fabs(speed[0]) : context->hardware[0];
        for (int a=0;a<2;++a) {
            slopes[a]=context->parameters[a+1]/denominator;
            patch[a]=slip[a]+context->hardware[1]*context->previous[a]/impedance;
            for (int b=0;b<2;++b) matrix[2*a+b]=(double)(a==b)-slopes[a]*(gradients[b][a]-(double)(a==b)/impedance);
        }
        double rhs_x=slopes[0]*patch[0],rhs_y=slopes[1]*patch[1];
        double determinant=matrix[0]*matrix[3]-matrix[1]*matrix[2];
        if (determinant==0.) { PyErr_SetString(PyExc_ZeroDivisionError,"轮胎初值切线行列式为零"); return NULL; }
        force[0]=(matrix[3]*rhs_x-matrix[1]*rhs_y)/determinant;
        force[1]=(matrix[0]*rhs_y-matrix[2]*rhs_x)/determinant;
    }
    int solved=context->rolling ? rolling_root_values(wheel_force_values,context,context->parameters[0],tolerance,force,context->hypot,&error)
                               : wheel_newton_values(context,tolerance,force,&error);
    if (!solved) return NULL;
    if (!wheel_force_state(context,force[0],force[1],state,end_velocity,&brake,&selected,&mode)) return NULL;
    return Py_BuildValue("(dddd)",force[0],force[1],brake,error);
}
static PyObject *wheel_force_solution(PyObject *self,PyObject *args) {
    WheelForce context;
    PyObject *coefficients,*base,*velocity,*active,*tangent,*axle,*moment_x,*moment_y,*previous,*parameters,*hardware,*initial;
    double tolerance,force[2];
    int predict;
    if (!PyArg_ParseTuple(args,"Oi" "OOOOOOOOO" "dOOOpdOpO",&coefficients,&context.wheel,&base,&velocity,&active,
        &context.warm_branches,&context.warm_modes,&tangent,&axle,&moment_x,&moment_y,&context.radius,&previous,
        &parameters,&hardware,&context.rolling,&tolerance,&initial,&predict,&context.hypot)) return NULL;
    context.map=PyCapsule_GetPointer(coefficients,wheel_map_name);
    if (!context.map) return NULL;
    if (context.wheel<0 || context.wheel>=4) { PyErr_SetString(PyExc_IndexError,"轮端索引越界"); return NULL; }
    if (!vector(base,context.base,9) || !vector(velocity,context.velocity,3) || !vector(active,context.active,3)
        || !vector(tangent,context.tangent,3) || !vector(axle,context.axle,3) || !vector(moment_x,context.moment_x,3)
        || !vector(moment_y,context.moment_y,3) || !vector(previous,context.previous,2)
        || !vector(parameters,context.parameters,3) || !vector(hardware,context.hardware,5) || !vector(initial,force,2)) return NULL;
    return wheel_force_result(&context,tolerance,force,predict);
}

/* 当前跨轮载荷直接进入局部力求根，不装配/读回自由状态元组。 */
static PyObject *loaded_wheel_force_solution(PyObject *self,PyObject *args) {
    WheelForce context;
    PyObject *coefficients,*forces,*velocity,*normal_forces,*normal_responses,*gradients,*gyro_object,*road_object;
    PyObject *active,*moment_x,*moment_y,*previous,*parameters,*hardware,*initial;
    double tolerance,force[2],angular[9],normal[9],gyro[3],road[4];
    int predict;
    if (!PyArg_ParseTuple(args,"Oi" "OOOOOOOOOOOOOOO" "pdOpO",&coefficients,&context.wheel,
        &forces,&velocity,&normal_forces,&normal_responses,&gradients,&gyro_object,&road_object,&active,
        &context.warm_branches,&context.warm_modes,&moment_x,&moment_y,&previous,&parameters,&hardware,
        &context.rolling,&tolerance,&initial,&predict,&context.hypot)) return NULL;
    context.map=PyCapsule_GetPointer(coefficients,wheel_map_name);
    if (!context.map) return NULL;
    if (context.wheel<0 || context.wheel>=4) { PyErr_SetString(PyExc_IndexError,"轮端索引越界"); return NULL; }
    if (!wheel_load_values(&context.map->load,forces,velocity,normal_forces,normal_responses,gradients,context.wheel,
        angular,normal,context.velocity) || !vector(gyro_object,gyro,3)
        || (road_object!=Py_None && !vector(road_object,road,4)) || !vector(active,context.active,3)
        || !vector(moment_x,context.moment_x,3) || !vector(moment_y,context.moment_y,3)
        || !vector(previous,context.previous,2) || !vector(parameters,context.parameters,3)
        || !vector(hardware,context.hardware,5) || !vector(initial,force,2)) return NULL;
    SharedMap *data=context.map->shared;
    known_values(&data->mass,data->base,gyro,angular,normal_forces!=Py_None ? normal : NULL,
        data->dt,road_object!=Py_None ? road : NULL,context.base);
    for (int a=0;a<3;++a) {
        context.tangent[a]=context.map->load.tangents[3*context.wheel+a];
        context.axle[a]=context.map->load.axles[3*context.wheel+a];
    }
    context.radius=data->radii[context.wheel];
    return wheel_force_result(&context,tolerance,force,predict);
}

/* 同一末状态下四轮接触与制动残差；原点积/本构/误差尺度保持。 */
static PyObject *wheel_residuals(PyObject *self,PyObject *args) {
    PyObject *coefficients,*state_object,*velocity_object,*forces_object,*modes_object,*previous_object;
    PyObject *parameters_object,*hardware_object,*rolling_object,*moment_x_object,*moment_y_object,*compliance_object,*hypot;
    if (!PyArg_ParseTuple(args,"OOOOOOOOOOOOO",&coefficients,&state_object,&velocity_object,&forces_object,
        &modes_object,&previous_object,&parameters_object,&hardware_object,&rolling_object,&moment_x_object,
        &moment_y_object,&compliance_object,&hypot)) return NULL;
    WheelMap *packet=PyCapsule_GetPointer(coefficients,wheel_map_name);
    if (!packet) return NULL;
    double state[9],velocity[3],forces[12],previous[8],parameters[12],hardware[20],rolling[4];
    double moment_x[12],moment_y[12],compliance[4];
    if (!vector(state_object,state,9) || !vector(velocity_object,velocity,3)
        || !matrix_values(forces_object,forces,4,3) || !matrix_values(previous_object,previous,4,2)
        || !matrix_values(parameters_object,parameters,4,3) || !matrix_values(hardware_object,hardware,4,5)
        || !vector(rolling_object,rolling,4) || !matrix_values(moment_x_object,moment_x,4,3)
        || !matrix_values(moment_y_object,moment_y,4,3) || !vector(compliance_object,compliance,4)) return NULL;
    PyObject *modes=PySequence_Fast(modes_object,"轮端模式须为四轮序列");
    if (!modes) return NULL;
    if (PySequence_Fast_GET_SIZE(modes)!=4) { Py_DECREF(modes); PyErr_SetString(PyExc_ValueError,"轮端模式须为四轮序列"); return NULL; }
    double maximum=0.,brake_error=0.,dt=packet->shared->dt;
    for (int i=0;i<4;++i) {
        const char *mode=PyUnicode_AsUTF8(PySequence_Fast_GET_ITEM(modes,i));
        if (!mode) { Py_DECREF(modes); return NULL; }
        const double *tangent=packet->load.tangents+3*i,*axle=packet->load.axles+3*i;
        double radius=packet->shared->radii[i],speed[2],slip[2],error,terms[9];
        wheel_velocity_values(state,velocity,i+5,tangent,axle,moment_x+3*i,moment_y+3*i,radius,speed,slip);
        if (strcmp(mode,"sticking")==0) {
            const double *rx=packet->load.responses+27*i,*ry=rx+9;
            for (int a=0;a<9;++a) terms[a]=(a<3 ? moment_x[3*i+a] : a==i+5 ? -radius : 0.)*rx[a];
            double scale_x=dt*(1/packet->load.mass+compensated(terms,9));
            for (int a=0;a<9;++a) terms[a]=(a<3 ? moment_y[3*i+a] : 0.)*ry[a];
            double scale_y=dt*(1/packet->load.mass+compensated(terms,9));
            if (!tire_norm(hypot,slip[0]/scale_x,slip[1]/scale_y,&error)) { Py_DECREF(modes); return NULL; }
        } else {
            const double *p=parameters+3*i,*h=hardware+5*i;
            double denominator=fabs(speed[0])>h[0] ? fabs(speed[0]) : h[0],target[2];
            if (compliance[i]!=0.) {
                double deformation[2],rate[2],patch[2],kappa,alpha;
                const char *contact_mode;
                if (!tire_contact_values(forces+3*i,previous+2*i,slip,denominator,rolling[i]!=0.,p[0],p[1],p[2],
                    dt,h[1],h[2],h[3],h[4],hypot,target,deformation,rate,patch,&kappa,&alpha,&contact_mode)) {
                    Py_DECREF(modes); return NULL;
                }
            } else if (!tire_curve_values(slip[0]/denominator,atan2(speed[1],denominator),p[0],p[1],p[2],h[3],h[4],hypot,target)) {
                Py_DECREF(modes); return NULL;
            }
            if (!tire_norm(hypot,forces[3*i]-target[0],forces[3*i+1]-target[1],&error)) { Py_DECREF(modes); return NULL; }
        }
        if (error>maximum) maximum=error;
        for (int a=0;a<9;++a) terms[a]=packet->brake_gradients[i][a]*state[a];
        double speed_brake=compensated(terms,9);
        const double *rb=packet->load.responses+27*i+18;
        for (int a=0;a<9;++a) terms[a]=packet->brake_gradients[i][a]*rb[a];
        double response=compensated(terms,9),brake=forces[3*i+2],target=brake+speed_brake/(dt*response);
        target=target<packet->brakes[i] ? target : packet->brakes[i];
        target=target>-packet->brakes[i] ? target : -packet->brakes[i];
        double brake_residual=fabs(brake-target);
        if (brake_residual>brake_error) brake_error=brake_residual;
    }
    Py_DECREF(modes);
    return Py_BuildValue("(dd)",maximum,brake_error);
}

/* 原法向力差与六分量几何共轭冲量，仍使用逐分量四项补偿和。 */
static PyObject *suspension_residuals(PyObject *self,PyObject *args) {
    PyObject *force_object,*target_force_object,*gradients_object,*target_gradients_object;
    double dt,forces[4],target_forces[4],gradients[24],target_gradients[24],normal_error=0.,geometry_error=0.,terms[4];
    if (!PyArg_ParseTuple(args,"OOOOd",&force_object,&target_force_object,&gradients_object,&target_gradients_object,&dt)) return NULL;
    if (!vector(force_object,forces,4) || !vector(target_force_object,target_forces,4)
        || !matrix_values(gradients_object,gradients,4,6) || !matrix_values(target_gradients_object,target_gradients,4,6)) return NULL;
    for (int i=0;i<4;++i) {
        double error=fabs(forces[i]-target_forces[i]);
        if (error>normal_error) normal_error=error;
    }
    for (int a=0;a<6;++a) {
        for (int i=0;i<4;++i) terms[i]=forces[i]*(target_gradients[6*i+a]-gradients[6*i+a]);
        double error=fabs(compensated(terms,4));
        if (error>geometry_error) geometry_error=error;
    }
    return Py_BuildValue("(dd)",normal_error,dt*geometry_error);
}

static PyMethodDef methods[] = {
    {"suspension_coefficients", (PyCFunction)suspension_coefficients, METH_VARARGS, "本advance固定悬架材料与硬件"},
    {"suspension_forces", (PyCFunction)suspension_forces, METH_VARARGS, "原活动集只返回当前反力"},
    {"suspension_projection", (PyCFunction)suspension_projection, METH_VARARGS, "四轮法向响应与Mobility整块计算"},
    {"wheel_residuals", (PyCFunction)wheel_residuals, METH_VARARGS, "同一末状态四轮接触与制动残差"},
    {"wheel_brake_correction", (PyCFunction)wheel_brake_correction, METH_VARARGS, "同一端口分区四轮制动联合修正"},
    {"suspension_residuals", (PyCFunction)suspension_residuals, METH_VARARGS, "原法向/几何共轭残差"},
    {"loaded_wheel_force_solution", (PyCFunction)loaded_wheel_force_solution, METH_VARARGS, "当前跨轮自由状态与原轮力求根共入口"},
    {"wheel_free_state", (PyCFunction)wheel_free_state, METH_VARARGS, "当前跨轮/法向载荷直接组合局部自由状态"},
    {"shared_load_solution", (PyCFunction)shared_load_solution, METH_VARARGS, "当前四轮/法向载荷直接接共同求根"},
    {"tire_energy_terms", (PyCFunction)tire_energy_terms, METH_VARARGS, "原胎体储能、材料/路面/离散耗散"},
    {"wheel_contact_state", (PyCFunction)wheel_contact_state, METH_VARARGS, "原共同末速度接点与胎体本构"},
    {"wheel_force_solution", (PyCFunction)wheel_force_solution, METH_VARARGS, "原九维轮端柔性接触力与解析Jacobian共同求解"},
    {"rolling_force_solution", (PyCFunction)rolling_force_solution, METH_VARARGS, "原滚动接触括根控制流"},
    {"suspension_step", (PyCFunction)suspension_step, METH_VARARGS, "原完整悬架步与能量账"},
    {"suspension_elastic_terms", (PyCFunction)suspension_elastic_terms, METH_VARARGS, "原悬架势能及硬件梯度"},
    {"suspension_energy_account", (PyCFunction)suspension_energy_account, METH_VARARGS, "原悬架离散能量账"},
    {"wheel_map_derivatives", (PyCFunction)wheel_map_derivatives, METH_VARARGS, "原轮端机械活动分区完整解析导数"},
    {"tire_combined_force", (PyCFunction)tire_combined_force, METH_VARARGS, "原联合滑移轮胎力"},
    {"tire_contact_force", (PyCFunction)tire_contact_force, METH_VARARGS, "原柔性胎体及接触分区"},
    {"tire_contact_jacobian", (PyCFunction)tire_contact_jacobian, METH_VARARGS, "原柔性接触解析导数"},
    {"shared_solution", (PyCFunction)shared_solution, METH_VARARGS, "原九/十一维共同转子求根"},
    {"suspension_contact_state", (PyCFunction)suspension_contact_state, METH_VARARGS, "原四轮接触阻尼止挡活动集"},
    {"wheel_map_coefficients", (PyCFunction)wheel_map_coefficients, METH_VARARGS, "本子步轮胎局部端口的固定系数"},
    {"wheel_map_state", (PyCFunction)wheel_map_state, METH_VARARGS, "原轮胎试探力与传动制动共同末状态"},
    {"shared_map_jacobian", (PyCFunction)shared_map_jacobian, METH_VARARGS | METH_KEYWORDS, "原九/十一维共同状态活动分区解析导数"},
    {"shared_map_coefficients", (PyCFunction)shared_map_coefficients, METH_VARARGS | METH_KEYWORDS, "本共同求解的固定实体轴活动分区"},
    {"shared_map_state", (PyCFunction)shared_map_state, METH_VARARGS | METH_KEYWORDS, "原九/十一维机械共同末状态映射"},
    {"known_state", (PyCFunction)known_state_call, METH_VARARGS | METH_KEYWORDS, "原共同自由速度与当前载荷组合"},
    {"rotor_known_state", (PyCFunction)rotor_known_state_call, METH_VARARGS | METH_KEYWORDS, "原转子陀螺与共同自由速度组合"},
    {"shaft_brake_plans", (PyCFunction)shaft_plans, METH_VARARGS | METH_KEYWORDS, "原四端口有序活动分区与三维逆矩阵"},
    {"rotor_coefficients", (PyCFunction)rotor_coefficients_call, METH_VARARGS | METH_KEYWORDS, "本共同求解的只读转子系数"},
    {"rotor_spin_prepared", (PyCFunction)rotor_spin_prepared_call, METH_VARARGS | METH_KEYWORDS, "复用本共同求解固定转子系数"},
    {"load_coefficients", (PyCFunction)load_coefficients_call, METH_VARARGS | METH_KEYWORDS, "本共同求解的固定轮端投影"},
    {"wheel_load_prepared", (PyCFunction)wheel_load_prepared_call, METH_VARARGS | METH_KEYWORDS, "当前轮端力与法向状态的原投影"},
    {"mass_coefficients", (PyCFunction)mass_coefficients_call, METH_VARARGS | METH_KEYWORDS, "本共同求解的只读逆惯量系数"},
    {"mass_response_prepared", (PyCFunction)mass_response_prepared_call, METH_VARARGS | METH_KEYWORDS, "复用本共同求解固定逆惯量系数"},
    {"wheel_load_terms", (PyCFunction)load_terms_call, METH_VARARGS | METH_KEYWORDS, "原四轮力矩与法向投影"},
    {"rotor_spin", (PyCFunction)rotor_spin_call, METH_VARARGS | METH_KEYWORDS, "原整组转子轴向角动量"},
    {"mass_response", (PyCFunction)mass_response_call, METH_VARARGS | METH_KEYWORDS, "原实体转子消元及发动机阻力响应"},
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

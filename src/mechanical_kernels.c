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

static PyObject *mass_response_prepared_call(PyObject *self,PyObject *args,PyObject *kwargs) {
    PyObject *coefficients,*input;
    static char *names[]={"coefficients","vector",NULL};
    if (!PyArg_ParseTupleAndKeywords(args,kwargs,"OO",names,&coefficients,&input)) return NULL;
    MassCoefficients *data=PyCapsule_GetPointer(coefficients,mass_coefficients_name);
    if (!data) return NULL;
    double source[9],values[9],terms[9];
    if (!vector(input,source,data->dimensions)) return NULL;
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

static PyObject *rotor_spin_prepared_call(PyObject *self,PyObject *args,PyObject *kwargs) {
    PyObject *coefficients,*input;
    static char *names[]={"coefficients","state",NULL};
    if (!PyArg_ParseTupleAndKeywords(args,kwargs,"OO",names,&coefficients,&input)) return NULL;
    RotorCoefficients *data=PyCapsule_GetPointer(coefficients,rotor_coefficients_name);
    if (!data) return NULL;
    double state[9],terms[9],base[3],result[3];
    if (!vector(input,state,data->dimensions)) return NULL;
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
    return Py_BuildValue("(ddd)",result[0],result[1],result[2]);
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

static PyObject *wheel_load_prepared_call(PyObject *self,PyObject *args,PyObject *kwargs) {
    PyObject *coefficients,*forces,*velocity_object,*normal_forces_object,*normal_responses_object,*gradients_object,*exclude_object;
    static char *names[]={"coefficients","forces","velocity","normal_forces","normal_responses","normal_gradients","exclude",NULL};
    if (!PyArg_ParseTupleAndKeywords(args,kwargs,"OOOOOOO",names,&coefficients,&forces,&velocity_object,&normal_forces_object,
                                     &normal_responses_object,&gradients_object,&exclude_object)) return NULL;
    LoadCoefficients *data=PyCapsule_GetPointer(coefficients,load_coefficients_name);
    if (!data) return NULL;
    double force[12],velocity[3],end_velocity[3],terms[4],angular[9],normal[9];
    if (!matrix_values(forces,force,4,3) || !vector(velocity_object,velocity,3)) return NULL;
    long exclude=exclude_object==Py_None ? -1 : PyLong_AsLong(exclude_object);
    if (PyErr_Occurred()) return NULL;
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
            || !matrix_values(gradients_object,gradients,4,6)) return NULL;
        for (int a=0; a<data->dimensions; ++a) {
            for (int i=0; i<4; ++i) terms[i]=normal_forces[i]*normal_responses[i*data->dimensions+a];
            normal[a]=data->dt*compensated(terms,4);
        }
        for (int a=0; a<3; ++a) {
            for (int i=0; i<4; ++i) terms[i]=normal_forces[i]*gradients[i*6+a];
            end_velocity[a]=end_velocity[a]+data->dt/data->mass*compensated(terms,4);
        }
    }
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

static PyMethodDef methods[] = {
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

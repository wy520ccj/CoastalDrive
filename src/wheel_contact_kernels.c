#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <math.h>

/* 部分和算法参考CPython 3.14.2 mathmodule.c，许可见licenses/CPython-LICENSE.txt。 */
/* 四个有限项的无重叠部分和，保留math.fsum的半偶舍入。 */
static double sum_four(double values[4]) {
    double partials[4], high = 0., low = 0.;
    int count = 0;
    for (int k = 0; k < 4; ++k) {
        double x = values[k];
        int write = 0;
        for (int j = 0; j < count; ++j) {
            double y = partials[j];
            if (fabs(x) < fabs(y)) { double swap = x; x = y; y = swap; }
            high = x + y;
            low = y - (high - x);
            if (low != 0.) partials[write++] = low;
            x = high;
        }
        count = write;
        if (!isfinite(x)) {
            PyErr_SetString(PyExc_OverflowError, "有限轮胎支持函数求和溢出");
            return 0.;
        }
        if (x != 0.) partials[count++] = x;
    }
    high = 0.;
    if (count) {
        high = partials[--count];
        while (count) {
            double x = high, y = partials[--count];
            high = x + y;
            low = y - (high - x);
            if (low != 0.) break;
        }
        if (count && ((low < 0. && partials[count-1] < 0.) || (low > 0. && partials[count-1] > 0.))) {
            double twice = low * 2., rounded = high + twice;
            if (twice == rounded - high) high = rounded;
        }
    }
    return high;
}

static double sum_values(const double *values,int count) {
    double main = 0., correction = 0.;
    for (int i = 0; i < count; ++i) {
        double next = main + values[i];
        correction += fabs(main) >= fabs(values[i])
            ? (main-next)+values[i] : (values[i]-next)+main;
        main = next;
    }
    return correction != 0. && isfinite(correction) ? main + correction : main;
}

static double sum_three(double values[3]) { return sum_values(values,3); }

static double dot(double a[3], double b[3]) {
    double terms[3];
    for (int i = 0; i < 3; ++i) terms[i] = a[i] * b[i];
    return sum_three(terms);
}

static void cross_precise(double a[3], double b[3], double result[3]) {
    const int pairs[3][2] = {{1,2},{2,0},{0,1}};
    for (int k = 0; k < 3; ++k) {
        int i = pairs[k][0], j = pairs[k][1];
        double first = a[i]*b[j], second = a[j]*b[i];
        double terms[4] = {first, -second, fma(a[i], b[j], -first), -fma(a[j], b[i], -second)};
        result[k] = sum_four(terms);
    }
}

static int vector(PyObject *object, double values[3]) {
    PyObject *sequence = PySequence_Fast(object, "轮胎支持向量须为序列");
    if (!sequence) return 0;
    if (PySequence_Fast_GET_SIZE(sequence) != 3) {
        Py_DECREF(sequence); PyErr_SetString(PyExc_ValueError, "轮胎支持向量须为三维"); return 0;
    }
    for (int i = 0; i < 3; ++i) {
        values[i] = PyFloat_AsDouble(PySequence_Fast_GET_ITEM(sequence, i));
        if (PyErr_Occurred()) { Py_DECREF(sequence); return 0; }
    }
    Py_DECREF(sequence); return 1;
}


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

static int support_values(double direction[3], double axis[3], double radius, double half_width,
                          double shoulder, double crown, double result[3]) {
    double inner[3], radial[3];
    double axis_squared = dot(axis, axis), axis_length = sqrt(axis_squared);
    if (axis_squared == 0.) { PyErr_SetString(PyExc_ZeroDivisionError, "轮轴不能为零向量"); return 0; }
    double axial = dot(direction, axis) / axis_length;
    cross_precise(direction, axis, inner);
    cross_precise(axis, inner, radial);
    if (PyErr_Occurred()) return 0;
    for (int i = 0; i < 3; ++i) radial[i] /= axis_squared;
    double radial_length = sqrt(dot(radial, radial)), length = sqrt(dot(direction, direction));
    double half = half_width - shoulder, x;
    if (crown != 0. && radial_length != 0.) {
        double free_x = axial * pow(half, 2.) / (2 * crown * radial_length);
        x = free_x < half ? free_x : half;
        x = x > -half ? x : -half;
    } else x = half * (axial > 0. ? 1. : axial < 0. ? -1. : 0.);
    if (half == 0.) { PyErr_SetString(PyExc_ZeroDivisionError, "轮胎内核半宽不能为零"); return 0; }
    double tread = radius - shoulder - crown * pow(x / half, 2.);
    for (int i = 0; i < 3; ++i)
        result[i] = x * (axis[i]/axis_length)
                    + (radial_length != 0. ? tread * radial[i] / radial_length : 0.)
                    + (length != 0. ? shoulder * direction[i] / length : 0.);
    return 1;
}

static PyObject *support(PyObject *self, PyObject *args, PyObject *kwargs) {
    PyObject *direction_object, *axis_object;
    double radius, half_width, shoulder, crown = 0.;
    static char *names[] = {"direction", "axis", "radius", "half_width", "shoulder", "crown", NULL};
    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "OOddd|d", names, &direction_object, &axis_object,
                                    &radius, &half_width, &shoulder, &crown)) return NULL;
    double direction[3], axis[3], result[3];
    if (!vector(direction_object, direction) || !vector(axis_object, axis)) return NULL;
    if (!support_values(direction, axis, radius, half_width, shoulder, crown, result)) return NULL;
    return Py_BuildValue("(ddd)", result[0], result[1], result[2]);
}

static void subtract(double first[3], double second[3], double result[3]) {
    for (int i = 0; i < 3; ++i) result[i] = first[i] - second[i];
}

static void cross(double a[3], double b[3], double result[3]) {
    result[0] = a[1]*b[2] - a[2]*b[1];
    result[1] = a[2]*b[0] - a[0]*b[2];
    result[2] = a[0]*b[1] - a[1]*b[0];
}

/* 既有单面入口与整条查询共用原有限面判据。 */
static PyObject *triangle_face_values(double start[3],double end[3],double vertices[3][3],
    double margin,double axis[3],double radius,double width,double shoulder,double crown,
    int face_only,double ceiling) {
    double ab[3], ac[3], normal[3], velocity[3], relative[3], offset[3];
    subtract(vertices[1],vertices[0],ab); subtract(vertices[2],vertices[0],ac);
    cross(ab,ac,normal);
    double length = sqrt(dot(normal,normal));
    if (length == 0.) { PyErr_SetString(PyExc_ZeroDivisionError,"三角面不能退化"); return NULL; }
    for (int i = 0; i < 3; ++i) normal[i] /= length;
    subtract(end,start,velocity);
    if (dot(normal,velocity) > 0.) for (int i = 0; i < 3; ++i) normal[i] = -normal[i];
    if (!support_values(normal,axis,radius,width/2,shoulder,crown,offset)) return NULL;
    subtract(start,vertices[0],relative);
    double distance = dot(normal,relative) - dot(normal,offset) - margin, speed = dot(normal,velocity);
    if (speed < 0. && distance >= 0.) {
        double fraction = -distance / speed;
        if (!face_only && fraction >= ceiling) return Py_BuildValue("(OO)",Py_True,Py_None);
        if (fraction >= 0. && fraction <= 1.) {
            double point[3], core[3];
            for (int i = 0; i < 3; ++i) {
                point[i] = start[i] + fraction * velocity[i] - offset[i];
                core[i] = point[i] - margin * normal[i];
            }
            int forward = 1, reverse = 1;
            for (int i = 0; i < 3; ++i) {
                double edge[3], side[3], product[3];
                subtract(vertices[(i+1)%3],vertices[i],edge);
                subtract(core,vertices[i],side);
                cross(edge,side,product);
                double orientation = dot(normal,product);
                if (orientation < -1e-12) forward = 0;
                if (orientation > 1e-12) reverse = 0;
            }
            if (forward || reverse) {
                PyObject *hit = Py_BuildValue("(d(ddd)(ddd)((ddd)d))",fraction,normal[0],normal[1],normal[2],
                    point[0],point[1],point[2],vertices[0][0],vertices[0][1],vertices[0][2],margin);
                if (!hit) return NULL;
                return Py_BuildValue("(ON)",Py_True,hit);
            }
        }
    }
    return Py_BuildValue("(OO)",face_only ? Py_True : Py_False,Py_None);
}

static PyObject *triangle_face(PyObject *self, PyObject *args, PyObject *kwargs) {
    PyObject *start_object, *end_object, *triangle_object, *axis_object;
    double margin, radius, width, shoulder, crown, ceiling = 1.;
    int face_only = 0;
    static char *names[] = {"start","end","triangle","margin","axis","radius","width","shoulder","crown",
                            "face_only","ceiling",NULL};
    if (!PyArg_ParseTupleAndKeywords(args,kwargs,"OOOdOdddd|pd",names,&start_object,&end_object,&triangle_object,
                                    &margin,&axis_object,&radius,&width,&shoulder,&crown,&face_only,&ceiling)) return NULL;
    double start[3], end[3], vertices[3][3], axis[3];
    if (!vector(start_object,start) || !vector(end_object,end) || !vector(axis_object,axis)) return NULL;
    PyObject *triangle = PySequence_Fast(triangle_object,"三角面须为三个顶点");
    if (!triangle) return NULL;
    if (PySequence_Fast_GET_SIZE(triangle) != 3) {
        Py_DECREF(triangle); PyErr_SetString(PyExc_ValueError,"三角面须为三个顶点"); return NULL;
    }
    for (int i = 0; i < 3; ++i)
        if (!vector(PySequence_Fast_GET_ITEM(triangle,i),vertices[i])) { Py_DECREF(triangle); return NULL; }
    Py_DECREF(triangle);
    return triangle_face_values(start,end,vertices,margin,axis,radius,width,shoulder,crown,face_only,ceiling);
}

static double exact_dot(double a[3], double b[3]) {
    double terms[4] = {a[0]*b[0],a[1]*b[1],a[2]*b[2],0.};
    return sum_four(terms);
}

static double point_derivative(double q, double axial, double rho, double radius, double k) {
    double gap = rho - radius + k*q*q;
    if (gap < 0.) gap = 0.;
    return q - axial + 2*k*q*gap;
}

static int point_delta(double relative[3], double axis[3], double radius, double half_width,
                       double crown, double delta[3]) {
    double axis_squared = dot(axis,axis), axis_length = sqrt(axis_squared);
    if (axis_squared == 0. || half_width == 0.) {
        PyErr_SetString(PyExc_ZeroDivisionError,"轮轴和轮胎内核半宽不能为零"); return 0;
    }
    double axial = exact_dot(relative,axis) / axis_length, inner[3], radial[3];
    cross_precise(relative,axis,inner); cross_precise(axis,inner,radial);
    for (int i = 0; i < 3; ++i) radial[i] /= axis_squared;
    double rho = sqrt(exact_dot(radial,radial)), k = crown / pow(half_width,2.);
    if (PyErr_Occurred()) return 0;
    double q = axial < half_width ? axial : half_width;
    q = q > -half_width ? q : -half_width;
    if (point_derivative(-half_width,axial,rho,radius,k) >= 0.) q = -half_width;
    else if (point_derivative(half_width,axial,rho,radius,k) <= 0.) q = half_width;
    else {
        double low = -half_width, high = half_width;
        for (int iteration = 0; iteration < 64; ++iteration) {
            double gap = rho - radius + k*q*q;
            if (gap < 0.) gap = 0.;
            double value = q - axial + 2*k*q*gap;
            if (value == 0.) break;
            double slope = 1 + 2*k*gap + (gap != 0. ? 4*k*k*q*q : 0.);
            double candidate = q - value/slope;
            if (candidate == q) break;
            if (value > 0.) high = q; else low = q;
            if (!(low < candidate && candidate < high)) candidate = (low+high)/2;
            q = candidate;
            if (q == low || q == high) break;
        }
    }
    double gap = rho - radius + k*q*q;
    if (gap < 0.) gap = 0.;
    for (int i = 0; i < 3; ++i)
        delta[i] = (axial-q)*(axis[i]/axis_length) + (rho != 0. ? gap*radial[i]/rho : 0.);
    return 1;
}

static PyObject *point_delta_call(PyObject *self, PyObject *args, PyObject *kwargs) {
    PyObject *relative_object, *axis_object;
    double relative[3], axis[3], delta[3], radius, half_width, crown;
    static char *names[] = {"relative","axis","radius","half_width","crown",NULL};
    if (!PyArg_ParseTupleAndKeywords(args,kwargs,"OOddd",names,&relative_object,&axis_object,&radius,&half_width,&crown)) return NULL;
    if (!vector(relative_object,relative) || !vector(axis_object,axis)) return NULL;
    if (!point_delta(relative,axis,radius,half_width,crown,delta)) return NULL;
    return Py_BuildValue("(ddd)",delta[0],delta[1],delta[2]);
}

static int edge_evaluate(double t, double center[3], double axis[3], double a[3], double edge[3],
                         double radius, double half_width, double crown, double delta[3], double *derivative) {
    double relative[3];
    for (int i = 0; i < 3; ++i) {
        double terms[4] = {a[i],-center[i],t*edge[i],0.};
        relative[i] = sum_four(terms);
    }
    if (PyErr_Occurred() || !point_delta(relative,axis,radius,half_width,crown,delta)) return 0;
    *derivative = exact_dot(delta,edge);
    return !PyErr_Occurred();
}

static PyObject *edge_distance_call(PyObject *self, PyObject *args, PyObject *kwargs) {
    PyObject *center_object, *axis_object, *a_object, *b_object;
    double center[3], axis[3], a[3], b[3], edge[3], delta[3], da[3], db[3], ga, gb;
    double radius, half_width, crown, t;
    static char *names[] = {"center","axis","a","b","radius","half_width","crown",NULL};
    if (!PyArg_ParseTupleAndKeywords(args,kwargs,"OOOOddd",names,&center_object,&axis_object,&a_object,&b_object,
                                    &radius,&half_width,&crown)) return NULL;
    if (!vector(center_object,center) || !vector(axis_object,axis) || !vector(a_object,a) || !vector(b_object,b)) return NULL;
    subtract(b,a,edge);
    if (!edge_evaluate(0.,center,axis,a,edge,radius,half_width,crown,da,&ga)
        || !edge_evaluate(1.,center,axis,a,edge,radius,half_width,crown,db,&gb)) return NULL;
    if (ga >= 0.) { t = 0.; for (int i=0; i<3; ++i) delta[i] = da[i]; }
    else if (gb <= 0.) { t = 1.; for (int i=0; i<3; ++i) delta[i] = db[i]; }
    else {
        double low = 0., high = 1.;
        for (int iteration = 0; iteration < 64; ++iteration) {
            t = (low+high)/2;
            double value;
            if (!edge_evaluate(t,center,axis,a,edge,radius,half_width,crown,delta,&value)) return NULL;
            if (value == 0. || t == low || t == high) break;
            if (value > 0.) high = t; else low = t;
        }
    }
    double distance = sqrt(exact_dot(delta,delta)), normal[3], witness[3];
    for (int i = 0; i < 3; ++i) {
        normal[i] = distance != 0. ? -delta[i]/distance : (i == 2 ? 1. : 0.);
        double terms[4] = {a[i],t*edge[i],0.,0.};
        witness[i] = sum_four(terms);
    }
    if (PyErr_Occurred()) return NULL;
    return Py_BuildValue("(d(ddd)(ddd))",distance,normal[0],normal[1],normal[2],witness[0],witness[1],witness[2]);
}

static void transform_values(const double value[3],const double axes[3][3],const double offset[3],
                             int transpose,double result[3]) {
    for (int a=0; a<3; ++a) {
        double terms[3];
        for (int b=0; b<3; ++b) terms[b] = (transpose ? axes[b][a] : axes[a][b])*value[b];
        /* 与Python三项sum及其后的平移分别舍入，不融合乘加。 */
        result[a] = offset[a] + sum_three(terms);
    }
}
static PyObject *surface_transform(PyObject *self, PyObject *args, PyObject *kwargs) {
    PyObject *value_object, *axes_object, *offset_object = Py_None;
    int transpose = 0;
    static char *names[] = {"value", "axes", "offset", "transpose", NULL};
    if (!PyArg_ParseTupleAndKeywords(args,kwargs,"OO|Op",names,&value_object,&axes_object,&offset_object,&transpose))
        return NULL;
    double value[3], axes[3][3], offset[3] = {0.,0.,0.};
    if (!vector(value_object,value) || (offset_object != Py_None && !vector(offset_object,offset))) return NULL;
    PyObject *rows = PySequence_Fast(axes_object,"支持面变换须为三行矩阵");
    if (!rows) return NULL;
    if (PySequence_Fast_GET_SIZE(rows) != 3) {
        Py_DECREF(rows); PyErr_SetString(PyExc_ValueError,"支持面变换须为三行矩阵"); return NULL;
    }
    for (int i=0; i<3; ++i) {
        if (!vector(PySequence_Fast_GET_ITEM(rows,i),axes[i])) { Py_DECREF(rows); return NULL; }
    }
    Py_DECREF(rows);
    double result[3];
    transform_values(value,axes,offset,transpose,result);
    return Py_BuildValue("(ddd)",result[0],result[1],result[2]);
}

static int box_interval_values(double start[3],double end[3],double half[3],
    double *entry_out,double *exit_out,int *axis_out,double *sign_out) {
    double entry=-INFINITY,exit_time=INFINITY,sign=0.;
    int normal_axis=-1;
    for (int a=0; a<3; ++a) {
        double speed=end[a]-start[a];
        if (speed == 0.) {
            if (fabs(start[a]) > half[a]) return 0;
            continue;
        }
        double near=(-half[a]-start[a])/speed,far=(half[a]-start[a])/speed;
        if (near > far) { double swap=near; near=far; far=swap; }
        if (near > entry) { entry=near; normal_axis=a; sign=speed>0. ? -1. : 1.; }
        if (far < exit_time) exit_time=far;
        if (entry > exit_time) return 0;
    }
    *entry_out=entry; *exit_out=exit_time; *axis_out=normal_axis; *sign_out=sign;
    return 1;
}

static PyObject *box_interval_call(PyObject *self, PyObject *args, PyObject *kwargs) {
    PyObject *start_object, *end_object, *half_object;
    static char *names[] = {"start", "end", "half", NULL};
    if (!PyArg_ParseTupleAndKeywords(args,kwargs,"OOO",names,&start_object,&end_object,&half_object)) return NULL;
    double start[3],end[3],half[3];
    if (!vector(start_object,start) || !vector(end_object,end) || !vector(half_object,half)) return NULL;
    double entry,exit_time,sign;
    int normal_axis;
    if (!box_interval_values(start,end,half,&entry,&exit_time,&normal_axis,&sign)) Py_RETURN_NONE;
    PyObject *normal=normal_axis < 0 ? Py_NewRef(Py_None) : Py_BuildValue("(ddd)",
        normal_axis==0 ? sign : 0.,normal_axis==1 ? sign : 0.,normal_axis==2 ? sign : 0.);
    if (!normal) return NULL;
    PyObject *result=Py_BuildValue("(ddO)",entry,exit_time,normal);
    Py_DECREF(normal);
    return result;
}

static void rotated_path_values(double value[3],double axis[3],double angle,double scale,
                                double end[3],double average[3]) {
    if (angle==0.) { for (int a=0; a<3; ++a) { end[a]=value[a]; average[a]=value[a]; } return; }
    double projection=dot(value,axis),parallel[3],radial[3],tangent[3];
    for (int a=0; a<3; ++a) { parallel[a]=projection*axis[a]; radial[a]=value[a]-parallel[a]; }
    tangent[0]=axis[1]*value[2]-axis[2]*value[1];
    tangent[1]=axis[2]*value[0]-axis[0]*value[2];
    tangent[2]=axis[0]*value[1]-axis[1]*value[0];
    double sine=sin(angle),cosine=cos(angle),average_sine=sine/angle;
    double average_cosine=2*pow(sin(angle/2),2)/angle;
    for (int a=0; a<3; ++a) {
        end[a]=parallel[a]+cosine*radial[a]+sine*tangent[a];
        average[a]=scale*(parallel[a]+average_sine*radial[a]+average_cosine*tangent[a]);
    }
}
static PyObject *rotated_path_call(PyObject *self, PyObject *args, PyObject *kwargs) {
    PyObject *value_object,*axis_object;
    double angle,scale;
    static char *names[] = {"vector", "axis", "angle", "scale", NULL};
    if (!PyArg_ParseTupleAndKeywords(args,kwargs,"OOdd",names,&value_object,&axis_object,&angle,&scale)) return NULL;
    if (angle == 0.) return Py_BuildValue("(OO)",value_object,value_object);
    double value[3],axis[3];
    if (!vector(value_object,value) || !vector(axis_object,axis)) return NULL;
    double end[3],average[3];
    rotated_path_values(value,axis,angle,scale,end,average);
    return Py_BuildValue("((ddd)(ddd))",end[0],end[1],end[2],average[0],average[1],average[2]);
}


/* 原索引的有序筛选、有限面与首接点在一次查询内完成，边角仍交给原求解函数。 */
static int triangle_query_possible(PyObject *center_object,PyObject *half_object,
                                   double start[3],double end[3],double padding[3]) {
    double center[3],base_half[3],half[3],local_start[3],local_end[3],entry,exit_time,sign;
    int axis;
    if (!vector(center_object,center) || !vector(half_object,base_half)) return -1;
    for (int i=0; i<3; ++i) {
        half[i]=base_half[i]+padding[i]; local_start[i]=start[i]-center[i]; local_end[i]=end[i]-center[i];
    }
    return box_interval_values(local_start,local_end,half,&entry,&exit_time,&axis,&sign)
        && !(entry>1. || exit_time<0.);
}
static int triangle_query_collect(PyObject *node,double start[3],double end[3],double padding[3],PyObject *result) {
    PyObject *center=PyObject_GetAttrString(node,"center"),*half=PyObject_GetAttrString(node,"half");
    PyObject *children=NULL,*triangles=NULL,*bounds=NULL;
    int status=0;
    if (!center || !half) goto done;
    int possible=triangle_query_possible(center,half,start,end,padding);
    if (possible<0) goto done;
    if (!possible) { status=1; goto done; }
    children=PyObject_GetAttrString(node,"children");
    triangles=PyObject_GetAttrString(node,"triangles");
    bounds=PyObject_GetAttrString(node,"triangle_bounds");
    if (!children || !triangles || !bounds) goto done;
    if (!PyTuple_Check(children) || !PyTuple_Check(triangles) || !PyTuple_Check(bounds)
        || PyTuple_GET_SIZE(triangles)!=PyTuple_GET_SIZE(bounds)) {
        PyErr_SetString(PyExc_ValueError,"三角面索引结构不一致"); goto done;
    }
    for (Py_ssize_t i=0; i<PyTuple_GET_SIZE(children); ++i)
        if (!triangle_query_collect(PyTuple_GET_ITEM(children,i),start,end,padding,result)) goto done;
    for (Py_ssize_t i=0; i<PyTuple_GET_SIZE(triangles); ++i) {
        PyObject *bound=PyTuple_GET_ITEM(bounds,i);
        if (!PyTuple_Check(bound) || PyTuple_GET_SIZE(bound)!=2) {
            PyErr_SetString(PyExc_ValueError,"原三角面边界结构不一致"); goto done;
        }
        possible=triangle_query_possible(PyTuple_GET_ITEM(bound,0),PyTuple_GET_ITEM(bound,1),start,end,padding);
        if (possible<0) goto done;
        if (possible && PyList_Append(result,PyTuple_GET_ITEM(triangles,i))<0) goto done;
    }
    status=1;
done:
    Py_XDECREF(center); Py_XDECREF(half); Py_XDECREF(children); Py_XDECREF(triangles); Py_XDECREF(bounds);
    return status;
}
static int triangle_query_best(PyObject *hit,PyObject **best,double *ceiling) {
    double fraction=PyFloat_AsDouble(PyTuple_GetItem(hit,0));
    if (PyErr_Occurred()) return 0;
    if (!*best || fraction<*ceiling) {
        Py_XSETREF(*best,Py_NewRef(hit)); *ceiling=fraction;
    }
    return 1;
}
static PyObject *triangle_support_entry(PyObject *self,PyObject *args,PyObject *kwargs) {
    PyObject *node,*start_object,*end_object,*margin_object,*axis_object,*radius_object,*width_object,*shoulder_object,*crown_object,*edge_entry;
    static char *names[]={"node","start","end","margin","axis","radius","width","shoulder","crown","edge_entry",NULL};
    if (!PyArg_ParseTupleAndKeywords(args,kwargs,"OOOOOOOOOO",names,&node,&start_object,&end_object,&margin_object,
        &axis_object,&radius_object,&width_object,&shoulder_object,&crown_object,&edge_entry)) return NULL;
    double start[3],end[3],axis[3],padding[3],margin=PyFloat_AsDouble(margin_object),radius=PyFloat_AsDouble(radius_object);
    double width=PyFloat_AsDouble(width_object),shoulder=PyFloat_AsDouble(shoulder_object),crown=PyFloat_AsDouble(crown_object);
    if (PyErr_Occurred() || !vector(start_object,start) || !vector(end_object,end) || !vector(axis_object,axis)) return NULL;
    for (int i=0; i<3; ++i) {
        double direction[3]={0.},support[3]; direction[i]=1.;
        if (!support_values(direction,axis,radius,width/2,shoulder,crown,support)) return NULL;
        padding[i]=support[i]+margin;
    }
    PyObject *candidates=PyList_New(0),*curved=PyList_New(0),*best=NULL,*keywords=NULL;
    double ceiling=1.;
    if (!candidates || !curved || !triangle_query_collect(node,start,end,padding,candidates)) goto error;
    for (Py_ssize_t k=0; k<PyList_GET_SIZE(candidates); ++k) {
        PyObject *triangle=PyList_GET_ITEM(candidates,k);
        double vertices[3][3];
        if (!PyTuple_Check(triangle) || PyTuple_GET_SIZE(triangle)!=3) {
            PyErr_SetString(PyExc_ValueError,"三角面须为三个顶点"); goto error;
        }
        for (int i=0; i<3; ++i) if (!vector(PyTuple_GET_ITEM(triangle,i),vertices[i])) goto error;
        PyObject *result=triangle_face_values(start,end,vertices,margin,axis,radius,width,shoulder,crown,1,1.);
        if (!result) goto error;
        PyObject *hit=PyTuple_GET_ITEM(result,1);
        int kept=hit!=Py_None ? triangle_query_best(hit,&best,&ceiling) : PyList_Append(curved,triangle)>=0;
        Py_DECREF(result);
        if (!kept) goto error;
    }
    keywords=PyDict_New();
    if (!keywords) goto error;
    for (Py_ssize_t k=0; k<PyList_GET_SIZE(curved); ++k) {
        PyObject *arguments=PyTuple_Pack(9,start_object,end_object,PyList_GET_ITEM(curved,k),margin_object,axis_object,
                                         radius_object,width_object,shoulder_object,crown_object);
        if (!arguments) goto error;
        PyObject *limit=PyFloat_FromDouble(ceiling);
        if (!limit) { Py_DECREF(arguments); goto error; }
        int updated=PyDict_SetItemString(keywords,"ceiling",limit); Py_DECREF(limit);
        if (updated<0) { Py_DECREF(arguments); goto error; }
        PyObject *hit=PyObject_Call(edge_entry,arguments,keywords); Py_DECREF(arguments);
        if (!hit) goto error;
        int kept=hit==Py_None || triangle_query_best(hit,&best,&ceiling);
        Py_DECREF(hit);
        if (!kept) goto error;
    }
    Py_DECREF(candidates); Py_DECREF(curved); Py_DECREF(keywords);
    return best ? best : Py_NewRef(Py_None);
error:
    Py_XDECREF(candidates); Py_XDECREF(curved); Py_XDECREF(best); Py_XDECREF(keywords);
    return NULL;
}


/* 几何差量保留原逐元素减法和较短序列的元组输出。 */
static PyObject *subtract_vector(PyObject *self,PyObject *args,PyObject *kwargs) {
    PyObject *first,*second;
    static char *names[]={"a","b",NULL};
    if (!PyArg_ParseTupleAndKeywords(args,kwargs,"OO",names,&first,&second)) return NULL;
    PyObject *a=PyObject_GetIter(first),*b=PyObject_GetIter(second),*values=PyList_New(0);
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
    Py_DECREF(a); Py_DECREF(b); Py_DECREF(values); return NULL;
}

/* 原六个覆盖盒裁剪平面及fma交点；保留顶点次序和未改变顶点的对象。 */
static PyObject *clipped_triangle_call(PyObject *self,PyObject *args,PyObject *kwargs) {
    PyObject *triangle,*start_object,*end_object,*padding_object;
    static char *names[]={"triangle","start","end","padding",NULL};
    if (!PyArg_ParseTupleAndKeywords(args,kwargs,"OOOO",names,&triangle,&start_object,&end_object,&padding_object)) return NULL;
    double start[3],end[3],padding[3];
    if (!vector(start_object,start) || !vector(end_object,end) || !vector(padding_object,padding)) return NULL;
    PyObject *polygon=PySequence_List(triangle);
    if (!polygon) return NULL;
    for (int axis=0; axis<3; ++axis) for (int side=0; side<2; ++side) {
        double sign=side==0 ? 1. : -1.;
        double bound=side==0 ? (end[axis]<start[axis] ? end[axis] : start[axis])-padding[axis]
                            : (end[axis]>start[axis] ? end[axis] : start[axis])+padding[axis];
        PyObject *result=PyList_New(0);
        if (!result) { Py_DECREF(polygon); return NULL; }
        Py_ssize_t n=PyList_GET_SIZE(polygon);
        for (Py_ssize_t i=0; i<n; ++i) {
            PyObject *a_object=PyList_GET_ITEM(polygon,i),*b_object=PyList_GET_ITEM(polygon,(i+1)%n);
            double a[3],b[3];
            if (!vector(a_object,a) || !vector(b_object,b)) { Py_DECREF(polygon); Py_DECREF(result); return NULL; }
            double da=sign*(a[axis]-bound),db=sign*(b[axis]-bound);
            if (da>=0. && PyList_Append(result,a_object)<0) { Py_DECREF(polygon); Py_DECREF(result); return NULL; }
            if ((da>=0.)!=(db>=0.)) {
                double fraction=da/(da-db),point[3];
                for (int j=0; j<3; ++j) point[j]=j==axis ? bound : fma(fraction,b[j]-a[j],a[j]);
                PyObject *vertex=Py_BuildValue("(ddd)",point[0],point[1],point[2]);
                if (!vertex) { Py_DECREF(polygon); Py_DECREF(result); return NULL; }
                int appended=PyList_Append(result,vertex); Py_DECREF(vertex);
                if (appended<0) { Py_DECREF(polygon); Py_DECREF(result); return NULL; }
            }
        }
        Py_SETREF(polygon,result);
    }
    return polygon;
}

/* 保留支持面和接点对象，只合并同一射线的数值变换与有序结果装配。 */
static PyObject *surface_ray_hits(PyObject *self,PyObject *args) {
    PyObject *surfaces,*start_object,*end_object,*axis_object,*origin_object,*surface_class,*contact_class;
    double radius,reach,width,shoulder,crown;
    int relative;
    if (!PyArg_ParseTuple(args,"OOOOOdddddOOp",&surfaces,&start_object,&end_object,&axis_object,&origin_object,
                         &radius,&reach,&width,&shoulder,&crown,&surface_class,&contact_class,&relative)) return NULL;
    double start[3],end[3],origin[3];
    if (!vector(start_object,start) || !vector(end_object,end) || !vector(origin_object,origin)) return NULL;
    PyObject *hits=PyList_New(0);
    if (!hits) return NULL;
    for (Py_ssize_t k=0; k<PyList_GET_SIZE(surfaces); ++k) {
        PyObject *part=PyList_GET_ITEM(surfaces,k),*body=PyTuple_GET_ITEM(part,0),*inverse=PyTuple_GET_ITEM(part,1);
        PyObject *frame=PyTuple_GET_ITEM(part,2),*half=PyTuple_GET_ITEM(part,3),*margin=PyTuple_GET_ITEM(part,4);
        PyObject *plane=PyTuple_GET_ITEM(part,5),*triangles=PyTuple_GET_ITEM(part,6);
        double axes[3][3],offset[3],local_start[3],local_end[3];
        PyObject *surface=NULL,*found=NULL,*offset_object=NULL,*local_a=NULL,*local_b=NULL,*normal_object=NULL,*point_object=NULL,*hit=NULL;
        for (int a=0; a<3; ++a) {
            if (!vector(PyTuple_GET_ITEM(frame,a),axes[a])) goto failure;
            PyObject *cell=PyObject_CallMethod(inverse,"getCell","ii",3,a);
            if (!cell) goto failure;
            double translation=PyFloat_AsDouble(cell); Py_DECREF(cell);
            if (PyErr_Occurred()) goto failure;
            double terms[3];
            for (int b=0; b<3; ++b) terms[b]=axes[a][b]*origin[b];
            offset[a]=translation+sum_three(terms);
        }
        offset_object=Py_BuildValue("(ddd)",offset[0],offset[1],offset[2]);
        if (!offset_object) goto failure;
        surface=PyObject_CallFunction(surface_class,"OOOOddddOOdO",half,margin,frame,offset_object,
                                      radius,reach,width,shoulder,axis_object,plane,crown,triangles);
        if (!surface) goto failure;
        transform_values(start,axes,offset,0,local_start);
        transform_values(end,axes,offset,0,local_end);
        local_a=Py_BuildValue("(ddd)",local_start[0],local_start[1],local_start[2]);
        local_b=Py_BuildValue("(ddd)",local_end[0],local_end[1],local_end[2]);
        if (!local_a || !local_b) goto failure;
        found=PyObject_CallMethod(surface,"entry","OOO",local_a,local_b,axis_object);
        if (!found) goto failure;
        if (found!=Py_None) {
            double normal[3],point[3],world_normal[3],world_point[3],zero[3]={0.};
            if (!vector(PyTuple_GET_ITEM(found,1),normal) || !vector(PyTuple_GET_ITEM(found,2),point)) goto failure;
            for (int a=0; a<3; ++a) point[a]=point[a]-offset[a];
            transform_values(normal,axes,zero,1,world_normal);
            transform_values(point,axes,zero,1,world_point);
            if (!relative) for (int a=0; a<3; ++a) world_point[a]=world_point[a]+origin[a];
            normal_object=Py_BuildValue("(ddd)",world_normal[0],world_normal[1],world_normal[2]);
            point_object=Py_BuildValue("(ddd)",world_point[0],world_point[1],world_point[2]);
            if (!normal_object || !point_object) goto failure;
            hit=PyObject_CallFunctionObjArgs(contact_class,body,PyTuple_GET_ITEM(found,0),point_object,normal_object,
                                            surface,PyTuple_GET_ITEM(found,3),NULL);
            if (!hit || PyList_Append(hits,hit)<0) goto failure;
        }
        Py_XDECREF(hit); Py_XDECREF(point_object); Py_XDECREF(normal_object);
        Py_DECREF(found); Py_DECREF(local_b); Py_DECREF(local_a); Py_DECREF(surface); Py_DECREF(offset_object);
        continue;
failure:
        Py_XDECREF(hit); Py_XDECREF(point_object); Py_XDECREF(normal_object);
        Py_XDECREF(found); Py_XDECREF(local_b); Py_XDECREF(local_a); Py_XDECREF(surface); Py_XDECREF(offset_object);
        Py_DECREF(hits); return NULL;
    }
    return hits;
}

/* 胎冠高度的原割线；同分区代数式与跨分区完整差商保持。 */
static double crown_secant_value(double a0,double a1,double radius,double half_width,double shoulder,double crown) {
    double half=half_width-shoulder,core=radius-shoulder;
    double r0=1-a0*a0,r1=1-a1*a1;
    double b0=sqrt(r0>0. ? r0 : 0.),b1=sqrt(r1>0. ? r1 : 0.);
    int inside0=crown>0. && fabs(a0)*half<2*crown*b0;
    int inside1=crown>0. && fabs(a1)*half<2*crown*b1;
    double radial=b0+b1!=0. ? -(a0+a1)/(b0+b1) : 0.;
    if (inside0 && inside1)
        return core*radial+pow(half,2.)/(4*crown)*((a0+a1)-a0*a0*radial/b0)/b1;
    if (!inside0 && !inside1) {
        double axial=a1!=a0 ? (fabs(a1)-fabs(a0))/(a1-a0) : (a0!=0. ? copysign(1.,a0) : 0.);
        return half*axial+(core-crown)*radial;
    }
    double h0=inside0 ? core*b0+pow(half,2.)*a0*a0/(4*crown*b0) : half*fabs(a0)+(core-crown)*b0;
    double h1=inside1 ? core*b1+pow(half,2.)*a1*a1/(4*crown*b1) : half*fabs(a1)+(core-crown)*b1;
    return (h1-h0)/(a1-a0);
}
static PyObject *crown_extent_secant(PyObject *self,PyObject *args) {
    double a0,a1,radius,half_width,shoulder,crown;
    if (!PyArg_ParseTuple(args,"dddddd",&a0,&a1,&radius,&half_width,&shoulder,&crown)) return NULL;
    return PyFloat_FromDouble(crown_secant_value(a0,a1,radius,half_width,shoulder,crown));
}
static int vector_attribute(PyObject *object,const char *name,double values[3]) {
    PyObject *value=PyObject_GetAttrString(object,name);
    if (!value) return 0;
    int result=vector(value,values); Py_DECREF(value); return result;
}
static int double_attribute(PyObject *object,const char *name,double *value) {
    PyObject *number=PyObject_GetAttrString(object,name);
    if (!number) return 0;
    *value=PyFloat_AsDouble(number); Py_DECREF(number); return !PyErr_Occurred();
}
static void cross_regular(double a[3],double b[3],double result[3]) {
    result[0]=a[1]*b[2]-a[2]*b[1];
    result[1]=a[2]*b[0]-a[0]*b[2];
    result[2]=a[0]*b[1]-a[1]*b[0];
}
/* 查询仍回到原支持面；同平面和跨面分别保留原功共轭公式。 */
static PyObject *cylinder_endpoint_values(PyObject *contact,
    double hub_end[3],double hub_average[3],double direction_end[3],double direction_average[3],
    double rotation_axis[3],double angle,double scale,double velocity[3],double angular[3],double dt,
    PyObject *hub_average_object,PyObject *direction_average_object,PyObject *rotation_axis_object,
    PyObject *velocity_object,PyObject *angular_object,PyObject *face_difference) {
    PyObject *owned_hub_average=NULL,*owned_direction_average=NULL;
    PyObject *surface=PyObject_GetAttrString(contact,"surface"),*old_normal_object=NULL,*wheel_object=NULL;
    PyObject *found=NULL,*start_object=NULL,*end_object=NULL,*difference_object=NULL;
    double old_axis[3],old_normal[3],old_direction[3],old_hub[3],old_point[3],radius,reach,width,shoulder,crown,old_length;
    if (!surface || !vector_attribute(surface,"wheel_axis",old_axis) || !double_attribute(surface,"wheel_radius",&radius)
        || !double_attribute(surface,"reach",&reach) || !double_attribute(surface,"width",&width)
        || !double_attribute(surface,"shoulder",&shoulder) || !double_attribute(surface,"crown",&crown)
        || !vector_attribute(contact,"direction",old_direction) || !vector_attribute(contact,"hub",old_hub)
        || !vector_attribute(contact,"point",old_point) || !double_attribute(contact,"length",&old_length)) goto failure;
    old_normal_object=PyObject_GetAttrString(contact,"normal");
    if (!old_normal_object || !vector(old_normal_object,old_normal)) goto failure;
    double wheel_axis[3],wheel_average[3],start[3],end[3];
    rotated_path_values(old_axis,rotation_axis,angle,scale,wheel_axis,wheel_average);
    for (int a=0; a<3; ++a) {
        double hub=hub_end[a]+dt*velocity[a];
        start[a]=hub-radius*direction_end[a]; end[a]=hub+reach*direction_end[a];
    }
    wheel_object=Py_BuildValue("(ddd)",wheel_axis[0],wheel_axis[1],wheel_axis[2]);
    start_object=Py_BuildValue("(ddd)",start[0],start[1],start[2]);
    end_object=Py_BuildValue("(ddd)",end[0],end[1],end[2]);
    if (!wheel_object || !start_object || !end_object) goto failure;
    found=PyObject_CallMethod(surface,"relative_entry","OOO",start_object,end_object,wheel_object);
    if (!found) goto failure;
    if (found==Py_None) goto no_contact;
    double normal[3],endpoint[3],fraction=PyFloat_AsDouble(PyTuple_GET_ITEM(found,0));
    if (PyErr_Occurred() || !vector(PyTuple_GET_ITEM(found,1),normal) || !vector(PyTuple_GET_ITEM(found,2),endpoint)) goto failure;
    double length=-radius+fraction*(radius+reach),alignment=-dot(normal,direction_end);
    if (alignment<=0.) goto no_contact;
    int equal=PyObject_RichCompareBool(PyTuple_GET_ITEM(found,1),old_normal_object,Py_EQ);
    if (equal<0) goto failure;
    double change[3];
    for (int a=0; a<3; ++a) change[a]=endpoint[a]-old_point[a];
    double gradient[6];
    if (equal && fabs(dot(normal,change))<=1e-10) {
        double a0=-dot(normal,old_direction),reciprocal=(1/a0+1/alignment)/2;
        double extent=crown_secant_value(dot(normal,old_axis),dot(normal,wheel_axis),radius,width/2,shoulder,crown);
        double p0=a0*old_length;
        for (int a=0; a<3; ++a) change[a]=wheel_axis[a]-old_axis[a];
        double axis_change=dot(normal,change);
        for (int a=0; a<3; ++a) change[a]=dt*velocity[a]+hub_end[a]-old_hub[a];
        double p1=p0+dot(normal,change)-extent*axis_change,arm[3],moment[3];
        for (int a=0; a<3; ++a) arm[a]=reciprocal*(hub_average[a]-extent*wheel_average[a])
                                           +(p0+p1)/(2*a0*alignment)*direction_average[a];
        cross_regular(arm,normal,moment);
        for (int a=0; a<3; ++a) { gradient[a]=reciprocal*normal[a]; gradient[a+3]=moment[a]; }
        alignment=1/reciprocal;
    } else {
        double endpoint_arm[3],old_moment[3],new_moment[3],old_alignment=-dot(old_normal,old_direction);
        for (int a=0; a<3; ++a) endpoint_arm[a]=endpoint[a]-dt*velocity[a];
        cross_regular(old_point,old_normal,old_moment); cross_regular(endpoint_arm,normal,new_moment);
        double speed[6],terms[6];
        for (int a=0; a<3; ++a) {
            gradient[a]=(old_normal[a]/old_alignment+normal[a]/alignment)/2;
            gradient[a+3]=scale*(old_moment[a]/old_alignment+new_moment[a]/alignment)/2;
            speed[a]=velocity[a]; speed[a+3]=angular[a];
        }
        for (int a=0; a<6; ++a) terms[a]=speed[a]*speed[a];
        double squared=sum_values(terms,6);
        if (squared!=0.) {
            double difference;
            PyObject *face=PyTuple_GET_ITEM(found,3);
            if (face!=Py_None) {
                if (!hub_average_object) {
                    owned_hub_average=Py_BuildValue("(ddd)",hub_average[0],hub_average[1],hub_average[2]);
                    if (!owned_hub_average) goto failure;
                    hub_average_object=owned_hub_average;
                }
                if (!direction_average_object) {
                    owned_direction_average=Py_BuildValue("(ddd)",direction_average[0],direction_average[1],direction_average[2]);
                    if (!owned_direction_average) goto failure;
                    direction_average_object=owned_direction_average;
                }
                difference_object=PyObject_CallFunction(face_difference,"OOOOOOOddOOd",contact,PyTuple_GET_ITEM(found,1),face,
                    wheel_object,hub_average_object,direction_average_object,rotation_axis_object,angle,scale,
                    velocity_object,angular_object,dt);
                if (!difference_object) goto failure;
                difference=PyFloat_AsDouble(difference_object);
                if (PyErr_Occurred()) goto failure;
            } else difference=length-old_length;
            for (int a=0; a<6; ++a) terms[a]=gradient[a]*speed[a];
            double correction=(difference/dt-sum_values(terms,6))/squared;
            for (int a=0; a<6; ++a) gradient[a]=gradient[a]+correction*speed[a];
        }
    }
    PyObject *result=Py_BuildValue("((dddddd)d)",gradient[0],gradient[1],gradient[2],gradient[3],gradient[4],gradient[5],alignment);
    Py_XDECREF(owned_hub_average); Py_XDECREF(owned_direction_average);
    Py_XDECREF(difference_object); Py_DECREF(found); Py_DECREF(end_object); Py_DECREF(start_object);
    Py_DECREF(wheel_object); Py_DECREF(old_normal_object); Py_DECREF(surface); return result;
no_contact:
    Py_XDECREF(owned_hub_average); Py_XDECREF(owned_direction_average);
    Py_XDECREF(found); Py_XDECREF(end_object); Py_XDECREF(start_object); Py_XDECREF(wheel_object);
    Py_XDECREF(old_normal_object); Py_XDECREF(surface); Py_RETURN_NONE;
failure:
    Py_XDECREF(owned_hub_average); Py_XDECREF(owned_direction_average);
    Py_XDECREF(difference_object); Py_XDECREF(found); Py_XDECREF(end_object); Py_XDECREF(start_object);
    Py_XDECREF(wheel_object); Py_XDECREF(old_normal_object); Py_XDECREF(surface); return NULL;
}
static PyObject *cylinder_endpoint(PyObject *self,PyObject *args) {
    PyObject *contact,*hub_end_object,*hub_average_object,*direction_end_object,*direction_average_object;
    PyObject *rotation_axis_object,*velocity_object,*angular_object,*face_difference;
    double angle,scale,dt;
    if (!PyArg_ParseTuple(args,"OOOOOOddOOdO",&contact,&hub_end_object,&hub_average_object,
        &direction_end_object,&direction_average_object,&rotation_axis_object,&angle,&scale,
        &velocity_object,&angular_object,&dt,&face_difference)) return NULL;
    double hub_end[3],hub_average[3],direction_end[3],direction_average[3],rotation_axis[3],velocity[3],angular[3];
    if (!vector(hub_end_object,hub_end) || !vector(hub_average_object,hub_average)
        || !vector(direction_end_object,direction_end) || !vector(direction_average_object,direction_average)
        || !vector(rotation_axis_object,rotation_axis) || !vector(velocity_object,velocity) || !vector(angular_object,angular)) return NULL;
    return cylinder_endpoint_values(contact,hub_end,hub_average,direction_end,direction_average,
        rotation_axis,angle,scale,velocity,angular,dt,hub_average_object,direction_average_object,
        rotation_axis_object,velocity_object,angular_object,face_difference);
}

/* 四轮共用有限转动与接点装配；每个支持面仍执行原relative_entry。 */
static PyObject *cylinder_contact_system(PyObject *self,PyObject *args) {
    PyObject *contacts,*axis_object,*velocity_object,*angular_object,*face_difference;
    double angle,scale,dt,axis[3],velocity[3],angular[3];
    if (!PyArg_ParseTuple(args,"OOddOOdO",&contacts,&axis_object,&angle,&scale,
        &velocity_object,&angular_object,&dt,&face_difference)) return NULL;
    if (!vector(axis_object,axis) || !vector(velocity_object,velocity) || !vector(angular_object,angular)) return NULL;
    Py_ssize_t count=PyTuple_Size(contacts);
    if (count<0) return NULL;
    PyObject *gradients=PyTuple_New(count),*alignment=PyTuple_New(count),*touching=PyTuple_New(count);
    if (!gradients || !alignment || !touching) goto failure;
    for (Py_ssize_t i=0; i<count; ++i) {
        PyObject *contact=PyTuple_GET_ITEM(contacts,i),*endpoint;
        if (contact==Py_None) { endpoint=Py_NewRef(Py_None); }
        else {
            double hub[3],direction[3],hub_end[3],hub_average[3],direction_end[3],direction_average[3];
            if (!vector_attribute(contact,"hub",hub) || !vector_attribute(contact,"direction",direction)) goto failure;
            rotated_path_values(hub,axis,angle,scale,hub_end,hub_average);
            rotated_path_values(direction,axis,angle,scale,direction_end,direction_average);
            endpoint=cylinder_endpoint_values(contact,hub_end,hub_average,direction_end,direction_average,
                axis,angle,scale,velocity,angular,dt,NULL,NULL,axis_object,velocity_object,angular_object,face_difference);
            if (!endpoint) goto failure;
        }
        if (endpoint==Py_None) {
            PyObject *zero=Py_BuildValue("(dddddd)",0.,0.,0.,0.,0.,0.);
            if (!zero) { Py_DECREF(endpoint); goto failure; }
            PyTuple_SET_ITEM(gradients,i,zero);
            PyTuple_SET_ITEM(alignment,i,Py_NewRef(Py_None));
            PyTuple_SET_ITEM(touching,i,Py_NewRef(Py_False));
        } else {
            PyTuple_SET_ITEM(gradients,i,Py_NewRef(PyTuple_GET_ITEM(endpoint,0)));
            PyTuple_SET_ITEM(alignment,i,Py_NewRef(PyTuple_GET_ITEM(endpoint,1)));
            PyTuple_SET_ITEM(touching,i,Py_NewRef(Py_True));
        }
        Py_DECREF(endpoint);
    }
    return Py_BuildValue("NNN",gradients,alignment,touching);
failure:
    Py_XDECREF(gradients); Py_XDECREF(alignment); Py_XDECREF(touching); return NULL;
}

static PyMethodDef methods[] = {
    {"cylinder_contact_system", (PyCFunction)cylinder_contact_system, METH_VARARGS, "原四轮有限接点几何与装配"},
    {"crown_extent_secant", (PyCFunction)crown_extent_secant, METH_VARARGS, "原胎冠支持高度割线"},
    {"cylinder_endpoint", (PyCFunction)cylinder_endpoint, METH_VARARGS, "原有限圆柱接点与功共轭离散梯度"},
    {"surface_ray_hits", (PyCFunction)surface_ray_hits, METH_VARARGS, "原有限支持面射线变换及有序接点装配"},
    {"subtract", (PyCFunction)subtract_vector, METH_VARARGS | METH_KEYWORDS, "原逐元素几何差量"},
    {"clipped_triangle", (PyCFunction)clipped_triangle_call, METH_VARARGS | METH_KEYWORDS, "原有限三角面六平面精确裁剪"},
    {"triangle_support_entry", (PyCFunction)triangle_support_entry, METH_VARARGS | METH_KEYWORDS, "原有限三角面有序查询及首接点"},
    {"support_candidates", (PyCFunction)support_candidates, METH_VARARGS | METH_KEYWORDS, "真实形状边界的原批量覆盖盒筛选"},
    {"box_interval", (PyCFunction)box_interval_call, METH_VARARGS | METH_KEYWORDS, "原三轴线段包围盒区间"},
    {"rotated_path", (PyCFunction)rotated_path_call, METH_VARARGS | METH_KEYWORDS, "原有限转动末向量与共轭平均"},
    {"surface_transform", (PyCFunction)surface_transform, METH_VARARGS | METH_KEYWORDS, "支持面三维变换原舍入次序"},
    {"cylinder_support", (PyCFunction)support, METH_VARARGS | METH_KEYWORDS, "有限胎宽原支持函数"},
    {"triangle_face", (PyCFunction)triangle_face, METH_VARARGS | METH_KEYWORDS, "原有限三角面入射与覆盖判据"},
    {"cylinder_point_delta", (PyCFunction)point_delta_call, METH_VARARGS | METH_KEYWORDS, "原胎冠点驻点"},
    {"cylinder_edge_distance", (PyCFunction)edge_distance_call, METH_VARARGS | METH_KEYWORDS, "原有限边胎冠驻点"},
    {NULL,NULL,0,NULL}
};
static struct PyModuleDef module = {PyModuleDef_HEAD_INIT, "wheel_contact_kernels", NULL, -1, methods};
PyMODINIT_FUNC PyInit_wheel_contact_kernels(void) { return PyModule_Create(&module); }

#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <math.h>

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

static double sum_three(double values[3]) {
    double main = 0., correction = 0.;
    for (int i = 0; i < 3; ++i) {
        double next = main + values[i];
        correction += fabs(main) >= fabs(values[i])
            ? (main-next)+values[i] : (values[i]-next)+main;
        main = next;
    }
    return correction != 0. && isfinite(correction) ? main + correction : main;
}

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

static PyMethodDef methods[] = {
    {"cylinder_support", (PyCFunction)support, METH_VARARGS | METH_KEYWORDS, "有限胎宽原支持函数"},
    {"triangle_face", (PyCFunction)triangle_face, METH_VARARGS | METH_KEYWORDS, "原有限三角面入射与覆盖判据"},
    {NULL,NULL,0,NULL}
};
static struct PyModuleDef module = {PyModuleDef_HEAD_INIT, "_support_probe", NULL, -1, methods};
PyMODINIT_FUNC PyInit__support_probe(void) { return PyModule_Create(&module); }

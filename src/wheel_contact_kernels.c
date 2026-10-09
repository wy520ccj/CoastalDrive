#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <math.h>
#include <string.h>

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
        PyObject *item=PySequence_Fast_GET_ITEM(sequence,i);
        if (PyFloat_CheckExact(item)) values[i]=PyFloat_AS_DOUBLE(item);
        else {
            values[i]=PyFloat_AsDouble(item);
            if (PyErr_Occurred()) { Py_DECREF(sequence); return 0; }
        }
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

/* 静态分区一次解包；每次覆盖盒查询仍执行同一精确投影与有序筛选。 */
typedef struct {
    int frame,bounded;
    double translation[3],low[3],high[3];
    PyObject *source;
} SupportPart;
typedef struct { Py_ssize_t first,count; PyObject *source; } SupportGroup;
typedef struct {
    Py_ssize_t group_count,part_count,frame_count;
    PyObject *owners;
    SupportGroup *groups;
    SupportPart *parts;
    double (*frames)[3][3];
} SupportPacket;
static const char *support_packet_name="CoastalDrive.static_support";
static void support_packet_free(SupportPacket *data) {
    Py_XDECREF(data->owners); PyMem_Free(data->groups); PyMem_Free(data->parts); PyMem_Free(data->frames); PyMem_Free(data);
}
static void release_support_packet(PyObject *object) {
    SupportPacket *data=PyCapsule_GetPointer(object,support_packet_name);
    if (data) support_packet_free(data);
}
static PyObject *support_coefficients(PyObject *self,PyObject *args) {
    PyObject *groups;
    if (!PyArg_ParseTuple(args,"O",&groups)) return NULL;
    SupportPacket *data=PyMem_Calloc(1,sizeof(SupportPacket));
    if (!data) return PyErr_NoMemory();
    PyObject *frames=PyDict_New();
    if (!frames) {support_packet_free(data); return NULL;}
    data->group_count=PyTuple_Size(groups);
    if (data->group_count<0) goto error;
    for (Py_ssize_t i=0;i<data->group_count;++i) {
        PyObject *group=PyTuple_GET_ITEM(groups,i);
        if (!PyTuple_Check(group) || PyTuple_GET_SIZE(group)!=3 || !PyTuple_Check(PyTuple_GET_ITEM(group,2))) {
            PyErr_SetString(PyExc_ValueError,"静态支持分区结构错误"); goto error;
        }
        data->part_count+=PyTuple_GET_SIZE(PyTuple_GET_ITEM(group,2));
    }
    data->groups=PyMem_Calloc(data->group_count,sizeof(SupportGroup));
    data->parts=PyMem_Calloc(data->part_count,sizeof(SupportPart));
    data->frames=PyMem_Malloc(data->part_count*sizeof(*data->frames));
    if ((data->group_count && !data->groups) || (data->part_count && (!data->parts || !data->frames))) {
        PyErr_NoMemory(); goto error;
    }
    Py_ssize_t index=0;
    for (Py_ssize_t i=0;i<data->group_count;++i) {
        SupportGroup *group=&data->groups[i]; group->source=PyTuple_GET_ITEM(groups,i); group->first=index;
        PyObject *parts=PyTuple_GET_ITEM(group->source,2); group->count=PyTuple_GET_SIZE(parts);
        for (Py_ssize_t j=0;j<group->count;++j,++index) {
            SupportPart *part=&data->parts[index]; part->source=PyTuple_GET_ITEM(parts,j);
            if (!PyTuple_Check(part->source) || PyTuple_GET_SIZE(part->source)!=8) {
                PyErr_SetString(PyExc_ValueError,"静态支持形状结构错误"); goto error;
            }
            PyObject *frame=PyTuple_GET_ITEM(part->source,1),*known=PyDict_GetItemWithError(frames,frame);
            if (!known && PyErr_Occurred()) goto error;
            if (!known) {
                if (!PyTuple_Check(frame) || PyTuple_GET_SIZE(frame)!=3) {
                    PyErr_SetString(PyExc_ValueError,"静态支持旋转须为三维"); goto error;
                }
                part->frame=(int)data->frame_count++;
                for (int a=0;a<3;++a) if (!vector(PyTuple_GET_ITEM(frame,a),data->frames[part->frame][a])) goto error;
                PyObject *number=PyLong_FromLong(part->frame);
                if (!number) goto error;
                int inserted=PyDict_SetItem(frames,frame,number); Py_DECREF(number);
                if (inserted<0) goto error;
            } else {
                part->frame=(int)PyLong_AsLong(known); if (PyErr_Occurred()) goto error;
            }
            if (!vector(PyTuple_GET_ITEM(part->source,2),part->translation)) goto error;
            PyObject *bounds=PyTuple_GET_ITEM(part->source,7);
            part->bounded=bounds!=Py_None;
            if (part->bounded) {
                if (!PyTuple_Check(bounds) || PyTuple_GET_SIZE(bounds)!=2) {
                    PyErr_SetString(PyExc_ValueError,"静态支持边界须含上下界"); goto error;
                }
                if (!vector(PyTuple_GET_ITEM(bounds,0),part->low) || !vector(PyTuple_GET_ITEM(bounds,1),part->high)) goto error;
            }
        }
    }
    data->owners=Py_NewRef(groups); Py_DECREF(frames);
    PyObject *result=PyCapsule_New(data,support_packet_name,release_support_packet);
    if (!result) support_packet_free(data);
    return result;
error:
    Py_DECREF(frames); support_packet_free(data); return NULL;
}

static PyObject *prepared_support_candidates(PyObject *self,PyObject *args) {
    PyObject *coefficients,*low_object,*high_object;
    if (!PyArg_ParseTuple(args,"OOO",&coefficients,&low_object,&high_object)) return NULL;
    SupportPacket *data=PyCapsule_GetPointer(coefficients,support_packet_name);
    double low[3],high[3],center[3],half[3];
    if (!data || !vector(low_object,low) || !vector(high_object,high)) return NULL;
    for (int a=0;a<3;++a) {center[a]=(low[a]+high[a])/2; half[a]=(high[a]-low[a])/2;}
    double (*projection)[6]=PyMem_Malloc(data->frame_count*sizeof(*projection));
    PyObject **half_objects=PyMem_Calloc(data->frame_count,sizeof(PyObject *));
    PyObject *result=PyList_New(0),*selected=NULL;
    if ((data->frame_count && (!projection || !half_objects)) || !result) {
        PyErr_NoMemory(); goto error;
    }
    for (Py_ssize_t i=0;i<data->frame_count;++i) for (int a=0;a<3;++a) {
        double terms[3];
        for (int b=0;b<3;++b) terms[b]=data->frames[i][a][b]*center[b];
        projection[i][a]=sum_three(terms);
        for (int b=0;b<3;++b) terms[b]=fabs(data->frames[i][a][b])*half[b];
        projection[i][a+3]=sum_three(terms);
    }
    for (Py_ssize_t i=0;i<data->group_count;++i) {
        SupportGroup *group=&data->groups[i]; selected=PyList_New(0);
        if (!selected) goto error;
        for (Py_ssize_t j=0;j<group->count;++j) {
            SupportPart *part=&data->parts[group->first+j]; double local[3],*frame=projection[part->frame]; int separated=0;
            for (int a=0;a<3;++a) {
                local[a]=part->translation[a]+frame[a];
                if (part->bounded && (local[a]+frame[a+3]<part->low[a] || local[a]-frame[a+3]>part->high[a])) separated=1;
            }
            if (separated) continue;
            if (!half_objects[part->frame]) {
                half_objects[part->frame]=Py_BuildValue("(ddd)",frame[3],frame[4],frame[5]);
                if (!half_objects[part->frame]) goto error;
            }
            PyObject *entry=Py_BuildValue("(O(ddd)O)",part->source,local[0],local[1],local[2],half_objects[part->frame]);
            if (!entry) goto error;
            int added=PyList_Append(selected,entry); Py_DECREF(entry);
            if (added<0) goto error;
        }
        if (PyList_GET_SIZE(selected)) {
            PyObject *entry=Py_BuildValue("(OOO)",PyTuple_GET_ITEM(group->source,0),PyTuple_GET_ITEM(group->source,1),selected);
            if (!entry) goto error;
            int added=PyList_Append(result,entry); Py_DECREF(entry);
            if (added<0) goto error;
        }
        Py_CLEAR(selected);
    }
    for (Py_ssize_t i=0;i<data->frame_count;++i) Py_XDECREF(half_objects[i]);
    PyMem_Free(projection); PyMem_Free(half_objects); return result;
error:
    if (half_objects) for (Py_ssize_t i=0;i<data->frame_count;++i) Py_XDECREF(half_objects[i]);
    PyMem_Free(projection); PyMem_Free(half_objects); Py_XDECREF(result); Py_XDECREF(selected); return NULL;
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

typedef struct {
    double normal[3], offset[3];
    int valid;
} FaceSupport;

typedef struct {
    int found,face;
    double fraction,normal[3],point[3],anchor[3],margin;
} SurfaceEntry;

static PyObject *surface_entry_object(const SurfaceEntry *entry) {
    if (!entry->found) return Py_NewRef(Py_None);
    PyObject *face=entry->face ? Py_BuildValue("((ddd)d)",entry->anchor[0],entry->anchor[1],entry->anchor[2],entry->margin)
                             : Py_NewRef(Py_None);
    if (!face) return NULL;
    return Py_BuildValue("(d(ddd)(ddd)N)",entry->fraction,entry->normal[0],entry->normal[1],entry->normal[2],
                         entry->point[0],entry->point[1],entry->point[2],face);
}

/* 既有单面入口与整条查询共用原有限面判据。 */
static int triangle_face_result(double start[3],double end[3],double vertices[3][3],
    double margin,double axis[3],double radius,double width,double shoulder,double crown,
    int face_only,double ceiling,double *fraction_bound,double *prepared_normal,FaceSupport *support_cache,
    SurfaceEntry *entry,int *finished) {
    entry->found=0; *finished=face_only;
    if (fraction_bound) *fraction_bound=-INFINITY;
    double ab[3], ac[3], normal[3], velocity[3], relative[3], offset[3];
    if (prepared_normal) {
        for (int i=0;i<3;++i) normal[i]=prepared_normal[i];
        if (normal[0]==0. && normal[1]==0. && normal[2]==0.) {
            PyErr_SetString(PyExc_ZeroDivisionError,"三角面不能退化"); return 0;
        }
    } else {
        subtract(vertices[1],vertices[0],ab); subtract(vertices[2],vertices[0],ac);
        cross(ab,ac,normal);
        double length = sqrt(dot(normal,normal));
        if (length == 0.) { PyErr_SetString(PyExc_ZeroDivisionError,"三角面不能退化"); return 0; }
        for (int i = 0; i < 3; ++i) normal[i] /= length;
    }
    subtract(end,start,velocity);
    if (dot(normal,velocity) > 0.) for (int i = 0; i < 3; ++i) normal[i] = -normal[i];
    if (support_cache && support_cache->valid && memcmp(normal,support_cache->normal,sizeof(normal))==0) {
        for (int i=0;i<3;++i) offset[i]=support_cache->offset[i];
    } else {
        if (!support_values(normal,axis,radius,width/2,shoulder,crown,offset)) return 0;
        if (support_cache) {
            for (int i=0;i<3;++i) { support_cache->normal[i]=normal[i]; support_cache->offset[i]=offset[i]; }
            support_cache->valid=1;
        }
    }
    subtract(start,vertices[0],relative);
    double distance = dot(normal,relative) - dot(normal,offset) - margin, speed = dot(normal,velocity);
    if (speed < 0. && distance >= 0.) {
        double fraction = -distance / speed;
        if (fraction_bound) *fraction_bound=fraction;
        if (!face_only && fraction >= ceiling) { *finished=1; return 1; }
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
                entry->found=entry->face=*finished=1; entry->fraction=fraction; entry->margin=margin;
                for (int i=0;i<3;++i) { entry->normal[i]=normal[i]; entry->point[i]=point[i]; entry->anchor[i]=vertices[0][i]; }
                return 1;
            }
        }
    }
    return 1;
}

static PyObject *triangle_face_values(double start[3],double end[3],double vertices[3][3],
    double margin,double axis[3],double radius,double width,double shoulder,double crown,
    int face_only,double ceiling,double *fraction_bound,double *prepared_normal,FaceSupport *support_cache) {
    SurfaceEntry entry={0}; int finished;
    if (!triangle_face_result(start,end,vertices,margin,axis,radius,width,shoulder,crown,
        face_only,ceiling,fraction_bound,prepared_normal,support_cache,&entry,&finished)) return NULL;
    PyObject *hit=surface_entry_object(&entry);
    if (!hit) return NULL;
    return Py_BuildValue("(ON)",finished ? Py_True : Py_False,hit);
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
    return triangle_face_values(start,end,vertices,margin,axis,radius,width,shoulder,crown,face_only,ceiling,NULL,NULL,NULL);
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

static int point_delta_values(double relative[3], double axis[3], double radius, double half_width,
                       double crown, double delta[3], double direction[3], double *curvature) {
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
    if (curvature) {
        double axial_rate=exact_dot(direction,axis)/axis_length;
        double radial_rate=rho!=0. ? exact_dot(direction,radial)/rho : 0.;
        double terms[4]={axial_rate*axial_rate,0.,0.,0.};
        if (gap!=0.) {
            terms[1]=radial_rate*radial_rate;
            double tangent=exact_dot(direction,direction)-terms[0]-terms[1];
            terms[3]=rho!=0. ? gap/rho*tangent : 0.;
        }
        if (q!=-half_width && q!=half_width) {
            double projection=axial_rate-(gap!=0. ? 2*k*q*radial_rate : 0.);
            double slope=1+2*k*gap+(gap!=0. ? 4*k*k*q*q : 0.);
            terms[2]=-projection*projection/slope;
        }
        *curvature=sum_four(terms);
    }
    return 1;
}

static int point_delta(double relative[3],double axis[3],double radius,double half_width,
                       double crown,double delta[3]) {
    return point_delta_values(relative,axis,radius,half_width,crown,delta,NULL,NULL);
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
                         double radius, double half_width, double crown, double delta[3], double *derivative,
                         double *curvature) {
    double relative[3];
    for (int i = 0; i < 3; ++i) {
        double terms[4] = {a[i],-center[i],t*edge[i],0.};
        relative[i] = sum_four(terms);
    }
    if (PyErr_Occurred() || !point_delta_values(relative,axis,radius,half_width,crown,delta,edge,curvature)) return 0;
    *derivative = exact_dot(delta,edge);
    return !PyErr_Occurred();
}

static int edge_distance_values(double center[3], double axis[3], double a[3], double b[3],
    double radius, double half_width, double crown, double *distance, double normal[3], double witness[3]) {
    double edge[3], delta[3], da[3], db[3], ga, gb, t;
    subtract(b,a,edge);
    if (!edge_evaluate(0.,center,axis,a,edge,radius,half_width,crown,da,&ga,NULL)
        || !edge_evaluate(1.,center,axis,a,edge,radius,half_width,crown,db,&gb,NULL)) return 0;
    if (ga >= 0.) { t = 0.; for (int i=0; i<3; ++i) delta[i] = da[i]; }
    else if (gb <= 0.) { t = 1.; for (int i=0; i<3; ++i) delta[i] = db[i]; }
    else {
        double low = 0., high = 1.; t=.5;
        for (int iteration = 0; iteration < 64; ++iteration) {
            double value,slope;
            if (!edge_evaluate(t,center,axis,a,edge,radius,half_width,crown,delta,&value,&slope)) return 0;
            if (value == 0. || t == low || t == high) break;
            if (value > 0.) high = t; else low = t;
            // 凸距离的解析导数加保守区间；平坦段及越界试探仍走二分。
            double candidate=slope>0. ? t-value/slope : (low+high)/2;
            if (candidate==t) break;
            if (!(low<candidate && candidate<high)) candidate=(low+high)/2;
            t=candidate;
        }
    }
    *distance = sqrt(exact_dot(delta,delta));
    for (int i = 0; i < 3; ++i) {
        normal[i] = *distance != 0. ? -delta[i]/ *distance : (i == 2 ? 1. : 0.);
        double terms[4] = {a[i],t*edge[i],0.,0.};
        witness[i] = sum_four(terms);
    }
    return !PyErr_Occurred();
}

static PyObject *edge_distance_call(PyObject *self, PyObject *args, PyObject *kwargs) {
    PyObject *center_object, *axis_object, *a_object, *b_object;
    double center[3], axis[3], a[3], b[3], distance, normal[3], witness[3];
    double radius, half_width, crown;
    static char *names[] = {"center","axis","a","b","radius","half_width","crown",NULL};
    if (!PyArg_ParseTupleAndKeywords(args,kwargs,"OOOOddd",names,&center_object,&axis_object,&a_object,&b_object,
                                    &radius,&half_width,&crown)) return NULL;
    if (!vector(center_object,center) || !vector(axis_object,axis) || !vector(a_object,a) || !vector(b_object,b)
        || !edge_distance_values(center,axis,a,b,radius,half_width,crown,&distance,normal,witness)) return NULL;
    return Py_BuildValue("(d(ddd)(ddd))",distance,normal[0],normal[1],normal[2],witness[0],witness[1],witness[2]);
}

#include "wheel_convex_distance.h"

/* 六个原裁剪平面和64次保守推进留在同一数值调用中。 */
static int triangle_edge_values(double start[3],double end[3],double vertices[3][3],double margin,
    double axis[3],double radius,double width,double shoulder,double crown,PyObject *coordinates,
    double ceiling,double padding[3],SurfaceEntry *entry) {
    entry->found=0;
    WheelConvex shape={0};
    for (int i=0;i<3;++i) shape.axis[i]=axis[i];
    double buffers[2][192][3]; int count=3,current=0;
    for (int i=0;i<3;++i) for (int j=0;j<3;++j) buffers[0][i][j]=vertices[i][j];
    for (int axis=0;axis<3;++axis) for (int side=0;side<2;++side) {
        double sign=side==0 ? 1. : -1.;
        double bound=side==0 ? (end[axis]<start[axis] ? end[axis] : start[axis])-padding[axis]
                            : (end[axis]>start[axis] ? end[axis] : start[axis])+padding[axis];
        int written=0,next=1-current;
        for (int i=0;i<count;++i) {
            double *a=buffers[current][i],*b=buffers[current][(i+1)%count];
            double da=sign*(a[axis]-bound),db=sign*(b[axis]-bound);
            if (da>=0.) {
                for (int j=0;j<3;++j) buffers[next][written][j]=a[j];
                ++written;
            }
            if ((da>=0.)!=(db>=0.)) {
                double fraction=da/(da-db);
                for (int j=0;j<3;++j) buffers[next][written][j]=j==axis ? bound : fma(fraction,b[j]-a[j],a[j]);
                ++written;
            }
        }
        count=written; current=next;
        if (!count) return 1;
    }
    shape.polygon=buffers[current]; shape.count=count; shape.coordinates=coordinates;
    shape.radius=radius-shoulder; shape.half=width/2-shoulder; shape.crown=crown;
    double fraction=0.,velocity[3]; subtract(end,start,velocity);
    for (int iteration=0;iteration<64;++iteration) {
        for (int i=0;i<3;++i) shape.center[i]=start[i]+fraction*velocity[i];
        double distance,normal[3],witness[3];
        if (!wheel_convex_values(&shape,&distance,normal,witness)) return 0;
        double gap=distance-margin-shoulder;
        if (fraction==0. && gap<-1e-9) return 1;
        if (gap<=1e-9) {
            for (int i=0;i<3;++i) witness[i]+=margin*normal[i];
            entry->found=1; entry->face=0; entry->fraction=fraction;
            for (int i=0;i<3;++i) { entry->normal[i]=normal[i]; entry->point[i]=witness[i]; }
            return 1;
        }
        double closing=-dot(normal,velocity);
        if (closing<=0.) return 1;
        fraction+=gap/closing;
        if (fraction>ceiling) return 1;
    }
    PyErr_SetString(PyExc_ArithmeticError,"圆柱/三角形悬架扫掠未收敛"); return 0;
}

static PyObject *triangle_edge_entry(PyObject *self,PyObject *args) {
    PyObject *start_object,*end_object,*triangle,*axis_object,*coordinates,*padding_object;
    double start[3],end[3],axis[3],padding[3],vertices[3][3],margin,radius,width,shoulder,crown,ceiling;
    if (!PyArg_ParseTuple(args,"OOOdOddddOdO",&start_object,&end_object,&triangle,&margin,
        &axis_object,&radius,&width,&shoulder,&crown,&coordinates,&ceiling,&padding_object)) return NULL;
    if (!vector(start_object,start) || !vector(end_object,end) || !vector(axis_object,axis)
        || !vector(padding_object,padding)) return NULL;
    PyObject *items=PySequence_Fast(triangle,"三角面须为三个顶点");
    if (!items) return NULL;
    if (PySequence_Fast_GET_SIZE(items)!=3) {
        Py_DECREF(items); PyErr_SetString(PyExc_ValueError,"三角面须为三个顶点"); return NULL;
    }
    for (int i=0;i<3;++i) if (!vector(PySequence_Fast_GET_ITEM(items,i),vertices[i])) { Py_DECREF(items); return NULL; }
    Py_DECREF(items);
    SurfaceEntry entry={0};
    if (!triangle_edge_values(start,end,vertices,margin,axis,radius,width,shoulder,crown,coordinates,ceiling,padding,&entry)) return NULL;
    return surface_entry_object(&entry);
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
/* 原三角网格的数值副本只随网格构造；源三角面对象供边角和面引用继续使用。 */
typedef struct {
    double vertices[3][3], center[3], half[3], normal[3];
    PyObject *source;
} PreparedTriangle;
typedef struct TrianglePacket {
    double center[3], half[3];
    Py_ssize_t triangle_count, child_count, total;
    PreparedTriangle *triangles;
    struct TrianglePacket **children;
    PyObject *triangle_owners, *child_owners;
} TrianglePacket;
static const char *triangle_packet_name = "coastaldrive.triangle_support";

static void triangle_packet_free(TrianglePacket *packet) {
    Py_XDECREF(packet->triangle_owners);
    Py_XDECREF(packet->child_owners);
    PyMem_Free(packet->triangles);
    PyMem_Free(packet->children);
    PyMem_Free(packet);
}
static void release_triangle_packet(PyObject *capsule) {
    TrianglePacket *packet = PyCapsule_GetPointer(capsule, triangle_packet_name);
    if (packet) triangle_packet_free(packet);
}
static PyObject *triangle_support_coefficients(PyObject *self, PyObject *args) {
    PyObject *center, *half, *triangles, *bounds, *children;
    if (!PyArg_ParseTuple(args, "OOOOO", &center, &half, &triangles, &bounds, &children)) return NULL;
    TrianglePacket *packet = PyMem_Calloc(1, sizeof(TrianglePacket));
    if (!packet) return PyErr_NoMemory();
    if (!vector(center, packet->center) || !vector(half, packet->half)) goto failed;
    packet->triangle_count = PyTuple_Size(triangles);
    packet->child_count = PyTuple_Size(children);
    if (packet->triangle_count < 0 || packet->child_count < 0) goto failed;
    if (PyTuple_Size(bounds) != packet->triangle_count) {
        PyErr_SetString(PyExc_ValueError, "原三角面与边界数目不一致"); goto failed;
    }
    packet->triangles = PyMem_Calloc(packet->triangle_count, sizeof(PreparedTriangle));
    packet->children = PyMem_Calloc(packet->child_count, sizeof(TrianglePacket *));
    if ((packet->triangle_count && !packet->triangles) || (packet->child_count && !packet->children)) {
        PyErr_NoMemory(); goto failed;
    }
    packet->total = packet->triangle_count;
    for (Py_ssize_t i = 0; i < packet->triangle_count; ++i) {
        PreparedTriangle *triangle = &packet->triangles[i];
        triangle->source = PyTuple_GET_ITEM(triangles, i);
        PyObject *bound = PyTuple_GET_ITEM(bounds, i);
        if (PyTuple_Size(triangle->source) != 3 || PyTuple_Size(bound) != 2) {
            PyErr_SetString(PyExc_ValueError, "原三角面顶点或边界结构不一致"); goto failed;
        }
        for (int a = 0; a < 3; ++a)
            if (!vector(PyTuple_GET_ITEM(triangle->source, a), triangle->vertices[a])) goto failed;
        double ab[3],ac[3];
        subtract(triangle->vertices[1],triangle->vertices[0],ab);
        subtract(triangle->vertices[2],triangle->vertices[0],ac);
        cross(ab,ac,triangle->normal);
        double length=sqrt(dot(triangle->normal,triangle->normal));
        if (length!=0.) for (int a=0;a<3;++a) triangle->normal[a]/=length;
        if (!vector(PyTuple_GET_ITEM(bound, 0), triangle->center)
            || !vector(PyTuple_GET_ITEM(bound, 1), triangle->half)) goto failed;
    }
    for (Py_ssize_t i = 0; i < packet->child_count; ++i) {
        packet->children[i] = PyCapsule_GetPointer(PyTuple_GET_ITEM(children, i), triangle_packet_name);
        if (!packet->children[i]) goto failed;
        packet->total += packet->children[i]->total;
    }
    packet->triangle_owners = Py_NewRef(triangles);
    packet->child_owners = Py_NewRef(children);
    PyObject *result = PyCapsule_New(packet, triangle_packet_name, release_triangle_packet);
    if (!result) goto failed;
    return result;
failed:
    triangle_packet_free(packet); return NULL;
}
static int triangle_packet_possible(const double center[3], const double base_half[3],
                                    double start[3], double end[3], double padding[3]) {
    double half[3], local_start[3], local_end[3], entry, exit_time, sign;
    int axis;
    for (int i = 0; i < 3; ++i) {
        half[i] = base_half[i] + padding[i];
        local_start[i] = start[i] - center[i];
        local_end[i] = end[i] - center[i];
    }
    return box_interval_values(local_start, local_end, half, &entry, &exit_time, &axis, &sign)
        && !(entry > 1. || exit_time < 0.);
}
static void triangle_packet_collect(TrianglePacket *packet, double start[3], double end[3], double padding[3],
                                    PreparedTriangle **result, Py_ssize_t *count) {
    if (!triangle_packet_possible(packet->center, packet->half, start, end, padding)) return;
    for (Py_ssize_t i = 0; i < packet->child_count; ++i)
        triangle_packet_collect(packet->children[i], start, end, padding, result, count);
    for (Py_ssize_t i = 0; i < packet->triangle_count; ++i) {
        PreparedTriangle *triangle = &packet->triangles[i];
        if (triangle_packet_possible(triangle->center, triangle->half, start, end, padding))
            result[(*count)++] = triangle;
    }
}

/* 候选窗口一次筛选并复用原顶点/法线/边界；不重新计算同一不可变三角面。 */
static PyObject *triangle_support_window(PyObject *self,PyObject *args) {
    PyObject *coefficients,*start_object,*end_object,*padding_object;
    if (!PyArg_ParseTuple(args,"OOOO",&coefficients,&start_object,&end_object,&padding_object)) return NULL;
    TrianglePacket *source=PyCapsule_GetPointer(coefficients,triangle_packet_name);
    if (!source) return NULL;
    double start[3],end[3],padding[3];
    if (!vector(start_object,start) || !vector(end_object,end) || !vector(padding_object,padding)) return NULL;
    PreparedTriangle **selected=PyMem_Malloc((source->total ? source->total : 1)*sizeof(*selected));
    if (!selected) return PyErr_NoMemory();
    Py_ssize_t count=0;
    triangle_packet_collect(source,start,end,padding,selected,&count);
    TrianglePacket *packet=PyMem_Calloc(1,sizeof(TrianglePacket));
    if (!packet) { PyMem_Free(selected); return PyErr_NoMemory(); }
    memcpy(packet->center,source->center,sizeof(packet->center));
    memcpy(packet->half,source->half,sizeof(packet->half));
    packet->triangle_count=packet->total=count;
    packet->triangles=PyMem_Calloc(count ? count : 1,sizeof(PreparedTriangle));
    packet->triangle_owners=PyTuple_New(count);
    PyObject *bounds=PyTuple_New(count);
    if (!packet->triangles || !packet->triangle_owners || !bounds) {
        PyMem_Free(selected); Py_XDECREF(bounds); triangle_packet_free(packet); return PyErr_NoMemory();
    }
    for (Py_ssize_t i=0;i<count;++i) {
        packet->triangles[i]=*selected[i];
        PyTuple_SET_ITEM(packet->triangle_owners,i,Py_NewRef(selected[i]->source));
        double *center=selected[i]->center,*half=selected[i]->half;
        PyObject *bound=Py_BuildValue("((ddd)(ddd))",center[0],center[1],center[2],half[0],half[1],half[2]);
        if (!bound) { PyMem_Free(selected); Py_DECREF(bounds); triangle_packet_free(packet); return NULL; }
        PyTuple_SET_ITEM(bounds,i,bound);
    }
    PyMem_Free(selected);
    PyObject *capsule=PyCapsule_New(packet,triangle_packet_name,release_triangle_packet);
    if (!capsule) { Py_DECREF(bounds); triangle_packet_free(packet); return NULL; }
    PyObject *result=PyTuple_Pack(3,packet->triangle_owners,bounds,capsule);
    Py_DECREF(bounds); Py_DECREF(capsule); return result;
}

static int triangle_query_best(PyObject *hit,PyObject **best,double *ceiling) {
    double fraction=PyFloat_AsDouble(PyTuple_GetItem(hit,0));
    if (PyErr_Occurred()) return 0;
    if (!*best || fraction<*ceiling) {
        Py_XSETREF(*best,Py_NewRef(hit)); *ceiling=fraction;
    }
    return 1;
}

/* 完整网格求交只保留原生候选和末接点；中间面/边不再装配Python对象。 */
static int triangle_query_values(TrianglePacket *packet,double start[3],double end[3],double padding[3],
    double margin,double axis[3],double radius,double width,double shoulder,double crown,PyObject *coordinates,
    SurfaceEntry *result) {
    PreparedTriangle *small_candidates[32]; double small_bounds[32];
    PreparedTriangle **candidates=packet->total<=32 ? small_candidates : PyMem_Malloc(packet->total*sizeof(*candidates));
    double *bounds=packet->total<=32 ? small_bounds : PyMem_Malloc(packet->total*sizeof(*bounds));
    if (!candidates || !bounds) {
        if (packet->total>32) { PyMem_Free(candidates); PyMem_Free(bounds); }
        PyErr_NoMemory(); return 0;
    }
    Py_ssize_t count=0;
    triangle_packet_collect(packet,start,end,padding,candidates,&count);
    SurfaceEntry best={0}; FaceSupport support_cache={0}; double ceiling=1.;
    for (Py_ssize_t k=0;k<count;++k) {
        PreparedTriangle *prepared=candidates[k]; SurfaceEntry hit={0}; int finished;
        if (!triangle_face_result(start,end,prepared->vertices,margin,axis,radius,width,shoulder,crown,
            1,1.,&bounds[k],prepared->normal,&support_cache,&hit,&finished)) goto failed;
        if (hit.found) {
            bounds[k]=NAN;
            if (!best.found || hit.fraction<ceiling) { best=hit; ceiling=hit.fraction; }
        }
    }
    for (Py_ssize_t k=0;k<count;++k) {
        if (isnan(bounds[k]) || bounds[k]>=ceiling) continue;
        SurfaceEntry hit={0};
        if (!triangle_edge_values(start,end,candidates[k]->vertices,margin,axis,radius,width,shoulder,crown,
            coordinates,ceiling,padding,&hit)) goto failed;
        if (hit.found && (!best.found || hit.fraction<ceiling)) { best=hit; ceiling=hit.fraction; }
    }
    if (packet->total>32) { PyMem_Free(candidates); PyMem_Free(bounds); }
    *result=best; return 1;
failed:
    if (packet->total>32) { PyMem_Free(candidates); PyMem_Free(bounds); }
    return 0;
}

static PyObject *triangle_support_entry(PyObject *self,PyObject *args,PyObject *kwargs) {
    PyObject *node,*start_object,*end_object,*margin_object,*axis_object,*radius_object,*width_object,*shoulder_object,*crown_object,*edge_entry;
    PyObject *coordinates=Py_None;
    static char *names[]={"node","start","end","margin","axis","radius","width","shoulder","crown","edge_entry","coordinates",NULL};
    if (!PyArg_ParseTupleAndKeywords(args,kwargs,"OOOOOOOOOO|O",names,&node,&start_object,&end_object,&margin_object,
        &axis_object,&radius_object,&width_object,&shoulder_object,&crown_object,&edge_entry,&coordinates)) return NULL;
    double start[3],end[3],axis[3],padding[3],margin=PyFloat_AsDouble(margin_object),radius=PyFloat_AsDouble(radius_object);
    double width=PyFloat_AsDouble(width_object),shoulder=PyFloat_AsDouble(shoulder_object),crown=PyFloat_AsDouble(crown_object);
    if (PyErr_Occurred() || !vector(start_object,start) || !vector(end_object,end) || !vector(axis_object,axis)) return NULL;
    for (int i=0; i<3; ++i) {
        double direction[3]={0.},support[3]; direction[i]=1.;
        if (!support_values(direction,axis,radius,width/2,shoulder,crown,support)) return NULL;
        padding[i]=support[i]+margin;
    }
    TrianglePacket *packet=PyCapsule_GetPointer(node,triangle_packet_name);
    if (!packet) return NULL;
    if (coordinates!=Py_None) {
        SurfaceEntry result={0};
        if (!triangle_query_values(packet,start,end,padding,margin,axis,radius,width,shoulder,crown,coordinates,&result)) return NULL;
        return surface_entry_object(&result);
    }
    PreparedTriangle **candidates=PyMem_Malloc(packet->total*sizeof(PreparedTriangle *));
    if (packet->total && !candidates) return PyErr_NoMemory();
    Py_ssize_t count=0;
    triangle_packet_collect(packet,start,end,padding,candidates,&count);
    PyObject *curved=PyList_New(0),*best=NULL,*keywords=NULL;
    double ceiling=1.;
    if (!curved) goto error;
    FaceSupport support_cache={0};
    for (Py_ssize_t k=0; k<count; ++k) {
        PreparedTriangle *prepared=candidates[k];
        PyObject *triangle=prepared->source;
        double (*vertices)[3]=prepared->vertices;
        double fraction_bound;
        PyObject *result=triangle_face_values(start,end,vertices,margin,axis,radius,width,shoulder,crown,
            1,1.,&fraction_bound,prepared->normal,&support_cache);
        if (!result) goto error;
        PyObject *hit=PyTuple_GET_ITEM(result,1);
        int kept;
        if (hit!=Py_None) kept=triangle_query_best(hit,&best,&ceiling);
        else {
            PyObject *pending=Py_BuildValue("(Od)",triangle,fraction_bound);
            if (!pending) { Py_DECREF(result); goto error; }
            kept=PyList_Append(curved,pending)>=0;
            Py_DECREF(pending);
        }
        Py_DECREF(result);
        if (!kept) goto error;
    }
    keywords=PyDict_New();
    if (!keywords) goto error;
    /* 同一查询的轮胎外廓固定；边角裁剪复用首次求交的原三轴padding。 */
    PyObject *padding_object=Py_BuildValue("(ddd)",padding[0],padding[1],padding[2]);
    if (!padding_object) goto error;
    int padding_set=PyDict_SetItemString(keywords,"padding",padding_object);
    Py_DECREF(padding_object);
    if (padding_set<0) goto error;
    if (PyDict_SetItemString(keywords,"face_checked",Py_True)<0) goto error;
    for (Py_ssize_t k=0; k<PyList_GET_SIZE(curved); ++k) {
        PyObject *pending=PyList_GET_ITEM(curved,k);
        double fraction_bound=PyFloat_AsDouble(PyTuple_GET_ITEM(pending,1));
        if (PyErr_Occurred()) goto error;
        /* 原第二次面查询也在fraction>=ceiling时返回None；复用首次精确计算。 */
        if (fraction_bound>=ceiling) continue;
        PyObject *arguments=PyTuple_Pack(9,start_object,end_object,PyTuple_GET_ITEM(pending,0),margin_object,axis_object,
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
    PyMem_Free(candidates); Py_DECREF(curved); Py_DECREF(keywords);
    return best ? best : Py_NewRef(Py_None);
error:
    PyMem_Free(candidates); Py_XDECREF(curved); Py_XDECREF(best); Py_XDECREF(keywords);
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

/* 查询入口与公开CylinderSurface共用纯几何；只为命中创建支持面对象。 */
static PyObject *cylinder_surface_values(PyObject *start_object, PyObject *end_object, PyObject *axis_object,
    double axes[3][3], double offset[3], PyObject *half, PyObject *plane, PyObject *triangles,
    double margin, double radius, double width, double shoulder, double crown,
    PyObject *edge_entry, PyObject *box_entry, PyObject *coordinates) {
    double axis[3], local_axis[3], zero[3] = {0.};
    if (!vector(axis_object, axis)) return NULL;
    transform_values(axis, axes, zero, 0, local_axis);
    PyObject *local_axis_object = Py_BuildValue("(ddd)", local_axis[0], local_axis[1], local_axis[2]);
    if (!local_axis_object) return NULL;
    PyObject *found = NULL;
    if (triangles != Py_None) {
        PyObject *packet = PyObject_GetAttrString(triangles, "_native");
        if (!packet) { Py_DECREF(local_axis_object); return NULL; }
        PyObject *arguments = Py_BuildValue("(OOOdOddddOO)", packet, start_object, end_object, margin,
            local_axis_object, radius, width, shoulder, crown, edge_entry, coordinates);
        Py_DECREF(packet);
        if (arguments) { found = triangle_support_entry(NULL, arguments, NULL); Py_DECREF(arguments); }
    } else if (plane == Py_None) {
        PyObject *arguments = Py_BuildValue("(OOOdOdddd)", start_object, end_object, half, margin,
            local_axis_object, radius, width / 2, shoulder, crown);
        if (arguments) { found = PyObject_CallObject(box_entry, arguments); Py_DECREF(arguments); }
    } else {
        double start[3], end[3], normal[3], extent[3], terms[3], point[3], anchor[3];
        PyObject *normal_object = PyTuple_GET_ITEM(plane, 0);
        double constant = PyFloat_AsDouble(PyTuple_GET_ITEM(plane, 1));
        if (PyErr_Occurred() || !vector(start_object, start) || !vector(end_object, end)
            || !vector(normal_object, normal) || !support_values(normal, local_axis, radius, width / 2, shoulder, crown, extent)) {
            Py_DECREF(local_axis_object); return NULL;
        }
        for (int a = 0; a < 3; ++a) terms[a] = normal[a] * (start[a] - extent[a]);
        double distance = sum_three(terms) - constant;
        for (int a = 0; a < 3; ++a) terms[a] = normal[a] * (end[a] - start[a]);
        double speed = sum_three(terms);
        if (speed >= 0. || distance < 0. || distance + speed > 0.) found = Py_NewRef(Py_None);
        else {
            double fraction = -distance / speed;
            for (int a = 0; a < 3; ++a) terms[a] = normal[a] * normal[a];
            double squared = sum_three(terms);
            for (int a = 0; a < 3; ++a) {
                point[a] = start[a] + fraction * (end[a] - start[a]) - extent[a];
                anchor[a] = constant * normal[a] / squared;
            }
            found = Py_BuildValue("(dO(ddd)((ddd)d))", fraction, normal_object, point[0], point[1], point[2],
                anchor[0], anchor[1], anchor[2], 0.);
        }
    }
    Py_DECREF(local_axis_object);
    if (!found || found == Py_None) return found;
    PyObject *face = PyTuple_GET_ITEM(found, 3);
    if (face == Py_None) return found;
    double anchor[3], world_anchor[3];
    if (!vector(PyTuple_GET_ITEM(face, 0), anchor)) { Py_DECREF(found); return NULL; }
    for (int a = 0; a < 3; ++a) anchor[a] = anchor[a] - offset[a];
    transform_values(anchor, axes, zero, 1, world_anchor);
    PyObject *world_face = Py_BuildValue("((ddd)O)", world_anchor[0], world_anchor[1], world_anchor[2], PyTuple_GET_ITEM(face, 1));
    if (!world_face) { Py_DECREF(found); return NULL; }
    PyObject *result = PyTuple_Pack(4, PyTuple_GET_ITEM(found, 0), PyTuple_GET_ITEM(found, 1), PyTuple_GET_ITEM(found, 2), world_face);
    Py_DECREF(world_face); Py_DECREF(found);
    return result;
}
static PyObject *cylinder_surface_entry(PyObject *self, PyObject *args) {
    PyObject *start, *end, *axis, *frame, *offset_object, *half, *plane, *triangles, *edge_entry, *box_entry;
    double margin, radius, width, shoulder, crown, axes[3][3], offset[3];
    if (!PyArg_ParseTuple(args, "OOOOOOOOdddddOO", &start, &end, &axis, &frame, &offset_object,
        &half, &plane, &triangles, &margin, &radius, &width, &shoulder, &crown, &edge_entry, &box_entry)) return NULL;
    for (int a = 0; a < 3; ++a) if (!vector(PyTuple_GET_ITEM(frame, a), axes[a])) return NULL;
    if (!vector(offset_object, offset)) return NULL;
    return cylinder_surface_values(start, end, axis, axes, offset, half, plane, triangles,
        margin, radius, width, shoulder, crown, edge_entry, box_entry, Py_None);
}

/* 保留支持面和接点对象，只合并同一射线的数值变换与有序结果装配。 */
static PyObject *surface_ray_hits(PyObject *self,PyObject *args) {
    PyObject *surfaces,*start_object,*end_object,*axis_object,*origin_object,*surface_class,*contact_class,*edge_entry,*box_entry;
    double radius,reach,width,shoulder,crown;
    int relative,entry_only=0;
    PyObject *coordinates=Py_None;
    if (!PyArg_ParseTuple(args,"OOOOOdddddOOOOp|pO",&surfaces,&start_object,&end_object,&axis_object,&origin_object,
                         &radius,&reach,&width,&shoulder,&crown,&surface_class,&contact_class,&edge_entry,&box_entry,&relative,&entry_only,&coordinates)) return NULL;
    double start[3],end[3],origin[3];
    if (!vector(start_object,start) || !vector(end_object,end) || !vector(origin_object,origin)) return NULL;
    PyObject *hits=entry_only ? Py_NewRef(Py_None) : PyList_New(0);
    double closest=INFINITY;
    if (!hits) return NULL;
    for (Py_ssize_t k=0; k<PyList_GET_SIZE(surfaces); ++k) {
        PyObject *part=PyList_GET_ITEM(surfaces,k),*body=PyTuple_GET_ITEM(part,0);
        PyObject *frame=PyTuple_GET_ITEM(part,2),*half=PyTuple_GET_ITEM(part,3),*margin=PyTuple_GET_ITEM(part,4);
        PyObject *plane=PyTuple_GET_ITEM(part,5),*triangles=PyTuple_GET_ITEM(part,6);
        double axes[3][3],offset[3],local_start[3],local_end[3];
        PyObject *surface=NULL,*found=NULL,*offset_object=NULL,*local_a=NULL,*local_b=NULL,*normal_object=NULL,*point_object=NULL,*hit=NULL;
        for (int a=0; a<3; ++a) {
            if (!vector(PyTuple_GET_ITEM(frame,a),axes[a])) goto failure;
            double translation=PyFloat_AsDouble(PyTuple_GET_ITEM(PyTuple_GET_ITEM(part,7),a));
            if (PyErr_Occurred()) goto failure;
            double terms[3];
            for (int b=0; b<3; ++b) terms[b]=axes[a][b]*origin[b];
            offset[a]=translation+sum_three(terms);
        }
        transform_values(start,axes,offset,0,local_start);
        transform_values(end,axes,offset,0,local_end);
        local_a=Py_BuildValue("(ddd)",local_start[0],local_start[1],local_start[2]);
        local_b=Py_BuildValue("(ddd)",local_end[0],local_end[1],local_end[2]);
        if (!local_a || !local_b) goto failure;
        found=cylinder_surface_values(local_a,local_b,axis_object,axes,offset,half,plane,triangles,
            PyFloat_AsDouble(margin),radius,width,shoulder,crown,edge_entry,box_entry,coordinates);
        if (!found) goto failure;
        if (found!=Py_None) {
            if (!entry_only) {
                offset_object=Py_BuildValue("(ddd)",offset[0],offset[1],offset[2]);
                if (!offset_object) goto failure;
                surface=PyObject_CallFunction(surface_class,"OOOOddddOOdO",half,margin,frame,offset_object,
                                              radius,reach,width,shoulder,axis_object,plane,crown,triangles);
                if (!surface) goto failure;
            }
            double normal[3],point[3],world_normal[3],world_point[3],zero[3]={0.};
            if (!vector(PyTuple_GET_ITEM(found,1),normal) || !vector(PyTuple_GET_ITEM(found,2),point)) goto failure;
            for (int a=0; a<3; ++a) point[a]=point[a]-offset[a];
            transform_values(normal,axes,zero,1,world_normal);
            transform_values(point,axes,zero,1,world_point);
            if (!relative) for (int a=0; a<3; ++a) world_point[a]=world_point[a]+origin[a];
            normal_object=Py_BuildValue("(ddd)",world_normal[0],world_normal[1],world_normal[2]);
            point_object=Py_BuildValue("(ddd)",world_point[0],world_point[1],world_point[2]);
            if (!normal_object || !point_object) goto failure;
            if (entry_only) {
                double fraction=PyFloat_AsDouble(PyTuple_GET_ITEM(found,0));
                if (PyErr_Occurred()) goto failure;
                if (fraction<closest) {
                    hit=PyTuple_Pack(4,PyTuple_GET_ITEM(found,0),normal_object,point_object,PyTuple_GET_ITEM(found,3));
                    if (!hit) goto failure;
                    Py_SETREF(hits,Py_NewRef(hit)); closest=fraction;
                }
            } else {
                hit=PyObject_CallFunctionObjArgs(contact_class,body,PyTuple_GET_ITEM(found,0),point_object,normal_object,
                                                surface,PyTuple_GET_ITEM(found,3),NULL);
                if (!hit || PyList_Append(hits,hit)<0) goto failure;
            }
        }
        Py_XDECREF(hit); Py_XDECREF(point_object); Py_XDECREF(normal_object);
        Py_DECREF(found); Py_DECREF(local_b); Py_DECREF(local_a); Py_XDECREF(surface); Py_XDECREF(offset_object);
        continue;
failure:
        Py_XDECREF(hit); Py_XDECREF(point_object); Py_XDECREF(normal_object);
        Py_XDECREF(found); Py_XDECREF(local_b); Py_XDECREF(local_a); Py_XDECREF(surface); Py_XDECREF(offset_object);
        Py_DECREF(hits); return NULL;
    }
    return hits;
}

typedef struct {
    int kind;
    double axes[3][3],translation[3],half[3],normal[3],constant,margin;
    TrianglePacket *triangles;
} SurfacePart;
typedef struct { PyObject *surfaces; Py_ssize_t count; SurfacePart *parts; } SurfacePacket;
static const char *surface_packet_name="coastaldrive.surface_queries";

static void surface_packet_free(SurfacePacket *packet) {
    Py_XDECREF(packet->surfaces); PyMem_Free(packet->parts); PyMem_Free(packet);
}
static void release_surface_packet(PyObject *capsule) {
    SurfacePacket *packet=PyCapsule_GetPointer(capsule,surface_packet_name);
    if (packet) surface_packet_free(packet);
}
static PyObject *surface_packet_create(PyObject *surfaces) {
    SurfacePacket *packet=PyMem_Calloc(1,sizeof(*packet));
    if (!packet) return PyErr_NoMemory();
    packet->count=PyList_Size(surfaces);
    if (packet->count<0) goto failed;
    packet->parts=PyMem_Calloc(packet->count,sizeof(*packet->parts));
    if (packet->count && !packet->parts) { PyErr_NoMemory(); goto failed; }
    for (Py_ssize_t k=0;k<packet->count;++k) {
        SurfacePart *part=&packet->parts[k]; PyObject *source=PyList_GET_ITEM(surfaces,k);
        PyObject *frame=PyTuple_GET_ITEM(source,2),*plane=PyTuple_GET_ITEM(source,5),*triangles=PyTuple_GET_ITEM(source,6);
        for (int a=0;a<3;++a) if (!vector(PyTuple_GET_ITEM(frame,a),part->axes[a])) goto failed;
        if (!vector(PyTuple_GET_ITEM(source,7),part->translation)) goto failed;
        part->margin=PyFloat_AsDouble(PyTuple_GET_ITEM(source,4));
        if (PyErr_Occurred()) goto failed;
        if (triangles!=Py_None) {
            part->kind=2;
            PyObject *capsule=PyObject_GetAttrString(triangles,"_native");
            if (!capsule) goto failed;
            part->triangles=PyCapsule_GetPointer(capsule,triangle_packet_name); Py_DECREF(capsule);
            if (!part->triangles) goto failed;
        } else if (plane!=Py_None) {
            part->kind=0;
            if (!vector(PyTuple_GET_ITEM(plane,0),part->normal)) goto failed;
            part->constant=PyFloat_AsDouble(PyTuple_GET_ITEM(plane,1));
            if (PyErr_Occurred()) goto failed;
        } else {
            part->kind=1;
            if (!vector(PyTuple_GET_ITEM(source,3),part->half)) goto failed;
        }
    }
    packet->surfaces=Py_NewRef(surfaces);
    PyObject *capsule=PyCapsule_New(packet,surface_packet_name,release_surface_packet);
    if (!capsule) goto failed;
    return capsule;
failed:
    surface_packet_free(packet); return NULL;
}

static int cylinder_box_values(double start[3],double end[3],double half[3],double margin,double axis[3],
    double radius,double half_width,double shoulder,double crown,PyObject *coordinates,SurfaceEntry *hit) {
    hit->found=0;
    double bounds[3],near,far,sign; int normal_axis;
    for (int a=0;a<3;++a) {
        double radial=1.-axis[a]*axis[a];
        double extent=fabs(axis[a])*(half_width-shoulder)+(radius-shoulder)*sqrt(radial>0. ? radial : 0.)+shoulder+margin;
        bounds[a]=half[a]+extent;
    }
    if (!box_interval_values(start,end,bounds,&near,&far,&normal_axis,&sign) || near>1. || far<0.) return 1;
    double velocity[3]; subtract(end,start,velocity);
    for (int a=0;a<3;++a) for (int side=0;side<2;++side) {
        double normal[3]={0.},support[3]; sign=side==0 ? -1. : 1.; normal[a]=sign;
        double speed=sign*velocity[a];
        if (!support_values(normal,axis,radius,half_width,shoulder,crown,support)) return 0;
        double distance=sign*start[a]-half[a]-margin-dot(normal,support);
        if (speed>=0. || distance<0.) continue;
        double fraction=-distance/speed;
        if (!(0.<=fraction && fraction<=1.)) continue;
        double point[3]; int inside=1;
        for (int b=0;b<3;++b) {
            point[b]=start[b]+fraction*velocity[b]-support[b];
            if (b!=a && fabs(point[b])>half[b]) inside=0;
        }
        if (inside) {
            hit->found=hit->face=1; hit->fraction=fraction; hit->margin=margin;
            for (int b=0;b<3;++b) { hit->normal[b]=normal[b]; hit->point[b]=point[b]; hit->anchor[b]=b==a ? sign*half[a] : 0.; }
            return 1;
        }
    }
    WheelConvex shape={0}; shape.coordinates=coordinates; shape.radius=radius-shoulder; shape.half=half_width-shoulder; shape.crown=crown;
    for (int a=0;a<3;++a) { shape.axis[a]=axis[a]; shape.box[a]=half[a]; }
    double fraction=0.;
    for (int iteration=0;iteration<64;++iteration) {
        for (int a=0;a<3;++a) shape.center[a]=start[a]+fraction*velocity[a];
        double distance,normal[3],witness[3];
        if (!wheel_convex_values(&shape,&distance,normal,witness)) return 0;
        double gap=distance-margin-shoulder;
        if (fraction==0. && gap<-1e-9) return 1;
        if (gap<=1e-9) {
            hit->found=1; hit->face=0; hit->fraction=fraction;
            for (int a=0;a<3;++a) { hit->normal[a]=normal[a]; hit->point[a]=witness[a]+margin*normal[a]; }
            return 1;
        }
        double closing=-dot(normal,velocity);
        if (closing<=0.) return 1;
        fraction+=gap/closing;
        if (fraction>1.) return 1;
    }
    PyErr_SetString(PyExc_ArithmeticError,"圆柱/Box悬架扫掠未收敛"); return 0;
}

static PyObject *cylinder_box_entry_call(PyObject *self,PyObject *args) {
    PyObject *start_object,*end_object,*half_object,*axis_object,*coordinates;
    double start[3],end[3],half[3],axis[3],margin,radius,half_width,shoulder,crown;
    if (!PyArg_ParseTuple(args,"OOOdOddddO",&start_object,&end_object,&half_object,&margin,&axis_object,
                         &radius,&half_width,&shoulder,&crown,&coordinates)) return NULL;
    if (!vector(start_object,start) || !vector(end_object,end) || !vector(half_object,half) || !vector(axis_object,axis)) return NULL;
    SurfaceEntry hit={0};
    if (!cylinder_box_values(start,end,half,margin,axis,radius,half_width,shoulder,crown,coordinates,&hit)) return NULL;
    return surface_entry_object(&hit);
}

/* 同一不可变候选表只解包一次；查询保留真实平移、轮轴和原候选次序。 */
static PyObject *surface_packet_entry(SurfacePacket *packet,double start[3],double end[3],double axis[3],double origin[3],
    double radius,double width,double shoulder,double crown,PyObject *coordinates) {
    SurfaceEntry best={0}; double ceiling=INFINITY,zero[3]={0.};
    for (Py_ssize_t k=0;k<packet->count;++k) {
        SurfacePart *part=&packet->parts[k]; SurfaceEntry hit={0};
        double offset[3],local_start[3],local_end[3],local_axis[3],terms[3];
        for (int a=0;a<3;++a) {
            for (int b=0;b<3;++b) terms[b]=part->axes[a][b]*origin[b];
            offset[a]=part->translation[a]+sum_three(terms);
        }
        transform_values(start,part->axes,offset,0,local_start);
        transform_values(end,part->axes,offset,0,local_end);
        transform_values(axis,part->axes,zero,0,local_axis);
        if (part->kind==2) {
            double padding[3];
            for (int a=0;a<3;++a) {
                double direction[3]={0.},support[3]; direction[a]=1.;
                if (!support_values(direction,local_axis,radius,width/2,shoulder,crown,support)) return NULL;
                padding[a]=support[a]+part->margin;
            }
            if (!triangle_query_values(part->triangles,local_start,local_end,padding,part->margin,local_axis,
                radius,width,shoulder,crown,coordinates,&hit)) return NULL;
        } else if (part->kind==0) {
            double extent[3];
            if (!support_values(part->normal,local_axis,radius,width/2,shoulder,crown,extent)) return NULL;
            for (int a=0;a<3;++a) terms[a]=part->normal[a]*(local_start[a]-extent[a]);
            double distance=sum_three(terms)-part->constant;
            for (int a=0;a<3;++a) terms[a]=part->normal[a]*(local_end[a]-local_start[a]);
            double speed=sum_three(terms);
            if (speed<0. && distance>=0. && distance+speed<=0.) {
                hit.found=hit.face=1; hit.fraction=-distance/speed; hit.margin=0.;
                for (int a=0;a<3;++a) terms[a]=part->normal[a]*part->normal[a];
                double squared=sum_three(terms);
                for (int a=0;a<3;++a) {
                    hit.normal[a]=part->normal[a];
                    hit.point[a]=local_start[a]+hit.fraction*(local_end[a]-local_start[a])-extent[a];
                    hit.anchor[a]=part->constant*part->normal[a]/squared;
                }
            }
        } else {
            if (!cylinder_box_values(local_start,local_end,part->half,part->margin,local_axis,
                radius,width/2,shoulder,crown,coordinates,&hit)) return NULL;
        }
        if (!hit.found || hit.fraction>=ceiling) continue;
        SurfaceEntry world=hit; double translated[3];
        transform_values(hit.normal,part->axes,zero,1,world.normal);
        for (int a=0;a<3;++a) translated[a]=hit.point[a]-offset[a];
        transform_values(translated,part->axes,zero,1,world.point);
        if (hit.face) {
            for (int a=0;a<3;++a) translated[a]=hit.anchor[a]-offset[a];
            transform_values(translated,part->axes,zero,1,world.anchor);
        }
        best=world; ceiling=hit.fraction;
    }
    return surface_entry_object(&best);
}

/* 冻结子步中覆盖盒内的静态查询，复用原求交，只省去Python射线/对象装配。 */
static PyObject *cached_surface_entry(PyObject *self,PyObject *args) {
    PyObject *cache,*start_object,*end_object,*axis_object,*origin_object,*edge_entry,*box_entry,*coordinates=Py_None;
    double radius,width,shoulder,crown;
    if (!PyArg_ParseTuple(args,"OOOOOddddOO|O",&cache,&start_object,&end_object,&axis_object,&origin_object,
                         &radius,&width,&shoulder,&crown,&edge_entry,&box_entry,&coordinates)) return NULL;
    if (!PyDict_Check(cache)) { PyErr_SetString(PyExc_TypeError,"支持候选缓存须为字典"); return NULL; }
    if (!PyDict_Size(cache)) return Py_BuildValue("(OO)",Py_False,Py_None);
    PyObject *native=PyDict_GetItemString(cache,"native_needed");
    if (!native || !PyDict_GetItemString(cache,"low") || !PyDict_GetItemString(cache,"high")
        || !PyDict_GetItemString(cache,"surfaces")) {
        PyErr_SetString(PyExc_ValueError,"支持候选缓存缺少覆盖盒或表面"); return NULL;
    }
    if (native==Py_True) return Py_BuildValue("(OO)",Py_False,Py_None);
    double start[3],end[3],origin[3],low[3],high[3],padding=radius+width/2+1e-5;
    if (!vector(start_object,start) || !vector(end_object,end) || !vector(origin_object,origin)
        || !vector(PyDict_GetItemString(cache,"low"),low) || !vector(PyDict_GetItemString(cache,"high"),high)) return NULL;
    for (int i=0;i<3;++i) {
        double a=start[i]+origin[i],b=end[i]+origin[i];
        double left=(a<b ? a : b)-padding,right=(a>b ? a : b)+padding;
        if (left<low[i] || right>high[i]) return Py_BuildValue("(OO)",Py_False,Py_None);
    }
    if (coordinates!=Py_None) {
        PyObject *surfaces=PyDict_GetItemString(cache,"surfaces"),*capsule=PyDict_GetItemString(cache,"numeric_surfaces");
        SurfacePacket *packet=capsule ? PyCapsule_GetPointer(capsule,surface_packet_name) : NULL;
        if (capsule && !packet) return NULL;
        if (!packet || packet->surfaces!=surfaces) {
            capsule=surface_packet_create(surfaces);
            if (!capsule) return NULL;
            packet=PyCapsule_GetPointer(capsule,surface_packet_name);
            int saved=PyDict_SetItemString(cache,"numeric_surfaces",capsule); Py_DECREF(capsule);
            if (saved<0) return NULL;
        }
        double axis[3];
        if (!vector(axis_object,axis)) return NULL;
        PyObject *hit=surface_packet_entry(packet,start,end,axis,origin,radius,width,shoulder,crown,coordinates);
        if (!hit) return NULL;
        return Py_BuildValue("(ON)",Py_True,hit);
    }
    PyObject *arguments=Py_BuildValue("(OOOOOdddddOOOOiiO)",PyDict_GetItemString(cache,"surfaces"),
        start_object,end_object,axis_object,origin_object,radius,0.,width,shoulder,crown,
        Py_None,Py_None,edge_entry,box_entry,1,1,coordinates);
    if (!arguments) return NULL;
    PyObject *hit=surface_ray_hits(NULL,arguments); Py_DECREF(arguments);
    if (!hit) return NULL;
    PyObject *result=PyTuple_Pack(2,Py_True,hit); Py_DECREF(hit); return result;
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


static int unit_values(double value[3]) {
    double length=sqrt(dot(value,value));
    if (length==0.) { PyErr_SetString(PyExc_ZeroDivisionError,"轮轴或接触基向量不能为零"); return 0; }
    for (int a=0;a<3;++a) value[a]/=length;
    return 1;
}
static int mechanical_axis_values(const double right[3],const double forward[3],double angle,double axis[3]) {
    double theta=angle*0.017453292519943295,cosine=cos(theta),sine=sin(theta);
    for (int a=0;a<3;++a) axis[a]=cosine*right[a]-sine*forward[a];
    return unit_values(axis);
}

/* 四轮机械轴、胎冠基、逆惯量响应和转向反力共享一次数值装配。 */
static PyObject *rotor_frame_geometry(PyObject *self,PyObject *args) {
    PyObject *right_object,*forward_object,*initial_object,*target_object,*normals_object,*points_object;
    PyObject *tensor_object,*omega_object,*parameters;
    if (!PyArg_ParseTuple(args,"OOOOOOOOO",&right_object,&forward_object,&initial_object,&target_object,
        &normals_object,&points_object,&tensor_object,&omega_object,&parameters)) return NULL;
    double right[3],forward[3],initial[4],target[4],omega[4],tensor[3][3];
    if (!vector(right_object,right) || !vector(forward_object,forward)) return NULL;
    if (PyTuple_Size(initial_object)!=4 || PyTuple_Size(target_object)!=4 || PyTuple_Size(omega_object)!=4
        || PyTuple_Size(parameters)!=9 || PyTuple_Size(normals_object)!=4 || PyTuple_Size(points_object)!=4
        || PyTuple_Size(tensor_object)!=3) {
        PyErr_SetString(PyExc_ValueError,"机械轮端输入须为四轮和三维惯量"); return NULL;
    }
    for (int i=0;i<4;++i) {
        initial[i]=PyFloat_AsDouble(PyTuple_GET_ITEM(initial_object,i));
        target[i]=PyFloat_AsDouble(PyTuple_GET_ITEM(target_object,i));
        omega[i]=PyFloat_AsDouble(PyTuple_GET_ITEM(omega_object,i));
    }
    for (int a=0;a<3;++a) if (!vector(PyTuple_GET_ITEM(tensor_object,a),tensor[a])) return NULL;
    double radius=PyFloat_AsDouble(PyTuple_GET_ITEM(parameters,0)),mass=PyFloat_AsDouble(PyTuple_GET_ITEM(parameters,1));
    double inertia=PyFloat_AsDouble(PyTuple_GET_ITEM(parameters,2)),dt=PyFloat_AsDouble(PyTuple_GET_ITEM(parameters,3));
    double fraction=PyFloat_AsDouble(PyTuple_GET_ITEM(parameters,4)),previous_fraction=PyFloat_AsDouble(PyTuple_GET_ITEM(parameters,5));
    PyObject *width_object=PyTuple_GET_ITEM(parameters,6);
    double width=width_object==Py_None ? 0. : PyFloat_AsDouble(width_object);
    double shoulder=PyFloat_AsDouble(PyTuple_GET_ITEM(parameters,7)),crown=PyFloat_AsDouble(PyTuple_GET_ITEM(parameters,8));
    if (PyErr_Occurred()) return NULL;
    if (mass==0. || dt==0.) { PyErr_SetString(PyExc_ZeroDivisionError,"质量和轮端步长不能为零"); return NULL; }
    PyObject *result=PyTuple_New(4);
    if (!result) return NULL;
    for (int i=0;i<4;++i) {
        double angle=initial[i]+(target[i]-initial[i])*fraction;
        double previous_angle=initial[i]+(target[i]-initial[i])*previous_fraction;
        double axis[3],previous_axis[3],normal[3],point[3],tangent[3],lateral[3],offset[3],moment_x[3],moment_y[3];
        if (!mechanical_axis_values(right,forward,angle,axis) || !mechanical_axis_values(right,forward,previous_angle,previous_axis)
            || !vector(PyTuple_GET_ITEM(normals_object,i),normal) || !vector(PyTuple_GET_ITEM(points_object,i),point)
            || !unit_values(axis) || !unit_values(normal)) goto failed;
        cross_regular(normal,axis,tangent);
        if (!unit_values(tangent)) goto failed;
        cross_regular(tangent,normal,lateral);
        if (width_object!=Py_None) {
            if (!support_values(normal,axis,radius,width/2,shoulder,crown,offset)) goto failed;
            for (int a=0;a<3;++a) offset[a]=-offset[a];
        } else for (int a=0;a<3;++a) offset[a]=-radius*normal[a];
        double radial_cross[3]; cross_regular(offset,tangent,radial_cross);
        double rolling_radius=dot(axis,radial_cross);
        cross_regular(point,tangent,moment_x); cross_regular(point,lateral,moment_y);
        for (int a=0;a<3;++a) moment_x[a]-=rolling_radius*axis[a];
        double responses[3][3],mobility[6],torque[3];
        double *moments[3]={moment_x,moment_y,axis};
        for (int j=0;j<3;++j) for (int a=0;a<3;++a) responses[j][a]=dot(tensor[a],moments[j]);
        mobility[0]=1/mass+dot(moment_x,responses[0]); mobility[1]=dot(moment_x,responses[1]);
        mobility[2]=dot(moment_x,responses[2]); mobility[3]=1/mass+dot(moment_y,responses[1]);
        mobility[4]=dot(moment_y,responses[2]); mobility[5]=dot(axis,responses[2]);
        for (int a=0;a<3;++a) torque[a]=inertia*omega[i]*(axis[a]-previous_axis[a])/dt;
        PyObject *row=Py_BuildValue("(d(ddd)((ddd)(ddd)(ddd))d(ddd)(ddd)(ddd)(ddd)(dddddd)(ddd))",
            angle,axis[0],axis[1],axis[2],tangent[0],tangent[1],tangent[2],lateral[0],lateral[1],lateral[2],
            normal[0],normal[1],normal[2],rolling_radius,moment_x[0],moment_x[1],moment_x[2],
            responses[0][0],responses[0][1],responses[0][2],responses[1][0],responses[1][1],responses[1][2],
            responses[2][0],responses[2][1],responses[2][2],mobility[0],mobility[1],mobility[2],mobility[3],mobility[4],mobility[5],
            torque[0],torque[1],torque[2]);
        if (!row) goto failed;
        PyTuple_SET_ITEM(result,i,row);
    }
    return result;
failed:
    Py_DECREF(result); return NULL;
}

/* 完成世界积分后批量采样四轮；保留原机械轴/胎冠/滑移与载荷幂律。 */
static PyObject *wheel_observations(PyObject *self,PyObject *args) {
    PyObject *right_object,*forward_object,*angles,*normals,*points,*velocity_object,*angular_object;
    PyObject *omega_object,*loads,*frictions,*parameters;
    if (!PyArg_ParseTuple(args,"OOOOOOOOOOO",&right_object,&forward_object,&angles,&normals,&points,
        &velocity_object,&angular_object,&omega_object,&loads,&frictions,&parameters)) return NULL;
    if (PyTuple_Size(angles)!=4 || PyTuple_Size(normals)!=4 || PyTuple_Size(points)!=4 ||
        PyTuple_Size(omega_object)!=4 || PyTuple_Size(loads)!=4 || PyTuple_Size(frictions)!=4 ||
        PyTuple_Size(parameters)!=7) {
        PyErr_SetString(PyExc_ValueError,"机械观测须为四轮和七个硬件参数"); return NULL;
    }
    double right[3],forward[3],velocity[3],angular[3];
    if (!vector(right_object,right) || !vector(forward_object,forward) ||
        !vector(velocity_object,velocity) || !vector(angular_object,angular)) return NULL;
    double radius=PyFloat_AsDouble(PyTuple_GET_ITEM(parameters,0));
    PyObject *width_object=PyTuple_GET_ITEM(parameters,1);
    double width=width_object==Py_None ? 0. : PyFloat_AsDouble(width_object);
    double shoulder=PyFloat_AsDouble(PyTuple_GET_ITEM(parameters,2));
    double crown=PyFloat_AsDouble(PyTuple_GET_ITEM(parameters,3));
    double slip_speed=PyFloat_AsDouble(PyTuple_GET_ITEM(parameters,4));
    double mass=PyFloat_AsDouble(PyTuple_GET_ITEM(parameters,5));
    double peak_exponent=PyFloat_AsDouble(PyTuple_GET_ITEM(parameters,6));
    if (PyErr_Occurred()) return NULL;
    PyObject *result=PyTuple_New(4);
    if (!result) return NULL;
    for (int i=0;i<4;++i) {
        double angle=PyFloat_AsDouble(PyTuple_GET_ITEM(angles,i));
        double omega=PyFloat_AsDouble(PyTuple_GET_ITEM(omega_object,i));
        double load=PyFloat_AsDouble(PyTuple_GET_ITEM(loads,i));
        double mu=PyFloat_AsDouble(PyTuple_GET_ITEM(frictions,i));
        double axis[3],normal[3],point[3],tangent[3],lateral[3],offset[3],radial[3],moment[3];
        if (PyErr_Occurred() || !mechanical_axis_values(right,forward,angle,axis) ||
            !vector(PyTuple_GET_ITEM(normals,i),normal) || !vector(PyTuple_GET_ITEM(points,i),point) ||
            !unit_values(axis) || !unit_values(normal)) goto failed;
        cross_regular(normal,axis,tangent);
        if (!unit_values(tangent)) goto failed;
        cross_regular(tangent,normal,lateral);
        if (width_object!=Py_None) {
            if (!support_values(normal,axis,radius,width/2,shoulder,crown,offset)) goto failed;
            for (int a=0;a<3;++a) offset[a]=-offset[a];
        } else for (int a=0;a<3;++a) offset[a]=-radius*normal[a];
        cross_regular(offset,tangent,radial);
        double rolling_radius=dot(axis,radial);
        cross_regular(point,tangent,moment);
        for (int a=0;a<3;++a) moment[a]-=rolling_radius*axis[a];
        double vx=dot(velocity,tangent)+dot(angular,moment);
        double hub_cross[3],lateral_velocity[3];
        cross_regular(angular,point,hub_cross);
        for (int a=0;a<3;++a) lateral_velocity[a]=velocity[a]+hub_cross[a];
        double vy=dot(lateral_velocity,lateral);
        double denominator=fmax(fabs(vx),slip_speed);
        if (denominator==0.) { PyErr_SetString(PyExc_ZeroDivisionError,"滑移速度分母不能为零"); goto failed; }
        double kappa=(rolling_radius*omega-vx)/denominator;
        double alpha=atan2(vy,denominator);
        double relative=omega+dot(angular,axis);
        double grip=0.;
        if (load!=0.) {
            if (load<0. || mass<=0.) { PyErr_SetString(PyExc_ValueError,"轮荷须非负且质量须为正"); goto failed; }
            double ratio=load/(mass*9.81/4);
            grip=mu*load*pow(ratio,peak_exponent-1);
        }
        PyObject *row=Py_BuildValue("((ddd)ddddddd)",axis[0],axis[1],axis[2],rolling_radius,relative,
            vx,vy,kappa,alpha,grip);
        if (!row) goto failed;
        PyTuple_SET_ITEM(result,i,row);
    }
    return result;
failed:
    Py_DECREF(result); return NULL;
}

/* 海岸固定折线的完整有序查询；材料资格和最近投影共用原几何数据。 */
typedef struct {
    Py_ssize_t count;
    double radius_squared;
    double (*segments)[10];
} RoadStrip;
static const char *road_strip_name="coastal.road-strip";
static void release_road_strip(PyObject *capsule) {
    RoadStrip *strip=PyCapsule_GetPointer(capsule,road_strip_name);
    if (strip) { PyMem_Free(strip->segments); PyMem_Free(strip); }
}
static PyObject *road_strip_coefficients(PyObject *self,PyObject *args) {
    PyObject *segments; double radius_squared;
    if (!PyArg_ParseTuple(args,"Od",&segments,&radius_squared)) return NULL;
    Py_ssize_t count=PyTuple_Size(segments);
    if (count<0) return NULL;
    if (!count || !(radius_squared>0.)) { PyErr_SetString(PyExc_ValueError,"道路须含线段和正的宽度平方"); return NULL; }
    RoadStrip *strip=PyMem_Calloc(1,sizeof(RoadStrip));
    if (!strip) return PyErr_NoMemory();
    strip->segments=PyMem_Calloc(count,sizeof(*strip->segments));
    if (!strip->segments) { PyMem_Free(strip); return PyErr_NoMemory(); }
    strip->count=count; strip->radius_squared=radius_squared;
    for (Py_ssize_t i=0;i<count;++i) {
        PyObject *segment=PyTuple_GET_ITEM(segments,i);
        if (PyTuple_Size(segment)!=9) { if (!PyErr_Occurred()) PyErr_SetString(PyExc_ValueError,"道路段须为九项数值"); goto failed; }
        for (int j=0;j<9;++j) strip->segments[i][j]=PyFloat_AsDouble(PyTuple_GET_ITEM(segment,j));
        if (PyErr_Occurred()) goto failed;
        double *s=strip->segments[i];
        s[9]=s[2]*s[2]+s[3]*s[3];
        if (!(s[4]>0. && s[9]>0.)) { PyErr_SetString(PyExc_ValueError,"道路段不能退化"); goto failed; }
    }
    PyObject *capsule=PyCapsule_New(strip,road_strip_name,release_road_strip);
    if (capsule) return capsule;
failed:
    PyMem_Free(strip->segments); PyMem_Free(strip); return NULL;
}
static double road_fraction(double x,double y,const double *s,double denominator) {
    double t=((x-s[0])*s[2]+(y-s[1])*s[3])/denominator;
    /* 保持Python max(0,min(1,t))的次序，包括NaN的既有比较行为。 */
    t=t<1. ? t : 1.;
    return t>0. ? t : 0.;
}
static double road_distance_squared(double x,double y,const double *s,double t) {
    return pow(x-s[0]-t*s[2],2.)+pow(y-s[1]-t*s[3],2.);
}
static PyObject *road_strip_contains(PyObject *self,PyObject *args) {
    PyObject *coefficients; double x,y;
    if (!PyArg_ParseTuple(args,"Odd",&coefficients,&x,&y)) return NULL;
    RoadStrip *strip=PyCapsule_GetPointer(coefficients,road_strip_name);
    if (!strip) return NULL;
    for (Py_ssize_t i=0;i<strip->count;++i) {
        double *s=strip->segments[i];
        if (s[5]<=x && x<=s[6] && s[7]<=y && y<=s[8]) {
            double t=road_fraction(x,y,s,s[4]);
            if (road_distance_squared(x,y,s,t)<=strip->radius_squared) Py_RETURN_TRUE;
        }
    }
    Py_RETURN_FALSE;
}
static PyObject *road_strip_project(PyObject *self,PyObject *args) {
    PyObject *coefficients; double x,y;
    if (!PyArg_ParseTuple(args,"Odd",&coefficients,&x,&y)) return NULL;
    RoadStrip *strip=PyCapsule_GetPointer(coefficients,road_strip_name);
    if (!strip) return NULL;
    Py_ssize_t index=0; double best=INFINITY,fraction=0.;
    for (Py_ssize_t i=0;i<strip->count;++i) {
        double *s=strip->segments[i],t=road_fraction(x,y,s,s[9]);
        double distance=road_distance_squared(x,y,s,t);
        if (distance<best) { best=distance; index=i; fraction=t; }
    }
    return Py_BuildValue("(ndd)",index,fraction,best);
}

static int joint_surface_values(SurfacePacket *packet,double start[3],double end[3],double axis[3],double origin[3],
    double radius,double width,double shoulder,double crown,SurfaceEntry *result) {
    PyObject *coordinates=Py_None;
    SurfaceEntry best={0}; double ceiling=INFINITY,zero[3]={0.};
    for (Py_ssize_t k=0;k<packet->count;++k) {
        SurfacePart *part=&packet->parts[k]; SurfaceEntry hit={0};
        double offset[3],local_start[3],local_end[3],local_axis[3],terms[3];
        for (int a=0;a<3;++a) {
            for (int b=0;b<3;++b) terms[b]=part->axes[a][b]*origin[b];
            offset[a]=part->translation[a]+sum_three(terms);
        }
        transform_values(start,part->axes,offset,0,local_start);
        transform_values(end,part->axes,offset,0,local_end);
        transform_values(axis,part->axes,zero,0,local_axis);
        if (part->kind==2) {
            double padding[3];
            for (int a=0;a<3;++a) {
                double direction[3]={0.},support[3]; direction[a]=1.;
                if (!support_values(direction,local_axis,radius,width/2,shoulder,crown,support)) return 0;
                padding[a]=support[a]+part->margin;
            }
            if (!triangle_query_values(part->triangles,local_start,local_end,padding,part->margin,local_axis,
                radius,width,shoulder,crown,coordinates,&hit)) return 0;
        } else if (part->kind==0) {
            double extent[3];
            if (!support_values(part->normal,local_axis,radius,width/2,shoulder,crown,extent)) return 0;
            for (int a=0;a<3;++a) terms[a]=part->normal[a]*(local_start[a]-extent[a]);
            double distance=sum_three(terms)-part->constant;
            for (int a=0;a<3;++a) terms[a]=part->normal[a]*(local_end[a]-local_start[a]);
            double speed=sum_three(terms);
            if (speed<0. && distance>=0. && distance+speed<=0.) {
                hit.found=hit.face=1; hit.fraction=-distance/speed; hit.margin=0.;
                for (int a=0;a<3;++a) terms[a]=part->normal[a]*part->normal[a];
                double squared=sum_three(terms);
                for (int a=0;a<3;++a) {
                    hit.normal[a]=part->normal[a];
                    hit.point[a]=local_start[a]+hit.fraction*(local_end[a]-local_start[a])-extent[a];
                    hit.anchor[a]=part->constant*part->normal[a]/squared;
                }
            }
        } else {
            if (!cylinder_box_values(local_start,local_end,part->half,part->margin,local_axis,
                radius,width/2,shoulder,crown,coordinates,&hit)) return 0;
        }
        if (!hit.found || hit.fraction>=ceiling) continue;
        SurfaceEntry world=hit; double translated[3];
        transform_values(hit.normal,part->axes,zero,1,world.normal);
        for (int a=0;a<3;++a) translated[a]=hit.point[a]-offset[a];
        transform_values(translated,part->axes,zero,1,world.point);
        if (hit.face) {
            for (int a=0;a<3;++a) translated[a]=hit.anchor[a]-offset[a];
            transform_values(translated,part->axes,zero,1,world.anchor);
        }
        best=world; ceiling=hit.fraction;
    }
    *result=best; return 1;
}


#include "joint_contact_impl.h"

static PyMethodDef methods[] = {
    {"joint_contact_prepare",joint_contact_prepare,METH_VARARGS,"连续共同求解的真实有限接点准备"},
    {"joint_surface_prepare",joint_surface_prepare,METH_VARARGS,"覆盖盒外真实几何的持久原生查询包"},
    {"_joint_coordinates",joint_coordinates_probe,METH_VARARGS,"连续有限几何的小型SVD验证入口"},
    {"road_strip_coefficients", (PyCFunction)road_strip_coefficients, METH_VARARGS, "固定道路原折线系数"},
    {"road_strip_contains", (PyCFunction)road_strip_contains, METH_VARARGS, "原顺序道路材料资格"},
    {"road_strip_project", (PyCFunction)road_strip_project, METH_VARARGS, "完整折线最近投影"},
    {"wheel_observations", (PyCFunction)wheel_observations, METH_VARARGS, "完成Bullet积分后的四轮机械观测"},
    {"cylinder_box_entry", (PyCFunction)cylinder_box_entry_call, METH_VARARGS, "原Box平面见证点与保守推进的完整数值入口"},
    {"rotor_frame_geometry", (PyCFunction)rotor_frame_geometry, METH_VARARGS, "原四轮机械几何和转向反力"},
    {"triangle_edge_entry", (PyCFunction)triangle_edge_entry, METH_VARARGS, "原有限三角面裁剪与保守推进"},
    {"support_coefficients", (PyCFunction)support_coefficients, METH_VARARGS, "静态形状数值分区一次解包"},
    {"prepared_support_candidates", (PyCFunction)prepared_support_candidates, METH_VARARGS, "原静态形状有序覆盖盒筛选"},
    {"cached_surface_entry", (PyCFunction)cached_surface_entry, METH_VARARGS, "同子步覆盖盒内静态求交的原生入口"},
    {"convex_distance", (PyCFunction)convex_distance_call, METH_VARARGS, "有限胎宽原GJK连续数值循环"},
    {"cylinder_surface_entry", (PyCFunction)cylinder_surface_entry, METH_VARARGS, "原圆柱/有限支持面纯几何入口"},
    {"triangle_support_coefficients", (PyCFunction)triangle_support_coefficients, METH_VARARGS, "原有限网格固定顶点与包围盒数值"},
    {"triangle_support_window", (PyCFunction)triangle_support_window, METH_VARARGS, "原顺序候选窗口及不可变三角几何复用"},
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
PyMODINIT_FUNC PyInit_wheel_contact_kernels(void) {
    PyObject *result=PyModule_Create(&module); if(!result)return NULL;
    PyObject *api=PyCapsule_New(&joint_contact_api,JOINT_CONTACT_API_NAME,NULL);
    if(!api || PyModule_AddObject(result,"_joint_contact_api",api)<0){Py_XDECREF(api);Py_DECREF(result);return NULL;}
    return result;
}

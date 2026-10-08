/* 原三角网格的数值副本只随网格构造；源三角面对象供边角和面引用继续使用。 */
typedef struct {
    double vertices[3][3], center[3], half[3];
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

/* 查询入口与公开CylinderSurface共用纯几何；只为命中创建支持面对象。 */
static PyObject *cylinder_surface_values(PyObject *start_object, PyObject *end_object, PyObject *axis_object,
    double axes[3][3], double offset[3], PyObject *half, PyObject *plane, PyObject *triangles,
    double margin, double radius, double width, double shoulder, double crown,
    PyObject *edge_entry, PyObject *box_entry) {
    double axis[3], local_axis[3], zero[3] = {0.};
    if (!vector(axis_object, axis)) return NULL;
    transform_values(axis, axes, zero, 0, local_axis);
    PyObject *local_axis_object = Py_BuildValue("(ddd)", local_axis[0], local_axis[1], local_axis[2]);
    if (!local_axis_object) return NULL;
    PyObject *found = NULL;
    if (triangles != Py_None) {
        PyObject *packet = PyObject_GetAttrString(triangles, "_native");
        if (!packet) { Py_DECREF(local_axis_object); return NULL; }
        PyObject *arguments = Py_BuildValue("(OOOdOddddO)", packet, start_object, end_object, margin,
            local_axis_object, radius, width, shoulder, crown, edge_entry);
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
        margin, radius, width, shoulder, crown, edge_entry, box_entry);
}

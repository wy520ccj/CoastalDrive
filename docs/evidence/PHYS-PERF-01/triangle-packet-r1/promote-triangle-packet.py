from pathlib import Path
root = Path(__file__).resolve().parents[3]
folder = root / 'logs/physics/PHYS-PERF-01'
path = root / 'src/wheel_contact_kernels.c'
source = path.read_text(encoding='utf-8')
start = source.index('static int triangle_query_possible(')
stop = source.index('static int triangle_query_best(', start)
source = source[:start] + (folder / 'triangle-packet-body.c').read_text(encoding='utf-8') + '\n' + source[stop:]
needle = '''    PyObject *candidates=PyList_New(0),*curved=PyList_New(0),*best=NULL,*keywords=NULL;
    double ceiling=1.;
    if (!candidates || !curved || !triangle_query_collect(node,start,end,padding,candidates)) goto error;
    for (Py_ssize_t k=0; k<PyList_GET_SIZE(candidates); ++k) {
        PyObject *triangle=PyList_GET_ITEM(candidates,k);
        double vertices[3][3];
        if (!PyTuple_Check(triangle) || PyTuple_GET_SIZE(triangle)!=3) {
            PyErr_SetString(PyExc_ValueError,"三角面须为三个顶点"); goto error;
        }
        for (int i=0; i<3; ++i) if (!vector(PyTuple_GET_ITEM(triangle,i),vertices[i])) goto error;'''
replacement = '''    TrianglePacket *packet=PyCapsule_GetPointer(node,triangle_packet_name);
    if (!packet) return NULL;
    PreparedTriangle **candidates=PyMem_Malloc(packet->total*sizeof(PreparedTriangle *));
    if (packet->total && !candidates) return PyErr_NoMemory();
    Py_ssize_t count=0;
    triangle_packet_collect(packet,start,end,padding,candidates,&count);
    PyObject *curved=PyList_New(0),*best=NULL,*keywords=NULL;
    double ceiling=1.;
    if (!curved) goto error;
    for (Py_ssize_t k=0; k<count; ++k) {
        PreparedTriangle *prepared=candidates[k];
        PyObject *triangle=prepared->source;
        double (*vertices)[3]=prepared->vertices;'''
assert needle in source
source = source.replace(needle, replacement)
source = source.replace('Py_DECREF(candidates); Py_DECREF(curved); Py_DECREF(keywords);', 'PyMem_Free(candidates); Py_DECREF(curved); Py_DECREF(keywords);')
source = source.replace('Py_XDECREF(candidates); Py_XDECREF(curved); Py_XDECREF(best); Py_XDECREF(keywords);', 'PyMem_Free(candidates); Py_XDECREF(curved); Py_XDECREF(best); Py_XDECREF(keywords);')
source = source.replace('static PyMethodDef methods[] = {', 'static PyMethodDef methods[] = {\n    {"triangle_support_coefficients", (PyCFunction)triangle_support_coefficients, METH_VARARGS, "原有限网格固定顶点与包围盒数值"},')
path.write_text(source, encoding='utf-8')
path = root / 'src/triangle_support.py'
source = path.read_text(encoding='utf-8')
source = source.replace('from wheel_contact_kernels import clipped_triangle, triangle_face, triangle_support_entry', 'from wheel_contact_kernels import clipped_triangle, triangle_face, triangle_support_coefficients, triangle_support_entry')
source = source.replace('        object.__setattr__(self, "triangle_bounds", tuple(bounds))', '''        object.__setattr__(self, "triangle_bounds", tuple(bounds))
        # 原生数值只复用本节点不可变几何；公开三角面和子节点仍为原对象。
        object.__setattr__(self, "_native", triangle_support_coefficients(
            self.center, self.half, self.triangles, self.triangle_bounds, tuple(child._native for child in self.children)))''')
source = source.replace('return triangle_support_entry(self, start, end, margin, axis, radius, width, shoulder, crown, triangle_entry)',
                        'return triangle_support_entry(self._native, start, end, margin, axis, radius, width, shoulder, crown, triangle_entry)')
path.write_text(source, encoding='utf-8')

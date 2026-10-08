from pathlib import Path
root = Path(__file__).resolve().parents[3]
folder = root / 'logs/physics/PHYS-PERF-01'
path = root / 'src/wheel_contact_kernels.c'
source = path.read_text(encoding='utf-8')
marker = '/* 保留支持面和接点对象，只合并同一射线的数值变换与有序结果装配。 */'
source = source.replace(marker, (folder / 'surface-entry-body.c').read_text(encoding='utf-8') + '\n' + marker)
source = source.replace('*surface_class,*contact_class;', '*surface_class,*contact_class,*edge_entry,*box_entry;')
source = source.replace('"OOOOOdddddOOp",&surfaces', '"OOOOOdddddOOOOp",&surfaces')
source = source.replace('&radius,&reach,&width,&shoulder,&crown,&surface_class,&contact_class,&relative)',
                        '&radius,&reach,&width,&shoulder,&crown,&surface_class,&contact_class,&edge_entry,&box_entry,&relative)')
source = source.replace('*body=PyTuple_GET_ITEM(part,0),*inverse=PyTuple_GET_ITEM(part,1);', '*body=PyTuple_GET_ITEM(part,0);')
old = '''            PyObject *cell=PyObject_CallMethod(inverse,"getCell","ii",3,a);
            if (!cell) goto failure;
            double translation=PyFloat_AsDouble(cell); Py_DECREF(cell);
            if (PyErr_Occurred()) goto failure;'''
new = '''            double translation=PyFloat_AsDouble(PyTuple_GET_ITEM(PyTuple_GET_ITEM(part,7),a));
            if (PyErr_Occurred()) goto failure;'''
assert old in source
source = source.replace(old, new)
old = '''        offset_object=Py_BuildValue("(ddd)",offset[0],offset[1],offset[2]);
        if (!offset_object) goto failure;
        surface=PyObject_CallFunction(surface_class,"OOOOddddOOdO",half,margin,frame,offset_object,
                                      radius,reach,width,shoulder,axis_object,plane,crown,triangles);
        if (!surface) goto failure;
'''
assert old in source
source = source.replace(old, '')
source = source.replace('found=PyObject_CallMethod(surface,"entry","OOO",local_a,local_b,axis_object);', '''found=cylinder_surface_values(local_a,local_b,axis_object,axes,offset,half,plane,triangles,
            PyFloat_AsDouble(margin),radius,width,shoulder,crown,edge_entry,box_entry);''')
source = source.replace('''        if (found!=Py_None) {
            double normal[3]''', '''        if (found!=Py_None) {
            offset_object=Py_BuildValue("(ddd)",offset[0],offset[1],offset[2]);
            if (!offset_object) goto failure;
            surface=PyObject_CallFunction(surface_class,"OOOOddddOOdO",half,margin,frame,offset_object,
                                          radius,reach,width,shoulder,axis_object,plane,crown,triangles);
            if (!surface) goto failure;
            double normal[3]''')
source = source.replace('Py_DECREF(surface); Py_DECREF(offset_object);', 'Py_XDECREF(surface); Py_XDECREF(offset_object);')
source = source.replace('static PyMethodDef methods[] = {', 'static PyMethodDef methods[] = {\n    {"cylinder_surface_entry", (PyCFunction)cylinder_surface_entry, METH_VARARGS, "原圆柱/有限支持面纯几何入口"},')
path.write_text(source, encoding='utf-8')
path = root / 'src/suspension_geometry.py'
source = path.read_text(encoding='utf-8')
source = source.replace('from wheel_contact_kernels import box_interval, surface_transform',
                        'from wheel_contact_kernels import box_interval, cylinder_surface_entry, surface_transform')
start = source.index('    def entry(self, start, end, axis):')
stop = source.index('\n\n\n', start)
source = source[:start] + '''    def entry(self, start, end, axis):
        from triangle_support import triangle_entry
        from wheel_envelope import cylinder_box_entry
        return cylinder_surface_entry(start, end, axis, self.axes, self.offset, self.half,
            self.plane, self.triangles, self.radius, self.wheel_radius, self.width,
            self.shoulder, self.crown, triangle_entry, cylinder_box_entry)
''' + source[stop:]
path.write_text(source, encoding='utf-8')
path = root / 'src/suspension_contacts.py'
source = path.read_text(encoding='utf-8')
source = source.replace('from triangle_support import TriangleSupport', 'from triangle_support import TriangleSupport, triangle_entry\nfrom wheel_envelope import cylinder_box_entry')
source = source.replace('CylinderSurface, RayContact, ray_origin is not None)', 'CylinderSurface, RayContact, triangle_entry, cylinder_box_entry, ray_origin is not None)')
source = source.replace('inverse, frame, _translation, half, margin, plane, triangles, _bounds = part',
                        'inverse, frame, translation, half, margin, plane, triangles, _bounds = part')
source = source.replace('surfaces.append((body, inverse, frame, half, margin, plane, triangles))',
                        'surfaces.append((body, inverse, frame, half, margin, plane, triangles, translation))')
path.write_text(source, encoding='utf-8')

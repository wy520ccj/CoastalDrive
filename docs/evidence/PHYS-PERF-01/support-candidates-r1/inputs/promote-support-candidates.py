from pathlib import Path
root=Path.cwd();p=root/'src/wheel_contact_kernels.c';s=p.read_text(encoding='utf-8');block=(root/'logs/physics/PHYS-PERF-01/support-candidates-body.c').read_text(encoding='utf-8');s=s.replace('static int support_values(',block+'\nstatic int support_values(',1);s=s.replace('static PyMethodDef methods[] = {','static PyMethodDef methods[] = {\n    {"support_candidates", (PyCFunction)support_candidates, METH_VARARGS | METH_KEYWORDS, "真实形状边界的原批量覆盖盒筛选"},',1);p.write_text(s,encoding='utf-8')
p=root/'src/suspension_contacts.py';s=p.read_text(encoding='utf-8');s=s.replace('from panda3d.core import BitMask32, Mat4, NodePath, Quat, TransformState, Vec3','from panda3d.core import BitMask32, Mat4, NodePath, Quat, TransformState, Vec3\nfrom wheel_contact_kernels import support_candidates',1)
start=s.index('    center = tuple((a+b)/2 for a,b in zip(low,high))',s.index('def cylinder_candidates('));end=s.index('    return surfaces, exact, native_needed',start)
block='''    surfaces, exact, native_needed = [], set(), False
    for body, supported, parts in support_candidates(static_shapes, low, high):
        if supported:
            for part, local_center, local_half in parts:
                inverse, frame, _translation, half, margin, plane, triangles, _bounds = part
                if triangles is not None:
                    # 只预取覆盖盒内原三角面，保留原索引遍历次序；每条射线仍作原精确筛选。
                    selected = tuple(triangles.candidates(local_center, local_center,
                                                         tuple(value+margin for value in local_half)))
                    triangles = TriangleSupport(triangles.low, triangles.high, selected)
                surfaces.append((body, inverse, frame, half, margin, plane, triangles))
            exact.add(body)
        else:
            native_needed = True
'''
s=s[:start]+block+s[end:];p.write_text(s,encoding='utf-8')

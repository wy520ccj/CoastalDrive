"""提取原支持查询前置数值，候选缓存、实际世界与全部求交保持。"""
from pathlib import Path
root=Path.cwd()
path=root/'src/wheel_contact_kernels.c'
source=path.read_text(encoding='utf-8')
body=(root/'logs/physics/PHYS-PERF-01/cylinder-query-body.c').read_text(encoding='utf-8')
index=source.index('static PyMethodDef methods[]')
source=source[:index]+body+'\n'+source[index:]
source=source.replace('static PyMethodDef methods[] = {','static PyMethodDef methods[] = {\n    {"cylinder_query_frame", (PyCFunction)cylinder_query_frame, METH_VARARGS, "原射线坐标与覆盖盒"},',1)
path.write_text(source,encoding='utf-8')
path=root/'src/suspension_contacts.py'
source=path.read_text(encoding='utf-8').replace('from wheel_contact_kernels import support_candidates, surface_ray_hits','from wheel_contact_kernels import cylinder_query_frame, support_candidates, surface_ray_hits',1)
begin=source.index('    relative_rays = (rays if ray_origin is not None else')
end=source.index('    cached = candidate_cache',begin)
source=source[:begin]+'''    relative_rays, world_rays, low, high = cylinder_query_frame(
        rays, origin, radius, width, ray_origin is not None)
'''+source[end:]
path.write_text(source,encoding='utf-8')

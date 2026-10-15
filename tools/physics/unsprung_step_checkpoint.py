"""保存本机生成的纯数值失败输入，去除世界对象；仅用于可信的内部复现文件。"""

import copy
import pickle
from dataclasses import replace


def numeric_geometry(geometry):
    return replace(geometry,hits=tuple(None if hit is None else replace(hit,node=hit.node.getName())
                                       for hit in geometry.hits))


def save_step(source,path):
    finite = copy.copy(source.finite_contact)
    roads = copy.copy(finite.roads)
    if any(surface.triangles is not None for surface in roads.surfaces):
        raise ValueError("该单步诊断只支持当前实验场Plane/Box/凸壳")
    roads.surfaces = tuple(replace(surface,body=surface.body.getName()) for surface in roads.surfaces)
    finite.roads,finite.on_asphalt = roads,None
    finite.initial,finite.target = numeric_geometry(finite.initial),numeric_geometry(finite.target)
    finite.cache_key,finite.cached = None,None
    finite.query_cache = (None if all(surface.plane is not None for surface in roads.surfaces)
                          else [{} for _ in roads.surfaces])
    value = replace(source,geometry=numeric_geometry(source.geometry),finite_contact=finite)
    path.write_bytes(pickle.dumps(value,protocol=5))


def load_step(path):
    # 文件只能来自本工具保存的可信本机输入，不用于工程参数/用户文件导入。
    value = pickle.loads(path.read_bytes())
    value.finite_contact.on_asphalt = lambda x,y:True
    return value

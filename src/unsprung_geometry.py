"""实际轮心与现有有限胎面查询共同决定径向压缩；不维护轮心积分状态。"""

from dataclasses import dataclass

import numpy as np

from suspension_contacts import cylinder_suspension_rays
from vehicle_contacts import road_support
from wheel_envelope import cylinder_support


@dataclass(frozen=True)
class UnsprungGeometry:
    hits: tuple
    deflection: np.ndarray
    offsets: np.ndarray
    normals: np.ndarray
    tangents: np.ndarray
    laterals: np.ndarray
    normal_offsets: np.ndarray


def read_unsprung_geometry(world, body, centers, up, axes, config, *, static_shapes=None):
    """每子步从同一真实世界读胎面；压缩量是名义接触轮心相对实际轮心的法向距离。"""
    radius = config.wheel_radius
    centers,up,axes = map(np.asarray,(centers,up,axes))
    before,after = radius,radius+config.suspension_travel
    starts,ends = centers+before*up,centers-after*up
    found = cylinder_suspension_rays(world,body,tuple(zip(map(tuple,starts),map(tuple,ends))),tuple(map(tuple,axes)),
        radius,config.wheel_width,config.wheel_shoulder_radius,config.wheel_crown_height,static_shapes=static_shapes)
    hits,delta,offsets,normals,tangents,laterals,normal_offsets = [],[],[],[],[],[],[]
    for center,start,end,axis,hit in zip(centers,starts,ends,axes,found):
        eligible = hit is not None and hit.node.isStatic() and road_support(hit.normal) and np.dot(hit.normal,up)>0.
        if eligible:
            normal = np.asarray(hit.normal)
            unloaded_center = start+hit.fraction*(end-start)
            compression = np.dot(unloaded_center-center,normal)
            offset = np.asarray(hit.point)-center
        else:
            normal,compression,offset = up,-after,-radius*up
        tangent = np.cross(normal,axis)
        tangent /= np.linalg.norm(tangent)
        hits.append(hit if eligible else None)
        delta.append(compression)
        offsets.append(offset)
        normals.append(normal)
        tangents.append(tangent)
        laterals.append(np.cross(tangent,normal))
        # 扫掠见证点属于平移后的未加载包络；法向压缩的梯度用包络支持点。
        # 轮胎绕自身轴旋转不改变包络，不能由扫掠方向的切向偏移产生自旋反力。
        support = np.asarray(cylinder_support(tuple(-normal),tuple(axis),radius,config.wheel_width/2,
                                               config.wheel_shoulder_radius,config.wheel_crown_height))
        normal_offsets.append(support+compression*normal)
    return UnsprungGeometry(tuple(hits),np.asarray(delta),np.asarray(offsets),np.asarray(normals),
                            np.asarray(tangents),np.asarray(laterals),np.asarray(normal_offsets))

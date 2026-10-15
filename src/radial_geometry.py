"""唯一世界静态道路的连续有符号接触；轮心/轮轴可为共同求解的试探末构型。"""

from dataclasses import dataclass
from itertools import product

import numpy as np
from mechanical_kernels import cross
from panda3d.core import BitMask32
from radial_contact_kernels import signed_distance

from box_radial_geometry import box_section, wheel_support
from suspension_contacts import StaticSupportShapes, static_support_shapes
from unsprung_body import quaternion_rotation
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


@dataclass(frozen=True)
class RadialHit:
    node: object
    point: tuple
    normal: tuple
    plane: tuple | None


@dataclass(frozen=True)
class RadialSurface:
    body: object
    frame: np.ndarray
    translation: np.ndarray
    vertices: tuple
    plane: tuple | None
    triangles: object
    margin: float
    half: tuple = ()

    def query(self, center, axis, config):
        local_center,local_axis = self.frame@center+self.translation,self.frame@axis
        if self.plane is not None:
            normal,constant = self.plane
            normal = np.asarray(normal)
            lower = np.asarray(cylinder_support(tuple(-normal),tuple(local_axis),config.wheel_radius,
                config.wheel_width/2,config.wheel_shoulder_radius,config.wheel_crown_height))
            distance = np.dot(normal,local_center+lower)-constant
            wheel = local_center+lower
            point = wheel-distance*normal
            results = [(float(distance),normal,wheel,point,self.plane)]
        else:
            section = None
            if self.half and self.margin==0.:
                half = np.asarray(self.half)
                minimum = np.asarray([local_center[j]+wheel_support(np.eye(3)[j],local_axis,config)[j] for j in range(3)])
                maximum = np.asarray([local_center[j]+wheel_support(-np.eye(3)[j],local_axis,config)[j] for j in range(3)])
                gap = np.maximum(np.maximum(minimum-half,-half-maximum),0.)
                if np.linalg.norm(gap)>config.wheel_radius+config.suspension_travel:
                    return
                section = box_section(local_center,local_axis,self.half,config)
            vertices = (self.vertices,)
            if self.triangles is not None:
                padding = (config.wheel_radius+config.wheel_width/2+self.margin,)*3
                vertices = self.triangles.candidates(tuple(local_center),tuple(local_center),padding)
            results = ([section] if section is not None else [(*signed_distance(tuple(local_center),tuple(local_axis),points,
                config.wheel_radius,config.wheel_width,config.wheel_shoulder_radius,
                config.wheel_crown_height,self.margin),None) for points in vertices])
        for distance,normal,wheel,point,plane in results:
            if self.half and self.margin==0. and section is None:
                # 一般凸体结果仅在面内部核对解析平面；棱的全局证明由剖面算法完成。
                half = np.asarray(self.half)
                tolerance = 16*np.finfo(float).eps*max(1.,max(half),max(abs(np.asarray(point))))
                boundary = np.abs(np.abs(point)-half)<=tolerance
                if np.count_nonzero(boundary)==1:
                    index = int(np.flatnonzero(boundary)[0])
                    exact_normal = np.zeros(3)
                    exact_normal[index] = np.copysign(1.,point[index])
                    lower = np.asarray(cylinder_support(tuple(-exact_normal),tuple(local_axis),config.wheel_radius,
                        config.wheel_width/2,config.wheel_shoulder_radius,config.wheel_crown_height))
                    exact_distance = np.dot(exact_normal,local_center+lower)-half[index]
                    exact_point = local_center+lower-exact_distance*exact_normal
                    if all(abs(exact_point[j])<half[j]-tolerance for j in range(3) if j!=index):
                        distance,normal,wheel,point = float(exact_distance),exact_normal,local_center+lower,exact_point
                        plane = tuple(exact_normal),float(half[index])
            normal = self.frame.T@normal
            normal /= np.linalg.norm(normal)
            world_plane = None if plane is None else (tuple(normal),float(plane[1]-np.dot(plane[0],self.translation)))
            yield distance,normal,self.frame.T@(np.asarray(point)-self.translation),world_plane


class RadialRoads:
    """当前子步真实静态几何的只读描述，不拥有另一套物体或积分状态。"""

    def __init__(self, world, body, config, static_shapes=None):
        groups = (static_support_shapes(world,body,BitMask32.bit(0),packet_cache={})
                  if static_shapes is None else static_shapes)
        surfaces = []
        for road,supported,parts in groups:
            for index,part in enumerate(parts):
                _inverse,_frame,_translation,half,margin,plane,triangles,_bounds = part
                if supported:
                    body_pose,shape_pose = road.getTransform(),road.getShapeTransform(index)
                    body_rotation = quaternion_rotation(body_pose.getQuat())
                    rotation = body_rotation@quaternion_rotation(shape_pose.getQuat())
                    position = np.asarray(tuple(body_pose.getPos()))+body_rotation@np.asarray(tuple(shape_pose.getPos()))
                    vertices = tuple(product(*((-h,h) for h in half))) if half else ()
                    surfaces.append(RadialSurface(road,rotation.T,-rotation.T@position,
                        vertices,plane,triangles,margin,half))
                elif isinstance(groups,StaticSupportShapes) and road in groups.hulls:
                    hull = groups.hull_parts[id(part)]
                    rotation_body = quaternion_rotation(hull.body_pose[3:])
                    rotation = rotation_body@quaternion_rotation(hull.shape_pose[3:])
                    position = np.asarray(hull.body_pose[:3])+rotation_body@hull.shape_pose[:3]
                    surfaces.append(RadialSurface(road,rotation.T,-rotation.T@position,
                        hull.vertices,None,None,hull.margin))
                else:
                    raise ValueError(f"独立轮心有符号接触尚不支持该静态形状：{road.getName()}")
        self.surfaces,self.config = tuple(surfaces),config

    def query(self, centers, up, axes):
        config = self.config
        centers,up,axes = map(np.asarray,(centers,up,axes))
        hits,delta,offsets,normals,tangents,laterals,normal_offsets = [],[],[],[],[],[],[]
        for center,axis in zip(centers,axes):
            best = None
            for surface in self.surfaces:
                for distance,normal,point,plane in surface.query(center,axis,config):
                    if (distance<=config.wheel_radius+config.suspension_travel and road_support(normal)
                            and (best is None or distance<best[0])):
                        best = distance,normal,point,surface.body,plane
            if best is None:
                normal = up
                compression = -config.wheel_radius-config.suspension_travel
                offset,hit = -config.wheel_radius*up,None
            else:
                distance,normal,point,road,plane = best
                compression,offset = -distance,point-center
                hit = RadialHit(road,tuple(point),tuple(normal),plane)
            tangent = np.asarray(cross(normal,axis))
            tangent /= np.linalg.norm(tangent)
            support = np.asarray(cylinder_support(tuple(-normal),tuple(axis),config.wheel_radius,
                config.wheel_width/2,config.wheel_shoulder_radius,config.wheel_crown_height))
            hits.append(hit)
            delta.append(compression)
            offsets.append(offset)
            normals.append(normal)
            tangents.append(tangent)
            laterals.append(cross(tangent,normal))
            normal_offsets.append(support+compression*normal)
        return UnsprungGeometry(tuple(hits),np.asarray(delta),np.asarray(offsets),np.asarray(normals),
            np.asarray(tangents),np.asarray(laterals),np.asarray(normal_offsets))

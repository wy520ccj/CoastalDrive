"""唯一世界静态道路的连续有符号接触；轮心/轮轴可为共同求解的试探末构型。"""

from dataclasses import dataclass
from functools import cached_property
from itertools import product

import numpy as np
from panda3d.core import BitMask32
from radial_contact_kernels import signed_distance
from wheel_contact_kernels import radial_contact_frames, radial_plane_values

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

    @cached_property
    def plane_frame(self):
        """本子步只读平面的常量项；矩阵运算保留原布局和舍入。"""
        local_normal = np.asarray(self.plane[0])
        normal = self.frame.T@local_normal
        normal /= np.linalg.norm(normal)
        plane = tuple(normal),float(self.plane[1]-np.dot(self.plane[0],self.translation))
        return local_normal,normal,plane

    def query_plane(self, centers, axes, config):
        local_normal,normal,plane = self.plane_frame
        count = len(centers)
        local_centers = np.asarray([self.frame@center+self.translation for center in centers])
        local_axes = np.asarray([self.frame@axis for axis in axes])
        distances,point_inputs = np.empty(count),np.empty((count,3))
        radial_plane_values((local_centers,local_axes,local_normal,self.translation),
            (distances,point_inputs),count,config.wheel_radius,config.wheel_width/2,
            config.wheel_shoulder_radius,config.wheel_crown_height,self.plane[1])
        return tuple((float(distance),normal,self.frame.T@point,plane)
                     for distance,point in zip(distances,point_inputs))

    def query(self, center, axis, config):
        if self.plane is not None:
            yield from self.query_plane((center,),(axis,),config)
            return
        local_center,local_axis = self.frame@center+self.translation,self.frame@axis
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
        for distance,normal,_wheel,point,plane in results:
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
                        distance,normal,point = float(exact_distance),exact_normal,exact_point
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
        count = len(centers)
        planes = tuple(surface.query_plane(centers,axes,config) if surface.plane is not None else None
                       for surface in self.surfaces)
        hits = []
        touch,distances = np.zeros(count),np.zeros(count)
        points,hit_normals = np.zeros((count,3)),np.zeros((count,3))
        for i,(center,axis) in enumerate(zip(centers,axes)):
            best = None
            for surface,values in zip(self.surfaces,planes):
                candidates = surface.query(center,axis,config) if values is None else (values[i],)
                for distance,normal,point,plane in candidates:
                    if (distance<=config.wheel_radius+config.suspension_travel and road_support(normal)
                            and (best is None or distance<best[0])):
                        best = distance,normal,point,surface.body,plane
            if best is None:
                hit = None
            else:
                distance,normal,point,road,plane = best
                touch[i],distances[i],points[i],hit_normals[i] = 1.,distance,point,normal
                hit = RadialHit(road,tuple(point),tuple(normal),plane)
            hits.append(hit)
        delta = np.empty(count)
        offsets,normals,tangents,laterals,normal_offsets = (np.empty((count,3)) for _ in range(5))
        radial_contact_frames((centers,axes,up,touch,distances,points,hit_normals),
            (delta,offsets,normals,tangents,laterals,normal_offsets),count,
            config.wheel_radius,config.wheel_width/2,config.wheel_shoulder_radius,
            config.wheel_crown_height,config.suspension_travel)
        return UnsprungGeometry(tuple(hits),delta,offsets,normals,tangents,laterals,normal_offsets)

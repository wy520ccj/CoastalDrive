"""LAB-PERF-13原完整道路查询；数学入口保持，用于复用路径对照。"""

import numpy as np
from wheel_contact_kernels import radial_contact_frames

from radial_geometry import RadialHit, UnsprungGeometry
from vehicle_contacts import road_support


def query_reference(self, centers, up, axes):
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

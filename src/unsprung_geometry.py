"""实际轮心的径向接触入口；读取唯一世界，不维护轮心积分状态。"""

from radial_geometry import RadialRoads, UnsprungGeometry

__all__ = ["UnsprungGeometry","read_unsprung_geometry"]


def read_unsprung_geometry(world, body, centers, up, axes, config, *, static_shapes=None):
    return RadialRoads(world,body,config,static_shapes).query(centers,up,axes)

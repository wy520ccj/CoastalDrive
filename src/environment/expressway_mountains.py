"""连续山体：主峰、支脊、沟谷与林岩表面；跟随现有segment释放。"""

import math
from functools import lru_cache

from panda3d.core import Vec3

from environment.expressway import smooth
from environment.expressway_route import anchor, sample, terrain_point


def noise(x, y, seed):
    """平滑二维值噪声，输入使用绝对里程，分段边界得到同一个值。"""
    ix, iy = math.floor(x), math.floor(y)
    u, v = x-ix, y-iy
    u, v = u*u*(3-2*u), v*v*(3-2*v)

    return ((1-u)*noise_value(ix, iy, seed)+u*noise_value(ix+1, iy, seed))*(1-v) + ((1-u)*noise_value(ix, iy+1, seed)+u*noise_value(ix+1, iy+1, seed))*v


@lru_cache(maxsize=8192)
def noise_value(a, b, seed):
    n = (a*374761393 + b*668265263 + seed*1442695041) & 0xffffffff
    n = ((n ^ (n >> 13))*1274126177) & 0xffffffff
    return ((n ^ (n >> 16)) & 65535)/65535



def mountain_point(curve, side, width, s, seed):
    if side < 0:
        edge = terrain_point(curve, -120, s, seed)
        x, y, base = edge.x-width, edge.y, edge.z
    else:
        center = sample(curve, s)
        x, y, base = 430+width, center.y, -4.0
    mass, fade = mountain_height(width,s,seed)
    z = base*(1-fade) + (mass-4)*fade
    return Vec3(x, y, z)


@lru_cache(maxsize=8192)
def mountain_height(width,s,seed):
    # 主脊横向摆动，支脊与山坳使用不同尺度，避免挤出的三角长条。
    shift = 40*(noise(0, s/290, seed)-.5)
    main = math.exp(-((width-155-shift)/105)**2)
    back = math.exp(-((width-335+shift)/90)**2)
    peak = 55+95*noise(width/180, s/230, seed+3)
    ridge = 1-abs(2*noise(width/48, s/62, seed+9)-1)
    erosion = 10*ridge+8*noise(width/21, s/29, seed+7)
    mass = main*(peak+erosion)+back*(85+95*noise(width/210,s/340,seed+13))
    fade = smooth(0, 65, width)
    return mass, fade


def build_mountains(root, index, seed, curve, kit, details):
    for _ in mountain_steps(root, index, seed, curve, kit, lambda s: details):
        pass


def mountain_steps(root, index, seed, curve, kit, detail_parent):
    from environment.surface_mesh import surface_mesh

    origin = Vec3(*anchor(curve, index))
    for side in (-1, 1):
        vertices, normals, colors, uvs, faces = [], [], [], [], []
        for local in range(0, 201, 10):
            s = index*200+local
            for width in range(0, 481, 12):
                p = mountain_point(curve, side, width, s, seed)
                dx = mountain_point(curve, side, width+.5, s, seed)-mountain_point(curve, side, width-.5, s, seed)
                dy = mountain_point(curve, side, width, s+.5, seed)-mountain_point(curve, side, width, s-.5, seed)
                normal = dx.cross(dy).normalized()*side
                vertices.append(tuple(p-origin))
                normals.append(normal)
                patches = noise(width/36, s/48, seed+21)
                rock = smooth(.18,.48,1-normal.z)*smooth(.28,.70,patches)
                colors.append((.13+.17*patches,.23+.16*patches,.10+.13*patches,rock))
                uvs.append((width,index*200 % 720+local))
            yield "mountain-row"
        for row in range(20):
            for col in range(40):
                a = row*41+col
                pair = ((a,a+1,a+42),(a,a+42,a+41))
                faces.extend(pair if side > 0 else tuple(tuple(reversed(f)) for f in pair))
        node = surface_mesh("route-mountain", vertices, faces, normals, colors, uvs)
        node.setMaterial(kit["surface-material"])
        node.setTexture(kit["ground"])
        node.setShader(kit["mountain-shader"],1)
        node.setShaderInput("expressway_rock",kit["rock"])
        node.reparentTo(root)
        yield "mountain-mesh"
        if side < 0:
            from environment.expressway_vegetation import mountain_vegetation_steps

            yield from mountain_vegetation_steps(index,seed,curve,kit,detail_parent)

"""高速林缘群落：全局斑块、树下灌丛与地面草簇，沿既有分段回收。"""

import math
import random
from functools import lru_cache
from itertools import pairwise

from panda3d.core import Vec3, Vec4

from highway_segments import SEGMENT_LENGTH, segment

TERRAIN_COLUMNS = (8.5, 11, 14, 17, 19, 20, 26, 32, 35, 39, 44, 50, 57, 65, 74, 86, 102, 120)


def ground_point(curve, d, s, seed):
    """直接插值已显示的5m地形三角面，灌丛底部随坡面落地。"""
    from environment.expressway_route import terrain_point

    columns = sorted((-1 if d < 0 else 1)*v for v in TERRAIN_COLUMNS)
    left, right = next((a,b) for a,b in pairwise(columns) if a <= d <= b)
    first = math.floor(s/5)*5
    u, v = (d-left)/(right-left), (s-first)/5
    a,b,c,e = (terrain_point(curve,x,y,seed) for x,y in
               ((left,first),(right,first),(right,first+5),(left,first+5)))
    return a*(1-u)+b*(u-v)+c*v if u >= v else a*(1-v)+c*u+e*(v-u)


@lru_cache(maxsize=32)
def planting(index, seed):
    """随机仅改变群落内部；以全局斑块为单位安排林缘和看海开口。"""
    from environment.expressway_route import district

    start, end = index*SEGMENT_LENGTH, (index+1)*SEGMENT_LENGTH
    items = []

    def add(model, d, s, scale, heading):
        if start <= s < end:
            items.append((model,d,s,scale,heading))

    for cell in range(math.floor((start-60)/160), math.floor((end+60)/160)+1):
        for side in (-1,1):
            rng = random.Random(seed*971+cell*7919+side*131)
            center = cell*160+rng.uniform(35,125)
            zone, local = district(center,seed)
            # 海湾留出较大的无遮挡视窗，桥台与声屏障区收敛为低灌丛。
            open_bay = side > 0 and zone in (0,2) and local < 1050
            length = rng.uniform(14,32) if open_bay else rng.uniform(28,50)
            cx = side*rng.uniform(15.5,19)
            for n in range(5 if open_bay else 11):
                d = cx+side*rng.uniform(-1.8,3.2)
                s = center+rng.triangular(-length,length,0)
                size = rng.uniform(.85,1.35)
                add("fine-shrubs",d,s,(size,size*rng.uniform(.8,1.2),rng.uniform(.65,1.05)),rng.uniform(0,360))
            if not open_bay and not (zone in (1,3) and 750 < local < 900):
                cx = side*rng.uniform(37,49)
                for n in range(rng.randint(5,9)):
                    d, s = cx+rng.uniform(-4,6)*side, center+rng.uniform(-21,21)
                    size = rng.uniform(.95,1.75)
                    add("broadleaf-a" if n%2 else "broadleaf-b",d,s,(size,size,size*rng.uniform(.9,1.1)),rng.uniform(0,360))
                    add("fine-shrubs",d+side*1.8,s+2,(1.3,1.4,.8),rng.uniform(0,360))
    # 原碰撞树不移动：加入林下植被及相邻树冠，把孤立的树接入局部林缘。
    for number,(d,local,scale,heading) in enumerate(segment(seed,index).trees):
        rng = random.Random(seed*773+index*6271+number*163)
        s,side = start+local,-1 if d < 0 else 1
        for n in range(3):
            add("fine-shrubs",d+rng.uniform(-2.6,2.6),s+rng.uniform(-4.5,4.5),
                (rng.uniform(1.1,1.6),rng.uniform(1,1.6),rng.uniform(.65,1)),rng.uniform(0,360))
        if side < 0 or district(s,seed)[0] in (1,3,4):
            size = rng.uniform(1.1,1.6)
            add("broadleaf-a" if number%2 else "broadleaf-b",d+side*rng.uniform(4,7),
                s+rng.uniform(-7,7),(size,size,size),heading+70)
    return tuple(items)


def vegetation_steps(root, index, seed, curve, kit, detail_parent):
    from environment.expressway_route import anchor
    from scene import make_mesh

    origin = Vec3(*anchor(curve,index))
    grass_vertices, grass_faces = [], []
    for number,(model,d,s,scale,heading) in enumerate(planting(index,seed)):
        point = ground_point(curve,d,s,seed)-origin
        if point.z+origin.z < -2:
            continue
        node = kit[model].copyTo(detail_parent(s))
        node.setScale(*scale)
        node.setPos(point-Vec3(0,0,.15 if model == "fine-shrubs" else .12))
        node.setH(heading)
        # 群落边缘的低草同样成簇；不沿路重复铺出等距小盆栽。
        if model == "fine-shrubs" and number%2 == 0:
            rng = random.Random(seed*997+index*101+number)
            for _ in range(12):
                x,y = d+rng.uniform(-2.4,2.4),s+rng.uniform(-2.8,2.8)
                base = ground_point(curve,x,y,seed)-origin-Vec3(0,0,.03)
                height = rng.uniform(.22,.55)
                angle = rng.uniform(0,math.tau)
                dx,dy = math.cos(angle)*.10,math.sin(angle)*.10
                i = len(grass_vertices)
                grass_vertices.extend((tuple(base+Vec3(-dx,-dy,0)),tuple(base+Vec3(dx,dy,0)),
                                       tuple(base+Vec3(dx*.4,dy*.4,height))))
                grass_faces.append((i,i+1,i+2))
        yield "vegetation"
    grass = make_mesh("forest-ground-cover",grass_vertices,grass_faces,Vec4(.22,.31,.08,1))
    grass.setTwoSided(True)
    grass.reparentTo(detail_parent(index*SEGMENT_LENGTH+100))
    yield "ground-cover"


def understory(index, seed):
    """林下色斑跨段采样；与实际树木共用位置，不额外叠贴地面。"""
    return [(d,s,6 if model.startswith("broadleaf") else 3.5)
            for adjacent in (index-1,index,index+1)
            for model,d,s,scale,heading in planting(adjacent,seed)]


def cover_color(d, s, color, beds):
    shade = 0
    for x,y,radius in beds:
        if abs(s-y) > radius*1.8 or abs(d-x) > radius:
            continue
        distance = ((d-x)/radius)**2+((s-y)/(radius*1.8))**2
        shade = max(shade, max(0,1-distance)**2*.55)
    # 苔草、林下土色和原草色柔和交接，不画人工整圆花坛。
    return tuple(a*(1-shade)+b*shade for a,b in zip(color,(.17,.22,.075)))


def mountain_ground(curve, width, s, seed):
    from environment.expressway_mountains import mountain_point

    x, y = math.floor(width/12)*12, math.floor(s/10)*10
    u, v = (width-x)/12, (s-y)/10
    a,b,c,d = (mountain_point(curve,-1,w,t,seed) for w,t in
               ((x,y),(x+12,y),(x+12,y+10),(x,y+10)))
    return a*(1-u)+b*(u-v)+c*v if u >= v else a*(1-v)+c*u+d*(v-u)


def mountain_vegetation_steps(index, seed, curve, kit, detail_parent):
    """山脚灌木以斑块贴合真实三角面，不再把无树干树冠等距悬在山坡上。"""
    from environment.expressway_route import anchor

    start,end = index*200,(index+1)*200
    origin = Vec3(*anchor(curve,index))
    for cell in range(math.floor((start-35)/240),math.floor((end+35)/240)+1):
        rng = random.Random(seed*1699+cell*3571)
        center = cell*240+rng.uniform(65,175)
        width = rng.uniform(14,44)
        for _ in range(8):
            s,w = center+rng.uniform(-26,26),width+rng.uniform(-5,5)
            if not start <= s < end:
                continue
            p = mountain_ground(curve,w,s,seed)
            across = mountain_ground(curve,w+2,s,seed)-mountain_ground(curve,w-2,s,seed)
            along = mountain_ground(curve,w,s+2,seed)-mountain_ground(curve,w,s-2,seed)
            if abs(across.z)/4 > .45 or abs(along.z)/4 > .45:
                continue
            size = rng.uniform(.9,1.5)
            floor = min(mountain_ground(curve,w+dw,s+ds,seed).z for dw,ds in
                        ((0,0),(-size*2,0),(size*2,0),(0,-size),(0,size)))
            node = kit["fine-shrubs"].copyTo(detail_parent(s))
            node.setPos(p.x-origin.x,p.y-origin.y,floor-origin.z-.12)
            node.setScale(size,size,.8)
            node.setH(rng.uniform(0,360))
            yield "mountain-understory"

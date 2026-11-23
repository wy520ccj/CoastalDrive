"""陆地街区：共享建筑模板、贴地街道与绿地，随原道路分段装卸。"""

import math

from panda3d.core import FadeLODNode, GeomVertexWriter, LODNode, Vec3, Vec4


def city_steps(root, index, seed, curve, kit):
    from environment.expressway_buildings import SPECS, BuildingMesh, _bind_surface
    from environment.expressway_materials import lab_asphalt_shader
    from environment.expressway_route import _city_shift, anchor, city_weight, terrain_point
    from scene import make_mesh

    start = index*200
    if city_weight(start+100, seed) < .95:
        return
    origin = Vec3(*anchor(curve, index))

    def city_point(d, s):
        return terrain_point(curve, d+_city_shift(s, seed), s, seed)

    # 与原树组一样保留独立LOD边界，避免道路合批烘焙每栋楼的共享顶点。
    district = root.attachNewNode(LODNode('city-district-distance'))
    district.node().addSwitch(1800, 0)
    district.node().setCenter(city_point(195, start+100)-origin)
    group = district.attachNewNode('mainland-city')
    group.setMaterial(kit['surface-material'])

    def plant(template, parent, position, height, heading):
        node = template.copyTo(parent)
        for child in (node, *node.findAllMatches('**')):
            child.show()
        low, high = node.getTightBounds(node)
        scale = height/(high.z-low.z)
        node.setScale(scale)
        node.setPos(position-Vec3(0, 0, low.z*scale+.04))
        node.setH(heading)
        return node

    def strip(name, left, right, begin, end, color, lift=.025, entrance_edge=None):
        vertices, faces, uv = [], [], []
        count = max(1, math.ceil((end-begin)/5))
        for row in range(count+1):
            s = begin+(end-begin)*row/count
            for d in (left, right):
                shift = _city_shift((begin+end)/2 if d == entrance_edge else s, seed)
                across = d+shift
                vertices.append(tuple(terrain_point(curve, across, s, seed)-origin+Vec3(0, 0, lift)))
                uv.append((across, start % 600+(s-start)))
            if row:
                a = (row-1)*2
                faces.extend(((a, a+1, a+3), (a, a+3, a+2)))
        node = make_mesh(name, vertices, faces, Vec4(*color))
        if name in ('city-local-street', 'city-cross-street'):
            node.setTexture(kit['road-albedo'])
            node.setShader(lab_asphalt_shader())
            node.setShaderInput('asphalt_normals', kit['road-normal'])
            node.setShaderInput('asphalt_roughness', kit['road-roughness'])
        elif name in ('city-footpath', 'city-cross-footpath', 'city-entrance-path', 'city-courtyard-path'):
            writer = GeomVertexWriter(node.node().modifyGeom(0).modifyVertexData(), 'texcoord')
            for face in faces:
                for vertex_index in face:
                    writer.setData2f(*uv[vertex_index])
            _bind_surface(node, 'paving')
        node.reparentTo(group)

    for road in (65, 155):
        strip('city-local-street', road-3.5, road+3.5, start, start+200, (.72, .72, .72, 1))
        yield 'city-street'
        for side in (-1, 1):
            a, b = sorted((road+side*3.5, road+side*5.3))
            # 横街接入内侧，路缘和人行道在路口让开，不能横堵地方车道。
            spans = ((start, start+7.2), (start+17.8, start+200)) if (
                (road == 65 and side == 1) or (road == 155 and side == -1)) else ((start, start+200),)
            for begin, end in spans:
                strip('city-footpath', a, b, begin, end, (.20, .19, .17, 1), .13)
                strip('city-curb', road+side*3.5-.08, road+side*3.5+.08,
                      begin, end, (.32, .31, .28, 1), .17)
            yield 'city-footpath'
        for station in range(25, 200, 40):
            strip('city-street-dash', road-.045, road+.045, start+station, start+station+3,
                  (.50, .48, .40, 1), .035)
            lamp = kit['lamp'].copyTo(group)
            lamp.setScale(.62)
            lamp.setPos(city_point(road-4.5, start+station)-origin)
            lamp.setH((curve.sample(start+station).heading if curve else 0)+180)
            yield 'city-street-detail'
    strip('city-cross-street', 61.5, 158.5, start+9, start+16, (.72, .72, .72, 1))
    for begin, end in ((start+7.2, start+9), (start+16, start+17.8)):
        strip('city-cross-footpath', 68.5, 151.5, begin, end, (.20, .19, .17, 1), .13)
    yield 'city-cross-street'
    # 两排住宅以后院相接，入口分别朝向两条街；中间保留贯通绿带和步道。
    strip('city-courtyard-path', 108, 110, start+17.8, start+207.2, (.23, .22, .19, 1), .06)
    yield 'city-courtyard'
    for number in range(8):
        row, place = divmod(number, 4)
        road, facing = (65, 1) if row == 0 else (155, -1)
        station = ((35, 78, 121, 164), (54, 96, 139, 182))[row][place]
        setback = ((25, 29, 24, 27), (26, 25, 29, 24))[row][place]
        s, d = start+station, road+facing*setback
        family = (index+number+row*2) % 4
        model = kit['city-models'][family].copyTo(group)
        p = city_point(d, s)-origin
        width, depth = SPECS[family][:2]
        model.setPos(p)
        heading = (curve.sample(s).heading if curve else 0)+(180 if facing < 0 else 0)
        model.setH(heading)
        floors = []
        for x in (-width/2-.12, width/2+.12):
            for y in (-depth/2-.12, depth/2+.12):
                corner = group.getRelativePoint(model, Vec3(x, y, 0))+origin
                along, across = curve.project(tuple(corner)) if curve else (corner.y, corner.x)
                floors.append(terrain_point(curve, across, along, seed).z)
        low, high = min(floors)-.08, max(floors)+.06
        model.setZ(high-origin.z)
        model.setTag('city-lot', str(number))
        foundation = group.attachNewNode('city-foundation')
        base_mesh = BuildingMesh()
        base_mesh.box('masonry', (0, 0, 0), (width/2+.12, depth/2+.12, (high-low)/2), (.23, .22, .19, 1))
        base_mesh.attach(foundation, {'masonry': kit['surface-material']})
        foundation.setPos(p.x, p.y, (low+high)/2-origin.z)
        foundation.setH(model.getH())
        foundation.setTag('city-lot', str(number))
        left, right = sorted((road+facing*5.3, d-facing*width/2))
        strip('city-entrance-path', left, right, s-1.48, s+1.48, (.20, .19, .17, 1), .13,
              entrance_edge=d-facing*width/2)
        yield 'city-building'
        # 围墙、树池、步道和入口围合成宅基地，不给整片城市垫一块板。
        plot = group.attachNewNode('city-garden')
        plot.setPos(p-Vec3(0, 0, .08))
        plot.setH(heading)
        plot.setTag('city-lot', str(number))
        mesh = BuildingMesh()
        front, back, side = -width/2-7.5, width/2+4, depth/2+4
        wall = (.28, .27, .23, 1)
        cap = (.38, .37, .32, 1)
        floors = {}

        def garden_floor(x, y, *, floors=floors, plot=plot):
            key = x, y
            if key not in floors:
                point = group.getRelativePoint(plot, Vec3(x, y, 0))+origin
                along, across = curve.project(tuple(point)) if curve else (point.y, point.x)
                floors[key] = terrain_point(curve, across, along, seed).z-origin.z-plot.getZ()
            return floors[key]

        def grounded_box(mesh, material, center, half, lower, upper, color, *, level=False):
            # 保留一个六面构件和原材质批次，只让底边/压顶接到各自的真实坡面。
            x, y = center
            hx, hy = half
            corners = [(x+sx*hx, y+sy*hy) for sy in (-1, 1) for sx in (-1, 1)]
            ground = [garden_floor(*point) for point in corners]
            top = [max(ground)+upper]*4 if level else [z+upper for z in ground]
            vertices = [Vec3(px, py, z+lower) for (px, py), z in zip(corners, ground)]
            vertices.extend(Vec3(px, py, z) for (px, py), z in zip(corners, top))
            for face in ((0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4),
                         (1, 3, 7, 5), (3, 2, 6, 7), (2, 0, 4, 6)):
                mesh.quad(material, [vertices[i] for i in face], color)
            return max(top)

        soil_tops = {}
        for direction in (-1, 1):
            grounded_box(mesh, 'masonry', ((front+back)/2, direction*side), ((back-front)/2, .18), -.12, .74, wall)
            grounded_box(mesh, 'trim', ((front+back)/2, direction*side),
                         ((back-front)/2+.05, .23), .715, .805, cap)
            length = (side-1.5)/2
            y = direction*(side+1.5)/2
            grounded_box(mesh, 'masonry', (front, y), (.18, length), -.12, .74, wall)
            grounded_box(mesh, 'trim', (front, y), (.23, length+.04), .715, .805, cap)
            # 窄种植池围绕院前铺装，保留到楼门的清楚通路。
            top = grounded_box(mesh, 'masonry', (front+2.4, direction*(side-2)),
                               (1.3, 1.15), -.08, .36, wall, level=True)
            mesh.box('soil', (front+2.4, direction*(side-2), top-.04),
                     (1.13, .98, .015), (.075, .055, .027, 1))
            soil_tops[direction] = top-.025
            yield 'city-garden-boundary'
        lift = high-origin.z-plot.getZ()
        landing = garden_floor(-width/2-2, 0)+.13
        for step in range(1, max(1, math.ceil((lift-landing)/.15))+1):
            x = -width/2-.34*step
            bottom = min(garden_floor(x+sx*.34, sy*1.35) for sx in (-1, 1) for sy in (-1, 1))-.08
            top = lift-.15*(step-1)
            mesh.box('trim', (x, 0, (bottom+top)/2), (.34, 1.35, (top-bottom)/2), cap)
        mesh.attach(plot, {name: kit['surface-material'] for name in ('masonry', 'trim', 'soil')})
        planting = plot.attachNewNode(FadeLODNode('garden-plants-distance'))
        planting.node().addSwitch(190, 0)
        planting.node().setFadeTime(.35)
        planting_group = planting.attachNewNode('garden-shrubs')
        for direction in (-1, 1):
            # 花池保留一株，另一株落到墙脚；用原四株接起庭院的高低层次。
            plant(kit['city-shrub'], planting_group,
                  Vec3(front+2.4, direction*(side-2), soil_tops[direction]),
                  1.1, number*67+direction*30)
            x, y = -width/2-2.4, direction*(side-1.3)
            shrub = plant(kit['city-shrub'], planting_group, Vec3(x, y, garden_floor(x, y)),
                          .85+(number % 3)*.1, number*67-direction*45)
            shrub.setSx(shrub.getSx()*1.3)
            shrub.setSy(shrub.getSy()*.9)
            shrub.setTag('city-garden-ground-shrub', '1')
        tree_y = side*.5*(-1 if number % 3 == 0 and number not in (1, 6) else 1)
        tree = plant(kit['tree-'+str(number % 2)], plot,
                     Vec3(front+3.4, tree_y, garden_floor(front+3.4, tree_y)),
                     6.5+number % 2, number*97)
        tree.setTag('city-garden-tree', '1')
        if number in (1, 6):
            # 停车仅复用既有显示模型；不进入交通列表或权威物理世界。
            car = kit['city-parked-cars'][number % 2].copyTo(plot)
            low, _high = car.getTightBounds(car)
            mesh = BuildingMesh()
            parking_top = grounded_box(mesh, 'trim', (front+3.3, -side*.53), (1.45, 2.7),
                                       -.08, .07, (.17, .17, .15, 1), level=True)
            car.setPos(front+3.3, -side*.53, parking_top+.02-low.z)
            car.setH(180 if number == 1 else 0)
            car.setTag('city-parked-car', '1')
            mesh.attach(plot, {'trim': kit['surface-material']})
        yield 'city-garden'
    for number in range(8):
        s = start+24+number*22
        d = 73 if number % 2 else 164
        # 外街两株转入后院绿带，连接已有院树；保留总量和另外两株外街树。
        if number == 2:
            d, s = 104, start+60
        elif number == 6:
            d, s = 115, start+160
        tree = plant(kit['tree-'+str(number % 2)], group,
                     city_point(d, s)-origin, 6+number % 3, (number*113+index*17) % 360)
        tree.setTag('city-tree', '1')
        yield 'city-tree'
    # 两组小乔木/灌丛沿公共绿带生长，替代原来排队的六株灌木。
    for number, (d, station) in enumerate(((104, 70), (115, 150))):
        s = start+station
        tree = plant(kit['tree-'+str(number)], group, city_point(d, s)-origin,
                     6, index*29+number*83)
        tree.setTag('city-courtyard-tree', '1')
        for offset in (-7, 7):
            shrub = plant(kit['city-shrub'], group, city_point(d, s+offset)-origin,
                          1.4, index*29+number*83+offset*3)
            shrub.setTag('city-courtyard-shrub', '1')
        yield 'city-courtyard-plant'
    # 公路与街区之间是成组的林缘，保留看向入口和建筑的开口。
    # 阔冠低树与窄冠高树相配，避免整排等高；不扩大全部树冠来填空。
    groves = ((75, 54, 6.5), (79, 60, 11), (78, 98, 6),
              (81, 104, 11), (74, 141, 7), (80, 147, 10))
    for number, (d, station, height) in enumerate(groves):
        s = start+station
        tree = plant(kit['tree-'+str(number % 2)], group, city_point(d, s)-origin,
                     height, number*131+index*23)
        tree.setTag('city-greenbelt-tree', '1')
        for across, along, height in ((-1.8, -2.5, 1.05), (2.2, 2., 1.25)):
            shrub = plant(kit['city-shrub'], group,
                          city_point(d+across, s+along)-origin, height, number*71+along*17)
            shrub.setTag('city-greenbelt-shrub', '1')
        yield 'city-greenbelt'

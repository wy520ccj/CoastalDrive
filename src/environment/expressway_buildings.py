"""设计43的住宅构件：按米制尺寸生成共享立面、阳台、入口和屋顶。"""

from functools import lru_cache

from panda3d.core import (
    FadeLODNode,
    Geom,
    GeomNode,
    GeomTriangles,
    GeomVertexData,
    GeomVertexFormat,
    GeomVertexWriter,
    Material,
    TextureStage,
    Vec3,
)

SPECS = ((14, 18, 3, (.48, .42, .31, 1)), (18, 20, 5, (.55, .53, .47, 1)),
         (16, 20, 4, (.31, .14, .075, 1)), (18, 22, 7, (.50, .49, .43, 1)))
TRIM = (.44, .44, .40, 1)
METAL = (.055, .065, .061, 1)
STONE = (.23, .22, .19, 1)
# 固定White Plaster 02原1K底色的线性均值；让顶点色定义涂层，照片只保留表面变化。
PLASTER_LINEAR_MEAN = (.2719839789, .2461039903, .1985410272)
MASONRY_LINEAR_MEAN = (.2521226957, .1815966833, .1119483300)
PAVING_LINEAR_MEAN = (.2482886943, .2066150268, .1583266953)


@lru_cache(maxsize=1)
def plaster_assets():
    from environment.expressway_materials import city_plaster_shader, photographed_surface

    return (city_plaster_shader(),
            photographed_surface('white_plaster_02_diff_1k.jpg', color=True),
            photographed_surface('white_plaster_02_nor_gl_1k.jpg'),
            photographed_surface('white_plaster_02_rough_1k.jpg'))


@lru_cache(maxsize=1)
def masonry_assets():
    from environment.expressway_materials import city_plaster_shader, photographed_surface

    return (city_plaster_shader(),
            photographed_surface('rustic_stone_wall_02_diff_1k.jpg', color=True),
            photographed_surface('rustic_stone_wall_02_nor_gl_1k.jpg'),
            photographed_surface('rustic_stone_wall_02_rough_1k.jpg'))


@lru_cache(maxsize=1)
def paving_assets():
    from environment.expressway_materials import city_plaster_shader, photographed_surface

    return (city_plaster_shader(),
            photographed_surface('floor_pavement_diff_1k.jpg', color=True),
            photographed_surface('floor_pavement_nor_gl_1k.jpg'),
            photographed_surface('floor_pavement_rough_1k.jpg'))


_SURFACE_SETTINGS = {
    'plaster': (plaster_assets, PLASTER_LINEAR_MEAN, 1., .35, .18),
    'masonry': (masonry_assets, MASONRY_LINEAR_MEAN, 1/1.5, 1., .6),
    'paving': (paving_assets, PAVING_LINEAR_MEAN, .5, .8, .35),
}


def _bind_surface(path, name):
    """三种城市表面沿用同一PBR，只绑定各自已校准的贴图和米制参数。"""
    load, mean, scale, variation, strength = _SURFACE_SETTINGS[name]
    shader, diffuse, normal, roughness = load()
    path.setTexture(diffuse)
    path.setShader(shader, 1)
    path.setShaderInput('city_normal', normal)
    path.setShaderInput('city_roughness', roughness)
    path.setShaderInput('city_albedo_scale', tuple(1/channel for channel in mean))
    path.setShaderInput('city_tex_scale', scale)
    path.setShaderInput('city_color_variation', variation)
    path.setShaderInput('city_normal_strength', strength)


class BuildingMesh:
    """同一模板按材料收集面片；实例不重新生成或烘焙顶点。"""

    def __init__(self):
        self.parts = {}

    def quad(self, material, points, color):
        points = [Vec3(*p) for p in points]
        normal = (points[1]-points[0]).cross(points[2]-points[0]).normalized()
        vertices, faces = self.parts.setdefault(material, ([], []))
        start = len(vertices)
        # 立面UV按水平长度/高度展开，不能沿用道路XY投影压成单行。
        for point in points:
            uv = ((point.y, point.z) if abs(normal.x) > .5 else
                  (point.x, point.z) if abs(normal.y) > .5 else (point.x, point.y))
            vertices.append((point, normal, color, uv))
        faces.extend(((start, start+1, start+2), (start, start+2, start+3)))

    def box(self, material, center, half, color):
        c, h = Vec3(*center), Vec3(*half)
        v = [c+Vec3(x*h.x, y*h.y, z*h.z)
             for z in (-1, 1) for y in (-1, 1) for x in (-1, 1)]
        for face in ((0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4),
                     (1, 3, 7, 5), (3, 2, 6, 7), (2, 0, 4, 6)):
            self.quad(material, [v[i] for i in face], color)

    def attach(self, parent, materials):
        for name, (vertices, faces) in self.parts.items():
            data = GeomVertexData(name, GeomVertexFormat.getV3n3c4t2(), Geom.UHStatic)
            data.setNumRows(len(vertices))
            writers = [GeomVertexWriter(data, key) for key in ('vertex', 'normal', 'color', 'texcoord')]
            for point, normal, color, uv in vertices:
                writers[0].addData3f(point)
                writers[1].addData3f(normal)
                writers[2].addData4f(*color)
                writers[3].addData2f(*uv)
            primitive = GeomTriangles(Geom.UHStatic)
            for face in faces:
                primitive.addVertices(*face)
            geom = Geom(data)
            geom.addPrimitive(primitive)
            node = GeomNode('city-'+name)
            node.addGeom(geom)
            path = parent.attachNewNode(node)
            path.setMaterial(materials[name], 1)
            if name in _SURFACE_SETTINGS:
                _bind_surface(path, name)


def facade(mesh, normal, along, center, extent, floors, color, family, detailed, first_floor=0):
    def point(u, z, outward=0):
        return center+along*u+normal*outward+Vec3(0, 0, z)

    def panel(material, left, right, bottom, top, tint, outward=0):
        mesh.quad(material, [point(left, bottom, outward), point(right, bottom, outward),
                             point(right, top, outward), point(left, top, outward)], tint)

    def bar(material, u, z, width, height, depth, outward, tint):
        half = Vec3(abs(along.x)*width+abs(normal.x)*depth,
                    abs(along.y)*width+abs(normal.y)*depth, height)*.5
        mesh.box(material, point(u, z, outward), half, tint)

    bays = round(extent/3.8)
    bays += bays % 2 == 0
    pitch = extent/bays
    for floor in range(first_floor, first_floor+floors):
        base, top = floor*3.1, (floor+1)*3.1
        for bay in range(bays):
            u = -extent/2+(bay+.5)*pitch
            entrance = normal.x < -.5 and floor == 0 and bay == bays//2
            balcony = floor > 0 and (
                (normal.x < -.5 and bay != bays//2) or
                (normal.x > .5 and bay in (1, bays-2)) or
                (normal.y < -.5 and bay == bays-1))
            half = 1.12 if balcony else .72
            bottom, head = base+(.16 if balcony or entrance else .80), base+2.65
            if entrance:
                half, bottom = 1.05, .10
            tint = color
            if family == 2 and bay in (0, bays-1):
                tint = (.46, .44, .39, 1)
            # 近远档都保留窗洞，不能靠极小偏移把窗片叠到整墙上。
            for a, b, lo, hi in ((u-pitch/2, u-half, base, top),
                                 (u+half, u+pitch/2, base, top),
                                 (u-half, u+half, base, bottom),
                                 (u-half, u+half, head, top)):
                panel('plaster', a, b, lo, hi, tint)
            outer = [point(u-half, bottom), point(u+half, bottom),
                     point(u+half, head), point(u-half, head)]
            inner = [p-normal*.19 for p in outer]
            for j in range(4):
                mesh.quad('stone', (outer[j], outer[(j+1) % 4], inner[(j+1) % 4], inner[j]), STONE)
            pane_depth = -.18
            shade = .78+((floor*13+bay*7+family*3) % 5)*.06
            glass = (.027*shade, .045*shade, .054*shade, 1)
            panel('glass', u-half, u+half, bottom, head, glass, pane_depth)
            if detailed:
                for x in (u-half+.04, u, u+half-.04):
                    bar('metal', x, (bottom+head)/2, .065, head-bottom, .09, -.12, METAL)
                for z in (bottom+.04, head-.04):
                    bar('metal', u, z, half*2, .075, .09, -.12, METAL)
                bar('stone', u, bottom-.045, half*2+.22, .09, .25, -.015, TRIM)
                curtain = (floor*3+bay+family) % 5
                if curtain < 3 and not entrance:
                    curtain_width = half*(.48 if curtain == 0 else .9)
                    for fold in range(4):
                        left = u-half+.08+fold*curtain_width/4
                        curtain_tint = (.24, .22, .18, 1) if fold % 2 else (.32, .30, .25, 1)
                        panel('trim', left, left+curtain_width/4, bottom+.09, head-.08, curtain_tint, -.165)
            if balcony:
                bar('trim', u, base+.07, 2.85, .20, 1.52, .66, TRIM)
                bar('trim', u, base+.42, 2.85, .55, .13, 1.34, tint)
                for side in (-1, 1):
                    bar('trim', u+side*1.36, base+.60, .13, .91, 1.38, .66, tint)
                bar('metal', u, base+1.14, 2.85, .055, .055, 1.34, METAL)
                if detailed:
                    for post in range(7):
                        bar('metal', u-1.29+post*.43, base+.91, .035, .43, .035, 1.34, METAL)
            if entrance:
                bar('trim', u, 2.87, 3.15, .18, 1.65, .60, TRIM)
                bar('stone', u, .07, 2.85, .14, 1.25, .45, STONE)
                if detailed:
                    bar('metal', u+.17, 1.13, .035, .55, .08, -.045, (.17, .18, .17, 1))
        # 楼板收边和低矮石基形成连续接缝，远景保留相同轮廓。
        bar('trim', 0, top-.055, extent+.08, .11, .12, .015, TRIM)
    if first_floor == 0:
        # 正门保留同窗洞的净宽，石基不能横穿门片及门前台阶。
        spans = ((-extent/2-.05, -1.05), (1.05, extent/2+.05)) if normal.x < -.5 else (
            (-extent/2-.05, extent/2+.05),)
        for left, right in spans:
            bar('stone', (left+right)/2, .325, right-left, .65, .12, .025, STONE)


def load_city_models(parent, surface):
    materials = {'plaster': surface, 'trim': surface, 'stone': surface}
    for name, rough, metallic in (('glass', .14, 0), ('metal', .48, .65), ('roof', .95, 0)):
        material = Material('city-'+name)
        material.setBaseColor((1, 1, 1, 1))
        material.setRoughness(rough)
        material.setMetallic(metallic)
        materials[name] = material
    models = []
    for family, (width, depth, floors, color) in enumerate(SPECS):
        model = parent.attachNewNode('city-building-'+str(family))
        model.setTag('city-footprint', f'{width} {depth}')
        lod = model.attachNewNode(FadeLODNode('city-building-lod'))
        lod.node().setFadeTime(.35)
        lod.node().setFadeStateOverride(10)
        height = floors*3.1
        for detailed, limits in ((True, (240, 0)), (False, (1800, 240))):
            level = lod.attachNewNode('city-near' if detailed else 'city-far')
            mesh = BuildingMesh()
            setback = family in (1, 3)
            levels = ((width, depth, floors-1, 0), (width-4, depth-4, 1, floors-1)) if setback else (
                (width, depth, floors, 0),)
            for w, d, count, first in levels:
                for normal, along, extent in ((Vec3(-1, 0, 0), Vec3(0, -1, 0), d),
                                              (Vec3(1, 0, 0), Vec3(0, 1, 0), d),
                                              (Vec3(0, -1, 0), Vec3(1, 0, 0), w),
                                              (Vec3(0, 1, 0), Vec3(-1, 0, 0), w)):
                    facade(mesh, normal, along, Vec3(normal.x*w/2, normal.y*d/2, 0),
                           extent, count, color, family, detailed, first)
            if setback:
                z = (floors-1)*3.1
                mesh.box('stone', (0, 0, z-.04), (width/2+.12, depth/2+.12, .10), STONE)
                for side in (-1, 1):
                    mesh.box('trim', (side*width/2, 0, z+.40), (.10, depth/2, .4), color)
                    mesh.box('trim', (0, side*depth/2, z+.40), (width/2, .10, .4), color)
                roof_width, roof_depth = width-4, depth-4
            else:
                roof_width, roof_depth = width, depth
            mesh.box('roof', (0, 0, height-.06), (roof_width/2, roof_depth/2, .08), (.045, .047, .044, 1))
            for side in (-1, 1):
                mesh.box('trim', (side*roof_width/2, 0, height+.23), (.13, roof_depth/2+.13, .24), color)
                mesh.box('trim', (0, side*roof_depth/2, height+.23), (roof_width/2, .13, .24), color)
                mesh.box('stone', (side*roof_width/2, 0, height+.49), (.17, roof_depth/2+.17, .045), STONE)
                mesh.box('stone', (0, side*roof_depth/2, height+.49), (roof_width/2, .17, .045), STONE)
            mesh.box('plaster', (width*.16, depth*.15, height+.82), (2.05, 2.3, .82), color)
            mesh.box('stone', (width*.16, depth*.15, height+1.68), (2.18, 2.43, .07), STONE)
            for unit in range(2):
                mesh.box('metal', (-width*.22, -depth*.16+unit*2.2, height+.40),
                         (.7, .65, .4), (.21, .23, .22, 1))
            if not detailed:
                # 远景微细金属不再单独绘制；几何/顶点色保留，合入粗糙收边材质。
                vertices, faces = mesh.parts['trim']
                for name in ('stone', 'metal', 'roof'):
                    source_vertices, source_faces = mesh.parts.pop(name)
                    offset = len(vertices)
                    vertices.extend(source_vertices)
                    faces.extend(tuple(i+offset for i in face) for face in source_faces)
            mesh.attach(level, materials)
            lod.node().addSwitch(*limits)
        models.append(model)
    # 石墙直到城市段才可见；让既有prepareScene在加载时准备三张贴图和同一shader。
    preparation = parent.attachNewNode('city-masonry-prepare')
    preparation.hide()
    mesh = BuildingMesh()
    mesh.quad('masonry', ((0, 0, 0), (1.5, 0, 0), (1.5, 0, 1.5), (0, 0, 1.5)), STONE)
    mesh.attach(preparation, {'masonry': surface})
    # prepareScene只遍历TextureAttrib，不准备ShaderInput中的纹理；隐藏样面显式携带数据图。
    for name, (load, _mean, _scale, _variation, _strength) in _SURFACE_SETTINGS.items():
        for channel, texture in zip(('diffuse', 'normal', 'roughness'), load()[1:], strict=True):
            preparation.setTexture(TextureStage('city-prepare-'+name+'-'+channel), texture)
    return tuple(models)

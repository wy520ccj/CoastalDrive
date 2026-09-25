"""Visual scene only; all moving transforms come from simulation snapshots."""

import math
from functools import lru_cache

import gltf
from panda3d.core import (
    AmbientLight,
    DirectionalLight,
    Filename,
    Fog,
    Geom,
    GeomNode,
    GeomTriangles,
    GeomVertexData,
    GeomVertexFormat,
    GeomVertexWriter,
    Material,
    NodePath,
    PNMImage,
    Quat,
    Texture,
    TexturePool,
    Vec3,
    Vec4,
)

from coastal_map import (
    MAP_POINTS,
    RAIL_OFFSET,
    ROAD_WIDTH,
    SEA_LEVEL,
    map_length,
    map_meshes,
    offset_point,
    point_at,
    strip_mesh,
)
from coastal_visuals import _add_ridge, add_city, add_coastal_backdrop, add_streetlight
from highway_map import HIGHWAY_LENGTH
from highway_map import ROAD_WIDTH as HIGHWAY_ROAD_WIDTH
from highway_map import meshes as highway_meshes
from paths import resource_root
from skins import apply_skin, traffic_models, traffic_skins
from sky_dome import make_sky
from test_track import OBSTACLES, TRACK_X
from vehicle_visual import load_vehicle
from world_props import collision_box


def make_quad(
    name: str, center: Vec3, size_x: float, size_y: float, color: Vec4, z: float = 0.0
) -> NodePath:
    """Create a flat colored rectangle in the XY plane."""
    half_x = size_x / 2
    half_y = size_y / 2
    vertices = [
        (center.x - half_x, center.y - half_y, z),
        (center.x + half_x, center.y - half_y, z),
        (center.x + half_x, center.y + half_y, z),
        (center.x - half_x, center.y + half_y, z),
    ]
    return make_mesh(name, vertices, [(0, 1, 2), (0, 2, 3)], color)


def make_ribbon(
    name: str, points: list[Vec3], width: float, color: Vec4, z: float | None = 0.0
) -> NodePath:
    vertices: list[tuple[float, float, float]] = []
    count = len(points)
    for index, point in enumerate(points):
        previous = points[(index - 1) % count]
        following = points[(index + 1) % count]
        tangent = points[1] - points[0] if count == 2 else following - previous
        tangent.z = 0
        tangent.normalize()
        side = Vec3(-tangent.y, tangent.x, 0)
        left = point + side * (width / 2)
        right = point - side * (width / 2)
        height = point.z if z is None else z
        vertices.extend([(left.x, left.y, height), (right.x, right.y, height)])

    triangles = []
    for index in range(1 if count == 2 else count):
        next_index = (index + 1) % count
        left = index * 2
        right = left + 1
        next_left = next_index * 2
        next_right = next_left + 1
        triangles.extend([(left, right, next_right), (left, next_right, next_left)])
    return make_mesh(name, vertices, triangles, color)


def make_cylinder(
    name: str, center: Vec3, radius: float, height: float, color: Vec4, sides: int = 10
) -> NodePath:
    vertices = []
    for z in (0.0, height):
        for index in range(sides):
            angle = 2 * math.pi * index / sides
            vertices.append(
                (
                    center.x + radius * math.cos(angle),
                    center.y + radius * math.sin(angle),
                    center.z + z,
                )
            )
    triangles = []
    for index in range(sides):
        next_index = (index + 1) % sides
        triangles.extend(
            [
                (index, next_index, sides + next_index),
                (index, sides + next_index, sides + index),
            ]
        )
    return make_mesh(name, vertices, triangles, color)


def make_cone(
    name: str, center: Vec3, radius: float, height: float, color: Vec4, sides: int = 10
) -> NodePath:
    vertices = []
    for index in range(sides):
        angle = 2 * math.pi * index / sides
        vertices.append(
            (center.x + radius * math.cos(angle), center.y + radius * math.sin(angle), center.z)
        )
    vertices.append((center.x, center.y, center.z + height))
    tip = len(vertices) - 1
    triangles = []
    for index in range(sides):
        triangles.append((index, (index + 1) % sides, tip))
    return make_mesh(name, vertices, triangles, color)


def make_mesh(
    name: str,
    vertices: list[tuple[float, float, float]],
    triangles: list[tuple[int, int, int]],
    color: Vec4,
) -> NodePath:
    format = GeomVertexFormat.getV3n3c4t2()
    data = GeomVertexData(name, format, Geom.UHStatic)
    vertex_writer = GeomVertexWriter(data, "vertex")
    normal_writer = GeomVertexWriter(data, "normal")
    color_writer = GeomVertexWriter(data, "color")
    uv_writer = GeomVertexWriter(data, "texcoord")
    primitive = GeomTriangles(Geom.UHStatic)
    for index, triangle in enumerate(triangles):
        a, b, c = [Vec3(*vertices[i]) for i in triangle]
        normal = (b - a).cross(c - a).normalized()
        for point in (a, b, c):
            vertex_writer.addData3f(point)
            normal_writer.addData3f(normal)
            color_writer.addData4f(*color)
            uv_writer.addData2f(point.x / 2.5, point.y / 2.5)
        primitive.addVertices(index * 3, index * 3 + 1, index * 3 + 2)
    geom = Geom(data)
    geom.addPrimitive(primitive)
    node = GeomNode(name)
    node.addGeom(geom)
    result = NodePath(node)
    material = Material()
    material.setBaseColor((1, 1, 1, 1))
    material.setRoughness(0.9)
    material.setMetallic(0)
    result.setMaterial(material)
    return result


@lru_cache(maxsize=1)
def asphalt_texture():
    path = resource_root() / "assets/game/materials/asphalt_floor_diff_2k.jpg"
    texture = TexturePool.loadTexture(Filename.fromOsSpecific(str(path)))
    texture.setWrapU(Texture.WMRepeat)
    texture.setWrapV(Texture.WMRepeat)
    texture.setMinfilter(Texture.FTLinearMipmapLinear)
    texture.setAnisotropicDegree(8)
    return texture


@lru_cache(maxsize=1)
def ground_texture():
    path = resource_root() / "assets/game/materials/grass_ground_diff_2k.jpg"
    texture = TexturePool.loadTexture(Filename.fromOsSpecific(str(path)))
    texture.setWrapU(Texture.WMRepeat)
    texture.setWrapV(Texture.WMRepeat)
    texture.setMinfilter(Texture.FTLinearMipmapLinear)
    texture.setAnisotropicDegree(8)
    return texture


@lru_cache(maxsize=1)
def water_texture():
    pixels = PNMImage(256, 256, 3)
    for y in range(256):
        for x in range(256):
            u, v = x / 256, y / 256
            long_wave = math.sin(math.tau * (u * 3 + math.sin(math.tau * v * 2) * 0.22))
            cross_wave = math.sin(math.tau * (v * 5 + u * 0.14))
            glint = max(0.0, math.sin(math.tau * (u * 11 + v * 7)) - 0.96)
            tone = 0.82 + long_wave * 0.055 + cross_wave * 0.018
            pixels.setXel(
                x,
                y,
                min(1, tone * 0.70 + glint * 0.18),
                min(1, tone * 0.87 + glint * 0.13),
                min(1, tone * 0.98 + glint * 0.04),
            )
    texture = Texture("water-ripples")
    texture.load(pixels)
    texture.setWrapU(Texture.WMRepeat)
    texture.setWrapV(Texture.WMRepeat)
    texture.setMinfilter(Texture.FTLinearMipmapLinear)
    return texture


@lru_cache(maxsize=1)
def cliff_texture():
    """Small tileable hand-made limestone texture, separate from grass and asphalt."""
    pixels = PNMImage(256, 256, 3)
    for y in range(256):
        for x in range(256):
            u, v = x / 256, y / 256
            strata = math.sin(math.tau * (v * 6 + math.sin(math.tau * u * 2) * 0.12))
            grain = math.sin(math.tau * (u * 17 + v * 13)) * math.sin(math.tau * (v * 19 - u * 7))
            value = 0.71 + strata * 0.055 + grain * 0.025
            pixels.setXel(x, y, value, value * 0.83, value * 0.65)
    texture = Texture("warm-limestone")
    texture.load(pixels)
    texture.setWrapU(Texture.WMRepeat)
    texture.setWrapV(Texture.WMRepeat)
    texture.setMinfilter(Texture.FTLinearMipmapLinear)
    texture.setAnisotropicDegree(4)
    return texture


def make_box(name, half_size, color):
    x, y, z = half_size
    vertices = [
        (-x, -y, -z),
        (x, -y, -z),
        (x, y, -z),
        (-x, y, -z),
        (-x, -y, z),
        (x, -y, z),
        (x, y, z),
        (-x, y, z),
    ]
    faces = [
        (0, 3, 2),
        (0, 2, 1),
        (4, 5, 6),
        (4, 6, 7),
        (0, 1, 5),
        (0, 5, 4),
        (1, 2, 6),
        (1, 6, 5),
        (2, 3, 7),
        (2, 7, 6),
        (3, 0, 4),
        (3, 4, 7),
    ]
    return make_mesh(name, vertices, faces, color)


class Scene:
    WHEEL_NAMES = (
        "wheel-front-left",
        "wheel-front-right",
        "wheel-back-left",
        "wheel-back-right",
    )

    def __init__(self, base):
        self.base = base
        self.render = base.render.attachNewNode("coastal-scene")
        self.segment_nodes = {}
        self.endless_surface_templates = {}
        self.endless_tree_templates = []
        self.endless_bush_template = None
        self.endless_templates = None
        self.ocean = None
        self.track_points = [Vec3(point.x, point.y, point.z) for point in MAP_POINTS]
        self.setup_lighting()
        self.setup_scene()
        self.sky = make_sky(base, self.render)

    def setup_lighting(self) -> None:
        coastal = self.base.session.simulation.track == "coastal"
        ambient = AmbientLight("coastal-ambient")
        ambient.setColor((0.29, 0.35, 0.40, 1) if coastal else (0.18, 0.22, 0.28, 1))
        self.ambient_path = self.render.attachNewNode(ambient)
        self.render.setLight(self.ambient_path)

        sun = DirectionalLight("coastal-sun")
        sun_color = (1.78, 1.52, 1.27, 1) if coastal else (2.6, 2.35, 1.9, 1)
        sun.setColor(sun_color)
        sun.setShadowCaster(True, 2048, 2048)
        sun.getLens().setFilmSize(95, 95)
        sun.getLens().setNearFar(10, 300)
        self.sun_path = self.render.attachNewNode(sun)
        self.render.setLight(self.sun_path)
        rail_sun = DirectionalLight("rail-sun")
        rail_sun.setColor(sun_color)
        self.rail_sun_path = self.render.attachNewNode(rail_sun)
        self.update_lighting(Vec3(TRACK_X, 0, 0))
        sky_color = (0.55, 0.76, 0.84) if coastal else (0.55, 0.73, 0.82)
        self.base.setBackgroundColor(*sky_color)
        fog = Fog("coastal-haze")
        fog.setColor(*sky_color)
        fog.setExpDensity(0.0008 if coastal else 0.0015)
        self.render.setFog(fog)

    def update_lighting(self, position):
        self.sun_path.setPos(position + Vec3(-55, -75, 125))
        self.sun_path.lookAt(position)
        self.rail_sun_path.setPos(self.sun_path.getPos())
        self.rail_sun_path.setHpr(self.sun_path.getHpr())

    def stabilize_rail(self, node):
        # 护栏保留太阳光照，但不接收低分辨率阴影图在细边缘上的自阴影。
        node.setLightOff(1)
        node.setLight(self.ambient_path, 1)
        node.setLight(self.rail_sun_path, 1)

    def setup_scene(self) -> None:
        self.ocean = make_quad(
            "ocean", Vec3(0, 0, 0), 1800, 1800, Vec4(0.045, 0.42, 0.61, 1), SEA_LEVEL
        )
        self.ocean.setTexture(water_texture())
        self.ocean.setLightOff(1)
        self.ocean.reparentTo(self.render)
        track = self.base.session.simulation.track
        if track == "endless":
            self.setup_endless()
        elif track == "test":
            make_quad(
                "test-ground", Vec3(0), 3000, 3000, Vec4(0.2, 0.31, 0.13, 1), -0.01
            ).reparentTo(self.render)
            self.add_test_field()
        elif self.base.session.simulation.track == "highway":
            self.setup_highway()
        else:
            colors = {
                "road": (0.075, 0.09, 0.11, 1),
                "inner-shoulder": (0.44, 0.41, 0.33, 1),
                "outer-shoulder": (0.44, 0.41, 0.33, 1),
                "island": (0.19, 0.32, 0.13, 1),
                "cliff": (0.32, 0.29, 0.23, 1),
                "inner-rail": (0.60, 0.64, 0.66, 1),
                "outer-rail": (0.60, 0.64, 0.66, 1),
            }
            for name, (vertices, triangles) in map_meshes().items():
                mesh = make_mesh(name, vertices, triangles, Vec4(*colors[name]))
                if name == "road":
                    mesh.setTexture(asphalt_texture())
                elif name == "island":
                    mesh.setTexture(ground_texture())
                elif name == "cliff":
                    mesh.setTexture(cliff_texture())
                elif "rail" in name:
                    self.stabilize_rail(mesh)
                mesh.reparentTo(self.render)
            self.add_map_details()
            self.add_start_grid()
            self.add_environment()
            add_coastal_backdrop(self.render, make_mesh, make_box, make_cylinder, make_cone)
        # Batch static road markings and barriers before adding the moving car.
        if track != "endless":
            self.render.flattenStrong()
        self.player, self.wheels = load_vehicle(self.render, self.base.vehicle_model_id)
        model = self.player.getChild(0)
        apply_skin(model, self.base.skin_index)
        self.traffic = []
        self.traffic_wheels = []
        self.traffic_signals = []
        traffic_count = len(self.base.session.simulation.snapshot().traffic)
        for model_id, skin in zip(
            traffic_models(self.base.session.seed, traffic_count),
            traffic_skins(self.base.session.seed, traffic_count),
        ):
            car, wheels = load_vehicle(self.render, model_id)
            apply_skin(car.getChild(0), skin)
            self.traffic.append(car)
            self.traffic_wheels.append(wheels)
            lights = []
            for side in (-1, 1):
                lamp = make_box("turn-signal", (0.12, 0.025, 0.055), Vec4(1, 0.55, 0.02, 1))
                lamp.reparentTo(car)
                lamp.setPos(side * 0.58, -2.07, 0.35)
                lamp.setLightOff()
                lamp.hide()
                lights.append(lamp)
            self.traffic_signals.append(lights)

    def setup_highway(self):
        for name, (vertices, triangles) in highway_meshes().items():
            color = Vec4(0.45, 0.42, 0.34, 1)
            if name == "highway-road":
                color = Vec4(0.075, 0.09, 0.11, 1)
            elif name == "highway-ground":
                color = Vec4(0.20, 0.31, 0.13, 1)
            elif "rail" in name:
                color = Vec4(0.62, 0.66, 0.68, 1)
            node = make_mesh(name, vertices, triangles, color)
            if name == "highway-road":
                node.setTexture(asphalt_texture())
            elif name == "highway-ground":
                node.setTexture(ground_texture())
            elif "rail" in name:
                self.stabilize_rail(node)
            node.reparentTo(self.render)
        for x in (-HIGHWAY_ROAD_WIDTH / 6, HIGHWAY_ROAD_WIDTH / 6):
            for y in range(0, int(HIGHWAY_LENGTH), 8):
                make_quad(
                    "highway-lane-mark",
                    Vec3(x, y, 0.035),
                    0.12,
                    4,
                    Vec4(0.94, 0.82, 0.35, 1),
                    0.035,
                ).reparentTo(self.render)
        for y in range(20, int(HIGHWAY_LENGTH), 40):
            for x in (-8.35, 8.35):
                self.add_road_post(self.render, (x, y, 0.46))
        self.add_environment()
        add_city(self.render, make_box, (-95, 210))
        for i in range(5):
            _add_ridge(self.render, make_mesh, (-260, i * 220, -3), 160, 65 + i * 5, i + 70, True)

    def add_road_post(self, parent, position):
        post = make_box("roadside-post", (0.09, 0.09, 0.46), Vec4(0.89, 0.88, 0.8, 1))
        post.setPos(*position)
        post.reparentTo(parent)
        reflector = make_box("roadside-reflector", (0.1, 0.1, 0.055), Vec4(1, 0.66, 0.13, 1))
        reflector.setPos(position[0], position[1], position[2] + 0.26)
        reflector.reparentTo(parent)

    def setup_endless(self):
        """Build reusable endless-road templates and the initially streamed segments."""
        from highway_segments import SEGMENT_LENGTH, surface_meshes

        self.highway_scenery = self.render.attachNewNode("highway-scenery")
        add_city(self.highway_scenery, make_box, (-95, 240))
        for i in range(5):
            _add_ridge(
                self.highway_scenery,
                make_mesh,
                (-310, i * 230 - 200, -3),
                160,
                65 + i * 5,
                i + 70,
                True,
            )
        self.highway_scenery.flattenStrong()
        self.endless_templates = self.render.attachNewNode("endless-templates")
        self.endless_templates.hide()
        self.endless_tree_templates = [
            self.load_model("nature/tree_pineTallA.glb"),
            self.load_model("nature/tree_pineTallB.glb"),
        ]
        for template in self.endless_tree_templates:
            template.reparentTo(self.endless_templates)
        self.endless_bush_template = self.load_model("nature/plant_bushLargeTriangle.glb")
        self.endless_bush_template.reparentTo(self.endless_templates)
        if self.base.session.simulation.road.curve:
            self.sync_segments()
            return
        colors = {
            "road": Vec4(0.075, 0.09, 0.11, 1),
            "ground": Vec4(0.20, 0.31, 0.13, 1),
            "shoulder": Vec4(0.45, 0.42, 0.34, 1),
        }
        for name, (vertices, triangles) in surface_meshes().items():
            color = colors.get(name, colors["ground"])
            if name.startswith("shoulder"):
                color = colors["shoulder"]
            elif name.startswith("rail"):
                color = Vec4(0.62, 0.66, 0.68, 1)
            node = make_mesh(f"endless-template-{name}", vertices, triangles, color)
            if name == "road":
                node.setTexture(asphalt_texture())
            elif name == "ground":
                node.setTexture(ground_texture())
            elif name.startswith("rail"):
                self.stabilize_rail(node)
            node.reparentTo(self.endless_templates)
            self.endless_surface_templates[name] = node
        for side in (-1, 1):
            for local_y in range(0, SEGMENT_LENGTH, 8):
                marker = make_quad(
                    "endless-lane-mark",
                    Vec3(side * 2.25, local_y, 0.035),
                    0.12,
                    4,
                    Vec4(0.94, 0.82, 0.35, 1),
                    0.035,
                )
                marker.reparentTo(self.endless_templates)
        self.sync_segments()

    def sync_segments(self):
        """Mirror the simulation's currently visible global segment window."""
        simulation = self.base.session.simulation
        stream = getattr(simulation, "stream", None)
        if stream is None:
            return
        import curve_mesh
        from highway_segments import SEGMENT_LENGTH, segment

        segments = stream.segments
        for index in tuple(self.segment_nodes):
            if index not in segments:
                self.segment_nodes.pop(index).removeNode()
        for index in segments:
            root = self.segment_nodes.get(index)
            if root is None:
                root = self.render.attachNewNode(f"endless-segment-{index}")
                if stream.curve:
                    colors = {
                        "road": Vec4(0.075, 0.09, 0.11, 1),
                        "ground": Vec4(0.20, 0.31, 0.13, 1),
                    }
                    for name, (vertices, triangles) in stream.meshes[index].items():
                        color = colors.get(
                            name,
                            Vec4(0.62, 0.66, 0.68, 1)
                            if name.startswith("rail")
                            else Vec4(0.45, 0.42, 0.34, 1),
                        )
                        node = make_mesh(name, vertices, triangles, color)
                        if name == "road":
                            node.setTexture(asphalt_texture())
                        elif name == "ground":
                            node.setTexture(ground_texture())
                        elif name.startswith("rail"):
                            self.stabilize_rail(node)
                        node.reparentTo(root)
                    for vertices, triangles in curve_mesh.markings(stream.curve, index):
                        make_mesh(
                            "lane-mark", vertices, triangles, Vec4(0.94, 0.82, 0.35, 1)
                        ).reparentTo(root)
                    for local_y in range(20, SEGMENT_LENGTH, 40):
                        for lateral in (-8.35, 8.35):
                            self.add_road_post(
                                root, curve_mesh.point(stream.curve, index, local_y, lateral, 0.46)
                            )
                    for local_y in range(20, SEGMENT_LENGTH, 40):
                        add_streetlight(
                            root, make_box, curve_mesh.point(stream.curve, index, local_y, 9, 0)
                        )
                    for number, (position, scale, heading) in enumerate(
                        curve_mesh.trees(stream.curve, simulation.seed, index)
                    ):
                        tree = self.endless_tree_templates[(index + number) % 2].copyTo(root)
                        tree.show()
                        tree.setPos(*position)
                        tree.setScale(scale)
                        tree.setH(heading)
                        if number % 2 == 0:
                            bush = self.endless_bush_template.copyTo(root)
                            bush.show()
                            bush.setPos(position[0] + 1.8, position[1] + 2, position[2])
                            bush.setScale(4)
                    root.flattenStrong()
                    self.segment_nodes[index] = root
                    x, y, z = curve_mesh.anchor(stream.curve, index)
                    root.setPos(x, y - simulation.origin_y, z)
                    continue
                for template in self.endless_surface_templates.values():
                    template.copyTo(root).show()
                for template in self.render.findAllMatches("endless-templates/endless-lane-mark"):
                    template.copyTo(root).show()
                for local_y in range(20, SEGMENT_LENGTH, 40):
                    for lateral in (-8.35, 8.35):
                        self.add_road_post(root, (lateral, local_y, 0.46))
                    add_streetlight(root, make_box, (9, local_y, 0))
                trees = segment(simulation.seed, index).trees
                for number, (x, local_y, scale, heading) in enumerate(trees):
                    tree = self.endless_tree_templates[(index + number) % 2].copyTo(root)
                    tree.show()
                    tree.setPos(x, local_y, -0.32 + 0.05 * scale)
                    tree.setScale(scale)
                    tree.setH(heading)
                    if number % 2 == 0:
                        bush = self.endless_bush_template.copyTo(root)
                        bush.show()
                        bush.setPos(x + 1.8, local_y + 2, -0.32)
                        bush.setScale(4)
                root.flattenStrong()
                self.segment_nodes[index] = root
            if stream.curve:
                x, y, z = curve_mesh.anchor(stream.curve, index)
                root.setPos(x, y - simulation.origin_y, z)
            else:
                root.setY(index * SEGMENT_LENGTH - simulation.origin_y)

    def add_test_field(self):
        asphalt = Vec4(0.075, 0.085, 0.095, 1)
        make_quad("acceleration-straight", Vec3(95, 350, 0), 14, 750, asphalt, 0.025).reparentTo(
            self.render
        )
        make_quad("handling-pad", Vec3(96, 42.5, 0), 68, 125, asphalt, 0.026).reparentTo(
            self.render
        )
        make_quad("long-test-straight", Vec3(180, 550, 0), 20, 1300, asphalt, 0.025).reparentTo(
            self.render
        )
        for x in (88.3, 101.7):
            make_quad(
                "white-edge", Vec3(x, 350, 0), 0.14, 745, Vec4(0.88, 0.87, 0.77, 1), 0.045
            ).reparentTo(self.render)
        for y in range(0, 701, 10):
            make_quad(
                "distance-dash", Vec3(95, y, 0), 0.15, 3, Vec4(0.92, 0.7, 0.23, 1), 0.048
            ).reparentTo(self.render)
        for x in range(89, 102):
            for y in (6, 7):
                shade = 0.92 if (x + y) % 2 else 0.045
                make_quad(
                    "start-grid", Vec3(x, y, 0), 1, 1, Vec4(shade, shade, shade, 1), 0.06
                ).reparentTo(self.render)
        for obstacle in OBSTACLES:
            color = (
                Vec4(0.15, 0.18, 0.20, 1) if obstacle.name == "ramp" else Vec4(0.9, 0.24, 0.05, 1)
            )
            node = make_box(obstacle.name, obstacle.half_size, color)
            node.setPos(*obstacle.center)
            node.setP(obstacle.pitch)
            node.reparentTo(self.render)
        for y in range(20, 701, 20):
            for x in (87, 103):
                post = make_box("road-post", (0.09, 0.09, 0.5), Vec4(0.92, 0.9, 0.8, 1))
                post.setPos(x, y, 0.5)
                post.reparentTo(self.render)

    def add_start_grid(self):
        for row in range(2):
            a, b = point_at(row * 0.7), point_at((row + 1) * 0.7)
            for column in range(12):
                inner = -ROAD_WIDTH / 2 + column * ROAD_WIDTH / 12
                outer = inner + ROAD_WIDTH / 12
                vertices = [
                    offset_point(a, inner, 0.025),
                    offset_point(a, outer, 0.025),
                    offset_point(b, outer, 0.025),
                    offset_point(b, inner, 0.025),
                ]
                shade = 0.92 if (row + column) % 2 else 0.045
                tile = make_mesh(
                    "start-grid", vertices, [(0, 1, 2), (0, 2, 3)], Vec4(shade, shade, shade, 1)
                )
                tile.setDepthOffset(2)
                tile.reparentTo(self.render)

    def add_map_details(self):
        for side in (-1, 1):
            edge = side * (ROAD_WIDTH / 2 - 0.18)
            vertices, triangles = strip_mesh(edge - 0.07, edge + 0.07, 0.025, 0.025)
            make_mesh("white-edge", vertices, triangles, Vec4(0.91, 0.91, 0.82, 1)).reparentTo(
                self.render
            )
        for distance in range(0, int(map_length()), 10):
            points = [point_at(distance), point_at(distance + 3)]
            make_ribbon(
                "centre-dash",
                [Vec3(p.x, p.y, p.z + 0.025) for p in points],
                0.16,
                Vec4(0.97, 0.78, 0.27, 1),
                None,
            ).reparentTo(self.render)
            for side in (-1, 1):
                p = points[0]
                marker = make_box("reflector", (0.04, 0.18, 0.14), Vec4(0.97, 0.86, 0.5, 1))
                marker.setPos(*offset_point(p, side * (RAIL_OFFSET - 0.14), 0.59))
                marker.setHpr(p.heading, p.grade, 0)
                marker.reparentTo(self.render)
        # Short curb blocks give nearby, fixed-scale references at driving speed.
        for i, p in enumerate(MAP_POINTS):
            q = MAP_POINTS[(i + 1) % len(MAP_POINTS)]
            for side in (-1, 1):
                low, high = sorted((side * ROAD_WIDTH / 2, side * (ROAD_WIDTH / 2 + 0.38)))
                vertices = [
                    offset_point(p, low, 0.02),
                    offset_point(p, high, 0.02),
                    offset_point(q, high, 0.02),
                    offset_point(q, low, 0.02),
                ]
                color = Vec4(0.75, 0.19, 0.10, 1) if i % 2 else Vec4(0.83, 0.80, 0.67, 1)
                make_mesh("curb-paint", vertices, [(0, 1, 2), (0, 2, 3)], color).reparentTo(
                    self.render
                )

    def add_environment(self):
        for number, (prop, z) in enumerate(self.base.session.simulation.props):
            if prop.kind.startswith("checkpoint"):
                if self.base.session.mode.value == "free_drive":
                    continue
                half, height = collision_box(prop)
                node = make_box(prop.kind, half, Vec4(0.15, 0.76, 0.86, 1))
                node.setPos(prop.x, prop.y, z + height)
                node.setH(prop.heading)
            else:
                filename = "nature/rock_largeA.glb"
                if prop.kind == "tree":
                    filename = (
                        "nature/tree_pineTallB.glb"
                        if number % 3 == 0
                        else "nature/tree_pineTallA.glb"
                    )
                node = self.load_model(filename)
                node.setScale(prop.scale)
                node.setPos(prop.x, prop.y, z)
                node.setH(prop.heading)
            node.reparentTo(self.render)

    def load_model(self, filename: str) -> NodePath:
        path = resource_root() / "assets" / "game" / filename
        root = NodePath(filename)
        model = NodePath(gltf.load_model(Filename.fromOsSpecific(str(path))))
        model.reparentTo(root)
        # Kenney GLBs face -Y after import; the simulation root always faces +Y.
        model.setH(180)
        return root

    def apply(self, state):
        if self.base.session.simulation.track == "endless":
            self.sync_segments()
            if self.ocean is not None:
                self.ocean.setY(state.player.position[1])
        self.player.setPos(*state.player.position)
        self.player.setHpr(state.player.heading, state.player.pitch, state.player.roll)
        for node, wheel in zip(self.wheels, state.player.wheels):
            node.setPos(*wheel.position)
            node.setQuat(Quat(*wheel.orientation))
        for node, wheels, car in zip(self.traffic, self.traffic_wheels, state.traffic):
            node.setPos(*car.position)
            node.setHpr(car.heading, car.pitch, car.roll)
            if car.active:
                node.show()
                for wheel_node, wheel in zip(wheels, car.wheels):
                    wheel_node.setPos(*wheel.position)
                    wheel_node.setQuat(Quat(*wheel.orientation))
                    wheel_node.show()
            else:
                node.hide()
                for wheel_node in wheels:
                    wheel_node.hide()
        for lights, car in zip(self.traffic_signals, state.traffic):
            for side, lamp in zip((-1, 1), lights):
                if (
                    car.active
                    and (car.hazards or car.signal == side)
                    and int(state.time * 2.5) % 2 == 0
                ):
                    lamp.show()
                else:
                    lamp.hide()

    def close(self):
        self.sky.removeNode()
        self.render.removeNode()
